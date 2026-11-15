"""Tests for AdSense on AX notes (tools/ads.py) and its gates (tools/checks.py AD-OFF, AD-PLACEMENT, AD-JS,
AD-BUDGET-DROP, ORIGIN). Every eligibility rule R1-R7 and every placement guard has a test that fails without it.
Run: python -m unittest discover -s tools/tests
"""
import json, os, re, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import ads  # noqa: E402
import checks  # noqa: E402
import noindex  # noqa: E402

SLOTS = {"in_article": "1", "rail_left": "2", "rail_right": "3"}
NOTE, NOTE_EN = "ax/sample-note/index.html", "en/ax/sample-note/index.html"
NOINDEX = noindex.NoIndex(prefixes=("privacy/", "ax/topic/"), ax_notes=("folded",), except_=())
PARA = {"ko": "<p>" + "가나다라마바사아자차 " * 30 + "</p>", "en": "<p>" + "word " * 120 + "</p>"}  # 300 chars / 120 words


REPO = os.path.dirname(os.path.dirname(HERE))


def read(*parts):
    with open(os.path.join(REPO, *parts), encoding="utf-8") as f: return f.read()


def cfg(data, preview=False):
    with tempfile.TemporaryDirectory() as root:
        os.makedirs(os.path.join(root, "data"))
        with open(os.path.join(root, ads.FILE), "w", encoding="utf-8") as f: json.dump(data, f)
        old = os.environ.pop("AX_ADS_PREVIEW", None)
        if preview: os.environ["AX_ADS_PREVIEW"] = "1"
        try: return ads.config(root)
        finally:
            os.environ.pop("AX_ADS_PREVIEW", None)
            if old is not None: os.environ["AX_ADS_PREVIEW"] = old


def on(**kw): return cfg({"client": "ca-pub-1", "mode": "on", "slots": SLOTS, **kw})
def review(**kw): return cfg({"client": "ca-pub-1", "mode": "review", "slots": SLOTS, **kw})


def section(i, lang, paras=1):
    return f'    <section aria-labelledby="s{i}">\n      <h2 id="s{i}">H{i}</h2>\n      {PARA[lang] * paras}\n    </section>\n\n'


def note_main(lang="ko", n=6, paras=1, cta_before=None):
    """A note's <main> as build.py leaves it: hero, toc block (with .ax-side), body sections, cta, FAQ, related."""
    toc = ('<!-- build:toc --><details class="toc-inline"><summary>T</summary><ol><li><a href="#s0">H0</a></li></ol></details>'
           '<div class="ax-side"><nav class="toc" aria-labelledby="toc-h"><p id="toc-h">T</p><ol><li><a href="#s0">H0</a></li></ol></nav></div><!-- /build:toc -->')
    out = '    <section class="hero">\n      <h1>Title</h1>\n      <p class="lead">Lead</p>\n    </section>\n\n    ' + toc + "\n\n"
    for i in range(n):
        if i == cta_before:
            out += '    <!-- build:cta-mid -->\n    <aside class="ax-cta ax-cta--inline"><p>Mail <a href="mailto:a@b.c">us</a></p></aside>\n    <!-- /build:cta-mid -->\n'
        out += section(i, lang, paras)
    out += ('    <!-- build:cta -->\n    <aside class="ax-cta"><p>Q</p></aside>\n    <!-- /build:cta -->\n'
            '    <section aria-labelledby="faq">\n      <h2 id="faq">FAQ</h2>\n      <details><summary>Q</summary><p>A</p></details>\n    </section>\n'
            '    <!-- build:extra -->\n    <section aria-labelledby="ax-related-heading">\n      <h2 id="ax-related-heading">More</h2>\n'
            '      <ul><li><a href="/ax/x/">x</a></li></ul>\n    </section>\n    <!-- /build:extra -->\n')
    return out


def page_of(main, lang="ko", head=""):
    return (f'<!DOCTYPE html>\n<html lang="{lang}">\n<head>\n  <title>t</title>\n{head}</head>\n<body class="page-read">\n'
            f'  <main id="main" class="container ax-note ax-t-x">\n{main}\n  </main>\n</body>\n</html>\n')


def boxes(html_text): return re.findall(r'<div class="ad (ad-\w+)[^"]*" data-s="(\w)"></div>', html_text)


