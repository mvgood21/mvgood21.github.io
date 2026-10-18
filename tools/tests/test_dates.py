"""Tests for tools/dates.py and tools/backfill_dates.py. Run: python -m unittest discover -s tools/tests"""
import datetime, json, os, shutil, subprocess, sys, tempfile, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import dates  # noqa: E402
import backfill_dates  # noqa: E402

PAGE = """<!DOCTYPE html><html><head><title>t</title></head><body><header><h2>menu</h2></header>
<main id="main" class="container">
    <nav class="crumbs" aria-label="x"><ol><li><a href="/">SugarMount</a></li></ol></nav>
    <h1>제목</h1>
    <p class="lead">답 먼저.</p>
    <!-- build:meta --><p class="meta">최종 업데이트 <time datetime="2026-10-01">2026년 10월 1일</time></p><!-- /build:meta -->
    <!-- build:toc --><nav class="toc"><a href="#a">a</a></nav><!-- /build:toc -->
    <h2 id="a">A</h2><p>본문</p>
    <!-- build:tasks --><ul><li>할 일</li></ul><!-- /build:tasks -->
    <!-- build:extra -->
    <p class="muted updated">최종 업데이트 <time datetime="2026-10-01">2026-10-01</time></p>
    <!-- /build:extra -->
</main>
<footer>f</footer></body></html>"""


class HashInput(unittest.TestCase):
    def h(self, page): return dates.content_hash(dates.hand_input(page))

    def test_build_blocks_do_not_change_hash(self):
        for name in ("meta", "toc", "tasks", "extra"):
            changed = PAGE.replace("2026-10-01", "2027-01-01") if name in ("meta", "extra") else PAGE.replace(">할 일<", ">다른 일<").replace('>a</a>', '>b</a>')
            self.assertEqual(self.h(PAGE), self.h(changed), name)

    def test_ax_list_block_ignored(self):
        a = PAGE.replace("<h2 id", "<!-- build:ax-list --><ul><li>1</li></ul><!-- /build:ax-list --><h2 id")
        b = a.replace("<li>1</li>", "<li>1</li><li>2</li>")
        self.assertEqual(self.h(a), self.h(b))

    def test_every_marker_block_is_removed(self):
        text = dates.hand_input(PAGE)
        self.assertNotIn("build:", text)
        self.assertNotIn("최종 업데이트", text)

    def test_crumbs_do_not_change_hash(self):
        self.assertEqual(self.h(PAGE), self.h(PAGE.replace(">SugarMount<", ">홈<")))

    def test_outside_main_does_not_change_hash(self):
        self.assertEqual(self.h(PAGE), self.h(PAGE.replace("<h2>menu</h2>", "<h2>메뉴</h2>").replace("<title>t", "<title>u")))

    def test_whitespace_normalised(self):
        self.assertEqual(self.h(PAGE), self.h(PAGE.replace("<p>본문</p>", "<p>본문</p>\n\n      ").replace("\n", "\r\n")))

    def test_content_change_changes_hash(self):
        self.assertNotEqual(self.h(PAGE), self.h(PAGE.replace("<p>본문</p>", "<p>본문을 고쳤다</p>")))
        self.assertNotEqual(self.h(PAGE), self.h(PAGE.replace('<h2 id="a">', '<h2 id="b">')))  # tags are kept

    def test_data_input_is_order_independent(self):
        self.assertEqual(dates.content_hash(dates.data_input({"a": 1, "b": [1, 2]})),
                         dates.content_hash(dates.data_input({"b": [1, 2], "a": 1})))
        self.assertNotEqual(dates.content_hash(dates.data_input({"a": 1})), dates.content_hash(dates.data_input({"a": 2})))

    def test_nested_and_adjacent_blocks(self):
        nested = PAGE.replace("<h2 id", "<!-- build:extra --><p>a</p><!-- build:toc --><p>b</p><!-- /build:toc --><!-- /build:extra --><h2 id")
        self.assertEqual(self.h(PAGE), self.h(nested))
        adjacent = PAGE.replace("<h2 id", "<!-- build:meta -->1<!-- /build:meta --><!-- build:meta -->2<!-- /build:meta --><h2 id")
        self.assertEqual(self.h(PAGE), self.h(adjacent))
        # a marker split by an inner block only forms after the inner block is removed: strip until stable
        split = PAGE.replace("<h2 id", "<!-- build:extra <!-- build:toc -->x<!-- /build:toc -->-->y<!-- /build:extra --><h2 id")
        self.assertNotIn("build:", dates.hand_input(split))
        self.assertEqual(self.h(PAGE), self.h(split))

    def test_page_without_main_hashes_whole_text(self):
        page = "<!DOCTYPE html><html><body><h1>t</h1><p>본문</p></body></html>"
        self.assertNotEqual(self.h(page), self.h(page.replace("본문", "다른 본문")))
        self.assertIn("본문", dates.hand_input(page))

    def test_hash_is_16_hex(self):
        self.assertRegex(dates.content_hash("x"), r"^[0-9a-f]{16}$")


