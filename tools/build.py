#!/usr/bin/env python3
"""Build the SugarMount site from data/apps.json.

  python3 tools/build.py          # rebuild everything in place
  python3 tools/build.py --check  # exit 1 if a rebuild would change any file

Generated from data:   index.html, en/index.html, privacy/index.html, en/privacy/index.html,
                       apps/<app_path>/ for apps with "page": "generated", 404.html,
                       sitemap.xml, llms.txt
Hand-written pages:    every other *.html keeps its <main> content byte for byte; the build only
                       replaces <head>, the site header/footer, breadcrumbs and JSON-LD around it.
Standard library only.
"""
import hashlib, html, json, os, re, subprocess, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://mvgood21.github.io"
EMAIL = "sugarmount21@gmail.com"
PLAY_DEV = "https://play.google.com/store/apps/dev?id=7906745536709395451"
PLAY = "https://play.google.com/store/apps/details?id="
ORG_ID = SITE + "/#org"
SITE_ID = SITE + "/#website"

T = {
  "ko": {
    "home": "홈", "apps": "앱", "privacy": "개인정보처리방침", "other_lang": "English", "other_lang_code": "en",
    "skip": "본문으로 건너뛰기", "site_tag": "한 가지 일을 간단하게 하는 Android 앱",
    "home_title": "SugarMount – 한 가지 일을 간단하게 하는 Android 앱",
    "home_desc": "SugarMount(simpest)가 만드는 Android 앱: 한글 맞춤법 검사(한글 띄어쓰기), 사진 용량 줄이기, 사진 반전·회전, 이미지 변환, HWP·PDF 뷰어, 인사말 카드, 사진 동영상 만들기, 복사 공유, 퍼즐 게임. 앱별 소개와 개인정보처리방침을 안내합니다.",
    "home_lead": "한 가지 일을 간단하게 하는 Android 앱을 만듭니다. 사진 용량 줄이기부터 한글 문서 보기, 한글 맞춤법, 퍼즐 게임까지 앱마다 하는 일은 하나입니다.",
    "count": "앱 {n}개 중 {live}개를 Google Play에서 받을 수 있습니다.",
    "all_apps": "앱 전체 보기",
    "groups": {"photo": "사진·영상", "video": "사진·영상", "document": "문서·글", "text": "문서·글", "card": "생활", "game": "게임"},
    "group_order": ["사진·영상", "문서·글", "생활", "게임"],
    "status": {"live": "Google Play", "soon": "출시 예정", "review": "심사 중"},
    "details": "자세히 보기", "get_play": "Google Play에서 받기", "on_play": "Google Play", "policy": "개인정보처리방침",
    "principles_h": "앱을 만드는 원칙",
    "principles": [
      ["파일은 기기 안에서", "사진·동영상·문서를 다루는 앱은 파일을 업로드하지 않고 기기에서 처리합니다. 원본은 그대로 둡니다."],
      ["계정 없이 바로", "회원 가입이나 로그인 없이 설치하고 바로 씁니다."],
      ["구현 그대로의 방침", "앱마다 실제 코드를 기준으로 개인정보처리방침을 쓰고, 광고·통계 SDK가 무엇을 하는지 적습니다."],
    ],
    "faq_h": "자주 묻는 질문",
    "home_faq": [
      ["SugarMount는 누가 만드나요?", "SugarMount는 개인 개발자 simpest가 Google Play에 앱을 배포할 때 쓰는 개발자 이름입니다. 앱 기획, 개발, 운영을 모두 직접 합니다."],
      ["사진이나 문서가 서버로 올라가나요?", "사진 용량 줄이기, 사진 반전·회전, 이미지 변환, 슈가독, 슈가앨범은 파일을 업로드하지 않고 기기 안에서만 처리합니다. 한글 띄어쓰기는 검사할 글을 네이버 또는 다음 맞춤법 검사기로 보내 검사합니다. 앱별 자세한 내용은 각 개인정보처리방침에 있습니다."],
      ["앱은 무료인가요?", "모든 앱을 무료로 설치할 수 있습니다. 앱에 따라 광고가 있고, 광고 제거나 Pro 기능을 일회성 구매 또는 구독으로 제공합니다. 슈가독에는 광고가 없습니다."],
      ["문의나 오류 신고는 어디로 하나요?", "이메일 " + EMAIL + "로 보내 주세요. 앱 이름과 기기 모델, Android 버전을 함께 적어 주시면 빨리 확인할 수 있습니다."],
    ],
    "contact_h": "문의", "contact_p": "앱 사용 중 문제가 있거나 궁금한 점이 있으면 이메일로 보내 주세요.", "email": "이메일",
    "privacy_title": "개인정보처리방침 – SugarMount",
    "privacy_desc": "SugarMount가 배포하는 모든 Android 앱의 개인정보처리방침 목록입니다. 앱마다 실제 구현을 기준으로 수집 항목, 처리 주체, 보존과 삭제 방법을 안내합니다.",
    "privacy_lead": "SugarMount가 배포하는 모든 앱의 개인정보처리방침을 앱별로 안내합니다. 각 방침은 실제 구현을 기준으로 씁니다.",
    "privacy_contact": "개인정보 처리에 관한 문의는 이메일로 보내 주세요.",
    "package": "패키지 이름", "read_policy": "방침 보기", "effective": "시행일",
    "app_title": "{name} ({brand}) – Android 앱 | SugarMount",
    "features_h": "이런 일을 합니다", "facts_h": "한눈에 보기", "status_h": "상태", "package_h": "패키지 이름", "dev_h": "개발자",
    "privacy_h": "개인정보", "privacy_more": "자세한 내용은 {link}에서 확인할 수 있습니다.", "policy_of": "{name} 개인정보처리방침",
    "related_h": "다른 앱", "shots_label": "{name} 스크린샷",
    "footer_apps": "앱", "footer_policies": "개인정보처리방침", "copyright": "© 2026 simpest · SugarMount",
    "nf_title": "페이지를 찾을 수 없습니다 – SugarMount", "nf_h": "페이지를 찾을 수 없습니다",
    "nf_p": "주소가 바뀌었거나 없는 페이지입니다. 홈에서 앱을 찾거나 개인정보처리방침 목록을 확인해 주세요.",
    "og_locale": "ko_KR", "date_fmt": "{y}년 {m}월 {d}일",
  },
  "en": {
    "home": "Home", "apps": "Apps", "privacy": "Privacy", "other_lang": "한국어", "other_lang_code": "ko",
    "skip": "Skip to content", "site_tag": "Small Android apps that each do one thing simply",
    "home_title": "SugarMount – Small Android apps that each do one thing simply",
    "home_desc": "Android apps by SugarMount (simpest): Korean spelling and spacing checker, photo compressor, flip and rotate, image converter, HWP and PDF viewer, greeting cards, photo video maker, clipboard sharing and puzzle games. App pages and privacy policies.",
    "home_lead": "Small Android apps that each do one thing simply, from shrinking photos and opening Korean HWP documents to checking Korean spelling and puzzle games.",
    "count": "{live} of {n} apps are on Google Play.",
    "all_apps": "All apps",
    "groups": {"photo": "Photo & video", "video": "Photo & video", "document": "Documents & text", "text": "Documents & text", "card": "Everyday", "game": "Games"},
    "group_order": ["Photo & video", "Documents & text", "Everyday", "Games"],
    "status": {"live": "Google Play", "soon": "Coming soon", "review": "In review"},
    "details": "Details", "get_play": "Get it on Google Play", "on_play": "Google Play", "policy": "Privacy policy",
    "principles_h": "How the apps are made",
    "principles": [
      ["Files stay on your device", "Apps that handle photos, videos and documents process files on the device without uploading them, and leave the originals untouched."],
      ["No account needed", "Install and start; no sign-up or log-in."],
      ["Policies that match the code", "Each app's privacy policy is written from its actual code, including what the ad and analytics SDKs do."],
    ],
    "faq_h": "Frequently asked questions",
    "home_faq": [
      ["Who makes SugarMount apps?", "SugarMount is the developer name used by simpest, an independent developer, to publish apps on Google Play. Planning, development and support are all done by the same person."],
      ["Are my photos or documents uploaded?", "Compress Image, Flip & Rotate Image, Convert Image, SugarDoc and SugarAlbum process files on your device without uploading them. SugarSpeller sends the text you check to the Naver or Daum spelling checker. Each app's privacy policy has the details."],
      ["Are the apps free?", "All apps are free to install. Some show ads and offer ad removal or Pro features as a one-time purchase or subscription. SugarDoc has no ads."],
      ["How do I get support or report a bug?", "Email " + EMAIL + ". Including the app name, device model and Android version helps us check faster."],
    ],
    "contact_h": "Contact", "contact_p": "If something isn't working or you have a question, send us an email.", "email": "Email",
    "privacy_title": "Privacy policies – SugarMount",
    "privacy_desc": "Privacy policies for every Android app published by SugarMount. Each one is written from the app's actual implementation and covers what is collected, who processes it, and how it is kept and deleted.",
    "privacy_lead": "Privacy policies for every app SugarMount publishes, one per app, each written from the app's actual implementation.",
    "privacy_contact": "For questions about how your data is handled, email us.",
    "package": "Package name", "read_policy": "Read the policy", "effective": "Effective",
    "app_title": "{name} – Android app | SugarMount",
    "features_h": "What it does", "facts_h": "At a glance", "status_h": "Status", "package_h": "Package name", "dev_h": "Developer",
    "privacy_h": "Privacy", "privacy_more": "See {link} for details.", "policy_of": "the {name} privacy policy",
    "related_h": "More apps", "shots_label": "{name} screenshots",
    "footer_apps": "Apps", "footer_policies": "Privacy policies", "copyright": "© 2026 simpest · SugarMount",
    "nf_title": "Page not found – SugarMount", "nf_h": "Page not found",
    "nf_p": "This page has moved or does not exist. Find an app on the home page or check the list of privacy policies.",
    "og_locale": "en_US", "date_fmt": "{M} {d}, {y}",
  },
}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

