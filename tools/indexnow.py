#!/usr/bin/env python3
"""IndexNow ping for mvgood21.github.io (manual, run after a deploy is live).

Targets: pages whose `modified` date in data/content-dates.json equals the deploy date
(default: today in Asia/Seoul, or $SOURCE_DATE, or --date). Pages where only the header or
footer changed keep the same <main> hash, so their `modified` does not move and they are
skipped. `--all` sends every indexable page once (use it once, right after the site is
registered in Naver Search Advisor). NOINDEX_PATHS and ownership files are always left out.

Dry run is the default: it prints the request bodies and sends nothing. Add --send to post.

    python tools/indexnow.py                 # dry run, pages modified today
    python tools/indexnow.py --date 2026-10-18
    python tools/indexnow.py --all           # dry run, every page
    python tools/indexnow.py --all --send    # post (needs the key file live on the site)

Endpoints (JSON POST {host, key, keyLocation, urlList}, at most 10,000 URLs per request):
  - https://api.indexnow.org/indexnow          shared with every IndexNow engine (Bing, Naver, ...)
    https://www.indexnow.org/searchengines.json
  - https://searchadvisor.naver.com/indexnow   Naver direct (--engine naver; not needed by default)
    https://searchadvisor.naver.com/guide/indexnow-request
Responses: 200 success, 202 received (key still being checked); 400 bad request,
403 key invalid, 422 URL does not match the key, 429 too many requests.

The key (data/indexnow-key.txt) is public by design; the build writes it to /<key>.txt.
Standard library only.
"""
import argparse, ast, datetime, json, os, re, sys, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, "tools")
SITE = "https://mvgood21.github.io"
HOST = "mvgood21.github.io"
KEY_FILE = os.path.join(ROOT, "data", "indexnow-key.txt")
DATES_FILE = os.path.join(ROOT, "data", "content-dates.json")
ENDPOINTS = {
    "indexnow": "https://api.indexnow.org/indexnow",
    "naver": "https://searchadvisor.naver.com/indexnow",
}
MAX_URLS = 10000
# Spec value (IA §2); the build's own constant wins when it can be read from tools/build.py.
NOINDEX_FALLBACK = {"404.html", "design/index.html"}
# Search Console / Search Advisor ownership files: never notify.
OWNERSHIP_RE = re.compile(r"^(google[0-9a-f]+|naver[0-9a-f]+)\.html$")
KST = datetime.timezone(datetime.timedelta(hours=9))  # Korea has no DST; avoids needing tzdata


def today():
    """Same rule as tools/dates.py (IA §4.1): $SOURCE_DATE, else today in Asia/Seoul."""
    sys.path.insert(0, TOOLS)
    try:
        import dates  # WP-F module; use its today() when it exposes one
        if callable(getattr(dates, "today", None)):
            return str(dates.today())
    except Exception:
        pass
    finally:
        sys.path.remove(TOOLS)
    env = os.environ.get("SOURCE_DATE")
    if env:
        return check_date(env)
    return datetime.datetime.now(KST).date().isoformat()


def check_date(s):
    try:
        return datetime.date.fromisoformat(s).isoformat()
    except ValueError:
        raise SystemExit(f"bad date {s!r}: use YYYY-MM-DD")


def read_key():
    try:
        key = open(KEY_FILE, encoding="utf-8").read().strip()
    except FileNotFoundError:
        raise SystemExit(f"missing {os.path.relpath(KEY_FILE, ROOT)}")
    if not re.fullmatch(r"[0-9a-fA-F-]{8,128}", key):
        raise SystemExit("data/indexnow-key.txt must hold 8-128 hex characters or '-'")
    return key


def noindex_paths():
    """NOINDEX_PATHS from tools/build.py without importing it (no build side effects)."""
    try:
        src = open(os.path.join(TOOLS, "build.py"), encoding="utf-8").read()
        m = re.search(r"^NOINDEX_PATHS\s*=\s*(\{[^}]*\}|\[[^\]]*\]|\([^)]*\))", src, re.M)
        if m:
            return set(ast.literal_eval(m.group(1)))
    except (OSError, ValueError, SyntaxError):
        pass
    return set(NOINDEX_FALLBACK)