class Store(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="dates-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, "content-dates.json")
        self.env = mock.patch.dict(os.environ, {"SOURCE_DATE": "2026-10-20"})
        self.env.start(); self.addCleanup(self.env.stop)

    def store(self, **kw): return dates.ContentDates(self.path, **kw)

    def seed(self, entries):
        with open(self.path, "w", encoding="utf-8") as f: json.dump(entries, f)

    def test_new_page_published_and_modified_today(self):
        s = self.store()
        self.assertEqual(s.get("a/index.html", "x"), ("2026-10-20", "2026-10-20"))
        self.assertEqual(s.stale, [("a/index.html", "new")])

    def test_same_hash_keeps_dates(self):
        self.seed({"a/index.html": {"hash": dates.content_hash("x"), "published": "2026-09-01", "modified": "2026-09-05"}})
        s = self.store()
        self.assertEqual(s.get("a/index.html", "x"), ("2026-09-01", "2026-09-05"))
        self.assertFalse(s.changed())

    def test_changed_hash_moves_modified_only(self):
        self.seed({"a/index.html": {"hash": dates.content_hash("x"), "published": "2026-09-01", "modified": "2026-09-05"}})
        s = self.store()
        self.assertEqual(s.get("a/index.html", "y"), ("2026-09-01", "2026-10-20"))
        self.assertEqual(s.entries["a/index.html"]["hash"], dates.content_hash("y"))
        self.assertTrue(s.changed())

    def test_earlier_source_date_never_moves_modified_back(self):
        self.seed({"a/index.html": {"hash": dates.content_hash("x"), "published": "2026-10-20", "modified": "2026-10-20"}})
        with mock.patch.dict(os.environ, {"SOURCE_DATE": "2026-10-19"}):
            s = self.store()
            self.assertEqual(s.get("a/index.html", "y"), ("2026-10-20", "2026-10-20"))
            self.assertEqual(s.entries["a/index.html"]["hash"], dates.content_hash("y"))
            s.save()
        self.assertEqual(self.store().peek("a/index.html"), ("2026-10-20", "2026-10-20"))  # reload validates

    def test_idempotent_next_day(self):
        s = self.store(); s.get("a/index.html", "x"); s.save()
        with mock.patch.dict(os.environ, {"SOURCE_DATE": "2026-10-21"}):
            s2 = self.store()
            self.assertEqual(s2.get("a/index.html", "x"), ("2026-10-20", "2026-10-20"))
            self.assertFalse(s2.save())

    def test_null_hash_is_adopted_without_moving_dates(self):
        self.seed({"index.html": {"hash": None, "published": "2026-09-20", "modified": "2026-10-05"}})
        s = self.store()
        self.assertEqual(s.get("index.html", "data"), ("2026-09-20", "2026-10-05"))
        self.assertEqual(s.entries["index.html"]["hash"], dates.content_hash("data"))
        self.assertEqual(s.stale, [("index.html", "baseline")])
        s.save()
        self.assertEqual(self.store().get("index.html", "data2"), ("2026-09-20", "2026-10-20"))

    def test_check_mode_never_writes(self):
        s = self.store(check=True)
        s.get("a/index.html", "x")
        self.assertTrue(s.save())  # reports that it would change
        self.assertFalse(os.path.exists(self.path))

    def test_save_writes_sorted_json(self):
        s = self.store(); s.get("b/index.html", "x"); s.get("a/index.html", "x"); s.save()
        with open(self.path, encoding="utf-8") as f: text = f.read()
        self.assertLess(text.index("a/index.html"), text.index("b/index.html"))
        self.assertEqual(text, s.dumps())

    def test_windows_separators(self):
        s = self.store()
        s.get("apps\\x\\index.html", "x")
        self.assertIn("apps/x/index.html", s.entries)

    def test_unused(self):
        self.seed({"gone/index.html": {"hash": "0" * 16, "published": "2026-09-01", "modified": "2026-09-01"}})
        s = self.store(); s.get("a/index.html", "x")
        self.assertEqual(s.unused(), ["gone/index.html"])

    def test_rejects_bad_file(self):
        self.seed({"a/index.html": {"hash": "x", "published": "2026-10-05", "modified": "2026-10-01"}})
        with self.assertRaises(ValueError): self.store()
        self.seed({"a/index.html": {"hash": "x", "published": "10/05/2026", "modified": "2026-10-06"}})
        with self.assertRaises(ValueError): self.store()


class Today(unittest.TestCase):
    def test_source_date(self):
        with mock.patch.dict(os.environ, {"SOURCE_DATE": "2026-12-31"}):
            self.assertEqual(dates.today(), "2026-12-31")

    def test_bad_source_date(self):
        for bad in ("2026-13-01", "20261231", "tomorrow"):
            with mock.patch.dict(os.environ, {"SOURCE_DATE": bad}):
                with self.assertRaises(ValueError): dates.today()

    def test_default_is_seoul(self):
        env = {k: v for k, v in os.environ.items() if k != "SOURCE_DATE"}
        with mock.patch.dict(os.environ, env, clear=True):
            fixed = datetime.datetime(2026, 10, 18, 16, 0, tzinfo=datetime.timezone.utc)  # 01:00 on the 19th in Seoul

            class FakeDT(datetime.datetime):
                @classmethod
                def now(cls, tz=None): return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)
            with mock.patch.object(dates.datetime, "datetime", FakeDT):
                self.assertEqual(dates.today(), "2026-10-19")

    def test_iso_datetime(self):
        self.assertEqual(dates.iso_datetime("2026-10-17"), "2026-10-17T09:00:00+09:00")
        with self.assertRaises(ValueError): dates.iso_datetime("2026-10-32")


