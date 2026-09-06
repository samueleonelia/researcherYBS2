#!/usr/bin/env python3
"""x_run.py - the one command that chains the X-list pipeline end to end.

    python3 x_run.py

creates a fresh run folder `x-lists/runs/<YYYY-MM-DD>-<HHMM>/` (UTC) and
drives, in order:

    1. x_scrape.py         (script)  ->  tweets.json, page.txt
    2. x_filter.py         (script)  ->  kept.json, links.md
    3. read agent(s)       (claude -p, prompts/read.md, one per batch of
                            x_read_batch links)  ->  notes/<id>.md
    4. cluster agent(s)    (claude -p, prompts/cluster.md [+ cluster-merge.md])
                                     ->  subjects.json
    5. x_score.py          (script)  ->  subjects.json, enriched
    6. judge agent(s)      (claude -p, prompts/judge.md, one per subject)
                                     ->  picks.md

Step 3 is new on 2026-09-06. The list feed only shows a collapsed preview of
a tweet, so cluster and judge used to work from text cut off at ~280
characters. The read step opens every surviving tweet on its own page and
writes its full text to notes/, and steps 4 and 6 prefer that text.

Every number this script obeys comes from settings.md at run time --
nothing here is hard-coded. If a step's script does not exist yet, the
chain stops with a clear message naming that step; it never lets the
missing file surface as a traceback.

Flags beyond the bare `python3 x_run.py` contract exist only to make the
chain testable and resumable, per GOAL.md's instruction to test the chain's
plumbing against the fixture:

    --run-dir DIR     use this folder instead of creating a fresh one
                       (e.g. one seeded with the fixture as tweets.json)
    --settings PATH   defaults to x-lists/settings.md
    --from STEP       start at this step (1-6), skipping earlier ones
                       because their output is already in --run-dir
    --only STEP       run just this one step

Python 3, standard library only.
"""

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from x_settings import load_settings, default_settings_path

HERE = Path(__file__).resolve().parent

STEP_NAMES = {
    1: "scrape",
    2: "filter",
    3: "read",
    4: "cluster",
    5: "score",
    6: "judge",
}

# The browser is a serial resource. GOAL.md section 3: "The browser is the one
# serial thing: never two agents on it at once." RUNLOG breach #1 records what
# happened when two agents drove it anyway. ego-browser task spaces isolate
# *tabs*, not the single browser process the CLI drives, so the read step runs
# its batches one after another regardless of x_agents_active_max. This is not
# a settings number; it is the project's standing rule about the browser.
READ_MAX_WORKERS = 1


