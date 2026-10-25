"""Gate tests for tools/checks.py. Each test breaks one rule in a valid fixture site and expects that gate's code;
deleting the guard in checks.py makes the test fail. Run: python -m unittest discover -s tools/tests
"""
import json, os, shutil, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import checks  # noqa: E402
from fixture_site import SITE, good_site, webp  # noqa: E402

EMPTY = tempfile.mkdtemp(prefix="checks-empty-")


def tearDownModule():
    shutil.rmtree(EMPTY, ignore_errors=True)


def run(files):
    return checks.run(EMPTY, outputs=files)


class Base(unittest.TestCase):
    baseline = None

    @classmethod
    def setUpClass(cls):
        if Base.baseline is None:
            Base.baseline = run(good_site())

    def files(self):
        return good_site()

    def edit(self, files, relpath, old, new, count=1):
        text = files[relpath]
        self.assertIn(old, text, f"fixture drift: {old!r} not in {relpath}")
        files[relpath] = text.replace(old, new, count)
        return files

    def assertGate(self, files, code, level="error"):
        self.assertNotIn(code, Base.baseline.codes(level), f"{code} already fires on the valid fixture")
        rep = run(files)
        self.assertIn(code, rep.codes(level), f"{code} did not fire; got {sorted(rep.codes())}")
        return rep


class Baseline(Base):
    def test_valid_fixture_has_no_errors(self):
        self.assertEqual([str(i) for i in Base.baseline.errors], [])

    def test_runs_against_files_on_disk(self):
        d = tempfile.mkdtemp(prefix="checks-disk-")
        try:
            for rp, v in good_site().items():
                full = os.path.join(d, rp)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "wb") as f:
                    f.write(v if isinstance(v, bytes) else v.encode("utf-8"))
            for skipped in ("tools/tests/index.html", "assets/x/index.html", "data/index.html", ".git/index.html"):
                os.makedirs(os.path.join(d, os.path.dirname(skipped)), exist_ok=True)
                with open(os.path.join(d, skipped), "w", encoding="utf-8") as f:
                    f.write("<h1>not a page</h1><h1>two</h1>")  # would fail H1-COUNT if it were scanned
            rep = checks.run(d)
            self.assertEqual([str(i) for i in rep.errors], [])
            os.remove(os.path.join(d, "apps", "foo", "task", "index.html"))
            self.assertIn("LINK-BROKEN", checks.run(d).codes("error"))
        finally:
            shutil.rmtree(d, ignore_errors=True)


class StructuredData(Base):
    def test_json_parse(self):
        f = self.edit(self.files(), "apps/foo/index.html", '"@type": "BreadcrumbList"', '"@type": "BreadcrumbList",,')
        self.assertGate(f, "SD-JSON")

    def test_aggregate_rating(self):
        f = self.edit(self.files(), "apps/foo/index.html", '"applicationCategory"', '"aggregateRating": {"ratingValue": 5}, "applicationCategory"')
        self.assertGate(f, "SD-FORBIDDEN")

    def test_howto(self):
        f = self.edit(self.files(), "apps/foo/task/index.html", '"@type": "Article"', '"@type": "HowTo"')
        self.assertGate(f, "SD-FORBIDDEN")

    def test_breadcrumb_short(self):
        f = self.files()
        f = self.edit(f, "privacy/index.html", '{"@type": "ListItem", "position": 1, "name": "SugarMount", "item": "https://mvgood21.github.io/"}, ', "")
        self.assertGate(f, "SD-CRUMB-SHORT")

    def test_breadcrumb_home_name(self):
        f = self.edit(self.files(), "apps/foo/index.html", '"position": 1, "name": "SugarMount"', '"position": 1, "name": "홈"')
        self.assertGate(f, "SD-CRUMB-HOME")

    def test_article_date_without_timezone(self):
        f = self.edit(self.files(), "apps/foo/task/index.html", '"dateModified": "2026-10-05T09:00:00+09:00"', '"dateModified": "2026-10-05"')
        self.assertGate(f, "SD-ARTICLE-DATE")

    def test_article_date_missing(self):
        f = self.edit(self.files(), "apps/foo/task/index.html", ', "dateModified": "2026-10-05T09:00:00+09:00"', "")
        self.assertGate(f, "SD-ARTICLE-DATE")

    def test_date_format_rule(self):
        f = self.edit(self.files(), "apps/foo/task/index.html", '"2026-10-05T09:00:00+09:00"', '"2026-10-05T00:00:00Z"')
        self.assertGate(f, "SD-DATE-FORMAT")

    def test_date_matches_content_dates(self):
        f = self.edit(self.files(), "apps/foo/task/index.html", '"datePublished": "2026-10-03T09:00:00+09:00"', '"datePublished": "2026-09-30T09:00:00+09:00"')
        self.assertGate(f, "SD-DATE-MISMATCH")

    def test_download_url(self):
        f = self.edit(self.files(), "apps/foo/index.html", '"installUrl"', '"downloadUrl": "https://play.google.com/x", "installUrl"')
        self.assertGate(f, "SD-APP-DOWNLOADURL")

    def test_app_required(self):
        f = self.edit(self.files(), "apps/foo/index.html", '"operatingSystem": "Android 8.0 이상", ', "")
        self.assertGate(f, "SD-APP-REQUIRED")

    def test_app_url_absolute(self):
        f = self.edit(self.files(), "apps/foo/index.html", '#app", "name": "Foo 앱", "url": "https://mvgood21.github.io/apps/foo/"',
                      '#app", "name": "Foo 앱", "url": "/apps/foo/"')
        self.assertGate(f, "SD-APP-URL")

    def test_app_screenshot_needs_size(self):
        f = self.edit(self.files(), "apps/foo/index.html", ', "width": 360, "height": 780}', "}")
        self.assertGate(f, "SD-APP-SHOT")

    def test_app_screenshot_plain_url(self):
        f = self.edit(self.files(), "apps/foo/index.html",
                      '{"@type": "ImageObject", "url": "https://mvgood21.github.io/assets/apps/foo/shot1-ko.webp", "width": 360, "height": 780}',
                      '"https://mvgood21.github.io/assets/apps/foo/shot1-ko.webp"')
        self.assertGate(f, "SD-APP-SHOT")

    def test_app_description_length(self):
        f = self.edit(self.files(), "apps/foo/index.html", '"Foo는 한 가지 일을 합니다."', json.dumps("가" * 161))
        self.assertGate(f, "SD-APP-DESC")

    def test_image_file_exists(self):
        f = self.files()
        del f["assets/apps/foo/icon.png"]
        self.assertGate(f, "SD-IMAGE-MISSING")

    def test_primary_image_equals_og(self):
        f = self.edit(self.files(), "apps/foo/index.html", 'og:image" content="https://mvgood21.github.io/assets/og/app-foo-ko.png"',
                      'og:image" content="https://mvgood21.github.io/assets/og.png"')
        self.assertGate(f, "SD-PRIMARY-IMAGE")

    def test_org_full_node_outside_home(self):
        f = self.edit(self.files(), "apps/foo/index.html", '"author": {"@id": "https://mvgood21.github.io/#org"}',
                      '"author": {"@type": "Organization", "@id": "https://mvgood21.github.io/#org", "name": "SugarMount", '
                      '"url": "https://mvgood21.github.io/", "email": "sugarmount21@gmail.com"}')
        self.assertGate(f, "SD-ORG-FULL")

    def test_org_alternate_name_no_handle(self):
        f = self.edit(self.files(), "index.html", '"alternateName": ["슈가마운트"]', '"alternateName": ["simpest", "슈가마운트"]')
        self.assertGate(f, "SD-ORG-ALTNAME")

    def test_org_single_url(self):
        f = self.edit(self.files(), "apps/foo/index.html", '"author": {"@id": "https://mvgood21.github.io/#org"}',
                      '"author": {"@type": "Organization", "@id": "https://mvgood21.github.io/#org", "url": "https://mvgood21.github.io/about/"}')
        self.assertGate(f, "SD-ORG-URL")

    def test_website_full_node_only_on_ko_home(self):
        f = self.edit(self.files(), "en/index.html", '"isPartOf": {"@id": "https://mvgood21.github.io/#website"}',
                      '"isPartOf": {"@type": "WebSite", "@id": "https://mvgood21.github.io/#website", "name": "SugarMount"}')
        self.assertGate(f, "SD-WEBSITE-FULL")

    def test_person_forbidden(self):
        f = self.edit(self.files(), "apps/foo/task/index.html", '"author": {"@id": "https://mvgood21.github.io/#org"}',
                      '"author": {"@type": "Person", "name": "X"}')
        self.assertGate(f, "SD-FORBIDDEN")


