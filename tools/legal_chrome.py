"""Isolated chrome for legal pages an app opens itself (apps.json "legal_chrome": "isolated").

Google Play payments policy (consumption-only apps): pages opened from inside the app must not lead to pricing or
purchase pages. These pages therefore get a header with only the app name (to its policy) and the language link, a
footer with only the same app's legal pages (apps.json "legal_links") and the email, and no breadcrumbs, no
build:extra links and no links to home, the app hub, the policy list or the app's landing page.

STANDALONE_PATHS are hand-written pages the build never wraps or rewrites (their own <head> and inline style stay),
for example a sign-in link landing page whose URL carries a one-time token. They are noindex and left out of the
sitemap, RSS and llms.txt. Keep this a plain set literal.
"""
import html

STANDALONE_PATHS = {"cardrawer/auth/index.html"}


def esc(s): return html.escape(s, quote=True)


def is_isolated(a, parts):
    """parts: the path split below the language prefix, e.g. ["privacy", "cardrawer", "terms"]."""
    return bool(a and a.get("legal_chrome") == "isolated" and parts and parts[0] == "privacy")


def header(t, a, lang, home_href, other_href, brand_mark):
    """home_href: the app's privacy policy URL (the brand link stays inside the legal pages)."""
    return f'''<a class="skip" href="#main">{t["skip"]}</a>
  <header class="site-header">
    <div class="container">
      <a class="brand" href="{home_href}">{brand_mark}<span class="brand-name">{esc(a[lang]["name"])}</span></a>
      <a class="lang" href="{other_href}" lang="{t["other_lang_code"]}" hreflang="{t["other_lang_code"]}">{t["other_lang"]}</a>
    </div>
  </header>'''


def footer(t, a, lang, base_href, email, here_href=None):
    """Only this app's legal pages and the email. The page itself is listed without a link."""
    lis = []
    for sub, name in a.get("legal_links", {}).get(lang, []):
        u = base_href + sub
        lis.append(f'<li><span aria-current="page">{esc(name)}</span></li>' if u == here_href else f'<li><a href="{u}">{esc(name)}</a></li>')
    return f'''<footer class="site-footer">
    <div class="container">
      <div>
        <p>{t["email"]}: <a href="mailto:{email}">{email}</a></p>
      </div>
      <nav aria-label="{esc(a[lang]["name"])}">
        <ul>{"".join(lis)}</ul>
      </nav>
      <div class="legal"><span><span class="sym">©</span> {t["copyright"]}</span></div>
    </div>
  </footer>'''
