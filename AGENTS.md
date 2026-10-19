# mvgood21.github.io — SugarMount site

GitHub Pages site for every SugarMount (simpest) Android app: home, app pages, privacy policies, `app-ads.txt`.
Korean at `/`, English at `/en/`. Support email: sugarmount21@gmail.com.

## How the site is built

Plain static files, no framework. `tools/build.py` (Python standard library only) rebuilds the shared parts:

| What | Source of truth | Who writes it |
|---|---|---|
| `index.html`, `en/index.html` (home), `apps/index.html`, `en/apps/index.html` (app hub) | `data/apps.json` | generated |
| `privacy/index.html`, `en/privacy/index.html` (policy list, incl. AXFamily delete/terms links) | `data/apps.json` + effective dates read from each policy | generated |
| `apps/<app_path>/` for apps with `"page": "generated"` | `data/apps.json` (`title_topic`, `meta`, `summary`, `features`, `facts`, `privacy`, `limits`, `faq`, `tasks`, `releases`) | generated |
| `sitemap.xml` (lastmod = modified; images: screenshots/article captures + app share image), `rss.xml` + `en/rss.xml` (full `<main>` per item, for Naver and subscribers; never submit RSS as a sitemap), `robots.txt` (one `User-agent: *` group, one `Sitemap:` line), `llms.txt`, `404.html`, `/<IndexNow key>.txt` (from `data/indexnow-key.txt`) | all pages + `data/apps.json` | generated |
| `assets/sds-apps.css` (per-app accent tokens for `[data-app]`), `assets/fonts/pretendard.css` (only the Pretendard subsets the site's text needs) | `data/apps.json`, rendered pages | generated in memory by `tools/sds_apps.py` before the CSS version `?v=` is computed |
| `data/content-dates.json` (published/modified per page) | hash of each hand page's `<main>` minus build blocks, or of a generated page's input data | `tools/dates.py` via the build; never edit dates by hand |
| articles under an app: `apps/<app_path>/<slug>/index.html` (ko and en pair) | the file's own `<title>`, description and `<main>` | you; build adds breadcrumbs, `build:meta` (byline, read time, updated), `build:toc` (3+ `h2[id]`), `Article` JSON-LD with the `assets/og/article-*` images, and lists the article on the app page, hub and home |
| AX notes: hub `ax/index.html` + `ax/<slug>/index.html` (ko and en); topics in `data/ax.json` (every note slug needs a topic there, or the build stops; `topic` is a reserved slug) | the file's own `<main>`; topic pages `ax/topic/<id>/` are generated | you; build adds breadcrumbs (AX 노트 › topic › note), `build:meta`, `build:toc`, `Article` JSON-LD with the topic as `articleSection`, the hub's newest 12 (`build:ax-list`) and topic cards (`build:ax-topics`), related notes (same topic first, 6 in all), the home section (topic links, so the home font budget doesn't move with each new title), RSS (newest 60 items per feed), sitemap and llms.txt entries grouped by topic. Notes are published daily (3 a day) from a private desk outside this repo; keep the Korean body within the 470 KB font budget by rewording rare syllables. Content rule: only SugarMount's own apps and repos, numbers with source and date; no employer, job title, or link to the separate AX consulting site (re-identification risk, owner decision 2026-10-18) |
| `/about/`, `/en/about/` | the file's own `<main>` | you; build adds `ProfilePage` + the one full `Organization` node, `build:toc` |
| `design/index.html` (SDS demo, ko only, `noindex`, listed in `NOINDEX_PATHS`) | the file's own `<main>` | you; no canonical, hreflang, breadcrumbs, JSON-LD, sitemap/RSS/llms entry |
| every other `*.html` (hand-written app pages, all privacy policies) | the file's own `<main>` | you; build keeps `<main>` byte for byte except the `<!-- build:NAME -->` blocks (`tasks`, `meta`, `toc`, `extra`, `ax-list`) and one rewrite: Play install links on app pages and articles get the site's `referrer` UTM. It replaces `<head>`, header (Popover menu), footer, breadcrumbs and JSON-LD around `<main>`. Policies get a `build:extra` "관련 문서" block (app page, one help article, AXFamily documents) |
| share images `assets/og/app-<id>-<lang>.png`, `assets/og/article-*.png`, hub/about/AX/privacy cards, `assets/og.png` (ko home) + `assets/og/home-en.png` (en home), `assets/logo.png`, `favicon.ico`, `assets/favicon.png`, `assets/apple-touch-icon.png` | real screenshots in `assets/apps`, `data/apps.json` | `tools/og.py` (needs Pillow); `python tools/og.py --articles` after adding an article |

Never edit generated files by hand; the next build overwrites them. Edit `data/apps.json` or `tools/build.py` instead.
`assets/site.css` is hand-written (SDS tokens and components); `sitemap.xsl` is static (SDS neutral colours).

```bash
python tools/og.py                 # when an app is added or its screenshots/name change (all share images)
python tools/build.py              # rebuild; prints how many files changed and a one-line gate summary
python tools/build.py --check      # exit 1 if a rebuild would change anything OR a gate fails (run before committing)
python tools/checks.py --file <path>   # read-only checks for content authors (title, description, <main>)
python -m unittest discover -s tools/tests
python tools/indexnow.py           # dry run: URLs whose modified date is today; --send only with owner approval
                                   # (default: the shared api.indexnow.org, which already reaches Naver)
```

`--check` gates: `tools/checks.py` over the in-memory build (structured data, links and anchors, headings, head/hreflang/NOINDEX,
sitemap/RSS/robots/llms, size and font budgets), plus SDS gates (accent contrast ≥ 4.5, `sds-apps.css` tokens equal the computed
ones, header mark colours equal `tools/og.py`). Idempotency test: two builds in a row change nothing, and
`SOURCE_DATE=<tomorrow> python tools/build.py` changes nothing either.

### Who edits what (several agents may work in parallel)

- Content authors own the `<title>`, `<meta name="description">` and `<main>` of hand-written pages. Do not edit inside
  `<!-- build:NAME -->` blocks or outside `<main>`, and do not run `tools/build.py`; check with `tools/checks.py --file`.
- `tools/build.py`, every generated file and everything outside `<main>` belong to the build owner, who runs the one
  integration build. New build logic goes in a new module that `build.py` imports (`dates.py`, `checks.py`, `sds_apps.py`).
- Headings in the chrome are `p.menu-title` / `p.footer-title` (no `<h*>` outside `<main>`); `data-app` goes on `<main>` only
  (menu `.app-tile` excepted); one anchor text never points at two URLs on a page, header and footer included.

### App source of truth (B0-7)

Facts on app pages, articles and policies are checked against these repositories:
`C:\Users\mvgood\sugar-utils` (canonical for sugarcompress, sugarflip, sugarconvert, sugardoc; the copy at
`P:\Projects\Projects_SM\sugar-utils` is not used), `C:\Users\mvgood\sugar-game` (arrows, blocks),
`P:\Projects\Projects_SM\<app>` (sugarspeller, sugarcard, sugaralbum, sugarclip). If a fact cannot be verified there, leave it out.

## Adding or updating an app

1. Assets: `assets/apps/<id>/icon.png` (192×192) and `icon.webp` (144×144); screenshots as `.webp` (about 360 px wide).
2. Add an entry to `data/apps.json` (copy a similar app). Key fields:
   - `id`, `package`, `accent` (hex, white text on it must reach 4.5:1), `icon` (path without extension), `category` (`photo|video|document|text|card|game`), `schema_category` (schema.org applicationCategory)
   - `status`: `live` (on Google Play), `soon`, `review` (in Play review). `play: true` only when the listing is public; it adds the Play button, Play link and `installUrl`.
   - `page`: `hand` (you write `apps/<app_path>/index.html`), `generated` (build writes it from `features/facts/privacy/faq`), or `none` (no app page; links go to the policy).
   - `app_path`, `privacy_path`: URL slugs. **Never rename an existing slug**: apps and the Play Console link to them.
   - `ko` / `en`: `name`, `brand`, optional `store_title`, `tagline` (one line), `desc` (2–3 sentences), `shots`.
3. Write the privacy policy pages `privacy/<privacy_path>/index.html` and `en/privacy/<privacy_path>/index.html` from a source audit (copy an existing policy for structure; the build replaces head/header/footer). Keep the `시행일: YYYY년 M월 D일` / `Effective: Month D, YYYY` line; the policy list reads it.
4. Hand-written app page (if `page: hand`): `apps/<app_path>/index.html` + `en/...`, content inside `<main>`.
5. `python tools/og.py && python tools/build.py && python tools/build.py --check`, check the page in a browser at 390 px and desktop, then commit.

## Fixed URLs (do not move)

- `/privacy/blocks/`, `/en/privacy/blocks/` — hard-coded in Block Turn and the Play Console.
- `/google83e3e62aee87a145.html` (Search Console) and `/naverc6d2c9710a0b598bb0562751a0d005b7.html` (Naver Search Advisor) — ownership files, keep them.
- `/privacy/doc-viewer/`, `/en/privacy/doc-viewer/`, `/apps/doc-viewer/`, `/en/apps/doc-viewer/` — SugarDoc app config and listing; `release_gate.sh` checks for 200.
- Every other `/privacy/<slug>/` linked from a Play listing. `/app-ads.txt` at the root (AdMob).

## Rules

- Policies describe the actual code. Don't add claims the code doesn't back.
- No home address, phone number or secrets anywhere. Privacy officer is listed as "Simpest".
- Several Claude sessions edit this repo. Pull before editing, keep changes small, run `--check` before committing.
- Design tokens and components live in `assets/site.css` (SDS; demo at `/design/`); each app's accent comes from `apps.json`
  through the generated `assets/sds-apps.css` and `data-app="<id>"` on `<main>`. Fonts are self-hosted (no external origin).
  `/en/` pages use the `Pretendard Latin` family (two subsets, about 62 KB); any other glyph there falls back to the system
  font, as do `.sym`, code and the breadcrumb separator.
