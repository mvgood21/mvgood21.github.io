#!/usr/bin/env python3
"""Site gates for the SugarMount site (IA spec 3.1, 4.1-4.4, 5.3, 6.4, 9.1). Standard library only. Read-only.

  python tools/checks.py                      # every gate over the built site; exit 1 on any error
  python tools/checks.py --file <path> ...    # content authors: gates for one hand-written file (no build needed)
  python tools/checks.py --no-warnings        # print errors only
  python tools/checks.py --root <dir>         # check another checkout

Errors fail (exit 1). Warnings (length rules, brand spelling, tiny font subsets) never fail.
Every issue has a stable code (e.g. SD-CRUMB-HOME); tools/tests/test_checks.py pins each gate to its code.

From tools/build.py (WP-A wires it):
    import checks
    report = checks.run(ROOT, outputs)   # outputs: {relpath: text} from this build overrides the files on disk
    report.print(); sys.exit(1) if report.errors else None
"""
import html, json, os, re, struct, sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dates  # noqa: E402
from legal_chrome import STANDALONE_PATHS  # noqa: E402  (pages the build never wraps; not checked)

ROOT = dates.ROOT
SITE = "https://sugarmount21.com"
SITE_HOST = "sugarmount21.com"
ORG_ID = SITE + "/#org"
SITE_ID = SITE + "/#website"
NOINDEX_PATHS = frozenset({"404.html", "design/index.html"})
ACCENT_DEMO_PAGES = frozenset({"design/index.html"})  # SDS demo (noindex): data-app samples allowed inside <main>
ADS_ORIGIN = "pagead2.googlesyndication.com"  # async AdSense loader, AX notes only (see the script check)
ALLOWED_ORIGINS = frozenset()          # e.g. {"gc.zgo.at"} once the owner approves one analytics origin
OWNERSHIP_FILES = ("google83e3e62aee87a145.html", "naverc6d2c9710a0b598bb0562751a0d005b7.html",
                   "naver336622988ccb96edbbdc3ad02fd2f6eb.html")
LINK_FILE_EXCEPTIONS = frozenset({"/sitemap.xml", "/rss.xml", "/en/rss.xml", "/llms.txt", "/404.html"})
FEEDS = ("rss.xml", "en/rss.xml")
ROBOTS_DISALLOW = ("/tools/", "/data/", "/AGENTS.md", "/404.html")
ORG_FULL_PAGES = frozenset({"index.html", "about/index.html", "en/about/index.html"})

KB = 1024
BUDGET = {
    # sds_apps_css: about 310 B per app; 12 apps took 4092 B, so the 13th (trimbox, 2026-10-30) needs a raise to 5 KB
    "html": 40 * KB, "html_privacy": 60 * KB, "site_css": 40 * KB, "sds_apps_css": 5 * KB, "js": 1 * KB,
    "icons_per_page": 80 * KB, "shot": 80 * KB, "og_max": 200 * KB, "og_min": 5 * KB, "rss": 10 * 1000 * 1000,
    "font_home": 400 * KB, "font_page": 470 * KB, "font_en": 70 * KB,
    # assets/fonts/pretendard.css (generated). SDS 10/11 says 20 KB; the 30 Hangul subsets the site's text needs already
    # take ~20.9 KB of @font-face rules that cannot shrink without dropping glyph coverage, so the gate sits at 24 KB
    # (deliberate raise, 2026-10-18 final review; the spec owner should confirm or lower it).
    "font_css": 24 * KB,
}
LEN = {  # IA 3.1, Python len()
    "ko": {"topic": 30, "title": 44, "desc": (60, 110), "lead": (40, 90)},
    "en": {"topic": 50, "title": 65, "desc": (110, 160), "lead_words": (25, 45)},
}
TITLE_SUFFIX = " – SugarMount"
GENERIC_ANCHORS = {"자세히 보기", "자세히", "더 보기", "더보기", "여기", "바로가기", "learn more", "read more", "more", "here",
                   "click here", "details"}
