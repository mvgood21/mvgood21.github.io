# mvgood21.github.io — SugarMount site

GitHub Pages site for every SugarMount (simpest) Android app: home, app pages, privacy policies, `app-ads.txt`.
Korean at `/`, English at `/en/`. Support email: sugarmount21@gmail.com.

## How the site is built

Plain static files, no framework. `tools/build.py` (Python standard library only) rebuilds the shared parts:

| What | Source of truth | Who writes it |
|---|---|---|
| `index.html`, `en/index.html` (home) | `data/apps.json` | generated |
| `privacy/index.html`, `en/privacy/index.html` (policy list) | `data/apps.json` + effective dates read from each policy | generated |
| `apps/<app_path>/` for apps with `"page": "generated"` | `data/apps.json` (`features`, `facts`, `privacy`, `faq`) | generated |
| `sitemap.xml`, `llms.txt`, `404.html` | all pages + `data/apps.json` | generated |
| every other `*.html` (hand-written app pages, all privacy policies) | the file's own `<main>` | you; build keeps `<main>` byte for byte and replaces `<head>`, header, footer, breadcrumbs and JSON-LD around it |
| share images `assets/og/<id>-<lang>.png`, `assets/og.png`, `assets/logo.png` | `data/apps.json` | `tools/og.py` (needs Pillow) |

Never edit generated files by hand; the next build overwrites them. Edit `data/apps.json` or `tools/build.py` instead.

```bash
python3 tools/og.py          # only when an app is added or its name/tagline/icon changes
python3 tools/build.py       # rebuild; prints how many files changed
python3 tools/build.py --check   # exit 1 if a rebuild would change anything (run before committing)
```

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
5. `python3 tools/og.py && python3 tools/build.py && python3 tools/build.py --check`, check the page in a browser at 390 px and desktop, then commit.

## Fixed URLs (do not move)

- `/privacy/blocks/`, `/en/privacy/blocks/` — hard-coded in Block Turn and the Play Console.
- `/privacy/doc-viewer/`, `/en/privacy/doc-viewer/`, `/apps/doc-viewer/`, `/en/apps/doc-viewer/` — SugarDoc app config and listing; `release_gate.sh` checks for 200.
- Every other `/privacy/<slug>/` linked from a Play listing. `/app-ads.txt` at the root (AdMob).

## Rules

- Policies describe the actual code. Don't add claims the code doesn't back.
- No home address, phone number or secrets anywhere. Privacy officer is listed as "Stephen, Jeong (simpest)".
- Several Claude sessions edit this repo. Pull before editing, keep changes small, run `--check` before committing.
- Design tokens and components live in `assets/site.css`; each app's accent comes from `apps.json` via `style="--accent:…"`.
