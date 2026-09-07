#!/usr/bin/env python3
"""Tests for x_settings.py -- the shared settings.md loader."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import x_settings  # noqa: E402


REAL_SETTINGS = Path(__file__).resolve().parents[1] / "settings.md"


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
        self.assertTrue(self.settings["x_list_url"].startswith("https://x.com/i/lists/"))

    def test_models_table_gives_model_and_effort(self):
        self.assertIn("cluster_model", self.settings)
        self.assertIn("cluster_effort", self.settings)
        self.assertIn("judge_model", self.settings)
        self.assertIn("judge_effort", self.settings)

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
        path = self.write("## Numbers\n\n| Setting | Value | What |\n|---|---|---|\n"
                           "| x_thing | 90% | a percentile |\n")
        settings = x_settings.load_settings(path)
        self.assertEqual(settings["x_thing"], 90)

    def test_missing_file_exits_nonzero(self):
        with self.assertRaises(SystemExit) as ctx:
            x_settings.load_settings(Path("/no/such/settings.md"))
        self.assertNotEqual(ctx.exception.code, 0)

    def test_duplicate_key_exits_nonzero(self):
        path = self.write("## Numbers\n\n| Setting | Value | What |\n|---|---|---|\n"
                           "| x_dup | 1 | first |\n| x_dup | 2 | second |\n")
        with self.assertRaises(SystemExit):
            x_settings.load_settings(path)

    def test_models_row_without_effort_exits_nonzero(self):
        path = self.write("## Models\n\n| Step | Model | Effort |\n|---|---|---|\n"
                           "| cluster | opus |  |\n")
        with self.assertRaises(SystemExit):
            x_settings.load_settings(path)


if __name__ == "__main__":
    unittest.main()
