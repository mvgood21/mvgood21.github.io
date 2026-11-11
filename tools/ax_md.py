"""AX note writer format: one Markdown file per language -> ax/<slug>/index.html (or en/ax/<slug>/index.html).

Why: hand-written HTML drifted (eyebrow spellings, notice lines, series links, box styles differed note to note).
Writers now fill a fixed Markdown template; this script owns every piece of markup, so every note gets the same
structure. tools/build.py then wraps <main> as before (head, header, TOC, meta, CTA, related notes).

Usage:
  python tools/ax_md.py <note.md> [--series <series.json>] [--out <site root>] [--check]
  --check  convert in memory and report errors only (nothing is written)

Format (see the template in the private desk; this docstring is the reference):

  ---
  slug: windows-harness-first-job
  lang: ko                     # ko | en
  type: howto                  # howto | incident | measurement | retro | short | case
  title: 제목 (h1, and <title> with " – SugarMount")
  description: 검색 결과 설명
  lead: 한 문장 답
  series: windows-harness      # optional; needs --series <file>
  part: 6                      # optional; this note's place in the series
  ---

  Intro paragraphs (before the first "##") go into the hero, under the lead.

  ## Heading {#kebab-id}        -> <section aria-labelledby><h2 id>   (the id is required)
  ### Small heading             -> <h3>
  - item / 1. item              -> <ul> / <ol>  (indented lines continue the item)
  | a | b |  + |---|---|         -> table in .table-wrap (first row is the header)
  ```                           -> <pre><code> (escaped, verbatim)
  ![alt](/assets/ax/x.webp "caption")  -> <figure> with width/height read from the file
                                    (class ax-fig for generated figures <slug>-<n>-<lang>.webp)
  :::steps                      -> <ol class="steps">; each "1. " line at the left edge starts a step,
                                   following lines (paragraphs, code, images, :::-free) belong to it
  :::box Title / :::note / :::warn / :::ok / :::danger [Title]   -> boxes (.box, .note, .note--warning, ...)
  :::faq                        -> FAQ section; "### Question" then the answer
  :::sources                    -> <p class="note"> source line (put it last)
  :::                           -> closes a container
  inline: `code`  **bold**  [text](url)  [[Ctrl+V]] (key)

The notice line (STYLE §2-7) and, for series notes, the series line under the lead and the series list at the
end are added here; writers do not type them.
"""
import html, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TYPES = {
    "howto": ("방법", "How-to"),
    "incident": ("사고 기록", "Incident"),
    "measurement": ("측정", "Measurement"),
    "retro": ("회고", "Retrospective"),
    "short": ("짧은 노트", "Short note"),
    "case": ("실측 사례", "Measured case"),
}
EYEBROW = {"ko": "AX 노트 · {}", "en": "AX notes · {}"}
NOTICE = {
    "ko": '<p class="muted">이 글은 SugarMount가 직접 측정한 값으로 쓰고, 초안 작성에 AI 코딩 에이전트를 썼습니다.</p>',
    "en": '<p class="muted">This note is written from values SugarMount measured itself; an AI coding agent was used to draft it.</p>',
}
FAQ_H = {"ko": "자주 묻는 질문", "en": "FAQ"}
SERIES_TXT = {
    "ko": {"prev": "이전 편", "next": "다음 편", "list": "{name} 전체 {n}편", "line": "{name} {i}/{n}",
           "nav": "연재 목차", "last": "마지막 편입니다."},
    "en": {"prev": "Previous", "next": "Next", "list": "{name}: all {n} parts", "line": "{name}, part {i} of {n}",
           "nav": "Series contents", "last": "This is the last part."},
}
REQUIRED = ("slug", "lang", "type", "title", "description", "lead")
BOXES = {"box": "box", "note": "note", "warn": "note note--warning", "ok": "note note--positive",
         "danger": "note note--critical"}
FORBIDDEN_CHARS = {"—": "em dash (STYLE §3)"}


class MdError(Exception):
    pass