def esc(s): return html.escape(s, quote=True)
def rel(path): return os.path.join(ROOT, path)
def read(path):
    with open(rel(path), encoding="utf-8") as f: return f.read()

DATA = json.load(open(rel("data/apps.json"), encoding="utf-8"))
APPS = DATA["apps"]
BY_APP_PATH = {a["app_path"]: a for a in APPS if a.get("app_path")}
BY_PRIVACY_PATH = {a["privacy_path"]: a for a in APPS if a.get("privacy_path")}

def css_version():
    return hashlib.sha1(open(rel("assets/site.css"), "rb").read()).hexdigest()[:8]
CSSV = css_version()

def prefix(lang): return "/en" if lang == "en" else ""
def url(lang, path):  # path like "/", "/privacy/", "/apps/x/"
    return prefix(lang) + path
def app_url(a, lang):
    return url(lang, f"/apps/{a['app_path']}/") if a.get("app_path") else None
def privacy_url(a, lang):
    return url(lang, f"/privacy/{a['privacy_path']}/") if a.get("privacy_path") else None
def play_url(a): return PLAY + a["package"] if a.get("play") else None
def primary_url(a, lang): return app_url(a, lang) or privacy_url(a, lang)
def disp_name(a, lang):
    d = a[lang]; return d["name"]
