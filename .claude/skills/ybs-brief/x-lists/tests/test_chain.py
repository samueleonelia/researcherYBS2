#!/usr/bin/env python3
"""Tests for x_run.py -- the lane's own plumbing.

These do NOT launch an agent (no cost, no network, no judgment to fake) and
do NOT drive a browser. `next_lane` is driven on temp folders seeded with
the files the scrape and the agents would have left, and what it prints is
checked: which prompt files it writes, which launches it prints, when it
retries, when it gives up, and when it moves on. The only script it runs
for real is x_score.py, which is fast. They cover:

  - a run folder is named runs/<YYYY-MM-DD>-<HHMM> in UTC and never collides
  - a missing step script fails with a message naming that step, not a
    traceback
  - prompt placeholders are discovered from the file, not assumed, and an
    unfillable placeholder fails clearly
  - read: batches cover every link once at x_read_batch, each in a task
    space of its own; a usable note is never read again; pass 2 covers only
    what pass 1 left; after pass 2 the unavailable note is written in code
  - cluster: one launch under the chunk, parts and a merge above it; an
    invalid subjects.json is set aside and the retry prompt quotes why; a
    second bad one fails the lane; zero kept tweets skips the agent; the
    score runs once the file is valid
  - judge: one launch per subject without a verdict, two attempts, then the
    subject is left out; all left out fails the lane
  - judge-merge and write: one launch, one retry, then failed; done once
    brief.md exists
  - every launch is `Read <abs path> and follow it.`, no prompt file holds
    an unfilled placeholder, and no settings number is hard-coded here
"""

import ast
import contextlib
import io
import json
import re
import shutil
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

SETTINGS_PATH = ROOT.parents[3] / "settings.md"   # one settings.md, at the project root
PROJECT_ROOT = ROOT.parents[3]
FIXTURE = ROOT / "tests" / "fixtures" / "tweets.json"

NOTE = ("# {tid}\n\n- id: {tid}\n- status: ok\n\n## full_text\n\n{text}\n\n"
        "## quoted\n\n(none)\n\n## media\n\n(none)\n")


def links_md(n, start=1000):
    lines = ["## POST"]
    for i in range(n):
        lines.append(f"- author: @acct{i}")
        lines.append(f"https://x.com/acct{i}/status/{start + i}")
    return "\n".join(lines) + "\n"


def write_note(notes_dir: Path, tid: str, text="hello"):
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / f"{tid}.md").write_text(NOTE.format(tid=tid, text=text), encoding="utf-8")


def ids_in_prompt(path: Path):
    return re.findall(r"^id:\s*(\d+)\s*$", path.read_text(encoding="utf-8"), re.M)


def prompt_of(launch: dict) -> Path:
    m = re.fullmatch(r"Read (.+) and follow it\.", launch["prompt"])
    assert m, launch["prompt"]
    return Path(m.group(1))


