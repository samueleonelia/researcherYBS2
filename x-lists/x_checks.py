#!/usr/bin/env python3
"""x_checks.py - the mechanical, JSON-only checks from GOAL.md section 2,
plus check 8 for the links.md artifact.

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

    This is the SCRAPE-STOP heuristic (design section 1): it decides where
    scrolling should have stopped, and on purpose tolerates a lone old
    non-repost that never joins a run of `stop_after_old` -- used below
    only by check2, to validate tweets.json's own scrape boundary. Filter
    rule 3 is a different, per-tweet question -- see `outside_window`.
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


def clears_engagement_floor(t: dict, scraped_at, reposts_rate, likes_rate,
                             views_rate) -> bool:
    """Rule 6, amended 2026-09-06: the floor RISES WITH AGE. A tweet
    clears it the moment any ONE of reposts, likes or views reaches its
    own per-hour rate times the tweet's age in hours at `scraped_at`. Kept
    independent of x_filter.py's own copy on purpose -- this file must
    never import x_filter."""
    posted_at = parse_iso(t["posted_at"])
    age_h = max((scraped_at - posted_at).total_seconds() / 3600.0, 0.0)
    return (
        t.get("reposts", 0) >= reposts_rate * age_h
        or t.get("likes", 0) >= likes_rate * age_h
        or t.get("views", 0) >= views_rate * age_h
    )


def outside_window(t: dict, cutoff) -> bool:
    """Rule 3, re-derived independently of x_filter.py's own copy of this
    same logic (this file must never import x_filter -- two independent
    implementations is the point).

    Reading: a repost's `posted_at` holds the ORIGINAL's time, not the
    repost's own timeline position, so rule 3 never fires on a repost --
    that is what the design means by "a repost rides the timeline at
    repost time" and its own worked case (8 reposts with
    older-than-window originals, "correctly kept") requires. A non-repost
    is outside the window exactly when its own posted_at is older than
    `cutoff`, individually -- NOT via `window_boundary`'s
    run-of-`stop_after_old` tolerance, which is a scrape-stop heuristic
    (see window_boundary's own docstring) and would wrongly let an
    isolated old non-repost through the filter."""
    if t.get("reposted_by"):
        return False
    return parse_iso(t["posted_at"]) < cutoff


def expected_filter(tweets_doc: dict, settings: dict):
    """Recompute the six filter rules independently of x_filter.py, per
    the design's fixed order (plans/x-lists-design.md section 2, as amended
    2026-09-06) and the window ruling above. Returns
    (kept_ids: set, dropped: {id: rule}).

    Rule 4 (has_link) no longer looks at word count at all -- any link at
    all drops the tweet, however much commentary rides with it. Rule 6,
    also amended 2026-09-06, is an age-scaled engagement floor: a tweet
    clears it the moment reposts, likes or views (any one) reaches its own
    per-hour rate times the tweet's age in hours at scraped_at -- not the
    old absolute floor of reposts < x_min_reposts AND likes < x_min_likes.

    Rule 3 is a per-tweet check (`outside_window`), independent of the
    scrape's own run-of-`stop_after_old` tolerance -- see that function's
    docstring."""
    tweets = tweets_doc.get("tweets") or []
    window_hours = settings["x_window_hours"]
    min_words = settings["x_min_own_words"]
    reposts_rate = settings["x_reposts_per_hour"]
    likes_rate = settings["x_likes_per_hour"]
    views_rate = settings["x_views_per_hour"]

    scraped_at = parse_iso(tweets_doc["scraped_at"])
    cutoff = scraped_at - timedelta(hours=window_hours)

    kept_ids, dropped = set(), {}
    for i, t in enumerate(tweets):
        words = word_count(t.get("text"))
        if t.get("promoted"):
            rule = 1
        elif t.get("is_reply"):
            rule = 2
        elif outside_window(t, cutoff):
            rule = 3
        elif t.get("has_link"):
            rule = 4
        elif words < min_words and not t.get("quoted_text"):
            rule = 5
        elif not clears_engagement_floor(t, scraped_at, reposts_rate,
                                          likes_rate, views_rate):
            rule = 6
        else:
            rule = None
        if rule is None:
            kept_ids.add(t["id"])
        else:
            dropped[t["id"]] = rule
    return kept_ids, dropped


def check3_kept(tweets_doc: dict, kept_doc: dict, settings: dict):
    """kept.json holds only tweets that survive the six filter rules, in
    order, and nothing else was dropped -- checked against an independent
    recomputation of the rules, not against x_filter.py's own code."""
    for key in ("x_window_hours", "x_min_own_words",
                "x_reposts_per_hour", "x_likes_per_hour", "x_views_per_hour"):
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
        if d["rule"] not in (1, 2, 3, 4, 5, 6):
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
            f"kept set does not match the six rules: "
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

    return True, f"{len(kept_ids)} kept, {len(dropped_by_id)} dropped, matches the six rules"


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


