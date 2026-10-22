#!/usr/bin/env python3
"""Make the site's images: brand mark files, share cards and per-app representative images.

  python3 tools/og.py          # writes everything listed below, then checks every image
  python3 tools/og.py --svg    # prints the 3-cube mark as inline SVG (for build.py BRAND_MARK)
  python3 tools/og.py --articles   # only the help-article images (after adding or changing an article)

Writes
  assets/favicon.png (64), favicon.ico (32+48, site root), assets/apple-touch-icon.png (180),
  assets/logo.png (512)                       3-cube mountain mark (SDS 6.0.3)
  assets/og/app-<id>-<lang>.png               app pages: real screenshots on a neutral ground, no text
  assets/og/article-<id>-<slug>-<16x9|4x3|1x1>-<lang>.png   help articles: the article's largest real
                                              screen on a neutral ground, no text (IA 3.2(4)); ≤ 200 KB
  assets/og.png, assets/og/home-en.png        home text cards, ko and en (icon mountain); --home writes only these
  assets/og/hub-apps-<lang>.png               /apps/ text card
  assets/og/about-<lang>.png                  /about/ text card
  assets/og/ax-<lang>.png, ax-<slug>-<lang>.png   AX hub and one card per AX note (title read from its <h1>)
  assets/og/privacy-<lang>.png                privacy pages (shared card until per-policy cards exist)

Text cards carry the mark; app images never carry text or a logo (Google/Naver representative-image
guidance). Screenshots come from assets/apps/<id>/ as listed in data/apps.json (real Play captures);
the marketing caption band of each capture is cropped off (CROP table).
Needs Pillow. Fonts: tools/fonts/NanumSquare (SIL Open Font License, see tools/fonts/OFL.txt).
Run it after adding an app, changing its screenshots or icon, adding an AX note or changing a title.
"""
import glob, hashlib, html, json, os, re, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glyphcheck  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_EB = os.path.join(ROOT, "tools/fonts/nanumsquareeb.ttf")
FONT_R = os.path.join(ROOT, "tools/fonts/nanumsquarer.ttf")
PAPER, FILL, INK, INK2, LINE = (246, 248, 251), (238, 241, 245), (20, 32, 51), (75, 86, 104), (220, 226, 234)
W, H = 1200, 630
DOMAIN = "mvgood21.github.io"

# Brand mark colours = site.css --sds-mark-* (light). build.py BRAND_MARK must use the same values.
MARK_TOP, MARK_LEFT, MARK_RIGHT, MARK_EDGE = "#FFFFFF", "#142033", "#4B5668", "#142033"

def hex2rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def p(*parts): return os.path.join(ROOT, *parts)

# ---------- 3-cube mountain mark ----------
K = 0.8660254

def cube_faces(x, y, s):
    """Isometric cube; (x, y) top vertex, s edge length. Returns top, left, right face polygons."""
    top = [(x, y), (x + s * K, y + s * .5), (x, y + s), (x - s * K, y + s * .5)]
    left = [(x - s * K, y + s * .5), (x, y + s), (x, y + s * 2), (x - s * K, y + s * 1.5)]
    right = [(x + s * K, y + s * .5), (x, y + s), (x, y + s * 2), (x + s * K, y + s * 1.5)]
    return top, left, right

def mark_cubes(cx, y0, s):
    """Two cubes below, one on top: top cube's lower side vertices sit on the bottom cubes' top vertices.
    Bounding box: width 2*sqrt(3)*s, height 3.5*s, top vertex at (cx, y0)."""
    yb = y0 + 1.5 * s
    return [cube_faces(cx - s * K, yb, s), cube_faces(cx + s * K, yb, s), cube_faces(cx, y0, s)]

def mark_image(size, pad=0.1, bg=None, radius=0.0):
    """RGBA mark of size x size px (supersampled). bg: tile colour or None (transparent)."""
    ss = 8 if size < 128 else 4
    S = size * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    if bg:
        if radius: dr.rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * radius), fill=bg + (255,))
        else: dr.rectangle((0, 0, S, S), fill=bg + (255,))
    inner = S * (1 - 2 * pad)
    s = inner / 3.5                       # height 3.5 s is the limiting side (width 3.46 s)
    y0 = (S - 3.5 * s) / 2
    lw = max(1, round(s * .09))
    top_c, left_c, right_c, edge_c = (hex2rgb(c) for c in (MARK_TOP, MARK_LEFT, MARK_RIGHT, MARK_EDGE))
    for top, left, right in mark_cubes(S / 2, y0, s):
        dr.polygon(left, fill=left_c); dr.polygon(right, fill=right_c); dr.polygon(top, fill=top_c)
        hexa = [top[0], top[1], right[3], right[2], left[3], top[3]]
        dr.line(hexa + hexa[:2], fill=edge_c, width=lw, joint="curve")   # overlap the start so no end cap shows
    return img.resize((size, size), Image.LANCZOS)

