#!/usr/bin/env python3
"""Make share images (1200x630) per app and language, the home share image and the site logo.

  python3 tools/og.py      # writes assets/og/<id>-<lang>.png, assets/og.png, assets/logo.png

Needs Pillow. Fonts: tools/fonts/NanumSquare (SIL Open Font License, see tools/fonts/OFL.txt).
Run it after adding an app or changing an app's name or tagline in data/apps.json, then run build.py.
"""
import json, os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_EB = os.path.join(ROOT, "tools/fonts/nanumsquareeb.ttf")
FONT_R = os.path.join(ROOT, "tools/fonts/nanumsquarer.ttf")
PAPER, INK, INK2, LINE = (246, 248, 251), (20, 32, 51), (75, 86, 104), (220, 226, 234)
W, H = 1200, 630

def hex2rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def wrap(draw, text, font, width):
    lines, cur = [], ""
    for word in text.split(" "):
        test = (cur + " " + word).strip()
        if draw.textlength(test, font=font) <= width: cur = test
        else:
            if cur: lines.append(cur)
            cur = word
    if cur: lines.append(cur)
    return lines

def rounded_icon(path, size):
    im = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * .22), fill=255)
    im.putalpha(mask)
    return im

def cube(draw, x, y, s):
    """Isometric sugar cube mark; (x, y) is the top vertex, s the edge length."""
    top = [(x, y), (x + s * .87, y + s * .5), (x, y + s), (x - s * .87, y + s * .5)]
    left = [(x - s * .87, y + s * .5), (x, y + s), (x, y + s * 2), (x - s * .87, y + s * 1.5)]
    right = [(x + s * .87, y + s * .5), (x, y + s), (x, y + s * 2), (x + s * .87, y + s * 1.5)]
    draw.polygon(top, fill=(230, 244, 241)); draw.polygon(left, fill=(15, 118, 110)); draw.polygon(right, fill=(11, 79, 74))

def footer(draw, f):
    cube(draw, 92, 548, 20)
    draw.text((128, 556), "SugarMount", font=f, fill=INK)
    draw.text((W - 80, 556), "mvgood21.github.io", font=f, fill=INK2, anchor="ra")

def app_card(app, lang, out):
    d = app[lang]
    accent = hex2rgb(app["accent"])
    img = Image.new("RGB", (W, H), PAPER)
    dr = ImageDraw.Draw(img)
    dr.rectangle((0, 0, W, 14), fill=accent)
    icon = rounded_icon(os.path.join(ROOT, app["icon"].lstrip("/") + ".png"), 220)
    img.paste(icon, (80, 120), icon)
    f_name, f_tag, f_small = ImageFont.truetype(FONT_EB, 68), ImageFont.truetype(FONT_R, 36), ImageFont.truetype(FONT_EB, 28)
    x, y, width = 350, 128, W - 350 - 80
    for line in wrap(dr, d["name"], f_name, width)[:2]:
        dr.text((x, y), line, font=f_name, fill=INK); y += 84
    if d.get("brand") and d["brand"] != d["name"]:
        dr.text((x, y), d["brand"], font=f_small, fill=accent); y += 48
    y += 14
    for line in wrap(dr, d["tagline"], f_tag, width)[:3]:
        dr.text((x, y), line, font=f_tag, fill=INK2); y += 52
    dr.line((80, 520, W - 80, 520), fill=LINE, width=2)
    footer(dr, f_small)
    img.save(out, optimize=True)

def home_card(apps, out):
    img = Image.new("RGB", (W, H), PAPER)
    dr = ImageDraw.Draw(img)
    f_big, f_tag, f_small = ImageFont.truetype(FONT_EB, 88), ImageFont.truetype(FONT_R, 36), ImageFont.truetype(FONT_EB, 28)
    dr.text((80, 150), "SugarMount", font=f_big, fill=INK)
    for i, line in enumerate(["한 가지 일을 간단하게 하는", "Android 앱"]):
        dr.text((80, 270 + i * 52), line, font=f_tag, fill=INK2)
    # the mountain of icons
    rows, k, n, order = [], 1, len(apps), apps[:]
    while n > 0: rows.append(min(k, n)); n -= k; k += 1
    size, gap, cx, y, i = 84, 12, 900, 70, 0
    for r in rows:
        total = r * size + (r - 1) * gap
        x = cx - total // 2
        for a in order[i:i + r]:
            ic = rounded_icon(os.path.join(ROOT, a["icon"].lstrip("/") + ".png"), size)
            img.paste(ic, (x, y), ic); x += size + gap
        i += r; y += size + gap
    dr.line((80, 520, W - 80, 520), fill=LINE, width=2)
    footer(dr, f_small)
    img.save(out, optimize=True)

def logo(out):
    s = 512
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    dr.rounded_rectangle((0, 0, s - 1, s - 1), radius=112, fill=PAPER + (255,))
    cube(dr, s / 2, 86, 170)
    img.save(out, optimize=True)

def main():
    apps = json.load(open(os.path.join(ROOT, "data/apps.json"), encoding="utf-8"))["apps"]
    os.makedirs(os.path.join(ROOT, "assets/og"), exist_ok=True)
    for a in apps:
        for lang in ("ko", "en"):
            app_card(a, lang, os.path.join(ROOT, f"assets/og/{a['id']}-{lang}.png"))
    order = sorted(apps, key=lambda a: (a["status"] != "live", apps.index(a)))
    home_card(order, os.path.join(ROOT, "assets/og.png"))
    logo(os.path.join(ROOT, "assets/logo.png"))
    print("ok", len(apps) * 2 + 2)

if __name__ == "__main__":
    main()
