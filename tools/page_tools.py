"""In-browser tools on hand-written pages (owner decision 2026-11-24): a page opts in with a marker in its own <main>,
`<section class="tool" data-tool="NAME">`; the build then links that tool's stylesheet and deferred script in <head>
(the build owns <head>). Each tool file is versioned by its own LF bytes, so two builds in a row change nothing and
pages without a tool are untouched. checks.py gives pages that load a script under assets/tools/ the BUDGET["js_tool"]
JavaScript budget instead of the general 1 KB one.

Standard library only.
"""
import hashlib, os, re

DIR = "assets/tools"
CSS = DIR + "/tools.css"  # shared by every tool
TOOLS = {  # data-tool name -> script
    "photo-size": DIR + "/photo-size.js",
    "png-to-jpg": DIR + "/png-to-jpg.js",
    "flip-photo": DIR + "/flip-photo.js",
}
MARK_RE = re.compile(r'<section\b[^>]*\bclass="tool\b[^"]*"[^>]*\bdata-tool="([a-z0-9-]+)"')


def used(main):
    """Tool names a <main> opts into, in page order, each once. Unknown names stop the build (typo guard)."""
    names = []
    for n in MARK_RE.findall(main):
        if n not in TOOLS: raise SystemExit(f'unknown in-browser tool data-tool="{n}" (tools/page_tools.py TOOLS)')
        if n not in names: names.append(n)
    return names


def _ver(root, relpaths):
    h = hashlib.sha1()
    for rp in relpaths:
        with open(os.path.join(root, rp), "rb") as f:
            h.update(f.read().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:8]


def head_tags(root, main):
    """<head> lines for the tools a <main> uses ('' when none)."""
    names = used(main)
    if not names: return ""
    lines = [f'  <link rel="stylesheet" href="/{CSS}?v={_ver(root, [CSS])}">']
    lines += [f'  <script src="/{TOOLS[n]}?v={_ver(root, [TOOLS[n]])}" defer></script>' for n in names]
    return "\n".join(lines) + "\n"


def add_head(h, root, main):
    tags = head_tags(root, main)
    return h.replace("</head>", tags + "</head>", 1) if tags else h