class Markup(Base):
    def test_heading_outside_main(self):
        f = self.edit(self.files(), "apps/foo/index.html", '<footer><p class="footer-title">SugarMount</p>', '<footer><h2>SugarMount</h2>')
        self.assertGate(f, "HEADING-OUTSIDE-MAIN")

    def test_badge_in_heading(self):
        f = self.edit(self.files(), "apps/index.html", '<h2>Photo</h2>', '<h2>Photo <span class="badge">new</span></h2>')
        self.assertGate(f, "HEADING-NONTEXT")

    def test_img_in_heading(self):
        f = self.edit(self.files(), "apps/index.html", '<h2>Photo</h2>', '<h2><img src="/assets/og.png" width="1" height="1" alt="">Photo</h2>')
        self.assertGate(f, "HEADING-NONTEXT")

    def test_one_h1(self):
        f = self.edit(self.files(), "apps/foo/task/index.html", '<h2 id="one">One</h2>', '<h1>One</h1>')
        self.assertGate(f, "H1-COUNT")

    def test_data_app_only_on_main(self):
        f = self.edit(self.files(), "apps/foo/index.html", "<body>", '<body data-app="foo">')
        self.assertGate(f, "DATA-APP")

    def test_data_app_demo_page_inside_main_only(self):
        f = self.files()
        f["design/index.html"] = f["apps/foo/index.html"].replace("</main>", '<p data-app="foo">x</p></main>', 1)
        self.assertFalse([i for i in run(f).errors if i.code == "DATA-APP" and i.path == "design/index.html"])
        f["design/index.html"] = f["design/index.html"].replace("<body>", '<body data-app="foo">', 1)
        self.assertTrue([i for i in run(f).errors if i.code == "DATA-APP" and i.path == "design/index.html"])
        f["apps/foo/index.html"] = f["apps/foo/index.html"].replace("</main>", '<p data-app="foo">x</p></main>', 1)
        self.assertTrue([i for i in run(f).errors if i.code == "DATA-APP" and i.path == "apps/foo/index.html"])

    def test_data_app_menu_tile_allowed(self):
        f = self.edit(self.files(), "apps/foo/index.html", "<nav><a", '<nav><a class="app-tile" data-app="foo" href="/apps/foo/">Foo 앱</a> <a')
        self.assertNotIn("DATA-APP", run(f).codes())

    def test_view_transition_name_unique(self):
        f = self.edit(self.files(), "apps/index.html", '<h2>Photo</h2>',
                      '<h2>Photo</h2><p style="view-transition-name: app-foo">a</p><p style="view-transition-name:app-foo">b</p>')
        self.assertGate(f, "VT-NAME-DUP")

    def test_popover_without_aria_expanded(self):
        f = self.edit(self.files(), "apps/index.html", '<h2>Photo</h2>',
                      '<h2>Photo</h2><button popovertarget="m" aria-expanded="false">menu</button><div id="m" popover>x</div>')
        self.assertGate(f, "POPOVER-EXPANDED")

    def test_toc_h2_need_ids(self):
        f = self.edit(self.files(), "apps/foo/task/index.html", '<h2 id="two">Two</h2>', "<h2>Two</h2>")
        self.assertGate(f, "TOC-H2-ID")

    def test_duplicate_id(self):
        f = self.edit(self.files(), "apps/foo/task/index.html", '<h2 id="two">', '<h2 id="one">')
        self.assertGate(f, "DUP-ID")


