"""AX notes: hub search, note type labels, inquiry boxes and figure images. Imported by build.py.

- search: the hub has a search box (<!-- build:ax-search -->) that loads /ax/search.json (/en/ax/search.json) on first
  input and filters every note by title, description, topic and type. Results come from JSON, so the hub's own text
  (and its font budget) does not grow with each new note.
- type: the note's eyebrow "AX 노트 · 사고 기록" names its type; the hub and search show it.
- inquiry: two boxes per note, one before the middle h2 and one at the end (<!-- build:cta-mid -->, <!-- build:cta -->).
  Plain mailto with a subject that names the note, so no form and no personal data stored on the site.
  Common syllables only: the box is on every note and counts toward each note's 470 KB font budget.
- figures: <figure> images in a note's <main> under /assets/ax/ (made by tools/ax_figures.py) go into the Article
  JSON-LD image list.
"""
import html
import json
import re
from urllib.parse import quote

EYEBROW_RE = re.compile(r'<span class="eyebrow">([^<]*)</span>')
FIG_RE = re.compile(r'<img\b[^>]*\bsrc="(/assets/ax/[^"]+)"')

T = {
    "ko": {
        "search_label": "AX 노트 검색", "search_ph": "예: 테스트, R8, 출시, 에이전트",
        "search_hint": "제목, 요약, 주제, 글 유형에서 찾습니다.",
        "cta_mid": "이 글과 비슷한 문제를 겪고 있다면 메일로 상황을 알려 주세요. 읽고 답하겠습니다.",
        "cta_h": "질문이나 제안이 있나요?",
        "cta_p": "글에 적은 방법을 직접 적용해 보다 막힌 곳, 숫자에 대한 질문, 다뤄 줬으면 하는 주제를 메일로 보내 주세요.",
        "cta_btn": "메일로 문의하기", "cta_subject": "[AX 노트] {title}",
    },
    "en": {
        "search_label": "Search AX notes", "search_ph": "e.g. tests, R8, release, agents",
        "search_hint": "Matches titles, summaries, topics and note types.",
        "cta_mid": "Running into the same problem? Email us what you are seeing and we will reply.",
        "cta_h": "Questions or ideas?",
        "cta_p": "Send us where you got stuck applying this, a question about the numbers, or a topic you would like covered.",
        "cta_btn": "Email us", "cta_subject": "[AX notes] {title}",
    },
}

# filters /ax/search.json on input; the page's JS budget is 1 KB (tools/checks.py BUDGET["js"]), menu script included
SEARCH_JS = ("<script>(function(i,o){var d;i.addEventListener('input',function(){var q=i.value.trim().toLowerCase();"
             "if(!q){o.innerHTML='';return}(d?Promise.resolve(d):fetch(i.dataset.src).then(function(r){return r.json()})"
             ".then(function(j){return d=j})).then(function(j){var r=j.filter(function(x){return(x.t+' '+x.d+' '+x.k+' '+x.y)"
             ".toLowerCase().indexOf(q)>-1});o.innerHTML=r.length?r.slice(0,30).map(function(x){return'<li><a href=\"'+x.u+'\">'"
             "+x.t+'</a><span class=\"meta\">'+x.k+' · '+x.y+' · '+x.p+'</span></li>'}).join(''):'<li>'+o.dataset.none+'</li>'})})"
             "})(document.getElementById('ax-q'),document.getElementById('ax-r'))</script>")
NONE = {"ko": "찾는 글이 없습니다. 다른 낱말로 찾아 보세요.", "en": "No notes match. Try another word."}


def note_type(main, lang):
    """'사고 기록' from 'AX 노트 · 사고 기록' (the note's eyebrow), or '' when the eyebrow has no type."""
    m = EYEBROW_RE.search(main)
    if not m: return ""
    parts = [p.strip() for p in html.unescape(m.group(1)).split("·")]
    return parts[-1] if len(parts) > 1 else ""


def figures(main):
    out = []
    for src in FIG_RE.findall(main):
        if src not in out: out.append(src)
    return out


def search_block(lang, json_url):
    t = T[lang]
    return (f'\n      <div class="ax-search" role="search">'
            f'<label for="ax-q">{t["search_label"]}</label>'
            f'<input id="ax-q" type="search" autocomplete="off" placeholder="{html.escape(t["search_ph"])}" data-src="{json_url}">'
            f'<p class="muted">{t["search_hint"]}</p>'
            f'<ul id="ax-r" class="ax-results" aria-live="polite" data-none="{NONE[lang]}"></ul></div>'
            f'\n      {SEARCH_JS}\n      ')


