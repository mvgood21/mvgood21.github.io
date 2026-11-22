"""Install button and status line that follow data/apps.json (build.py imports this).

A hand-written app page or help article places empty markers, and build.py fills them on every build:

  <!-- build:install --><!-- /build:install -->   the install button. "play": true in the app's entry: a Google Play
                                                  link with the site's install referrer. Otherwise a "coming soon"
                                                  pill that is not a link (<span>), so no page points at a store page
                                                  that is not public yet.
  <!-- build:status --><!-- /build:status -->     app page hero only: the status badge and one line.

Going public is then one edit in data/apps.json (the app's "status": "live", "play": true) and a build: the hand
pages do not change. Page dates hash <main> minus build blocks (tools/dates.py), so they keep their dates too.
The pill's look is per page (AXFamily: assets/apps/axfamily/page.css .button--soon), since only pages that use the
marker need it. Standard library only.
"""
import html

TEXT = {
    "ko": {"soon_button": "Google Play 곧 공개", "soon_line": "곧 Google Play에 공개해요.", "review_line": "Google Play 심사 중이에요."},
    "en": {"soon_button": "Coming soon to Google Play", "soon_line": "Coming to Google Play soon.", "review_line": "In Google Play review."},
}


def esc(s): return html.escape(s, quote=True)


def button(a, lang, href, label):
    """Inner HTML of <!-- build:install -->. href: the Play URL with referrer (None while the listing is not public);
    label: the button text the page would show once live (e.g. "Google Play에서 받기")."""
    if a.get("play") and href:
        return f'<a class="button play-badge" href="{esc(href)}" rel="noopener">{esc(label)}</a>'
    return f'<span class="button button--soon">{esc(TEXT[lang]["soon_button"])}</span>'


def status(a, lang, badge_text, store_title=""):
    """Inner HTML of <!-- build:status -->: badge + one line (live: the store title, otherwise when it comes)."""
    line = {"soon": TEXT[lang]["soon_line"], "review": TEXT[lang]["review_line"]}.get(a["status"], store_title)
    b = f' <span class="brandline">{esc(line)}</span>' if line else ""
    return f'<p class="status"><span class="badge badge--{a["status"]}">{esc(badge_text)}</span>{b}</p>'
