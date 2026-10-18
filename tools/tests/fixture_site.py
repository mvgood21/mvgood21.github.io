"""A small, fully valid in-memory site for tools/checks.py tests.

good_site() returns {relpath: str | bytes}. checks.run(empty_dir, outputs=good_site()) must report 0 errors;
each test changes one thing and expects one gate code. Pages: home, app hub, one app page, one help article,
privacy list, one policy (each ko + en), 404, sitemap, two feeds, robots, llms.txt, assets, content-dates.
"""
import datetime, json, os, re, sys
from email.utils import format_datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dates  # noqa: E402

SITE = "https://mvgood21.github.io"
ORG = {"@id": SITE + "/#org"}
WEBSITE = {"@id": SITE + "/#website"}
PUB, MOD, ART_PUB = "2026-10-01", "2026-10-05", "2026-10-03"

L = {
    "ko": {"apps": "앱", "privacy": "개인정보처리방침", "other": "English", "other_code": "en", "locale": "ko_KR",
           "alt_locale": "en_US"},
    "en": {"apps": "Apps", "privacy": "Privacy", "other": "한국어", "other_code": "ko", "locale": "en_US",
           "alt_locale": "ko_KR"},
}
LONG = {
    "ko": "이 문단은 검사 도구 시험용 본문입니다. 실제 페이지처럼 문장이 여러 개 이어지며, 피드 본문 길이 검사가 메타 설명보다 충분히 긴 본문을 "
          "요구하기 때문에 넉넉하게 씁니다. 사진을 줄이고, 문서를 열고, 글을 고치는 작은 앱들이 각자 한 가지 일을 합니다. "
          "본문에는 단락과 목록, 링크가 들어가며 링크는 모두 사이트 안의 실제 파일로 이어집니다. 끝.",
    "en": "This paragraph is the body text used by the checker tests. It runs for several sentences like a real page, because "
          "the feed gate wants a body much longer than the meta description. Small apps each do one job: shrink a photo, "
          "open a document, fix a sentence. The body holds paragraphs, a list and links that resolve to real files. End.",
}
DESC = {
    "ko": "검사 도구 시험용 페이지입니다. 실제 페이지와 같은 머리말 구조와 구조화 데이터를 갖추고, 모든 링크가 실제 파일로 이어지도록 만든 고정 예제입니다.",
    "en": "A fixed example page for the checker tests. It has the head and structured data of a real page, "
          "and every link resolves to a file.",
}


def pre(lang): return "/en" if lang == "en" else ""
def rp_of(lang, path): return (("en" + path) if lang == "en" else path).lstrip("/") + "index.html"


def iso(day): return dates.iso_datetime(day)


def crumbs_ld(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, **({"item": SITE + h} if h else {})}
        for i, (n, h) in enumerate(items)]}


def crumbs_nav(items):
    lis = "".join(f'<li><a href="{h}">{n}</a></li>' if h else f'<li><span aria-current="page">{n}</span></li>'
                  for n, h in items)
    return f'<nav class="crumbs" aria-label="crumbs"><ol>{lis}</ol></nav>'


def page(lang, path, title, main, lds=(), *, og="/assets/og.png", alt=True, noindex=False, data_app=None):
    t = L[lang]
    other_lang = "en" if lang == "ko" else "ko"
    bare = path[3:] if path.startswith("/en/") else path
    other_path = pre(other_lang) + bare
    ko_p, en_p = ("/" + bare.lstrip("/"), "/en" + bare) if True else None
    head = [f"<title>{title}</title>", f'<meta name="description" content="{DESC[lang]} ({path})">']  # unique per page
    if noindex:
        head.append('<meta name="robots" content="noindex">')
    else:
        head.append(f'<link rel="canonical" href="{SITE + path}">')
        if alt:
            head += [f'<link rel="alternate" hreflang="ko" href="{SITE + ko_p}">',
                     f'<link rel="alternate" hreflang="en" href="{SITE + en_p}">',
                     f'<link rel="alternate" hreflang="x-default" href="{SITE + ko_p}">']
        head.append(f'<meta property="og:url" content="{SITE + path}">')
    head += [f'<meta property="og:image" content="{SITE + og}">', f'<meta property="og:locale" content="{t["locale"]}">']
    if alt and not noindex:
        head.append(f'<meta property="og:locale:alternate" content="{t["alt_locale"]}">')
    head += ['<link rel="icon" type="image/png" sizes="64x64" href="https://mvgood21.github.io/assets/favicon.png">',
             '<link rel="stylesheet" href="/assets/site.css?v=1">']
    head += [f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in lds]
    switch = other_path if (alt and not noindex) else pre(other_lang) + "/"
    header = (f'<header class="site-header"><a class="brand" href="{pre(lang)}/">SugarMount</a>'
              f'<nav><a href="{pre(lang)}/apps/">{t["apps"]}</a> <a href="{pre(lang)}/privacy/">{t["privacy"]}</a> '
              f'<a class="lang" href="{switch}" lang="{t["other_code"]}" hreflang="{t["other_code"]}">{t["other"]}</a></nav></header>')
    footer = f'<footer><p class="footer-title">SugarMount</p><p>sugarmount21@gmail.com</p></footer>'
    da = f' data-app="{data_app}"' if data_app else ""
    nl = "\n  "
    return (f'<!DOCTYPE html>\n<html lang="{lang}">\n<head>\n  <meta charset="utf-8">\n  {nl.join(head)}\n</head>\n'
            f'<body>\n<a class="skip" href="#main">skip</a>\n{header}\n<main id="main"{da}>\n{main}\n</main>\n{footer}\n</body>\n</html>\n')


