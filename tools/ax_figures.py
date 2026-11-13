"""Figures for AX notes, drawn from data/ax-figures.json (Pillow). Output: assets/ax/<slug>-<n>-<lang>.webp, 1200 px wide.

Every number in a figure must already be in the note's text (the figure restates it; it never adds a claim).
A note shows a figure with:
  <figure class="ax-fig"><img src="/assets/ax/<slug>-<n>-<lang>.webp" width="1200" height="<h>" alt="..." loading="lazy">
  <figcaption>...</figcaption></figure>
build.py puts these images into the note's Article JSON-LD (ax_extras.figures).

Spec: data/ax-figures/<slug>.json holds a list of figures, text per language under "ko"/"en"
(unit is appended as written: "개", "ms", " MB"; optional "alt" and "caption" feed --html):
  {"kind": "bars", "ko": {"title", "unit", "note", "items": [[label, value, "hi"?], ...]}, "en": {...}}
  {"kind": "steps", "ko": {"title", "note", "items": [[label, text], ...]}, "en": {...}}       # timeline / procedure
  {"kind": "compare", "ko": {"title", "note", "left": [head, [lines]], "right": [head, [lines]]}, "en": {...}}

Look (2026-11-13 rebrand): bars are Summit Blue, "hi" bars Honey; steps are blue markers with the last in Honey;
compare has a neutral left card and a blue right card. Text that names a bar colour must name these ("노란 막대",
"the honey bars"); the run fails on the old palette's words (STALE_COLOUR) in a spec or a note's figure.

usage: python tools/ax_figures.py [--only <slug>]   # (re)draw figures; prints "<path> <w>x<h> <size>" per file
       python tools/ax_figures.py --html <slug>   # print the <figure> markup to paste (ko and en)
       python tools/ax_figures.py --sync-html     # set width/height of every /assets/ax/<file>.webp <img> in
                                                  # ax/*/index.html and en/ax/*/index.html to the file's pixel size
"""
import glob
import html
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glyphcheck  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_EB = os.path.join(ROOT, "tools/fonts/nanumsquareeb.ttf")
FONT_R = os.path.join(ROOT, "tools/fonts/nanumsquarer.ttf")
# Palette: SugarMount Design System v2, "Summit Blue + Honey" (assets/site.css --sds-*, tools/og.py MARK_*; rebrand
# 2026-11-13). The figure carries its own white ground, so it reads the same on light and dark pages (assets/ax.css
# dims it a little on dark pages) and as a card on the cover band (tools/ax_cover.py).
PAPER = (255, 255, 255)                                         # --sds-ref-white
INK, INK2, INK3 = (26, 30, 36), (86, 91, 98), (118, 123, 129)   # ink-900, ink-600, ink-400
LINE, AXIS = (217, 223, 230), (197, 203, 210)                   # line-200, line-300
BLUE, BLUE_DEEP = (21, 108, 221), (14, 89, 186)                 # --sds-bg-accent-solid, --sds-fg-accent
BLUE_WEAK, BLUE_TINT = (242, 247, 255), (191, 214, 246)         # --sds-bg-accent-weak; timeline connector
HONEY = (255, 184, 72)                                          # --sds-bg-sugar-solid (ink text on it: 10.9:1)
FILL, FILL_HEAD = (244, 246, 249), (230, 234, 239)              # neutral card and its header band
ACCENT = BLUE
W, PAD, STRIPE = 1200, 64, 8
SPEC_DIR = os.path.join(ROOT, "data/ax-figures")


def font(bold, size): return ImageFont.truetype(FONT_EB if bold else FONT_R, size)


def wrap(dr, text, f, width):
    """Wrap on spaces; a word longer than the line (Korean without spaces) is split by characters."""
    lines, cur = [], ""
    for word in str(text).split(" "):
        test = (cur + " " + word).strip()
        if dr.textlength(test, font=f) <= width:
            cur = test; continue
        if cur: lines.append(cur)
        cur = ""
        for ch in word:
            if dr.textlength(cur + ch, font=f) > width and cur: lines.append(cur); cur = ch
            else: cur += ch
    if cur: lines.append(cur)
    return lines