def full_name(a, lang):
    d = a[lang]
    return d["name"] if d["brand"] in d["name"] else f"{d['name']} ({d['brand']})"

# ---------------------------------------------------------------- shared chrome
BRAND_MARK = ('<svg class="brand-mark" viewBox="0 0 32 32" aria-hidden="true">'
              '<path d="M16 3 28 9.5 16 16 4 9.5Z" fill="#E6F4F1"/>'
              '<path d="M4 9.5 16 16v13L4 22.5Z" fill="#0F766E"/>'
              '<path d="M28 9.5 16 16v13l12-6.5Z" fill="#0B4F4A"/>'
              '<path d="M16 3 28 9.5v13L16 29 4 22.5v-13Z" fill="none" stroke="#0B4F4A" stroke-width="1.6" stroke-linejoin="round"/></svg>')

def header(lang, current, other_href):
    t = T[lang]
    cur = lambda k: ' aria-current="page"' if current == k else ""
    return f'''<a class="skip" href="#main">{t["skip"]}</a>
  <header class="site-header">
    <div class="container">
      <a class="brand" href="{url(lang, "/")}">{BRAND_MARK}<span class="brand-name">SugarMount</span></a>
      <nav class="site-nav" aria-label="{"주요 메뉴" if lang == "ko" else "Main menu"}">
        <a class="nav-apps" href="{url(lang, "/")}#apps">{t["apps"]}</a>
        <a href="{url(lang, "/privacy/")}"{cur("privacy")}>{t["privacy"]}</a>
        <a class="lang" href="{other_href}" lang="{t["other_lang_code"]}" hreflang="{t["other_lang_code"]}">{t["other_lang"]}</a>
      </nav>
    </div>
  </header>'''

def footer(lang):
    t = T[lang]
    apps_li = "\n".join(f'          <li><a href="{primary_url(a, lang)}">{esc(disp_name(a, lang))}</a></li>' for a in APPS)
    pol_li = "\n".join(f'          <li><a href="{privacy_url(a, lang)}">{esc(disp_name(a, lang))}</a></li>' for a in APPS if a.get("privacy_path"))
    return f'''<footer class="site-footer">
    <div class="container">
      <div>
        <a class="brand" href="{url(lang, "/")}">{BRAND_MARK}<span>SugarMount</span></a>
        <p>{t["site_tag"]}</p>
        <p>{t["email"]}: <a href="mailto:{EMAIL}">{EMAIL}</a></p>
      </div>
      <nav aria-label="{t["footer_apps"]}">
        <h2>{t["footer_apps"]}</h2>
        <ul>
{apps_li}
        </ul>
      </nav>
      <nav aria-label="{t["footer_policies"]}">
        <h2><a href="{url(lang, "/privacy/")}">{t["footer_policies"]}</a></h2>
        <ul>
{pol_li}
        </ul>
      </nav>
      <div class="legal"><span>{t["copyright"]}</span><a href="{PLAY_DEV}" rel="noopener">Google Play</a></div>
    </div>
  </footer>'''

def crumbs(lang, items):
    """items: [(name, href or None)] after Home."""
    t = T[lang]
    allitems = [(t["home"], url(lang, "/"))] + items
    lis = []
    for i, (name, href) in enumerate(allitems):
        last = i == len(allitems) - 1
        if last or not href:
            lis.append(f'<li><span aria-current="page">{esc(name)}</span></li>' if last else f"<li>{esc(name)}</li>")
        else:
            lis.append(f'<li><a href="{href}">{esc(name)}</a></li>')
    nav = f'<nav class="crumbs" aria-label="{"이동 경로" if lang == "ko" else "Breadcrumb"}"><ol>{"".join(lis)}</ol></nav>'
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, **({"item": SITE + h} if h else {})} for i, (n, h) in enumerate(allitems)]}
    return nav, ld

def org_ld():
    return {"@type": "Organization", "@id": ORG_ID, "name": "SugarMount", "alternateName": ["simpest", "슈가마운트"],
            "url": SITE + "/", "logo": SITE + "/assets/logo.png", "email": EMAIL, "sameAs": [PLAY_DEV]}

def app_ld(a, lang, page_url):
    d = a[lang]
    alt = []
    for x in (d["brand"], d.get("store_title")):
        if x and x != d["name"] and x not in alt: alt.append(x)
    ld = {"@context": "https://schema.org", "@type": "MobileApplication", "@id": SITE + page_url + "#app",
          "name": d["name"], "alternateName": alt,
          "description": d["desc"], "url": SITE + page_url, "operatingSystem": "Android",
          "applicationCategory": a["schema_category"], "image": SITE + a["icon"] + ".png",
          "author": {"@id": ORG_ID}, "publisher": {"@id": ORG_ID}}
    if a.get("languages"): ld["inLanguage"] = a["languages"]
    if d.get("shots"): ld["screenshot"] = [SITE + s["src"] for s in d["shots"]]
    if a.get("play"):  # only public listings get an offer and install link
        ld["offers"] = {"@type": "Offer", "price": "0", "priceCurrency": "KRW"}
        ld["installUrl"] = ld["downloadUrl"] = play_url(a); ld["sameAs"] = [play_url(a)]
    return ld

