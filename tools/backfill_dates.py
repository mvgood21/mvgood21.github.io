#!/usr/bin/env python3
"""One-off: create data/content-dates.json from git history (IA spec 4.1). Standard library only.

  python tools/backfill_dates.py             # write data/content-dates.json (refuses if it exists)
  python tools/backfill_dates.py --force     # overwrite an existing file
  python tools/backfill_dates.py --dry-run   # print the result, write nothing

For every committed page (index.html files and /404.html, outside tools/, data/, assets/):
  published = date of the first commit that added the file at this path
  (no --follow on purpose: git's similarity detection "follows" e.g. apps/image-flip/ back to apps/image-compress/,
  which is a different URL; site URLs are never renamed, so the path history is the URL history)
  modified  = date of the last commit whose <main> hash (dates.hand_input) differs from the commit before it
  hash      = that hash at HEAD for hand-written pages; null for generated pages, whose hash input is the
              build's data (dates.data_input) and is adopted on the first build without moving the dates.
Dates are git %cs (committer date, YYYY-MM-DD). Pages not yet committed are left out: the build adds them
as new (published = modified = today). The working tree is never read for page content, only for the list
of pages and data/apps.json (which apps are generated).
"""
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dates  # noqa: E402

ROOT = dates.ROOT


def git(root, *args):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout


def committed_pages(root):
    out = git(root, "ls-files", "-z").decode("utf-8").split("\0")
    pages = []
    for p in out:
        if not p: continue
        top = p.split("/", 1)[0]
        if top.startswith(".") or top in ("tools", "data", "assets"): continue
        if p.endswith("/index.html") or p == "index.html" or p == "404.html":
            pages.append(p)
    return sorted(pages)


def generated_pages(root):
    gen = {"index.html", "en/index.html", "privacy/index.html", "en/privacy/index.html", "404.html",
           "apps/index.html", "en/apps/index.html"}
    path = os.path.join(root, "data", "apps.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for a in json.load(f).get("apps", []):
                if a.get("page") == "generated" and a.get("app_path"):
                    gen.add(f"apps/{a['app_path']}/index.html")
                    gen.add(f"en/apps/{a['app_path']}/index.html")
    return gen


def history(root, relpath):
    """[(sha, day, path_at_commit)] oldest first, for this path only (see module docstring on --follow)."""
    raw = git(root, "log", "--format=%x01%H %cs", "--name-only", "--", relpath).decode("utf-8")
    out = []
    for block in raw.split("\x01"):
        lines = [l for l in block.strip().splitlines() if l.strip()]
        if not lines: continue
        sha, day = lines[0].split()
        path = lines[-1].strip() if len(lines) > 1 else relpath
        out.append((sha, day, path))
    out.reverse()
    return out


def backfill_page(root, relpath):
    hist = history(root, relpath)
    if not hist:
        return None
    published, modified, last_hash = hist[0][1], None, None
    for sha, day, path in hist:
        try:
            text = git(root, "show", f"{sha}:{path}").decode("utf-8", "replace")
        except RuntimeError:
            continue  # the file was deleted in this commit (rename/delete in followed history)
        h = dates.content_hash(dates.hand_input(text))
        if h != last_hash:
            modified, last_hash = day, h
    if modified is None:
        return None
    return {"hash": last_hash, "published": published, "modified": max(modified, published)}


def backfill(root=ROOT):
    gen = generated_pages(root)
    entries = {}
    for relpath in committed_pages(root):
        e = backfill_page(root, relpath)
        if e is None: continue
        if relpath in gen:
            e["hash"] = None
        entries[relpath] = e
    return entries


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    root = ROOT
    if "--root" in argv:
        root = os.path.abspath(argv[argv.index("--root") + 1])
    target = os.path.join(root, dates.DATES_FILE)
    entries = backfill(root)
    text = json.dumps(entries, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
    if "--dry-run" in argv:
        sys.stdout.write(text)
        return 0
    if os.path.exists(target) and "--force" not in argv:
        print(f"{dates.DATES_FILE} exists; pass --force to overwrite", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"{dates.DATES_FILE}: {len(entries)} pages "
          f"({sum(1 for e in entries.values() if e['hash'] is None)} generated with hash null)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