class Links(Base):
    def test_broken_internal_link(self):
        f = self.edit(self.files(), "apps/index.html", 'href="/apps/foo/task/"', 'href="/apps/foo/missing/"')
        self.assertGate(f, "LINK-BROKEN")

    def test_broken_image(self):
        f = self.edit(self.files(), "apps/foo/index.html", "shot1-ko.webp\" width", "shot9.webp\" width")
        self.assertGate(f, "LINK-BROKEN")

    def test_trailing_slash(self):
        f = self.edit(self.files(), "apps/index.html", 'href="/apps/foo/task/"', 'href="/apps/foo/task"')
        self.assertGate(f, "LINK-FORMAT")

    def test_no_index_html_links(self):
        f = self.edit(self.files(), "apps/index.html", 'href="/apps/foo/task/"', 'href="/apps/foo/task/index.html"')
        self.assertGate(f, "LINK-FORMAT")

    def test_relative_page_links(self):
        f = self.edit(self.files(), "apps/index.html", 'href="/apps/foo/task/"', 'href="foo/task/"')
        self.assertGate(f, "LINK-FORMAT")

    def test_fragment_on_same_page(self):
        f = self.edit(self.files(), "apps/foo/task/index.html", 'href="#one"', 'href="#nope"')
        self.assertGate(f, "LINK-FRAGMENT")

    def test_fragment_on_other_page(self):
        f = self.edit(self.files(), "index.html", 'href="/apps/foo/">', 'href="/apps/#video">')
        self.assertGate(f, "LINK-FRAGMENT")

    def test_fragment_on_other_page_ok(self):
        f = self.edit(self.files(), "index.html", 'href="/apps/foo/">', 'href="/apps/#photo">')
        self.assertNotIn("LINK-FRAGMENT", run(f).codes())

    def test_anchor_text_one_url(self):
        f = self.edit(self.files(), "apps/foo/index.html", 'Foo 개인정보처리방침</a>', '앱</a>')
        self.assertGate(f, "ANCHOR-DUP")

    def test_anchor_mailto_subject_same_mailbox(self):
        """mailto:a and mailto:a?subject=… are one destination; two different addresses are not."""
        def dup(extra):
            f = self.edit(self.files(), "apps/foo/index.html", "</main>", extra + "</main>")
            return "ANCHOR-DUP" in run(f).codes("error")
        self.assertFalse(dup('<p><a href="mailto:a@example.com">mail</a> <a href="mailto:a@example.com?subject=x">mail</a></p>'))
        self.assertTrue(dup('<p><a href="mailto:a@example.com">mail</a> <a href="mailto:b@example.com">mail</a></p>'))

    def test_nofollow(self):
        f = self.edit(self.files(), "apps/foo/index.html", 'rel="noopener"', 'rel="noopener nofollow"')
        self.assertGate(f, "NOFOLLOW")

    def test_js_link(self):
        f = self.edit(self.files(), "apps/index.html", "<h2>Photo</h2>", '<h2>Photo</h2><span onclick="go()">go</span>')
        self.assertGate(f, "JS-LINK")

    def test_nosourceinfo(self):
        f = self.edit(self.files(), "apps/index.html", '<meta charset="utf-8">', '<meta charset="utf-8"><meta name="robots" content="nosourceinfo">')
        self.assertGate(f, "NOSOURCEINFO")

    def test_orphan(self):
        f = self.files()
        for rp in ("apps/index.html", "apps/foo/index.html", "privacy/index.html"):
            f = self.edit(f, rp, 'href="/privacy/foo/"', 'href="/privacy/"')
        rep = self.assertGate(f, "ORPHAN")
        self.assertEqual({i.path for i in rep.errors if i.code == "ORPHAN"}, {"privacy/foo/index.html"})

    def test_language_switch_does_not_count_as_inbound(self):
        f = self.files()
        for rp in ("apps/index.html", "apps/foo/index.html", "privacy/index.html"):
            f = self.edit(f, rp, 'href="/privacy/foo/"', 'href="/privacy/"')
        self.assertIn('href="/privacy/foo/"', f["en/privacy/foo/index.html"])  # the en twin still links it
        self.assertIn("ORPHAN", run(f).codes("error"))

    def test_article_needs_two_inbound(self):
        f = self.edit(self.files(), "apps/index.html", '<li><a href="/apps/foo/task/">갤럭시에서 Foo 하는 법</a></li>', "")
        rep = self.assertGate(f, "ORPHAN")
        self.assertTrue(any(i.path == "apps/foo/task/index.html" for i in rep.errors if i.code == "ORPHAN"))