def ld_json(x):
    # "</" inside a script element would end it early
    return json.dumps(x, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

def faq_ld(pairs):
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": ans}} for q, ans in pairs]}

def head(lang, title, desc, path, alt_path, *, og_type="website", og_image=None, og_image_size=(1200, 630), lds=(), noindex=False):
    t = T[lang]
    canon = SITE + path
    alts = ""
    if alt_path:
        ko_p, en_p = (path, alt_path) if lang == "ko" else (alt_path, path)
        alts = (f'\n  <link rel="alternate" hreflang="ko" href="{SITE + ko_p}">'
                f'\n  <link rel="alternate" hreflang="en" href="{SITE + en_p}">'
                f'\n  <link rel="alternate" hreflang="x-default" href="{SITE + ko_p}">')
    img = og_image or "/assets/og.png"
    w, h = og_image_size
    other_locale = "en_US" if lang == "ko" else "ko_KR"
    ld_html = "".join(f'\n  <script type="application/ld+json">{ld_json(x)}</script>' for x in lds)
    robots = '\n  <meta name="robots" content="noindex">' if noindex else ""
    return f'''<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}">{robots}
  <link rel="canonical" href="{canon}">{alts}
  <meta property="og:type" content="{og_type}">
  <meta property="og:site_name" content="SugarMount">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(desc)}">
  <meta property="og:url" content="{canon}">
  <meta property="og:image" content="{SITE + img}">
  <meta property="og:image:width" content="{w}">
  <meta property="og:image:height" content="{h}">
  <meta property="og:locale" content="{t["og_locale"]}">
  <meta property="og:locale:alternate" content="{other_locale}">
  <meta name="twitter:card" content="{"summary_large_image" if w > h else "summary"}">
  <meta name="color-scheme" content="light dark">
  <meta name="theme-color" content="#F6F8FB" media="(prefers-color-scheme: light)">
  <meta name="theme-color" content="#0F1622" media="(prefers-color-scheme: dark)">
  <link rel="icon" type="image/png" href="/assets/favicon.png">
  <link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
  <link rel="preconnect" href="https://hangeul.pstatic.net" crossorigin>
  <link rel="preload" href="https://hangeul.pstatic.net/hangeul_static/webfont/NanumSquareNeo/NanumSquareNeoTTF-bRg.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/assets/site.css?v={CSSV}">{ld_html}
</head>'''

def page(lang, head_html, body_attrs, header_html, main_html, footer_html):
    return f'''<!DOCTYPE html>
<html lang="{lang}">
{head_html}
<body{body_attrs}>
  {header_html}

  <main id="main" class="container">
{main_html}
  </main>

  {footer_html}
</body>
</html>
'''

def accent_attr(a, extra_class=""):
    cls = f' class="{extra_class}"' if extra_class else ""
    return f'{cls} style="--accent:{a["accent"]}"' if a else cls

def icon_img(a, size, cls="app-icon", alt=""):
    return f'<img class="{cls}" src="{a["icon"]}.webp" width="{size}" height="{size}" alt="{esc(alt)}">'

def clip_sentences(text, limit):
    """Keep whole sentences up to limit characters (at least the first sentence)."""
    parts = re.split(r"(?<=[.!?。])\s+", text.strip())
    out = parts[0]
    for p in parts[1:]:
        if len(out) + 1 + len(p) > limit: break
        out += " " + p
    return out

def fmt_date(lang, iso):
    y, m, d = (int(x) for x in iso.split("-"))
    return T[lang]["date_fmt"].format(y=y, m=m, d=d, M=MONTHS[m - 1])

# ---------------------------------------------------------------- home
def mountain_rows(n):
    rows, k = [], 1
    while n > 0:
        rows.append(min(k, n)); n -= k; k += 1
    return rows

def build_home(lang):
    t = T[lang]
    live = [a for a in APPS if a["status"] == "live"]
    # mountain: games at the summit, then the rest in data order
    order = sorted(APPS, key=lambda a: (a["status"] != "live", APPS.index(a)))
    rows, i, rows_html = mountain_rows(len(order)), 0, []
    for r in rows:
        cells = []
        for a in order[i:i + r]:
            cells.append(f'<a href="{primary_url(a, lang)}" aria-label="{esc(full_name(a, lang))}" style="--i:{i + len(cells)}">{icon_img(a, 84)}</a>')
        rows_html.append(f'        <li class="row">{"".join(cells)}</li>')
        i += r
    groups = {}
    for a in APPS:
        groups.setdefault(t["groups"][a["category"]], []).append(a)
    group_html = []
    for g in t["group_order"]:
        if g not in groups: continue
        items = []
        for a in groups[g]:
            d = a[lang]
            links = []
            if a.get("app_path"): links.append(f'<a href="{app_url(a, lang)}">{t["details"]}</a>')
            if a.get("play"): links.append(f'<a href="{play_url(a)}" rel="noopener">{t["on_play"]}</a>')
            if a.get("privacy_path"): links.append(f'<a class="muted-link" href="{privacy_url(a, lang)}">{t["policy"]}</a>')
            badge = f' <span class="badge badge--{a["status"]}">{t["status"][a["status"]]}</span>'
            brandline = d["brand"] if d["brand"] != d["name"] else ""
            title_link = primary_url(a, lang)
            items.append(f'''          <li class="app-row" id="{a["id"]}" style="--accent:{a["accent"]}">
            {icon_img(a, 56)}
            <div>
              <h4><a href="{title_link}">{esc(d["name"])}</a>{badge}</h4>
              {f'<p class="brandline">{esc(brandline)}</p>' if brandline else ''}
              <p class="tagline">{esc(d["tagline"])}</p>
              <div class="links">{"".join(links)}</div>
            </div>
          </li>''')
        group_html.append(f'''      <div class="group">
        <h3>{g}</h3>
        <ul class="app-rows">
{chr(10).join(items)}
        </ul>
      </div>''')
    principles = "\n".join(f'      <li><h3>{h}</h3><p>{p}</p></li>' for h, p in t["principles"])
    faq = "\n".join(f'      <details><summary>{esc(q)}</summary><div><p>{esc(a_)}</p></div></details>' for q, a_ in t["home_faq"])
    main = f'''    <section class="home-hero" aria-labelledby="hero-heading">
      <div>
        <h1 id="hero-heading">SugarMount</h1>
        <p class="lead">{t["home_lead"]}</p>
        <p class="count">{t["count"].format(n=len(APPS), live=len(live))}</p>
      </div>
      <div>
        <ul class="mountain" aria-label="{t["apps"]}">
{chr(10).join(rows_html)}
        </ul>
        <div class="mountain-base" aria-hidden="true"></div>
      </div>
    </section>

    <section id="apps" aria-labelledby="apps-heading">
      <h2 id="apps-heading">{t["apps"]}</h2>
{chr(10).join(group_html)}
    </section>

    <section aria-labelledby="principles-heading">
      <h2 id="principles-heading">{t["principles_h"]}</h2>
      <ul class="principles">
{principles}
      </ul>
    </section>

    <section aria-labelledby="faq-heading">
      <h2 id="faq-heading">{t["faq_h"]}</h2>
      <div class="faq">
{faq}
      </div>
    </section>

    <section aria-labelledby="contact-heading">
      <h2 id="contact-heading">{t["contact_h"]}</h2>
      <p>{t["contact_p"]}</p>
      <p>{t["email"]}: <a href="mailto:{EMAIL}">{EMAIL}</a></p>
    </section>'''
    path, alt = url(lang, "/"), url("en" if lang == "ko" else "ko", "/")
    graph = {"@context": "https://schema.org", "@graph": [
        org_ld(),
        {"@type": "WebSite", "@id": SITE_ID, "name": "SugarMount", "url": SITE + "/", "inLanguage": ["ko", "en"], "publisher": {"@id": ORG_ID}},
        {"@type": "ItemList", "name": t["apps"], "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "url": SITE + primary_url(a, lang), "name": full_name(a, lang)} for i, a in enumerate(APPS)]},
    ]}
    h = head(lang, t["home_title"], t["home_desc"], path, alt, lds=[graph, faq_ld(t["home_faq"])])
    return page(lang, h, "", header(lang, "home", alt), main, footer(lang))

# ---------------------------------------------------------------- privacy index
def effective_date(a, lang):
    try:
        s = read(f"{'en/' if lang == 'en' else ''}privacy/{a['privacy_path']}/index.html")
    except FileNotFoundError:
        return None
    m = re.search(r"<main[^>]*>(.*)</main>", s, re.S)
    s = m.group(1) if m else s
    if lang == "ko":
        m = re.search(r"시행일[:：]?\s*(?:<[^>]+>\s*)*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", s)
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None
    m = re.search(r"Effective(?: date)?[:：]?\s*(?:<[^>]+>\s*)*(" + "|".join(MONTHS) + r") (\d{1,2}), (\d{4})", s)
    return f"{int(m.group(3)):04d}-{MONTHS.index(m.group(1)) + 1:02d}-{int(m.group(2)):02d}" if m else None

def build_privacy_index(lang):
    t = T[lang]
    items = []
    for a in APPS:
        if not a.get("privacy_path"): continue
        eff = effective_date(a, lang) or effective_date(a, "ko")
        eff_s = f' · {t["effective"]} {fmt_date(lang, eff)}' if eff else ""
        items.append(f'''        <li class="card" style="--accent:{a["accent"]}">
          <h2>{esc(full_name(a, lang))} <span class="badge badge--{a["status"]}">{t["status"][a["status"]]}</span></h2>
          <p class="sub">{t["package"]} <code>{a["package"]}</code>{eff_s}</p>
          <div class="card-actions"><a class="button button--outline" href="{privacy_url(a, lang)}">{t["read_policy"]}</a></div>
        </li>''')
    path, alt = url(lang, "/privacy/"), url("en" if lang == "ko" else "ko", "/privacy/")
    nav, bc = crumbs(lang, [(t["privacy"], None)])
    main = f'''    {nav}
    <section class="hero">
      <h1>{t["privacy"]}</h1>
      <p class="lead">{t["privacy_lead"]}</p>
    </section>

    <section aria-label="{t["privacy"]}">
      <ul class="card-list">
{chr(10).join(items)}
      </ul>
    </section>

    <section aria-labelledby="contact-heading">
      <h2 id="contact-heading">{t["contact_h"]}</h2>
      <p>{t["privacy_contact"]}</p>
      <p>{t["email"]}: <a href="mailto:{EMAIL}">{EMAIL}</a></p>
    </section>'''
    lds = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": t["privacy_title"], "url": SITE + path,
            "inLanguage": lang, "isPartOf": {"@id": SITE_ID}, "publisher": org_ld()}, bc]
    h = head(lang, t["privacy_title"], t["privacy_desc"], path, alt, lds=lds)
    return page(lang, h, ' class="page-read"', header(lang, "privacy", alt), main, footer(lang))