def die(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
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


# ---------------------------------------------------------------- run folder

def new_run_dir(runs_root: Path) -> Path:
    """runs/<YYYY-MM-DD>-<HHMM>/, UTC, never colliding with an existing one."""
    now = datetime.now(timezone.utc)
    base = now.strftime("%Y-%m-%d-%H%M")
    candidate = runs_root / base
    suffix = 2
    while candidate.exists():
        candidate = runs_root / f"{base}-{suffix}"
        suffix += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


# ---------------------------------------------------------------- script steps

def run_script_step(step_num: int, script_name: str, run_dir: Path, settings_path: Path):
    """Shell out to one of the script steps (x_scrape/x_filter/x_score).

    If the script is missing, fail with a message naming the step -- never
    let a missing file surface as a traceback further down the chain.
    """
    label = STEP_NAMES[step_num]
    script_path = HERE / script_name
    if not script_path.exists():
        die(
            f"step {step_num} ({label}) cannot run: {script_name} does not "
            f"exist yet at {script_path}. Build it before running x_run.py."
        )
    cmd = [
        sys.executable, str(script_path),
        "--run-dir", str(run_dir),
        "--settings", str(settings_path),
    ]
    print(f"-- step {step_num} ({label}): {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(HERE))
    if result.returncode != 0:
        die(f"step {step_num} ({label}) failed: {script_name} exited {result.returncode}")


# ---------------------------------------------------------------- agent steps

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def load_prompt_template(prompt_name: str, step_num: int, label: str) -> str:
    path = HERE / "prompts" / prompt_name
    if not path.exists():
        die(
            f"step {step_num} ({label}) cannot run: prompts/{prompt_name} "
            f"does not exist yet at {path}. Build it before running x_run.py."
        )
    return path.read_text(encoding="utf-8")


def placeholders_in(template: str) -> set:
    return set(PLACEHOLDER_RE.findall(template))


def fill_template(template: str, values: dict) -> str:
    """Substitute every {{PLACEHOLDER}} found in `template` from `values`.
    Dies naming any placeholder the template needs that `values` does not
    provide, rather than shipping a literal {{FOO}} to the agent.
    """
    needed = placeholders_in(template)
    missing = [k for k in needed if k not in values]
    if missing:
        die(f"prompt needs placeholder(s) with no known value: {missing}")

    def _sub(m):
        return str(values[m.group(1)])

    return PLACEHOLDER_RE.sub(_sub, template)


def call_claude(prompt_text: str, model: str, cwd: Path, timeout: int = 1800) -> str:
    """Shell out to `claude -p` headless, prompt on stdin, at `model`.
    Returns the agent's stdout (its one-line summary); dies clearly on a
    non-zero exit or a missing `claude` binary.
    """
    cmd = ["claude", "-p", "--model", model]
    try:
        result = subprocess.run(
            cmd, input=prompt_text, capture_output=True, text=True,
            cwd=str(cwd), timeout=timeout,
        )
    except FileNotFoundError:
        die("the `claude` CLI is not on PATH; cannot run an agent step")
    except subprocess.TimeoutExpired:
        die(f"claude -p timed out after {timeout}s")
    if result.returncode != 0:
        die(f"claude -p exited {result.returncode}: {result.stderr.strip()[:2000]}")
    return result.stdout.strip()


def tweet_block(t: dict, notes: dict = None) -> str:
    """One tweet as the cluster and judge prompts see it.

    Since 2026-09-06 the text comes from the read step's note when there is
    one: `notes.json`-free, just notes/<id>.md, holding the tweet's FULL text
    read off its own page. The feed text in kept.json is a collapsed preview
    cut at ~280 characters, so it is only the fallback -- used when the read
    step wrote no usable note for this id.
    """
    note = (notes or {}).get(t["id"]) or {}
    text = note.get("full_text") or t.get("text")
    quoted = note.get("quoted") or t.get("quoted_text")
    lines = [f"id: {t['id']}", f"author: {t['author']}"]
    if text:
        lines.append(f"text: {text}")
    if quoted:
        lines.append(f"quoted_text: {quoted}")
    if t.get("card_title"):
        lines.append(f"card_title: {t['card_title']}")
    return "\n".join(lines)


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def run_pool(jobs, max_workers):
    """Run `jobs` (zero-arg callables) with at most `max_workers` at once,
    returning their results in the same order. Re-raises the first
    exception any job raised, after every job has finished."""
    if max_workers < 1:
        max_workers = 1
    results = [None] * len(jobs)
    errors = [None] * len(jobs)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(job): i for i, job in enumerate(jobs)}
        for fut in concurrent.futures.as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as e:  # noqa: BLE001 - surface after all jobs finish
                errors[i] = e
    for e in errors:
        if e is not None:
            raise e
    return results


# ---- step 3: read ----

# links.md (written by x_filter.py) is plain markdown: a `## POST` / `## REPOST`
# heading per survivor, an `- author:` line, and the bare permalink on its own
# line. Parse it tolerantly -- pull the status URL out of any line that holds
# one, and carry whatever kind/author heading was most recently seen.
STATUS_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:x|twitter)\.com/([A-Za-z0-9_]+)/status/(\d+)"
)
KIND_RE = re.compile(r"^#{1,6}\s*(POST|REPOST)\s*$", re.I)
AUTHOR_RE = re.compile(r"^[-*]?\s*author:\s*(\S+)", re.I)
REPOSTED_BY_RE = re.compile(r"^[-*]?\s*reposted_by:\s*(\S+)", re.I)