class HeadRules(Base):
    def test_noindex_needs_meta(self):
        f = self.edit(self.files(), "404.html", '<meta name="robots" content="noindex">', "")
        self.assertGate(f, "NOINDEX-MISSING")

    def test_noindex_no_canonical(self):
        f = self.edit(self.files(), "404.html", '<meta charset="utf-8">', '<meta charset="utf-8"><link rel="canonical" href="https://mvgood21.github.io/404.html">')
        self.assertGate(f, "NOINDEX-CANONICAL")

    def test_noindex_no_hreflang(self):
        f = self.edit(self.files(), "404.html", '<meta charset="utf-8">', '<meta charset="utf-8"><link rel="alternate" hreflang="en" href="https://mvgood21.github.io/en/">')
        self.assertGate(f, "NOINDEX-HREFLANG")

    def test_noindex_no_og_url(self):
        f = self.edit(self.files(), "404.html", '<meta charset="utf-8">', '<meta charset="utf-8"><meta property="og:url" content="https://mvgood21.github.io/404.html">')
        self.assertGate(f, "NOINDEX-OGURL")

    def test_design_page_is_noindex(self):
        f = self.files()
        f["design/index.html"] = f["404.html"].replace('<meta name="robots" content="noindex">', "")
        self.assertGate(f, "NOINDEX-MISSING")

    def test_indexable_page_without_noindex(self):
        f = self.edit(self.files(), "apps/index.html", '<meta charset="utf-8">', '<meta charset="utf-8"><meta name="robots" content="noindex">')
        self.assertGate(f, "INDEX-NOINDEX")

    def test_canonical_self(self):
        f = self.edit(self.files(), "apps/index.html", 'rel="canonical" href="https://mvgood21.github.io/apps/"', 'rel="canonical" href="https://mvgood21.github.io/"')
        self.assertGate(f, "CANONICAL")

    def test_hreflang_target_exists(self):
        f = self.edit(self.files(), "apps/index.html", 'hreflang="en" href="https://mvgood21.github.io/en/apps/"', 'hreflang="en" href="https://mvgood21.github.io/en/apps/x/"')
        self.assertGate(f, "HREFLANG-TARGET")

    def test_hreflang_needed_when_counterpart_exists(self):
        f = self.edit(self.files(), "apps/index.html", '<link rel="alternate" hreflang="x-default" href="https://mvgood21.github.io/apps/">', "")
        self.assertGate(f, "HREFLANG-MISSING")

    def test_no_hreflang_without_counterpart(self):
        f = self.files()
        del f["en/apps/foo/task/index.html"]
        f = self.edit(f, "en/apps/index.html", '<li><a href="/en/apps/foo/task/">How to foo on a Galaxy phone</a></li>', "")
        f = self.edit(f, "en/apps/foo/index.html", '<li><a href="/en/apps/foo/task/">How to foo on a Galaxy phone</a></li>', "")
        rep = self.assertGate(f, "HREFLANG-NO-COUNTERPART")
        self.assertIn("OGLOCALE-ALT", rep.codes("error"))


class Feeds(Base):
    def test_robots_one_agent_group(self):
        f = self.files(); f["robots.txt"] += "User-agent: GPTBot\nAllow: /\n"
        self.assertGate(f, "ROBOTS-AGENTS")

    def test_robots_disallow(self):
        f = self.edit(self.files(), "robots.txt", "Disallow: /data/\n", "")
        self.assertGate(f, "ROBOTS-DISALLOW")

    def test_robots_sitemap_only(self):
        f = self.files(); f["robots.txt"] += f"Sitemap: {SITE}/rss.xml\n"
        self.assertGate(f, "ROBOTS-SITEMAP")

    def test_sitemap_no_noindex(self):
        f = self.edit(self.files(), "sitemap.xml", "</urlset>", f"<url><loc>{SITE}/404.html</loc><lastmod>2026-10-05</lastmod></url></urlset>")
        self.assertGate(f, "SITEMAP-NOINDEX")

    def test_sitemap_lastmod_from_content_dates(self):
        f = self.edit(self.files(), "sitemap.xml", "<lastmod>2026-10-05</lastmod>", "<lastmod>2026-10-18</lastmod>")
        self.assertGate(f, "SITEMAP-LASTMOD")

    def test_sitemap_lists_every_indexable_page(self):
        f = self.files()
        start = f["sitemap.xml"].index(f"<url>\n<loc>{SITE}/apps/foo/task/</loc>")
        end = f["sitemap.xml"].index("</url>", start) + len("</url>")
        f["sitemap.xml"] = f["sitemap.xml"][:start] + f["sitemap.xml"][end:]
        self.assertGate(f, "SITEMAP-MISSING-PAGE")

    def test_sitemap_hreflang_matches_page(self):
        f = self.edit(self.files(), "sitemap.xml", f'<xhtml:link rel="alternate" hreflang="x-default" href="{SITE}/apps/"/>', "")
        self.assertGate(f, "SITEMAP-HREFLANG")

    def test_dates_entry_for_every_listed_page(self):
        f = self.files()
        d = json.loads(f["data/content-dates.json"]); del d["apps/index.html"]
        f["data/content-dates.json"] = json.dumps(d)
        self.assertGate(f, "DATES-MISSING")

    def test_llms_no_noindex(self):
        f = self.files(); f["llms.txt"] += f"- [design]({SITE}/design/)\n"
        self.assertGate(f, "LLMS-NOINDEX")

    def test_rss_exists(self):
        f = self.files(); del f["en/rss.xml"]
        self.assertGate(f, "RSS-MISSING")

    def test_rss_size(self):
        f = self.edit(self.files(), "rss.xml", "<description>d</description>", "<description>" + "d" * 10_000_000 + "</description>")
        self.assertGate(f, "RSS-SIZE")

    def test_rss_not_empty(self):
        f = self.files()
        s = f["rss.xml"]; f["rss.xml"] = s[:s.index("<item>")] + "</channel></rss>\n"
        self.assertGate(f, "RSS-EMPTY")

    def test_rss_absolute_urls(self):
        f = self.edit(self.files(), "rss.xml", f'href="{SITE}/apps/foo/"', 'href="/apps/foo/"')
        self.assertGate(f, "RSS-RELATIVE")

    def test_rss_fragment_absolute(self):
        f = self.edit(self.files(), "rss.xml", f'href="{SITE}/apps/foo/task/#three"', 'href="#three"')
        self.assertGate(f, "RSS-RELATIVE")

    def test_rss_full_body(self):
        f = self.files()
        s = f["rss.xml"]; a = s.index("<description><![CDATA["); b = s.index("]]></description>", a)
        f["rss.xml"] = s[:a] + "<description>short summary</description>" + s[b + len("]]></description>"):]
        self.assertGate(f, "RSS-BODY")

    def test_rss_pubdate_is_published(self):
        f = self.edit(self.files(), "rss.xml", "Sat, 03 Oct 2026", "Mon, 05 Oct 2026")
        self.assertGate(f, "RSS-PUBDATE")

    def test_rss_order(self):
        f = self.files()
        d = json.loads(f["data/content-dates.json"]); d["apps/foo/task/index.html"]["published"] = "2026-09-01"
        f["data/content-dates.json"] = json.dumps(d)
        f = self.edit(f, "apps/foo/task/index.html", '"datePublished": "2026-10-03T09:00:00+09:00"', '"datePublished": "2026-09-01T09:00:00+09:00"')
        f = self.edit(f, "rss.xml", "Sat, 03 Oct 2026", "Tue, 01 Sep 2026")
        self.assertGate(f, "RSS-ORDER")

    def test_rss_no_noindex_or_policy(self):
        f = self.edit(self.files(), "rss.xml", f"<link>{SITE}/apps/</link>", f"<link>{SITE}/privacy/foo/</link>")
        self.assertGate(f, "RSS-PRIVACY")
        f = self.edit(self.files(), "rss.xml", f"<link>{SITE}/apps/</link>", f"<link>{SITE}/404.html</link>")
        self.assertGate(f, "RSS-NOINDEX")

    def test_rss_strips_meta_toc_script(self):
        f = self.edit(self.files(), "rss.xml", "<![CDATA[", "<![CDATA[<!-- build:meta --><p>by</p><!-- /build:meta -->")
        self.assertGate(f, "RSS-STRIP")
        f = self.edit(self.files(), "rss.xml", "<![CDATA[", '<![CDATA[<script>x()</script>')
        self.assertGate(f, "RSS-STRIP")

    def test_rss_language(self):
        f = self.edit(self.files(), "en/rss.xml", f"<link>{SITE}/en/apps/</link>", f"<link>{SITE}/apps/</link>")
        self.assertGate(f, "RSS-LANG")