# ---------------------------------------------------------------- generated app page
def build_app(a, lang):
    t, d = T[lang], a[lang]
    path, alt = app_url(a, lang), app_url(a, "en" if lang == "ko" else "ko")
    name = d["name"]
    nav, bc = crumbs(lang, [(name, None)])
    actions = []
    if a.get("play"): actions.append(f'<a class="button play-badge" href="{play_url(a)}" rel="noopener">{t["get_play"]}</a>')
    actions.append(f'<a class="button button--outline" href="{privacy_url(a, lang)}">{t["policy"]}</a>')
    shots = "".join(f'<li><img src="{s["src"]}" width="{s["w"]}" height="{s["h"]}" loading="lazy" alt="{esc(s["alt"])}"></li>' for s in d.get("shots", []))
    feats = "\n".join(f'        <li><h3>{esc(h_)}</h3><p>{esc(p)}</p></li>' for h_, p in d.get("features", []))
    facts = [(t["status_h"], t["status"][a["status"]])] + [tuple(x) for x in d.get("facts", [])] + [(t["package_h"], f'<code>{a["package"]}</code>'), (t["dev_h"], "SugarMount (simpest)")]
    facts_html = "\n".join(f'          <dt>{esc(k)}</dt><dd>{v if v.startswith("<code>") else esc(v)}</dd>' for k, v in facts)
    priv = "\n".join(f"        <li>{esc(x)}</li>" for x in d.get("privacy", []))
    policy_link = f'<a href="{privacy_url(a, lang)}">{esc(t["policy_of"].format(name=name))}</a>'
    faq = "\n".join(f'        <details><summary>{esc(q)}</summary><div><p>{esc(x)}</p></div></details>' for q, x in d.get("faq", []))
    others = [o for o in APPS if o is not a and o["category"] == a["category"]] + [o for o in APPS if o is not a and o["category"] != a["category"]]
    related = "\n".join(f'        <li><a href="{primary_url(o, lang)}" style="--accent:{o["accent"]}">{icon_img(o, 56)}<span>{esc(o[lang]["name"])}</span></a></li>' for o in others[:6])
    brandline = " · ".join(x for x in [d["brand"] if d["brand"] != name else "", d.get("store_title", "")] if x and x != name)
    main = f'''    {nav}
    <section class="app-hero">
      {icon_img(a, 96)}
      <h1>{esc(name)}</h1>
      {f'<p class="brandline">{esc(brandline)}</p>' if brandline else ''}
      <p class="tagline">{esc(d["desc"])}</p>
      <div class="actions">{"".join(actions)}</div>
    </section>

    {f'<ul class="shots" aria-label="{esc(t["shots_label"].format(name=name))}">{shots}</ul>' if shots else ''}

    <div class="app-layout">
      <div>
        <h2 id="features-heading">{t["features_h"]}</h2>
        <ul class="features">
{feats}
        </ul>

        <h2 id="privacy-heading">{t["privacy_h"]}</h2>
        <ul>
{priv}
        </ul>
        <p>{t["privacy_more"].format(link=policy_link)}</p>

        <h2 id="faq-heading">{t["faq_h"]}</h2>
        <div class="faq">
{faq}
        </div>

        <h2 id="contact-heading">{t["contact_h"]}</h2>
        <p>{t["contact_p"]}</p>
        <p>{t["email"]}: <a href="mailto:{EMAIL}">{EMAIL}</a></p>
      </div>
      <aside class="facts-box" aria-labelledby="facts-heading">
        <h2 id="facts-heading">{t["facts_h"]}</h2>
        <dl>
{facts_html}
        </dl>
      </aside>
    </div>

    <section aria-labelledby="related-heading">
      <h2 id="related-heading">{t["related_h"]}</h2>
      <ul class="related">
{related}
      </ul>
    </section>'''
    title = t["app_title"].format(name=name, brand=d["brand"]) if d["brand"] != name else t["app_title"].replace(" ({brand})", "").format(name=name)
    desc = clip_sentences(f'{d["tagline"]} {d["desc"]}', 170)
    og = f"/assets/og/{a['id']}-{lang}.png"
    lds = [app_ld(a, lang, path), bc]
    if d.get("faq"): lds.append(faq_ld(d["faq"]))
    h = head(lang, title, desc, path, alt, og_image=og if os.path.exists(rel(og.lstrip("/"))) else None, lds=lds)
    return page(lang, h, accent_attr(a), header(lang, "apps", alt), main, footer(lang))