def mark_svg():
    """Inline SVG for build.py BRAND_MARK; colours via classes (SDS 6.0.3), e.g. .brand-mark .t{fill:var(--sds-mark-top)}."""
    s = 28 / 3.5; y0 = 2.0
    f = lambda pts: "M" + " ".join(f"{x:.2f} {y:.2f}".replace(".00", "") for x, y in pts) + "Z"
    out = ['<svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true">']
    for top, left, right in mark_cubes(16, y0, s):
        hexa = [top[0], top[1], right[3], right[2], left[3], top[3]]
        out += [f'<path class="l" d="{f(left)}"/>', f'<path class="r" d="{f(right)}"/>',
                f'<path class="t" d="{f(top)}"/>',
                f'<path class="e" d="{f(hexa)}" fill="none" stroke-width="1.1" stroke-linejoin="round"/>']
    out.append("</svg>")
    return "".join(out)

def brand_files():
    mark_image(64, pad=.08, bg=PAPER, radius=.22).save(p("assets/favicon.png"), optimize=True)
    m48, m32 = mark_image(48, pad=.07, bg=PAPER, radius=.22), mark_image(32, pad=.06, bg=PAPER, radius=.22)
    m48.save(p("favicon.ico"), format="ICO", sizes=[(48, 48), (32, 32)], append_images=[m32])
    mark_image(180, pad=.14, bg=PAPER).convert("RGB").save(p("assets/apple-touch-icon.png"), optimize=True)
    mark_image(512, pad=.14, bg=PAPER, radius=.22).save(p("assets/logo.png"), optimize=True)
    return ["assets/favicon.png", "favicon.ico", "assets/apple-touch-icon.png", "assets/logo.png"]

# ---------- helpers ----------
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

def rounded(im, radius):
    im = im.convert("RGBA")
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=radius, fill=255)
    im.putalpha(mask)
    return im

def rounded_icon(path, size):
    return rounded(Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS), int(size * .22))

def icon_path(a): return p(a["icon"].lstrip("/") + ".png")

def footer(img, dr, f):
    m = mark_image(44, pad=0)
    img.paste(m, (80, 548), m)
    dr.text((136, 556), "SugarMount", font=f, fill=INK)
    dr.text((W - 80, 556), DOMAIN, font=f, fill=INK2, anchor="ra")

# ---------- app representative images (no text, no logo) ----------
# Store captures carry a marketing caption band; drop it so the image shows only the app screen.
# (top, bottom) fractions of the capture height, checked by eye against every shot in assets/apps.
CROP = {"sugarcompress": (.19, 0), "sugarflip": (.19, 0), "sugarconvert": (.19, 0), "sugardoc": (.172, 0),
        "arrows": (.135, 0), "blocks": (.13, 0), "sugaralbum": (.16, 0), "sugarcard": (.22, 0),
        "sugarspeller": (0, 0), "sugarclip": (.26, 0)}
CROP_SHOT = {"/assets/apps/sugaralbum/shot2.webp": (0, .145)}   # caption at the bottom
# sugarspeller: the caption band (with outdated "최대 4000자" copy) was cut off the source files themselves (top 160 px)

def caption_crop(app_id, src, im):
    top, bottom = CROP_SHOT.get(src, CROP.get(app_id, (0, 0)))
    return im.crop((0, round(im.height * top), im.width, im.height - round(im.height * bottom)))

def shot_list(a, lang):
    ko = [s["src"] for s in a["ko"].get("shots", [])]
    own = [s["src"] for s in a[lang].get("shots", [])] or ko
    pick = own[:3]
    if lang == "en" and own[:3] == ko[:3]:      # same captures in both languages: vary the order
        pick = own[1:3] + own[:1]
    return pick