class Budgets(Base):
    def test_html_size(self):
        f = self.edit(self.files(), "apps/index.html", "<h2>Photo</h2>", "<h2>Photo</h2><p>" + "x" * 41_000 + "</p>")
        self.assertGate(f, "BUDGET-HTML")

    def test_policy_html_size_60k(self):
        f = self.edit(self.files(), "privacy/foo/index.html", "<!-- build:extra -->", "<p>" + "x" * 45_000 + "</p><!-- build:extra -->")
        self.assertNotIn("BUDGET-HTML", run(f).codes())
        f = self.edit(f, "privacy/foo/index.html", "<!-- build:extra -->", "<p>" + "x" * 20_000 + "</p><!-- build:extra -->")
        self.assertGate(f, "BUDGET-HTML")

    def test_js_budget(self):
        f = self.edit(self.files(), "apps/index.html", "</main>", "<script>" + "1;" * 600 + "</script></main>")
        self.assertGate(f, "BUDGET-JS")

    def test_external_stylesheet(self):
        f = self.edit(self.files(), "apps/index.html", '<link rel="stylesheet"', '<link rel="stylesheet" href="https://fonts.example.com/a.css"><link rel="stylesheet"')
        self.assertGate(f, "ORIGIN")

    def test_external_script(self):
        f = self.edit(self.files(), "apps/index.html", "</main>", '<script src="https://cdn.example.com/a.js" defer></script></main>')
        self.assertGate(f, "ORIGIN")

    def test_external_font_in_css(self):
        f = self.files(); f["assets/site.css"] += "@font-face{font-family:X;src:url(https://hangeul.pstatic.net/x.woff2)}\n"
        self.assertGate(f, "ORIGIN")

    def test_external_image(self):
        f = self.edit(self.files(), "apps/index.html", "<h2>Photo</h2>", '<h2>Photo</h2><img src="https://img.example.com/a.png" width="1" height="1" alt="">')
        self.assertGate(f, "ORIGIN")

    def test_play_link_is_not_an_origin(self):
        self.assertNotIn("ORIGIN", Base.baseline.codes())

    def test_font_preload(self):
        f = self.edit(self.files(), "apps/index.html", '<link rel="stylesheet"', '<link rel="preload" href="/assets/fonts/latin.woff2" as="font" type="font/woff2" crossorigin><link rel="stylesheet"')
        self.assertGate(f, "FONT-PRELOAD")

    def test_font_budget(self):
        f = self.files(); f["assets/fonts/hangul.woff2"] = b"\0" * (480 * 1024)
        rep = self.assertGate(f, "BUDGET-FONT")
        self.assertTrue(any(i.path == "index.html" for i in rep.errors if i.code == "BUDGET-FONT"))
        self.assertFalse(any(i.path.startswith("en/") for i in rep.errors if i.code == "BUDGET-FONT"),
                         "en pages without Hangul must not count the Hangul subset")

    def test_font_css_budget(self):
        f = self.files(); f["assets/fonts/pretendard.css"] = "/* x */\n" * 1000
        self.assertNotIn("BUDGET-CSS", run(f).codes())
        f["assets/fonts/pretendard.css"] = "@font-face{font-family:P;unicode-range:U+AC00}\n" * 600  # ~28 KB > 24 KB
        self.assertGate(f, "BUDGET-CSS")

    def test_font_budget_en(self):
        f = self.files(); f["assets/fonts/latin.woff2"] = b"\0" * (71 * 1024)
        rep = self.assertGate(f, "BUDGET-FONT")
        self.assertTrue(any(i.path.startswith("en/") for i in rep.errors if i.code == "BUDGET-FONT"))

    def test_font_budget_system_font_text_not_counted(self):
        """.sym, code and an en page's [lang=ko] are drawn in the system font (SDS 5.2-4); bare Hangul is not."""
        def en_errors(snippet):
            f = self.edit(self.files(), "en/apps/index.html", "<h2>Photo</h2>", "<h2>Photo</h2>" + snippet)
            f["assets/fonts/hangul.woff2"] = b"\0" * (480 * 1024)
            rep = run(f)
            return [i for i in rep.errors if i.code == "BUDGET-FONT" and i.path == "en/apps/index.html"]
        self.assertTrue(en_errors("<p>가</p>"))
        for wrapped in ('<p><span class="sym">가</span></p>', "<p><code>가</code></p>", '<p><span lang="ko">가</span></p>'):
            self.assertFalse(en_errors(wrapped), wrapped)

    def test_font_budget_en_family(self):
        """With an English-only family declared, /en/ pages count only its files (other glyphs use the system font)."""
        f = self.edit(self.files(), "en/apps/index.html", "<h2>Photo</h2>", "<h2>Photo</h2><p>가</p>")
        f["assets/fonts/hangul.woff2"] = b"\0" * (480 * 1024)
        f["assets/site.css"] = (f"@font-face{{font-family:'{checks.EN_FONT_FAMILY}';src:url(fonts/latin.woff2);"
                                "unicode-range:U+0000-00FF}\n" + f["assets/site.css"])
        rep = run(f)
        bad = {i.path for i in rep.errors if i.code == "BUDGET-FONT"}
        self.assertNotIn("en/apps/index.html", bad)
        self.assertIn("index.html", bad, "ko pages still count the Hangul file")
        f["assets/fonts/latin.woff2"] = b"\0" * (71 * 1024)
        bad = {i.path for i in run(f).errors if i.code == "BUDGET-FONT"}
        self.assertIn("en/apps/index.html", bad, "the English family's own files still count")

    def test_font_budget_same_file_counted_once(self):
        f = self.files(); f["assets/fonts/latin.woff2"] = b"x" * (40 * 1024)
        f["assets/site.css"] = ("@font-face{font-family:'P';font-weight:700;src:url(fonts/latin.woff2);unicode-range:U+0000-00FF}\n"
                                + f["assets/site.css"])
        self.assertNotIn("BUDGET-FONT", run(f).codes("error"))

    def test_font_budget_policy_warns(self):
        """ko policy documents have no IA 9.1 limit: over the page limit is a warning there, an error on app pages."""
        f = self.files(); f["assets/fonts/hangul.woff2"] = b"x" * (480 * 1024)
        f["privacy/foo/index.html"] = f["apps/foo/index.html"]
        rep = run(f)
        self.assertFalse([i for i in rep.errors if i.code == "BUDGET-FONT" and i.path == "privacy/foo/index.html"])
        self.assertTrue([i for i in rep.warnings if i.code == "BUDGET-FONT" and i.path == "privacy/foo/index.html"])
        self.assertTrue([i for i in rep.errors if i.code == "BUDGET-FONT" and i.path == "apps/foo/index.html"])

    def test_font_tiny_subset_warning(self):
        f = self.edit(self.files(), "en/apps/index.html", "<h2>Photo</h2>", "<h2>Photo</h2><p>가</p>")
        self.assertGate(f, "FONT-TINY", level="warning")

    def test_img_needs_size(self):
        f = self.edit(self.files(), "apps/foo/index.html", 'width="360" height="780" loading="lazy"', 'loading="lazy"')
        self.assertGate(f, "IMG-SIZE")

    def test_app_screenshots_lazy(self):
        f = self.edit(self.files(), "apps/foo/index.html", ' loading="lazy"', "")
        self.assertGate(f, "IMG-LAZY")

    def test_icons_per_page(self):
        f = self.files(); f["assets/apps/foo/icon.webp"] = webp(b"VP8 ", 90 * 1024)
        self.assertGate(f, "BUDGET-ICONS")

    def test_css_budget(self):
        f = self.files(); f["assets/site.css"] += "/*" + "x" * 41 * 1024 + "*/"
        self.assertGate(f, "BUDGET-CSS")
        f = self.files(); f["assets/sds-apps.css"] = "/*" + "x" * 5 * 1024 + "*/"
        self.assertGate(f, "BUDGET-CSS")

    def test_screenshot_size(self):
        f = self.files(); f["assets/apps/foo/shot1-ko.webp"] = webp(b"VP8 ", 81 * 1024)
        self.assertGate(f, "BUDGET-SHOT")

    def test_screenshot_lossy(self):
        f = self.files(); f["assets/apps/foo/shot1-ko.webp"] = webp(b"VP8L", 3000)
        self.assertGate(f, "BUDGET-SHOT-LOSSLESS")

    def test_screenshot_lossless_inside_vp8x(self):
        f = self.files()
        vp8x = b"VP8X" + (10).to_bytes(4, "little") + b"\0" * 10
        inner = b"WEBP" + vp8x + b"VP8L" + (100).to_bytes(4, "little") + b"\0" * 100
        f["assets/apps/foo/shot1-ko.webp"] = b"RIFF" + len(inner).to_bytes(4, "little") + inner
        self.assertGate(f, "BUDGET-SHOT-LOSSLESS")

    def test_share_image_size(self):
        f = self.files(); f["assets/og/app-foo-ko.png"] = b"\x89PNG" + b"\0" * 100
        self.assertGate(f, "BUDGET-OG")
        f = self.files(); f["assets/og/app-foo-ko.png"] = b"\x89PNG" + b"\0" * (201 * 1024)
        self.assertGate(f, "BUDGET-OG")


