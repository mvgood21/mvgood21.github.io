"""Related AX notes: only indexable notes are offered, and links from noindex notes do not count (tools/build.py)."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import build  # noqa: E402


def noindex(u):
    return u.lstrip("/") + "index.html" in build.NOINDEX_PATHS


class AxRelated(unittest.TestCase):
    def test_only_indexable_notes_are_offered(self):
        for lang in ("ko", "en"):
            pre = "/en/ax/" if lang == "en" else "/ax/"
            arts = [(f"{pre}{s}/", s) for s in build.AX_NOTE_TOPIC]
            build._AX_INLINKS[lang] = {}  # ranking is not under test; the real one needs a dated build
            self.addCleanup(build._AX_INLINKS.clear)
            self.assertTrue(any(noindex(u) for u, _ in arts))  # otherwise the check below proves nothing
            for path, _ in arts:
                pool = [x for x in arts if x[0] != path]
                got, has_topic = build.ax_related(path, lang, build.ax_topic_of(path), pool, build.AX_RELATED)
                self.assertTrue(has_topic, path)  # games: every note is noindex, the topic link must stay
                self.assertEqual(len(got), build.AX_RELATED, path)
                self.assertEqual([u for u, _ in got if noindex(u)], [], path)

    def test_links_from_noindex_notes_do_not_count(self):
        arts = [("/ax/a/", "a", ""), ("/ax/b/", "b", ""), ("/ax/c/", "c", "")]
        bodies = {"ax/a/index.html": "", "ax/b/index.html": '<a href="/ax/a/">', "ax/c/index.html": '<a href="/ax/a/">'}
        saved = build.ax_articles, build.read, build.NOINDEX_PATHS
        build._AX_INLINKS.clear()
        try:
            build.ax_articles = lambda lang: arts
            build.read = bodies.__getitem__
            build.NOINDEX_PATHS = {"ax/b/index.html"}
            self.assertEqual(build.ax_inlinks("ko"), {"/ax/a/": 1})
        finally:
            build.ax_articles, build.read, build.NOINDEX_PATHS = saved
            build._AX_INLINKS.clear()


if __name__ == "__main__":
    unittest.main()