def parse_links_md(path: Path) -> list:
    """Return links.md's survivors, in file order, as dicts with
    id / url / author / kind / reposted_by. A duplicated id is kept once."""
    if not path.exists():
        die(
            "step 3 (read) cannot run: links.md is missing at "
            f"{path}. It is written by step 2 (filter)."
        )
    kind = "POST"
    author = ""
    reposted_by = ""
    out = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = KIND_RE.match(line)
        if m:
            kind = m.group(1).upper()
            author = ""
            reposted_by = ""
            continue
        m = AUTHOR_RE.match(line)
        if m:
            author = m.group(1)
            continue
        m = REPOSTED_BY_RE.match(line)
        if m:
            reposted_by = m.group(1)
            continue
        m = STATUS_URL_RE.search(line)
        if not m:
            continue
        handle, tweet_id = m.group(1), m.group(2)
        if tweet_id in seen:
            continue
        seen.add(tweet_id)
        out.append({
            "id": tweet_id,
            "url": m.group(0),
            "author": author or ("@" + handle),
            "kind": kind,
            "reposted_by": reposted_by,
        })
    return out


def link_block(link: dict) -> str:
    lines = [
        f"id: {link['id']}",
        f"url: {link['url']}",
        f"author: {link['author']}",
        f"kind: {link['kind']}",
    ]
    if link.get("reposted_by"):
        lines.append(f"reposted_by: {link['reposted_by']}")
    return "\n".join(lines)


NOTE_HEADING_RE = re.compile(r"^##\s+(\w+)\s*$", re.M)


def parse_note(text: str) -> dict:
    """One notes/<id>.md into a dict. `- key: value` lines become fields;
    `## section` headings become fields holding everything up to the next
    heading. A `(none)` / `(unavailable...)` body reads as empty."""
    out = {}
    head, sections = text, []
    first = NOTE_HEADING_RE.search(text)
    if first:
        head = text[:first.start()]
        marks = list(NOTE_HEADING_RE.finditer(text))
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            sections.append((m.group(1).lower(), text[m.end():end]))
    for line in head.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        body = line.lstrip("-").strip()
        if ":" not in body:
            continue
        key, _, value = body.partition(":")
        out[key.strip().lower()] = value.strip()
    for name, body in sections:
        body = body.strip()
        if body.lower().startswith("(none)") or body.lower().startswith("(unavailable"):
            body = ""
        out[name] = body
    return out