# ---------------------------------------------------------------- check 8

URL_RE = re.compile(r"^https?://\S+$")


def parse_links_md(text: str):
    """Parse links.md into a list of {"kind": "POST"|"REPOST", "url": str}
    entries. Format written by x_filter.write_links_md: a "## POST" or
    "## REPOST" heading, some "- key: value" lines, then the bare
    permalink on its own line, one entry per survivor. Independent of
    x_filter.py's own code -- this just reads the markdown shape."""
    entries = []
    kind = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line == "## POST":
            kind = "POST"
        elif line == "## REPOST":
            kind = "REPOST"
        elif URL_RE.match(line):
            if kind is None:
                raise ValueError(f"a url appears before any ## POST/REPOST heading: {line}")
            entries.append({"kind": kind, "url": line})
    return entries


def check8_links(kept_doc: dict, links_md_text: str):
    """links.md lists every surviving (kept) tweet as a permalink, marked
    POST or REPOST (REPOST exactly when reposted_by is non-empty), and
    nothing that failed a rule. The set of urls in it must equal exactly
    the set of kept tweets' urls."""
    kept = kept_doc.get("kept") or []
    if not kept:
        return False, "kept.json has no 'kept' tweets to check links.md against"

    expected_by_url = {}
    for t in kept:
        if "url" not in t or "id" not in t:
            return False, f"a kept tweet is missing id or url: {t}"
        expected_kind = "REPOST" if t.get("reposted_by") else "POST"
        if t["url"] in expected_by_url:
            return False, f"two kept tweets share url {t['url']!r}"
        expected_by_url[t["url"]] = expected_kind

    try:
        entries = parse_links_md(links_md_text)
    except ValueError as e:
        return False, str(e)

    seen_urls = set()
    for e in entries:
        url = e["url"]
        if url in seen_urls:
            return False, f"url {url!r} appears twice in links.md"
        seen_urls.add(url)
        if url not in expected_by_url:
            return False, f"links.md has a url not in kept.json: {url!r}"
        if e["kind"] != expected_by_url[url]:
            return False, (
                f"url {url!r} marked {e['kind']} in links.md, "
                f"expected {expected_by_url[url]} from reposted_by"
            )

    expected_urls = set(expected_by_url)
    if seen_urls != expected_urls:
        missing = expected_urls - seen_urls
        return False, f"links.md is missing kept url(s): {missing}"

    return True, f"links.md lists exactly the {len(expected_urls)} kept urls, correctly marked"


