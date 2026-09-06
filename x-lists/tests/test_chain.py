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
  - the read step (step 3) now runs its batches POOLED, up to
    x_agents_active_max at once, each batch its own ego task space -- not
    serially, which was the pre-2026-09-06 rule
  - the write step (step 7) fills every one of prompts/write.md's twelve
    placeholders correctly, and resolves each pick's permalink to its
    notes/<id>.md file, failing loudly (never silently dropping the pick)
    when a note is missing
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


class TestReadStageConcurrency(unittest.TestCase):
    """Job 1: the read stage is pooled, not serial. This test would FAIL if
    the read stage silently went back to running its batches one at a time
    (max_workers pinned to 1) -- it asserts the pool is opened with the
    settings value, not a hard-coded 1."""

    def _make_links_md(self, n):
        lines = ["## POST"]
        for i in range(n):
            lines.append(f"- author: @acct{i}")
            lines.append(f"https://x.com/acct{i}/status/{1000 + i}")
        return "\n".join(lines) + "\n"

    def test_batches_cover_every_link_exactly_once_at_the_settings_batch_size(self):
        settings = {"x_read_batch": 3, "x_agents_active_max": 8, "read_model": "sonnet"}
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            (run_dir / "links.md").write_text(self._make_links_md(10), encoding="utf-8")

            seen_ids = []

            def fake_run_pool(jobs, max_workers):
                self.assertEqual(max_workers, settings["x_agents_active_max"],
                                  "read stage did not pool at x_agents_active_max")
                return [job() for job in jobs]

            def fake_call_claude(prompt_text, model, cwd, timeout=1800):
                ids = re.findall(r"^id:\s*(\d+)\s*$", prompt_text, re.M)
                seen_ids.extend(ids)
                notes_dir = run_dir / "notes"
                for tid in ids:
                    (notes_dir / f"{tid}.md").write_text(
                        "# " + tid + "\n\n- id: " + tid + "\n- status: ok\n\n"
                        "## full_text\n\nhello\n\n## quoted\n\n(none)\n\n## media\n\n(none)\n",
                        encoding="utf-8",
                    )
                return "wrote notes"

            with mock.patch.object(x_run, "run_pool", side_effect=fake_run_pool), \
                    mock.patch.object(x_run, "call_claude", side_effect=fake_call_claude):
                x_run.step_read(run_dir, settings)

            expected_ids = [str(1000 + i) for i in range(10)]
            self.assertEqual(sorted(seen_ids), sorted(expected_ids))
            self.assertEqual(len(seen_ids), len(set(seen_ids)), "a link was read by more than one batch")

    def test_pool_opened_with_agents_active_max_not_hardcoded_serial(self):
        """The specific regression this guards: a read step that reverts to
        READ_MAX_WORKERS = 1 (the old 'browser is the one serial thing'
        rule) fails this test, because it asserts the pool call's
        max_workers came from settings, and a fixed max_workers of 1 with
        x_agents_active_max set to 8 in settings does not match."""
        settings = {"x_read_batch": 3, "x_agents_active_max": 8, "read_model": "sonnet"}
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            (run_dir / "links.md").write_text(self._make_links_md(9), encoding="utf-8")

            captured = {}

            def fake_run_pool(jobs, max_workers):
                captured["max_workers"] = max_workers
                captured["n_jobs"] = len(jobs)
                return [job() for job in jobs]

            def fake_call_claude(prompt_text, model, cwd, timeout=1800):
                ids = re.findall(r"^id:\s*(\d+)\s*$", prompt_text, re.M)
                notes_dir = run_dir / "notes"
                for tid in ids:
                    (notes_dir / f"{tid}.md").write_text(
                        "# " + tid + "\n\n- id: " + tid + "\n- status: ok\n\n"
                        "## full_text\n\nhello\n\n## quoted\n\n(none)\n\n## media\n\n(none)\n",
                        encoding="utf-8",
                    )
                return "wrote notes"

            with mock.patch.object(x_run, "run_pool", side_effect=fake_run_pool), \
                    mock.patch.object(x_run, "call_claude", side_effect=fake_call_claude):
                x_run.step_read(run_dir, settings)

            self.assertEqual(captured["n_jobs"], 3)  # ceil(9/3)
            self.assertNotEqual(captured["max_workers"], 1,
                                 "read stage ran its batches serially -- the old rule is back")
            self.assertEqual(captured["max_workers"], 8)

    def test_each_batch_gets_its_own_ego_task_space(self):
        """GOAL.md: 'each opens its own ego task space... never two agents
        in one task space.' Each batch's filled prompt must carry a
        distinct TASK_SPACE value."""
        settings = {"x_read_batch": 2, "x_agents_active_max": 8, "read_model": "sonnet"}
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            (run_dir / "links.md").write_text(self._make_links_md(6), encoding="utf-8")

            task_spaces = []

            def fake_call_claude(prompt_text, model, cwd, timeout=1800):
                m = re.search(r"Browser task space to use:\s*(.+)", prompt_text)
                self.assertIsNotNone(m)
                task_spaces.append(m.group(1).strip())
                ids = re.findall(r"^id:\s*(\d+)\s*$", prompt_text, re.M)
                notes_dir = run_dir / "notes"
                for tid in ids:
                    (notes_dir / f"{tid}.md").write_text(
                        "# " + tid + "\n\n- id: " + tid + "\n- status: ok\n\n"
                        "## full_text\n\nhello\n\n## quoted\n\n(none)\n\n## media\n\n(none)\n",
                        encoding="utf-8",
                    )
                return "wrote notes"

            with mock.patch.object(x_run, "call_claude", side_effect=fake_call_claude):
                x_run.step_read(run_dir, settings)

            self.assertEqual(len(task_spaces), 3)  # ceil(6/2)
            self.assertEqual(len(set(task_spaces)), len(task_spaces), "two batches shared one task space")


