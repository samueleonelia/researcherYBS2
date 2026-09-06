#!/usr/bin/env python3
"""x_checks.py - the five mechanical, JSON-only checks from GOAL.md section 2.

Each `check_N` function takes already-loaded JSON (plus settings where a
number is needed) and returns `(ok: bool, reason: str)`. Nothing here opens
a browser, calls an agent, or reads a tweet for meaning -- these are the
checks a verifier or a test can run from the files alone.

The window rule follows the orchestrator's ruling in
`plans/interfaces.md` ("The window boundary" section, 2026-09-06):

    Walk the timeline in order. The boundary is the position of the FIRST
    tweet in the first run of `x_stop_after_old` consecutive non-repost
    tweets whose own posted_at is older than x_window_hours before
    scraped_at. Every tweet above that line is in the window (reposts
    included, an isolated old non-repost included); every tweet from that
    line down is out.

Python 3, standard library only.
"""

import re
from datetime import datetime, timedelta, timezone

# The full tweet schema: the design's field table plus `promoted`, which
# filter rule 1 needs and the design's table omits (see interfaces.md).
TWEET_FIELDS = [
    "id", "url", "list", "author", "reposted_by", "posted_at", "seen_at",
    "text", "card_title", "quoted_text", "is_reply", "has_link", "promoted",
    "replies", "reposts", "likes", "views",
]

SUBJECT_SCORE_FIELDS = [
    "authors", "lists", "endorsements", "velocity", "velocity_rank",
    "cross_list", "flags", "tag",
]

VALID_FLAGS = {"CONVERGENCE", "ENDORSEMENT", "VELOCITY"}


def parse_iso(s):
    if not isinstance(s, str) or not s:
        raise ValueError(f"bad timestamp: {s!r}")
    d = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- window

def window_boundary(tweets: list, cutoff, stop_after_old: int):
    """Index of the first tweet in the first run of `stop_after_old`
    consecutive non-repost tweets older than `cutoff`, walking the
    non-repost tweets in timeline order. `None` if no such run exists.

    Returns the boundary as an index into the FULL `tweets` list (reposts
    included) -- the position of the run's first member.
    """
    run_start_idx = None
    run_len = 0
    for i, t in enumerate(tweets):
        if t.get("reposted_by"):
            continue  # reposts are not part of the non-repost sequence
        old = parse_iso(t["posted_at"]) < cutoff
        if old:
            if run_len == 0:
                run_start_idx = i
            run_len += 1
            if run_len >= stop_after_old:
                return run_start_idx
        else:
            run_len = 0
            run_start_idx = None
    return None


# ---------------------------------------------------------------- check 1

def check1_schema(tweets_doc: dict, settings: dict):
    """tweets.json exists (caller loaded it), has >= x_tweets_min tweets,
    and every record carries every field in TWEET_FIELDS (empty allowed,
    missing not)."""
    if "x_tweets_min" not in settings:
        return False, "settings.md has no x_tweets_min"
    minimum = settings["x_tweets_min"]

    for key in ("list_url", "account", "scraped_at", "window_hours", "tweets"):
        if key not in tweets_doc:
            return False, f"tweets.json is missing top-level '{key}'"

    tweets = tweets_doc["tweets"]
    if not isinstance(tweets, list):
        return False, "tweets.json's 'tweets' is not a list"
    if len(tweets) < minimum:
        return False, f"only {len(tweets)} tweets, need at least {minimum} (x_tweets_min)"

    for i, t in enumerate(tweets):
        if not isinstance(t, dict):
            return False, f"tweet at index {i} is not an object"
        missing = [f for f in TWEET_FIELDS if f not in t]
        if missing:
            return False, f"tweet {t.get('id', f'#{i}')} is missing field(s): {missing}"

    return True, f"{len(tweets)} tweets, all {len(TWEET_FIELDS)} fields present"


# ---------------------------------------------------------------- check 2