class LengthWarnings(Base):
    def test_title_length_ko(self):
        f = self.edit(self.files(), "apps/index.html", "<title>Android 앱 전체 목록 – SugarMount</title>",
                      "<title>" + "가" * 35 + " – SugarMount</title>")
        self.assertGate(f, "TITLE-TOPIC-LENGTH", "warning")
        self.assertGate(f, "TITLE-LENGTH", "warning")

    def test_title_separator(self):
        f = self.edit(self.files(), "apps/index.html", "목록 – SugarMount", "목록 | SugarMount")
        self.assertGate(f, "TITLE-SEPARATOR", "warning")

    def test_description_length(self):
        f = self.files()
        f["apps/index.html"] = f["apps/index.html"].replace('<meta name="description" content="', '<meta name="description" content="' + "가" * 120, 1)
        self.assertGate(f, "DESC-LENGTH", "warning")

    def test_lead_right_after_h1(self):
        f = self.edit(self.files(), "apps/index.html", '<p class="lead">', '<p>x</p><p class="lead">')
        self.assertGate(f, "LEAD-POSITION", "warning")

    def test_lead_length(self):
        f = self.edit(self.files(), "apps/index.html", '<p class="lead">', '<p class="lead">' + "가" * 80)
        self.assertGate(f, "LEAD-LENGTH", "warning")

    def test_brand_variant(self):
        f = self.edit(self.files(), "apps/index.html", "<h2>Photo</h2>", "<h2>Photo</h2><p>Sugar Mount 앱</p>")
        self.assertGate(f, "BRAND-VARIANT", "warning")

    def test_brand_variant_ignores_email_and_package(self):
        f = self.edit(self.files(), "apps/index.html", "<h2>Photo</h2>", "<h2>Photo</h2><p>sugarmount21@gmail.com com.sugarmount.foo</p>")
        self.assertNotIn("BRAND-VARIANT", run(f).codes())

    def test_warnings_do_not_fail(self):
        f = self.edit(self.files(), "apps/index.html", "목록 – SugarMount", "목록 | SugarMount")
        self.assertEqual(run(f).errors, [])


