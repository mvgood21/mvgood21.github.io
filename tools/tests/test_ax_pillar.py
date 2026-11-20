import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ax_pillar  # noqa: E402


class Pillar(unittest.TestCase):
    def write(self, root, text):
        os.makedirs(os.path.join(root, ax_pillar.DIR), exist_ok=True)
        open(ax_pillar.path("topic", "android", "ko", root), "w", encoding="utf-8").write(text)

    def test_no_file_is_none(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(ax_pillar.load("topic", "android", "ko", root))

    def test_headers_and_body(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "<!-- title: T -->\r\n<!-- h1: H -->\n<!-- lead: L\n  two -->\n<!-- desc: D -->\n<section><p>x</p></section>\n")
            pl = ax_pillar.load("topic", "android", "ko", root)
            self.assertEqual((pl["title"], pl["h1"], pl["lead"], pl["desc"]), ("T", "H", "L two", "D"))
            self.assertEqual(pl["body"], "<section><p>x</p></section>")

    def test_missing_header_fails(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "<!-- title: T -->\n<!-- h1: H -->\n<p>x</p>")
            with self.assertRaises(SystemExit):
                ax_pillar.load("topic", "android", "ko", root)


if __name__ == "__main__":
    unittest.main()