LEAD_KINDS = {"home", "hub", "app", "article", "ax-hub", "ax-note", "ax-topic", "about"}
ARTICLE_KINDS = {"article", "ax-note"}
TZ_RE = re.compile(r"T\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z)$")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SKIP_TEXT = {"script", "style", "template", "noscript"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


# ------------------------------------------------------------------ report
class Issue:
    __slots__ = ("level", "code", "path", "msg")

    def __init__(self, level, code, path, msg):
        self.level, self.code, self.path, self.msg = level, code, path, msg

    def __str__(self):
        return f"{self.level}: [{self.code}] {self.path}: {self.msg}"


class Report:
    def __init__(self):
        self.issues = []

    def error(self, code, path, msg): self.issues.append(Issue("error", code, path, msg))
    def warn(self, code, path, msg): self.issues.append(Issue("warning", code, path, msg))

    @property
    def errors(self): return [i for i in self.issues if i.level == "error"]
    @property
    def warnings(self): return [i for i in self.issues if i.level == "warning"]

    def codes(self, level=None):
        return {i.code for i in self.issues if level is None or i.level == level}

    def print(self, warnings=True, file=sys.stdout):
        for i in self.issues:
            if warnings or i.level == "error":
                print(i, file=file)
        print(f"checks: {len(self.errors)} errors, {len(self.warnings)} warnings", file=file)


# ------------------------------------------------------------------ tiny DOM
class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent

    def get(self, k, default=None):
        v = self.attrs.get(k, default)
        return default if v is None and default is not None else v

    def classes(self): return (self.attrs.get("class") or "").split()

    def iter(self):
        for c in self.children:
            if isinstance(c, Node):
                yield c
                yield from c.iter()

    def find_all(self, *tags):
        return [n for n in self.iter() if n.tag in tags]

    def find(self, tag):
        for n in self.iter():
            if n.tag == tag: return n
        return None

    def ancestors(self):
        p = self.parent
        while p is not None:
            yield p
            p = p.parent

    def text(self):
        out = []
        for c in self.children:
            if isinstance(c, Node):
                if c.tag not in SKIP_TEXT: out.append(c.text())
            else:
                out.append(c)
        return "".join(out)

    def element_children(self): return [c for c in self.children if isinstance(c, Node)]


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(n)
        if tag not in VOID: self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        n = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(n)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(text):
    b = _Builder()
    b.feed(text); b.close()
    return b.root


def text_nodes(node):
    for c in node.children:
        if isinstance(c, Node):
            if c.tag not in SKIP_TEXT: yield from text_nodes(c)
        else:
            yield c


def norm_ws(s): return re.sub(r"\s+", " ", s or "").strip()


# ------------------------------------------------------------------ site model
def page_kind(relpath):
    bare = relpath[3:] if relpath.startswith("en/") else relpath
    if bare == "404.html": return "404"
    if not bare.endswith("index.html"): return "other"
    parts = [p for p in bare[:-len("index.html")].split("/") if p]
    if not parts: return "home"
    head, n = parts[0], len(parts)
    if head == "apps": return {1: "hub", 2: "app", 3: "article"}.get(n, "other")
    if head == "ax": return "ax-topic" if n == 3 and parts[1] == "topic" else {1: "ax-hub", 2: "ax-note"}.get(n, "other")
    if head == "about" and n == 1: return "about"
    if head == "privacy": return "privacy-list" if n == 1 else "policy"
    if head == "design" and n == 1: return "design"
    return "other"


def page_lang_of(relpath): return "en" if relpath.startswith("en/") else "ko"


def counterpart(relpath):
    if relpath in NOINDEX_PATHS or relpath == "404.html": return None
    return relpath[3:] if relpath.startswith("en/") else "en/" + relpath


def url_of(relpath):
    return "/" + (relpath[:-len("index.html")] if relpath.endswith("index.html") else relpath)


class Link:
    __slots__ = ("raw", "internal", "path", "relpath", "fragment", "host", "scheme")

    def __init__(self, raw, internal, path=None, relpath=None, fragment="", host="", scheme=""):
        self.raw, self.internal, self.path, self.relpath = raw, internal, path, relpath
        self.fragment, self.host, self.scheme = fragment, host, scheme

    @property
    def target(self):
        """Normalised identity for anchor comparison."""
        if self.scheme == "mailto":  # same mailbox: a prefilled ?subject= is not a different destination
            return self.raw.strip().split("?", 1)[0].lower()
        if not self.internal: return self.raw.strip()
        return url_of(self.relpath) + (("#" + self.fragment) if self.fragment else "")


def resolve(href, base_relpath):
    """Resolve an href/src against the page it appears on."""
    raw = (href or "").strip()
    low = raw.lower()
    for scheme in ("mailto:", "tel:", "data:", "javascript:", "sms:", "intent:", "market:"):
        if low.startswith(scheme): return Link(raw, False, scheme=scheme[:-1])
    if low.startswith(("http://", "https://", "//")):
        sp = urlsplit(raw if not raw.startswith("//") else "https:" + raw)
        if sp.hostname != SITE_HOST:
            return Link(raw, False, host=sp.hostname or "", scheme=sp.scheme)
        path, frag = sp.path or "/", sp.fragment
    else:
        base = url_of(base_relpath) if base_relpath else "/"
        if base_relpath and not base_relpath.endswith("index.html"):
            base = "/" + base_relpath  # e.g. 404.html, rss.xml: resolve against the file
        joined = urljoin(base, raw)
        sp = urlsplit(joined)
        path, frag = sp.path or "/", sp.fragment
    path = unquote(path)
    relpath = path.lstrip("/")
    if path.endswith("/"): relpath += "index.html"
    return Link(raw, True, path=path, relpath=relpath, fragment=frag)


class Page:
    def __init__(self, site, relpath, text):
        self.site, self.relpath, self.text = site, relpath, text
        self.dom = parse_html(text)
        h = self.dom.find("html")
        self.lang = ((h.get("lang") if h else None) or page_lang_of(relpath)).split("-")[0]
        self.kind = page_kind(relpath)
        mains = self.dom.find_all("main")
        self.main = mains[-1] if mains else None
        self.head = self.dom.find("head")
        t = self.dom.find("title")
        self.title = norm_ws(t.text()) if t else None
        self.metas = [n for n in self.dom.find_all("meta")]
        self.links = [n for n in self.dom.find_all("link")]

    def meta(self, name=None, prop=None):
        for m in self.metas:
            if name and (m.get("name") or "").lower() == name: return m.get("content")
            if prop and m.get("property") == prop: return m.get("content")
        return None

    def metas_prop(self, prop): return [m.get("content") for m in self.metas if m.get("property") == prop]

    @property
    def desc(self):
        d = self.meta(name="description")
        return norm_ws(d) if d is not None else None

    def link_rel(self, rel):
        return [l for l in self.links if rel in (l.get("rel") or "").lower().split()]

    def hreflangs(self):
        return {l.get("hreflang"): l.get("href") for l in self.link_rel("alternate") if l.get("hreflang")}

    def jsonld(self):
        """[(raw, parsed or None, error)]"""
        out = []
        for s in self.dom.find_all("script"):
            if (s.get("type") or "").lower() == "application/ld+json":
                raw = "".join(c for c in s.children if isinstance(c, str))
                try:
                    out.append((raw, json.loads(raw), None))
                except ValueError as e:
                    out.append((raw, None, str(e)))
        return out

    def ids(self):
        return {n.get("id") for n in self.dom.iter() if n.get("id")}

    def in_main(self, node):
        return self.main is not None and any(a is self.main for a in node.ancestors())


class Site:
    def __init__(self, root=ROOT, outputs=None):
        self.root = root
        self.outputs = {k.replace(os.sep, "/"): v for k, v in (outputs or {}).items()}
        self._pages = {}
        self._dates = False

    def path(self, relpath): return os.path.join(self.root, relpath)

    def exists(self, relpath):
        if relpath in self.outputs: return True
        return os.path.isfile(self.path(relpath))

    def read(self, relpath):
        if relpath in self.outputs: return self.outputs[relpath]
        p = self.path(relpath)
        if not os.path.isfile(p): return None
        with open(p, encoding="utf-8") as f: return f.read()

    def size(self, relpath):
        if relpath in self.outputs:
            v = self.outputs[relpath]
            return len(v.encode("utf-8")) if isinstance(v, str) else len(v)
        p = self.path(relpath)
        return os.path.getsize(p) if os.path.isfile(p) else None

    def read_bytes(self, relpath, n=None):
        if relpath in self.outputs:
            v = self.outputs[relpath]
            b = v.encode("utf-8") if isinstance(v, str) else v
            return b[:n] if n else b
        with open(self.path(relpath), "rb") as f: return f.read(n) if n else f.read()

    def html_pages(self):
        out = set()
        for dp, dn, fn in os.walk(self.root):
            dn[:] = [d for d in dn if not d.startswith(".") and d not in ("tools", "data", "assets", "node_modules")]
            for f in fn:
                if f == "index.html" or (dp == self.root and f == "404.html"):
                    out.add(os.path.relpath(os.path.join(dp, f), self.root).replace(os.sep, "/"))
        for k in self.outputs:
            top = k.split("/", 1)[0]
            if top in ("tools", "data", "assets"): continue
            if k.endswith("index.html") or k == "404.html": out.add(k)
        return sorted(out - STANDALONE_PATHS)

    def files_under(self, prefix):
        out = set()
        base = self.path(prefix)
        for dp, dn, fn in os.walk(base):
            for f in fn:
                out.add(os.path.relpath(os.path.join(dp, f), self.root).replace(os.sep, "/"))
        out |= {k for k in self.outputs if k.startswith(prefix.rstrip("/") + "/")}
        return sorted(out)

    def page(self, relpath):
        if relpath not in self._pages:
            text = self.read(relpath)
            self._pages[relpath] = Page(self, relpath, text) if text is not None else None
        return self._pages[relpath]

    @property
    def dates(self):
        """content-dates entries, or None when the file does not exist yet."""
        if self._dates is False:
            raw = self.read(dates.DATES_FILE)
            self._dates = json.loads(raw) if raw else None
        return self._dates


# ------------------------------------------------------------------ helpers
def jsonld_nodes(x):
    if isinstance(x, dict):
        if "@type" in x or "@id" in x: yield x
        for v in x.values(): yield from jsonld_nodes(v)
    elif isinstance(x, list):
        for v in x: yield from jsonld_nodes(v)


def types_of(node):
    t = node.get("@type")
    return set(t) if isinstance(t, list) else {t} if t else set()


def has_key_anywhere(x, keys):
    if isinstance(x, dict):
        for k, v in x.items():
            if k in keys or has_key_anywhere(v, keys): return True
    elif isinstance(x, list):
        return any(has_key_anywhere(v, keys) for v in x)
    return False


def is_abs(u): return isinstance(u, str) and u.startswith(("https://", "http://"))


def image_urls(v):
    if isinstance(v, str): return [v]
    if isinstance(v, dict):
        u = v.get("url") or v.get("contentUrl")
        return [u] if isinstance(u, str) else []
    if isinstance(v, list):
        return [u for x in v for u in image_urls(x)]
    return []


def srcset_urls(v):
    return [part.strip().split()[0] for part in (v or "").split(",") if part.strip()]


def title_topic(title):
    return title[:-len(TITLE_SUFFIX)] if title.endswith(TITLE_SUFFIX) else title


def parse_unicode_range(spec):
    """'U+0-FF, U+4??' -> [(lo, hi)]"""
    out = []
    for part in (spec or "").split(","):
        p = part.strip().upper()
        if not p.startswith("U+"): continue
        p = p[2:]
        if "?" in p:
            out.append((int(p.replace("?", "0"), 16), int(p.replace("?", "F"), 16)))
        elif "-" in p:
            a, b = p.split("-", 1); out.append((int(a, 16), int(b, 16)))
        else:
            out.append((int(p, 16), int(p, 16)))
    return out


def font_faces(css_text, css_relpath):
    """[(family, weight, style, font_relpath or external url, ranges or None)]"""
    faces = []
    for body in re.findall(r"@font-face\s*\{(.*?)\}", css_text, re.S | re.I):
        fam = re.search(r"font-family\s*:\s*([^;]+)", body, re.I)
        wt = re.search(r"font-weight\s*:\s*([^;]+)", body, re.I)
        st = re.search(r"font-style\s*:\s*([^;]+)", body, re.I)
        ur = re.search(r"unicode-range\s*:\s*([^;]+)", body, re.I)
        src = re.search(r"src\s*:\s*([^;]+)", body, re.I | re.S)
        urls = re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", src.group(1)) if src else []
        if not urls: continue
        lk = resolve(urls[0], css_relpath)
        faces.append(((fam.group(1).strip().strip("'\"") if fam else ""), (wt.group(1).strip() if wt else "400"),
                      (st.group(1).strip() if st else "normal"), lk.relpath if lk.internal else urls[0],
                      parse_unicode_range(ur.group(1)) if ur else None))
    return faces


def css_urls(css_text):
    return re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", css_text) + re.findall(r"@import\s+['\"]([^'\"]+)['\"]", css_text)


def webp_lossless(head):
    """True for VP8L (lossless) WebP. head = first bytes of the file."""
    if head[:4] != b"RIFF" or head[8:12] != b"WEBP": return False
    pos = 12
    while pos + 8 <= len(head):
        tag = head[pos:pos + 4]
        size = struct.unpack("<I", head[pos + 4:pos + 8])[0]
        if tag == b"VP8L": return True
        if tag == b"VP8 ": return False
        pos += 8 + size + (size & 1)
    return False


FONT_SYSTEM_TAGS = {"code", "pre", "kbd", "samp", "svg", "textarea"}  # drawn in the mono/system stack by site.css
FONT_BUDGET_WARN_KINDS = frozenset({"policy", "design"})  # ko pages with no font limit in IA 9.1 (warning only)
EN_FONT_FAMILY = "Pretendard Latin"  # tools/sds_apps.py EN_FAMILY; when present, /en/ pages use only this family


def page_chars(page):
    """Characters a page draws in the Pretendard stack (SDS 5.2-4; same rule as build.py _FontChars and site.css):
    code/pre/kbd/samp/svg/textarea, `.sym` and, on English pages, any [lang=ko] subtree use the system font."""
    chars = set()
    body = page.dom.find("body") or page.dom

    def walk(n, lang_ok):
        for c in n.children:
            if isinstance(c, Node):
                if c.tag in SKIP_TEXT or c.tag in FONT_SYSTEM_TAGS or "sym" in c.classes(): continue
                l = (c.get("lang") or "").split("-")[0]
                walk(c, lang_ok and not (page.lang == "en" and l == "ko"))
            elif lang_ok:
                chars.update(c)
    walk(body, True)
    chars.discard("\n"); chars.discard("\t"); chars.discard("\r")
    return chars


# ------------------------------------------------------------------ page gates
def check_lengths(page, report):
    """IA 3.1 length and wording rules: warnings only."""
    p, lang = page.relpath, page.lang
    rule = LEN.get(lang, LEN["en"])
    if page.title is None:
        report.error("TITLE-MISSING", p, "no <title>")
    else:
        topic = title_topic(page.title)
        if len(page.title) > rule["title"]:
            report.warn("TITLE-LENGTH", p, f"title {len(page.title)} chars > {rule['title']}: {page.title}")
        if len(topic) > rule["topic"]:
            report.warn("TITLE-TOPIC-LENGTH", p, f"title topic {len(topic)} chars > {rule['topic']}: {topic}")
        if " | " in page.title:
            report.warn("TITLE-SEPARATOR", p, "use ' – SugarMount', not ' | '")
        if (page.kind not in ("home", "about") and not page.title.endswith(TITLE_SUFFIX)
                and len(page.title + TITLE_SUFFIX) <= rule["title"]):
            report.warn("TITLE-SUFFIX", p, "title fits with ' – SugarMount' but has no suffix")
        words = [w.lower() for w in re.findall(r"[\w가-힣]{2,}", page.title)]
        dup = sorted({w for w in words if words.count(w) > 1})
        if dup:
            report.warn("TITLE-REPEAT", p, "title repeats " + ", ".join(dup))
    d = page.desc
    if d is None:
        report.error("DESC-MISSING", p, "no meta description")
    else:
        lo, hi = rule["desc"]
        if not lo <= len(d) <= hi:
            report.warn("DESC-LENGTH", p, f"description {len(d)} chars, want {lo}-{hi}")
        if page.title and d == page.title:
            report.warn("DESC-EQUALS-TITLE", p, "description equals title")
    if page.kind in LEAD_KINDS and page.main is not None:
        h1 = page.main.find("h1")
        lead = None
        if h1 is not None:
            sibs = h1.parent.element_children()
            i = next(k for k, s in enumerate(sibs) if s is h1)
            nxt = sibs[i + 1] if i + 1 < len(sibs) else None
            if nxt is not None and nxt.tag == "p" and "lead" in nxt.classes(): lead = nxt
        if lead is None:
            report.warn("LEAD-POSITION", p, 'no <p class="lead"> right after the H1')
        else:
            t = norm_ws(lead.text())
            if lang == "ko":
                lo, hi = rule["lead"]
                if not lo <= len(t) <= hi: report.warn("LEAD-LENGTH", p, f"lead {len(t)} chars, want {lo}-{hi}")
            else:
                lo, hi = LEN["en"]["lead_words"]
                n = len(t.split())
                if not lo <= n <= hi: report.warn("LEAD-LENGTH", p, f"lead {n} words, want {lo}-{hi}")
    body = page.main if page.main is not None else page.dom
    text = " ".join(t for t in text_nodes(body))  # text nodes apart, so "Photo</h2><p>SugarMount" is two words
    for m in re.finditer(r"(?<![\w./@-])(Sugar\s+Mount|Sugarmount|SUGARMOUNT|sugarmount|SugarMOUNT|슈가\s+마운트)(?![\w@.])", text):
        report.warn("BRAND-VARIANT", p, f"brand spelled {m.group(1)!r}; use SugarMount / 슈가마운트")
    if lang == "ko":
        for m in re.finditer(r"(?<!한글뷰어 )슈가독", text):
            ctx = text[max(0, m.start() - 8):m.end() + 4].replace("\n", " ")
            report.warn("BRAND-SUGARDOC", p, f"write 한글뷰어 슈가독, not 슈가독 alone (…{ctx}…)")
            break


def check_headings(page, report, file_mode):
    p = page.relpath
    scope = page.main if file_mode else page.dom
    if scope is None:
        report.error("MAIN-MISSING", p, "no <main>"); return
    h1s = scope.find_all("h1")
    if len(h1s) != 1:
        report.error("H1-COUNT", p, f"{len(h1s)} <h1> elements, want 1")
    for h in scope.find_all(*HEADINGS):
        if not file_mode and not page.in_main(h):
            report.error("HEADING-OUTSIDE-MAIN", p, f"<{h.tag}> outside <main>: {norm_ws(h.text())[:40]}")
        for n in h.iter():
            if n.tag in ("button", "img") or "badge" in n.classes():
                report.error("HEADING-NONTEXT", p, f"<{h.tag}> contains <{n.tag} class={n.get('class')!r}>")
    if page.kind in ARTICLE_KINDS and page.main is not None:
        h2s = page.main.find_all("h2")
        if len(h2s) >= 3:
            for h in h2s:
                if not h.get("id"):
                    report.error("TOC-H2-ID", p, f"h2 without id on a TOC page: {norm_ws(h.text())[:40]}")
    seen = {}
    for n in scope.iter():
        i = n.get("id")
        if i:
            if i in seen: report.error("DUP-ID", p, f"id {i!r} used twice")
            seen[i] = True


def check_links(page, report, file_mode):
    p, site = page.relpath, page.site
    scope = page.main if file_mode else page.dom
    if scope is None: return
    ids = page.ids()
    anchors = {}
    for n in scope.iter():
        if "onclick" in n.attrs:
            report.error("JS-LINK", p, f"<{n.tag} onclick> (JS-only links are not crawled)")
        attrs = []
        if n.tag in ("a", "area") and n.get("href") is not None: attrs.append(("href", n.get("href")))
        if n.tag in ("img", "source", "script", "iframe", "video", "audio", "track", "embed") and n.get("src"):
            attrs.append(("src", n.get("src")))
        if n.tag in ("img", "source") and n.get("srcset"):
            attrs += [("srcset", u) for u in srcset_urls(n.get("srcset"))]
        if n.tag == "link" and n.get("href") and not {"canonical", "alternate"} & set((n.get("rel") or "").lower().split()):
            attrs.append(("href", n.get("href")))
        if n.tag == "video" and n.get("poster"): attrs.append(("poster", n.get("poster")))
        for attr, v in attrs:
            lk = resolve(v, p)
            if lk.scheme == "javascript":
                report.error("JS-LINK", p, f"{attr}={v!r}")
                continue
            if not lk.internal: continue
            if v.strip().startswith("#"):
                if lk.fragment and not lk.fragment.startswith(":~:") and lk.fragment not in ids:
                    report.error("LINK-FRAGMENT", p, f"#{lk.fragment} has no matching id on this page")
                continue
            target_exists = site.exists(lk.relpath)
            if not target_exists:
                if site.exists(lk.relpath.rstrip("/") + "/index.html"):
                    report.error("LINK-FORMAT", p, f"{v!r}: page links end with '/'")
                else:
                    report.error("LINK-BROKEN", p, f"{attr}={v!r} does not resolve to a file ({lk.relpath})")
                continue
            if n.tag == "a":
                raw_path = urlsplit(v.strip()).path
                is_page = lk.relpath.endswith(".html")
                if is_page and lk.path not in LINK_FILE_EXCEPTIONS:
                    if not v.strip().startswith(("/", "https://", "http://")):
                        report.error("LINK-FORMAT", p, f"{v!r}: write internal page links as /path/")
                    elif raw_path.endswith("index.html"):
                        report.error("LINK-FORMAT", p, f"{v!r}: link the directory with a trailing '/', not index.html")
                    elif v.strip().startswith("http"):
                        report.warn("LINK-ABSOLUTE", p, f"{v!r}: internal links are usually root-relative")
                if lk.fragment and not lk.fragment.startswith(":~:") and lk.relpath.endswith(".html"):
                    tp = site.page(lk.relpath)
                    if tp is not None and lk.fragment not in tp.ids():
                        report.error("LINK-FRAGMENT", p, f"{v!r}: #{lk.fragment} not found on {lk.relpath}")
        if n.tag == "a" and n.get("href") is not None:
            rel = (n.get("rel") or "").lower().split()
            if "nofollow" in rel:
                report.error("NOFOLLOW", p, f"rel=nofollow on {n.get('href')!r}")
            text = norm_ws(n.text())
            if text:
                lk = resolve(n.get("href"), p)
                anchors.setdefault(text, set()).add(lk.target)
                if text.lower() in GENERIC_ANCHORS:
                    report.warn("ANCHOR-GENERIC", p, f"anchor text {text!r} alone; name the target")
    for text, targets in sorted(anchors.items()):
        if len(targets) > 1:
            report.error("ANCHOR-DUP", p, f"anchor text {text!r} points to {len(targets)} URLs: {', '.join(sorted(targets))}")
    if not file_mode:
        for m in page.metas:
            if "nosourceinfo" in (m.get("content") or "").lower():
                report.error("NOSOURCEINFO", p, "meta nosourceinfo is not allowed")
            if "nofollow" in (m.get("content") or "").lower() and (m.get("name") or "").lower() in ("robots", "googlebot", "yeti"):
                report.error("NOFOLLOW", p, "meta robots nofollow is not allowed")


def check_markup(page, report, file_mode):
    p = page.relpath
    scope = page.main if file_mode else page.dom
    if scope is None: return
    for n in scope.iter():
        demo = p in ACCENT_DEMO_PAGES and page.in_main(n)  # the noindex SDS demo shows every app's accent
        if "data-app" in n.attrs and n.tag != "main" and "app-tile" not in n.classes() and not demo:
            report.error("DATA-APP", p, f"data-app on <{n.tag}>; it belongs on <main> only (menu .app-tile excepted)")
        if n.get("popovertarget") is not None and "aria-expanded" in n.attrs:
            report.error("POPOVER-EXPANDED", p, "aria-expanded on a popovertarget invoker (the browser exposes it)")
    names = []
    for n in scope.iter():
        names += re.findall(r"view-transition-name\s*:\s*([\w-]+)", n.get("style") or "")
        if n.tag == "style":
            names += re.findall(r"view-transition-name\s*:\s*([\w-]+)", "".join(c for c in n.children if isinstance(c, str)))
    names = [x for x in names if x not in ("none", "auto", "match-element")]
    for x in sorted({x for x in names if names.count(x) > 1}):
        report.error("VT-NAME-DUP", p, f"view-transition-name {x!r} used {names.count(x)} times")


def check_head(page, report, all_org_urls):
    """Build-owned <head> rules: canonical, NOINDEX, hreflang, og:locale:alternate (not in --file mode)."""
    p, site = page.relpath, page.site
    robots = (page.meta(name="robots") or "").lower()
    canon = page.link_rel("canonical")
    hl = page.hreflangs()
    og_url = page.meta(prop="og:url")
    if p in NOINDEX_PATHS:
        if "noindex" not in robots: report.error("NOINDEX-MISSING", p, "NOINDEX page without <meta name=robots content=noindex>")
        if canon: report.error("NOINDEX-CANONICAL", p, "NOINDEX page outputs canonical")
        if hl: report.error("NOINDEX-HREFLANG", p, "NOINDEX page outputs hreflang")
        if og_url: report.error("NOINDEX-OGURL", p, "NOINDEX page outputs og:url")
        return
    if "noindex" in robots:
        report.error("INDEX-NOINDEX", p, f"noindex on a page that is not in NOINDEX_PATHS {sorted(NOINDEX_PATHS)}")
    want = SITE + url_of(p)
    if len(canon) != 1 or canon[0].get("href") != want:
        report.error("CANONICAL", p, f"want exactly one canonical {want}, got {[c.get('href') for c in canon]}")
    cp = counterpart(p)
    has_cp = cp is not None and site.exists(cp)
    for lang, href in hl.items():
        lk = resolve(href, p)
        if not lk.internal or not site.exists(lk.relpath):
            report.error("HREFLANG-TARGET", p, f"hreflang={lang} {href} does not resolve to a page")
    if has_cp:
        ko_rel, en_rel = (p, cp) if page.lang == "ko" else (cp, p)
        expect = {"ko": SITE + url_of(ko_rel), "en": SITE + url_of(en_rel), "x-default": SITE + url_of(ko_rel)}
        if hl != expect:
            report.error("HREFLANG-MISSING", p, f"hreflang set {hl} != {expect}")
    else:
        if hl: report.error("HREFLANG-NO-COUNTERPART", p, f"hreflang output but {cp} does not exist")
        if page.metas_prop("og:locale:alternate"):
            report.error("OGLOCALE-ALT", p, f"og:locale:alternate output but {cp} does not exist")


def check_jsonld(page, report, org_urls, dates_entries):
    p, site = page.relpath, page.site
    entry = (dates_entries or {}).get(p)
    blocks = page.jsonld()
    app_primary = []
    for raw, data, err in blocks:
        if err:
            report.error("SD-JSON", p, f"JSON-LD does not parse: {err}"); continue
        if has_key_anywhere(data, {"aggregateRating", "review", "reviews"}):
            report.error("SD-FORBIDDEN", p, "aggregateRating/review in JSON-LD")
        for node in jsonld_nodes(data):
            ts = types_of(node)
            if ts & {"HowTo", "AggregateRating", "Review", "SearchAction", "SpeakableSpecification"}:
                report.error("SD-FORBIDDEN", p, f"@type {sorted(ts)} is not used on this site")
            if "Person" in ts:
                report.error("SD-FORBIDDEN", p, "Person node (no real-name Person markup)")
            if "BreadcrumbList" in ts:
                items = node.get("itemListElement") or []
                if len(items) < 2:
                    report.error("SD-CRUMB-SHORT", p, f"BreadcrumbList has {len(items)} items, want >= 2")
                if items and isinstance(items[0], dict) and str(items[0].get("name", "")).strip() in ("홈", "Home", "home"):
                    report.error("SD-CRUMB-HOME", p, "first breadcrumb is named 홈/Home; use SugarMount")
            if "Article" in ts:
                dm = node.get("dateModified")
                if not (isinstance(dm, str) and TZ_RE.search(dm)):
                    report.error("SD-ARTICLE-DATE", p, f"Article dateModified missing or without time zone: {dm!r}")
                dp = node.get("datePublished")
                if dp is not None and not (isinstance(dp, str) and TZ_RE.search(dp)):
                    report.error("SD-ARTICLE-DATE", p, f"Article datePublished without time zone: {dp!r}")
            for key, idx in (("dateModified", 1), ("datePublished", 0)):
                v = node.get(key)
                if isinstance(v, str) and node.get("@id", "").split("#")[0] in ("", SITE + url_of(p)):
                    day = v[:10]
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", day) and v != dates.iso_datetime(day):
                        report.error("SD-DATE-FORMAT", p, f"{key} {v!r}: use {dates.iso_datetime(day)!r} (dates.iso_datetime)")
                    if entry and day != (entry["published"], entry["modified"])[idx]:
                        report.error("SD-DATE-MISMATCH", p, f"{key} {day} != content-dates {('published', 'modified')[idx]} "
                                                            f"{(entry['published'], entry['modified'])[idx]}")
            if ts & {"MobileApplication", "SoftwareApplication", "VideoGame"}:
                if "downloadUrl" in node:
                    report.error("SD-APP-DOWNLOADURL", p, "MobileApplication.downloadUrl (schema.org: binary link) must go")
                missing = [k for k in ("name", "applicationCategory", "operatingSystem") if not node.get(k)]
                if missing:
                    report.error("SD-APP-REQUIRED", p, f"MobileApplication missing {', '.join(missing)}")
                if not is_abs(node.get("url")):
                    report.error("SD-APP-URL", p, f"MobileApplication url {node.get('url')!r} is not absolute")
                for s in node.get("screenshot") or []:
                    if not (isinstance(s, dict) and is_abs(s.get("url")) and s.get("width") and s.get("height")):
                        report.error("SD-APP-SHOT", p, f"screenshot needs an ImageObject with absolute url, width, height: {s!r}"[:200])
                desc = node.get("description")
                if isinstance(desc, str) and len(desc) > 160:
                    report.error("SD-APP-DESC", p, f"MobileApplication description {len(desc)} chars > 160")
            for key in ("screenshot", "image", "primaryImageOfPage", "logo"):
                for u in image_urls(node.get(key)):
                    lk = resolve(u, p)
                    if lk.internal and not site.exists(lk.relpath):
                        report.error("SD-IMAGE-MISSING", p, f"{key} {u} does not resolve to a file")
            if "primaryImageOfPage" in node:
                app_primary += image_urls(node["primaryImageOfPage"])
            is_org = "Organization" in ts or node.get("@id") == ORG_ID
            if is_org:
                if set(node) - {"@type", "@id", "name", "url", "@context"} and p not in ORG_FULL_PAGES:
                    report.error("SD-ORG-FULL", p, "full Organization node outside / and /about/ (reference {\"@id\": \"…/#org\"})")
                alt = node.get("alternateName") or []
                alt = [alt] if isinstance(alt, str) else alt
                if any("simpest" in str(a).lower() for a in alt):
                    report.error("SD-ORG-ALTNAME", p, "Organization alternateName must not carry the personal handle")
                if node.get("@id") == ORG_ID and "url" in node:
                    org_urls.setdefault(node["url"], set()).add(p)
            if "WebSite" in ts and set(node) - {"@type", "@id", "@context"} and p != "index.html":
                report.error("SD-WEBSITE-FULL", p, "full WebSite node outside the ko home /")
    if page.kind == "app":
        og = page.meta(prop="og:image")
        if not app_primary:
            report.error("SD-PRIMARY-IMAGE", p, "app page has no WebPage.primaryImageOfPage")
        elif og not in app_primary:
            report.error("SD-PRIMARY-IMAGE", p, f"og:image {og} != primaryImageOfPage {app_primary[0]}")


def check_page_budget(page, report, file_mode):
    p, site = page.relpath, page.site
    size = len(page.text.encode("utf-8"))
    limit = BUDGET["html_privacy"] if page.kind in ("policy", "privacy-list") else BUDGET["html"]
    if size > limit:
        (report.warn if file_mode else report.error)("BUDGET-HTML", p, f"{size} B > {limit} B")
    scope = page.main if file_mode else page.dom
    if scope is None: return
    js = 0
    for s in scope.find_all("script"):
        typ = (s.get("type") or "").lower()
        if typ == "application/ld+json": continue
        src = s.get("src")
        if src:
            lk = resolve(src, p)
            if not lk.internal:
                # the one approved exception: AdSense on AX notes (data/ads.json, owner decision 2026-10-22)
                if not (lk.host == ADS_ORIGIN and re.match(r"(en/)?ax/[^/]+/index\.html$", p) and "async" in s.attrs):
                    report.error("ORIGIN", p, f"external script {src}")
                continue
            js += site.size(lk.relpath) or 0
            if "defer" not in s.attrs and "async" not in s.attrs and (s.get("type") or "") != "module":
                report.warn("JS-DEFER", p, f"script {src} without defer")
        else:
            js += len("".join(c for c in s.children if isinstance(c, str)).encode("utf-8"))
    if js > BUDGET["js"]:
        report.error("BUDGET-JS", p, f"{js} B of JavaScript > {BUDGET['js']} B")
    for l in scope.find_all("link"):
        rels = set((l.get("rel") or "").lower().split())
        if "preload" in rels and (l.get("as") or "").lower() == "font":
            report.error("FONT-PRELOAD", p, f"font preload {l.get('href')} (preload ignores unicode-range)")
        if rels & {"stylesheet", "preload", "preconnect", "dns-prefetch", "icon", "apple-touch-icon", "modulepreload",
                   "prefetch", "manifest"}:
            lk = resolve(l.get("href"), p)
            if not lk.internal and lk.host and lk.host not in ALLOWED_ORIGINS:
                report.error("ORIGIN", p, f"<link rel={' '.join(sorted(rels))}> to {lk.host}")
    icon_bytes = {}
    for n in scope.find_all("img", "source", "video", "audio", "iframe"):
        for v in [n.get("src")] + srcset_urls(n.get("srcset")):
            if not v: continue
            lk = resolve(v, p)
            if not lk.internal and lk.host and lk.host not in ALLOWED_ORIGINS:
                report.error("ORIGIN", p, f"<{n.tag}> from {lk.host}")
            elif lk.internal and re.search(r"/icon\.(webp|png|jpg|svg)$", lk.relpath):
                icon_bytes[lk.relpath] = site.size(lk.relpath) or 0
        if n.tag == "img":
            if not (n.get("width") and n.get("height")):
                report.error("IMG-SIZE", p, f"<img src={n.get('src')!r}> without width and height")
            src = n.get("src") or ""
            if page.kind == "app" and "/assets/apps/" in src and not re.search(r"/icon\.\w+$", src):
                if (n.get("loading") or "").lower() != "lazy":
                    report.error("IMG-LAZY", p, f"screenshot {src} without loading=lazy")
    if sum(icon_bytes.values()) > BUDGET["icons_per_page"]:
        report.error("BUDGET-ICONS", p, f"icons on this page {sum(icon_bytes.values())} B > {BUDGET['icons_per_page']} B")
    if file_mode: return
    css = []
    for l in page.link_rel("stylesheet"):
        lk = resolve(l.get("href"), p)
        if lk.internal and site.exists(lk.relpath):
            css.append((lk.relpath, site.read(lk.relpath)))
    for s in page.dom.find_all("style"):
        css.append((p, "".join(c for c in s.children if isinstance(c, str))))
    faces = []
    seen_css = set()
    while css:
        rp, text = css.pop()
        if (rp, len(text)) in seen_css: continue
        seen_css.add((rp, len(text)))
        for u in css_urls(text):
            lk = resolve(u, rp)
            if not lk.internal and lk.host and lk.host not in ALLOWED_ORIGINS:
                report.error("ORIGIN", p, f"CSS {rp} loads {lk.host}")
            elif lk.internal and lk.relpath.endswith(".css") and site.exists(lk.relpath):
                css.append((lk.relpath, site.read(lk.relpath)))
        faces += font_faces(text, rp)
    if faces:
        chars = {ord(c) for c in page_chars(page)}
        if any(f[0] == EN_FONT_FAMILY for f in faces):  # site.css :lang(en) draws English pages in EN_FONT_FAMILY only
            faces = [f for f in faces if (f[0] == EN_FONT_FAMILY) == (page.lang == "en")]
        total, tiny, counted = 0, 0, set()
        for fam, wt, st, src, ranges in faces:
            if ranges is None:
                hit = len(chars)
            else:
                hit = sum(1 for c in chars if any(lo <= c <= hi for lo, hi in ranges))
            if not hit: continue
            if not is_abs(src) and src not in counted:
                counted.add(src); total += site.size(src) or 0
            if hit <= 2: tiny += 1
        limit = (BUDGET["font_en"] if page.lang == "en" else
                 BUDGET["font_home"] if page.kind in ("home", "hub", "privacy-list") else BUDGET["font_page"])
        if total > limit:
            # IA 9.1 / SDS 5.2-6 set limits for home/hub/policy list, app/article/AX and every /en/ page. A ko policy
            # document or the noindex /design/ demo has no limit of its own: legal text is not reworded to save a
            # subset, so those report against the page limit as a warning.
            (report.warn if page.kind in FONT_BUDGET_WARN_KINDS else report.error)(
                "BUDGET-FONT", p, f"font files this page needs {total // KB} KB > {limit // KB} KB")
        if tiny:
            report.warn("FONT-TINY", p, f"{tiny} font subset(s) downloaded for only 1-2 characters")


def check_page(site, relpath, report, *, file_mode=False, org_urls=None, dates_entries=None):
    page = site.page(relpath)
    if page is None:
        report.error("FILE-MISSING", relpath, "file not found"); return None
    if relpath not in NOINDEX_PATHS: check_lengths(page, report)
    check_headings(page, report, file_mode)
    check_links(page, report, file_mode)
    check_markup(page, report, file_mode)
    check_page_budget(page, report, file_mode)
    if not file_mode:
        check_head(page, report, org_urls)
        check_jsonld(page, report, org_urls if org_urls is not None else {}, dates_entries)
    return page


# ------------------------------------------------------------------ site gates
SM_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9", "xhtml": "http://www.w3.org/1999/xhtml"}


def sitemap_urls(site, report):
    """<url> elements of sitemap.xml: a <urlset> itself, or every child <urlset> its <sitemapindex> lists (same site)."""
    def parse(name):
        text = site.read(name)
        if text is None:
            report.error("SITEMAP-MISSING", name, f"no {name}"); return None
        try:
            return ET.fromstring(text.encode("utf-8"))
        except ET.ParseError as e:
            report.error("SITEMAP-XML", name, str(e)); return None
    root = parse("sitemap.xml")
    if root is None: return None
    if root.tag != "{%s}sitemapindex" % SM_NS["sm"]:
        return root.findall("sm:url", SM_NS)
    urls = []
    for s in root.findall("sm:sitemap", SM_NS):
        loc = (s.findtext("sm:loc", "", SM_NS) or "").strip()
        if not re.fullmatch(re.escape(SITE) + r"/sitemap-[\w-]+\.xml", loc):
            report.error("SITEMAP-INDEX", "sitemap.xml", f"{loc} is not a sitemap-*.xml file on this site"); continue
        child = parse(loc[len(SITE) + 1:])
        if child is not None: urls += child.findall("sm:url", SM_NS)
    return urls


def check_sitemap(site, report, pages, dates_entries):
    urls = sitemap_urls(site, report)
    if urls is None: return set()
    listed = set()
    for u in urls:
        loc = (u.findtext("sm:loc", "", SM_NS) or "").strip()
        lm = (u.findtext("sm:lastmod", "", SM_NS) or "").strip()
        lk = resolve(loc, "")
        if not loc.startswith(SITE + "/") or not lk.internal or not site.exists(lk.relpath):
            report.error("SITEMAP-LOC", "sitemap.xml", f"{loc} does not resolve to a page"); continue
        rp = lk.relpath
        listed.add(rp)
        if rp in NOINDEX_PATHS: report.error("SITEMAP-NOINDEX", "sitemap.xml", f"{loc} is a NOINDEX page")
        if rp in OWNERSHIP_FILES: report.error("SITEMAP-OWNERSHIP", "sitemap.xml", f"{loc} is an ownership file")
        if dates_entries is not None:
            e = dates_entries.get(rp)
            if e is None:
                report.error("DATES-MISSING", rp, "page has no data/content-dates.json entry")
            elif lm != e["modified"]:
                report.error("SITEMAP-LASTMOD", "sitemap.xml", f"{loc} lastmod {lm!r} != content-dates modified {e['modified']}")
        alts = {l.get("hreflang"): l.get("href") for l in u.findall("xhtml:link", SM_NS)}
        pg = site.page(rp)
        if alts and pg is not None and rp not in NOINDEX_PATHS and alts != pg.hreflangs():  # optional; pages carry hreflang
            report.error("SITEMAP-HREFLANG", "sitemap.xml", f"{loc}: sitemap alternates {alts} != page hreflang {pg.hreflangs()}")
    for rp in pages:
        if rp not in NOINDEX_PATHS and rp not in listed:
            report.error("SITEMAP-MISSING-PAGE", "sitemap.xml", f"{url_of(rp)} is indexable but not in the sitemap")
    return listed


def check_feeds(site, report, dates_entries):
    for feed in FEEDS:
        text = site.read(feed)
        if text is None:
            report.error("RSS-MISSING", feed, "feed does not exist"); continue
        size = site.size(feed)
        if size >= BUDGET["rss"]:
            report.error("RSS-SIZE", feed, f"{size} B >= 10 MB")
        try:
            root = ET.fromstring(text.encode("utf-8"))
        except ET.ParseError as e:
            report.error("RSS-XML", feed, str(e)); continue
        items = root.findall("./channel/item")
        if not items:
            report.error("RSS-EMPTY", feed, "no <item>")
        lang = "en" if feed.startswith("en/") else "ko"
        pubs = []
        for it in items:
            link = (it.findtext("link") or "").strip()
            lk = resolve(link, "")
            if not lk.internal or not site.exists(lk.relpath):
                report.error("RSS-LINK", feed, f"item link {link} does not resolve"); continue
            rp = lk.relpath
            if rp in NOINDEX_PATHS: report.error("RSS-NOINDEX", feed, f"{link} is a NOINDEX page")
            if page_kind(rp) in ("policy", "privacy-list"): report.error("RSS-PRIVACY", feed, f"{link}: policies stay out of RSS")
            if page_lang_of(rp) != lang: report.error("RSS-LANG", feed, f"{link} is not a {lang} page")
            bodies = [it.findtext("description") or ""]
            enc = it.find("{http://purl.org/rss/1.0/modules/content/}encoded")
            if enc is not None: bodies.append(enc.text or "")
            for body in bodies:
                for attr, v in re.findall(r'\b(href|src|srcset)\s*=\s*"([^"]*)"', body):
                    for u in (srcset_urls(v) if attr == "srcset" else [v]):
                        if not re.match(r"^(https?:)?//|^(mailto|tel):", u):
                            report.error("RSS-RELATIVE", feed, f"{link}: {attr}={u!r} must be absolute")
            for body in bodies:
                if re.search(r"<!--\s*build:(meta|toc)\b|<script\b|class=\"crumbs\"", body):
                    report.error("RSS-STRIP", feed, f"{link}: feed body keeps crumbs, build:meta/build:toc or <script>")
                    break
            pg = site.page(rp)
            meta = (pg.desc or "") if pg else ""
            body = bodies[0]
            if not (len(body) > 3 * len(meta) and "<p" in body):
                report.error("RSS-BODY", feed, f"{link}: <description> must carry the full <main> HTML "
                                               f"({len(body)} chars, meta description {len(meta)})")
            pd = (it.findtext("pubDate") or "").strip()
            try:
                from email.utils import parsedate_to_datetime
                day = parsedate_to_datetime(pd).astimezone(dates.KST).date().isoformat()
            except (TypeError, ValueError):
                report.error("RSS-PUBDATE", feed, f"{link}: bad pubDate {pd!r}"); continue
            pubs.append(day)
            e = (dates_entries or {}).get(rp)
            if e and day != e["published"]:
                report.error("RSS-PUBDATE", feed, f"{link}: pubDate {day} != content-dates published {e['published']}")
        if pubs != sorted(pubs, reverse=True):
            report.error("RSS-ORDER", feed, "items are not sorted by published date, newest first")


def check_robots(site, report):
    text = site.read("robots.txt")
    if text is None:
        report.error("ROBOTS-MISSING", "robots.txt", "no robots.txt"); return
    lines = [l.split("#", 1)[0].strip() for l in text.splitlines()]
    kv = [(l.split(":", 1)[0].strip().lower(), l.split(":", 1)[1].strip()) for l in lines if ":" in l]
    agents = [v for k, v in kv if k == "user-agent"]
    if agents != ["*"]:
        report.error("ROBOTS-AGENTS", "robots.txt", f"want exactly one 'User-agent: *' group, got {agents}")
    dis = {v for k, v in kv if k == "disallow"}
    for d in ROBOTS_DISALLOW:
        if d not in dis: report.error("ROBOTS-DISALLOW", "robots.txt", f"missing 'Disallow: {d}'")
    sm = [v for k, v in kv if k == "sitemap"]
    if sm != [SITE + "/sitemap.xml"]:
        report.error("ROBOTS-SITEMAP", "robots.txt", f"want exactly 'Sitemap: {SITE}/sitemap.xml', got {sm}")


def check_llms(site, report):
    text = site.read("llms.txt")
    if text is None: return
    for rp in NOINDEX_PATHS:
        u = SITE + url_of(rp)
        if re.search(re.escape(u) + r"(?![\w/-])", text):
            report.error("LLMS-NOINDEX", "llms.txt", f"{u} is a NOINDEX page")


def check_orphans(site, report, pages, listed):
    inbound = {}
    for rp in pages:
        if rp in NOINDEX_PATHS: continue
        pg = site.page(rp)
        if pg is None: continue
        for a in pg.dom.find_all("a"):
            lk = resolve(a.get("href"), rp)
            if lk.internal and lk.relpath != rp:
                inbound.setdefault(lk.relpath, set()).add(rp)
    for rp in sorted(listed):
        n = len(inbound.get(rp, set()) - {counterpart(rp)})  # the language switch on the twin page does not count
        need = 2 if page_kind(rp) == "article" else 1
        if n < need:
            report.error("ORPHAN", rp, f"linked from {n} other page(s), want >= {need}")


def check_assets(site, report):
    for rp, key in (("assets/site.css", "site_css"), ("assets/sds-apps.css", "sds_apps_css"),
                    ("assets/fonts/pretendard.css", "font_css")):
        s = site.size(rp)
        if s is not None and s > BUDGET[key]:
            report.error("BUDGET-CSS", rp, f"{s} B > {BUDGET[key]} B")
    for rp in site.files_under("assets/apps"):
        if not rp.endswith(".webp") or rp.endswith("/icon.webp"): continue
        s = site.size(rp)
        if s > BUDGET["shot"]:
            report.error("BUDGET-SHOT", rp, f"screenshot {s} B > {BUDGET['shot']} B")
        if webp_lossless(site.read_bytes(rp, 4096)):
            report.error("BUDGET-SHOT-LOSSLESS", rp, "lossless (VP8L) WebP; re-encode lossy q≈80")
    for rp in site.files_under("assets/og") + (["assets/og.png"] if site.exists("assets/og.png") else []):
        if not rp.lower().endswith((".png", ".jpg", ".jpeg")): continue
        s = site.size(rp)
        if not BUDGET["og_min"] <= s <= BUDGET["og_max"]:
            report.error("BUDGET-OG", rp, f"share image {s} B, want {BUDGET['og_min']}-{BUDGET['og_max']} B")


def run(root=ROOT, outputs=None):
    """Every gate over the whole site. outputs = {relpath: text} from an in-memory build override files on disk."""
    site = Site(root, outputs)
    report = Report()
    pages = site.html_pages()
    dates_entries = site.dates
    if dates_entries is None:
        report.warn("DATES-FILE", dates.DATES_FILE, "missing; date gates skipped")
    org_urls = {}
    titles, descs = {}, {}
    for rp in pages:
        pg = check_page(site, rp, report, org_urls=org_urls, dates_entries=dates_entries)
        if pg is None or rp in NOINDEX_PATHS: continue
        if pg.title: titles.setdefault(pg.title, []).append(rp)
        if pg.desc: descs.setdefault(pg.desc, []).append(rp)
    for text, rps in sorted(titles.items()):
        if len(rps) > 1: report.warn("TITLE-DUP", rps[0], f"same title on {', '.join(rps)}")
    for text, rps in sorted(descs.items()):
        if len(rps) > 1: report.warn("DESC-DUP", rps[0], f"same description on {', '.join(rps)}")
    if set(org_urls) - {SITE + "/"}:
        report.error("SD-ORG-URL", "#org", "#org url must be only https://sugarmount21.com/, found "
                     + "; ".join(f"{u} on {', '.join(sorted(ps)[:3])}" for u, ps in sorted(org_urls.items())))
    listed = check_sitemap(site, report, pages, dates_entries)
    check_feeds(site, report, dates_entries)
    check_robots(site, report)
    check_llms(site, report)
    check_orphans(site, report, pages, listed)
    check_assets(site, report)
    return report


def check_files(paths, root=ROOT):
    """Read-only gates for content authors: author-owned parts of hand-written files (title, description, <main>)."""
    site = Site(root)
    report = Report()
    for path in paths:
        full = os.path.abspath(path if os.path.isabs(path) or os.path.exists(path) else os.path.join(root, path))
        rp = os.path.relpath(full, os.path.abspath(root)).replace(os.sep, "/")
        if rp.startswith(".."):
            report.error("FILE-OUTSIDE", path, f"not under {root}"); continue
        check_page(site, rp, report, file_mode=True)
    return report


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = ROOT
    if "--root" in argv:
        i = argv.index("--root"); root = os.path.abspath(argv[i + 1]); del argv[i:i + 2]
    warnings = "--no-warnings" not in argv
    files = [argv[i + 1] for i, a in enumerate(argv) if a == "--file" and i + 1 < len(argv)]
    report = check_files(files, root) if files else run(root)
    report.print(warnings=warnings)
    return 1 if report.errors else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