# ---------------------------------------------------------------- hand-written pages
def wrap_hand(relpath):
    s = read(relpath)
    lang = "en" if relpath.startswith("en/") else "ko"
    t = T[lang]
    mt = re.search(r"<title>(.*?)</title>", s, re.S)
    mm = re.search(r"<main[^>]*>\n?(.*?)\n?\s*</main>(?!.*</main>)", s, re.S)  # the last </main> closes it
    desc = None
    for tag in re.findall(r"<meta\b[^>]*>", s):
        if re.search(r'name="description"', tag):
            c = re.search(r'content="([^"]*)"', tag)
            desc = html.unescape(c.group(1)) if c else None
    if not (mt and mm and desc):
        raise SystemExit(f"{relpath}: a hand-written page needs <title>, <meta name=\"description\"> and <main> (missing: "
                         + ", ".join(n for n, v in (("title", mt), ("description", desc), ("main", mm)) if not v) + ")")
    title = html.unescape(mt.group(1).strip())
    main = mm.group(1)
    main = re.sub(r'^\s*<nav class="crumbs".*?</nav>\n?', "", main, flags=re.S)  # ours, re-added below
    path = "/" + relpath[:-len("index.html")]
    bare = path[3:] if lang == "en" else path
    other = ("/en" + bare) if lang == "ko" else bare
    alt = other if os.path.exists(rel(other.lstrip("/") + "index.html")) else None
    parts = bare.strip("/").split("/")
    a, items, lds, current = None, [], [], None
    if parts[0] == "apps" and len(parts) == 2:
        a = BY_APP_PATH.get(parts[1]); current = "apps"
        name = a[lang]["name"] if a else title
        items = [(name, None)]
        if a: lds.append(app_ld(a, lang, path))
    elif parts[0] == "privacy" and len(parts) == 2:
        a = BY_PRIVACY_PATH.get(parts[1]); current = "privacy"
        name = a[lang]["name"] if a else title
        items = [(t["privacy"], url(lang, "/privacy/")), (name, None)]
        lds.append({"@context": "https://schema.org", "@type": "WebPage", "name": title, "url": SITE + path, "inLanguage": lang,
                    "isPartOf": {"@id": SITE_ID}, "publisher": org_ld(),
                    **({"about": {"@id": SITE + app_url(a, lang) + "#app"}} if a and a.get("app_path") else {})})
    nav, bc = crumbs(lang, items)
    lds.append(bc)
    og = f"/assets/og/{a['id']}-{lang}.png" if a else None
    og = og if og and os.path.exists(rel(og.lstrip("/"))) else None
    h = head(lang, title, desc, path, alt, og_type="article" if current == "privacy" else "website", og_image=og, lds=lds)
    body = accent_attr(a, "page-read")
    return page(lang, h, body, header(lang, current, alt or url("en" if lang == "ko" else "ko", "/")), f"    {nav}\n" + main, footer(lang))