class FileMode(Base):
    def write_tree(self, files):
        d = tempfile.mkdtemp(prefix="checks-file-")
        self.addCleanup(shutil.rmtree, d, True)
        for rp, v in files.items():
            full = os.path.join(d, rp)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as fh:
                fh.write(v if isinstance(v, bytes) else v.encode("utf-8"))
        return d

    def snapshot(self, d):
        out = {}
        for dp, _, fn in os.walk(d):
            for f in fn:
                p = os.path.join(dp, f); out[p] = (os.path.getsize(p), os.path.getmtime(p))
        return out

    def test_file_mode_checks_main_only_and_is_read_only(self):
        f = self.files()
        f = self.edit(f, "apps/index.html", '<footer><p class="footer-title">SugarMount</p>', "<footer><h2>SugarMount</h2>")
        f = self.edit(f, "apps/index.html", "<h2>Photo</h2>", '<h2>Photo <span class="badge">new</span></h2>')
        d = self.write_tree(f)
        before = self.snapshot(d)
        rep = checks.check_files([os.path.join(d, "apps", "index.html")], d)
        self.assertIn("HEADING-NONTEXT", rep.codes("error"))
        self.assertNotIn("HEADING-OUTSIDE-MAIN", rep.codes())  # outside <main> is the build's, not the author's
        self.assertEqual(before, self.snapshot(d))

    def test_file_mode_relative_path_and_cli_exit(self):
        d = self.write_tree(self.files())
        self.assertEqual(checks.main(["--root", d, "--file", "apps/foo/task/index.html", "--no-warnings"]), 0)
        with open(os.path.join(d, "apps", "foo", "task", "index.html"), encoding="utf-8") as fh:
            s = fh.read()
        with open(os.path.join(d, "apps", "foo", "task", "index.html"), "w", encoding="utf-8") as fh:
            fh.write(s.replace('href="/apps/foo/">', 'href="/apps/nope/">'))
        self.assertEqual(checks.main(["--root", d, "--file", "apps/foo/task/index.html", "--no-warnings"]), 1)