class LaneCase(unittest.TestCase):
    """A temp run folder named the way a real one is, with quiet stderr."""

    def setUp(self):
        self.td = tempfile.mkdtemp()
        self.run_dir = Path(self.td) / "2026-09-06-0954"
        self.run_dir.mkdir()
        self.settings = load_settings(SETTINGS_PATH)

    def tearDown(self):
        shutil.rmtree(self.td, ignore_errors=True)

    def seed(self, n_links=0, kept=None):
        (self.run_dir / "links.md").write_text(links_md(n_links), encoding="utf-8")
        x_run.write_json(self.run_dir / "kept.json", {"kept": kept or []})

    def seed_from_fixture(self):
        """A real kept.json and links.md: the fixture through x_filter.py."""
        shutil.copy(FIXTURE, self.run_dir / "tweets.json")
        r = subprocess.run([sys.executable, str(ROOT / "x_filter.py"),
                            "--run-dir", str(self.run_dir), "--settings", str(SETTINGS_PATH)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [t["id"] for t in json.loads((self.run_dir / "kept.json").read_text())["kept"]]

    def next(self):
        with contextlib.redirect_stderr(io.StringIO()):
            return x_run.next_lane(self.run_dir, self.settings, SETTINGS_PATH, PROJECT_ROOT)

    def next_dies(self):
        with mock.patch.object(x_run, "die") as mock_die:
            mock_die.side_effect = SystemExit(1)
            with self.assertRaises(SystemExit):
                self.next()
            return mock_die.call_args[0][0]


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
            self.assertLessEqual(stamp, after.replace(second=0, microsecond=0))

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
            with self.assertRaises(SystemExit):
                x_run.run_script_step(1, "no_such_script.py", run_dir, SETTINGS_PATH)

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

    def test_scrape_fails_clearly_with_no_settings(self):
        """`x_run.py scrape` with a settings path that does not exist: an
        ERROR line, never a traceback, and no scrape is attempted (a real
        one would open the browser, which no test may do)."""
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(
                [sys.executable, str(ROOT / "x_run.py"), "scrape", "--run-dir", td,
                 "--settings", str(Path(td) / "no-settings.md")],
                capture_output=True, text=True, cwd=str(ROOT), timeout=60)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("ERROR:", r.stderr)
            self.assertIn("no settings file", r.stderr)
            self.assertNotIn("Traceback", r.stderr)
            self.assertFalse((Path(td) / "tweets.json").exists())

    def test_next_refuses_a_folder_the_scrape_did_not_fill(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(x_run, "die") as mock_die:
                mock_die.side_effect = SystemExit(1)
                with self.assertRaises(SystemExit):
                    x_run.next_lane(Path(td), load_settings(SETTINGS_PATH), SETTINGS_PATH,
                                    PROJECT_ROOT)
                self.assertIn("links.md", mock_die.call_args[0][0])


class TestPlaceholders(unittest.TestCase):
    def test_placeholders_in_finds_every_slot(self):
        template = "a {{FOO}} b {{BAR}} c {{FOO}}"
        self.assertEqual(x_run.placeholders_in(template), {"FOO", "BAR"})

    def test_fill_template_substitutes_every_slot(self):
        template = "x={{A}} y={{B}}"
        out = x_run.fill_template(template, {"A": "1", "B": "2"})
        self.assertEqual(out, "x=1 y=2")

    def test_fill_template_dies_on_unknown_placeholder(self):
        template = "x={{A}} y={{B}}"
        with mock.patch.object(x_run, "die") as mock_die:
            mock_die.side_effect = SystemExit(1)
            with self.assertRaises(SystemExit):
                x_run.fill_template(template, {"A": "1"})
            self.assertIn("B", str(mock_die.call_args[0][0]))

    def test_real_prompt_placeholders_are_discovered_not_assumed(self):
        """Whatever names the six prompt files actually use, the lane must
        supply them all. The values here are the keys each phase fills."""
        provided = {
            "read.md": {"RUN_DIR", "NOTES_DIR", "TASK_SPACE", "BATCH_NOTE", "LINKS",
                        "ALLOWED_URLS"},
            "cluster.md": {"RUN_DIR", "TWEETS", "PART_NOTE", "OUTPUT_PATH"},
            "cluster-merge.md": {"RUN_DIR", "PARTS", "PART_SUBJECTS", "ALL_TWEET_IDS",
                                 "OUTPUT_PATH"},
            "judge.md": {"RUN_DIR", "SUBJECT", "SCORE_TAG", "FLAGS", "MEASURES",
                         "VELOCITY_RANK", "CURIOUS_PERCENTILE", "TWEETS", "PROFILE_DATE",
                         "PROFILE", "PREFERENCES", "LENS", "OUTPUT_PATH"},
            "judge-merge.md": {"RUN_DIR", "PICKS_MAX", "VERDICTS", "OUTPUT_PATH"},
            "write.md": {"RUN_DIR", "RUN_NAME", "WINDOW_HOURS", "RUN_DATETIME",
                         "SUBJECTS_JUDGED", "WORDS_PER_SENTENCE_MAX", "OUTPUT_PATH",
                         "PICKS", "NOTES", "TEMPLATE", "LENS", "PREFERENCES"},
        }
        for name, keys in provided.items():
            path = ROOT / "prompts" / name
            self.assertTrue(path.exists(), f"prompts/{name} is missing")
            found = x_run.placeholders_in(path.read_text(encoding="utf-8"))
            self.assertTrue(found <= keys,
                            f"{name} needs placeholder(s) the lane does not supply: {found - keys}")


class TestChunking(unittest.TestCase):
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


class TestCoverage(unittest.TestCase):
    def test_passes_on_full_coverage(self):
        kept = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        doc = {"subjects": [{"subject": "a", "tweet_ids": ["1", "2"]},
                            {"subject": "b", "tweet_ids": ["3"]}]}
        self.assertIsNone(x_run.cluster_coverage_problem(kept, doc))
        x_run.validate_cluster_coverage(kept, doc)  # must not raise

    def test_names_a_missing_id(self):
        kept = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        doc = {"subjects": [{"subject": "a", "tweet_ids": ["1", "2"]}]}
        problem = x_run.cluster_coverage_problem(kept, doc)
        self.assertIn("missing", problem)
        self.assertIn("3", problem)

    def test_names_a_duplicated_id(self):
        kept = [{"id": "1"}, {"id": "2"}]
        doc = {"subjects": [{"subject": "a", "tweet_ids": ["1", "2"]},
                            {"subject": "b", "tweet_ids": ["2"]}]}
        self.assertIn("two subjects", x_run.cluster_coverage_problem(kept, doc))

    def test_names_a_file_of_the_wrong_shape(self):
        self.assertIsNotNone(x_run.cluster_coverage_problem([{"id": "1"}], ["not", "a", "dict"]))
        self.assertIsNotNone(x_run.cluster_coverage_problem([{"id": "1"}], {"items": []}))


class TestReadPhase(LaneCase):
    def test_batches_cover_every_link_once_at_the_settings_batch_size(self):
        self.seed(n_links=10)
        size = self.settings["x_read_batch"]
        out = self.next()
        self.assertEqual(out["phase"], "read")
        self.assertEqual(out["attempt"], 1)
        self.assertEqual(len(out["launch"]), -(-10 // size))
        seen = []
        for launch in out["launch"]:
            self.assertEqual(launch["agent"], "ybs4-x-reader")
            path = prompt_of(launch)
            self.assertTrue(path.is_absolute() and path.exists(), path)
            self.assertNotIn("{{", path.read_text(encoding="utf-8"))
            ids = ids_in_prompt(path)
            self.assertLessEqual(len(ids), size)
            seen += ids
        self.assertEqual(sorted(seen), [str(1000 + i) for i in range(10)])
        self.assertEqual(len(seen), len(set(seen)), "a link was read by more than one batch")
        self.assertEqual([l["description"] for l in out["launch"]][:2],
                         ["x read p1 b1", "x read p1 b2"])

    def test_each_batch_and_each_pass_gets_its_own_task_space(self):
        self.seed(n_links=6)
        spaces = []
        for _ in range(2):          # pass 1, then pass 2 with nothing written
            out = self.next()
            for launch in out["launch"]:
                m = re.search(r"Browser task space to use:\s*`?([^`\n]+)",
                              prompt_of(launch).read_text(encoding="utf-8"))
                self.assertIsNotNone(m)
                spaces.append(m.group(1).strip())
        self.assertEqual(len(spaces), 2 * -(-6 // self.settings["x_read_batch"]))
        self.assertEqual(len(set(spaces)), len(spaces), "two batches shared one task space")

    def test_links_that_already_have_a_note_are_not_read_again(self):
        self.seed(n_links=6)
        for tid in ("1000", "1001", "1002", "1003"):
            write_note(self.run_dir / "notes", tid)
        out = self.next()
        seen = [tid for l in out["launch"] for tid in ids_in_prompt(prompt_of(l))]
        self.assertEqual(sorted(seen), ["1004", "1005"])
        self.assertIn("4 link(s) already have a usable note", out["notes"])
        self.assertIn("hello", (self.run_dir / "notes" / "1000.md").read_text(encoding="utf-8"))

    def test_an_empty_note_does_not_count_as_read(self):
        self.seed(n_links=2)
        notes_dir = self.run_dir / "notes"
        notes_dir.mkdir()
        (notes_dir / "1000.md").write_text(
            "# 1000\n\n- id: 1000\n- status: ok\n\n## full_text\n\n(none)\n", encoding="utf-8")
        write_note(notes_dir, "1001")
        out = self.next()
        seen = [tid for l in out["launch"] for tid in ids_in_prompt(prompt_of(l))]
        self.assertEqual(seen, ["1000"])

    def test_pass_two_covers_only_what_pass_one_left(self):
        self.seed(n_links=4)
        out = self.next()
        self.assertEqual(out["attempt"], 1)
        # every agent writes only the first note of its batch
        for launch in out["launch"]:
            write_note(self.run_dir / "notes", ids_in_prompt(prompt_of(launch))[0])
        out = self.next()
        self.assertEqual((out["phase"], out["attempt"]), ("read", 2))
        seen = sorted(tid for l in out["launch"] for tid in ids_in_prompt(prompt_of(l)))
        missing = sorted(tid for tid in ("1000", "1001", "1002", "1003")
                         if not (self.run_dir / "notes" / f"{tid}.md").exists())
        self.assertEqual(seen, missing)
        self.assertTrue(any("re-reading once" in n for n in out["notes"]), out["notes"])
        self.assertTrue(all(l["description"].startswith("x read p2 b") for l in out["launch"]))

    def test_after_pass_two_the_unavailable_note_is_written_in_code(self):
        self.seed(n_links=2)
        self.next()                      # pass 1, nothing written
        self.next()                      # pass 2, nothing written
        out = self.next()                # code writes the notes and moves on
        self.assertNotEqual(out["phase"], "read")
        self.assertTrue(any("written here in code" in n for n in out["notes"]), out["notes"])
        for tid in ("1000", "1001"):
            text = (self.run_dir / "notes" / f"{tid}.md").read_text(encoding="utf-8")
            note = x_run.parse_note(text)
            self.assertEqual(note["status"], "unavailable")
            self.assertIn("no note after two read passes", text)
            self.assertEqual(note["full_text"], "",
                             "the code-written note must read as empty, not as text")
        # the pass files are the record: two passes, never three
        self.assertEqual(len(list((self.run_dir / "prompts").glob("read-p3-*.md"))), 0)
        # and tweet_block falls back to the feed text for the unread tweet
        block = x_run.tweet_block({"id": "1000", "author": "@acct0",
                                   "text": "the collapsed preview"}, x_run.load_notes(self.run_dir))
        self.assertIn("the collapsed preview", block)

    def test_no_links_means_no_read(self):
        self.seed(n_links=0)
        out = self.next()
        self.assertNotEqual(out["phase"], "read")
        self.assertEqual(len(list((self.run_dir / "prompts").glob("read-*.md"))), 0)


class TestClusterPhase(LaneCase):
    def subjects_for(self, ids, n=2):
        cut = -(-len(ids) // n)
        return {"subjects": [{"subject": f"s{k}", "tweet_ids": ids[k * cut:(k + 1) * cut]}
                             for k in range(n) if ids[k * cut:(k + 1) * cut]]}

    def read_done(self):
        """Every link noted, so the lane is past the read phase."""
        for link in x_run.parse_links_md(self.run_dir / "links.md"):
            write_note(self.run_dir / "notes", link["id"])

    def test_one_launch_under_the_chunk(self):
        ids = self.seed_from_fixture()
        self.assertLessEqual(len(ids), self.settings["x_cluster_chunk"])
        self.read_done()
        out = self.next()
        self.assertEqual((out["phase"], out["attempt"]), ("cluster", 1))
        self.assertEqual(len(out["launch"]), 1)
        self.assertEqual(out["launch"][0]["agent"], "ybs4-x-cluster")
        self.assertEqual(out["launch"][0]["description"], "x cluster a1")
        text = prompt_of(out["launch"][0]).read_text(encoding="utf-8")
        self.assertNotIn("{{", text)
        self.assertEqual(sorted(ids_in_prompt(prompt_of(out["launch"][0]))), sorted(ids))
        self.assertIn(str(self.run_dir / "subjects.json"), text)

    def test_an_invalid_file_is_set_aside_and_the_retry_quotes_why(self):
        ids = self.seed_from_fixture()
        self.read_done()
        self.next()
        x_run.write_json(self.run_dir / "subjects.json", self.subjects_for(ids[:-1]))
        out = self.next()
        self.assertEqual((out["phase"], out["attempt"]), ("cluster", 2))
        self.assertTrue((self.run_dir / "subjects.invalid-a1.json").exists())
        self.assertFalse((self.run_dir / "subjects.json").exists())
        text = prompt_of(out["launch"][0]).read_text(encoding="utf-8")
        self.assertIn("Your last attempt was rejected", text)
        self.assertIn(ids[-1], text)           # the missing id is named
        self.assertTrue(any("set aside" in n for n in out["notes"]), out["notes"])
        # a second bad file ends the lane
        x_run.write_json(self.run_dir / "subjects.json", self.subjects_for(ids[:-1]))
        out = self.next()
        self.assertEqual(out["phase"], "failed")
        self.assertIn("cluster", out["reason"])
        self.assertIn("2 attempts", out["reason"])

    def test_no_file_at_all_gets_one_retry_then_fails(self):
        self.seed_from_fixture()
        self.read_done()
        self.next()
        out = self.next()
        self.assertEqual((out["phase"], out["attempt"]), ("cluster", 2))
        self.assertIn("wrote no file", prompt_of(out["launch"][0]).read_text(encoding="utf-8"))
        out = self.next()
        self.assertEqual(out["phase"], "failed")

    def test_a_valid_file_is_scored_and_the_lane_moves_on(self):
        ids = self.seed_from_fixture()
        self.read_done()
        self.next()
        x_run.write_json(self.run_dir / "subjects.json", self.subjects_for(ids))
        out = self.next()
        self.assertEqual(out["phase"], "judge")
        subjects = json.loads((self.run_dir / "subjects.json").read_text())["subjects"]
        self.assertTrue(all("velocity_rank" in s and "tag" in s for s in subjects))

    def test_zero_kept_tweets_skips_the_agent(self):
        self.seed(n_links=0, kept=[])
        out = self.next()
        self.assertNotIn(out["phase"], ("read", "cluster"))
        self.assertEqual(json.loads((self.run_dir / "subjects.json").read_text()), {"subjects": []})
        self.assertTrue(any("nothing to group" in n for n in out["notes"]), out["notes"])
        self.assertEqual(len(list((self.run_dir / "prompts").glob("cluster*.md"))), 0)

    def test_parts_then_a_merge(self):
        chunk = self.settings["x_cluster_chunk"]
        ids = [str(2000 + i) for i in range(chunk + 2)]
        kept = [{"id": i, "author": "@a", "text": "t", "url": f"https://x.com/a/status/{i}"}
                for i in ids]
        (self.run_dir / "links.md").write_text(links_md(0), encoding="utf-8")
        x_run.write_json(self.run_dir / "kept.json", {"kept": kept})
        out = self.next()
        self.assertEqual(out["phase"], "cluster")
        self.assertEqual([l["description"] for l in out["launch"]],
                         ["x cluster part 1 a1", "x cluster part 2 a1"])
        for k, launch in enumerate(out["launch"], 1):
            self.assertIn(str(self.run_dir / f"cluster_part_{k}.json"),
                          prompt_of(launch).read_text(encoding="utf-8"))
        # part 1 written, part 2 not: only part 2 is launched again
        x_run.write_json(self.run_dir / "cluster_part_1.json",
                         {"subjects": [{"subject": "p1", "tweet_ids": ids[:chunk]}]})
        out = self.next()
        self.assertEqual([l["description"] for l in out["launch"]], ["x cluster part 2 a2"])
        x_run.write_json(self.run_dir / "cluster_part_2.json",
                         {"subjects": [{"subject": "p2", "tweet_ids": ids[chunk:]}]})
        out = self.next()
        self.assertEqual((out["phase"], out["attempt"]), ("cluster-merge", 1))
        self.assertEqual(out["launch"][0]["description"], "x cluster-merge a1")
        text = prompt_of(out["launch"][0]).read_text(encoding="utf-8")
        self.assertIn("[part 1] p1", text)
        self.assertIn("[part 2] p2", text)
        self.assertNotIn("{{", text)
        # a part missing twice fails the lane
        (self.run_dir / "cluster_part_2.json").unlink()
        out = self.next()
        self.assertEqual(out["phase"], "failed")
        self.assertIn("part 2", out["reason"])


class TestJudgePhase(LaneCase):
    def to_judge(self):
        """A run folder past the cluster phase, with two scored subjects."""
        ids = self.seed_from_fixture()
        for link in x_run.parse_links_md(self.run_dir / "links.md"):
            write_note(self.run_dir / "notes", link["id"])
        self.next()
        x_run.write_json(self.run_dir / "subjects.json",
                         {"subjects": [{"subject": "s0", "tweet_ids": ids[:3]},
                                       {"subject": "s1", "tweet_ids": ids[3:]}]})
        return ids

    def test_one_launch_per_subject_without_a_verdict(self):
        self.to_judge()
        out = self.next()
        self.assertEqual((out["phase"], out["attempt"]), ("judge", 1))
        self.assertEqual([l["description"] for l in out["launch"]],
                         ["x judge 1 a1", "x judge 2 a1"])
        for launch in out["launch"]:
            self.assertEqual(launch["agent"], "ybs4-x-judge")
            text = prompt_of(launch).read_text(encoding="utf-8")
            self.assertNotIn("{{", text)
            self.assertIn(str(self.settings["x_curious_percentile"]), text)
        self.assertIn(str(self.run_dir / "judge_2.json"),
                      prompt_of(out["launch"][1]).read_text(encoding="utf-8"))

    def test_a_subject_without_a_verdict_is_left_out_after_two_attempts(self):
        self.to_judge()
        self.next()
        x_run.write_json(self.run_dir / "judge_1.json", {"verdict": "KEEP", "why": "test"})
        out = self.next()
        self.assertEqual([l["description"] for l in out["launch"]], ["x judge 2 a2"])
        out = self.next()
        self.assertEqual((out["phase"], out["attempt"]), ("judge-merge", 1))
        self.assertTrue(any("unjudged" in n and "2" in n for n in out["notes"]), out["notes"])
        text = prompt_of(out["launch"][0]).read_text(encoding="utf-8")
        self.assertIn("KEEP", text)
        self.assertIn(str(self.settings["x_picks_max"]), text)
        self.assertEqual(out["launch"][0]["agent"], "ybs4-x-judge")

    def test_every_subject_unjudged_fails_the_lane(self):
        self.to_judge()
        self.next()
        self.next()
        out = self.next()
        self.assertEqual(out["phase"], "failed")
        self.assertIn("no subject", out["reason"])

    def test_a_verdict_that_is_not_json_counts_as_missing(self):
        self.to_judge()
        self.next()
        (self.run_dir / "judge_1.json").write_text("not json", encoding="utf-8")
        x_run.write_json(self.run_dir / "judge_2.json", {"verdict": "DROP"})
        out = self.next()
        self.assertEqual([l["description"] for l in out["launch"]], ["x judge 1 a2"])


PICKS_MD = ("# X list picks\n\n"
            "Run: 2026-09-06-0954 · subjects judged: 1 · kept: 1 · cut by the ceiling: 0\n\n"
            "## 1. Something happened\n\n"
            "- **Tag:** TRENDING\n- **Flags:** VELOCITY\n"
            "- **Storyline:** A very particular test storyline\n"
            "- **Why:** because the test says so\n"
            "- **The tweet that states it best:**\n"
            "  - @acct — https://x.com/acct/status/{tid}\n"
            "  > hello world\n")


class TestMergeAndWrite(LaneCase):
    def to_merge(self):
        self.seed(n_links=1)
        write_note(self.run_dir / "notes", "1000", "hello world")
        x_run.write_json(self.run_dir / "kept.json",
                         {"kept": [{"id": "1000", "author": "@acct0", "text": "t",
                                    "url": "https://x.com/acct0/status/1000"}]})
        x_run.write_json(self.run_dir / "subjects.json",
                         {"subjects": [{"subject": "s", "tweet_ids": ["1000"],
                                        "velocity_rank": 50, "tag": "SINGLETON", "flags": []}]})
        x_run.write_json(self.run_dir / "judge_1.json", {"verdict": "KEEP"})

    def test_merge_then_write_then_done(self):
        self.to_merge()
        out = self.next()
        self.assertEqual((out["phase"], out["attempt"]), ("judge-merge", 1))
        out = self.next()
        self.assertEqual((out["phase"], out["attempt"]), ("judge-merge", 2))
        (self.run_dir / "picks.md").write_text(PICKS_MD.format(tid="1000"), encoding="utf-8")
        out = self.next()
        self.assertEqual((out["phase"], out["attempt"]), ("write", 1))
        self.assertEqual(out["launch"][0]["agent"], "ybs4-x-write")
        self.assertEqual(out["launch"][0]["description"], "x write a1")
        prompt = prompt_of(out["launch"][0]).read_text(encoding="utf-8")
        self.assertNotIn("{{", prompt)
        self.assertIn(str(self.run_dir), prompt)                                   # RUN_DIR
        self.assertIn("2026-09-06-0954", prompt)                                   # RUN_NAME
        self.assertIn(str(self.settings["x_window_hours"]), prompt)                # WINDOW_HOURS
        self.assertIn("6 September 2026 at 09:54 UTC", prompt)                     # RUN_DATETIME
        self.assertIn(str(self.settings["x_words_per_sentence_max"]), prompt)      # WORDS_PER_SENTENCE_MAX
        self.assertIn(str(self.run_dir / "brief.md"), prompt)                      # OUTPUT_PATH
        self.assertIn("A very particular test storyline", prompt)                  # PICKS
        self.assertIn("hello world", prompt)                                       # NOTES
        self.assertIn("# X brief", prompt)                                         # TEMPLATE
        out = self.next()
        self.assertEqual((out["phase"], out["attempt"]), ("write", 2))
        out = self.next()
        self.assertEqual(out["phase"], "failed")
        self.assertIn("write", out["reason"])
        (self.run_dir / "brief.md").write_text("# What the list is moving on\n", encoding="utf-8")
        out = self.next()
        self.assertEqual(out["phase"], "done")
        self.assertEqual(out["launch"], [])

    def test_a_merge_that_never_writes_fails_after_two(self):
        self.to_merge()
        self.next()
        self.next()
        out = self.next()
        self.assertEqual(out["phase"], "failed")
        self.assertIn("judge-merge", out["reason"])

    def test_a_pick_without_a_note_stops_the_write(self):
        self.to_merge()
        (self.run_dir / "picks.md").write_text(PICKS_MD.format(tid="222"), encoding="utf-8")
        msg = self.next_dies()
        self.assertIn("222", msg)
        self.assertIn("Something happened", msg)


class TestWriteInputs(unittest.TestCase):
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

    def test_parse_picks_md_dies_on_a_pick_with_no_permalink(self):
        with tempfile.TemporaryDirectory() as td:
            picks_path = Path(td) / "picks.md"
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
        self.assertEqual(x_run.format_run_datetime("2026-09-06-0954"),
                         "6 September 2026 at 09:54 UTC")

    def test_tolerates_a_collision_suffix(self):
        self.assertEqual(x_run.format_run_datetime("2026-09-06-0954-2"),
                         "6 September 2026 at 09:54 UTC")


class TestNextCommand(unittest.TestCase):
    def test_stdout_is_one_json_line_and_progress_goes_to_stderr(self):
        """ybs_run.py x-next reads the last line of stdout as JSON: nothing
        else may land there, whatever the phase prints along the way."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "2026-09-06-0954"
            run_dir.mkdir()
            (run_dir / "links.md").write_text(links_md(2), encoding="utf-8")
            x_run.write_json(run_dir / "kept.json", {"kept": []})
            for tid in ("1000", "1001"):
                write_note(run_dir / "notes", tid)
            r = subprocess.run(
                [sys.executable, str(ROOT / "x_run.py"), "next", "--run-dir", str(run_dir),
                 "--settings", str(SETTINGS_PATH)],
                capture_output=True, text=True, cwd=str(ROOT), timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
            self.assertEqual(len(lines), 1, r.stdout)
            out = json.loads(lines[0])
            self.assertIn("phase", out)
            self.assertIn("note(s) verified", r.stderr)


class TestNoHardcodedSettings(unittest.TestCase):
    def test_module_source_has_no_bare_settings_number_literal(self):
        """A crude but real guardrail check: none of settings.md's own
        Numbers values appear in x_run.py as a bare literal outside of
        settings[...] lookups. This can't catch everything, but it fails
        loudly if e.g. `5` gets hard-coded for x_picks_max.

        The module docstring is prose, not code: it explains the lane and
        lists the ten finish-line checks, so its numbered rows are not
        settings values and are skipped. Everything below it is checked."""
        source = (ROOT / "x_run.py").read_text(encoding="utf-8")
        settings = load_settings(SETTINGS_PATH)

        tree = ast.parse(source)
        doc_lines = set()
        if (tree.body and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)):
            node = tree.body[0]
            doc_lines = set(range(node.lineno, node.end_lineno + 1))
        self.assertTrue(doc_lines, "x_run.py lost its module docstring")

        risky = {v for k, v in settings.items()
                 if isinstance(v, int) and v >= 10}
        for value in risky:
            for match in re.finditer(rf"(?<![\w.]){value}(?![\w.])", source):
                lineno = source.count("\n", 0, match.start()) + 1
                if lineno in doc_lines:
                    continue
                line_start = source.rfind("\n", 0, match.start()) + 1
                line_end = source.find("\n", match.start())
                line = source[line_start:line_end]
                self.assertIn("settings", line,
                              f"possible hard-coded setting {value} in: {line.strip()!r}")


if __name__ == "__main__":
    unittest.main()
