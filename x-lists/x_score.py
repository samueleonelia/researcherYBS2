#!/usr/bin/env python3
"""x_score.py - step 4 of the X pipeline: score (script).

Reads DIR/kept.json (tweet records) and DIR/subjects.json (subject name +
tweet_ids from the cluster agent), and rewrites DIR/subjects.json with the
measures and flags the design calls for. `subject` and `tweet_ids` are
preserved untouched; nothing here groups or judges relevance.

Standard library only. See plans/x-lists-design.md section 4 and
plans/interfaces.md for the exact schema before and after this step.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

FLAG_NAMES = ("CONVERGENCE", "ENDORSEMENT", "VELOCITY")


def die(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def load_json(path: Path):
    if not path.exists():
        die(f"missing {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"bad json in {path}: {e}")


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_iso(s: str):
    """Strict-ish: the pipeline's own iso-Z timestamps, tolerant of a bare
    +00:00 offset too. None if unparseable (a tweet with a bad timestamp is
    skipped from velocity rather than crashing the run)."""
    if not s or not isinstance(s, str):
        return None
    t = s.strip().replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def load_settings(path: Path) -> dict:
    """Read settings.md's `## Numbers` table: `| key | value | meaning |`.
    Digits become ints; a trailing `%` is stripped before the int conversion;
    anything else is kept as the text as written. Same shape as ybs_run.py's
    load_settings, trimmed to what this script needs (no Models section)."""
    if not path.exists():
        die(f"no settings file at {path}")
    out, section = {}, ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        key, raw = cells[0], cells[1]
        if key.lower() in ("setting", "step") or set(key) <= set("-: "):
            continue
        if section != "numbers":
            continue
        val = raw
        if val.endswith("%"):
            val = val[:-1].strip()
        if val.lstrip("-").isdigit():
            val = int(val)
        out[key] = val
    return out


def need(settings: dict, key: str):
    if key not in settings:
        die(f"settings.md is missing '{key}'")
    return settings[key]


def percentile_rank(values, target) -> float:
    """Percentile of `target` inside `values` (both already computed velocities).

    Definition chosen: fraction of the set at or below `target`, as a
    percentage — i.e. rank = 100 * (count of v <= target) / n. This is the
    "percentile of rank" (a.k.a. proportion-below, inclusive) form:
    - it is stable with very few subjects: with n=1 the single subject's own
      value is trivially <= itself, so it lands at 100 — the only sane answer
      when a lone subject can't be ranked against anything else.
    - it never needs interpolation or a choice of rank method (nearest-rank,
      linear, etc.) that would matter with small n and behave oddly.
    - ties share the same percentile (both count as "at or below"), so two
      subjects with identical velocity both clear or both miss a threshold
      together — no arbitrary tie-break.
    """
    n = len(values)
    if n == 0:
        return 0.0
    at_or_below = sum(1 for v in values if v <= target)
    return 100.0 * at_or_below / n


def score_subjects(kept: list, subjects: list, settings: dict, scraped_at: str):
    tweets_by_id = {t["id"]: t for t in kept}

    scraped_dt = parse_iso(scraped_at)
    if scraped_dt is None:
        die(f"kept.json / run has an unparseable scraped_at: {scraped_at!r}")

    conv_n = need(settings, "x_convergence_authors")
    endorse_m = need(settings, "x_endorsement_min")
    velocity_p = need(settings, "x_velocity_percentile")

    # First pass: per-subject raw measures that don't depend on other subjects.
    prepared = []
    for subj in subjects:
        ids = subj.get("tweet_ids", [])
        tws = [tweets_by_id[i] for i in ids if i in tweets_by_id]

        # authors: distinct author + reposted_by, both lists, non-empty only.
        authors = set()
        for t in tws:
            a = (t.get("author") or "").strip()
            if a:
                authors.add(a)
            rb = (t.get("reposted_by") or "").strip()
            if rb:
                authors.add(rb)

        # lists: how many of A, B appear among this subject's tweets.
        lists_seen = {t.get("list") for t in tws if t.get("list")}
        lists_count = len(lists_seen)

        # endorsements: max over tweets of (reposts by list members inside
        # the subject) + (quotes inside the subject pointing at that tweet).
        # "reposts by list members" = count of OTHER tweets in this subject
        # that carry a non-empty reposted_by and whose own id traces back to
        # this tweet's text/author being reposted — but reposted_by tells us
        # only that *a* repost happened, not which original tweet it targets
        # beyond the record it sits on. So a `reposted_by`-bearing tweet is
        # itself the one list-member repost of *its own* content (decision
        # noted below). Quotes: a tweet with non-empty quoted_text quotes
        # another tweet; we match quoted_text against this subject's other
        # tweets' text (case/whitespace-insensitive substring-safe exact
        # match) to find which tweet it quotes.
        texts = {t["id"]: (t.get("text") or "").strip() for t in tws}
        repost_flag = {t["id"]: bool((t.get("reposted_by") or "").strip()) for t in tws}
        quoted_text = {t["id"]: (t.get("quoted_text") or "").strip() for t in tws}

        endorsements_per_tweet = {}
        for t in tws:
            tid = t["id"]
            # this tweet's own repost-by-a-list-member count: 1 if this
            # record itself carries a reposted_by, else 0. See note above.
            reposts = 1 if repost_flag[tid] else 0
            # quotes inside the subject that target this tweet's text
            this_text = texts[tid]
            quotes = 0
            if this_text:
                for other_id, qtext in quoted_text.items():
                    if other_id == tid:
                        continue
                    if qtext and qtext == this_text:
                        quotes += 1
            endorsements_per_tweet[tid] = reposts + quotes
        endorsements = max(endorsements_per_tweet.values(), default=0)

        # velocity: max over tweets of views / minutes since posted_at,
        # measured against the run's scraped_at (reproducible, not wall clock).
        velocities = []
        for t in tws:
            posted_dt = parse_iso(t.get("posted_at"))
            if posted_dt is None:
                continue
            minutes = (scraped_dt - posted_dt).total_seconds() / 60.0
            # A tweet posted at/after scraped_at (clock skew, or posted in
            # the same minute) would divide by ~0; floor at 1 minute so a
            # very fresh tweet gets a large but finite velocity instead of
            # inf or a crash.
            minutes = max(minutes, 1.0)
            views = t.get("views") or 0
            velocities.append(views / minutes)
        velocity = max(velocities, default=0.0)

        prepared.append({
            "subject": subj["subject"],
            "tweet_ids": ids,
            "authors": len(authors),
            "lists": lists_count,
            "endorsements": endorsements,
            "velocity": velocity,
        })

    # Second pass: velocity_rank needs every subject's velocity in this run.
    all_velocities = [p["velocity"] for p in prepared]
    for p in prepared:
        p["velocity_rank"] = percentile_rank(all_velocities, p["velocity"])
        p["cross_list"] = (p["lists"] == 2)

        flags = []
        if p["authors"] >= conv_n:
            flags.append("CONVERGENCE")
        if p["endorsements"] >= endorse_m:
            flags.append("ENDORSEMENT")
        if p["velocity_rank"] >= velocity_p:
            flags.append("VELOCITY")
        p["flags"] = flags
        p["tag"] = "TRENDING" if flags else "SINGLETON"

    return prepared


def main():
    ap = argparse.ArgumentParser(description="Score subjects.json in place.")
    ap.add_argument("--run-dir", required=True, help="run folder holding kept.json and subjects.json")
    ap.add_argument("--settings", default=None, help="path to settings.md (default: x-lists/settings.md next to this script)")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    settings_path = Path(args.settings).resolve() if args.settings else (Path(__file__).resolve().parent / "settings.md")

    kept_path = run_dir / "kept.json"
    subjects_path = run_dir / "subjects.json"

    kept_doc = load_json(kept_path)
    subjects_doc = load_json(subjects_path)
    settings = load_settings(settings_path)

    kept = kept_doc.get("kept", [])
    subjects_in = subjects_doc.get("subjects", [])

    scraped_at = kept_doc.get("kept_at")
    if not scraped_at:
        die("kept.json is missing 'kept_at' to measure velocity against")

    scored = score_subjects(kept, subjects_in, settings, scraped_at)

    subjects_doc["subjects"] = scored
    write_json(subjects_path, subjects_doc)

    n = len(scored)
    trending = sum(1 for s in scored if s["tag"] == "TRENDING")
    print(f"scored {n} subject(s): {trending} TRENDING, {n - trending} SINGLETON -> {subjects_path}")


if __name__ == "__main__":
    main()