def fmt(v):
    return f"{v:,}" if isinstance(v, int) else (f"{v:,.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v))


class Canvas:
    """Draws top to bottom on a tall scratch image, then crops to the used height."""
    def __init__(self):
        self.im = Image.new("RGB", (W, 4000), PAPER); self.dr = ImageDraw.Draw(self.im); self.y = PAD

    def text(self, s, f, fill=INK, x=PAD, width=W - 2 * PAD, gap=10):
        for line in wrap(self.dr, s, f, width):
            self.dr.text((x, self.y), line, font=f, fill=fill); self.y += f.size + gap
        return self

    def done(self):
        self.y += PAD - 16
        # brand stripe along the top edge: Summit Blue with a Honey tab over the start of the text column
        self.dr.rectangle((0, 0, W, STRIPE - 1), fill=BLUE)
        self.dr.rectangle((PAD, 0, PAD + 96, STRIPE - 1), fill=HONEY)
        return self.im.crop((0, 0, W, self.y))


def title_block(c, d):
    c.text(d["title"], font(True, 40), gap=12); c.y += 18


def note_block(c, d):
    if d.get("note"):
        c.y += 14; c.dr.line((PAD, c.y, W - PAD, c.y), fill=LINE, width=2); c.y += 20
        c.text(d["note"], font(False, 24), INK2, gap=8)


def draw_bars(d):
    """Horizontal bars from a zero axis, length proportional to the value, value label at the bar's end. "hi" items
    are Honey, the rest Summit Blue; when any item is highlighted, the others' label and value step back to muted ink."""
    c = Canvas(); title_block(c, d)
    items = d["items"]; f_l, f_v = font(False, 28), font(True, 28)
    is_hi = [len(x) > 2 and x[2] == "hi" for x in items]; any_hi = any(is_hi)
    label_w = min(420, max(c.dr.textlength(str(x[0]), font=f_l) for x in items) + 24)
    vtxt = [fmt(x[1]) + d.get("unit", "") for x in items]
    vals = [max(0.0, float(x[1])) for x in items]; top = max(vals) or 1
    bar_x = PAD + label_w
    bar_w = W - PAD - bar_x - max(c.dr.textlength(t, font=f_v) for t in vtxt) - 18
    bar_h, line_h = 38, 36
    y_top = c.y - 10
    for x, hi, vt, v in zip(items, is_hi, vtxt, vals):
        lines = wrap(c.dr, x[0], f_l, label_w - 24); y0 = c.y
        tone = INK if (hi or not any_hi) else INK2
        for i, line in enumerate(lines): c.dr.text((PAD, y0 + 4 + i * line_h), line, font=f_l, fill=tone)
        w = round(bar_w * v / top)
        if w > 0:
            w = max(w, 6)
            c.dr.rounded_rectangle((bar_x, y0, bar_x + w, y0 + bar_h), radius=min(8, w // 2),
                                   fill=HONEY if hi else BLUE, corners=(False, True, True, False))
        c.dr.text((bar_x + w + 14, y0 + 4), vt, font=f_v, fill=tone)
        c.y = y0 + max(bar_h + 6, len(lines) * line_h) + 20
    c.dr.line((bar_x - 1, y_top, bar_x - 1, c.y - 10), fill=AXIS, width=2)   # zero axis
    note_block(c, d)
    return c.done()


def draw_steps(d):
    """Numbered timeline: Summit Blue markers joined by a tint line; the last step (where it ends up) in Honey."""
    c = Canvas(); title_block(c, d)
    f_k, f_t, f_n = font(True, 28), font(False, 27), font(True, 26)
    n, r = len(d["items"]), 24
    cx, tx = PAD + r, PAD + 2 * r + 30
    for i, (k, t) in enumerate(d["items"]):
        y0 = c.y; last = i == n - 1
        c.dr.ellipse((cx - r, y0, cx + r, y0 + 2 * r), fill=HONEY if last else BLUE)
        c.dr.text((cx, y0 + r + 1), str(i + 1), font=f_n, fill=INK if last else PAPER, anchor="mm")
        c.y = y0 + 5; c.text(k, f_k, INK, x=tx, width=W - PAD - tx, gap=8)
        c.text(t, f_t, INK2, x=tx, width=W - PAD - tx, gap=8)
        c.y = max(c.y, y0 + 2 * r) + 20
        if not last: c.dr.line((cx, y0 + 2 * r + 8, cx, c.y - 8), fill=BLUE_TINT, width=4)
    note_block(c, d)
    return c.done()


def draw_compare(d):
    """Two cards side by side: the left in neutral grey, the right (the after, the answer) in Summit Blue with a solid
    header band. Both cards share one header height and one body height."""
    c = Canvas(); title_block(c, d)
    gap = 32; col = (W - 2 * PAD - gap) // 2; f_h, f_t = font(True, 30), font(False, 27)
    inner, ind, hp, bp, lh, bg = col - 48, 22, 18, 22, 35, 8
    sides = (d["left"], d["right"])
    heads = [wrap(c.dr, head, f_h, inner) for head, _ in sides]
    bodies = [[wrap(c.dr, line, f_t, inner - ind) for line in lines] for _, lines in sides]
    head_h = max(len(h) for h in heads) * 40 - 10 + 2 * hp
    body_h = max(sum(len(b) * lh + bg for b in body) - bg for body in bodies) + 2 * bp
    y0 = c.y
    for j in (0, 1):
        x = PAD + j * (col + gap); right = j == 1
        box = (x, y0, x + col, y0 + head_h + body_h)
        c.dr.rounded_rectangle(box, radius=16, fill=BLUE_WEAK if right else FILL)
        c.dr.rounded_rectangle((x, y0, x + col, y0 + head_h), radius=16, fill=BLUE if right else FILL_HEAD,
                               corners=(True, True, False, False))
        c.dr.rounded_rectangle(box, radius=16, outline=BLUE if right else LINE, width=3 if right else 2)
        off = (head_h - 2 * hp - (len(heads[j]) * 40 - 10)) // 2   # a shorter head sits centred in the shared band
        for i, line in enumerate(heads[j]):
            c.dr.text((x + 24, y0 + hp + off + i * 40), line, font=f_h, fill=PAPER if right else INK)
        yy = y0 + head_h + bp
        for b in bodies[j]:
            c.dr.ellipse((x + 24, yy + 11, x + 34, yy + 21), fill=BLUE if right else INK3)
            for i, line in enumerate(b):
                c.dr.text((x + 24 + ind, yy + i * lh), line, font=f_t, fill=INK if right else INK2)
            yy += len(b) * lh + bg
    c.y = y0 + head_h + body_h + 24
    note_block(c, d)
    return c.done()


DRAW = {"bars": draw_bars, "steps": draw_steps, "compare": draw_compare}


def out_path(slug, n, lang): return f"assets/ax/{slug}-{n}-{lang}.webp"


def load(only=None):
    out = {}
    for fn in sorted(os.listdir(SPEC_DIR)) if os.path.isdir(SPEC_DIR) else []:
        slug = fn[:-len(".json")]
        if fn.endswith(".json") and (only is None or slug == only):
            out[slug] = json.load(open(os.path.join(SPEC_DIR, fn), encoding="utf-8"))
    return out


def render_all(only=None):
    spec = load(only)
    os.makedirs(os.path.join(ROOT, "assets/ax"), exist_ok=True)
    sizes = {}
    for slug, figs in spec.items():
        for n, fig in enumerate(figs, 1):
            for lang in ("ko", "en"):
                im = DRAW[fig["kind"]](fig[lang])
                rp = out_path(slug, n, lang)
                full = os.path.join(ROOT, rp)
                buf = __import__("io").BytesIO(); im.save(buf, "WEBP", quality=82, method=6)
                data = buf.getvalue()
                old = open(full, "rb").read() if os.path.exists(full) else None
                if old != data: open(full, "wb").write(data)
                sizes[rp] = im.size
                print(rp, f"{im.size[0]}x{im.size[1]}", f"{len(data) // 1024} KB")
    return sizes


def figure_html(slug):
    spec = load(slug)[slug]
    for lang in ("ko", "en"):
        print(f"--- {lang}")
        for n, fig in enumerate(spec, 1):
            rp = out_path(slug, n, lang)
            w, h = Image.open(os.path.join(ROOT, rp)).size
            d = fig[lang]
            print(f'      <figure class="ax-fig"><img src="/{rp}" width="{w}" height="{h}" alt="{html.escape(d.get("alt", d["title"]))}" '
                  f'loading="lazy"><figcaption>{html.escape(d.get("caption", d["title"]), quote=False)}</figcaption></figure>')


IMG_RE = re.compile(r'<img\b[^>]*>')
SRC_RE = re.compile(r'\ssrc="/assets/ax/([^"/]+\.webp)"')


def _set_size(tag, w, h):
    """Set width/height on one <img> tag; every other byte of the tag stays as it was."""
    add = ""
    for name, val in (("width", w), ("height", h)):
        new, n = re.subn(r'(\s%s=")[^"]*(")' % name, lambda m: f"{m.group(1)}{val}{m.group(2)}", tag, count=1)
        if n: tag = new
        else: add += f' {name}="{val}"'   # missing: added right after src (checks.py IMG-SIZE wants both)
    if add:
        end = SRC_RE.search(tag).end(); tag = tag[:end] + add + tag[end:]
    return tag


def sync_html(root=None):
    """Rewrite width/height of every <img src="/assets/ax/<file>.webp"> in ax/*/index.html and en/ax/*/index.html to
    that file's pixel size. Idempotent; touches no other attribute or byte. Returns [(page, images changed)]."""
    root = root or ROOT
    sizes, changed, missing = {}, [], []
    pages = sorted(glob.glob(os.path.join(root, "ax", "*", "index.html")) +
                   glob.glob(os.path.join(root, "en", "ax", "*", "index.html")))
    for page in pages:
        with open(page, encoding="utf-8", newline="") as fh: src = fh.read()
        count = [0]

        def fix(m):
            tag = m.group(0); s = SRC_RE.search(tag)
            if not s: return tag
            f = os.path.join(root, "assets", "ax", s.group(1))
            if f not in sizes:
                sizes[f] = Image.open(f).size if os.path.exists(f) else None
            if sizes[f] is None:
                missing.append(f"{os.path.relpath(page, root)}: {s.group(1)}"); return tag
            new = _set_size(tag, *sizes[f])
            if new != tag: count[0] += 1
            return new
        out = IMG_RE.sub(fix, src)
        if out != src:
            with open(page, "w", encoding="utf-8", newline="") as fh: fh.write(out)
            changed.append((os.path.relpath(page, root).replace("\\", "/"), count[0]))
    for m in missing: print("MISSING", m)
    return changed


# Words for the pre-2026-11-13 palette (navy "hi" bars on grey ones). A spec or a note's figure that still says them
# describes a picture that no longer exists.
STALE_COLOUR = re.compile(r"(?:진한|짙은|어두운|검은|회색|옅은|연한)(?: 색)?(?: 짧은)? 막대|\b(?:dark(?:er)?|grey|gray|pale|black|"
                          r"light(?:er)?) bars?\b|\bdark ones\b", re.I)
FIG_BLOCK = re.compile(r'<figure class="ax-fig">.*?</figure>', re.S)


def stale_colour_words(root=None, only=None):
    root = root or ROOT
    out = []

    def walk(where, v):
        if isinstance(v, str):
            for m in STALE_COLOUR.finditer(v): out.append(f"{where}: {m.group(0)!r}")
        elif isinstance(v, (list, dict)):
            for x in (v.values() if isinstance(v, dict) else v): walk(where, x)
    sd = os.path.join(root, "data", "ax-figures")
    for fn in sorted(os.listdir(sd)) if os.path.isdir(sd) else []:
        if fn.endswith(".json") and (only is None or fn == only + ".json"):
            walk(f"data/ax-figures/{fn}", json.load(open(os.path.join(sd, fn), encoding="utf-8")))
    for page in sorted(glob.glob(os.path.join(root, "ax", "*", "index.html")) +
                       glob.glob(os.path.join(root, "en", "ax", "*", "index.html"))):
        if only and os.path.basename(os.path.dirname(page)) != only: continue
        for block in FIG_BLOCK.findall(open(page, encoding="utf-8").read()):
            walk(os.path.relpath(page, root).replace("\\", "/"), block)
    return out


if __name__ == "__main__":
    if "--html" in sys.argv: figure_html(sys.argv[sys.argv.index("--html") + 1])
    elif "--sync-html" in sys.argv:
        done = sync_html()
        for page, n in done: print(page, f"{n} img")
        print(f"sync-html: {len(done)} page(s) changed")
    else:
        glyphcheck.install()  # a rare syllable the font only pretends to have would print as a gap (tools/glyphcheck.py)
        only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
        render_all(only)
        ok = glyphcheck.report()
        stale = stale_colour_words(only=only)
        for s in stale: print("STALE COLOUR WORD (bars are blue, hi bars honey now):", s)
        if not ok or stale: sys.exit(1)
