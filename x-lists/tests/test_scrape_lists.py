#!/usr/bin/env python3
"""Tests for reading more than one X list -- x_scrape.py's merge step.

The browser half of x_scrape.py cannot be tested here: opening two lists in
the ego browser and checking the guardrail on each needs a live session, and
that is the acceptance test for this feature. What IS testable is everything
after the scroll: how two lists become one pile, who keeps the `list` field,
and what the head of tweets.json says.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import x_scrape  # noqa: E402
import x_checks  # noqa: E402
import x_score  # noqa: E402


ONE = {"name": "List one", "slug": "list-one", "url": "https://x.com/i/lists/111"}
TWO = {"name": "List two", "slug": "list-two", "url": "https://x.com/i/lists/222"}


def tweet(tid, list_name, author="@a", posted="2026-09-06T11:50:00Z"):
    """A record shaped the way to_record() shapes one."""
    return {
        "id": tid, "url": f"https://x.com/{author.lstrip('@')}/status/{tid}",
        "list": list_name, "lists": [list_name], "author": author,
        "reposted_by": "", "posted_at": posted, "seen_at": posted,
        "text": "some words here about a thing", "card_title": "",
        "quoted_text": "", "is_reply": False, "has_link": False,
        "promoted": False, "replies": 1, "reposts": 2, "likes": 3, "views": 400,
    }


class TestMergeLists(unittest.TestCase):
    def test_one_list_is_unchanged(self):
        tweets, counts = x_scrape.merge_lists([(ONE, [tweet("1", ONE["name"]),
                                                       tweet("2", ONE["name"])])])
        self.assertEqual([t["id"] for t in tweets], ["1", "2"])
        self.assertEqual(counts, [{"name": "List one", "url": ONE["url"], "tweets": 2}])

    def test_a_tweet_in_both_lists_is_stored_once(self):
        shared = "9"
        tweets, counts = x_scrape.merge_lists([
            (ONE, [tweet("1", ONE["name"]), tweet(shared, ONE["name"])]),
            (TWO, [tweet(shared, TWO["name"]), tweet("2", TWO["name"])]),
        ])
        ids = [t["id"] for t in tweets]
        self.assertEqual(ids, ["1", "9", "2"], "first-seen order, one record each")
        both = next(t for t in tweets if t["id"] == shared)
        self.assertEqual(both["list"], "List one", "the first list keeps the field")
        self.assertEqual(both["lists"], ["List one", "List two"])

    def test_the_head_counts_what_each_list_showed(self):
        shared = "9"
        _, counts = x_scrape.merge_lists([
            (ONE, [tweet("1", ONE["name"]), tweet(shared, ONE["name"])]),
            (TWO, [tweet(shared, TWO["name"])]),
        ])
        self.assertEqual([c["tweets"] for c in counts], [2, 1],
                          "each list reports what it showed, before the dedupe")

    def test_the_same_list_named_twice_does_not_double_count(self):
        tweets, _ = x_scrape.merge_lists([
            (ONE, [tweet("1", ONE["name"])]),
            (ONE, [tweet("1", ONE["name"])]),
        ])
        self.assertEqual(tweets[0]["lists"], ["List one"])


class TestTweetsJsonHead(unittest.TestCase):
    def test_check1_accepts_a_two_list_file(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d)
            tweets, counts = x_scrape.merge_lists([
                (ONE, [tweet(str(i), ONE["name"]) for i in range(1, 13)]),
                (TWO, [tweet(str(i), TWO["name"]) for i in range(10, 25)]),
            ])
            x_scrape.write_tweets_json(run_dir, "@EgoismoEfficace", counts, 2, tweets)
            doc = json.loads((run_dir / "tweets.json").read_text())
            ok, reason = x_checks.check1_schema(doc, {"x_tweets_min": 20})
            self.assertTrue(ok, reason)
            self.assertIn("2 list(s)", reason)

    def test_check1_refuses_a_tweet_from_a_list_nothing_scraped(self):
        tweets, counts = x_scrape.merge_lists([(ONE, [tweet(str(i), ONE["name"])
                                                       for i in range(1, 22)])])
        doc = {"lists": counts, "account": "@a", "scraped_at": "2026-09-06T12:00:00Z",
               "window_hours": 2, "tweets": tweets}
        doc["tweets"][0]["lists"] = ["A list nobody read"]
        doc["tweets"][0]["list"] = "A list nobody read"
        ok, reason = x_checks.check1_schema(doc, {"x_tweets_min": 20})
        self.assertFalse(ok)
        self.assertIn("nothing scraped", reason)

    def test_check2_reads_each_list_on_its_own_timeline(self):
        """An old run at the end of list one must not cut list two short."""
        settings = {"x_window_hours": 1, "x_stop_after_old": 2}
        old = "2026-09-06T09:00:00Z"      # two hours before scraped_at
        fresh = "2026-09-06T11:50:00Z"
        tweets = (
            [tweet("1", ONE["name"], posted=fresh),
             tweet("2", ONE["name"], posted=old),
             tweet("3", ONE["name"], posted=old)]      # list one's own old run
            + [tweet("4", TWO["name"], posted=fresh),
               tweet("5", TWO["name"], posted=fresh)]  # list two: all in window
        )
        doc = {"lists": [{"name": ONE["name"], "url": ONE["url"], "tweets": 3},
                          {"name": TWO["name"], "url": TWO["url"], "tweets": 2}],
               "account": "@a", "scraped_at": "2026-09-06T12:00:00Z",
               "window_hours": 1, "tweets": tweets}
        ok, reason = x_checks.check2_window(doc, settings)
        self.assertTrue(ok, reason)
        self.assertIn("List one: boundary at position 1", reason)
        self.assertIn("List two: no run", reason)


class TestConvergenceCountsLists(unittest.TestCase):
    def test_a_subject_in_two_lists_counts_as_two(self):
        kept = [tweet("1", ONE["name"], author="@a"),
                tweet("2", TWO["name"], author="@b")]
        kept[0]["lists"] = ["List one", "List two"]
        subjects = [{"subject": "a thing", "tweet_ids": ["1", "2"]}]
        scored = x_score.score_subjects(kept, subjects,
                                         {"x_convergence_authors": 3,
                                          "x_endorsement_min": 3,
                                          "x_velocity_percentile": 90},
                                         "2026-09-06T12:00:00Z")
        self.assertEqual(scored[0]["lists"], 2)
        self.assertTrue(scored[0]["cross_list"])


if __name__ == "__main__":
    unittest.main()