# ---------------------------------------------------------------- inline
def inline(text):
    """Escape, then apply code, keys, links, bold. Code spans are protected from the other rules."""
    out, keep = [], []

    def stash(s):
        keep.append(s)
        return f"\x00{len(keep) - 1}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1), quote=False)}</code>"), text)
    text = re.sub(r"\[\[([^\]]+)\]\]", lambda m: stash(f"<kbd>{html.escape(m.group(1), quote=False)}</kbd>"), text)

    def link(m):
        label, url = m.group(1), m.group(2).strip()
        return stash(f'<a href="{html.escape(url)}">{inline_plain(label)}</a>')

    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], text)


def inline_plain(text):
    text = html.escape(text, quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


# ---------------------------------------------------------------- front matter
def parse_front(lines):
    if not lines or lines[0].strip() != "---":
        raise MdError("line 1: the file must start with a '---' front matter block")
    meta = {}
    for i in range(1, len(lines)):
        s = lines[i].rstrip()
        if s.strip() == "---":
            for k in REQUIRED:
                if not meta.get(k):
                    raise MdError(f"front matter: '{k}' is missing")
            if meta["lang"] not in ("ko", "en"):
                raise MdError("front matter: lang must be ko or en")
            if meta["type"] not in TYPES:
                raise MdError(f"front matter: type must be one of {', '.join(TYPES)}")
            return meta, i + 1
        if not s.strip() or s.lstrip().startswith("#"):
            continue
        m = re.match(r"^([a-z_]+):\s*(.*)$", s)
        if not m:
            raise MdError(f"line {i + 1}: front matter lines are 'key: value'")
        meta[m.group(1)] = m.group(2).strip()
    raise MdError("front matter: closing '---' not found")


# ---------------------------------------------------------------- blocks
class Ctx:
    def __init__(self, meta, site, path):
        self.meta, self.site, self.path = meta, site, path
        self.ids = set()


def image_size(ctx, src, ln):
    if not src.startswith("/"):
        raise MdError(f"line {ln}: image path must start with / (site path), got {src}")
    full = os.path.join(ctx.site, src.lstrip("/").replace("/", os.sep))
    if not os.path.exists(full):
        raise MdError(f"line {ln}: image not found in the site: {src}")
    from PIL import Image
    with Image.open(full) as im:
        return im.size


def figure(ctx, m, ln):
    alt, src, cap = m.group(1), m.group(2), m.group(3) or ""
    if not alt.strip():
        raise MdError(f"line {ln}: image needs alt text (describe what is on screen)")
    w, h = image_size(ctx, src, ln)
    cls = ' class="ax-fig"' if re.search(rf"/{re.escape(ctx.meta['slug'])}-\d+-(ko|en)\.webp$", src) else ""
    capt = f"<figcaption>{inline(cap)}</figcaption>" if cap else ""
    return (f'<figure{cls}><img src="{html.escape(src)}" width="{w}" height="{h}" alt="{html.escape(alt)}" '
            f'loading="lazy">{capt}</figure>')


IMG_RE = re.compile(r'^!\[([^\]]*)\]\((\S+?)(?:\s+"(.*)")?\)\s*$')
LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def blocks(ctx, lines, start_ln, allow_containers=True):
    """Render a list of body lines (no headings handling here) to HTML lines."""
    out, i, n = [], 0, len(lines)
    while i < n:
        raw = lines[i]
        s = raw.strip()
        ln = start_ln + i
        if not s:
            i += 1
            continue
        if s.startswith("```"):
            j = i + 1
            while j < n and not lines[j].strip().startswith("```"):
                j += 1
            if j >= n:
                raise MdError(f"line {ln}: code block is not closed with ```")
            body = "\n".join(l.rstrip() for l in lines[i + 1:j])
            out.append(f"<pre><code>{html.escape(body, quote=False)}</code></pre>")
            i = j + 1
            continue
        if s.startswith(":::"):
            if not allow_containers:
                raise MdError(f"line {ln}: ':::' containers cannot be nested")
            m = re.match(r"^:::(\w+)\s*(.*)$", s)
            if not m:
                raise MdError(f"line {ln}: stray ':::' (a container closes only after it opens)")
            kind, title = m.group(1), m.group(2).strip()
            j = i + 1
            while j < n and lines[j].strip() != ":::":
                if lines[j].strip().startswith("```"):  # skip code inside the container
                    j += 1
                    while j < n and not lines[j].strip().startswith("```"):
                        j += 1
                j += 1
            if j >= n:
                raise MdError(f"line {ln}: ':::{kind}' is not closed with ':::'")
            out += container(ctx, kind, title, lines[i + 1:j], ln + 1)
            i = j + 1
            continue
        m = IMG_RE.match(s)
        if m:
            out.append(figure(ctx, m, ln))
            i += 1
            continue
        if s.startswith("|"):
            j = i
            while j < n and lines[j].strip().startswith("|"):
                j += 1
            out += table(lines[i:j], ln)
            i = j
            continue
        if s.startswith("#"):
            if s.startswith("### "):
                out.append(f"<h3>{inline(s[4:].strip())}</h3>")
                i += 1
                continue
            raise MdError(f"line {ln}: only '## ' (section) and '### ' headings are allowed here")
        if LIST_RE.match(raw) and not LIST_RE.match(raw).group(1):
            ordered = LIST_RE.match(raw).group(2)[0].isdigit()
            items, j = [], i
            while j < n:
                mm = LIST_RE.match(lines[j])
                if mm and not mm.group(1) and (mm.group(2)[0].isdigit()) == ordered:
                    items.append(mm.group(3).strip())
                    j += 1
                elif lines[j].startswith(("  ", "\t")) and lines[j].strip() and items:
                    items[-1] += " " + lines[j].strip()
                    j += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(t)}</li>" for t in items) + f"</{tag}>")
            i = j
            continue
        j = i
        para = []
        while j < n and lines[j].strip() and not starts_block(lines[j]):
            para.append(lines[j].strip())
            j += 1
        out.append(f"<p>{inline(' '.join(para))}</p>")
        i = j
    return out


