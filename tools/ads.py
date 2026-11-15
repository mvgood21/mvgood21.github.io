"""AdSense on AX notes: modes, eligibility, placement and the page budget. Imported by build.py and checks.py.

Owner decisions 2026-10-22 (ads on AX notes only) and 2026-11-15 (ad design: review mode, gate R1-R7, placement).

data/ads.json
  client        "ca-pub-…": the ownership meta on every page and ads.txt need only this
  mode          "off" | "review" | "on". Old files without "mode": "serve": false → off, otherwise on.
  slots         in_article, rail_left, rail_right; the same ids are in assets/ads.js (checks.py AD-JS compares them)
  min_text      {"ko": characters without spaces, "en": words} of body text a note needs (R5)
  second_unit   {"ko", "en", "min_h2"}: body length and body h2 count for a second in-article unit
  exclude       note slugs that never carry ads (R4)
  reviewed_only, reviewed   R7, owner decision, off by default: only notes the owner has read and approved

Modes
  off     no loader, box or ads.js on any page (checks.py AD-OFF). ads.txt and the ownership meta stay.
  review  AdSense site review: eligible notes get Google's async loader tag in <head> and no ad units (empty boxes
          before approval read as an unfinished page).
  on      eligible notes get empty reserved boxes and /assets/ads.js (defer). ads.js loads adsbygoogle.js after the
          first scroll, tap or key and fills only boxes that have a width and come within 800 px of the viewport, so a
          box hidden at this screen width (side, rail) never gets an ad unit.

Eligibility, eligible(): R1 mode is not off; R2 the page is an AX note; R3 not noindex (tools/noindex.py, which also
covers data/noindex.json ax_notes); R4 slug not in exclude; R5 body text >= min_text; R7 with reviewed_only, slug in
reviewed. R6, fit(): the finished page stays within the HTML budget; parts drop in the order rail, side, second
unit, first unit (review: the loader tag) until it fits.

Placement (on): the first in-article unit goes before the second body h2, the second unit (long notes only) before
the last body h2. A unit sits only between two body sections, never next to the hero, TOC, series line or box,
inquiry box, FAQ or related list: when the element before the chosen h2 is not a body section (the mid inquiry box
sits there), the first unit moves to the next h2 and the second to the previous one, keeping two or more <p> between
them. Side 300x250 goes under the side TOC (>= 1100 px), the rail 160x600 is main's grid column 1 (>= 1380 px).
Labels are CSS (assets/ax.css ::before): ko "광고", en "Advertisements". AX_ADS_PREVIEW=1 draws the boxes with a
dashed outline and no script, for layout review in a scratch copy only.
"""
import hashlib
import html
import json
import os
import re

import dates

FILE = "data/ads.json"
JS = "assets/ads.js"
MODES = ("off", "review", "on")
SLOT_KEYS = ("in_article", "rail_left", "rail_right")
RESERVED = frozenset({"topic", "series", "page"})  # /ax/<reserved>/… are list pages, not notes
DEFAULTS = {"min_text": {"ko": 1500, "en": 600}, "second_unit": {"ko": 3000, "en": 1200, "min_h2": 5}}
BLOCKS = ("ad-1", "ad-2", "ad-rail")  # build block names; build.py's RSS strips these, dates.py ignores them
DROP_ORDER = ("ad-rail", "side", "ad-2", "ad-1")  # R6
BOX = {"ad-1": ("ad-in", "i"), "ad-2": ("ad-in", "i"), "ad-rail": ("ad-rail", "r"), "side": ("ad-side", "s")}
LABEL = {"ko": "광고", "en": "Advertisements"}  # AdSense allows only these (ko "광고", en "Advertisements")
FOOTER = {"ko": "광고·쿠키", "en": "Ads & cookies"}  # footer link to /privacy/site/ on every page (G8)
NOTE_RE = re.compile(r"(?:en/)?ax/([^/]+)/index\.html$")
BODY_H2_RE = re.compile(r'<section aria-labelledby="(?!faq"|ax-related)[^"]*">\s*<h2\b')
SKIP_RE = re.compile(r"<(nav|aside|figure|pre|code|script|style|template)\b.*?</\1>", re.S)