def app_image(a, lang, out):
    shots = []
    for src in shot_list(a, lang):
        im = Image.open(p(src.lstrip("/"))).convert("RGB")
        shots.append(caption_crop(a["id"], src, im))
    gap, side, vpad = 36, 72, 40
    ar = [s.width / s.height for s in shots]
    hh = min(H - 2 * vpad, (W - 2 * side - gap * (len(shots) - 1)) / sum(ar))
    ws = [round(hh * r) for r in ar]; hh = round(hh)
    img = Image.new("RGB", (W, H), PAPER)
    x = (W - sum(ws) - gap * (len(shots) - 1)) // 2
    y = (H - hh) // 2
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    xs = []
    for w in ws:
        sd.rounded_rectangle((x, y + 8, x + w, y + hh + 8), radius=22, fill=INK + (40,))
        xs.append(x); x += w + gap
    img.paste(shadow.filter(ImageFilter.GaussianBlur(14)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(14)))
    dr = ImageDraw.Draw(img)
    for s, w, x in zip(shots, ws, xs):
        r = rounded(s.resize((w, hh), Image.LANCZOS), 20)
        img.paste(r, (x, y), r)
        dr.rounded_rectangle((x, y, x + w - 1, y + hh - 1), radius=20, outline=LINE, width=2)
    save_png_budget(img, out)