def check2_window(tweets_doc: dict, settings: dict):
    """Every tweet in tweets.json is inside the window rule: reposts
    included, cut at the first run of x_stop_after_old non-repost tweets
    older than x_window_hours (see the ruling above)."""
    for key in ("x_window_hours", "x_stop_after_old"):
        if key not in settings:
            return False, f"settings.md has no {key}"
    window_hours = settings["x_window_hours"]
    stop_after_old = settings["x_stop_after_old"]

    tweets = tweets_doc.get("tweets") or []
    if "scraped_at" not in tweets_doc:
        return False, "tweets.json has no scraped_at"
    try:
        scraped_at = parse_iso(tweets_doc["scraped_at"])
    except ValueError as e:
        return False, str(e)
    cutoff = scraped_at - timedelta(hours=window_hours)

    try:
        boundary = window_boundary(tweets, cutoff, stop_after_old)
    except (ValueError, KeyError) as e:
        return False, f"unparseable tweet: {e}"

    if boundary is None:
        return True, f"no run of {stop_after_old} old non-reposts found; all {len(tweets)} tweets in window"

    kept_len = boundary
    dropped = tweets[boundary:]
    # every dropped tweet must be part of, or after, that first old run --
    # i.e. nothing before the boundary is out, nothing at/after it is in.
    if len(tweets) != kept_len + len(dropped):
        return False, "internal accounting error"

    return True, (
        f"boundary at position {boundary} (0-based); "
        f"{kept_len} tweets in window, {len(dropped)} cut at the old run"
    )


# ---------------------------------------------------------------- check 3

def word_count(text):
    return len((text or "").split())


def expected_filter(tweets_doc: dict, settings: dict):
    """Recompute the five filter rules independently of x_filter.py, per
    the design's fixed order and the window ruling above. Returns
    (kept_ids: set, dropped: {id: rule})."""
    tweets = tweets_doc.get("tweets") or []
    window_hours = settings["x_window_hours"]
    stop_after_old = settings["x_stop_after_old"]
    min_words = settings["x_min_own_words"]

    scraped_at = parse_iso(tweets_doc["scraped_at"])
    cutoff = scraped_at - timedelta(hours=window_hours)
    boundary = window_boundary(tweets, cutoff, stop_after_old)

    kept_ids, dropped = set(), {}
    for i, t in enumerate(tweets):
        words = word_count(t.get("text"))
        if t.get("promoted"):
            rule = 1
        elif t.get("is_reply"):
            rule = 2
        elif boundary is not None and i >= boundary:
            rule = 3
        elif t.get("has_link") and words < min_words:
            rule = 4
        elif words < min_words and not t.get("quoted_text"):
            rule = 5
        else:
            rule = None
        if rule is None:
            kept_ids.add(t["id"])
        else:
            dropped[t["id"]] = rule
    return kept_ids, dropped