def config(root):
    path = os.path.join(root, FILE)
    raw = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f: raw = json.load(f)
    client, slots = raw.get("client", ""), raw.get("slots", {})
    mode = raw.get("mode")
    if mode is None: mode = "off" if raw.get("serve", True) is not True else "on"  # files written before modes
    if mode not in MODES: raise ValueError(f"{FILE}: mode must be one of {MODES}, not {mode!r}")
    if not client: mode = "off"  # review needs the client, units need it and every slot
    elif mode == "on" and not all(slots.get(k) for k in SLOT_KEYS): mode = "off"
    js = os.path.join(root, JS)
    js_v = ""
    if os.path.exists(js):
        with open(js, "rb") as f: js_v = hashlib.sha1(f.read().replace(b"\r\n", b"\n")).hexdigest()[:8]
    return {"mode": mode, "client": client, "slots": slots,
            "preview": os.environ.get("AX_ADS_PREVIEW") == "1" and mode != "on",
            "min_text": {**DEFAULTS["min_text"], **raw.get("min_text", {})},
            "second_unit": {**DEFAULTS["second_unit"], **raw.get("second_unit", {})},
            "exclude": frozenset(raw.get("exclude", ())), "reviewed_only": raw.get("reviewed_only", False) is True,
            "reviewed": frozenset(raw.get("reviewed", ())), "js_v": js_v}


def meta(cfg):
    """Site-ownership tag AdSense asks for on every page; present as soon as the client is set, in every mode."""
    return f'<meta name="google-adsense-account" content="{cfg["client"]}">' if cfg["client"] else ""


def ads_txt(cfg):
    """ads.txt line for the AdSense publisher (pub-… from ca-pub-…), or None until the client is set."""
    if not cfg["client"]: return None
    return f"google.com, {cfg['client'].replace('ca-', '', 1)}, DIRECT, f08c47fec0942fa0\n"


def loader_url(cfg):
    return f"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={cfg['client']}"


def head_tag(cfg):
    """Google's standard async loader (review mode only; in mode on assets/ads.js adds it after the first interaction)."""
    return f'<script async src="{loader_url(cfg)}" crossorigin="anonymous"></script>'


def js_tag(cfg):
    return f'<script src="/{JS}?v={cfg["js_v"]}" defer></script>'


def note_slug(relpath):
    m = NOTE_RE.fullmatch(relpath)
    return m.group(1) if m and m.group(1) not in RESERVED else None