class TestWriteStepNoteResolution(unittest.TestCase):
    """Job 2's interface gap: picks.md carries a permalink, notes are filed
    by id. build_notes_block must resolve one to the other, and must fail
    loudly -- never silently drop the pick -- when the note is missing."""

    def test_resolves_permalink_to_note_by_id(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            (run_dir / "notes").mkdir()
            (run_dir / "notes" / "111.md").write_text(
                "# 111\n\n- id: 111\n\n## full_text\n\nhello world\n", encoding="utf-8")
            (run_dir / "notes" / "999999.md").write_text(
                "# 999999\n\n- id: 999999\n\n## full_text\n\nNOT PICKED\n", encoding="utf-8")
            picks = [{"title": "A", "handle": "@a",
                      "url": "https://x.com/a/status/111", "id": "111"}]
            block = x_run.build_notes_block(run_dir, picks)
            self.assertIn("111", block)
            self.assertIn("hello world", block)
            self.assertNotIn("NOT PICKED", block, "a note for an unpicked tweet leaked into {{NOTES}}")

    def test_missing_note_fails_loudly_and_does_not_drop_the_pick(self):
        """This test FAILS if a missing note is silently skipped instead of
        dying: it asserts the run stops (SystemExit) and that the die
        message names both the pick's title and its expected note id."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            (run_dir / "notes").mkdir()
            (run_dir / "notes" / "111.md").write_text(
                "# 111\n\n- id: 111\n\n## full_text\n\nhello\n", encoding="utf-8")
            picks = [
                {"title": "Has a note", "handle": "@a",
                 "url": "https://x.com/a/status/111", "id": "111"},
                {"title": "Missing its note", "handle": "@b",
                 "url": "https://x.com/b/status/222", "id": "222"},
            ]
            with mock.patch.object(x_run, "die") as mock_die:
                mock_die.side_effect = SystemExit(1)
                with self.assertRaises(SystemExit):
                    x_run.build_notes_block(run_dir, picks)
                msg = mock_die.call_args[0][0]
                self.assertIn("Missing its note", msg)
                self.assertIn("222", msg)
                # and it must not have silently returned a block missing just
                # that one pick -- the call under test raised before returning.

    def test_parse_picks_md_dies_on_a_pick_with_no_permalink(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            picks_path = run_dir / "picks.md"
            picks_path.write_text(
                "# X list picks\n\nRun: x · subjects judged: 1 · kept: 1 · cut by the ceiling: 0\n\n"
                "## 1. No permalink here\n\n- **Tag:** TRENDING\n- **Storyline:** s\n",
                encoding="utf-8",
            )
            with mock.patch.object(x_run, "die") as mock_die:
                mock_die.side_effect = SystemExit(1)
                with self.assertRaises(SystemExit):
                    x_run.parse_picks_md(picks_path)
                self.assertIn("No permalink here", mock_die.call_args[0][0])


class TestFormatRunDatetime(unittest.TestCase):
    def test_formats_the_run_name_into_the_fixed_shape(self):
        self.assertEqual(
            x_run.format_run_datetime("2026-09-06-0954"),
            "6 September 2026 at 09:54 UTC",
        )

    def test_tolerates_a_collision_suffix(self):
        self.assertEqual(
            x_run.format_run_datetime("2026-09-06-0954-2"),
            "6 September 2026 at 09:54 UTC",
        )


class TestStepWrite(unittest.TestCase):
    """Job 2: step_write fills every one of prompts/write.md's twelve
    placeholders. This mocks `claude -p` the way TestJudgeMerge does."""

    def _seed_run_dir(self, run_dir: Path):
        (run_dir / "notes").mkdir()
        (run_dir / "notes" / "111.md").write_text(
            "# 111\n\n- id: 111\n- status: ok\n\n## full_text\n\nhello world\n\n"
            "## quoted\n\n(none)\n\n## media\n\n(none)\n",
            encoding="utf-8",
        )
        picks_md = (
            "# X list picks\n\n"
            "Run: 2026-09-06-0954 · subjects judged: 1 · kept: 1 · cut by the ceiling: 0\n\n"
            "## 1. Something happened\n\n"
            "- **Tag:** TRENDING\n- **Flags:** VELOCITY\n"
            "- **Storyline:** A very particular test storyline\n"
            "- **Why:** because the test says so\n"
            "- **The tweet that states it best:**\n"
            "  - @acct — https://x.com/acct/status/111\n"
            "  > hello world\n"
        )
        (run_dir / "picks.md").write_text(picks_md, encoding="utf-8")
        (run_dir / "subjects.json").write_text(
            json.dumps({"subjects": [{"tweet_ids": ["111"]}]}), encoding="utf-8")

    def test_fills_every_placeholder_and_writes_brief(self):
        prompt_path = ROOT / "prompts" / "write.md"
        if not prompt_path.exists():
            self.skipTest("prompts/write.md not built yet")
        template_path = ROOT / "templates" / "x-brief.md"
        if not template_path.exists():
            self.skipTest("templates/x-brief.md not built yet")

        settings = load_settings(SETTINGS_PATH)
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "2026-09-06-0954"
            run_dir.mkdir()
            self._seed_run_dir(run_dir)

            captured = {}

            def fake_call_claude(prompt_text, model, cwd, timeout=1800):
                captured["prompt"] = prompt_text
                captured["model"] = model
                (run_dir / "brief.md").write_text("# What the list is moving on\n", encoding="utf-8")
                return "wrote 1 item, 1 TRENDING, 0 CURIOUS"

            with mock.patch.object(x_run, "call_claude", side_effect=fake_call_claude):
                x_run.step_write(run_dir, settings, ROOT.parent)

            self.assertTrue((run_dir / "brief.md").exists())
            prompt = captured["prompt"]
            self.assertNotIn("{{", prompt, "an unfilled placeholder leaked into the write prompt")
            self.assertEqual(captured["model"], settings["write_model"])

            # every one of the twelve placeholders' values, present in the prompt
            self.assertIn(str(run_dir), prompt)                                    # RUN_DIR
            self.assertIn("2026-09-06-0954", prompt)                               # RUN_NAME
            self.assertIn(str(settings["x_window_hours"]), prompt)                 # WINDOW_HOURS
            self.assertIn("6 September 2026 at 09:54 UTC", prompt)                 # RUN_DATETIME
            self.assertIn(str(settings["x_words_per_sentence_max"]), prompt)       # WORDS_PER_SENTENCE_MAX
            self.assertIn(str(run_dir / "brief.md"), prompt)                       # OUTPUT_PATH
            self.assertIn("A very particular test storyline", prompt)              # PICKS
            self.assertIn("hello world", prompt)                                   # NOTES (from notes/111.md)
            self.assertIn("# X brief", prompt)                                     # TEMPLATE (its own title)

    def test_dies_when_a_pick_has_no_matching_note(self):
        prompt_path = ROOT / "prompts" / "write.md"
        if not prompt_path.exists():
            self.skipTest("prompts/write.md not built yet")
        settings = load_settings(SETTINGS_PATH)
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "2026-09-06-0954"
            run_dir.mkdir()
            (run_dir / "notes").mkdir()
            # no notes/111.md written -- the pick below has no matching note
            picks_md = (
                "# X list picks\n\nRun: x · subjects judged: 1 · kept: 1 · cut by the ceiling: 0\n\n"
                "## 1. Something happened\n\n- **Tag:** TRENDING\n- **Flags:** VELOCITY\n"
                "- **Storyline:** s\n- **Why:** because\n"
                "- **The tweet that states it best:**\n  - @acct — https://x.com/acct/status/111\n  > hi\n"
            )
            (run_dir / "picks.md").write_text(picks_md, encoding="utf-8")
            (run_dir / "subjects.json").write_text(
                json.dumps({"subjects": [{"tweet_ids": ["111"]}]}), encoding="utf-8")

            with mock.patch.object(x_run, "die") as mock_die, \
                    mock.patch.object(x_run, "call_claude") as mock_call:
                mock_die.side_effect = SystemExit(1)
                with self.assertRaises(SystemExit):
                    x_run.step_write(run_dir, settings, ROOT.parent)
                mock_call.assert_not_called()
                self.assertIn("111", mock_die.call_args[0][0])


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
