"""Tests for tools/glyphcheck.py: a syllable the bundled font maps but does not draw must be reported.
Run: python -m unittest discover -s tools/tests
"""
import importlib, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

FONT = os.path.join(os.path.dirname(os.path.dirname(HERE)), "tools/fonts/nanumsquareeb.ttf")


class GlyphCheck(unittest.TestCase):
    def setUp(self):
        import glyphcheck
        self.g = importlib.reload(glyphcheck)
        self.g.install()
        self.f = ImageFont.truetype(FONT, 30)

    def tearDown(self):
        ImageDraw.ImageDraw.text = self.g._orig

    def draw(self, text):
        ImageDraw.Draw(Image.new("RGB", (300, 60))).text((0, 0), text, font=self.f)

    def test_rare_syllable_is_reported(self):
        self.draw("가 밣")  # U+BC23: in cmap, empty outline in NanumSquare EB (measured 2026-10-23)
        self.assertFalse(self.g.report())
        self.assertIn("밣", self.g._blank)

    def test_common_text_and_spaces_pass(self):
        self.draw("한글 띄어쓰기 R8 1,200")
        self.assertTrue(self.g.report())


if __name__ == "__main__":
    unittest.main()
