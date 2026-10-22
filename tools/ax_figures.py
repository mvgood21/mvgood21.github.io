"""Figures for AX notes, drawn from data/ax-figures.json (Pillow). Output: assets/ax/<slug>-<n>-<lang>.webp, 1200 px wide.

Every number in a figure must already be in the note's text (the figure restates it; it never adds a claim).
A note shows a figure with:
  <figure class="ax-fig"><img src="/assets/ax/<slug>-<n>-<lang>.webp" width="1200" height="<h>" alt="..." loading="lazy">
  <figcaption>...</figcaption></figure>
build.py puts these images into the note's Article JSON-LD and the image sitemap (ax_extras.figures).

Spec: data/ax-figures/<slug>.json holds a list of figures, text per language under "ko"/"en"
(unit is appended as written: "개", "ms", " MB"; optional "alt" and "caption" feed --html):
  {"kind": "bars", "ko": {"title", "unit", "note", "items": [[label, value, "hi"?], ...]}, "en": {...}}
  {"kind": "steps", "ko": {"title", "note", "items": [[label, text], ...]}, "en": {...}}       # timeline / procedure
  {"kind": "compare", "ko": {"title", "note", "left": [head, [lines]], "right": [head, [lines]]}, "en": {...}}

usage: python tools/ax_figures.py [--only <slug>]   # (re)draw figures; prints "<path> <w>x<h> <size>" per file
       python tools/ax_figures.py --html <slug>   # print the <figure> markup to paste (ko and en)
"""
import html
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_EB = os.path.join(ROOT, "tools/fonts/nanumsquareeb.ttf")
FONT_R = os.path.join(ROOT, "tools/fonts/nanumsquarer.ttf")
PAPER, FILL, INK, INK2, LINE, ACCENT, SOFT = ((246, 248, 251), (238, 241, 245), (20, 32, 51), (75, 86, 104),
                                              (220, 226, 234), (20, 32, 51), (176, 186, 201))
W, PAD = 1200, 64
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
        return self.im.crop((0, 0, W, self.y))


def title_block(c, d):
    c.text(d["title"], font(True, 40), gap=12); c.y += 18


def note_block(c, d):
    if d.get("note"):
        c.y += 14; c.dr.line((PAD, c.y, W - PAD, c.y), fill=LINE, width=2); c.y += 20
        c.text(d["note"], font(False, 24), INK2, gap=8)


def draw_bars(d):
    c = Canvas(); title_block(c, d)
    items = d["items"]; f_l, f_v = font(False, 28), font(True, 28)
    label_w = min(420, max(c.dr.textlength(str(x[0]), font=f_l) for x in items) + 24)
    vals = [float(x[1]) for x in items]; top = max(vals) or 1
    bar_x, bar_w = PAD + label_w, W - 2 * PAD - label_w - 190
    for x in items:
        hi = len(x) > 2 and x[2] == "hi"
        lines = wrap(c.dr, x[0], f_l, label_w - 24); y0 = c.y
        for i, line in enumerate(lines): c.dr.text((PAD, y0 + i * 36), line, font=f_l, fill=INK)
        h = max(44, len(lines) * 36)
        w = max(18, int(bar_w * float(x[1]) / top))
        c.dr.rounded_rectangle((bar_x, y0, bar_x + w, y0 + 40), radius=8, fill=ACCENT if hi else SOFT)
        c.dr.text((bar_x + w + 16, y0 + 4), fmt(x[1]) + d.get("unit", ""), font=f_v, fill=INK)
        c.y = y0 + h + 22
    note_block(c, d)
    return c.done()


def draw_steps(d):
    c = Canvas(); title_block(c, d)
    f_k, f_t = font(True, 28), font(False, 28)
    n = len(d["items"])
    for i, (k, t) in enumerate(d["items"]):
        y0 = c.y; cx = PAD + 22
        c.dr.ellipse((cx - 22, y0, cx + 22, y0 + 44), fill=ACCENT)
        num = str(i + 1); c.dr.text((cx - c.dr.textlength(num, font=f_k) / 2, y0 + 7), num, font=f_k, fill=PAPER)
        c.y = y0 + 4; c.text(k, f_k, INK, x=PAD + 70, width=W - 2 * PAD - 70, gap=8)
        c.text(t, f_t, INK2, x=PAD + 70, width=W - 2 * PAD - 70, gap=8)
        if i < n - 1: c.dr.line((cx, y0 + 50, cx, c.y + 14), fill=LINE, width=4)
        c.y += 22
    note_block(c, d)
    return c.done()


def draw_compare(d):
    c = Canvas(); title_block(c, d)
    col = (W - 2 * PAD - 32) // 2; f_h, f_t = font(True, 30), font(False, 27)
    y0 = c.y; heights = []
    for j, (head, lines) in enumerate((d["left"], d["right"])):
        x = PAD + j * (col + 32)
        tmp = Canvas(); tmp.y = 0
        tmp.text(head, f_h, width=col - 48); tmp.y += 10
        for line in lines: tmp.text("· " + line, f_t, INK2, width=col - 48, gap=8); tmp.y += 6
        heights.append(tmp.y)
    box_h = max(heights) + 56
    for j, (head, lines) in enumerate((d["left"], d["right"])):
        x = PAD + j * (col + 32)
        c.dr.rounded_rectangle((x, y0, x + col, y0 + box_h), radius=16, fill=FILL if j == 0 else (226, 232, 241),
                               outline=LINE if j == 0 else ACCENT, width=2 if j == 0 else 3)
        c.y = y0 + 28; c.text(head, f_h, x=x + 24, width=col - 48); c.y += 10
        for line in lines: c.text("· " + line, f_t, INK2, x=x + 24, width=col - 48, gap=8); c.y += 6
    c.y = y0 + box_h + 24
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


if __name__ == "__main__":
    if "--html" in sys.argv: figure_html(sys.argv[sys.argv.index("--html") + 1])
    else: render_all(sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None)