def starts_block(line):
    s = line.strip()
    return (s.startswith(("```", ":::", "|", "#")) or bool(IMG_RE.match(s))
            or bool(LIST_RE.match(line) and not LIST_RE.match(line).group(1)))


def split_row(row):
    """Split a table row on '|', except inside `code` spans or when written as \\|."""
    s = row.strip()
    if s.startswith("|"): s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"): s = s[:-1]
    cells, cur, code, i = [], "", False, 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur += "|"; i += 2; continue
        if ch == "`":
            code = not code
        if ch == "|" and not code:
            cells.append(cur.strip()); cur = ""
        else:
            cur += ch
        i += 1
    cells.append(cur.strip())
    return cells


def table(rows, ln):
    cells = [split_row(r) for r in rows]
    if len(cells) < 2 or not all(re.fullmatch(r":?-{3,}:?", c) for c in cells[1]):
        raise MdError(f"line {ln}: a table needs a header row and a |---| separator row")
    head, body = cells[0], cells[2:]
    for k, r in enumerate(body):
        if len(r) != len(head):
            raise MdError(f"line {ln + 2 + k}: table row has {len(r)} cells, header has {len(head)}")
    th = "".join(f"<th>{inline(c)}</th>" for c in head)
    trs = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
    return [f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>']


def container(ctx, kind, title, lines, ln):
    lang = ctx.meta["lang"]
    if kind == "steps":
        items, cur, fence = [], None, False
        for k, l in enumerate(lines):
            if l.strip().startswith("```"):
                fence = not fence
            m = None if fence or l.strip().startswith("```") else re.match(r"^\d+\.\s+(.*)$", l)
            if m:
                cur = [ln + k, [m.group(1)]]
                items.append(cur)
            elif cur is None:
                if l.strip():
                    raise MdError(f"line {ln + k}: ':::steps' must start with a '1. ' line")
            else:
                cur[1].append(l)
        if not items:
            raise MdError(f"line {ln}: ':::steps' has no steps")
        lis = []
        for start, body in items:
            inner = blocks(ctx, body, start, allow_containers=False)
            lis.append("<li>" + "".join(inner) + "</li>")
        return ['<ol class="steps">' + "".join(lis) + "</ol>"]
    if kind in BOXES:
        head = f"<p><strong>{inline(title)}</strong></p>" if title else ""
        return [f'<div class="{BOXES[kind]}">' + head + "".join(blocks(ctx, lines, ln, False)) + "</div>"]
    if kind == "faq":
        if "faq" in ctx.ids:
            raise MdError(f"line {ln}: only one ':::faq' per note")
        ctx.ids.add("faq")
        qs, cur = [], None
        for k, l in enumerate(lines):
            if l.startswith("### "):
                cur = [l[4:].strip(), [], ln + k + 1]
                qs.append(cur)
            elif cur is None:
                if l.strip():
                    raise MdError(f"line {ln + k}: ':::faq' must start with a '### question' line")
            else:
                cur[1].append(l)
        if len(qs) < 2:
            raise MdError(f"line {ln}: FAQ needs at least 2 questions (STYLE §2-6); drop the FAQ otherwise")
        det = "".join(f"<details><summary>{inline(q)}</summary><div>{''.join(blocks(ctx, b, s, False))}</div></details>"
                      for q, b, s in qs)
        return ["@@FAQ@@", f'<section aria-labelledby="faq">', f'<h2 id="faq">{FAQ_H[lang]}</h2>',
                f'<div class="faq">{det}</div>', "</section>"]
    if kind == "sources":
        text = " ".join(l.strip() for l in lines if l.strip())
        return ["@@SOURCES@@" + f'<p class="note">{inline(text)}</p>']
    raise MdError(f"line {ln - 1}: unknown container ':::{kind}'")


# ---------------------------------------------------------------- series
def series_bits(meta, series_path):
    if not meta.get("series"):
        return "", ""
    if not series_path:
        raise MdError("front matter names a series; pass --series <file>")
    with open(series_path, encoding="utf-8") as f:
        ser = json.load(f)
    if ser.get("id") != meta["series"]:
        raise MdError(f"series file id {ser.get('id')!r} != front matter series {meta['series']!r}")
    lang = meta["lang"]
    parts = ser["parts"]
    slugs = [p["slug"] for p in parts]
    if meta["slug"] not in slugs:
        raise MdError(f"slug {meta['slug']} is not in the series file")
    i = slugs.index(meta["slug"])
    if meta.get("part") and int(meta["part"]) != i + 1:
        raise MdError(f"front matter part {meta['part']} != position {i + 1} in the series file")
    t = SERIES_TXT[lang]
    pre = "/en" if lang == "en" else ""
    url = lambda p: f"{pre}/ax/{p['slug']}/"
    name = ser["name"][lang]
    bits = [html.escape(t["line"].format(name=name, i=i + 1, n=len(parts)))]
    if i > 0:
        bits.append(f'{t["prev"]} <a href="{url(parts[i - 1])}">{html.escape(parts[i - 1][lang])}</a>')
    if i < len(parts) - 1:
        bits.append(f'{t["next"]} <a href="{url(parts[i + 1])}">{html.escape(parts[i + 1][lang])}</a>')
    top = '<p class="note">' + ' <span aria-hidden="true">·</span> '.join(bits) + "</p>"
    lis = []
    for k, p in enumerate(parts):
        label = f"{k + 1}. {html.escape(p[lang])}"
        lis.append(f'<li><strong aria-current="page">{label}</strong></li>' if k == i
                   else f'<li><a href="{url(p)}">{label}</a></li>')
    nxt = (f'<p>{t["next"]}: <a href="{url(parts[i + 1])}">{html.escape(parts[i + 1][lang])}</a></p>'
           if i < len(parts) - 1 else f'<p>{t["last"]}</p>')
    bottom = (f'<nav class="box" aria-label="{t["nav"]}"><p><strong>{html.escape(t["list"].format(name=name, n=len(parts)))}'
              f'</strong></p><ul>{"".join(lis)}</ul>{nxt}</nav>')
    return top, bottom


# ---------------------------------------------------------------- page
def convert(text, path="note.md", series_path=None, site=ROOT):
    for ch, why in FORBIDDEN_CHARS.items():
        for k, l in enumerate(text.splitlines(), 1):
            if ch in l:
                raise MdError(f"line {k}: {why} is not allowed")
    lines = text.splitlines()
    meta, body_start = parse_front(lines)
    ctx = Ctx(meta, site, path)
    lang = meta["lang"]
    top, bottom = series_bits(meta, series_path)

    # split into intro + sections at "## " headings
    sections, cur, cur_start = [], {"h": None, "lines": [], "ln": body_start + 1}, body_start
    i = body_start
    in_code = False
    while i < len(lines):
        l = lines[i]
        if l.strip().startswith("```"):
            in_code = not in_code
        if not in_code and l.startswith("## "):
            sections.append(cur)
            m = re.match(r"^##\s+(.+?)\s*\{#([a-z0-9][a-z0-9-]*)\}\s*$", l)
            if not m:
                raise MdError(f"line {i + 1}: section heading needs an id: '## Heading {{#kebab-id}}'")
            hid = m.group(2)
            if hid in ctx.ids or hid == "faq":
                raise MdError(f"line {i + 1}: id '{hid}' is used twice (or is the reserved 'faq')")
            ctx.ids.add(hid)
            cur = {"h": (m.group(1), hid), "lines": [], "ln": i + 2}
        else:
            cur["lines"].append(l)
        i += 1
    sections.append(cur)

    intro = sections[0]
    out = ["<!doctype html>", f'<html lang="{lang}">', "<head>", '<meta charset="utf-8">',
           f"<title>{html.escape(meta['title'], quote=False)} – SugarMount</title>",
           f'<meta name="description" content="{html.escape(meta["description"])}">',
           "</head>", "<body>", '  <main id="main" class="container">', '    <section class="hero">',
           f'      <span class="eyebrow">{EYEBROW[lang].format(TYPES[meta["type"]][0 if lang == "ko" else 1])}</span>',
           f"      <h1>{inline_plain(meta['title'])}</h1>",
           f'      <p class="lead">{inline(meta["lead"])}</p>']
    if top:
        out.append("      " + top)
    tail, sources = [], []
    for b in blocks(ctx, intro["lines"], intro["ln"]):
        if b.startswith("@@SOURCES@@"):
            sources.append(b[11:])
        elif b == "@@FAQ@@":
            raise MdError("':::faq' cannot sit in the intro")
        else:
            out.append("      " + b)
    out.append("    </section>")
    for sec in sections[1:]:
        title, hid = sec["h"]
        rendered = blocks(ctx, sec["lines"], sec["ln"])
        body, faq = [], []
        target = body
        for b in rendered:
            if b == "@@FAQ@@":
                target = faq
            elif b.startswith("@@SOURCES@@"):
                sources.append(b[11:])
            else:
                target.append(b)
        out += ["", f'    <section aria-labelledby="{hid}">', f'      <h2 id="{hid}">{inline(title)}</h2>']
        out += ["      " + b for b in body]
        out.append("    </section>")
        if faq:
            tail.append(faq)
    if len(ctx.ids - {"faq"}) < 1:
        raise MdError("the note has no '## Heading {#id}' section")
    if bottom:
        out += ["", "    " + bottom]
    for faq in tail:
        out += [""] + ["    " + b for b in faq]
    for s in sources:
        out += ["", "    " + s]
    out += ["", "    " + NOTICE[lang], "  </main>", "</body>", "</html>", ""]
    return meta, "\n".join(out)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    src = argv[0]
    series = argv[argv.index("--series") + 1] if "--series" in argv else None
    site = argv[argv.index("--out") + 1] if "--out" in argv else ROOT
    with open(src, encoding="utf-8-sig") as f:
        text = f.read()
    try:
        meta, page = convert(text, src, series, site)
    except MdError as e:
        print(f"{src}: {e}", file=sys.stderr)
        return 1
    rel = (["en"] if meta["lang"] == "en" else []) + ["ax", meta["slug"], "index.html"]
    dest = os.path.join(site, *rel)
    if "--check" in argv:
        print(f"ok {src} -> {'/'.join(rel)} ({len(page.encode('utf-8'))} B)")
        return 0
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(f"wrote {'/'.join(rel)} ({len(page.encode('utf-8'))} B)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