def build_404():
    t = T["ko"]; te = T["en"]
    main = f'''    <section class="notfound">
      <h1>{t["nf_h"]}</h1>
      <p>{t["nf_p"]}</p>
      <div class="actions"><a class="button" href="/">{t["home"]}</a><a class="button button--outline" href="/privacy/">{t["privacy"]}</a></div>
      <p lang="en" class="muted" style="margin-top:32px">{te["nf_h"]}. {te["nf_p"]} <a href="/en/">English home</a></p>
    </section>'''
    h = head("ko", t["nf_title"], t["nf_p"], "/404.html", None, noindex=True)
    return page("ko", h, "", header("ko", None, "/en/"), main, footer("ko"))

# ---------------------------------------------------------------- sitemap, llms.txt
CHANGED = set()  # files this build rewrites; their lastmod is today

def git_date(relpath):
    if relpath in CHANGED:
        return datetime.date.today().isoformat()
    try:
        dirty = subprocess.run(["git", "status", "--porcelain", "--", relpath], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if not dirty:
            out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", relpath], cwd=ROOT, capture_output=True, text=True).stdout.strip()
            if out: return out
    except OSError:
        pass
    return datetime.date.today().isoformat()

def build_sitemap(pages):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for relpath in sorted(pages, key=lambda p: (p.startswith("en/"), p.count("/"), p)):
        if relpath == "404.html": continue
        path = "/" + relpath[:-len("index.html")]
        bare = path[3:] if path.startswith("/en/") else path
        ko_p, en_p = bare, "/en" + bare
        has_ko, has_en = (ko_p.lstrip("/") + "index.html") in pages, (en_p.lstrip("/") + "index.html") in pages
        out.append("  <url>")
        out.append(f"    <loc>{SITE + path}</loc>")
        out.append(f"    <lastmod>{git_date(relpath)}</lastmod>")
        if has_ko and has_en:
            out.append(f'    <xhtml:link rel="alternate" hreflang="ko" href="{SITE + ko_p}"/>')
            out.append(f'    <xhtml:link rel="alternate" hreflang="en" href="{SITE + en_p}"/>')
            out.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{SITE + ko_p}"/>')
        out.append("  </url>")
    out.append("</urlset>")
    return "\n".join(out) + "\n"

def build_llms():
    ko, en = T["ko"], T["en"]
    lines = ["# SugarMount", "",
             "> SugarMount is the Google Play developer name of simpest, an independent developer in Korea. "
             "It publishes small Android apps that each do one thing simply. Photo, video and document apps process files on the device "
             "without uploading them, no app requires an account, and every app has its own privacy policy written from its code. "
             f"Contact: {EMAIL}. Korean pages live at /, English pages at /en/.", "",
             "## Apps", ""]
    for a in APPS:
        d, k = a["en"], a["ko"]
        st = {"live": "on Google Play", "soon": "coming soon", "review": "in Play review"}[a["status"]]
        link = SITE + (app_url(a, "en") or privacy_url(a, "en"))
        lines.append(f"- [{d['name']} / {k['name']}]({link}): {d['tagline']} Package {a['package']}, {st}.")
    lines += ["", "## Privacy policies", ""]
    for a in APPS:
        if a.get("privacy_path"):
            lines.append(f"- [{a['en']['name']}]({SITE + privacy_url(a, 'en')}) · [한국어]({SITE + privacy_url(a, 'ko')})")
    lines += ["", "## Facts", ""]
    for q, x in en["home_faq"]:
        lines.append(f"- {q} {x}")
    lines += ["", "## Optional", "", f"- [Korean home (한국어)]({SITE}/): {ko['home_lead']}", f"- [Google Play developer page]({PLAY_DEV})", ""]
    return "\n".join(lines)

# ---------------------------------------------------------------- main
def all_pages():
    out = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if not d.startswith(".") and d not in ("tools", "data", "assets")]
        for f in fn:
            if f == "index.html" or (dp == ROOT and f == "404.html"):
                out.append(os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, "/"))
    return sorted(out)

