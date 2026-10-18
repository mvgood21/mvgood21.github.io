#!/usr/bin/env python3
"""content-dates: the single source of page dates (IA spec 4.1). Standard library only.

Every page gets {"hash", "published", "modified"} in data/content-dates.json.

  hash input, hand-written page:  <main>…</main> without <nav class="crumbs"> and without every
                                  <!-- build:NAME -->…<!-- /build:NAME --> block, whitespace runs -> one space, trimmed
                                  (tags are kept).                      -> hand_input(page_html)
  hash input, generated page:     the input data the page is rendered from (apps.json entry, T strings),
                                  never the rendered HTML and never dates or automatic lists.
                                                                        -> data_input(*parts)
  rules:  same hash -> keep both dates
          other hash -> modified = today, hash updated (published kept)
          new page   -> published = modified = today
          stored hash null (backfill could not know the generated-page input) -> adopt the hash, keep the dates
  today:  $SOURCE_DATE (YYYY-MM-DD) if set, else today in Asia/Seoul.

Use from tools/build.py (WP-A wires it):

    import dates
    store = dates.ContentDates(check=CHECK)          # loads data/content-dates.json
    pub, mod = store.get("apps/doc-viewer/index.html", dates.hand_input(html_text))
    pub, mod = store.get("index.html", dates.data_input(home_fields, T["ko"]))
    dates.iso_datetime(mod)                          # "2026-10-17T09:00:00+09:00" for JSON-LD
    outputs["data/content-dates.json"] = store.dumps()   # compare/write like any other output
    store.stale                                      # [(relpath, reason)] that changed in this run

The module never writes by itself in check mode; store.save() is a no-op when check=True.
"""
import datetime, hashlib, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATES_FILE = "data/content-dates.json"
KST = datetime.timezone(datetime.timedelta(hours=9), "KST")  # Korea has no DST; avoids needing tzdata on Windows
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_MAIN_RE = re.compile(r"<main\b[^>]*>(.*)</main>", re.S)  # greedy: the last </main> closes it
_CRUMBS_RE = re.compile(r'<nav\s+class="crumbs"[^>]*>.*?</nav>', re.S)
_BUILD_RE = re.compile(r"<!--\s*build:([\w-]+)\s*-->.*?<!--\s*/build:\1\s*-->", re.S)
_WS_RE = re.compile(r"\s+")


def today():
    """$SOURCE_DATE (YYYY-MM-DD) or today's date in Asia/Seoul, as an ISO string."""
    env = os.environ.get("SOURCE_DATE", "").strip()
    if env:
        if not DAY_RE.match(env):
            raise ValueError(f"SOURCE_DATE must be YYYY-MM-DD, got {env!r}")
        datetime.date.fromisoformat(env)  # reject 2026-13-40
        return env
    return datetime.datetime.now(KST).date().isoformat()


def iso_datetime(day):
    """JSON-LD date form used by build and backfill alike: 09:00 Korea time."""
    datetime.date.fromisoformat(day)
    return f"{day}T09:00:00+09:00"


def main_html(page_html):
    m = _MAIN_RE.search(page_html)
    return m.group(1) if m else None


def strip_build_blocks(html_text):
    """Remove every <!-- build:NAME -->…<!-- /build:NAME --> block (repeat for nested/adjacent blocks)."""
    prev = None
    while prev != html_text:
        prev, html_text = html_text, _BUILD_RE.sub("", html_text)
    return html_text


def hand_input(page_html):
    """Hash input for a hand-written page: its <main> minus crumbs and build:* blocks, whitespace-normalised.

    A page without <main> hashes its whole text so that a broken page still changes date when edited."""
    inner = main_html(page_html)
    if inner is None:
        inner = page_html
    inner = _CRUMBS_RE.sub("", inner)
    inner = strip_build_blocks(inner)
    return _WS_RE.sub(" ", inner).strip()


def data_input(*parts):
    """Hash input for a generated page: canonical JSON of the data it is rendered from."""
    return json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(hash_input):
    if not isinstance(hash_input, str):
        hash_input = data_input(hash_input)
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]


class ContentDates:
    def __init__(self, path=None, *, check=False, root=ROOT):
        self.path = path or os.path.join(root, DATES_FILE)
        self.check = check
        self.entries = {}
        self.stale = []      # (relpath, "new" | "changed" | "baseline")
        self.seen = set()
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                self._validate(k, v)
            self.entries = raw
        self._loaded = self.dumps()

    @staticmethod
    def _validate(relpath, v):
        if not isinstance(v, dict) or not {"hash", "published", "modified"} <= set(v):
            raise ValueError(f"{DATES_FILE}: {relpath} needs hash, published and modified")
        for k in ("published", "modified"):
            if not (isinstance(v[k], str) and DAY_RE.match(v[k])):
                raise ValueError(f"{DATES_FILE}: {relpath}.{k} must be YYYY-MM-DD")
        if v["modified"] < v["published"]:
            raise ValueError(f"{DATES_FILE}: {relpath} modified {v['modified']} is before published {v['published']}")

    def get(self, relpath, hash_input):
        """(published, modified) for relpath after applying the rules to this hash input."""
        relpath = relpath.replace(os.sep, "/").lstrip("/")
        h = content_hash(hash_input)
        self.seen.add(relpath)
        e = self.entries.get(relpath)
        if e is None:
            d = today()
            self.entries[relpath] = {"hash": h, "published": d, "modified": d}
            self.stale.append((relpath, "new"))
        elif e["hash"] is None:
            e["hash"] = h
            self.stale.append((relpath, "baseline"))
        elif e["hash"] != h:
            d = today()
            e["hash"] = h
            if d > e["modified"]:
                e["modified"] = d
            # a SOURCE_DATE earlier than the stored date never moves dates backwards
            self.stale.append((relpath, "changed"))
        e = self.entries[relpath]
        return e["published"], e["modified"]

    def peek(self, relpath):
        """Stored (published, modified) without hashing, or None."""
        e = self.entries.get(relpath)
        return (e["published"], e["modified"]) if e else None

    def unused(self):
        """Entries no page asked for in this run (deleted or renamed pages)."""
        return sorted(set(self.entries) - self.seen)

    def dumps(self):
        return json.dumps(self.entries, ensure_ascii=False, sort_keys=True, indent=1) + "\n"

    def changed(self):
        return self.dumps() != self._loaded

    def save(self):
        """Write the file when it changed; never in check mode. Returns True if it would change."""
        changed = self.changed()
        if changed and not self.check:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8", newline="\n") as f:
                f.write(self.dumps())
            self._loaded = self.dumps()
        return changed


_default = None


def get(relpath, hash_input):
    """Module-level shortcut over one shared store (data/content-dates.json under the repo root)."""
    global _default
    if _default is None:
        _default = ContentDates()
    return _default.get(relpath, hash_input)


def default_store():
    global _default
    if _default is None:
        _default = ContentDates()
    return _default
