"""Tests for the "AX notes on this app" list on app pages (tools/build.py ax_notes_for_app).
Run: python -m unittest discover -s tools/tests
"""
import os, sys, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build  # noqa: E402

APP = {"app_path": "x", "page": "generated", "ko": {}, "en": {}}
MENU = '<nav><a href="/apps/x/">X</a></nav>'
BLOCK = '<!-- build:cta --><a href="/apps/x/">X</a><!-- /build:cta -->'
BODY = '<p><a href="/apps/x/">X</a></p>'


def notes(pages):
    """ax_notes_for_app over fake notes: pages maps note url -> its <main> inner HTML (the menu sits outside <main>)."""
    arts = [(u, u, "") for u in pages]
    html_of = {build.relpath_of(u): f"<html>{MENU}<main>{inner}</main></html>" for u, inner in pages.items()}
    with mock.patch.object(build, "ax_articles", lambda lang: arts), \
         mock.patch.object(build, "read", lambda relp: html_of[relp]), \
         mock.patch.object(build, "app_url", lambda a, lang: "/apps/x/"):
        return [u for u, _, _ in build.ax_notes_for_app(APP, "ko")]


class AxNotesForApp(unittest.TestCase):
    def test_menu_and_build_block_links_do_not_count(self):
        self.assertEqual(notes({"/ax/a/": "<p>no link</p>", "/ax/b/": BLOCK}), [])

    def test_body_link_counts_in_article_order_up_to_three(self):
        pages = {f"/ax/n{i}/": BODY for i in range(5)}
        pages["/ax/n1/"] = BLOCK
        self.assertEqual(notes(pages), ["/ax/n0/", "/ax/n2/", "/ax/n3/"])


if __name__ == "__main__":
    unittest.main()
