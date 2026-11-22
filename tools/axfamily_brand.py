#!/usr/bin/env python3
"""Copy AXFamily's brand assets from the app repository into this site (run again when the brand changes).

  python tools/axfamily_brand.py --axf <AXFamily checkout> [--font-mid <NanumSquare Bold .ttf>]
  python tools/axfamily_brand.py --axf <AXFamily checkout> --shots     # store screenshots only (after a re-shoot)

The brand's source of truth is the app repository (docs/brand/brand-guide.md, tools/store/make_icon.py and
make_brand.py; brand fixed 2026-11-09, symbol "lit window"). This script only reads that checkout and writes:

  assets/apps/axfamily/icon.png (192) and icon.webp (144)   copied byte for byte from tools/release/site/assets/
                                                            (make_icon.py output: rounded apricot tile, transparent corners)
  tools/brand/axfamily-lockup-{ko,en}.png                   the apricot lockup (bare symbol + "AXFamily" wordmark
                                                            + descriptor), drawn by make_brand.draw_lockup at T = 240 px,
                                                            tight, on Apricot. tools/og.py scales it into the share cards

--shots: docs/store/assets/screenshots/{ko,en}/NN.png (1080x1920 store captures with their caption band) ->
assets/apps/axfamily/shots/{ko,en}/NN.webp, 360 px wide, lossy (under checks.py BUDGET shot, 80 KB). screenshots.json
marks each language on its own (assets.<lang>, app repo since 2026-11-15): only the captures in assets.<lang>.publish
are copied (en has 01, 02, 07, 08 until its AI screens are re-shot with real model output), and a site copy of a
capture that language no longer publishes is removed. It refuses while a language's captures are older than the
captions (assets.<lang>.assets_storyboard != storyboard), so the site never shows the old storyboard under the new
captions. Then run python tools/build.py: tools/app_shots.py puts every file that exists on the page (alt =
data/apps.json shot_captions, by store number) and in the JSON-LD.

Fonts: the wordmark uses tools/fonts/nanumsquareeb.ttf (ExtraBold, the same file the app repo uses); the descriptor
needs NanumSquare Bold, which this repository does not carry, so pass it with --font-mid (default: the sugar-utils
copy the app repo's tools use). Needs Pillow. Writes no bytecode into the app checkout.
"""
import argparse, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = 240  # lockup symbol height in px; og.py downsamples (brand guide §5: T >= 110 px keeps the descriptor readable)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--axf", required=True, help="AXFamily repository checkout (read only)")
    ap.add_argument("--font-mid", default=os.path.expanduser("~/sugar-utils/core/designsystem/src/main/res/font/nanumsquareb.ttf"))
    ap.add_argument("--shots", action="store_true", help="copy the store screenshots only")
    a = ap.parse_args()
    sys.dont_write_bytecode = True
    if a.shots:
        return shots(a.axf)
    sys.path.insert(0, os.path.join(a.axf, "tools", "store"))
    import make_brand as mb  # noqa: E402  (app repo: draw_lockup, colours via make_icon)

    for ext in ("png", "webp"):
        src = os.path.join(a.axf, "tools", "release", "site", "assets", f"icon.{ext}")
        shutil.copyfile(src, os.path.join(ROOT, "assets", "apps", "axfamily", f"icon.{ext}"))

    f = {"eb": os.path.join(ROOT, "tools", "fonts", "nanumsquareeb.ttf"), "b": a.font_mid,
         "r": os.path.join(ROOT, "tools", "fonts", "nanumsquarer.ttf")}
    from PIL import Image
    os.makedirs(os.path.join(ROOT, "tools", "brand"), exist_ok=True)
    for lang in ("ko", "en"):
        w, h = mb.lockup_size(T, lang, f)
        img = Image.new("RGB", (w, h), mb.mi.APRICOT)
        mb.draw_lockup(img, (0, 0), T, "apricot", lang, f)
        img.save(os.path.join(ROOT, "tools", "brand", f"axfamily-lockup-{lang}.png"), optimize=True)
    print("ok: assets/apps/axfamily/icon.{png,webp}, tools/brand/axfamily-lockup-{ko,en}.png")


def shots(axf):
    import json
    from PIL import Image
    meta = json.load(open(os.path.join(axf, "docs", "store", "screenshots.json"), encoding="utf-8"))
    caps = {x["id"]: x for x in json.load(open(os.path.join(ROOT, "data", "apps.json"), encoding="utf-8"))["apps"]}["axfamily"]
    for lang in ("ko", "en"):
        # per-language marks (assets.<lang>); an older file has one set at the top level for both languages
        side = (meta.get("assets") or {}).get(lang) or {k: meta.get(k) for k in ("assets_storyboard", "ai_text")}
        if side.get("assets_storyboard") != meta.get("storyboard"):
            raise SystemExit(f"screenshots.json {lang}: captures are {side.get('assets_storyboard')}, captions "
                             f"{meta.get('storyboard')}; re-shoot first (app repo tools/store/README.md)")
        if side.get("ai_text") not in ("model", "none"):
            print(f"note: screenshots.json {lang} ai_text={side.get('ai_text')!r} (AI screens are not real model output yet)")
        want = len(caps[lang].get("shot_captions") or [])
        publish = set(side.get("publish") or (f"{n:02d}" for n in range(1, want + 1)))
        out_dir = os.path.join(ROOT, "assets", "apps", "axfamily", "shots", lang)
        os.makedirs(out_dir, exist_ok=True)
        done = []
        for n in range(1, want + 1):
            out = os.path.join(out_dir, f"{n:02d}.webp")
            if f"{n:02d}" not in publish:
                if os.path.exists(out): os.remove(out)
                continue
            im = Image.open(os.path.join(axf, "docs", "store", "assets", "screenshots", lang, f"{n:02d}.png")).convert("RGB")
            im = im.resize((360, round(im.height * 360 / im.width)), Image.LANCZOS)
            for q in (80, 72, 64, 56):
                im.save(out, "WEBP", quality=q, method=6)
                if os.path.getsize(out) <= 80 * 1024: break
            done.append(f"{n:02d}")
        print(f"ok: {lang} screenshots {', '.join(done)} in assets/apps/axfamily/shots/{lang}/")


if __name__ == "__main__":
    main()
