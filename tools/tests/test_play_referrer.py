"""Tests for the Play install-link rewrite on hand-written app pages and articles (tools/build.py hand_source).
Run: python -m unittest discover -s tools/tests
"""
import os, sys, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build  # noqa: E402

APP = {"id": "x", "package": "com.example.x", "play": True}
BARE = '<a href="https://play.google.com/store/apps/details?id=com.example.x">Get</a>'
LANDING = ('<a href="https://play.google.com/store/apps/details?id=com.example.x&amp;referrer=utm_source%3Dsugarmount21'
           '%26utm_medium%3Dlanding%26utm_campaign%3Dlaunch%26utm_content%3Da&amp;hl=en">Get</a>')


def source(html, relpath="apps/x/guide/index.html", app=APP):
    with mock.patch.object(build, "read", lambda relp: html), \
         mock.patch.object(build, "BY_PACKAGE", {app["package"]: app}):
        return build.hand_source(relpath)


class PlayReferrer(unittest.TestCase):
    def test_article_link_gets_site_referrer(self):
        out = source(BARE)
        self.assertIn("utm_medium%3Dhowto", out)
        self.assertIn("utm_campaign%3Dx", out)

    def test_landing_link_with_utm_content_is_kept(self):
        self.assertEqual(source(LANDING), LANDING)
        self.assertEqual(source(LANDING, "en/apps/x/guide/index.html"), LANDING)

    def test_app_not_on_play_is_left_alone(self):
        self.assertEqual(source(BARE, app=dict(APP, play=False)), BARE)


if __name__ == "__main__":
    unittest.main()