# ---------- text cards ----------
def text_card(out, eyebrow, title, sub, art=None, text_w=None):
    img = Image.new("RGB", (W, H), PAPER)
    dr = ImageDraw.Draw(img)
    f_eye, f_title, f_sub, f_small = (ImageFont.truetype(FONT_EB, 30), ImageFont.truetype(FONT_EB, 64),
                                      ImageFont.truetype(FONT_R, 34), ImageFont.truetype(FONT_EB, 28))
    width = text_w or W - 160
    t_lines = wrap(dr, title, f_title, width)
    if len(t_lines) > 3:
        f_title = ImageFont.truetype(FONT_EB, 52); t_lines = wrap(dr, title, f_title, width)[:4]
    s_lines = wrap(dr, sub, f_sub, width)[:3] if sub else []
    lh = f_title.size + 18
    block = 48 + len(t_lines) * lh + (16 + len(s_lines) * 50 if s_lines else 0)
    y = max(64, (520 - block) // 2)
    dr.text((80, y), eyebrow, font=f_eye, fill=INK2); y += 48
    for line in t_lines: dr.text((80, y), line, font=f_title, fill=INK); y += lh
    y += 16
    for line in s_lines: dr.text((80, y), line, font=f_sub, fill=INK2); y += 50
    if art: art(img, dr)
    dr.line((80, 520, W - 80, 520), fill=LINE, width=2)
    footer(img, dr, f_small)
    img.save(out, optimize=True)

def icon_mountain(apps, cx, top, size=84, gap=12):
    def draw(img, dr):
        rows, k, n = [], 1, len(apps)
        while n > 0: rows.append(min(k, n)); n -= k; k += 1
        y, i = top, 0
        for r in rows:
            x = cx - (r * size + (r - 1) * gap) // 2
            for a in apps[i:i + r]:
                ic = rounded_icon(icon_path(a), size); img.paste(ic, (x, y), ic); x += size + gap
            i += r; y += size + gap
    return draw

def icon_grid(apps, x0, y0, cols=4, size=92, gap=16):
    def draw(img, dr):
        for i, a in enumerate(apps):
            ic = rounded_icon(icon_path(a), size)
            img.paste(ic, (x0 + (i % cols) * (size + gap), y0 + (i // cols) * (size + gap)), ic)
    return draw

def big_mark(img, dr):
    m = mark_image(300, pad=0); img.paste(m, (W - 80 - 300, 100), m)

HOME_TAG = {"ko": ["한 가지 일을 간단하게 하는", "Android 앱"], "en": ["Small Android apps that", "each do one thing simply"]}

def home_card(apps, out, lang="ko"):
    img = Image.new("RGB", (W, H), PAPER)
    dr = ImageDraw.Draw(img)
    f_big, f_tag, f_small = ImageFont.truetype(FONT_EB, 88), ImageFont.truetype(FONT_R, 36), ImageFont.truetype(FONT_EB, 28)
    dr.text((80, 150), "SugarMount", font=f_big, fill=INK)
    for i, line in enumerate(HOME_TAG[lang]):
        dr.text((80, 270 + i * 52), line, font=f_tag, fill=INK2)
    icon_mountain(apps, 900, 44, size=74, gap=10)(img, dr)
    dr.line((80, 520, W - 80, 520), fill=LINE, width=2)
    footer(img, dr, f_small)
    img.save(out, optimize=True)

# ---------- help-article representative images (IA 3.2(4): one real step screen, no text, 3 ratios) ----------
ARTICLE_SIZES = {"16x9": (1200, 675), "4x3": (1200, 900), "1x1": (1200, 1200)}
ARTICLE_MAX_UPSCALE = 2.0      # captures are ~270-540 px wide; past 2x they only get blurrier, not more detailed
OG_MAX_BYTES = 200 * 1024      # IA 9.1 / checks.py BUDGET og_max

def main_imgs(path):
    """Screenshots inside <main> of an article, in page order: (src, file pixel area, aspect w/h)."""
    text = open(path, encoding="utf-8").read()
    m = re.search(r"<main\b.*?</main>", text, re.S)
    out = []
    for src in re.findall(r'<img\b[^>]*\bsrc="(/assets/apps/[^"]+)"', m.group(0) if m else ""):
        with Image.open(p(src.lstrip("/"))) as im: w, h = im.size
        out.append((src, w * h, w / h))
    return out

def article_shot(imgs, avoid=None):
    """The largest real screen in the article (ties: earlier wins); thin strips (notification bars) never.
    avoid: the src the ko page already uses, so ko/en images stay distinct when both share one capture."""
    cands = [i for i in imgs if 0.3 <= i[2] <= 2.2]
    pool = [i for i in cands if i[0] != avoid] or cands
    return max(pool, key=lambda i: (i[1], -imgs.index(i)))[0] if pool else None

def save_png_budget(img, out):
    """PNG under OG_MAX_BYTES: plain optimize first, then a 256-colour palette (dithered) if it is too big."""
    img.save(out, optimize=True)
    if os.path.getsize(out) > OG_MAX_BYTES:
        img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG).save(out, optimize=True)

def article_image(src, size, out, tight=False):
    """tight: the en page has no capture of its own and reuses ko's (e.g. one shared capture), so frame it
    closer (drop the status bar and bottom input row) to keep the two pages' images distinct."""
    cw, ch = size
    shot = Image.open(p(src.lstrip("/"))).convert("RGB")
    if tight: shot = shot.crop((0, round(shot.height * .06), shot.width, round(shot.height * .9)))
    pad = round(min(cw, ch) * .08)
    scale = min((cw - 2 * pad) / shot.width, (ch - 2 * pad) / shot.height, ARTICLE_MAX_UPSCALE)
    w, h = round(shot.width * scale), round(shot.height * scale)
    x, y = (cw - w) // 2, (ch - h) // 2
    rad = max(12, round(min(w, h) * .05))
    img = Image.new("RGB", (cw, ch), PAPER)
    shadow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((x, y + 10, x + w, y + h + 10), radius=rad, fill=INK + (40,))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    img.paste(shadow, (0, 0), shadow)
    r = rounded(shot.resize((w, h), Image.LANCZOS), rad)
    img.paste(r, (x, y), r)
    ImageDraw.Draw(img).rounded_rectangle((x, y, x + w - 1, y + h - 1), radius=rad, outline=LINE, width=2)
    save_png_budget(img, out)

def same_pixels(a, b):
    """True when two captures are the same file content (an -en.webp can be a byte copy of the -ko.webp)."""
    if not a or not b: return False
    if a == b: return True
    return open(p(a.lstrip("/")), "rb").read() == open(p(b.lstrip("/")), "rb").read()

def article_images(apps):
    """assets/og/article-<app id>-<slug>-<ratio>-<lang>.png for every help article apps/<app_path>/<slug>/ (ko and en)."""
    by_path = {a["app_path"]: a["id"] for a in apps if a.get("app_path")}
    files = []
    for ko_path in sorted(glob.glob(p("apps", "*", "*", "index.html"))):
        app_path, slug = ko_path.replace("\\", "/").split("/")[-3:-1]
        if app_path not in by_path: continue
        used = None
        for lang in ("ko", "en"):
            path = ko_path if lang == "ko" else p("en", "apps", app_path, slug, "index.html")
            if not os.path.exists(path): continue
            src = article_shot(main_imgs(path), avoid=used)
            if not src:
                print("NO SHOT", os.path.relpath(path, ROOT)); continue
            tight = lang == "en" and same_pixels(src, used)
            used = src
            for ratio, size in ARTICLE_SIZES.items():
                f = f"assets/og/article-{by_path[app_path]}-{slug}-{ratio}-{lang}.png"
                article_image(src, size, p(f), tight); files.append(f)
    return files

def h1_of(path):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", open(path, encoding="utf-8").read(), re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else None

# ---------- checks ----------
def check(files):
    seen, bad = {}, []
    for f in files:
        full = p(f)
        size = os.path.getsize(full)
        im = Image.open(full); w, h = im.size
        digest = hashlib.sha256(open(full, "rb").read()).hexdigest()
        is_og = f.startswith("assets/og")
        if is_og and (w < 150 or h < 150 or size < 5000 or max(w, h) / min(w, h) > 3):
            bad.append(f"{f}: {w}x{h} {size}B")
        if is_og and size > OG_MAX_BYTES:
            bad.append(f"{f}: {size}B > {OG_MAX_BYTES}B")
        if digest in seen: bad.append(f"{f}: same bytes as {seen[digest]}")
        seen[digest] = f
    return bad

def main():
    if "--svg" in sys.argv:
        print(mark_svg()); return
    apps = json.load(open(p("data/apps.json"), encoding="utf-8"))["apps"]
    os.makedirs(p("assets/og"), exist_ok=True)
    if "--home" in sys.argv:                     # only the home cards (assets/og.png = ko, assets/og/home-en.png)
        order = sorted(apps, key=lambda a: (a["status"] != "live", apps.index(a)))
        home_card(order, p("assets/og.png")); home_card(order, p("assets/og/home-en.png"), "en")
        files = ["assets/og.png", "assets/og/home-en.png"]; bad = check(files)
        for b in bad: print("CHECK FAIL", b)
        print("ok" if not bad else "failed", len(files), "files")
        if bad: sys.exit(1)
        return
    if "--articles" in sys.argv:                 # only the help-article images (after adding or changing an article)
        files = article_images(apps); bad = check(files)
        for b in bad: print("CHECK FAIL", b)
        print("ok" if not bad else "failed", len(files), "files")
        if bad: sys.exit(1)
        return
    files = brand_files()
    for a in apps:
        if not a["ko"].get("shots"): continue          # no screenshots (axfamily): no app image
        for lang in ("ko", "en"):
            f = f"assets/og/app-{a['id']}-{lang}.png"; app_image(a, lang, p(f)); files.append(f)
    files += article_images(apps)
    order = sorted(apps, key=lambda a: (a["status"] != "live", apps.index(a)))
    home_card(order, p("assets/og.png")); files.append("assets/og.png")          # ko home (and 404/design fallback)
    home_card(order, p("assets/og/home-en.png"), "en"); files.append("assets/og/home-en.png")  # en home: English tagline
    live = [a for a in apps if a["status"] == "live" and a.get("play")]
    n = len(live)
    cards = {
        "hub-apps": {"ko": ("앱", "Android 앱 전체 목록", f"Google Play에 낸 앱 {n}개를 사진·문서·글·게임 분야별로 모았습니다."),
                     "en": ("Apps", "All Android apps", f"{n} apps on Google Play, grouped by photo, document, text and games.")},
        "about": {"ko": ("소개", "SugarMount 소개", "개인 개발자 simpest가 운영하는 Android 앱 브랜드로, 한 가지 일을 하는 작은 앱을 만듭니다."),
                  "en": ("About", "About SugarMount", "An Android app brand run by independent developer simpest, making small apps that each do one job.")},
        "ax": {"ko": ("AX 노트", "AX 노트", "1인 앱 개발에 AI 코딩 에이전트를 쓰며 정한 규칙과 실제로 잰 숫자"),
               "en": ("AX notes", "AX notes", "Rules and measured numbers from building Android apps with an AI coding agent")},
        "privacy": {"ko": ("개인정보처리방침", "앱별 개인정보처리방침", "앱마다 수집하는 정보, 처리 위치, 보관·삭제 방법을 실제 코드 기준으로 설명합니다."),
                    "en": ("Privacy", "Privacy policies for each app", "What each app collects, where it is processed and how to delete it, written from the actual code.")},
    }
    for key, langs in cards.items():
        for lang, (eye, title, sub) in langs.items():
            f = f"assets/og/{key}-{lang}.png"
            art, tw = None, None
            if key == "hub-apps": art, tw = icon_grid(live, 700, 70, cols=4, size=88, gap=16), 560
            if key == "about": art, tw = big_mark, 640
            text_card(p(f), eye, title, sub, art, tw); files.append(f)
    for lang, base in (("ko", "ax"), ("en", "en/ax")):
        for path in sorted(glob.glob(p(base, "*", "index.html"))):
            slug = os.path.basename(os.path.dirname(path))
            title = h1_of(path)
            if not title: continue
            f = f"assets/og/ax-{slug}-{lang}.png"
            text_card(p(f), "AX 노트" if lang == "ko" else "AX notes", title, None); files.append(f)
    bad = check(files)
    for b in bad: print("CHECK FAIL", b)
    print("ok" if not bad else "failed", len(files), "files")
    if bad: sys.exit(1)

if __name__ == "__main__":
    glyphcheck.install()  # titles with a syllable the font only pretends to have would print as a gap (tools/glyphcheck.py)
    main()
    if not glyphcheck.report(): sys.exit(1)