def check3_kept(tweets_doc: dict, kept_doc: dict, settings: dict):
    """kept.json holds only tweets that survive the five filter rules, in
    order, and nothing else was dropped -- checked against an independent
    recomputation of the rules, not against x_filter.py's own code."""
    for key in ("x_window_hours", "x_stop_after_old", "x_min_own_words"):
        if key not in settings:
            return False, f"settings.md has no {key}"

    for key in ("kept", "dropped"):
        if key not in kept_doc:
            return False, f"kept.json is missing '{key}'"

    all_tweets = tweets_doc.get("tweets") or []
    all_ids = {t["id"] for t in all_tweets}

    kept_ids = {t["id"] for t in kept_doc["kept"]}
    dropped_by_id = {}
    for d in kept_doc["dropped"]:
        if "id" not in d or "rule" not in d:
            return False, f"a dropped entry is missing id or rule: {d}"
        if d["rule"] not in (1, 2, 3, 4, 5):
            return False, f"dropped id {d['id']} has an invalid rule: {d['rule']}"
        if d["id"] in dropped_by_id:
            return False, f"id {d['id']} appears twice in dropped"
        dropped_by_id[d["id"]] = d["rule"]

    accounted = kept_ids | set(dropped_by_id)
    if accounted != all_ids:
        missing = all_ids - accounted
        extra = accounted - all_ids
        return False, f"not exactly one bucket per input tweet (missing={missing}, extra={extra})"
    if kept_ids & set(dropped_by_id):
        return False, f"id(s) in both kept and dropped: {kept_ids & set(dropped_by_id)}"

    exp_kept, exp_dropped = expected_filter(tweets_doc, settings)
    if kept_ids != exp_kept:
        return False, (
            f"kept set does not match the five rules: "
            f"wrongly kept={kept_ids - exp_kept}, wrongly dropped={exp_kept - kept_ids}"
        )
    for tid, rule in dropped_by_id.items():
        if exp_dropped.get(tid) != rule:
            return False, f"id {tid} dropped by rule {rule}, expected rule {exp_dropped.get(tid)}"

    # kept holds whole tweet records, in timeline order.
    order_in_tweets = [t["id"] for t in all_tweets if t["id"] in kept_ids]
    order_in_kept = [t["id"] for t in kept_doc["kept"]]
    if order_in_kept != order_in_tweets:
        return False, "kept tweets are not in timeline order"

    return True, f"{len(kept_ids)} kept, {len(dropped_by_id)} dropped, matches the five rules"


# ---------------------------------------------------------------- check 4

def check4_subject_coverage(kept_doc: dict, subjects_doc: dict):
    """Every kept tweet id appears in exactly one subject."""
    if "subjects" not in subjects_doc:
        return False, "subjects.json has no 'subjects'"
    kept_ids = {t["id"] for t in kept_doc.get("kept") or []}

    seen = {}
    for si, subj in enumerate(subjects_doc["subjects"]):
        if "tweet_ids" not in subj:
            return False, f"subject #{si} has no tweet_ids"
        for tid in subj["tweet_ids"]:
            if tid in seen:
                return False, f"id {tid} appears in two subjects ({seen[tid]} and {si})"
            seen[tid] = si

    covered = set(seen)
    if covered != kept_ids:
        missing = kept_ids - covered
        extra = covered - kept_ids
        return False, f"coverage mismatch (missing={missing}, invented={extra})"

    return True, f"{len(kept_ids)} kept ids, each in exactly one of {len(subjects_doc['subjects'])} subjects"


# ---------------------------------------------------------------- check 5

def check5_subject_fields(subjects_doc: dict, settings: dict = None):
    """Every subject carries authors, lists, endorsements, velocity,
    velocity_rank, cross_list and its flags (plus tag, derived from
    flags)."""
    subjects = subjects_doc.get("subjects") or []
    if not subjects:
        return False, "subjects.json has no subjects"

    for si, subj in enumerate(subjects):
        missing = [f for f in SUBJECT_SCORE_FIELDS if f not in subj]
        if missing:
            return False, f"subject '{subj.get('subject', f'#{si}')}' is missing: {missing}"
        if not isinstance(subj["flags"], list):
            return False, f"subject '{subj['subject']}' flags is not a list"
        bad_flags = set(subj["flags"]) - VALID_FLAGS
        if bad_flags:
            return False, f"subject '{subj['subject']}' has unknown flag(s): {bad_flags}"
        expected_tag = "TRENDING" if subj["flags"] else "SINGLETON"
        if subj["tag"] != expected_tag:
            return False, (
                f"subject '{subj['subject']}' tag is {subj['tag']!r}, "
                f"expected {expected_tag!r} from its flags"
            )
        if not (0 <= subj["velocity_rank"] <= 100):
            return False, f"subject '{subj['subject']}' velocity_rank out of 0-100: {subj['velocity_rank']}"
        if not isinstance(subj["cross_list"], bool):
            return False, f"subject '{subj['subject']}' cross_list is not a bool"

    return True, f"all {len(subjects)} subjects carry every score field"
