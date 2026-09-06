#!/usr/bin/env python3
"""x_filter.py - step 2 of the X pipeline: filter (script).

Reads DIR/tweets.json, drops tweets in the design's fixed order, writes
DIR/kept.json and DIR/links.md. Every input tweet ends up in exactly one of
`kept` or `dropped`; `dropped` records the first rule (1..6) that applies,
in order:

    1. promoted
    2. is_reply
    3. outside the window
    4. has_link
    5. fewer than x_min_own_words words and no quoted_text
    6. below the age-scaled engagement floor: a tweet clears rule 6 the
       moment any ONE of reposts, likes or views reaches its own rate
       (x_reposts_per_hour, x_likes_per_hour, x_views_per_hour) times the
       tweet's age in hours at scraped_at; nothing clears it if all three
       fall short

`links.md` lists every survivor (nothing that failed a rule) as a
permalink, marked POST or REPOST -- the file the read stage consumes.

Window rule (see plans/interfaces.md, "The window boundary — orchestrator
ruling"): a repost sits in the timeline at repost time, but its own
timestamp is the original's, so a repost never counts toward the run below
and never breaks it either. Walk the timeline (the order tweets appear in
tweets.json). The boundary is the position of the FIRST tweet in the first
run of x_stop_after_old consecutive non-repost tweets whose own posted_at is
older than x_window_hours before scraped_at. Every tweet above that line is
in the window -- reposts included, and an isolated old non-repost included.
Every tweet from that line down is out.

Python 3, standard library only.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from x_settings import load_settings, require


def die(msg: str, code: int = 2):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(code)


def load_json(path: Path):
    if not path.exists():
        die(f"missing file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"bad JSON in {path}: {e}")


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def parse_iso(s: str) -> datetime:
    """Strict enough for our own iso-Z timestamps; dies rather than guess."""
    if not s or not isinstance(s, str):
        die(f"bad timestamp: {s!r}")
    t = s.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        die(f"unparseable timestamp: {s!r}")
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------- filter

def word_count(text: str) -> int:
    return len((text or "").split())


def clears_engagement_floor(t: dict, scraped_at: datetime, reposts_rate,
                             likes_rate, views_rate) -> bool:
    """Rule 6: the floor RISES WITH AGE. A tweet clears it the moment any
    one of reposts, likes or views reaches its own per-hour rate times the
    tweet's age in hours at `scraped_at`. A tweet with age_h == 0 needs
    literally nothing -- the design's own intent ("a very fresh tweet
    needs almost nothing")."""
    posted_at = parse_iso(t["posted_at"])
    age_h = max((scraped_at - posted_at).total_seconds() / 3600.0, 0.0)
    return (
        t.get("reposts", 0) >= reposts_rate * age_h
        or t.get("likes", 0) >= likes_rate * age_h
        or t.get("views", 0) >= views_rate * age_h
    )


def window_boundary(tweets: list, cutoff: datetime, stop_after_old: int):
    """Index of the first tweet in the first run of `stop_after_old`
    consecutive non-repost tweets whose own posted_at is older than the
    cutoff. None if the timeline never reaches such a run.

    A repost's own timestamp is the original's, not a timeline position, so
    a repost is skipped entirely here: it neither extends a run of old
    non-reposts nor breaks one.
    """
    run_start = None
    run_len = 0
    for i, t in enumerate(tweets):
        if t.get("reposted_by"):
            continue
        if parse_iso(t["posted_at"]) < cutoff:
            if run_len == 0:
                run_start = i
            run_len += 1
            if run_len >= stop_after_old:
                return run_start
        else:
            run_len = 0
            run_start = None
    return None


def filter_tweets(data: dict, settings: dict):
    (min_words, window_hours, stop_after_old, reposts_rate, likes_rate,
     views_rate) = require(
        settings, "x_min_own_words", "x_window_hours", "x_stop_after_old",
        "x_reposts_per_hour", "x_likes_per_hour", "x_views_per_hour",
    )
    tweets = data.get("tweets") or []

    scraped_at = parse_iso(data["scraped_at"])
    cutoff = scraped_at - timedelta(hours=window_hours)
    boundary = window_boundary(tweets, cutoff, stop_after_old)

    kept, dropped = [], []
    for i, t in enumerate(tweets):
        words = word_count(t.get("text"))
        if t.get("promoted"):
            rule = 1
        elif t.get("is_reply"):
            rule = 2
        elif boundary is not None and i >= boundary:
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
            kept.append(t)
        else:
            dropped.append({"id": t["id"], "rule": rule})

    return kept, dropped


def write_links_md(path: Path, run_name: str, kept: list):
    """Write DIR/links.md: every survivor, permalink plus POST/REPOST, and
    nothing that failed a rule. Plain markdown, one entry per tweet, the
    bare url on its own line so a dispatcher can pull it back out with a
    regex.
    """
    lines = [f"# links: {run_name}", "", f"survivors: {len(kept)}", ""]
    for t in kept:
        kind = "REPOST" if t.get("reposted_by") else "POST"
        lines.append(f"## {kind}")
        lines.append(f"- author: {t.get('author', '')}")
        if kind == "REPOST":
            lines.append(f"- reposted_by: {t.get('reposted_by', '')}")
        lines.append(t.get("url", ""))
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--settings", default=None)
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    settings_path = (Path(args.settings).resolve() if args.settings
                      else Path(__file__).resolve().parent / "settings.md")

    settings = load_settings(settings_path)
    data = load_json(run_dir / "tweets.json")

    kept, dropped = filter_tweets(data, settings)

    total = len(data.get("tweets") or [])
    if len(kept) + len(dropped) != total:
        die(f"internal error: {len(kept)} kept + {len(dropped)} dropped "
            f"!= {total} input tweets")

    out = {
        "run": run_dir.name,
        "kept_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kept": kept,
        "dropped": dropped,
    }
    write_json(run_dir / "kept.json", out)
    write_links_md(run_dir / "links.md", run_dir.name, kept)

    by_rule = {}
    for d in dropped:
        by_rule[d["rule"]] = by_rule.get(d["rule"], 0) + 1
    print(f"filtered {total} tweets: kept {len(kept)}, dropped {len(dropped)} "
          f"(by rule: {by_rule})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