def body_size(main, lang):
    """Body text of a note's <main> without build blocks, nav, aside, figure, pre and code:
    ko = characters without whitespace, en = words."""
    t = re.sub(r"<!--.*?-->", " ", dates.strip_build_blocks(main), flags=re.S)
    prev = None
    while prev != t: prev, t = t, SKIP_RE.sub(" ", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return len(t.split()) if lang == "en" else len(re.sub(r"\s+", "", t))


def eligible(cfg, relpath, main, noindex_paths, lang=None):
    """None when the page may carry ads, else the first rule it fails: "R1" … "R7" (R6 is fit())."""
    if cfg["mode"] == "off" and not cfg["preview"]: return "R1"
    slug = note_slug(relpath)
    if slug is None: return "R2"
    if relpath in noindex_paths: return "R3"
    if slug in cfg["exclude"]: return "R4"
    lang = lang or ("en" if relpath.startswith("en/") else "ko")
    if body_size(main, lang) < cfg["min_text"][lang]: return "R5"
    if cfg["reviewed_only"] and slug not in cfg["reviewed"]: return "R7"
    return None


def _block_re(n, trailing=False):
    return re.compile(rf"<!-- build:{n} -->.*?<!-- /build:{n} -->" + (r"(?:\n\n    )?" if trailing else ""), re.S)


def clear_blocks(main, cfg):
    """Mode on (or preview): remove the ad blocks, fit() places them again on the finished page. Otherwise empty
    them where they are, so turning ads off or reviewing leaves every note's <main> as it was."""
    for n in BLOCKS:
        if cfg["mode"] == "on" or cfg["preview"]:
            main = _block_re(n, True).sub("", main)
        else:
            main = _block_re(n).sub(f"<!-- build:{n} --><!-- /build:{n} -->", main)
    return main


def unplace(main):
    """A finished note's <main> without the parts render() placed (checks.py asks spots() what should be there)."""
    for n in BLOCKS: main = _block_re(n, True).sub("", main)
    return re.sub(r'<div class="ad ad-side[^"]*" data-s="s"></div>', "", main)


def _after_section(main, starts, k):
    """True when the element right before body section k is body section k-1 (no box, block or list between)."""
    return k > 0 and main[starts[k - 1]:starts[k]].rstrip().endswith("</section>")


def spots(main, cfg, lang):
    """Offsets in main (the finished page's <main>…) where each part goes, or None: {"ad-1", "ad-2", "ad-rail", "side"}."""
    s = [m.start() for m in BODY_H2_RE.finditer(main)]
    a = next((k for k in range(1, len(s)) if _after_section(main, s, k)), None)
    b = None
    su = cfg["second_unit"]
    if a is not None and len(s) >= su["min_h2"] and body_size(main, lang) >= su[lang]:
        b = next((k for k in range(len(s) - 1, a, -1)
                  if _after_section(main, s, k) and len(re.findall(r"<p\b", main[s[a]:s[k]])) >= 2), None)
    out = {"ad-1": s[a] if a is not None else None, "ad-2": s[b] if b is not None else None, "ad-rail": None, "side": None}
    toc_end = main.find("<!-- /build:toc -->")
    side = main.find('<div class="ax-side">')
    if toc_end != -1 and side != -1 and side < toc_end:
        nav_end = main.find("</nav>", side)
        if nav_end != -1 and nav_end < toc_end: out["side"] = nav_end + len("</nav>")
        m = re.compile(r"\s*").match(main, toc_end + len("<!-- /build:toc -->"))
        out["ad-rail"] = m.end()
    return out


def box(part, cfg):
    cls, s = BOX[part]
    return f'<div class="ad {cls}{" ad-preview" if cfg["preview"] else ""}" data-s="{s}"></div>'


def render(page, cfg, lang, parts):
    """page with the given parts placed (spots() decides where); parts that have no spot are skipped."""
    i0, i1 = page.find("<main"), page.rfind("</main>")
    main = page[i0:i1]
    sp = spots(main, cfg, lang)
    placed = sorted(((sp[p], p) for p in parts if sp.get(p) is not None), reverse=True)
    for at, p in placed:
        main = (main[:at] + box(p, cfg) + main[at:] if p == "side"
                else main[:at] + f"<!-- build:{p} -->{box(p, cfg)}<!-- /build:{p} -->\n\n    " + main[at:])
    out = page[:i0] + main + page[i1:]
    if placed and not cfg["preview"]: out = out.replace("</head>", f"  {js_tag(cfg)}\n</head>", 1)
    return out


def fit(page, cfg, lang, limit):
    """Finished, eligible note page → (page with the mode's ad parts that fit in limit bytes, dropped parts). R6."""
    size = lambda s: len(s.encode("utf-8"))
    if cfg["mode"] == "review" and not cfg["preview"]:
        out = page.replace("</head>", f"  {head_tag(cfg)}\n</head>", 1)
        return (out, []) if size(out) <= limit else (page, ["head"])
    if cfg["mode"] != "on" and not cfg["preview"]: return page, []
    parts, dropped = list(DROP_ORDER), []
    while parts:
        out = render(page, cfg, lang, parts)
        if size(out) <= limit: return out, dropped
        dropped.append(parts.pop(0))
    return page, dropped