def body(lang, extra=""):
    return f'<p>{LONG[lang]}</p>\n<ul><li>{LONG[lang][:40]}</li></ul>\n{extra}'


def good_site():
    files = {}
    for lang in ("ko", "en"):
        t = L[lang]
        p = pre(lang)
        home_crumb = ("SugarMount", p + "/")
        app_name = "Foo 앱" if lang == "ko" else "Foo App"
        art_h1 = "갤럭시에서 Foo 하는 법" if lang == "ko" else "How to foo on a Galaxy phone"
        pol = "Foo 개인정보처리방침" if lang == "ko" else "Foo privacy policy"
        lead = {"ko": "SugarMount는 한 가지 일을 하는 작은 Android 앱을 만들고, 앱마다 소개와 개인정보처리방침을 둡니다.",
                "en": "SugarMount makes small Android apps that each do one job, and every app has its own page and "
                      "its own privacy policy written from the code."}[lang]

        # home
        if lang == "ko":
            home_ld = [{"@context": "https://schema.org", "@graph": [
                {"@type": "Organization", "@id": SITE + "/#org", "name": "SugarMount", "alternateName": ["슈가마운트"],
                 "url": SITE + "/", "logo": {"@type": "ImageObject", "url": SITE + "/assets/logo.png", "width": 512, "height": 512},
                 "email": "sugarmount21@gmail.com"},
                {"@type": "WebSite", "@id": SITE + "/#website", "name": "SugarMount", "url": SITE + "/",
                 "publisher": ORG}]}]
        else:
            home_ld = [{"@context": "https://schema.org", "@type": "WebPage", "@id": SITE + "/en/", "isPartOf": WEBSITE,
                        "about": ORG}]
        files[rp_of(lang, "/")] = page(lang, p + "/", "SugarMount – small apps" if lang == "en" else "SugarMount(슈가마운트) – 작은 앱",
                                       f'<h1>SugarMount</h1>\n<p class="lead">{lead}</p>\n'
                                       + body(lang, f'<p><a href="{p}/apps/foo/">{app_name}</a></p>'), home_ld)
        # hub
        files[rp_of(lang, "/apps/")] = page(
            lang, p + "/apps/", ("Android 앱 전체 목록 – SugarMount" if lang == "ko" else "All Android apps – SugarMount"),
            crumbs_nav([home_crumb, (t["apps"], None)]) + f'\n<h1>{t["apps"]}</h1>\n<p class="lead">{lead}</p>\n'
            + body(lang, f'<section id="photo"><h2>Photo</h2><h3><a href="{p}/apps/foo/">{app_name}</a></h3>'
                         f'<p class="status">Google Play</p><ul><li><a href="{p}/apps/foo/task/">{art_h1}</a></li></ul>'
                         f'<p><a href="{p}/privacy/foo/">{pol}</a></p></section>'),
            [crumbs_ld([home_crumb, (t["apps"], None)])])
        # app page
        og_app = f"/assets/og/app-foo-{lang}.png"
        app_url = SITE + p + "/apps/foo/"
        app_ld = [{"@context": "https://schema.org", "@graph": [
            {"@type": "WebPage", "@id": app_url, "url": app_url, "name": app_name, "isPartOf": WEBSITE,
             "primaryImageOfPage": {"@type": "ImageObject", "url": SITE + og_app, "width": 1200, "height": 630},
             "mainEntity": {"@id": app_url + "#app"}, "dateModified": iso(MOD)},
            {"@type": ["MobileApplication"], "@id": app_url + "#app", "name": app_name, "url": app_url,
             "operatingSystem": "Android 8.0 이상", "applicationCategory": "UtilitiesApplication",
             "description": "Foo는 한 가지 일을 합니다.", "image": SITE + "/assets/apps/foo/icon.png",
             "screenshot": [{"@type": "ImageObject", "url": SITE + "/assets/apps/foo/shot1-ko.webp", "width": 360, "height": 780}],
             "offers": {"@type": "Offer", "price": "0", "priceCurrency": "KRW"},
             "installUrl": "https://play.google.com/store/apps/details?id=com.example.foo",
             "author": ORG, "publisher": ORG}]},
            crumbs_ld([home_crumb, (t["apps"], p + "/apps/"), (app_name, None)])]
        files[rp_of(lang, "/apps/foo/")] = page(
            lang, p + "/apps/foo/", f"{app_name}: 사진 줄이기 – SugarMount" if lang == "ko" else f"{app_name}: shrink photos for Android – SugarMount",
            crumbs_nav([home_crumb, (t["apps"], p + "/apps/"), (app_name, None)])
            + f'\n<img src="/assets/apps/foo/icon.webp" width="96" height="96" alt="">\n<h1>{app_name}</h1>\n<p class="lead">{lead}</p>\n'
            + body(lang, f'<p><a href="{p}/privacy/foo/">{pol}</a> · '
                         f'<a href="https://play.google.com/store/apps/details?id=com.example.foo" rel="noopener">Foo Google Play</a></p>'
                         f'<img src="/assets/apps/foo/shot1-ko.webp" width="360" height="780" loading="lazy" alt="Foo main screen">'
                         f'<h2 id="guides">Help</h2><ul><li><a href="{p}/apps/foo/task/">{art_h1}</a></li></ul>'),
            app_ld, og=og_app, data_app="foo")
        # help article
        art_url = SITE + p + "/apps/foo/task/"
        art_ld = [{"@context": "https://schema.org", "@type": "Article", "@id": art_url + "#article", "headline": art_h1,
                   "url": art_url, "mainEntityOfPage": art_url, "inLanguage": lang,
                   "datePublished": iso(ART_PUB), "dateModified": iso(MOD), "image": [SITE + "/assets/og.png"],
                   "author": ORG, "publisher": ORG, "isPartOf": WEBSITE, "about": {"@id": app_url + "#app"}},
                  crumbs_ld([home_crumb, (t["apps"], p + "/apps/"), (app_name, p + "/apps/foo/"), (art_h1, None)])]
        files[rp_of(lang, "/apps/foo/task/")] = page(
            lang, p + "/apps/foo/task/", art_h1 + " – SugarMount",
            crumbs_nav([home_crumb, (t["apps"], p + "/apps/"), (app_name, p + "/apps/foo/"), (art_h1, None)])
            + f'\n<h1>{art_h1}</h1>\n<p class="lead">{lead}</p>\n<!-- build:toc --><nav class="toc"><a href="#one">1</a></nav><!-- /build:toc -->\n'
            + body(lang, f'<h2 id="one">One</h2><p>a <a href="#three">see three</a></p><h2 id="two">Two</h2><p>b</p><h2 id="three">Three</h2>'
                         f'<p><a href="{p}/apps/foo/">{app_name} {"소개" if lang == "ko" else "overview"}</a></p>'),
            art_ld)
        # privacy list + policy
        files[rp_of(lang, "/privacy/")] = page(
            lang, p + "/privacy/", t["privacy"] + " – SugarMount",
            crumbs_nav([home_crumb, (t["privacy"], None)]) + f'\n<h1>{t["privacy"]}</h1>\n'
            + body(lang, f'<p><a href="{p}/privacy/foo/">{pol} {"보기" if lang == "ko" else "(read)"}</a></p>'),
            [crumbs_ld([home_crumb, (t["privacy"], None)])])
        files[rp_of(lang, "/privacy/foo/")] = page(
            lang, p + "/privacy/foo/", pol + " – SugarMount",
            crumbs_nav([home_crumb, (t["privacy"], p + "/privacy/"), (app_name, None)]) + f'\n<h1>{pol}</h1>\n'
            + body(lang, f'<!-- build:extra --><p><a href="{p}/apps/foo/">{app_name} {"소개 보기" if lang == "ko" else "page"}</a></p><!-- /build:extra -->'),
            [{"@context": "https://schema.org", "@type": "WebPage", "@id": SITE + p + "/privacy/foo/", "isPartOf": WEBSITE,
              "about": {"@id": app_url + "#app"}},
             crumbs_ld([home_crumb, (t["privacy"], p + "/privacy/"), (app_name, None)])])

    files["404.html"] = page("ko", "/404.html", "페이지를 찾을 수 없습니다 – SugarMount",
                             '<h1>페이지를 찾을 수 없습니다</h1><p><a href="/">SugarMount 홈</a></p>', noindex=True, alt=False)

    indexable = sorted(k for k in files if k.endswith("index.html"))
    entries = {k: {"hash": "0" * 16, "published": PUB, "modified": MOD} for k in indexable}
    for k in ("apps/foo/task/index.html", "en/apps/foo/task/index.html"):
        entries[k]["published"] = ART_PUB
    files["data/content-dates.json"] = json.dumps(entries, indent=1)

    def url_of(rp): return SITE + "/" + rp[:-len("index.html")]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for k in indexable:
        bare = k[3:] if k.startswith("en/") else k
        sm += ["<url>", f"<loc>{url_of(k)}</loc>", f"<lastmod>{entries[k]['modified']}</lastmod>",
               f'<xhtml:link rel="alternate" hreflang="ko" href="{url_of(bare)}"/>',
               f'<xhtml:link rel="alternate" hreflang="en" href="{url_of("en/" + bare)}"/>',
               f'<xhtml:link rel="alternate" hreflang="x-default" href="{url_of(bare)}"/>', "</url>"]
    files["sitemap.xml"] = "\n".join(sm + ["</urlset>"]) + "\n"

    def feed(lang):
        p = "en/" if lang == "en" else ""
        items = [f"{p}apps/foo/task/index.html", f"{p}apps/foo/index.html", f"{p}apps/index.html"]
        out = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>',
               "<title>SugarMount</title>", f"<link>{SITE}/</link>", "<description>d</description>"]
        for k in items:
            main = files[k].split('<main id="main"', 1)[1].split(">", 1)[1].rsplit("</main>", 1)[0]
            main = main.split("</nav>", 1)[1] if main.lstrip().startswith("<nav") else main
            main = re.sub(r"<!-- build:(meta|toc) -->.*?<!-- /build:\1 -->", "", main, flags=re.S)
            main = main.replace('href="/', f'href="{SITE}/').replace('src="/', f'src="{SITE}/').replace('href="#', f'href="{url_of(k)}#')
            day = entries[k]["published"]
            pd = format_datetime(datetime.datetime.fromisoformat(day + "T09:00:00+09:00"))
            out += ["<item>", f"<title>t</title>", f"<link>{url_of(k)}</link>",
                    f"<description><![CDATA[{main}]]></description>", f"<pubDate>{pd}</pubDate>", "</item>"]
        return "\n".join(out + ["</channel></rss>"]) + "\n"
    files["rss.xml"] = feed("ko")
    files["en/rss.xml"] = feed("en")
    files["robots.txt"] = ("User-agent: *\nAllow: /\nDisallow: /tools/\nDisallow: /data/\nDisallow: /AGENTS.md\n"
                           f"Disallow: /404.html\n\nSitemap: {SITE}/sitemap.xml\n")
    files["llms.txt"] = f"# SugarMount\n\n- [Foo]({SITE}/en/apps/foo/)\n"
    files["assets/site.css"] = ("@font-face{font-family:'P';src:url(fonts/hangul.woff2) format('woff2');unicode-range:U+AC00-D7A3}\n"
                                "@font-face{font-family:'P';src:url(fonts/latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+2013}\n"
                                "body{font-family:P,system-ui}\n")
    files["assets/fonts/hangul.woff2"] = b"\0" * 2000
    files["assets/fonts/latin.woff2"] = b"\0" * 1000
    files["assets/og.png"] = b"\x89PNG" + b"\0" * 9000
    files["assets/logo.png"] = b"\x89PNG" + b"\0" * 9000
    files["assets/favicon.png"] = b"\x89PNG" + b"\0" * 900
    for lang in ("ko", "en"):
        files[f"assets/og/app-foo-{lang}.png"] = b"\x89PNG" + b"\0" * 9000
    files["assets/apps/foo/icon.webp"] = webp(b"VP8 ", 3000)
    files["assets/apps/foo/icon.png"] = b"\x89PNG" + b"\0" * 5000
    files["assets/apps/foo/shot1-ko.webp"] = webp(b"VP8 ", 30000)
    return files


def webp(chunk, size):
    payload = b"\0" * size
    data = b"WEBP" + chunk + len(payload).to_bytes(4, "little") + payload
    return b"RIFF" + len(data).to_bytes(4, "little") + data
