"""Tests for tools/ax_figures.py: --sync-html sets only width/height of /assets/ax/*.webp images, idempotently; the bar
chart draws real proportional bars in the brand colours; stale colour words are caught.
Run: python -m unittest discover -s tools/tests
"""
import json, os, shutil, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image  # noqa: E402
import ax_figures as F  # noqa: E402

PAGE = ('<!doctype html>\r\n<main>\r\n'
        '<figure class="ax-fig"><img src="/assets/ax/n-1-ko.webp" width="1200" height="498" alt="막대 &quot;A&quot;" loading="lazy">'
        '<figcaption>c</figcaption></figure>\r\n'
        '<img alt="x" height="10" src="/assets/ax/n-2-ko.webp" loading="lazy" width="5">\r\n'
        '<img src="/assets/ax/n-3-ko.webp" alt="no size yet">\r\n'
        '<img src="/assets/ax/cover/n-ko.webp" width="1200" height="900" alt="">\r\n'
        '<img src="/assets/apps/a/shot.webp" width="7" height="7" alt="">\r\n'
        '<img src="/assets/ax/missing-1-ko.webp" width="1" height="1" alt="">\r\n</main>\r\n')


class SyncHtml(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        for rel in ("ax/n", "en/ax/n", "assets/ax/cover"): os.makedirs(os.path.join(self.root, rel))
        for name, size in (("n-1-ko", (1200, 512)), ("n-2-ko", (1200, 640)), ("n-3-ko", (1200, 333)),
                           ("cover/n-ko", (1200, 901))):
            Image.new("RGB", size, "white").save(os.path.join(self.root, "assets/ax", name + ".webp"), "WEBP")
        self.page = os.path.join(self.root, "ax/n/index.html")
        with open(self.page, "w", encoding="utf-8", newline="") as fh: fh.write(PAGE)
        self.en = os.path.join(self.root, "en/ax/n/index.html")
        with open(self.en, "w", encoding="utf-8", newline="") as fh:
            fh.write('<img src="/assets/ax/n-1-ko.webp" width="1200" height="512" alt="">\n')

    def tearDown(self): shutil.rmtree(self.root)

    def read(self, p):
        with open(p, encoding="utf-8", newline="") as fh: return fh.read()

    def test_sets_real_size_and_nothing_else(self):
        changed = F.sync_html(self.root)
        self.assertEqual(changed, [("ax/n/index.html", 3)])
        want = (PAGE.replace('n-1-ko.webp" width="1200" height="498"', 'n-1-ko.webp" width="1200" height="512"')
                    .replace('height="10" src="/assets/ax/n-2-ko.webp" loading="lazy" width="5"',
                             'height="640" src="/assets/ax/n-2-ko.webp" loading="lazy" width="1200"')
                    .replace('n-3-ko.webp" alt=', 'n-3-ko.webp" width="1200" height="333" alt='))
        self.assertEqual(self.read(self.page), want)   # CRLF, the cover, other images and the missing file untouched
        self.assertEqual(self.read(self.en), '<img src="/assets/ax/n-1-ko.webp" width="1200" height="512" alt="">\n')

    def test_idempotent(self):
        F.sync_html(self.root)
        first = self.read(self.page)
        self.assertEqual(F.sync_html(self.root), [])
        self.assertEqual(self.read(self.page), first)


class Draw(unittest.TestCase):
    def count(self, im, rgb):
        return sum(1 for px in im.getdata() if px == rgb)

    def test_bars_are_proportional_and_branded(self):
        d = {"title": "t", "unit": "", "items": [["a", 100], ["b", 50, "hi"], ["c", 0]]}
        im = F.draw_bars(d)
        self.assertEqual(im.width, F.W)
        rows = [y for y in range(F.STRIPE, im.height) if im.getpixel((F.W // 2, y)) == F.BLUE]
        self.assertTrue(rows, "the plain bar is Summit Blue")
        y_blue = rows[len(rows) // 2]
        y_honey = next(y for y in range(im.height) if im.getpixel((F.W // 2 - 200, y)) == F.HONEY)
        blue_w = sum(1 for x in range(F.W) if im.getpixel((x, y_blue)) == F.BLUE)
        honey_w = sum(1 for x in range(F.W) if im.getpixel((x, y_honey + 10)) == F.HONEY)
        self.assertAlmostEqual(honey_w / blue_w, 0.5, delta=0.02)

    def test_no_hi_means_no_honey_bar(self):
        im = F.draw_bars({"title": "t", "items": [["a", 3], ["b", 1]]})
        # the top stripe's Honey tab is the only Honey left
        self.assertEqual(self.count(im, F.HONEY), self.count(im.crop((0, 0, F.W, F.STRIPE)), F.HONEY))

    def test_string_values_and_old_kinds_still_draw(self):
        F.draw_bars({"title": "t", "unit": "%", "items": [["a", "4.20", "hi"], ["b", 4.4]]})
        F.draw_steps({"title": "t", "note": "n", "items": [["a", "b"], ["c", "d"]]})
        im = F.draw_compare({"title": "t", "left": ["L", ["x"]], "right": ["R long head " * 6, ["y", "z"]]})
        self.assertEqual(im.width, F.W)


class StaleColour(unittest.TestCase):
    def test_old_palette_words_are_found(self):
        root = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(root, "data/ax-figures"))
            with open(os.path.join(root, "data/ax-figures/n.json"), "w", encoding="utf-8") as fh:
                json.dump([{"kind": "bars", "ko": {"note": "진한 막대 3개"}, "en": {"note": "The dark bars are"}}], fh,
                          ensure_ascii=False)
            self.assertEqual(len(F.stale_colour_words(root)), 2)
            with open(os.path.join(root, "data/ax-figures/n.json"), "w", encoding="utf-8") as fh:
                json.dump([{"kind": "bars", "ko": {"note": "노란 막대 3개"}, "en": {"note": "The honey bars are"}}], fh,
                          ensure_ascii=False)
            self.assertEqual(F.stale_colour_words(root), [])
        finally:
            shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
