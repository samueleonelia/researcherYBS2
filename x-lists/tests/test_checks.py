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
  - ...017, ...018, ...019: all posted only minutes before scraped_at
    (see below -- once rule 6 itself became age-scaled, all three clear
    it, since a very fresh tweet needs almost nothing).

Rule 6 changed again the same day, from an absolute floor
(x_min_reposts OR x_min_likes, at any age) to an age-scaled rate: a
tweet clears it the moment reposts, likes or views (any one) reaches its
own per-hour rate (x_reposts_per_hour / x_likes_per_hour /
x_views_per_hour) times the tweet's age in hours at scraped_at. Three
more records, ids ...020-...022, were added to give the new rule cases
the original fixture couldn't: something old enough to actually fail it,
and the >= boundary at exactly-equal. All three sit right after ...001
(before ...002), a spot with a fresh non-repost on both sides, so an old
one among them can never join the run of 3 old non-reposts that rule 3's
tests depend on:
  - ...020: posted 90 min before scraped_at (age_h=1.5) -- an isolated
    old non-repost, so still inside the window. reposts=12, likes=50,
    views=1000; needs reposts>=15, likes>=150, views>=30000 -- clears
    none, dropped by rule 6. Under the retired absolute floor
    (reposts>=10) this record would have been KEPT: if rule 6 ever
    reverts to that floor, this test fails.
  - ...021: posted 30 min before scraped_at (age_h=0.5, needs
    reposts>=5.0). reposts=5 exactly -- the >= boundary clearing case.
  - ...022: same age, reposts=4 -- one short of the same 5.0 line,
    dropped by rule 6. Together with ...021 this pins down that the
    comparison is >=, not >.

  With that 22-record fixture (against the live settings.md, x_window_hours=2),
  expected_filter() gives: kept = {1,2,6,9,10,11,12,13,14,15,17,18,19,21}
  (14), dropped = {3:2, 4:4, 5:4, 7:1, 8:5, 16:2, 20:6, 22:6} (8) --
  confirmed against x_filter.py's real output, which matches exactly. Note
  ids ...013-...015 are all *inside* the 2h window at this scraped_at (they
  sit past 10:00, the cutoff), so none of the 22 original records ever
  exercised rule 3 -- the fixture had no case that told a correctly firing
  rule 3 apart from a rule 3 that never fires at all.

  Two more records, ids ...023-...024, were added on 2026-09-06 to close
  that hole, after a verifier caught the filter attributing an
  out-of-window tweet to rule 6 instead of rule 3 on a real run
  (runs/2026-09-06-1214, tweet 2096442845708042345 -- posted 8.61h before
  scraped_at, correctly outside the 2h window, but the filter's rule 3 used
  the scrape's own run-of-x_stop_after_old boundary tolerance instead of
  checking the tweet on its own terms, so it fell through to rule 6, which
  happened to also drop it -- and would not have if its engagement had been
  strong):
  - ...023: an isolated old non-repost (posted 4h before scraped_at, no
    run of 3 old non-reposts around it) with engagement far above every
    rule-6 threshold at that age. It must be dropped by rule 3 -- if rule 3
    is ever narrowed back to the run-of-x_stop_after_old check, this record
    clears rule 6 instead and is wrongly KEPT.
  - ...024: a repost whose original is ~27h old, engagement far below the
    age-scaled floor at that age. Rule 3 must never fire on a repost (its
    posted_at is the original's, not its own timeline position), so it
    reaches rule 6 and is dropped there -- proving repost-immunity from
    rule 3 is not a free pass past every other rule.

  With ...023-...024 included, expected_filter() gives: kept unchanged
  (14), dropped = {..., 23:3, 24:6} (10).
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
        # The fixture is chosen for field/rule coverage, not to sit on
        # either side of the real x_tweets_min (20) -- a real scrape must
        # clear that bar regardless (and did: a live run produced 47).
        # Schema-completeness tests here use a settings copy with the
        # minimum lowered so they test field-presence, not the fixture's
        # tweet count.
        settings = dict(self.settings)
        settings["x_tweets_min"] = 1
        return settings

    def test_fixture_passes(self):
        ok, reason = x_checks.check1_schema(self.doc, self._lenient_settings())
        self.assertTrue(ok, reason)

    def _tweets_of_count(self, n):
        # Build a tweet list of exactly n records out of the fixture's own
        # records (cycling through them if n exceeds the fixture's real
        # length), so the count tested is fixed and chosen by the test --
        # not incidentally whatever the shared fixture happens to hold.
        from itertools import cycle, islice
        return copy.deepcopy(list(islice(cycle(self.doc["tweets"]), n)))

    def test_below_x_tweets_min_is_rejected_and_named(self):
        # A document with one fewer tweet than x_tweets_min must be
        # rejected, and the reason must name x_tweets_min -- this is the
        # real behaviour check1_schema exists to enforce.
        minimum = self.settings["x_tweets_min"]
        doc = copy.deepcopy(self.doc)
        doc["tweets"] = self._tweets_of_count(minimum - 1)
        ok, reason = x_checks.check1_schema(doc, self.settings)
        self.assertFalse(ok)
        self.assertIn("x_tweets_min", reason)

    def test_at_x_tweets_min_is_not_rejected_for_count(self):
        # A document with exactly x_tweets_min tweets clears the minimum
        # (check1_schema's boundary is `len(tweets) < minimum`, so equal
        # passes) and must not be rejected on the count.
        minimum = self.settings["x_tweets_min"]
        doc = copy.deepcopy(self.doc)
        doc["tweets"] = self._tweets_of_count(minimum)
        ok, reason = x_checks.check1_schema(doc, self.settings)
        self.assertTrue(ok, reason)

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

    def test_promoted_tweet_is_dropped_by_rule_1(self):
        # id ...007 (fixture): promoted=true, and would otherwise clear
        # every later rule easily. Named explicitly so this is a real
        # assertion on rule 1 firing, not just an incidental match inside
        # the whole-set comparisons above -- rule 1 has never fired on a
        # real scrape in this project (see RUNLOG.md), so this fixture
        # record is what stands between "never fires because it's dead"
        # and "never fires because no real tweet has been promoted yet".
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertNotIn("1000000000000000007", exp_kept)
        self.assertEqual(exp_dropped.get("1000000000000000007"), 1)

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
        # id ...017: posted 3 min before scraped_at, reposts=15 -- needs
        # only reposts>=0.5 at that age, clears easily.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertIn("1000000000000000017", exp_kept)
        self.assertNotIn("1000000000000000017", exp_dropped)

    def test_engagement_floor_cleared_by_likes_alone(self):
        # id ...018: posted 4 min before scraped_at, likes=150 -- needs
        # only likes>=6.67 at that age, clears easily.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertIn("1000000000000000018", exp_kept)
        self.assertNotIn("1000000000000000018", exp_dropped)

    def test_very_fresh_tweet_clears_on_almost_nothing(self):
        # id ...019: posted 5 min before scraped_at, reposts=3, likes=20.
        # Under the retired absolute floor (reposts>=10 OR likes>=100)
        # this record would have been dropped; under the age-scaled rule
        # it needs only reposts>=0.83 or likes>=8.3 at that age, so it
        # clears -- exactly the design's "a very fresh tweet needs almost
        # nothing" intent.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertIn("1000000000000000019", exp_kept)
        self.assertNotIn("1000000000000000019", exp_dropped)

    def test_engagement_floor_scales_with_age_not_absolute(self):
        # id ...020: posted 90 min before scraped_at, reposts=12, likes=50,
        # views=1000. Under the retired absolute floor (reposts>=10) this
        # would have been KEPT; the age-scaled rule needs reposts>=15,
        # likes>=150, views>=30000 at that age, and it clears none of them
        # -- dropped by rule 6. If rule 6 ever reverts to an absolute
        # floor, this test fails.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertNotIn("1000000000000000020", exp_kept)
        self.assertEqual(exp_dropped.get("1000000000000000020"), 6)

    def test_engagement_floor_boundary_exactly_equal_clears(self):
        # id ...021: posted 30 min before scraped_at (age_h=0.5), needs
        # reposts>=5.0 at x_reposts_per_hour=10; reposts=5 exactly. The
        # rule is >=, so an exact match clears it.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertIn("1000000000000000021", exp_kept)
        self.assertNotIn("1000000000000000021", exp_dropped)

    def test_engagement_floor_boundary_one_below_drops(self):
        # id ...022: same age as ...021 (needs reposts>=5.0), reposts=4 --
        # one short of the line, so it is dropped by rule 6. Paired with
        # ...021 this pins the comparison down as >=, not >.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertNotIn("1000000000000000022", exp_kept)
        self.assertEqual(exp_dropped.get("1000000000000000022"), 6)

    def test_isolated_old_tweet_with_strong_engagement_is_dropped_by_rule_3(self):
        # id ...023: posted 4h before scraped_at (window is 2h), isolated
        # (not part of any run of x_stop_after_old old non-reposts), with
        # engagement far above every per-hour threshold at that age
        # (reposts=5000, likes=40000, views=2000000 vs needing >=40/>=400/
        # >=80000). This is the real production bug (verifier's FAIL on
        # runs/2026-09-06-1214, tweet 2096442845708042345): a tweet that
        # would clear rule 6 easily must still never reach rule 6, because
        # it is outside the window on its own posted_at. If rule 3 is ever
        # reduced back to the scrape's run-of-x_stop_after_old boundary
        # tolerance, this isolated tweet slips through rule 3 and is
        # wrongly KEPT via rule 6 instead -- exactly the hole the verifier
        # caught.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertNotIn("1000000000000000023", exp_kept)
        self.assertEqual(exp_dropped.get("1000000000000000023"), 3)

    def test_old_repost_is_never_caught_by_rule_3(self):
        # id ...024: reposted_by set, original posted_at ~27h before
        # scraped_at -- far outside the 2h window by its own timestamp.
        # Rule 3 must never fire on a repost (the design's "a repost rides
        # the timeline at repost time" -- posted_at holds the ORIGINAL's
        # time, not the repost's own timeline position). It still must not
        # be kept for free: its engagement (reposts=3, likes=10, views=500)
        # falls far short of the age-scaled floor at 27h old
        # (needs reposts>=270, likes>=2700, views>=540000), so it is
        # dropped by rule 6, not rule 3 -- proving repost-immunity from
        # rule 3 is not a blanket keep.
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertNotIn("1000000000000000024", exp_kept)
        self.assertEqual(exp_dropped.get("1000000000000000024"), 6)

    def test_old_repost_with_strong_original_is_kept_id_2(self):
        # id ...002 (one of the original fixture records): reposted_by
        # set, original posted 2026-09-05T08:15 (~27.75h before
        # scraped_at). Rule 3 does not touch it (it's a repost); its
        # engagement (reposts=640, likes=2900) clears the age-scaled floor
        # at that age (needs reposts>=277.5, likes>=2775), so it is kept.
        # This is the design's own worked case -- "8 reposts whose
        # originals are older than the window... correctly kept".
        exp_kept, exp_dropped = x_checks.expected_filter(self.doc, self.settings)
        self.assertIn("1000000000000000002", exp_kept)
        self.assertNotIn("1000000000000000002", exp_dropped)

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
