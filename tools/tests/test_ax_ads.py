"""Tests for the AX note ad units (tools/ax_extras.py ads_config / ad_unit / ads_txt).
Run: python -m unittest discover -s tools/tests
"""
import json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import ax_extras  # noqa: E402

SLOTS = {"in_article": "1", "rail_left": "2", "rail_right": "3"}


def cfg(data, preview=False):
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "data"))
        with open(os.path.join(root, ax_extras.ADS_FILE), "w", encoding="utf-8") as f: json.dump(data, f)
        old = os.environ.pop("AX_ADS_PREVIEW", None)
        if preview: os.environ["AX_ADS_PREVIEW"] = "1"
        try: return ax_extras.ads_config(root)
        finally:
            os.environ.pop("AX_ADS_PREVIEW", None)
            if old is not None: os.environ["AX_ADS_PREVIEW"] = old


class Ads(unittest.TestCase):
    def test_no_client_means_no_markup_head_or_ads_txt(self):
        c = cfg({"client": "", "slots": SLOTS})
        for kind in SLOTS: self.assertEqual(ax_extras.ad_unit(c, kind, "ko"), "")
        self.assertEqual(ax_extras.ads_head(c), "")
        self.assertIsNone(ax_extras.ads_txt(c))
        self.assertEqual(ax_extras.ads_meta(c), "")

    def test_missing_slot_keeps_ads_off(self):
        c = cfg({"client": "ca-pub-1", "slots": {"in_article": "1"}})
        self.assertFalse(c["on"])
        self.assertEqual(ax_extras.ad_unit(c, "in_article", "ko"), "")
        self.assertEqual(ax_extras.ads_head(c), "")
        # ownership meta and ads.txt come with the client alone (AdSense site review happens before ad units exist)
        self.assertEqual(ax_extras.ads_meta(c), '<meta name="google-adsense-account" content="ca-pub-1">')
        self.assertEqual(ax_extras.ads_txt(c), "google.com, pub-1, DIRECT, f08c47fec0942fa0\n")

    def test_on_renders_labelled_unit_loader_and_ads_txt(self):
        c = cfg({"client": "ca-pub-123", "slots": SLOTS})
        u = ax_extras.ad_unit(c, "rail_left", "en")
        self.assertIn('data-ad-client="ca-pub-123"', u)
        self.assertIn('data-ad-slot="2"', u)
        self.assertIn(">Advertisement<", u)
        self.assertIn("async", ax_extras.ads_head(c))
        self.assertEqual(ax_extras.ads_txt(c), "google.com, pub-123, DIRECT, f08c47fec0942fa0\n")

    def test_serve_false_keeps_units_off_but_keeps_ownership(self):
        c = cfg({"client": "ca-pub-9", "serve": False, "slots": SLOTS})
        self.assertFalse(c["on"])
        self.assertEqual(ax_extras.ad_unit(c, "rail_right", "ko"), "")
        self.assertEqual(ax_extras.ads_head(c), "")
        self.assertIn("ca-pub-9", ax_extras.ads_meta(c))
        self.assertTrue(cfg({"client": "ca-pub-9", "serve": True, "slots": SLOTS})["on"])

    def test_preview_only_when_off(self):
        self.assertIn("ad-preview", ax_extras.ad_unit(cfg({"client": "", "slots": SLOTS}, preview=True), "in_article", "ko"))
        on = cfg({"client": "ca-pub-1", "slots": SLOTS}, preview=True)
        self.assertNotIn("ad-preview", ax_extras.ad_unit(on, "in_article", "ko"))


if __name__ == "__main__":
    unittest.main()