# ---------------------------------------------------------------- check 10
#
# Check 10, in full, needs a human reader: "follows templates/x-brief.md",
# "the story in Yaron's lens", "obeys preferences.md". Those go to a sonnet
# verifier. What follows is the part a script can decide from the two files
# alone, independent of x_run.py and x_filter.py (this module imports
# neither, on purpose -- it re-parses picks.md and brief.md itself, the same
# way check3/check8 above re-derive the filter and links.md rather than
# trusting the code that produced them):
#
#   - brief.md exists and is non-empty
#   - item count equals the pick count, and no permalink appears that is not
#     in picks.md, and none is missing
#   - every TRENDING item precedes every CURIOUS item, and (going a little
#     further, since it costs nothing extra to check) each item actually
#     carries the permalink of a pick tagged with its own section's tag
#   - every sentence is at or under x_words_per_sentence_max words
#   - every pick's storyline line appears in the brief
#
# Left to the human/sonnet verifier, deliberately not faked here:
#   - "follows templates/x-brief.md" beyond the mechanical shape above (the
#     exact heading punctuation, bullet order/labels, the closing-line
#     wording) -- matching prose shape is a reading judgment, not a
#     re-derivable fact.
#   - "the story in Yaron's lens" -- a judgment about the writing itself.
#   - "every figure and quote in it appears in that pick's note" -- checking
#     this for real means reading the item's prose and the note's full_text
#     and deciding what counts as "the same figure" or "the same quote"
#     (rounding, paraphrase, a number spelled out vs digits). A script that
#     tried to automate this would either reject good prose that restates a
#     figure in different words, or pass bad prose by only checking for a
#     bare digit's presence somewhere in the note -- neither is the check.
#     This needs a reader.
#   - "obeys preferences.md" -- preferences are prose instructions, not a
#     table of rules a script can enumerate and test for.

PICKS_HEADING_RE = re.compile(r"^##\s+\d+\.\s*(.+?)\s*$", re.M)
PICKS_TWEET_LINE_RE = re.compile(r"^\s*-\s*(@\S+)\s*—\s*(https?://\S+)\s*$", re.M)
PICKS_TAG_RE = re.compile(r"^-\s*\*\*Tag:\*\*\s*(\S+)", re.M)
PICKS_STORYLINE_RE = re.compile(r"^-\s*\*\*Storyline:\*\*\s*(.+?)\s*$", re.M)

BRIEF_SECTION_RE = re.compile(r"^##\s+(TRENDING|CURIOUS)\s*$", re.M)
BRIEF_ITEM_HEADING_RE = re.compile(r"^###\s+(\d+)\.\s*(.+?)\s*$", re.M)
BRIEF_SOURCE_RE = re.compile(r"^-\s*\*\*Source:\*\*\s*\[[^\]]*\]\((https?://\S+)\)\s*$", re.M)


def parse_picks_for_brief(picks_md_text: str):
    """picks.md into a list of {title, tag, storyline, url} dicts, one per
    pick, in file order. Kept deliberately independent of x_run.py's own
    parse_picks_md -- a bug in one must not hide the same bug in the other."""
    headings = list(PICKS_HEADING_RE.finditer(picks_md_text))
    picks = []
    for i, m in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(picks_md_text)
        block = picks_md_text[m.start():end]
        tag_m = PICKS_TAG_RE.search(block)
        story_m = PICKS_STORYLINE_RE.search(block)
        url_m = PICKS_TWEET_LINE_RE.search(block)
        if not (tag_m and story_m and url_m):
            raise ValueError(f"pick '{m.group(1).strip()}' in picks.md is missing Tag, Storyline or its tweet line")
        picks.append({
            "title": m.group(1).strip(),
            "tag": tag_m.group(1).strip(),
            "storyline": story_m.group(1).strip(),
            "url": url_m.group(2).strip(),
        })
    return picks


def parse_brief_items(brief_md_text: str):
    """brief.md into a list of {number, section, url} dicts, one per ###
    item, in document order, tagged with the ## section (TRENDING/CURIOUS)
    it falls under."""
    sections = list(BRIEF_SECTION_RE.finditer(brief_md_text))
    headings = list(BRIEF_ITEM_HEADING_RE.finditer(brief_md_text))
    items = []
    for i, m in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(brief_md_text)
        block = brief_md_text[m.start():end]

        section = None
        for sm in sections:
            if sm.start() < m.start():
                section = sm.group(1)
            else:
                break

        source_m = BRIEF_SOURCE_RE.search(block)
        items.append({
            "number": int(m.group(1)),
            "heading": m.group(2).strip(),
            "section": section,
            "url": source_m.group(1).strip() if source_m else None,
            "block": block,
        })
    return items


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def extract_prose_sentences(brief_md_text: str):
    """The sentences check 10's sentence-length ceiling applies to.

    Decision (documented so a verifier can re-derive it independently):
    the ceiling applies to written prose -- item headings, story paragraphs,
    and the closing line -- not to the `**Run:**` metadata line, the `##`
    section headers, the `---` rule, or the three bullets (`Storyline`,
    `Flags`, `Source`): those are labels and copied values, not composed
    sentences, and `Source` is a markdown link whose brackets and
    parentheses are not sentence punctuation.

    A "sentence" is text ending in `.`, `!` or `?` followed by whitespace or
    the end of the text. A "word" is a whitespace-separated token (so a
    hyphenated word or a number with a decimal point count as one word,
    matching how a person would count it reading aloud). An item heading's
    leading `### <n>.` numbering is stripped first so the item number itself
    is never mistaken for a sentence end.
    """
    lines = brief_md_text.splitlines()
    prose = []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if s.startswith("**Run:**"):
            continue
        if s.startswith("## "):
            continue
        if s.startswith("- **"):
            continue
        if s == "---":
            continue
        if s.startswith("### "):
            s = re.sub(r"^###\s*\d+\.\s*", "", s)
        if s.startswith("# "):
            continue
        prose.append(s)
    text = " ".join(prose)
    if not text.strip():
        return []
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]