def h2_after(html_text, marker):
    """id of the first h2 after the first occurrence of marker."""
    return re.search(r'<h2 id="([^"]+)"', html_text[html_text.index(marker):]).group(1)


class Config(unittest.TestCase):
    def test_modes_and_legacy_serve(self):
        self.assertEqual(review()["mode"], "review")
        self.assertEqual(on()["mode"], "on")
        self.assertEqual(cfg({"client": "ca-pub-1", "serve": False, "slots": SLOTS})["mode"], "off")
        self.assertEqual(cfg({"client": "ca-pub-1", "serve": True, "slots": SLOTS})["mode"], "on")
        self.assertEqual(cfg({"client": "ca-pub-1", "slots": SLOTS})["mode"], "on")
        with self.assertRaises(ValueError): cfg({"client": "ca-pub-1", "mode": "maybe", "slots": SLOTS})

    def test_units_need_client_and_every_slot_review_needs_client(self):
        self.assertEqual(cfg({"client": "ca-pub-1", "mode": "on", "slots": {"in_article": "1"}})["mode"], "off")
        self.assertEqual(cfg({"client": "", "mode": "review", "slots": SLOTS})["mode"], "off")
        self.assertEqual(cfg({"client": "ca-pub-1", "mode": "review", "slots": {}})["mode"], "review")

    def test_ownership_meta_and_ads_txt_in_every_mode_with_a_client(self):
        for mode in ads.MODES:
            c = cfg({"client": "ca-pub-9", "mode": mode, "slots": SLOTS})
            self.assertEqual(ads.meta(c), '<meta name="google-adsense-account" content="ca-pub-9">')
            self.assertEqual(ads.ads_txt(c), "google.com, pub-9, DIRECT, f08c47fec0942fa0\n")
        none = cfg({"client": "", "slots": SLOTS})
        self.assertEqual(ads.meta(none), ""); self.assertIsNone(ads.ads_txt(none))

    def test_repo_config_is_review_with_unchanged_ids(self):
        c = ads.config(REPO)
        self.assertEqual(c["mode"], "review")
        self.assertEqual(c["client"], "ca-pub-8023868702717237")
        self.assertEqual(c["slots"], {"in_article": "9285164276", "rail_left": "7972082606", "rail_right": "2468474484"})
        self.assertFalse(c["reviewed_only"])  # R7 is the owner's decision, off by default


class Eligibility(unittest.TestCase):
    def test_eligible_note(self):
        self.assertIsNone(ads.eligible(on(), NOTE, note_main(), NOINDEX))
        self.assertIsNone(ads.eligible(review(), NOTE_EN, note_main("en"), NOINDEX))

    def test_r1_mode_off(self):
        self.assertEqual(ads.eligible(cfg({"client": "ca-pub-1", "mode": "off", "slots": SLOTS}), NOTE, note_main(), NOINDEX), "R1")

    def test_r2_ax_notes_only(self):
        for rp in ("index.html", "ax/index.html", "ax/topic/games/index.html", "ax/series/x/index.html",
                   "ax/page/2/index.html", "ax/topic/index.html", "ax/series/index.html", "apps/blocks/index.html",
                   "apps/blocks/how-to/index.html", "privacy/site/index.html", "about/index.html", "404.html"):
            self.assertEqual(ads.eligible(on(), rp, note_main(), NOINDEX), "R2", rp)

    def test_r3_noindex_notes(self):
        self.assertEqual(ads.eligible(on(), "ax/folded/index.html", note_main(), NOINDEX), "R3")
        self.assertEqual(ads.eligible(on(), "en/ax/folded/index.html", note_main("en"), NOINDEX), "R3")

    def test_r4_exclude(self):
        self.assertEqual(ads.eligible(on(exclude=["sample-note"]), NOTE, note_main(), NOINDEX), "R4")

    def test_r5_body_text(self):
        self.assertEqual(ads.eligible(on(), NOTE, note_main(n=4), NOINDEX), "R5")  # 1,200 chars < 1,500
        self.assertIsNone(ads.eligible(on(), NOTE, note_main(n=5), NOINDEX))     # 1,500
        self.assertEqual(ads.eligible(on(), NOTE_EN, note_main("en", n=4), NOINDEX), "R5")  # 480 words < 600
        self.assertIsNone(ads.eligible(on(min_text={"ko": 1000}), NOTE, note_main(n=4), NOINDEX))

    def test_r5_counts_body_text_only(self):
        filler = "<pre>" + "가" * 5000 + "</pre><figure>" + "가" * 5000 + "</figure><nav>" + "가" * 5000 + "</nav>" \
                 "<aside>" + "가" * 5000 + "</aside><!-- build:x -->" + "가" * 5000 + "<!-- /build:x -->"
        self.assertEqual(ads.eligible(on(), NOTE, note_main(n=4) + filler, NOINDEX), "R5")
        self.assertEqual(ads.body_size("<p>a b  c</p><code>d e</code>", "en"), 3)
        self.assertEqual(ads.body_size("<p>가 나 &amp;</p>", "ko"), 3)

    def test_r7_reviewed_only(self):
        self.assertEqual(ads.eligible(on(reviewed_only=True), NOTE, note_main(), NOINDEX), "R7")
        self.assertIsNone(ads.eligible(on(reviewed_only=True, reviewed=["sample-note"]), NOTE, note_main(), NOINDEX))
        self.assertIsNone(ads.eligible(on(reviewed=[]), NOTE, note_main(), NOINDEX))  # off by default


