#!/usr/bin/env python3
"""Tests for x_settings.py -- the loader for the X half of settings.md."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import x_settings  # noqa: E402


REAL_SETTINGS = Path(__file__).resolve().parents[2] / "settings.md"


class TestLoadRealSettings(unittest.TestCase):
    def setUp(self):
        self.settings = x_settings.load_settings(REAL_SETTINGS)

    def test_every_number_present_and_typed(self):
        numbers = [
            "x_window_hours", "x_stop_after_old", "x_min_own_words",
            "x_convergence_authors", "x_endorsement_min", "x_velocity_percentile",
            "x_curious_percentile", "x_picks_max", "x_tweets_min",
            "x_cluster_chunk", "x_agents_active_max",
        ]
        for key in numbers:
            self.assertIn(key, self.settings, f"missing {key}")
            self.assertIsInstance(self.settings[key], int, f"{key} should be an int")

    def test_fixed_values_present(self):
        self.assertEqual(self.settings["x_account"], "@EgoismoEfficace")

    def test_which_lists_to_read_is_not_in_settings(self):
        """The lists live in sources.md now, so Yaron adds one the same way he
        adds a news site. A leftover x_list_url here would be read by nothing."""
        self.assertNotIn("x_list_url", self.settings)

    def test_models_table_gives_model_and_effort(self):
        self.assertIn("cluster_model", self.settings)
        self.assertIn("cluster_effort", self.settings)
        self.assertIn("judge_model", self.settings)
        self.assertIn("judge_effort", self.settings)

    def test_every_agent_step_has_a_model_and_an_effort(self):
        """The four agent steps x_run.py launches. Both halves of each row
        must load: since the effort is now passed to `claude -p` as
        `--effort`, a row with no effort key stops the run instead of
        quietly running the step at some default."""
        for step in ("read", "cluster", "judge", "write"):
            for suffix in ("_model", "_effort"):
                key = step + suffix
                self.assertIn(key, self.settings, f"missing {key}")
                self.assertTrue(str(self.settings[key]).strip(), f"{key} is empty")

    def test_the_article_halfs_rows_are_not_read(self):
        """The one file holds both halves. A step named `cluster` in each is
        the reason this loader reads only the `X` headings: the article
        brief's own tables must not reach here at all."""
        self.assertNotIn("picks_max", self.settings)
        self.assertNotIn("triage_batch_size", self.settings)
        self.assertNotIn("screen_model", self.settings)
        self.assertNotIn("counterpoint_model", self.settings)

    def test_no_key_named_twice(self):
        # load_settings itself dies (exit 2) on a duplicate; loading twice
        # without dying is itself the proof there is no collision.
        again = x_settings.load_settings(REAL_SETTINGS)
        self.assertEqual(self.settings, again)


class TestLoaderMechanics(unittest.TestCase):
    def write(self, text: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
        tmp.write(text)
        tmp.close()
        return Path(tmp.name)

    def test_percent_cell_becomes_int(self):
        path = self.write("## X numbers\n\n| Setting | Value | What |\n|---|---|---|\n"
                           "| x_thing | 90% | a percentile |\n")
        settings = x_settings.load_settings(path)
        self.assertEqual(settings["x_thing"], 90)

    def test_missing_file_exits_nonzero(self):
        with self.assertRaises(SystemExit) as ctx:
            x_settings.load_settings(Path("/no/such/settings.md"))
        self.assertNotEqual(ctx.exception.code, 0)

    def test_duplicate_key_exits_nonzero(self):
        path = self.write("## X numbers\n\n| Setting | Value | What |\n|---|---|---|\n"
                           "| x_dup | 1 | first |\n| x_dup | 2 | second |\n")
        with self.assertRaises(SystemExit):
            x_settings.load_settings(path)

    def test_a_foreign_section_is_skipped_not_merged(self):
        path = self.write(
            "## Numbers\n\n| Setting | Value | What |\n|---|---|---|\n"
            "| cluster_articles_max | 150 | the article half |\n\n"
            "## X numbers\n\n| Setting | Value | What |\n|---|---|---|\n"
            "| x_thing | 7 | ours |\n")
        settings = x_settings.load_settings(path)
        self.assertEqual(settings["x_thing"], 7)
        self.assertNotIn("cluster_articles_max", settings)

    def test_models_row_without_effort_exits_nonzero(self):
        path = self.write("## X models\n\n| Step | Model | Effort |\n|---|---|---|\n"
                           "| cluster | opus |  |\n")
        with self.assertRaises(SystemExit):
            x_settings.load_settings(path)


class TestReadXLists(unittest.TestCase):
    """`## X lists` in sources.md is where the lists to read are named."""

    def write(self, text: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False)
        tmp.write(text)
        tmp.close()
        return Path(tmp.name)

    SOURCES = (
        "# Sources\n\n"
        "1. Guardian - https://www.theguardian.com/\n"
        "2. Reason - https://reason.com/ - Sign Out\n\n"
        "## X lists\n\n"
        "Prose with no link is ignored, the way it is above.\n\n"
        "1. List one - https://x.com/i/lists/111\n"
        "- List two - https://x.com/i/lists/222\n"
    )

    def test_reads_the_x_section_only(self):
        rows = x_settings.read_x_lists(self.write(self.SOURCES))
        self.assertEqual([r["url"] for r in rows],
                          ["https://x.com/i/lists/111", "https://x.com/i/lists/222"])
        self.assertEqual([r["name"] for r in rows], ["List one", "List two"])
        self.assertEqual([r["slug"] for r in rows], ["list-one", "list-two"])

    def test_a_news_front_page_is_never_returned(self):
        rows = x_settings.read_x_lists(self.write(self.SOURCES))
        for r in rows:
            self.assertNotIn("theguardian", r["url"])
            self.assertNotIn("reason.com", r["url"])

    def test_one_list_is_fine(self):
        rows = x_settings.read_x_lists(self.write(
            "## X lists\n\n1. Only - https://x.com/i/lists/1\n"))
        self.assertEqual(len(rows), 1)

    def test_no_section_exits_nonzero(self):
        with self.assertRaises(SystemExit):
            x_settings.read_x_lists(self.write(
                "# Sources\n\n1. Guardian - https://www.theguardian.com/\n"))

    def test_the_same_list_twice_exits_nonzero(self):
        with self.assertRaises(SystemExit):
            x_settings.read_x_lists(self.write(
                "## X lists\n\n1. A - https://x.com/i/lists/1\n"
                "2. B - https://x.com/i/lists/1\n"))

    def test_the_real_sources_file_names_at_least_one_list(self):
        rows = x_settings.read_x_lists()
        self.assertTrue(rows)
        for r in rows:
            self.assertTrue(r["url"].startswith("https://x.com/i/lists/"), r["url"])
            self.assertTrue(r["name"])


if __name__ == "__main__":
    unittest.main()