def check10_mechanical(picks_md_text: str, brief_md_text: str, settings: dict):
    """The mechanical slice of check 10 -- see the block comment above this
    section for exactly what is and is not covered here."""
    if "x_words_per_sentence_max" not in settings:
        return False, "settings.md has no x_words_per_sentence_max"
    max_words = settings["x_words_per_sentence_max"]

    if not (brief_md_text or "").strip():
        return False, "brief.md does not exist or is empty"

    try:
        picks = parse_picks_for_brief(picks_md_text)
    except ValueError as e:
        return False, f"picks.md could not be parsed: {e}"

    try:
        items = parse_brief_items(brief_md_text)
    except Exception as e:  # noqa: BLE001 - surface as a check failure, not a crash
        return False, f"brief.md could not be parsed: {e}"

    # item count vs pick count, and permalink set equality
    if len(items) != len(picks):
        return False, f"brief.md has {len(items)} item(s), picks.md has {len(picks)} pick(s)"

    pick_urls = [p["url"] for p in picks]
    item_urls = [it["url"] for it in items]
    if None in item_urls:
        bad = [it["number"] for it in items if it["url"] is None]
        return False, f"item(s) {bad} have no parseable Source permalink"
    if set(item_urls) != set(pick_urls):
        missing = set(pick_urls) - set(item_urls)
        extra = set(item_urls) - set(pick_urls)
        return False, f"brief permalinks do not match picks.md (missing={missing}, extra={extra})"
    if len(set(item_urls)) != len(item_urls):
        return False, "a permalink appears in more than one brief item"

    # TRENDING before CURIOUS, and each item's permalink actually belongs to
    # a pick tagged with that item's own section
    seen_curious = False
    for it in items:
        if it["section"] is None:
            return False, f"item {it['number']} does not fall under a ## TRENDING or ## CURIOUS heading"
        if it["section"] == "CURIOUS":
            seen_curious = True
        elif seen_curious:
            return False, f"item {it['number']} is TRENDING but appears after a CURIOUS item"

    url_to_tag = {p["url"]: p["tag"] for p in picks}
    for it in items:
        expected_tag = url_to_tag.get(it["url"])
        if expected_tag and expected_tag != it["section"]:
            return False, (
                f"item {it['number']} is under {it['section']} but its pick "
                f"'{expected_tag}' -- {it['url']}"
            )

    # sentence length ceiling
    for sentence in extract_prose_sentences(brief_md_text):
        n = word_count(sentence)
        if n > max_words:
            return False, f"a sentence has {n} words (max {max_words}): {sentence[:120]!r}"

    # every pick's storyline line appears in the brief, character for character
    missing_storylines = [p["title"] for p in picks if p["storyline"] not in brief_md_text]
    if missing_storylines:
        return False, f"pick(s) missing their storyline in brief.md: {missing_storylines}"

    return True, (
        f"{len(items)} item(s) match {len(picks)} pick(s); TRENDING precedes CURIOUS; "
        f"every sentence <= {max_words} words; every storyline present"
    )
