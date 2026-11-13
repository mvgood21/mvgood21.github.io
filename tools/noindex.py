"""Which pages carry <meta name=robots content=noindex>: one rule for build.py, checks.py and indexnow.py.

Fixed pages (404, the /design/ demo) are always noindex. A site adds more in data/noindex.json:
  {"prefixes": ["privacy/", ...], "ax_notes": ["<slug>", ...]}   (paths without the en/ prefix; both languages match)
Owner decision 2026-11-13 (AdSense "replicated / low value content"): policies (one template per app), AX topic
and board pages (lists of notes that are indexed themselves) and AX notes folded into a sibling are noindex.
They stay reachable and linked. Noindex pages get no canonical, og:url, hreflang, breadcrumbs or JSON-LD, and stay
out of the sitemap, RSS, llms.txt and IndexNow (IA spec 2)."""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = frozenset({"404.html", "design/index.html"})
FILE = "data/noindex.json"


class NoIndex:
    """Set-like: `relpath in NOINDEX_PATHS`. Iterating yields the fixed pages and the listed notes (ko and en);
    prefix rules have no fixed members, so a caller that must cover every page tests each page for membership."""

    def __init__(self, root=ROOT, prefixes=None, ax_notes=None):
        cfg = {}
        if prefixes is None or ax_notes is None:
            try:
                cfg = json.load(open(os.path.join(root, FILE), encoding="utf-8"))
            except (OSError, ValueError):
                cfg = {}
        self.prefixes = tuple(cfg.get("prefixes", ()) if prefixes is None else prefixes)
        self.ax_notes = frozenset(cfg.get("ax_notes", ()) if ax_notes is None else ax_notes)

    def __contains__(self, relpath):
        if relpath in BASE: return True
        bare = relpath[3:] if relpath.startswith("en/") else relpath
        if self.prefixes and bare.startswith(self.prefixes): return True
        parts = bare.split("/")
        return len(parts) == 3 and parts[0] == "ax" and parts[2] == "index.html" and parts[1] in self.ax_notes

    def __iter__(self):
        yield from sorted(BASE)
        for s in sorted(self.ax_notes):
            yield f"ax/{s}/index.html"; yield f"en/ax/{s}/index.html"

    def __repr__(self): return f"NoIndex(base={sorted(BASE)}, prefixes={list(self.prefixes)}, ax_notes={sorted(self.ax_notes)})"
