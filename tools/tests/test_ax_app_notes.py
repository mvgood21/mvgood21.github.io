"""Tests for the "AX notes on this app" list on app pages (tools/build.py ax_notes_for_app), against the repo's own pages.
Run: python -m unittest discover -s tools/tests
"""
import os, re, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build  # noqa: E402


class AxNotesForApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build.STORE = build.dates.ContentDates(check=True)  # read-only: newest-first order needs published dates

    def test_site_menu_links_do_not_count(self):
        # every note's menu and footer link every live app; only body links may put a note on an app page
        a = next(x for x in build.APPS if x.get("app_path") == "sugaralbum")
        for lang in ("ko", "en"):
            self.assertEqual(build.ax_notes_for_app(a, lang), [])

    def test_listed_notes_link_the_app_in_their_body(self):
        a = next(x for x in build.APPS if x.get("app_path") == "doc-viewer")
        for lang in ("ko", "en"):
            notes = build.ax_notes_for_app(a, lang)
            self.assertTrue(1 <= len(notes) <= 3)
            target = build.app_url(a, lang)
            for u, _, _ in notes:
                s = build.read(build.relpath_of(u))
                body = re.sub(r"<!-- build:([\w-]+) -->.*?<!-- /build:\1 -->", "", s, flags=re.S)
                self.assertIn(f'href="{target}"', body, u)


if __name__ == "__main__":
    unittest.main()