def git(repo, *args, date=None):
    env = dict(os.environ)
    if date:
        env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = f"{date}T12:00:00+09:00"
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                    "-c", "core.autocrlf=false", *args], cwd=repo, env=env, check=True, capture_output=True)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class Backfill(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="backfill-")
        self.addCleanup(shutil.rmtree, self.repo, True)
        git(self.repo, "init", "-q")

    def write(self, rel, text):
        full = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f: f.write(text)

    def commit(self, date):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", date, date=date)

    def test_dates_from_history(self):
        self.write("apps/a/index.html", PAGE); self.commit("2026-09-20")
        self.write("apps/a/index.html", PAGE.replace("<p>본문</p>", "<p>새 본문</p>")); self.commit("2026-10-01")
        # only build-owned parts change afterwards: modified must stay 2026-10-01
        self.write("apps/a/index.html", PAGE.replace("<p>본문</p>", "<p>새 본문</p>").replace("2026-10-01", "2026-10-09")
                   .replace("<h2>menu</h2>", "<h2>메뉴</h2>")); self.commit("2026-10-09")
        self.write("index.html", PAGE); self.commit("2026-10-02")
        self.write("data/apps.json", json.dumps({"apps": []})); self.write("tools/x/index.html", PAGE)
        self.write("assets/index.html", PAGE); self.commit("2026-10-03")
        e = backfill_dates.backfill(self.repo)
        self.assertEqual(sorted(e), ["apps/a/index.html", "index.html"])  # tools/, assets/ are not pages
        a = e["apps/a/index.html"]
        self.assertEqual((a["published"], a["modified"]), ("2026-09-20", "2026-10-01"))
        with open(os.path.join(self.repo, "apps/a/index.html"), encoding="utf-8") as f:
            self.assertEqual(a["hash"], dates.content_hash(dates.hand_input(f.read())))
        self.assertIsNone(e["index.html"]["hash"])  # generated: the build's data hash is adopted later
        self.assertEqual(e["index.html"]["published"], "2026-10-02")

    def test_generated_app_pages_from_apps_json(self):
        self.write("data/apps.json", json.dumps({"apps": [{"page": "generated", "app_path": "g"}, {"page": "hand", "app_path": "h"}]}))
        self.write("apps/g/index.html", PAGE); self.write("apps/h/index.html", PAGE); self.commit("2026-10-05")
        e = backfill_dates.backfill(self.repo)
        self.assertIsNone(e["apps/g/index.html"]["hash"])
        self.assertIsNotNone(e["apps/h/index.html"]["hash"])

    def test_similar_file_is_not_followed(self):
        self.write("apps/a/index.html", PAGE); self.commit("2026-09-20")
        os.remove(os.path.join(self.repo, "apps/a/index.html"))
        self.write("apps/b/index.html", PAGE); self.commit("2026-09-24")  # git sees a rename a -> b
        e = backfill_dates.backfill(self.repo)
        self.assertEqual(e["apps/b/index.html"]["published"], "2026-09-24")

    def test_uncommitted_pages_are_left_out(self):
        self.write("apps/a/index.html", PAGE); self.commit("2026-09-20")
        self.write("ax/new/index.html", PAGE)
        self.assertNotIn("ax/new/index.html", backfill_dates.backfill(self.repo))

    def test_main_refuses_to_overwrite(self):
        self.write("apps/a/index.html", PAGE); self.commit("2026-09-20")
        self.assertEqual(backfill_dates.main(["--root", self.repo]), 0)
        self.assertEqual(backfill_dates.main(["--root", self.repo]), 1)
        self.assertEqual(backfill_dates.main(["--root", self.repo, "--force"]), 0)
        s = dates.ContentDates(os.path.join(self.repo, dates.DATES_FILE))  # loads and validates
        self.assertEqual(s.peek("apps/a/index.html"), ("2026-09-20", "2026-09-20"))


if __name__ == "__main__":
    unittest.main()
