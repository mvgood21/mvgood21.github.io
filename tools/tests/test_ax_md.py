"""Tests for tools/ax_md.py (Markdown writer format for AX notes).
Run: python -m unittest discover -s tools/tests
"""
import json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import ax_md  # noqa: E402
from PIL import Image  # noqa: E402

FRONT = """---
slug: demo-note
lang: ko
type: howto
title: 데모 제목
description: 데모 설명
lead: 한 문장 답
{extra}---
"""


def doc(body, extra=""):
    return FRONT.format(extra=extra) + body


class AxMdTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.site = self.tmp.name
        os.makedirs(os.path.join(self.site, "assets", "ax"))
        Image.new("RGB", (640, 360)).save(os.path.join(self.site, "assets", "ax", "demo-note-shot1-ko.webp"))
        Image.new("RGB", (1200, 700)).save(os.path.join(self.site, "assets", "ax", "demo-note-1-ko.webp"))

    def tearDown(self):
        self.tmp.cleanup()

    def conv(self, text, series=None):
        return ax_md.convert(text, "t.md", series, self.site)[1]

    def test_hero_eyebrow_notice(self):
        out = self.conv(doc("첫 문단 `code`.\n\n## 하나 {#one}\n본문 **굵게**.\n"))
        self.assertIn('<span class="eyebrow">AX 노트 · 방법</span>', out)
        self.assertIn("<title>데모 제목 – SugarMount</title>", out)
        self.assertIn('<p class="lead">한 문장 답</p>', out)
        self.assertIn("<p>첫 문단 <code>code</code>.</p>", out)
        self.assertIn('<section aria-labelledby="one">', out)
        self.assertIn("<strong>굵게</strong>", out)
        self.assertTrue(out.rstrip().endswith("</html>"))
        self.assertIn(ax_md.NOTICE["ko"], out)
        # intro sits inside the hero, before the first section
        self.assertLess(out.index("첫 문단"), out.index("</section>"))

    def test_en_eyebrow(self):
        out = self.conv(doc("## A {#a}\nx\n").replace("lang: ko", "lang: en"))
        self.assertIn("AX notes · How-to", out)
        self.assertIn(ax_md.NOTICE["en"], out)

    def test_heading_needs_id_and_unique(self):
        with self.assertRaises(ax_md.MdError):
            self.conv(doc("## 아이디 없음\nx\n"))
        with self.assertRaises(ax_md.MdError):
            self.conv(doc("## A {#a}\nx\n## B {#a}\ny\n"))

    def test_missing_front_key(self):
        with self.assertRaises(ax_md.MdError):
            self.conv(doc("## A {#a}\nx\n").replace("lead: 한 문장 답\n", ""))

    def test_steps_with_code_and_image(self):
        body = """## 따라 하기 {#do}
:::steps
1. PowerShell을 엽니다.
   시작 단추를 누릅니다.
2. 아래 줄을 붙여 넣습니다.
```
claude --version
```
![검은 창](/assets/ax/demo-note-shot1-ko.webp "실제 출력")
:::
"""
        out = self.conv(doc(body))
        self.assertIn('<ol class="steps"><li><p>PowerShell을 엽니다. 시작 단추를 누릅니다.</p></li>', out)
        self.assertIn("<pre><code>claude --version</code></pre>", out)
        self.assertIn('width="640" height="360"', out)
        self.assertIn("<figcaption>실제 출력</figcaption>", out)
        self.assertEqual(out.count("<li>"), 2)

    def test_numbered_line_inside_code_stays_in_step(self):
        out = self.conv(doc("## A {#a}\n:::steps\n1. 이렇게 넣습니다.\n```\n1. not a step\n```\n2. 다음\n:::\n"))
        self.assertIn("<pre><code>1. not a step</code></pre>", out)
        self.assertEqual(out.count("<li>"), 2)

    def test_generated_figure_gets_class(self):
        out = self.conv(doc('## A {#a}\n![그림](/assets/ax/demo-note-1-ko.webp "캡션")\n'))
        self.assertIn('<figure class="ax-fig"><img src="/assets/ax/demo-note-1-ko.webp" width="1200" height="700"', out)

    def test_missing_image_and_alt(self):
        with self.assertRaises(ax_md.MdError):
            self.conv(doc("## A {#a}\n![x](/assets/ax/nope.webp)\n"))
        with self.assertRaises(ax_md.MdError):
            self.conv(doc("## A {#a}\n![](/assets/ax/demo-note-shot1-ko.webp)\n"))

    def test_boxes_table_lists_keys_links(self):
        body = """## A {#a}
:::box 이 편을 마치면
- 결과: 예약 작업 1개
- 시간: 20분
:::
:::warn 주의
관리자 창은 쓰지 않습니다.
:::
| 증상 | 해결 |
|---|---|
| 'irm' 오류 | PowerShell에서 다시 |

1. 하나
2. 둘

[[Ctrl+V]]로 붙이고 [1편](/ax/x/)을 봅니다. <b>는 글자로 남습니다.
"""
        out = self.conv(doc(body))
        self.assertIn('<div class="box"><p><strong>이 편을 마치면</strong></p><ul><li>결과: 예약 작업 1개</li>', out)
        self.assertIn('<div class="note note--warning"><p><strong>주의</strong></p><p>관리자 창은 쓰지 않습니다.</p></div>', out)
        self.assertIn('<div class="table-wrap"><table><thead><tr><th>증상</th><th>해결</th></tr></thead>', out)
        self.assertIn("<ol><li>하나</li><li>둘</li></ol>", out)
        self.assertIn("<kbd>Ctrl+V</kbd>", out)
        self.assertIn('<a href="/ax/x/">1편</a>', out)
        self.assertIn("&lt;b&gt;", out)

    def test_table_pipe_in_code_and_escaped(self):
        out = self.conv(doc("## A {#a}\n| 명령 | 뜻 |\n|---|---|\n| `irm x \\| iex` | a \\| b |\n| `a | b` | c |\n"))
        self.assertIn("<td><code>irm x | iex</code></td><td>a | b</td>", out)
        self.assertIn("<td><code>a | b</code></td><td>c</td>", out)

    def test_table_row_mismatch(self):
        with self.assertRaises(ax_md.MdError):
            self.conv(doc("## A {#a}\n| a | b |\n|---|---|\n| 1 |\n"))

    def test_faq_moves_after_sections_and_needs_two(self):
        body = """## A {#a}
x
:::faq
### 질문 하나?
답 하나.
### 질문 둘?
답 둘.
:::
## B {#b}
y
:::sources
기준일 2026-11-12, 출처 실행 로그.
:::
"""
        out = self.conv(doc(body))
        self.assertIn('<h2 id="faq">자주 묻는 질문</h2>', out)
        self.assertIn("<details><summary>질문 하나?</summary><div><p>답 하나.</p></div></details>", out)
        self.assertLess(out.index('id="b"'), out.index('id="faq"'))
        self.assertLess(out.index('id="faq"'), out.index('<p class="note">기준일'))
        self.assertLess(out.index('<p class="note">기준일'), out.index('class="muted"'))
        with self.assertRaises(ax_md.MdError):
            self.conv(doc("## A {#a}\n:::faq\n### 하나?\n답.\n:::\n"))

    def test_em_dash_rejected(self):
        with self.assertRaises(ax_md.MdError):
            self.conv(doc("## A {#a}\n이것 — 저것\n"))

    def test_unclosed_container_and_code(self):
        with self.assertRaises(ax_md.MdError):
            self.conv(doc("## A {#a}\n:::note\nx\n"))
        with self.assertRaises(ax_md.MdError):
            self.conv(doc("## A {#a}\n```\nx\n"))

    def test_heading_inside_code_is_not_a_section(self):
        out = self.conv(doc("## A {#a}\n```\n## not a heading\n```\n"))
        self.assertIn("<pre><code>## not a heading</code></pre>", out)

    def test_series(self):
        ser = {"id": "s", "name": {"ko": "연재", "en": "Series"},
               "parts": [{"slug": "p1", "ko": "첫 편", "en": "One"},
                         {"slug": "demo-note", "ko": "둘째 편", "en": "Two"},
                         {"slug": "p3", "ko": "셋째 편", "en": "Three"}]}
        path = os.path.join(self.site, "s.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ser, f, ensure_ascii=False)
        out = self.conv(doc("## A {#a}\nx\n", "series: s\npart: 2\n"), path)
        self.assertIn('<p class="note">연재 2/3 <span aria-hidden="true">·</span> 이전 편 <a href="/ax/p1/">첫 편</a>', out)
        self.assertIn('<strong aria-current="page">2. 둘째 편</strong>', out)
        self.assertIn('<p>다음 편: <a href="/ax/p3/">셋째 편</a></p>', out)
        with self.assertRaises(ax_md.MdError):
            self.conv(doc("## A {#a}\nx\n", "series: s\npart: 3\n"), path)
        en = self.conv(doc("## A {#a}\nx\n", "series: s\npart: 2\n").replace("lang: ko", "lang: en"), path)
        self.assertIn('href="/en/ax/p1/"', en)


if __name__ == "__main__":
    unittest.main()
