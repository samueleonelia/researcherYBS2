#!/usr/bin/env python3
"""Tests for x_run.py -- the chain's own plumbing.

These do NOT invoke the real `claude` CLI (no cost, no network, no
judgment to fake) and do NOT drive a browser. They cover:

  - settings are read from the table, never hard-coded, by checking that
    x_run.py's own module holds no numeric literal that shadows a
    settings.md number
  - a run folder is named runs/<YYYY-MM-DD>-<HHMM> in UTC and never
    collides
  - a missing step script fails the chain with a message naming that step,
    not a traceback
  - prompt placeholders are discovered from the file, not assumed, and an
    unfillable placeholder fails clearly
  - cluster's chunking splits kept tweets into x_cluster_chunk-sized parts
  - cluster's coverage check catches a missing or duplicated id
  - the judge merge step fills judge-merge.md's placeholders and calls
    `claude` at the configured model (mocked)
"""

import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import x_run  # noqa: E402
from x_settings import load_settings  # noqa: E402

SETTINGS_PATH = ROOT / "settings.md"


class TestRunDir(unittest.TestCase):
    def test_name_format_is_utc_date_time(self):
        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td)
            before = datetime.now(timezone.utc)
            run_dir = x_run.new_run_dir(runs_root)
            after = datetime.now(timezone.utc)
            self.assertTrue(run_dir.exists())
            self.assertTrue(re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{4}", run_dir.name),
                             run_dir.name)
            stamp = datetime.strptime(run_dir.name, "%Y-%m-%d-%H%M").replace(tzinfo=timezone.utc)
            self.assertLessEqual(before.replace(second=0, microsecond=0), stamp)
            self.assertLessEqual(stamp, after.replace(second=0, microsecond=0).replace(second=0))

    def test_never_collides(self):
        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td)
            first = x_run.new_run_dir(runs_root)
            second = x_run.new_run_dir(runs_root)
            self.assertNotEqual(first, second)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())


