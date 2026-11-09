"""Store screenshots that show on an app page only once their files exist (build.py imports this).

An app with "shot_captions" in data/apps.json (ko and en: one caption per store screenshot, in store order) gets its
a[lang]["shots"] filled from assets/apps/<id>/shots/<lang>/01.webp, 02.webp, ... for every file that is there, with
the caption as alt text. No file, no entry: the page draws no empty box and the MobileApplication JSON-LD lists no
screenshot. A hand-written app page places the list with an empty <!-- build:shots --><!-- /build:shots --> marker
right after its hero; build.py fills it from block(). Standard library only (WebP size read from the RIFF header).
"""
import html
import os
import struct


def webp_size(path):
    """(width, height) of a WebP file (VP8, VP8L or VP8X), or None."""
    with open(path, "rb") as f:
        head = f.read(30)
    if len(head) < 30 or head[:4] != b"RIFF" or head[8:12] != b"WEBP":
        return None
    kind = head[12:16]
    if kind == b"VP8 ":
        w, h = struct.unpack("<HH", head[26:30])
        return w & 0x3FFF, h & 0x3FFF
    if kind == b"VP8L":
        b = head[21:25]
        return 1 + (((b[1] & 0x3F) << 8) | b[0]), 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
    if kind == b"VP8X":
        return 1 + int.from_bytes(head[24:27], "little"), 1 + int.from_bytes(head[27:30], "little")
    return None


def shot_path(app_id, lang, n):
    return f"assets/apps/{app_id}/shots/{lang}/{n:02d}.webp"


def fill(apps, root):
    """Set a[lang]["shots"] for every app with shot_captions, from the files that exist (in place)."""
    for a in apps:
        for lang in ("ko", "en"):
            caps = a.get(lang, {}).get("shot_captions")
            if not caps:
                continue
            shots = []
            for n, cap in enumerate(caps, 1):
                rel = shot_path(a["id"], lang, n)
                full = os.path.join(root, rel)
                size = webp_size(full) if os.path.isfile(full) else None
                if size:
                    shots.append({"src": "/" + rel, "w": size[0], "h": size[1], "alt": cap})
            if shots:
                a[lang]["shots"] = shots
            else:
                a[lang].pop("shots", None)


def block(a, lang, label):
    """Inner HTML of <!-- build:shots -->: the screenshot strip, or nothing when no file exists yet."""
    shots = a.get(lang, {}).get("shots") or []
    if not shots:
        return ""
    lis = "".join(f'\n      <li><img src="{s["src"]}" width="{s["w"]}" height="{s["h"]}" loading="lazy" alt="{html.escape(s["alt"], quote=True)}"></li>'
                  for s in shots)
    return (f'\n    <ul class="shots" tabindex="0" role="region" aria-label="{html.escape(label, quote=True)}">{lis}\n    </ul>\n    ')