class MoreGates(Base):
    """One test per guard that the first pass of mutation testing left uncovered."""

    def test_title_missing(self):
        f = self.edit(self.files(), "apps/index.html", "<title>Android 앱 전체 목록 – SugarMount</title>", "")
        self.assertGate(f, "TITLE-MISSING")

    def test_description_missing(self):
        f = self.files()
        s = f["apps/index.html"]; a = s.index('<meta name="description"'); b = s.index(">", a) + 1
        f["apps/index.html"] = s[:a] + s[b:]
        self.assertGate(f, "DESC-MISSING")

    def test_description_equals_title(self):
        f = self.files()
        s = f["apps/index.html"]; a = s.index('<meta name="description"'); b = s.index(">", a) + 1
        f["apps/index.html"] = s[:a] + '<meta name="description" content="Android 앱 전체 목록 – SugarMount">' + s[b:]
        self.assertGate(f, "DESC-EQUALS-TITLE", "warning")

    def test_title_suffix(self):
        f = self.edit(self.files(), "apps/index.html", "<title>Android 앱 전체 목록 – SugarMount</title>", "<title>Android 앱 전체 목록</title>")
        self.assertGate(f, "TITLE-SUFFIX", "warning")

    def test_title_repeat(self):
        f = self.edit(self.files(), "apps/index.html", "<title>Android 앱 전체 목록", "<title>Android 앱 Android 목록")
        self.assertGate(f, "TITLE-REPEAT", "warning")

    def test_title_and_description_duplicates(self):
        f = self.edit(self.files(), "privacy/index.html", "<title>개인정보처리방침 – SugarMount</title>", "<title>Android 앱 전체 목록 – SugarMount</title>")
        self.assertGate(f, "TITLE-DUP", "warning")
        f = self.edit(self.files(), "privacy/index.html", " (/privacy/)\">", " (/apps/)\">")
        self.assertGate(f, "DESC-DUP", "warning")

    def test_lead_length_en_words(self):
        f = self.edit(self.files(), "en/apps/index.html", '<p class="lead">', '<p class="lead">' + "word " * 30)
        self.assertGate(f, "LEAD-LENGTH", "warning")

    def test_sugardoc_alone(self):
        f = self.edit(self.files(), "apps/index.html", "<h2>Photo</h2>", "<h2>Photo</h2><p>슈가독으로 엽니다. 한글뷰어 슈가독</p>")
        self.assertGate(f, "BRAND-SUGARDOC", "warning")

    def test_javascript_href(self):
        f = self.edit(self.files(), "apps/index.html", "<h2>Photo</h2>", '<h2>Photo</h2><a href="javascript:go()">go</a>')
        self.assertGate(f, "JS-LINK")

    def test_absolute_internal_link_warning(self):
        f = self.edit(self.files(), "apps/index.html", 'href="/apps/foo/task/"', 'href="https://mvgood21.github.io/apps/foo/task/"')
        self.assertGate(f, "LINK-ABSOLUTE", "warning")

    def test_generic_anchor_warning(self):
        f = self.edit(self.files(), "apps/index.html", "<h2>Photo</h2>", '<h2>Photo</h2><a href="/apps/foo/">자세히 보기</a>')
        self.assertGate(f, "ANCHOR-GENERIC", "warning")

    def test_meta_robots_nofollow(self):
        f = self.edit(self.files(), "apps/index.html", '<meta charset="utf-8">', '<meta charset="utf-8"><meta name="robots" content="nofollow">')
        self.assertGate(f, "NOFOLLOW")

    def test_article_date_published_timezone(self):
        f = self.edit(self.files(), "apps/foo/task/index.html", '"datePublished": "2026-10-03T09:00:00+09:00"', '"datePublished": "2026-10-03"')
        self.assertGate(f, "SD-ARTICLE-DATE")

    def test_app_page_needs_primary_image(self):
        f = self.edit(self.files(), "apps/foo/index.html",
                      '"primaryImageOfPage": {"@type": "ImageObject", "url": "https://mvgood21.github.io/assets/og/app-foo-ko.png", "width": 1200, "height": 630}, ', "")
        self.assertGate(f, "SD-PRIMARY-IMAGE")

    def test_script_defer_warning(self):
        f = self.edit(self.files(), "apps/index.html", "</main>", '<script src="/assets/menu.js"></script></main>')
        f["assets/menu.js"] = "1;"
        self.assertGate(f, "JS-DEFER", "warning")
        f = self.edit(self.files(), "apps/index.html", "</main>", '<script src="/assets/menu.js" defer></script></main>')
        f["assets/menu.js"] = "1;"
        self.assertNotIn("JS-DEFER", run(f).codes())

    def test_sitemap_missing_or_broken(self):
        f = self.files(); del f["sitemap.xml"]
        self.assertGate(f, "SITEMAP-MISSING")
        f = self.edit(self.files(), "sitemap.xml", "</urlset>", "<url></urlset>")
        self.assertGate(f, "SITEMAP-XML")

    def test_sitemap_index(self):
        f = self.files()
        f["sitemap-all.xml"] = f["sitemap.xml"]
        f["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                            f"<sitemap><loc>{SITE}/sitemap-all.xml</loc></sitemap></sitemapindex>")
        self.assertFalse([c for c in run(f).codes() if c.startswith("SITEMAP")])
        del f["sitemap-all.xml"]
        self.assertGate(f, "SITEMAP-MISSING")
        f["sitemap.xml"] = f["sitemap.xml"].replace(f"{SITE}/sitemap-all.xml", "https://example.com/sitemap-all.xml")
        self.assertGate(f, "SITEMAP-INDEX")

    def test_sitemap_loc_resolves(self):
        f = self.edit(self.files(), "sitemap.xml", "</urlset>", f"<url><loc>{SITE}/apps/nope/</loc></url></urlset>")
        self.assertGate(f, "SITEMAP-LOC")

    def test_sitemap_no_ownership_file(self):
        f = self.files()
        f["google83e3e62aee87a145.html"] = "google-site-verification: google83e3e62aee87a145.html"
        f = self.edit(f, "sitemap.xml", "</urlset>", f"<url><loc>{SITE}/google83e3e62aee87a145.html</loc></url></urlset>")
        self.assertGate(f, "SITEMAP-OWNERSHIP")

    def test_rss_xml_and_links(self):
        f = self.edit(self.files(), "rss.xml", "</channel>", "<item></channel>")
        self.assertGate(f, "RSS-XML")
        f = self.edit(self.files(), "rss.xml", f"<link>{SITE}/apps/</link>", f"<link>{SITE}/apps/nope/</link>")
        self.assertGate(f, "RSS-LINK")

    def test_rss_bad_pubdate(self):
        f = self.edit(self.files(), "rss.xml", "Sat, 03 Oct 2026", "someday")
        self.assertGate(f, "RSS-PUBDATE")

    def test_robots_missing(self):
        f = self.files(); del f["robots.txt"]
        self.assertGate(f, "ROBOTS-MISSING")

    def test_dates_file_missing_warns_and_skips(self):
        f = self.files(); del f["data/content-dates.json"]
        rep = self.assertGate(f, "DATES-FILE", "warning")
        self.assertEqual(rep.errors, [])

    def test_file_mode_errors(self):
        rep = checks.check_files([os.path.join(EMPTY, "nope", "index.html")], EMPTY)
        self.assertIn("FILE-MISSING", rep.codes("error"))
        other = tempfile.mkdtemp(prefix="checks-other-")
        self.addCleanup(shutil.rmtree, other, True)
        rep = checks.check_files([os.path.join(other, "index.html")], EMPTY)
        self.assertIn("FILE-OUTSIDE", rep.codes("error"))

    def test_file_mode_needs_main(self):
        d = tempfile.mkdtemp(prefix="checks-nomain-")
        self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as fh:
            fh.write('<html lang="ko"><head><title>t</title><meta name="description" content="d"></head><body><h1>x</h1></body></html>')
        self.assertIn("MAIN-MISSING", checks.check_files([os.path.join(d, "index.html")], d).codes("error"))


class Helpers(unittest.TestCase):
    def test_unicode_range(self):
        self.assertEqual(checks.parse_unicode_range("U+0-FF, U+4??, U+20AC"), [(0, 0xFF), (0x400, 0x4FF), (0x20AC, 0x20AC)])

    def test_page_kind(self):
        k = checks.page_kind
        self.assertEqual([k("index.html"), k("en/apps/index.html"), k("apps/x/index.html"), k("en/apps/x/y/index.html"),
                          k("ax/index.html"), k("ax/n/index.html"), k("about/index.html"), k("privacy/axfamily/delete/index.html"),
                          k("404.html"), k("design/index.html")],
                         ["home", "hub", "app", "article", "ax-hub", "ax-note", "about", "policy", "404", "design"])

    def test_noindex_constant(self):
        self.assertEqual(checks.NOINDEX_PATHS, {"404.html", "design/index.html"})


if __name__ == "__main__":
    unittest.main()