def validate():
    """Fail on data that would produce broken links; warn about policy pages missing from apps.json."""
    errors, ids = [], set()
    for a in APPS:
        if a["id"] in ids: errors.append(f"duplicate id {a['id']}")
        ids.add(a["id"])
        for lang in ("ko", "en"):
            if lang not in a: errors.append(f"{a['id']}: missing {lang}"); continue
            for k in ("name", "brand", "tagline", "desc"):
                if not a[lang].get(k): errors.append(f"{a['id']}.{lang}: missing {k}")
        if not a.get("privacy_path"): errors.append(f"{a['id']}: missing privacy_path")
        for lang in ("", "en/"):
            if a.get("privacy_path") and not os.path.exists(rel(f"{lang}privacy/{a['privacy_path']}/index.html")):
                errors.append(f"{a['id']}: {lang}privacy/{a['privacy_path']}/index.html does not exist")
            if a.get("page") == "hand" and not os.path.exists(rel(f"{lang}apps/{a['app_path']}/index.html")):
                errors.append(f"{a['id']}: page is hand but {lang}apps/{a['app_path']}/index.html does not exist")
        if a.get("page") in ("hand", "generated") and not a.get("app_path"): errors.append(f"{a['id']}: page {a['page']} needs app_path")
        if a.get("page") == "none" and a.get("app_path"): errors.append(f"{a['id']}: page none but app_path set")
        for ext in (".png", ".webp"):
            if not os.path.exists(rel(a["icon"].lstrip("/") + ext)): errors.append(f"{a['id']}: missing {a['icon']}{ext}")
        if a["status"] not in ("live", "soon", "review"): errors.append(f"{a['id']}: bad status")
        if a.get("play") and a["status"] != "live": errors.append(f"{a['id']}: play is true but status is not live")
    known = {a.get("privacy_path") for a in APPS} | {a.get("app_path") for a in APPS}
    for p in all_pages():
        parts = p.split("/")
        if parts[0] == "en": parts = parts[1:]
        if len(parts) == 3 and parts[0] in ("apps", "privacy") and parts[1] not in known:
            print(f"warning: {p} is not in data/apps.json (no home card, list entry or footer link)", file=sys.stderr)
    if errors:
        raise SystemExit("data/apps.json problems:\n  " + "\n  ".join(errors))

def main():
    check = "--check" in sys.argv
    validate()
    outputs = {}
    generated = {"index.html", "en/index.html", "privacy/index.html", "en/privacy/index.html", "404.html"}
    for lang in ("ko", "en"):
        outputs[f"{'en/' if lang == 'en' else ''}index.html"] = build_home(lang)
        outputs[f"{'en/' if lang == 'en' else ''}privacy/index.html"] = build_privacy_index(lang)
        for a in APPS:
            if a.get("page") == "generated":
                p = f"{'en/' if lang == 'en' else ''}apps/{a['app_path']}/index.html"
                generated.add(p); outputs[p] = build_app(a, lang)
    outputs["404.html"] = build_404()
    for p in all_pages():
        if p not in generated:
            outputs[p] = wrap_hand(p)
    outputs["llms.txt"] = build_llms()
    for p_, content in outputs.items():
        full = rel(p_)
        if not os.path.exists(full) or open(full, encoding="utf-8").read() != content:
            CHANGED.add(p_)
    outputs["sitemap.xml"] = build_sitemap(set(all_pages()) | set(outputs) - {"sitemap.xml", "llms.txt"})
    changed = []
    for p, content in sorted(outputs.items()):
        full = rel(p)
        old = open(full, encoding="utf-8").read() if os.path.exists(full) else None
        if old != content:
            changed.append(p)
            if not check:
                os.makedirs(os.path.dirname(full) or ROOT, exist_ok=True)
                with open(full, "w", encoding="utf-8") as f: f.write(content)
    if check:
        if changed:
            print("out of date:", *changed, sep="\n  "); sys.exit(1)
        print("up to date")
    else:
        print(f"{len(outputs)} files, {len(changed)} changed")

if __name__ == "__main__":
    main()