class Placement(unittest.TestCase):
    def placed(self, c=None, main=None, lang="ko", limit=10 ** 6):
        return ads.fit(page_of(main or note_main(lang), lang), c or on(), lang, limit)

    def test_on_places_reserved_boxes_and_deferred_loader_only(self):
        out, dropped = self.placed()
        self.assertEqual(dropped, [])
        self.assertEqual(sorted(boxes(out)), [("ad-in", "i"), ("ad-rail", "r"), ("ad-side", "s")])
        self.assertIn('<script src="/assets/ads.js?v=', out)
        self.assertIn('" defer></script>\n</head>', out)
        for bad in ("<ins", "adsbygoogle", "push(", "pagead2", "광고", "Advertisement", "<aside class=\"ad"):
            self.assertNotIn(bad, out)  # units, label and network script come from ads.js / ax.css

    def test_first_unit_before_second_body_h2_not_after_hero_or_toc(self):
        out, _ = self.placed()
        self.assertEqual(h2_after(out, "<!-- build:ad-1 -->"), "s1")
        self.assertIn('</section>\n\n    <!-- build:ad-1 -->', out)

    def test_first_unit_moves_past_the_inquiry_box(self):
        out, _ = self.placed(main=note_main(cta_before=1))
        self.assertEqual(h2_after(out, "<!-- build:ad-1 -->"), "s2")
        self.assertNotIn("<!-- /build:cta-mid -->\n    <!-- build:ad-1", out)

    def test_second_unit_only_for_long_notes_with_enough_h2(self):
        self.assertEqual([b for b in boxes(self.placed(main=note_main(n=6))[0]) if b[0] == "ad-in"], [("ad-in", "i")])
        long_ = self.placed(main=note_main(n=6, paras=2))[0]  # 3,600 chars, 6 body h2
        self.assertEqual(h2_after(long_, "<!-- build:ad-2 -->"), "s5")
        self.assertEqual(len([b for b in boxes(long_) if b[0] == "ad-in"]), 2)
        few_h2 = self.placed(main=note_main(n=4, paras=3))[0]  # 3,600 chars but 4 body h2 < 5
        self.assertNotIn("build:ad-2", few_h2)

    def test_second_unit_moves_up_past_the_inquiry_box_and_keeps_two_paragraphs_apart(self):
        out = self.placed(main=note_main(n=6, paras=2, cta_before=5))[0]
        self.assertEqual(h2_after(out, "<!-- build:ad-2 -->"), "s4")
        tight = self.placed(c=on(second_unit={"min_h2": 3}), main=note_main(n=3, paras=6, cta_before=2))[0]
        self.assertNotIn("build:ad-2", tight)  # s2 is taken by the inquiry box; s1 holds the first unit
        short = on(second_unit={"ko": 500, "min_h2": 3})
        self.assertNotIn("build:ad-2", self.placed(c=short, main=note_main(n=3))[0])  # one <p> between s1 and s2
        self.assertEqual(h2_after(self.placed(c=short, main=note_main(n=4))[0], "<!-- build:ad-2 -->"), "s3")

    def test_side_under_the_side_toc_rail_after_the_toc_block(self):
        out, _ = self.placed()
        self.assertIn('</nav><div class="ad ad-side" data-s="s"></div></div><!-- /build:toc -->', out)
        self.assertIn('<!-- /build:toc -->\n\n    <!-- build:ad-rail --><div class="ad ad-rail" data-s="r"></div>', out)

    def test_r6_drops_rail_side_second_first_in_that_order(self):
        main = note_main(n=6, paras=2)
        full = len(self.placed(main=main)[0].encode())
        base = len(page_of(main).encode())
        expect = [[], ["ad-rail"], ["ad-rail", "side"], ["ad-rail", "side", "ad-2"], ["ad-rail", "side", "ad-2", "ad-1"]]
        sizes = [full] + [len(ads.render(page_of(main), on(), "ko", list(ads.DROP_ORDER)[i:]).encode()) for i in range(1, 4)]
        for i, want in enumerate(expect):
            out, dropped = self.placed(main=main, limit=sizes[i] if i < 4 else base)
            self.assertEqual(dropped, want, i)
            self.assertLessEqual(len(out.encode()), sizes[i] if i < 4 else base)
        self.assertNotIn("ads.js", self.placed(main=main, limit=base)[0])  # nothing placed, no loader either

    def test_review_mode_loader_tag_only_and_r6(self):
        pg = page_of(note_main())
        out, dropped = ads.fit(pg, review(), "ko", 10 ** 6)
        self.assertEqual(dropped, [])
        self.assertIn('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1" '
                      'crossorigin="anonymous"></script>\n</head>', out)
        self.assertEqual(boxes(out), []); self.assertNotIn("ads.js", out)
        self.assertEqual(ads.fit(pg, review(), "ko", len(pg.encode()) + 10), (pg, ["head"]))

    def test_preview_draws_outlined_boxes_without_script(self):
        out, _ = ads.fit(page_of(note_main()), cfg({"client": "", "slots": SLOTS}, preview=True), "ko", 10 ** 6)
        self.assertIn('class="ad ad-in ad-preview"', out)
        self.assertNotIn("<script", out)

    def test_place_unplace_place_is_stable(self):
        orig = page_of(note_main(n=6, paras=2, cta_before=3))
        once = ads.fit(orig, on(), "ko", 10 ** 6)[0]
        i0, i1 = once.index("<main"), once.rindex("</main>")
        unplaced = re.sub(r'  <script src="/assets/ads.js[^\n]*\n', "", once[:i0] + ads.unplace(once[i0:i1]) + once[i1:])
        self.assertEqual(unplaced, orig)  # the next build starts from the same <main>
        self.assertEqual(ads.fit(unplaced, on(), "ko", 10 ** 6)[0], once)

    def test_clear_blocks_keeps_legacy_markers_unless_on(self):
        main = "<p>a</p>\n\n    <!-- build:ad-1 --><aside class=\"ad\">x</aside><!-- /build:ad-1 -->\n\n    <section>"
        self.assertEqual(ads.clear_blocks(main, review()), "<p>a</p>\n\n    <!-- build:ad-1 --><!-- /build:ad-1 -->\n\n    <section>")
        self.assertEqual(ads.clear_blocks(main, on()), "<p>a</p>\n\n    <section>")


