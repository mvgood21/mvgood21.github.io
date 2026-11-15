"""Pillar text for AX topic and series pages (2026-11-15 SEO/GEO plan).

A topic or series page that only lists notes is noindex (data/noindex.json, AdSense "low value": pages that only list
other pages). A page with a pillar file gets a hand-written guide above its list and can be indexed: add its path to
"except" in data/noindex.json (checks.py PILLAR-MISSING fails if an indexed topic page has no pillar).

File: data/ax-pillars/<kind>-<id>.<lang>.html, kind = topic | series. Header comment lines, then body HTML:
    <!-- title: page <title> (search title) -->
    <!-- h1: page heading -->
    <!-- lead: one-sentence answer under the heading -->
    <!-- desc: meta description -->
    <section aria-labelledby="...">...</section> ...
Headers are plain text (escaped by the builder); the body is trusted hand-written HTML (h2/h3/p/ul/ol/table/a/code),
links to notes as /ax/<slug>/ (ko) or /en/ax/<slug>/ (en)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = "data/ax-pillars"
KEYS = ("title", "h1", "lead", "desc")
HEAD_RE = re.compile(r"\A\s*((?:<!--\s*\w+:.*?-->\s*)+)", re.S)


def path(kind, pid, lang, root=ROOT):
    return os.path.join(root, DIR, f"{kind}-{pid}.{lang}.html")


def load(kind, pid, lang, root=ROOT):
    """{"title", "h1", "lead", "desc", "body"} or None when the page has no pillar."""
    p = path(kind, pid, lang, root)
    if not os.path.isfile(p):
        return None
    text = open(p, encoding="utf-8").read().replace("\r\n", "\n")
    out = {k: "" for k in KEYS}
    m = HEAD_RE.match(text)
    if m:
        for k, v in re.findall(r"<!--\s*(\w+):\s*(.*?)\s*-->", m.group(1), re.S):
            if k in out: out[k] = " ".join(v.split())
        text = text[m.end():]
    missing = [k for k in KEYS if not out[k]]
    if missing:
        raise SystemExit(f"{p}: missing header(s) {', '.join(missing)}")
    out["body"] = text.strip()
    return out