def load_dates():
    try:
        with open(DATES_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit("missing data/content-dates.json (written by tools/build.py via tools/dates.py)")
    if not isinstance(data, dict):
        raise SystemExit("data/content-dates.json: expected an object keyed by page path")
    return data


def page_url(relpath):
    """'index.html' -> SITE/, 'apps/x/index.html' -> SITE/apps/x/, 'foo.html' -> SITE/foo.html"""
    p = relpath.replace("\\", "/").lstrip("/")
    if p == "index.html":
        return SITE + "/"
    if p.endswith("/index.html"):
        return f"{SITE}/{p[:-len('index.html')]}"
    return f"{SITE}/{p}"


def targets(data, day, send_all, noindex):
    urls, skipped = [], []
    for rel in sorted(data):
        rec = data[rel] if isinstance(data[rel], dict) else {}
        p = rel.replace("\\", "/").lstrip("/")
        if not p.endswith(".html"):
            continue
        if p in noindex or OWNERSHIP_RE.match(p):
            skipped.append((p, "noindex/ownership"))
            continue
        if not os.path.isfile(os.path.join(ROOT, p)):
            skipped.append((p, "file not in tree"))
            continue
        if send_all or rec.get("modified") == day:
            urls.append(page_url(p))
    return urls, skipped


def key_live(key, key_location):
    req = urllib.request.Request(key_location, headers={"User-Agent": "sugarmount-indexnow/1"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200 and r.read().decode("utf-8", "replace").strip() == key
    except (urllib.error.URLError, OSError):
        return False


def post(endpoint, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "sugarmount-indexnow/1",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read(500).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(500).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        return None, str(e)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Notify IndexNow engines about changed pages.")
    ap.add_argument("--date", help="deploy date YYYY-MM-DD (default: $SOURCE_DATE or today, Asia/Seoul)")
    ap.add_argument("--all", action="store_true", help="send every indexable page (one-off, after Search Advisor registration)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True, help="print only (default)")
    mode.add_argument("--send", action="store_true", help="actually POST")
    # default: the shared endpoint only. It already forwards to every participating engine, Naver included, so
    # "both" would notify Naver twice (429 risk, no gain); keep naver/both for Naver-only troubleshooting.
    ap.add_argument("--engine", choices=["both", *ENDPOINTS], default="indexnow",
                    help="indexnow (default; shared: Bing, Naver, ...), naver (direct, troubleshooting) or both")
    ap.add_argument("--skip-key-check", action="store_true", help="do not GET /<key>.txt before sending")
    args = ap.parse_args(argv)

    key = read_key()
    key_location = f"{SITE}/{key}.txt"
    day = check_date(args.date) if args.date else today()
    urls, skipped = targets(load_dates(), day, args.all, noindex_paths())

    print(f"mode: {'SEND' if args.send else 'dry run'}; target: {'all pages' if args.all else 'modified == ' + day}")
    for p, why in skipped:
        print(f"  skip {p} ({why})")
    if not urls:
        print("nothing to send")
        return 0
    print(f"{len(urls)} URL(s):")
    for u in urls:
        print("  " + u)

    engines = list(ENDPOINTS) if args.engine == "both" else [args.engine]
    batches = [urls[i:i + MAX_URLS] for i in range(0, len(urls), MAX_URLS)]
    if not args.send:
        sample = {"host": HOST, "key": key, "keyLocation": key_location, "urlList": batches[0][:3] + (["..."] if len(batches[0]) > 3 else [])}
        for name in engines:
            print(f"would POST {len(urls)} URL(s) in {len(batches)} request(s) to {ENDPOINTS[name]}")
        print("body: " + json.dumps(sample, ensure_ascii=False))
        print("dry run: nothing sent (add --send)")
        return 0

    if not args.skip_key_check and not key_live(key, key_location):
        print(f"key file not live at {key_location}; deploy it first (or --skip-key-check)", file=sys.stderr)
        return 2
    failed = False
    for name in engines:
        for batch in batches:
            status, text = post(ENDPOINTS[name], {"host": HOST, "key": key, "keyLocation": key_location, "urlList": batch})
            ok = status in (200, 202)
            failed |= not ok
            note = {200: "success", 202: "accepted, key being checked"}.get(status, text.strip()[:200])
            print(f"{name}: HTTP {status} ({len(batch)} URL(s)) {note}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
