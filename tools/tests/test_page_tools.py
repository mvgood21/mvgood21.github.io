"""tools/page_tools.py: a data-tool section in <main> adds the tool's stylesheet and deferred script to <head>;
pages without one are untouched. Run: python -m unittest discover -s tools/tests
"""
import os, shutil, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import page_tools  # noqa: E402

MAIN = '<section class="hero"><h1>x</h1></section>\n<section class="tool" aria-labelledby="t" data-tool="photo-size">'


class PageTools(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="page-tools-")
        os.makedirs(os.path.join(self.root, "assets", "tools"))
        for rp, text in ((page_tools.CSS, ".tool{}\n"), (page_tools.TOOLS["photo-size"], "1;\n")):
            with open(os.path.join(self.root, rp), "w", encoding="utf-8", newline="\n") as f: f.write(text)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_no_marker_no_change(self):
        h = "<head>\n</head>"
        self.assertEqual(page_tools.add_head(h, self.root, "<p>tool</p><section class=\"tools\">"), h)

    def test_marker_adds_css_and_deferred_script_once(self):
        out = page_tools.add_head("<head>\n</head>", self.root, MAIN + MAIN)
        self.assertEqual(out.count('<link rel="stylesheet" href="/assets/tools/tools.css?v='), 1)
        self.assertEqual(out.count('<script src="/assets/tools/photo-size.js?v='), 1)
        self.assertIn(" defer></script>", out)
        self.assertTrue(out.endswith("</head>"))

    def test_version_follows_lf_bytes(self):
        a = page_tools.head_tags(self.root, MAIN)
        self.assertEqual(a, page_tools.head_tags(self.root, MAIN), "stable across builds")
        js = os.path.join(self.root, page_tools.TOOLS["photo-size"])
        with open(js, "wb") as f: f.write(b"1;\r\n")  # CRLF checkout: same served bytes, same version
        self.assertEqual(a, page_tools.head_tags(self.root, MAIN))
        with open(js, "wb") as f: f.write(b"2;\n")
        self.assertNotEqual(a, page_tools.head_tags(self.root, MAIN))

    def test_unknown_tool_stops_the_build(self):
        with self.assertRaises(SystemExit):
            page_tools.used('<section class="tool" data-tool="nope">')


if __name__ == "__main__":
    unittest.main()