def load_notes(run_dir: Path) -> dict:
    """id -> parsed note, for every notes/<id>.md this run wrote. Returns an
    empty dict when the read step has not run -- callers then fall back to
    the feed text, so an older run folder still replays."""
    notes_dir = run_dir / "notes"
    if not notes_dir.is_dir():
        return {}
    out = {}
    for path in sorted(notes_dir.glob("*.md")):
        try:
            note = parse_note(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        out[note.get("id") or path.stem] = note
    return out


def step_read(run_dir: Path, settings: dict):
    links = parse_links_md(run_dir / "links.md")
    notes_dir = run_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    if not links:
        print("-- step 3 (read): links.md holds no survivors, nothing to read")
        return

    batch_size = settings["x_read_batch"]
    model = settings.get("read_model", "sonnet")
    batches = list(chunked(links, batch_size))
    template = load_prompt_template("read.md", 3, "read")
    task_space = f"x-lists read {run_dir.name}"

    def make_job(i, batch):
        def job():
            values = {
                "RUN_DIR": str(run_dir),
                "NOTES_DIR": str(notes_dir),
                "TASK_SPACE": task_space,
                "BATCH_NOTE": (
                    f"This is batch {i + 1} of {len(batches)}. Other batches hold "
                    f"other tweets; you read only the ones listed below."
                ),
                "LINKS": "\n\n".join(link_block(l) for l in batch),
                "ALLOWED_URLS": "\n".join(l["url"] for l in batch),
            }
            prompt = fill_template(template, values)
            call_claude(prompt, model, HERE)
        return job

    print(
        f"-- step 3 (read): {len(links)} link(s) in {len(batches)} batch(es) of "
        f"{batch_size}, model={model}, serial (the browser is not shareable)"
    )
    run_pool([make_job(i, b) for i, b in enumerate(batches)], READ_MAX_WORKERS)

    validate_notes(links, notes_dir)


def validate_notes(links: list, notes_dir: Path):
    """Check 9, enforced in code: every link in links.md has a note, and that
    note actually says something. Fails loudly naming the ids."""
    missing = []
    empty = []
    for link in links:
        path = notes_dir / f"{link['id']}.md"
        if not path.exists():
            missing.append(link["id"])
            continue
        note = parse_note(path.read_text(encoding="utf-8"))
        if not note.get("full_text") and (note.get("status", "").lower() != "unavailable"):
            empty.append(link["id"])
    if missing:
        die(
            "step 3 (read) finished but "
            f"{len(missing)} link(s) in links.md have no note in {notes_dir}: "
            + ", ".join(missing)
        )
    if empty:
        die(
            "step 3 (read) finished but "
            f"{len(empty)} note(s) hold no full_text and are not marked "
            "status: unavailable: " + ", ".join(empty)
        )
    print(f"-- step 3 (read): {len(links)} note(s) verified in {notes_dir}")


# ---- step 4: cluster ----

def step_cluster(run_dir: Path, settings: dict):
    kept_doc = load_json(run_dir / "kept.json")
    kept = kept_doc.get("kept") or []
    # The read step's full text, where it exists; tweet_block prefers it.
    notes = load_notes(run_dir)
    chunk_size = settings["x_cluster_chunk"]
    model = settings.get("cluster_model", "opus")
    max_workers = settings.get("x_agents_active_max", 1)
    subjects_path = run_dir / "subjects.json"

    parts = list(chunked(kept, chunk_size))

    if len(parts) <= 1:
        template = load_prompt_template("cluster.md", 4, "cluster")
        values = {
            "RUN_DIR": str(run_dir),
            "TWEETS": "\n\n".join(tweet_block(t, notes) for t in kept),
            "PART_NOTE": "",
            "OUTPUT_PATH": str(subjects_path),
        }
        prompt = fill_template(template, values)
        print(f"-- step 4 (cluster): 1 agent, {len(kept)} tweet(s), model={model}, "
              f"{len(notes)} note(s) available")
        call_claude(prompt, model, HERE)
    else:
        part_template = load_prompt_template("cluster.md", 4, "cluster")
        part_paths = [run_dir / f"cluster_part_{i+1}.json" for i in range(len(parts))]

        def make_job(i, part):
            def job():
                values = {
                    "RUN_DIR": str(run_dir),
                    "TWEETS": "\n\n".join(tweet_block(t, notes) for t in part),
                    "PART_NOTE": f"This is part {i+1} of {len(parts)}. Other parts hold "
                                 f"other sources. Group only what is in front of you; an "
                                 f"event another part ran is merged later.",
                    "OUTPUT_PATH": str(part_paths[i]),
                }
                prompt = fill_template(part_template, values)
                call_claude(prompt, model, HERE)
            return job

        print(f"-- step 4 (cluster): {len(parts)} part(s), model={model}, up to {max_workers} at once, "
              f"{len(notes)} note(s) available")
        run_pool([make_job(i, p) for i, p in enumerate(parts)], max_workers)

        # Build PART_SUBJECTS text from what each part actually wrote.
        by_id = {t["id"]: t for t in kept}
        part_blocks = []
        for i, part_path in enumerate(part_paths):
            part_doc = load_json(part_path)
            for subj in part_doc.get("subjects", []):
                lines = [f"[part {i+1}] {subj['subject']}"]
                for tid in subj["tweet_ids"]:
                    t = by_id.get(tid)
                    lines.append("  " + tweet_block(t, notes).replace("\n", " | ") if t else f"  {tid} (unknown)")
                part_blocks.append("\n".join(lines))

        merge_template = load_prompt_template("cluster-merge.md", 4, "cluster (merge)")
        merge_values = {
            "RUN_DIR": str(run_dir),
            "PARTS": str(len(parts)),
            "PART_SUBJECTS": "\n\n".join(part_blocks),
            "ALL_TWEET_IDS": "\n".join(t["id"] for t in kept),
            "OUTPUT_PATH": str(subjects_path),
        }
        merge_prompt = fill_template(merge_template, merge_values)
        print("-- step 4 (cluster): merging parts, model=" + model)
        call_claude(merge_prompt, model, HERE)

    if not subjects_path.exists():
        die("step 4 (cluster) finished but subjects.json was not written")
    subjects_doc = load_json(subjects_path)
    validate_cluster_coverage(kept, subjects_doc)


def validate_cluster_coverage(kept: list, subjects_doc: dict):
    """Every kept id in exactly one subject -- checked here, in code, so a
    bad agent output fails the run instead of drifting downstream."""
    kept_ids = {t["id"] for t in kept}
    seen = {}
    for si, subj in enumerate(subjects_doc.get("subjects") or []):
        for tid in subj.get("tweet_ids") or []:
            if tid in seen:
                die(f"cluster output invalid: id {tid} in two subjects")
            seen[tid] = si
    covered = set(seen)
    if covered != kept_ids:
        die(
            "cluster output invalid: coverage mismatch "
            f"(missing={kept_ids - covered}, invented={covered - kept_ids})"
        )


# ---- step 6: judge ----

def read_optional(path: Path, empty_note: str) -> str:
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip() or empty_note
        except OSError:
            return empty_note
    return empty_note


def format_profile(profile: dict) -> str:
    lines = []
    for section, label in (("storylines", "Storylines"), ("themes", "Themes")):
        items = profile.get(section) or []
        if not items:
            continue
        lines.append(f"### {label}")
        for item in items:
            name = item.get("name", "")
            note = item.get("note", "")
            lines.append(f"- {name}" + (f" -- {note}" if note else ""))
    return "\n".join(lines) if lines else "(no profile available)"


def find_lens_and_profile(root: Path):
    """Read-only lookups outside x-lists/, per GOAL.md step 5 ('profile,
    lens, preferences in, read from the root'). Missing files degrade to an
    empty block, matching judge.md's own "empty block" convention."""
    profile_path = root / "shows" / "profile.json"
    prefs_path = root / "preferences.md"
    lens_path = root / ".claude" / "skills" / "ybs-brief" / "prompts" / "_lens.md"

    profile_date = "unknown"
    profile_text = "(no profile available)"
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile_date = profile.get("built_local_date") or profile.get("built_utc", "unknown")
            profile_text = format_profile(profile)
        except (json.JSONDecodeError, OSError):
            pass

    preferences_text = read_optional(prefs_path, "(none)")
    lens_text = read_optional(lens_path, "(no lens available)")
    return profile_date, profile_text, preferences_text, lens_text


def step_judge(run_dir: Path, settings: dict, root: Path):
    subjects_doc = load_json(run_dir / "subjects.json")
    subjects = subjects_doc.get("subjects") or []
    kept_doc = load_json(run_dir / "kept.json")
    by_id = {t["id"]: t for t in kept_doc.get("kept") or []}
    notes = load_notes(run_dir)
    model = settings.get("judge_model", "opus")
    max_workers = settings.get("x_agents_active_max", 1)
    curious_percentile = settings["x_curious_percentile"]

    profile_date, profile_text, preferences_text, lens_text = find_lens_and_profile(root)

    template = load_prompt_template("judge.md", 6, "judge")
    verdict_paths = [run_dir / f"judge_{i+1}.json" for i in range(len(subjects))]

    def make_job(i, subj):
        def job():
            tweets = [by_id[tid] for tid in subj["tweet_ids"] if tid in by_id]
            measures = {k: subj.get(k) for k in
                        ("authors", "lists", "endorsements", "velocity", "velocity_rank", "cross_list")}
            values = {
                "RUN_DIR": str(run_dir),
                "SUBJECT": subj["subject"],
                "SCORE_TAG": subj.get("tag", ""),
                "FLAGS": ", ".join(subj.get("flags") or []),
                "MEASURES": json.dumps(measures, indent=2),
                "VELOCITY_RANK": str(subj.get("velocity_rank")),
                "CURIOUS_PERCENTILE": str(curious_percentile),
                "TWEETS": "\n\n".join(tweet_block(t, notes) + f"\nurl: {t.get('url','')}" for t in tweets),
                "PROFILE_DATE": profile_date,
                "PROFILE": profile_text,
                "PREFERENCES": preferences_text,
                "LENS": lens_text,
                "OUTPUT_PATH": str(verdict_paths[i]),
            }
            prompt = fill_template(template, values)
            call_claude(prompt, model, HERE)
        return job

    print(f"-- step 6 (judge): {len(subjects)} subject(s), model={model}, up to {max_workers} at once, "
          f"{len(notes)} note(s) available")
    run_pool([make_job(i, s) for i, s in enumerate(subjects)], max_workers)

    verdict_texts = []
    for i, path in enumerate(verdict_paths):
        if not path.exists():
            die(f"step 6 (judge) finished but subject #{i+1} wrote no verdict at {path}")
        verdict_texts.append(path.read_text(encoding="utf-8"))
        load_json(path)  # dies clearly if a verdict file is not valid JSON

    merge_judge_verdicts(run_dir, verdict_texts, settings, model)


def merge_judge_verdicts(run_dir: Path, verdict_texts: list, settings: dict, model: str):
    """Step 6's second agent: judge-merge.md turns every per-subject verdict
    into picks.md, applying the x_picks_max ceiling. This is the only
    "judgment" left after each subject was judged alone -- which kept
    subjects the ceiling cuts -- so it is an agent call, not code, per
    prompts/judge-merge.md."""
    picks_max = settings["x_picks_max"]
    picks_path = run_dir / "picks.md"
    template = load_prompt_template("judge-merge.md", 6, "judge (merge)")
    values = {
        "RUN_DIR": str(run_dir),
        "PICKS_MAX": str(picks_max),
        "VERDICTS": "\n\n".join(verdict_texts),
        "OUTPUT_PATH": str(picks_path),
    }
    prompt = fill_template(template, values)
    print(f"-- step 6 (judge): merging {len(verdict_texts)} verdict(s), ceiling {picks_max}, model={model}")
    call_claude(prompt, model, HERE)

    if not picks_path.exists():
        die("step 6 (judge) finished but picks.md was not written")


# ---------------------------------------------------------------- chain

def run_chain(run_dir: Path, settings_path: Path, settings: dict, start: int, only: int, root: Path):
    steps = [only] if only else list(range(start, 7))
    for step in steps:
        if step == 1:
            run_script_step(1, "x_scrape.py", run_dir, settings_path)
        elif step == 2:
            run_script_step(2, "x_filter.py", run_dir, settings_path)
        elif step == 3:
            step_read(run_dir, settings)
        elif step == 4:
            step_cluster(run_dir, settings)
        elif step == 5:
            run_script_step(5, "x_score.py", run_dir, settings_path)
        elif step == 6:
            step_judge(run_dir, settings, root)
        else:
            die(f"no such step: {step}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", default=None,
                     help="use this folder instead of creating a fresh one")
    ap.add_argument("--settings", default=None,
                     help="path to settings.md (default: x-lists/settings.md)")
    ap.add_argument("--from", dest="from_step", type=int, default=1, choices=range(1, 7),
                     help="start at this step, skipping earlier ones")
    ap.add_argument("--only", type=int, default=0, choices=range(0, 7),
                     help="run just this one step (0 = off)")
    args = ap.parse_args()

    settings_path = Path(args.settings).resolve() if args.settings else default_settings_path()
    settings = load_settings(settings_path)

    root = HERE.parent  # the repo root, for read-only lens/profile/preferences

    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_dir = new_run_dir(HERE / "runs")

    print(f"run folder: {run_dir}")
    run_chain(run_dir, settings_path, settings, args.from_step, args.only, root)
    print(f"done: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
