"""Cover art for AX notes (Pillow). Output: assets/ax/cover/<slug>-<lang>.webp, 1200x900.

The cover sits in the note's hero, a band of the topic's tint (build.py: the note's .hero becomes the band;
assets/ax.css .ax-note; on phones the art comes after the title). It carries no text: the title, lead and date are HTML on the band, so they stay readable, indexable
and translatable. The art is the note's own figures (tools/ax_figures.py) laid out as two cards on the band colour,
so every cover restates numbers that are already in the note and adds no claim of its own.

usage: python tools/ax_cover.py [--only <slug>]   # prints "<path> <w>x<h> <size>" per file
"""
import glob
import json
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1200, 900
OUT_DIR = os.path.join(ROOT, "assets/ax/cover")
MAX_BYTES = 160 * 1024

# Transparent ground (2026-11-13 rebrand): the band colour comes from assets/ax.css .ax-t-<topic> (--cover), light or
# dark with the reader's colour scheme, so the same file sits on both bands; only the figure cards and their soft
# shadows are drawn.


def hex2rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def p(*parts): return os.path.join(ROOT, *parts)


def note_topics():
    return json.load(open(p("data/ax.json"), encoding="utf-8"))["notes"]


def figure_files(slug, lang):
    """The note's figures in page order (the page lists them; fall back to files on disk)."""
    page = p("ax" if lang == "ko" else "en/ax", slug, "index.html")
    srcs = re.findall(r'<img\b[^>]*\bsrc="/assets/ax/(%s-\d+-%s\.webp)"' % (re.escape(slug), lang),
                      open(page, encoding="utf-8").read()) if os.path.exists(page) else []
    if not srcs:
        srcs = sorted(os.path.basename(f) for f in glob.glob(p("assets/ax", f"{slug}-[0-9]*-{lang}.webp")))
    out = []
    for s in srcs:
        if s not in out: out.append(s)
    return [p("assets/ax", s) for s in out]


def card(src, width, radius=22):
    im = Image.open(src).convert("RGB")
    h = round(im.height * width / im.width)
    im = im.resize((width, h), Image.LANCZOS)
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=255)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def place(base, c, x, y, angle):
    """Paste card c rotated by angle with a soft shadow; (x, y) is the centre."""
    pad = 60
    layer = Image.new("RGBA", (c.width + 2 * pad, c.height + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((pad, pad + 18, pad + c.width, pad + c.height + 18), radius=26, fill=(26, 30, 36, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(22))
    layer.alpha_composite(sh)
    layer.alpha_composite(c, (pad, pad))
    layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    base.alpha_composite(layer, (round(x - layer.width / 2), round(y - layer.height / 2)))


def fit(c, max_w, max_h):
    s = min(max_w / c.width, max_h / c.height, 1.0)
    return c if s == 1.0 else c.resize((round(c.width * s), round(c.height * s)), Image.LANCZOS)


def cover(slug, lang, topic):
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # topic is kept for callers; the band colour is CSS
    figs = figure_files(slug, lang)
    if not figs:
        return None
    if len(figs) >= 2:
        back = fit(card(figs[1], 820), 860, 560)
        place(base, back, W * .60, H * .36, -5)
    front = fit(card(figs[0], 900), 940, 640 if len(figs) >= 2 else 720)
    place(base, front, W * .46 if len(figs) >= 2 else W * .5, H * .60 if len(figs) >= 2 else H * .5, 2.5 if len(figs) >= 2 else 0)
    return base


def save(img, out):
    for q in (84, 78, 70, 62):
        img.save(out, "WEBP", quality=q, method=6)
        if os.path.getsize(out) <= MAX_BYTES: return
    raise SystemExit(f"{out}: {os.path.getsize(out)} B > {MAX_BYTES} B")


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    os.makedirs(OUT_DIR, exist_ok=True)
    missing = []
    for slug, topic in note_topics().items():
        if only and slug != only: continue
        for lang in ("ko", "en"):
            if not os.path.exists(p("ax" if lang == "ko" else "en/ax", slug, "index.html")): continue
            img = cover(slug, lang, topic)
            if img is None:
                missing.append(f"{slug}-{lang}"); continue
            out = os.path.join(OUT_DIR, f"{slug}-{lang}.webp")
            save(img, out)
            print(os.path.relpath(out, ROOT).replace("\\", "/"), f"{W}x{H}", os.path.getsize(out))
    if missing:
        print("NO FIGURES (no cover):", ", ".join(missing)); sys.exit(1)


if __name__ == "__main__":
    main()
