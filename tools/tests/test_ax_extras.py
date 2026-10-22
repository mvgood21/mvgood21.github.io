"""Tests for tools/ax_extras.py (AX hub search, note types, inquiry boxes, figures).
Run: python -m unittest discover -s tools/tests
"""
import json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import ax_extras  # noqa: E402

NOTE = """    <section class="hero">
      <span class="eyebrow">AX 노트 · 사고 기록</span>
      <h1>t</h1>
    </section>

    <section aria-labelledby="a">
      <h2 id="a">A</h2>
      <figure class="ax-fig"><img src="/assets/ax/x-1-ko.webp" alt="a"></figure>
    </section>

    <section aria-labelledby="b">
      <h2 id="b">B</h2>
      <figure class="ax-fig"><img src="/assets/ax/x-1-ko.webp" alt="a"></figure>
    </section>

    <section aria-labelledby="c">
      <h2 id="c">C</h2>
      <img src="/assets/apps/y.webp" alt="">
    </section>

    <section aria-labelledby="faq">
      <h2 id="faq">FAQ</h2>
    </section>
"""


class AxExtrasTest(unittest.TestCase):
    def test_note_type_from_eyebrow(self):
        self.assertEqual(ax_extras.note_type(NOTE, "ko"), "사고 기록")
        self.assertEqual(ax_extras.note_type('<span class="eyebrow">AX 노트</span>', "ko"), "")

    def test_figures_only_ax_assets_once(self):
        self.assertEqual(ax_extras.figures(NOTE), ["/assets/ax/x-1-ko.webp"])

    def test_middle_h2_is_a_body_section_line_start(self):
        at = ax_extras.middle_h2(NOTE)
        self.assertEqual(NOTE[at:].lstrip("\n").lstrip().split(">")[0], '<section aria-labelledby="b"')

    def test_middle_h2_needs_three_body_sections(self):
        short = NOTE.split('<section aria-labelledby="c">')[0]
        self.assertIsNone(ax_extras.middle_h2(short))

    def test_search_json_escapes_html(self):
        rows = json.loads(ax_extras.search_json([("/ax/x/", "a <b> 'c'", "d", "k", "y", "p")]))
        self.assertEqual(rows[0]["t"], "a &lt;b&gt; &#x27;c&#x27;")

    def test_cta_subject_names_the_note(self):
        html_ = ax_extras.cta_end("en", "a@b.c", "My note")
        self.assertIn("subject=%5BAX%20notes%5D%20My%20note", html_)


if __name__ == "__main__":
    unittest.main()