def search_json(rows):
    """rows: [(url, title, desc, topic, type, date)] newest first. Strings are HTML-escaped: the page inserts them as HTML."""
    e = lambda s: html.escape(s or "", quote=True)
    return json.dumps([{"u": u, "t": e(t), "d": e(d), "k": e(k), "y": e(y), "p": p} for u, t, d, k, y, p in rows],
                      ensure_ascii=False, separators=(",", ":")) + "\n"


def cta_mid(lang, email, title):
    t = T[lang]
    href = f"mailto:{email}?subject={quote(t['cta_subject'].format(title=title))}"
    return f'\n    <aside class="ax-cta ax-cta--inline"><p>{t["cta_mid"]} <a href="{html.escape(href)}">{t["cta_btn"]}</a></p></aside>\n    '


def cta_end(lang, email, title):
    t = T[lang]
    href = f"mailto:{email}?subject={quote(t['cta_subject'].format(title=title))}"
    return (f'\n    <aside class="ax-cta" aria-labelledby="ax-cta-h"><p class="ax-cta-title" id="ax-cta-h">{t["cta_h"]}</p>'
            f'<p>{t["cta_p"]}</p><p><a class="button" href="{html.escape(href)}">{t["cta_btn"]}</a> '
            f'<span class="muted">{email}</span></p></aside>\n    ')


def middle_h2(main):
    """Offset of the h2 nearest the middle of the note's body sections (FAQ and build blocks excluded), or None."""
    hs = [m.start() for m in re.finditer(r'<section aria-labelledby="(?!faq"|ax-related)[^"]*">\s*<h2\b', main)]
    if len(hs) < 3: return None
    return main.rfind("\n", 0, hs[len(hs) // 2])  # start of that line, so the box gets its own line


# ---------- ads (AdSense display units on AX notes only) ----------
# data/ads.json: {"client": "ca-pub-…", "serve": true|false, "slots": {"in_article": "…", "rail_left": "…", "rail_right": "…"}}.
# No client → no ad markup at all (no empty boxes, no script). AX_ADS_PREVIEW=1 draws labelled placeholders instead
# (for layout review in a scratch copy only; never build the real site with it).
ADS_FILE = "data/ads.json"
AD_LABEL = {"ko": "광고", "en": "Advertisement"}
AD_PUSH = "<script>(adsbygoogle=window.adsbygoogle||[]).push({})</script>"


def ads_config(root):
    import os
    path = os.path.join(root, ADS_FILE)
    cfg = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    preview = os.environ.get("AX_ADS_PREVIEW") == "1"
    # "serve": false keeps units off while AdSense reviews the site (empty boxes otherwise); flip to true once approved
    on = (bool(cfg.get("client")) and all(cfg.get("slots", {}).get(k) for k in ("in_article", "rail_left", "rail_right"))
          and cfg.get("serve", True) is True)
    return {"on": on, "preview": preview and not on, "client": cfg.get("client", ""), "slots": cfg.get("slots", {})}


def ads_head(cfg):
    if not cfg["on"]: return ""
    return (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={cfg["client"]}"'
            ' crossorigin="anonymous"></script>')


def ad_unit(cfg, kind, lang):
    """kind: in_article (responsive, in the text column), rail_left (160 wide), rail_right (300 wide)."""
    cls = {"in_article": "ad ad-in", "rail_left": "ad ad-rail", "rail_right": "ad ad-side"}[kind]
    label = f'<p class="ad-label">{AD_LABEL[lang]}</p>'
    if cfg["on"]:
        fmt = ' data-ad-format="auto" data-full-width-responsive="true"' if kind == "in_article" else ""
        ins = (f'<ins class="adsbygoogle" style="display:block" data-ad-client="{cfg["client"]}"'
               f' data-ad-slot="{cfg["slots"][kind]}"{fmt}></ins>{AD_PUSH}')
        return f'<aside class="{cls}" aria-label="{AD_LABEL[lang]}">{label}{ins}</aside>'
    if cfg["preview"]:
        return f'<aside class="{cls} ad-preview" aria-label="{AD_LABEL[lang]}">{label}<div class="ad-box">{kind}</div></aside>'
    return ""


def ads_meta(cfg):
    """Site-ownership tag AdSense asks for on every page; present as soon as the client is set (before ad units exist)."""
    if not cfg["client"]: return ""
    return f'<meta name="google-adsense-account" content="{cfg["client"]}">'


def ads_txt(cfg):
    """ads.txt line for the AdSense publisher (pub-… from ca-pub-…), or None until the client is set."""
    if not cfg["client"]: return None
    pub = cfg["client"].replace("ca-", "", 1)
    return f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n"