class Gates(unittest.TestCase):
    def run_page(self, html_text, c, rp=NOTE):
        report = checks.Report()
        checks.check_ads_page(checks.Page(None, rp, html_text), report, c, NOINDEX)
        return report

    def codes(self, report, level="error"):
        return [i.code for i in report.issues if i.level == level]

    def test_placed_page_passes(self):
        for lang, rp in (("ko", NOTE), ("en", NOTE_EN)):
            out, _ = ads.fit(page_of(note_main(lang, n=6, paras=2), lang), on(), lang, 10 ** 6)
            r = self.run_page(out, on(), rp)
            self.assertEqual(r.issues, [], [str(i) for i in r.issues])

    def test_review_page_passes_and_off_page_passes(self):
        out, _ = ads.fit(page_of(note_main()), review(), "ko", 10 ** 6)
        self.assertEqual(self.run_page(out, review()).issues, [])
        off = cfg({"client": "ca-pub-1", "mode": "off", "slots": SLOTS})
        self.assertEqual(self.run_page(page_of(note_main()), off).issues, [])

    def test_ad_off_means_zero_traces(self):
        off = cfg({"client": "ca-pub-1", "mode": "off", "slots": SLOTS})
        for trace in ('<div class="ad ad-in" data-s="i"></div>', '<ins class="adsbygoogle"></ins>',
                      '<ins class="kakao_ad_area"></ins>', '<script src="/assets/ads.js?v=1" defer></script>',
                      '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1"></script>',
                      '<script>(adsbygoogle=window.adsbygoogle||[]).push({})</script>'):
            for rp in (NOTE, "index.html", "privacy/site/index.html"):
                self.assertEqual(self.codes(self.run_page(page_of(note_main() + trace), off, rp)), ["AD-OFF"], (trace, rp))

    def test_ads_on_a_page_that_may_not_carry_them(self):
        out, _ = ads.fit(page_of(note_main()), on(), "ko", 10 ** 6)
        for rp in ("ax/index.html", "ax/topic/games/index.html", "apps/blocks/index.html", "ax/folded/index.html"):
            self.assertIn("AD-PLACEMENT", self.codes(self.run_page(out, on(), rp)), rp)
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(out, on(exclude=["sample-note"]))))
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(out, on(reviewed_only=True))))

    def test_box_neighbours(self):
        box = '<div class="ad ad-in" data-s="i"></div>\n'
        js = '  <script src="/assets/ads.js?v=1" defer></script>\n'
        m = note_main(n=6, cta_before=3)
        no_toc = re.sub(r"<!-- build:toc -->.*?<!-- /build:toc -->", "", m)
        no_cta = re.sub(r"    <!-- build:cta -->.*?<!-- /build:cta -->\n", "", m, flags=re.S)
        no_faq = re.sub(r'    <section aria-labelledby="faq">.*?</section>\n', "", no_cta, flags=re.S)
        series = no_cta.replace('    <section aria-labelledby="faq">', '    <nav class="box" aria-label="연재 목차"><ol><li>a</li></ol></nav>\n'
                                                                       '    <section aria-labelledby="faq">', 1)
        s = lambda i: f'    <section aria-labelledby="s{i}">'
        for where, base, before in (("after hero", no_toc, s(0)), ("after toc", m, s(0)), ("before cta-mid", m, "    <!-- build:cta-mid -->"),
                                    ("after cta-mid", m, s(3)), ("before the closing inquiry box", m, "    <!-- build:cta -->"),
                                    ("before FAQ", no_cta, '    <section aria-labelledby="faq">'),
                                    ("before related", no_faq, "    <!-- build:extra -->"),
                                    ("before series box", series, '    <nav class="box"')):
            self.assertEqual(base.count(before), 1, where)
            bad = base.replace(before, box + before, 1)
            self.assertIn("AD-PLACEMENT", self.codes(self.run_page(page_of(bad, head=js), on())), where)
        good = m.replace('    <section aria-labelledby="s1">', box + '    <section aria-labelledby="s1">', 1)
        self.assertEqual(self.codes(self.run_page(page_of(good, head=js), on())), [])

    def test_two_paragraphs_between_units_and_at_most_four_boxes(self):
        box = '<div class="ad ad-in" data-s="i"></div>\n'
        js = '  <script src="/assets/ads.js?v=1" defer></script>\n'
        m = note_main(n=6)
        near = m.replace('    <section aria-labelledby="s1">', box + '    <section aria-labelledby="s1">', 1)
        near = near.replace('    <section aria-labelledby="s2">', box + '    <section aria-labelledby="s2">', 1)
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(page_of(near, head=js), on())))
        far = m.replace('    <section aria-labelledby="s1">', box + '    <section aria-labelledby="s1">', 1)
        far = far.replace('    <section aria-labelledby="s3">', box + '    <section aria-labelledby="s3">', 1)
        self.assertEqual(self.codes(self.run_page(page_of(far, head=js), on())), [])
        three = far.replace('    <section aria-labelledby="s5">', box + '    <section aria-labelledby="s5">', 1)
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(page_of(three, head=js), on())))

    def test_static_units_network_script_and_missing_loader(self):
        out, _ = ads.fit(page_of(note_main()), on(), "ko", 10 ** 6)
        with_ins = out.replace('data-s="i"></div>', 'data-s="i"><ins class="adsbygoogle"></ins></div>', 1)
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(with_ins, on())))
        net = out.replace("</head>", f"  {ads.head_tag(on())}\n</head>")
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(net, on())))
        no_js = re.sub(r'  <script src="/assets/ads.js[^\n]*\n', "", out)
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(no_js, on())))
        no_defer = out.replace('" defer></script>', '"></script>')
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(no_defer, on())))

    def test_loader_without_boxes_side_rail_and_unknown_boxes(self):
        out, _ = ads.fit(page_of(note_main()), on(), "ko", 10 ** 6)
        no_boxes = re.sub(r'<div class="ad [^"]*" data-s="\w"></div>', "", out)
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(no_boxes, on())))
        side_out = out.replace('<div class="ad ad-side" data-s="s"></div></div>', '</div><div class="ad ad-side" data-s="s"></div>')
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(side_out, on())))
        rail_in = out.replace('<div class="ad ad-rail" data-s="r"></div>', "").replace(
            '<h2 id="s4">H4</h2>', '<h2 id="s4">H4</h2><div class="ad ad-rail" data-s="r"></div>')
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(rail_in, on())))
        odd = out.replace('class="ad ad-rail"', 'class="ad ad-banner"')
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(odd, on())))

    def test_label_wording_lives_in_ax_css(self):
        r = checks.Report()
        css = read("assets", "ax.css")
        checks.check_ad_labels(css, r)
        self.assertEqual(r.issues, [])
        checks.check_ad_labels(css.replace('content:"Advertisements"', 'content:"Advertisement"'), r)
        self.assertEqual(self.codes(r), ["AD-PLACEMENT"])

    def test_review_mode_allows_the_loader_tag_only(self):
        out, _ = ads.fit(page_of(note_main()), on(), "ko", 10 ** 6)
        self.assertIn("AD-PLACEMENT", self.codes(self.run_page(out, review())))

    def test_budget_drop_is_a_warning(self):
        main = note_main(n=6, paras=2)
        out, dropped = ads.fit(page_of(main), on(), "ko", len(page_of(main).encode()) + 200)
        self.assertTrue(dropped)
        r = self.run_page(out, on())
        self.assertEqual(self.codes(r), [])
        self.assertEqual(self.codes(r, "warning"), ["AD-BUDGET-DROP"])
        self.assertEqual(self.codes(self.run_page(page_of(main), review()), "warning"), ["AD-BUDGET-DROP"])

    def test_ads_js_names_the_configured_ids(self):
        r = checks.Report()
        checks.check_ads_js('C="ca-pub-1",S={i:"1",r:"2",s:"3"}', on(), r)
        self.assertEqual(r.issues, [])
        checks.check_ads_js('C="ca-pub-1",S={i:"1",r:"2",s:"4"}', on(), r)
        checks.check_ads_js(None, on(), r)
        self.assertEqual(self.codes(r), ["AD-JS", "AD-JS"])
        r = checks.Report()
        checks.check_ads_js(read(ads.JS), ads.config(REPO), r)
        self.assertEqual(r.issues, [])

    def test_origin_allows_the_network_script_in_review_mode_only(self):
        pg = page_of(note_main(), head=f"  {ads.head_tag(on())}\n")
        with tempfile.TemporaryDirectory() as root:
            site = checks.Site(root, {})
            old = checks.ADS_CFG
            try:
                for c, want in ((review(), []), (on(), ["ORIGIN"])):
                    checks.ADS_CFG = c
                    for rp, w in ((NOTE, want), ("ax/topic/games/index.html", ["ORIGIN"])):
                        r = checks.Report()
                        checks.check_page_budget(checks.Page(site, rp, pg), r, False)
                        self.assertEqual([i.code for i in r.issues if i.code == "ORIGIN"], w, (c["mode"], rp))
            finally:
                checks.ADS_CFG = old


class Loader(unittest.TestCase):
    def test_loader_waits_for_interaction_and_skips_hidden_boxes(self):
        js = read(ads.JS)
        self.assertIn('["scroll","pointerdown","keydown"]', js)
        self.assertIn("IntersectionObserver", js)
        self.assertIn('rootMargin:"800px 0px"', js)
        self.assertIn("!b.offsetWidth", js)  # display:none (side, rail on narrow screens) → no <ins>, no push
        self.assertNotIn("data-ad-format", js)  # fixed CSS size, never auto/full-width (CLS)
        self.assertLessEqual(len(js.encode()) + 192, checks.BUDGET["js"])  # + the menu script on every page


if __name__ == "__main__":
    unittest.main()