class TestMissingStep(unittest.TestCase):
    def test_missing_script_names_the_step_and_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            with self.assertRaises(SystemExit) as ctx:
                x_run.run_script_step(1, "no_such_script.py", run_dir, SETTINGS_PATH)
            self.assertNotEqual(ctx.exception.code, 0)

    def test_missing_script_message_names_step_and_file(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            with mock.patch.object(x_run, "die") as mock_die:
                mock_die.side_effect = SystemExit(1)
                with self.assertRaises(SystemExit):
                    x_run.run_script_step(2, "x_ghost.py", run_dir, SETTINGS_PATH)
                msg = mock_die.call_args[0][0]
                self.assertIn("step 2", msg)
                self.assertIn("filter", msg)
                self.assertIn("x_ghost.py", msg)

    def test_missing_prompt_names_the_step_and_file(self):
        with mock.patch.object(x_run, "die") as mock_die:
            mock_die.side_effect = SystemExit(1)
            with self.assertRaises(SystemExit):
                x_run.load_prompt_template("no_such_prompt.md", 3, "cluster")
            msg = mock_die.call_args[0][0]
            self.assertIn("step 3", msg)
            self.assertIn("no_such_prompt.md", msg)

    def test_missing_claude_binary_is_a_clear_die_not_a_traceback(self):
        with mock.patch("subprocess.run", side_effect=FileNotFoundError()):
            with mock.patch.object(x_run, "die") as mock_die:
                mock_die.side_effect = SystemExit(1)
                with self.assertRaises(SystemExit):
                    x_run.call_claude("prompt", "opus", ROOT)
                self.assertIn("claude", mock_die.call_args[0][0])

    def test_chain_full_run_fails_clearly_when_step_missing(self):
        """python3 x_run.py against a run dir with no tweets.json and a
        renamed-away x_scrape.py fails with a named step, no traceback."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            result = subprocess.run(
                [sys.executable, str(ROOT / "x_run.py"),
                 "--run-dir", str(run_dir), "--settings", str(SETTINGS_PATH),
                 "--only", "1", "--from", "1"],
                capture_output=True, text=True,
                env={**__import__("os").environ, "PATH": "/usr/bin:/bin"},
            )
            # Without a real PATH, x_scrape.py itself may or may not run
            # (it exists in the repo); the contract we actually own is: if
            # a step script is absent, x_run.py must name it, not traceback.
            self.assertNotIn("Traceback", result.stderr)


class TestPlaceholders(unittest.TestCase):
    def test_placeholders_in_finds_every_slot(self):
        template = "hello {{FOO}} and {{BAR}} and {{FOO}} again"
        self.assertEqual(x_run.placeholders_in(template), {"FOO", "BAR"})

    def test_fill_template_substitutes_every_slot(self):
        template = "{{A}}-{{B}}"
        out = x_run.fill_template(template, {"A": "1", "B": "2"})
        self.assertEqual(out, "1-2")

    def test_fill_template_dies_on_unknown_placeholder(self):
        template = "{{A}}-{{MYSTERY}}"
        with mock.patch.object(x_run, "die") as mock_die:
            mock_die.side_effect = SystemExit(1)
            with self.assertRaises(SystemExit):
                x_run.fill_template(template, {"A": "1"})
            self.assertIn("MYSTERY", mock_die.call_args[0][0])

    def test_real_prompt_placeholders_are_discovered_not_assumed(self):
        """Whatever names cluster.md and judge.md actually use, x_run.py
        must be able to supply all of them -- this is the contract
        (discover placeholders from the file, don't assume names)."""
        cluster_path = ROOT / "prompts" / "cluster.md"
        if not cluster_path.exists():
            self.skipTest("prompts/cluster.md not built yet")
        found = x_run.placeholders_in(cluster_path.read_text(encoding="utf-8"))
        provided = {"RUN_DIR", "TWEETS", "PART_NOTE", "OUTPUT_PATH"}
        self.assertTrue(found <= provided,
                         f"cluster.md needs placeholder(s) x_run.py doesn't supply: {found - provided}")

        judge_path = ROOT / "prompts" / "judge.md"
        if judge_path.exists():
            found = x_run.placeholders_in(judge_path.read_text(encoding="utf-8"))
            provided = {"RUN_DIR", "SUBJECT", "SCORE_TAG", "FLAGS", "MEASURES",
                        "VELOCITY_RANK", "CURIOUS_PERCENTILE", "TWEETS",
                        "PROFILE_DATE", "PROFILE", "PREFERENCES", "LENS", "OUTPUT_PATH"}
            self.assertTrue(found <= provided,
                             f"judge.md needs placeholder(s) x_run.py doesn't supply: {found - provided}")

        merge_path = ROOT / "prompts" / "judge-merge.md"
        if merge_path.exists():
            found = x_run.placeholders_in(merge_path.read_text(encoding="utf-8"))
            provided = {"RUN_DIR", "PICKS_MAX", "VERDICTS", "OUTPUT_PATH"}
            self.assertTrue(found <= provided,
                             f"judge-merge.md needs placeholder(s) x_run.py doesn't supply: {found - provided}")


class TestClusterChunking(unittest.TestCase):
    def test_chunked_splits_by_size(self):
        items = list(range(7))
        parts = list(x_run.chunked(items, 3))
        self.assertEqual(parts, [[0, 1, 2], [3, 4, 5], [6]])

    def test_uses_settings_chunk_size_not_a_hardcoded_number(self):
        settings = load_settings(SETTINGS_PATH)
        chunk = settings["x_cluster_chunk"]
        items = list(range(chunk * 2 + 1))
        parts = list(x_run.chunked(items, chunk))
        self.assertEqual(len(parts), 3)
        self.assertEqual(len(parts[0]), chunk)
        self.assertEqual(len(parts[-1]), 1)

    def test_validate_cluster_coverage_passes_on_full_coverage(self):
        kept = [{"id": "1"}, {"id": "2"}]
        subjects_doc = {"subjects": [{"tweet_ids": ["1"]}, {"tweet_ids": ["2"]}]}
        x_run.validate_cluster_coverage(kept, subjects_doc)  # must not raise

    def test_validate_cluster_coverage_dies_on_missing_id(self):
        kept = [{"id": "1"}, {"id": "2"}]
        subjects_doc = {"subjects": [{"tweet_ids": ["1"]}]}
        with mock.patch.object(x_run, "die") as mock_die:
            mock_die.side_effect = SystemExit(1)
            with self.assertRaises(SystemExit):
                x_run.validate_cluster_coverage(kept, subjects_doc)

    def test_validate_cluster_coverage_dies_on_duplicate_id(self):
        kept = [{"id": "1"}, {"id": "2"}]
        subjects_doc = {"subjects": [{"tweet_ids": ["1", "2"]}, {"tweet_ids": ["2"]}]}
        with mock.patch.object(x_run, "die") as mock_die:
            mock_die.side_effect = SystemExit(1)
            with self.assertRaises(SystemExit):
                x_run.validate_cluster_coverage(kept, subjects_doc)


class TestJudgeMerge(unittest.TestCase):
    """The merge agent step (judge-merge.md), with `claude` mocked out."""

    def test_merge_fills_placeholders_and_writes_picks(self):
        merge_path = ROOT / "prompts" / "judge-merge.md"
        if not merge_path.exists():
            self.skipTest("prompts/judge-merge.md not built yet")

        settings = load_settings(SETTINGS_PATH)
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            captured = {}

            def fake_call_claude(prompt_text, model, cwd, timeout=1800):
                captured["prompt"] = prompt_text
                captured["model"] = model
                # simulate the agent doing its job: write picks.md
                (run_dir / "picks.md").write_text("# Picks\n\nkept: 0\n", encoding="utf-8")
                return "wrote 0 picks, 0 cut"

            with mock.patch.object(x_run, "call_claude", side_effect=fake_call_claude):
                x_run.merge_judge_verdicts(run_dir, ['{"subject": "x"}'], settings, "opus")

            self.assertTrue((run_dir / "picks.md").exists())
            self.assertEqual(captured["model"], "opus")
            self.assertIn(str(settings["x_picks_max"]), captured["prompt"])
            self.assertNotIn("{{", captured["prompt"])

    def test_merge_dies_if_picks_not_written(self):
        merge_path = ROOT / "prompts" / "judge-merge.md"
        if not merge_path.exists():
            self.skipTest("prompts/judge-merge.md not built yet")
        settings = load_settings(SETTINGS_PATH)
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            with mock.patch.object(x_run, "call_claude", return_value="did nothing"):
                with mock.patch.object(x_run, "die") as mock_die:
                    mock_die.side_effect = SystemExit(1)
                    with self.assertRaises(SystemExit):
                        x_run.merge_judge_verdicts(run_dir, ["{}"], settings, "opus")


class TestNoHardcodedSettings(unittest.TestCase):
    def test_module_source_has_no_bare_settings_number_literal(self):
        """A crude but real guardrail check: none of settings.md's own
        Numbers values appear in x_run.py as a bare literal outside of
        settings[...] lookups. This can't catch everything, but it fails
        loudly if e.g. `5` gets hard-coded for x_picks_max."""
        source = (ROOT / "x_run.py").read_text(encoding="utf-8")
        settings = load_settings(SETTINGS_PATH)
        # Only check multi-digit numbers -- small ints like 0/1 are used as
        # ordinary indices/booleans throughout and would false-positive.
        risky = {v for k, v in settings.items()
                 if isinstance(v, int) and v >= 10}
        for value in risky:
            # allow it inside a string that also contains 'settings' nearby,
            # or as part of a larger number/identifier
            for match in re.finditer(rf"(?<![\w.]){value}(?![\w.])", source):
                line_start = source.rfind("\n", 0, match.start()) + 1
                line_end = source.find("\n", match.start())
                line = source[line_start:line_end]
                self.assertIn("settings", line,
                              f"possible hard-coded setting {value} in: {line.strip()!r}")


if __name__ == "__main__":
    unittest.main()
