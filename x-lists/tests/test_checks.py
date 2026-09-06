#!/usr/bin/env python3
"""Tests for x_checks.py -- the mechanical, JSON-only checks.

Covers, from JSON alone:
  1. tweets.json schema + x_tweets_min
  2. the window rule (reposts included, cut at the first run of
     x_stop_after_old old non-reposts)
  3. kept.json holds exactly what the six filter rules say, in order
  4. every kept id in exactly one subject
  5. every subject carries authors/lists/endorsements/velocity/
     velocity_rank/cross_list/flags(+tag)
  8. links.md lists exactly the kept tweets, correctly marked POST/REPOST

Checks 1 and 2 run against the real fixture. Check 3 runs the real
x_filter.py against the fixture (when it exists) and validates its output
against an independent recomputation of the rules; it also runs a
synthetic case built to discriminate the window ruling from the older,
looser reading a verifier already caught once (see RUNLOG.md attempt 7).
Checks 4 and 5 run against a hand-built subjects.json plus the real
x_score.py's enrichment of it (when it exists). Check 8 runs the real
x_filter.py's links.md against an independent parse/recompute.

The fixture (tests/fixtures/tweets.json) was extended on 2026-09-06 with
four records, ids ...016-...019, to cover the rule-6 engagement floor and
the reply-with-link rule-order case (none of the original 15 exercised
rule 6 under the amended rules):
  - ...016: is_reply=true AND has_link=true -- must be dropped by rule 2
    (reply), not rule 4 (link), proving rule order.
  - ...017: has_link=false, words>=6, reposts=15 (>= x_min_reposts=10),
    likes=5 (< x_min_likes=100) -- clears the engagement floor on reposts
    alone, so it is kept.
  - ...018: reposts=2 (< 10), likes=150 (>= x_min_likes=100) -- clears the
    floor on likes alone, so it is kept.
  - ...019: reposts=3, likes=20 -- clears neither, dropped by rule 6.
  All four are inserted before the existing old-tweet run (between
  ...012 and ...013) so they stay inside the window and don't disturb the
  run of 3 old non-reposts that rule 3's tests depend on. No existing
  record's content changed.

  With the extended fixture, expected_filter() now gives: kept =
  {1,2,6,9,10,11,12,17,18} (9), dropped = {3:2, 4:4, 5:4, 7:1, 8:5, 16:2,
  19:6, 13:3, 14:3, 15:3} (10) -- confirmed against x_filter.py's real
  output, which matches exactly.
"""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import x_checks  # noqa: E402
from x_settings import load_settings  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "tweets.json"
SETTINGS_PATH = ROOT / "settings.md"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class TestCheck1Schema(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings(SETTINGS_PATH)
        self.doc = load_fixture()

    def _lenient_settings(self):
        # The fixture has 15 tweets, chosen for field/rule coverage, not to
        # meet the real x_tweets_min (20) -- a real scrape must clear that
        # bar (and did: a live run produced 47). Schema-completeness tests
        # here use a settings copy with the minimum lowered so they test
        # field-presence, not the fixture's tweet count.
        settings = dict(self.settings)
        settings["x_tweets_min"] = 1
        return settings

    def test_fixture_passes(self):
        ok, reason = x_checks.check1_schema(self.doc, self._lenient_settings())
        self.assertTrue(ok, reason)

    def test_fixture_is_below_the_real_x_tweets_min(self):
        # Documents a real, deliberate fact about the fixture rather than
        # hiding it: it is a coverage fixture, not a pass/fail sample.
        ok, reason = x_checks.check1_schema(self.doc, self.settings)
        self.assertFalse(ok)
        self.assertIn("x_tweets_min", reason)

    def test_missing_field_fails(self):
        doc = copy.deepcopy(self.doc)
        del doc["tweets"][0]["promoted"]
        ok, reason = x_checks.check1_schema(doc, self._lenient_settings())
        self.assertFalse(ok)
        self.assertIn("promoted", reason)

    def test_below_minimum_fails(self):
        doc = copy.deepcopy(self.doc)
        doc["tweets"] = doc["tweets"][:1]
        ok, reason = x_checks.check1_schema(doc, self.settings)
        self.assertFalse(ok)

    def test_empty_string_field_is_allowed(self):
        doc = copy.deepcopy(self.doc)
        doc["tweets"][0]["card_title"] = ""
        ok, reason = x_checks.check1_schema(doc, self._lenient_settings())
        self.assertTrue(ok, reason)


class TestCheck2Window(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings(SETTINGS_PATH)

    def test_fixture_passes(self):
        doc = load_fixture()
        ok, reason = x_checks.check2_window(doc, self.settings)
        self.assertTrue(ok, reason)

    def _tweet(self, tid, minutes_old, reposted_by="", scraped="2026-09-06T12:00:00Z"):
        # minutes_old is relative to `scraped`.
        from datetime import datetime, timedelta, timezone
        base = datetime.fromisoformat(scraped.replace("Z", "+00:00"))
        posted = base - timedelta(minutes=minutes_old)
        return {
            "id": tid, "url": f"https://x.com/x/status/{tid}", "list": "B",
            "author": "@x", "reposted_by": reposted_by,
            "posted_at": posted.strftime("%Y-%m-%dT%H:%M:%SZ"), "seen_at": scraped,
            "text": "some words here to pass the word count easily today",
            "card_title": "", "quoted_text": "", "is_reply": False,
            "has_link": False, "promoted": False,
            "replies": 0, "reposts": 0, "likes": 0, "views": 100,
        }

    def test_isolated_old_tweet_stays_in_window(self):
        """The ruling in interfaces.md: a single old non-repost, not part of
        a run of x_stop_after_old, is still inside the window. This is the
        exact case the old ('cut at the first old non-repost') reading gets
        wrong."""
        settings = dict(self.settings)
        settings["x_window_hours"] = 1
        settings["x_stop_after_old"] = 3
        tweets = [
            self._tweet("1", 5),     # in window
            self._tweet("2", 90),    # isolated old one -- still IN under the ruling
            self._tweet("3", 6),     # in window again, breaks the old run
            self._tweet("4", 70),    # old, run of 1 so far
            self._tweet("5", 71),    # old, run of 2
            self._tweet("6", 72),    # old, run of 3 -- THIS is the real boundary
            self._tweet("7", 200),   # old, after the boundary
        ]
        doc = {
            "list_url": "u", "account": "@a", "scraped_at": "2026-09-06T12:00:00Z",
            "window_hours": 1, "tweets": tweets,
        }
        cutoff_idx = x_checks.window_boundary(
            tweets, __import__("datetime").datetime(2026, 9, 6, 11, 0, tzinfo=__import__("datetime").timezone.utc),
            3,
        )
        self.assertEqual(cutoff_idx, 3, "boundary should start at tweet index 3 (0-based), the first of the 3-run")
        ok, reason = x_checks.check2_window(doc, settings)
        self.assertTrue(ok, reason)

    def test_repost_does_not_break_or_extend_the_run(self):
        settings = {"x_window_hours": 1, "x_stop_after_old": 2}
        tweets = [
            self._tweet("1", 70),                     # old, run=1
            self._tweet("2", 300, reposted_by="@x"),   # repost: skipped, doesn't break the run
            self._tweet("3", 71),                     # old, run=2 -> boundary here (index 0)
        ]
        boundary = x_checks.window_boundary(
            tweets, __import__("datetime").datetime(2026, 9, 6, 11, 0, tzinfo=__import__("datetime").timezone.utc),
            2,
        )
        self.assertEqual(boundary, 0)


class TestCheck3Kept(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings(SETTINGS_PATH)
        self.doc = load_fixture()

    def _run_real_filter(self, doc, with_links=False):
        script = ROOT / "x_filter.py"
        if not script.exists():
            self.skipTest("x_filter.py not built yet")
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            (run_dir / "tweets.json").write_text(json.dumps(doc), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), "--run-dir", str(run_dir),
                 "--settings", str(SETTINGS_PATH)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                self.fail(f"x_filter.py failed: {result.stderr}")
            kept_doc = json.loads((run_dir / "kept.json").read_text(encoding="utf-8"))
            if with_links:
                links_path = run_dir / "links.md"
                links_text = links_path.read_text(encoding="utf-8") if links_path.exists() else None
                return kept_doc, links_text
            return kept_doc

    def test_real_filter_matches_the_six_rules_on_the_fixture(self):
        kept_doc = self._run_real_filter(self.doc)
        ok, reason = x_checks.check3_kept(self.doc, kept_doc, self.settings)
        self.assertTrue(ok, reason)

    def test_link_with_commentary_is_dropped_by_rule_4(self):
        # id ...005: a link with plenty of its own words. Used to survive
        # under the old rule (link + fewer than x_min_own_words words);
        # under the amended rule 4 (any link at all) it is dropped.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertNotIn("1000000000000000005", exp_kept)
        self.assertEqual(exp_dropped.get("1000000000000000005"), 4)

    def test_reply_with_link_is_dropped_by_rule_2_not_rule_4(self):
        # id ...016: is_reply=true AND has_link=true. Rule order means
        # rule 2 (reply) fires before rule 4 (link) ever gets a look.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertNotIn("1000000000000000016", exp_kept)
        self.assertEqual(exp_dropped.get("1000000000000000016"), 2)

    def test_engagement_floor_cleared_by_reposts_alone(self):
        # id ...017: reposts=15 (>= x_min_reposts), likes=5 (< x_min_likes).
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertIn("1000000000000000017", exp_kept)
        self.assertNotIn("1000000000000000017", exp_dropped)

    def test_engagement_floor_cleared_by_likes_alone(self):
        # id ...018: reposts=2 (< x_min_reposts), likes=150 (>= x_min_likes).
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertIn("1000000000000000018", exp_kept)
        self.assertNotIn("1000000000000000018", exp_dropped)

    def test_engagement_floor_fails_both(self):
        # id ...019: reposts=3, likes=20 -- clears neither number.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertNotIn("1000000000000000019", exp_kept)
        self.assertEqual(exp_dropped.get("1000000000000000019"), 6)

    def test_dropped_rule_7_is_rejected(self):
        # rule must be 1..6; anything outside that range is an invalid
        # kept.json, not a real filter outcome.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        all_tweets = self.doc["tweets"]
        kept = [t for t in all_tweets if t["id"] in exp_kept]
        dropped = [{"id": tid, "rule": rule} for tid, rule in exp_dropped.items()]
        dropped[0]["rule"] = 7
        kept_doc = {"run": "test", "kept_at": "x", "kept": kept, "dropped": dropped}
        ok, reason = x_checks.check3_kept(self.doc, kept_doc, self.settings)
        self.assertFalse(ok)
        self.assertIn("invalid rule", reason)

    def test_hand_built_kept_matches_expected(self):
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        all_tweets = self.doc["tweets"]
        kept = [t for t in all_tweets if t["id"] in exp_kept]
        dropped = [{"id": tid, "rule": rule} for tid, rule in exp_dropped.items()]
        kept_doc = {"run": "test", "kept_at": "2026-09-06T12:00:00Z",
                    "kept": kept, "dropped": dropped}
        ok, reason = x_checks.check3_kept(self.doc, kept_doc, self.settings)
        self.assertTrue(ok, reason)

    def test_wrongly_dropped_tweet_fails(self):
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        all_tweets = self.doc["tweets"]
        # Drop one that should have been kept, mislabel it rule 5.
        victim = next(t["id"] for t in all_tweets if t["id"] in exp_kept)
        kept = [t for t in all_tweets if t["id"] in exp_kept and t["id"] != victim]
        dropped = [{"id": tid, "rule": rule} for tid, rule in exp_dropped.items()]
        dropped.append({"id": victim, "rule": 5})
        kept_doc = {"run": "test", "kept_at": "x", "kept": kept, "dropped": dropped}
        ok, reason = x_checks.check3_kept(self.doc, kept_doc, self.settings)
        self.assertFalse(ok)

    def test_double_bucketed_tweet_fails(self):
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        all_tweets = self.doc["tweets"]
        kept = [t for t in all_tweets if t["id"] in exp_kept]
        dropped = [{"id": tid, "rule": rule} for tid, rule in exp_dropped.items()]
        # Put the first kept tweet into dropped too.
        dropped.append({"id": kept[0]["id"], "rule": 5})
        kept_doc = {"run": "test", "kept_at": "x", "kept": kept, "dropped": dropped}
        ok, reason = x_checks.check3_kept(self.doc, kept_doc, self.settings)
        self.assertFalse(ok)


class TestCheck4And5(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings(SETTINGS_PATH)
        self.doc = load_fixture()
        exp_kept, _ = x_checks.expected_filter(self.doc, self.settings)
        self.kept = [t for t in self.doc["tweets"] if t["id"] in exp_kept]
        self.kept_doc = {"kept": self.kept}

    def _grouped_subjects(self):
        # One subject per kept tweet -- simplest valid clustering.
        return {"subjects": [{"subject": f"subject {i}", "tweet_ids": [t["id"]]}
                              for i, t in enumerate(self.kept)]}

    def test_check4_passes_on_full_coverage(self):
        subjects_doc = self._grouped_subjects()
        ok, reason = x_checks.check4_subject_coverage(self.kept_doc, subjects_doc)
        self.assertTrue(ok, reason)

    def test_check4_fails_on_missing_id(self):
        subjects_doc = self._grouped_subjects()
        subjects_doc["subjects"].pop()
        ok, reason = x_checks.check4_subject_coverage(self.kept_doc, subjects_doc)
        self.assertFalse(ok)

    def test_check4_fails_on_id_in_two_subjects(self):
        subjects_doc = self._grouped_subjects()
        dupe_id = subjects_doc["subjects"][0]["tweet_ids"][0]
        subjects_doc["subjects"][1]["tweet_ids"].append(dupe_id)
        ok, reason = x_checks.check4_subject_coverage(self.kept_doc, subjects_doc)
        self.assertFalse(ok)

    def test_check5_passes_after_real_score(self):
        script = ROOT / "x_score.py"
        if not script.exists():
            self.skipTest("x_score.py not built yet")
        subjects_doc = self._grouped_subjects()
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            kept_doc = dict(self.kept_doc, kept_at="2026-09-06T12:00:00Z")
            (run_dir / "kept.json").write_text(json.dumps(kept_doc), encoding="utf-8")
            (run_dir / "subjects.json").write_text(json.dumps(subjects_doc), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), "--run-dir", str(run_dir),
                 "--settings", str(SETTINGS_PATH)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                self.fail(f"x_score.py failed: {result.stderr}")
            scored = json.loads((run_dir / "subjects.json").read_text(encoding="utf-8"))
        ok, reason = x_checks.check5_subject_fields(scored, self.settings)
        self.assertTrue(ok, reason)
        # score must not have changed subject/tweet_ids/coverage.
        ok, reason = x_checks.check4_subject_coverage(self.kept_doc, scored)
        self.assertTrue(ok, reason)

    def test_check5_fails_on_missing_field(self):
        subjects_doc = {"subjects": [{
            "subject": "x", "tweet_ids": ["1"], "authors": 1, "lists": 1,
            "endorsements": 0, "velocity": 1.0, "velocity_rank": 50.0,
            "cross_list": False, "flags": [],
            # "tag" deliberately missing
        }]}
        ok, reason = x_checks.check5_subject_fields(subjects_doc)
        self.assertFalse(ok)

    def test_check5_fails_on_tag_flag_mismatch(self):
        subjects_doc = {"subjects": [{
            "subject": "x", "tweet_ids": ["1"], "authors": 5, "lists": 1,
            "endorsements": 0, "velocity": 1.0, "velocity_rank": 50.0,
            "cross_list": False, "flags": ["CONVERGENCE"], "tag": "SINGLETON",
        }]}
        ok, reason = x_checks.check5_subject_fields(subjects_doc)
        self.assertFalse(ok)


class TestCheck8Links(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings(SETTINGS_PATH)
        self.doc = load_fixture()

    def _run_real_filter_with_links(self, doc):
        script = ROOT / "x_filter.py"
        if not script.exists():
            self.skipTest("x_filter.py not built yet")
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td)
            (run_dir / "tweets.json").write_text(json.dumps(doc), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), "--run-dir", str(run_dir),
                 "--settings", str(SETTINGS_PATH)],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                self.fail(f"x_filter.py failed: {result.stderr}")
            kept_doc = json.loads((run_dir / "kept.json").read_text(encoding="utf-8"))
            links_path = run_dir / "links.md"
            if not links_path.exists():
                self.fail("x_filter.py did not write links.md")
            return kept_doc, links_path.read_text(encoding="utf-8")

    def test_real_links_md_matches_kept(self):
        kept_doc, links_text = self._run_real_filter_with_links(self.doc)
        ok, reason = x_checks.check8_links(kept_doc, links_text)
        self.assertTrue(ok, reason)

    def _hand_built_kept(self):
        exp_kept, _ = x_checks.expected_filter(self.doc, self.settings)
        kept = [t for t in self.doc["tweets"] if t["id"] in exp_kept]
        return {"run": "test", "kept_at": "x", "kept": kept, "dropped": []}

    def test_hand_built_links_md_passes(self):
        kept_doc = self._hand_built_kept()
        lines = []
        for t in kept_doc["kept"]:
            kind = "REPOST" if t.get("reposted_by") else "POST"
            lines.append(f"## {kind}")
            lines.append(f"- author: {t['author']}")
            lines.append(t["url"])
            lines.append("")
        ok, reason = x_checks.check8_links(kept_doc, "\n".join(lines))
        self.assertTrue(ok, reason)

    def test_links_md_missing_a_kept_url_fails(self):
        kept_doc = self._hand_built_kept()
        lines = []
        for t in kept_doc["kept"][1:]:  # drop the first survivor's entry
            kind = "REPOST" if t.get("reposted_by") else "POST"
            lines.append(f"## {kind}")
            lines.append(t["url"])
        ok, reason = x_checks.check8_links(kept_doc, "\n".join(lines))
        self.assertFalse(ok)

    def test_links_md_with_extra_url_fails(self):
        kept_doc = self._hand_built_kept()
        lines = []
        for t in kept_doc["kept"]:
            kind = "REPOST" if t.get("reposted_by") else "POST"
            lines.append(f"## {kind}")
            lines.append(t["url"])
        lines.append("## POST")
        lines.append("https://x.com/nobody/status/9999999999999999999")
        ok, reason = x_checks.check8_links(kept_doc, "\n".join(lines))
        self.assertFalse(ok)

    def test_links_md_wrong_kind_fails(self):
        kept_doc = self._hand_built_kept()
        # id ...002 is a repost (reposted_by=@econwatcher); mark it POST.
        lines = []
        for t in kept_doc["kept"]:
            kind = "REPOST" if t.get("reposted_by") else "POST"
            if t["id"] == "1000000000000000002":
                kind = "POST"
            lines.append(f"## {kind}")
            lines.append(t["url"])
        ok, reason = x_checks.check8_links(kept_doc, "\n".join(lines))
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
