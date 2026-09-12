#!/usr/bin/env python3
"""x_run.py - the X-list pipeline: two commands, seven steps.

    python3 x_run.py scrape [--run-dir DIR] [--settings PATH]
    python3 x_run.py next   --run-dir DIR  [--settings PATH]

`scrape` creates (or reuses) a run folder `briefs/x/<YYYY-MM-DD>-<HHMM>/` at
the repo root (UTC) and runs the two scripts that need no agent. `next` is
the lane: called by `ybs_run.py x-next`, it looks at the folder, does what
code can do, and prints what the orchestrator must launch now. The seven
steps, in order:

    1. x_scrape.py     (script, `scrape`)  ->  tweets.json, page.txt
    2. x_filter.py     (script, `scrape`)  ->  kept.json, links.md
    3. read            (agents, `next`)    ->  notes/<id>.md, one per tweet
    4. cluster         (agents, `next`)    ->  subjects.json
    5. x_score.py      (script, `next`)    ->  subjects.json, enriched
    6. judge           (agents, `next`)    ->  judge_<i>.json, then picks.md
    7. write           (agent,  `next`)    ->  brief.md

No agent is run by this script. Every agent step is a subagent of the
orchestrator, launched from a generated agent file in `.claude/agents/`
(`ybs4-x-reader`, `ybs4-x-cluster`, `ybs4-x-judge`, `ybs4-x-write`) whose
model and effort come from settings.md's `## X models` table through
`ybs_run.py build`. Before 2026-09-12 this script spawned a second Claude
Code (`claude -p`) per agent step; launched from inside the desktop app that
copy could not renew its own login, and the X half died whenever the login
expired mid-run. Now the X agents run under the orchestrator's own session.

How `next` works. The state of the lane is the files in the run folder:
the prompt files it has written and the output files the agents have
written. Each call re-derives the phase from them, in this order, and a
phase with nothing left to do falls through to the next:

    phase          prompt file written by `next`          agent writes
    -------------  -------------------------------------  ------------------------
    read           prompts/read-p<pass>-b<k>.md           notes/<id>.md
    cluster        prompts/cluster-a<n>.md                subjects.json
      (parts)      prompts/cluster-part<k>-a<n>.md        cluster_part_<k>.json
    cluster-merge  prompts/cluster-merge-a<n>.md          subjects.json
    judge          prompts/judge-<i>-a<n>.md              judge_<i>.json
    judge-merge    prompts/judge-merge-a<n>.md            picks.md
    write          prompts/write-a<n>.md                  brief.md

`<pass>` and `<n>` are attempt numbers, 1 or 2: a phase whose output is
still missing or invalid after two attempts fails the lane, and the reason
says which. Every launch is one line, `Read <path> and follow it.`, and the
orchestrator calls `next` again only once every launch it printed has
returned, so a prompt file is never launched twice. The JSON `next` prints
is the only thing on its stdout; progress and script output go to stderr:

    {"phase": "read", "attempt": 1,
     "launch": [{"agent": "ybs4-x-reader",
                 "prompt": "Read <run>/prompts/read-p1-b1.md and follow it.",
                 "description": "x read p1 b1"}],
     "notes": ["4 link(s) already have a usable note"]}

`phase` is `done` once brief.md exists and `failed` (with `reason`) when a
phase ran out of attempts. The read phase re-reads once whatever pass 1
left without a note, and after pass 2 writes a `status: unavailable` note
itself for what is still missing -- the only note code writes, and it says
so. The cluster phase sets an invalid subjects.json aside and quotes the
problem in the retry prompt. A subject with no verdict after two attempts
is left out of the merge and named in `notes`.

Every number this script obeys comes from settings.md at run time --
nothing here is hard-coded, and nothing here has a fallback. If a step's
script does not exist, the lane stops with a clear message naming that
step; it never lets the missing file surface as a traceback.

The ten finish-line checks, and where each one lives:

    check | What it checks                         | Enforced by
    ------|----------------------------------------|-------------------------
     1.   | tweets.json schema + x_tweets_min      | x_checks.check1_schema
     2.   | the scrape window rule                 | x_checks.check2_window
     3.   | kept.json = the six filter rules       | x_checks.check3_kept
     4.   | every kept id in exactly one subject   | x_checks.check4_subject_coverage
          |                                        | + cluster_coverage_problem below
     5.   | every subject carries its score fields | x_checks.check5_subject_fields
     6.   | picks.md within the x_picks_max        | prompts/judge-merge.md, handed
          | ceiling, each pick tagged              | the ceiling by `next`
     7.   | the tests pass                         | x-lists/tests/
     8.   | links.md = the survivors, POST/REPOST  | x_checks.check8_links
     9.   | every link has a note with FULL text   | validate_notes below
          |                                        | + prompts/read.md
    10.   | brief.md follows the template, quotes  | x_checks.check10_mechanical
          | only what the notes say                | + prompts/write.md (reader half)

`x_checks.py` is run by `x-lists/tests/` and by a verifier agent. A run
never calls it: the lane enforces only the checks written into it here (4,
6's ceiling and 9), so a bad agent output stops the lane instead of
drifting downstream.

Python 3, standard library only.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from x_settings import load_settings, default_settings_path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]  # the repo root: .claude/skills/ybs-brief/x-lists -> root

STEP_NAMES = {
    1: "scrape",
    2: "filter",
    3: "read",
    4: "cluster",
    5: "score",
    6: "judge",
    7: "write",
}

# Which generated agent file runs which lane phase. The names are the
# `name:` of the templates in .claude/skills/ybs-brief/agents/x-*.md.tmpl.
AGENT_OF = {
    "read": "ybs4-x-reader",
    "cluster": "ybs4-x-cluster",
    "judge": "ybs4-x-judge",
    "write": "ybs4-x-write",
}

# A read agent works in its own ego task space; two agents in one task space
# is the thing that must never happen. The name carries the run, the pass and
# the batch, so no two batches of any pass ever share one.
TASK_SPACE = "x read {run} p{pass_no} b{k}"


def die(msg: str, code: int = 1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def say(msg: str):
    """Progress, on stderr: `next`'s stdout is its JSON and nothing else."""
    print(msg, file=sys.stderr)


def load_json(path: Path):
    if not path.exists():
        die(f"missing file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"bad JSON in {path}: {e}")


def load_json_or_none(path: Path):
    """The file's JSON, or None when it is missing or not JSON at all."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


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

def run_script_step(step_num: int, script_name: str, run_dir: Path, settings_path: Path,
                    quiet: bool = False):
    """Shell out to one of the script steps (x_scrape/x_filter/x_score).

    If the script is missing, fail with a message naming the step -- never
    let a missing file surface as a traceback further down the chain.
    `quiet` is for `next`: the step's line and the script's own output go to
    stderr, so stdout stays the one JSON object.
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
    line = f"-- step {step_num} ({label}): {' '.join(cmd)}"
    if quiet:
        say(line)
        result = subprocess.run(cmd, cwd=str(HERE), capture_output=True, text=True)
        for stream in (result.stdout, result.stderr):
            if stream and stream.strip():
                say(stream.rstrip())
    else:
        print(line)
        result = subprocess.run(cmd, cwd=str(HERE))
    if result.returncode != 0:
        die(f"step {step_num} ({label}) failed: {script_name} exited {result.returncode}")


# ---------------------------------------------------------------- prompts

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


def tweet_block(t: dict, notes: dict = None) -> str:
    """One tweet as the cluster and judge prompts see it.

    Since 2026-09-06 the text comes from the read step's note when there is
    one: just notes/<id>.md, holding the tweet's FULL text read off its own
    page. The feed text in kept.json is a collapsed preview cut at ~280
    characters, so it is only the fallback -- used when the read step wrote
    no usable note for this id.
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


# ---- links and notes ----

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


UNAVAILABLE_REASON = "(unavailable: no note after two read passes)"


def note_is_usable(notes_dir: Path, tweet_id: str) -> bool:
    """The one test of a note, shared by the read phase and validate_notes: the
    file exists and either holds a full_text or says `status: unavailable`.
    Anything else counts as no note at all."""
    path = notes_dir / f"{tweet_id}.md"
    if not path.exists():
        return False
    try:
        note = parse_note(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    return bool(note.get("full_text")) or note.get("status", "").lower() == "unavailable"


def links_without_notes(links: list, notes_dir: Path) -> list:
    """The links `validate_notes` would fail on, in file order."""
    return [l for l in links if not note_is_usable(notes_dir, l["id"])]


def write_unavailable_note(notes_dir: Path, link: dict) -> None:
    """The one note in the whole lane that code writes rather than an agent.

    It is the last resort of the read phase: two read passes went by and
    this link still has no note. The shape is prompts/read.md's own "when a
    tweet will not load" shape, so `parse_note`, `validate_notes` and
    `tweet_block`'s fallback all read it as they read any other note -- and
    the reason line says in words that no agent read this tweet, so nobody
    downstream mistakes it for a page that was actually opened."""
    text = (
        f"# {link['id']}\n\n"
        f"- id: {link['id']}\n"
        f"- url: {link['url']}\n"
        f"- author: {link['author']}\n"
        f"- kind: {link['kind']}\n"
        "- posted_at:\n"
        "- replies: 0\n"
        "- reposts: 0\n"
        "- likes: 0\n"
        "- views: 0\n"
        "- status: unavailable\n\n"
        "## full_text\n\n"
        f"{UNAVAILABLE_REASON}\n"
        "This note was written by x_run.py, not by a read agent: the tweet was\n"
        "handed to a read sub-agent twice and neither pass left a note.\n\n"
        "## quoted\n\n(none)\n\n"
        "## media\n\n(none)\n"
    )
    notes_dir.mkdir(parents=True, exist_ok=True)
    (notes_dir / f"{link['id']}.md").write_text(text, encoding="utf-8")


def validate_notes(links: list, notes_dir: Path):
    """Check 9's countable half, enforced in code: every link in links.md has
    a note in notes/, and that note actually says something. Fails loudly
    naming the ids.

    The rest of check 9 -- that the note was written from the tweet's OWN
    page by a read sub-agent, and holds the tweet's FULL text rather than the
    feed's collapsed ~280-character preview -- is prompts/read.md's job; no
    code here can tell one text from the other."""
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
    say(f"-- step 3 (read): {len(links)} note(s) verified in {notes_dir}")


# ---- cluster ----

def cluster_coverage_problem(kept: list, subjects_doc) -> str:
    """Check 4 in code: every kept id in exactly one subject. Returns the
    problem as text, or None when the file is right. The lane hands the text
    back to the agent in its retry prompt, so it is written to be read."""
    if not isinstance(subjects_doc, dict) or not isinstance(subjects_doc.get("subjects"), list):
        return "the file is not a JSON object with a `subjects` list"
    kept_ids = {t["id"] for t in kept}
    seen = {}
    for si, subj in enumerate(subjects_doc["subjects"]):
        if not isinstance(subj, dict):
            return f"subject #{si + 1} is not an object"
        for tid in subj.get("tweet_ids") or []:
            if tid in seen:
                return f"id {tid} in two subjects"
            seen[tid] = si
    covered = set(seen)
    if covered != kept_ids:
        return (f"coverage mismatch (missing={sorted(kept_ids - covered)}, "
                f"invented={sorted(covered - kept_ids)})")
    return None


def validate_cluster_coverage(kept: list, subjects_doc: dict):
    """`cluster_coverage_problem` as a hard stop, for callers that want one."""
    problem = cluster_coverage_problem(kept, subjects_doc)
    if problem:
        die(f"cluster output invalid: {problem}")


# ---- judge and write inputs ----

def read_optional(path: Path, empty_note: str) -> str:
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip() or empty_note
        except OSError:
            return empty_note
    return empty_note


def preference_lines(text: str) -> list:
    """The instruction lines of preferences.md, and nothing else.

    The file is a readable note to him above a `---` line, and his
    instructions below it. Only what is below the first `---` counts. Inside
    that, a line starting with # and anything in an HTML comment are notes
    too. A file with no `---` is read whole. The same function, character for
    character, lives in x-lists/x_run.py; a test keeps the two identical.
    """
    parts = re.split(r"^---\s*$", text, maxsplit=1, flags=re.M)
    text = parts[1] if len(parts) == 2 else parts[0]
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    lines = [ln.strip() for ln in text.splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")]


def read_preferences(path: Path, empty_note: str) -> str:
    """preferences.md with his notes stripped, so only instructions reach a
    prompt. Missing, unreadable or all-notes all mean the same thing: he has
    asked for nothing in particular."""
    lines = preference_lines(read_optional(path, ""))
    return "\n".join(lines) or empty_note


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
    """Read-only lookups outside x-lists/. The judge and write phases need
    the show profile, Yaron's lens and his preferences, and all three live at
    the repo root: this pipeline reads outside its own folder but never
    writes there. Missing files degrade to an empty block, matching judge.md's
    own "empty block" convention."""
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

    preferences_text = read_preferences(prefs_path, "(none)")
    lens_text = read_optional(lens_path, "(no lens available)")
    return profile_date, profile_text, preferences_text, lens_text


# One pick's block in picks.md is a level-2 heading "## <n>. <title>" (written
# by judge-merge.md, see prompts/judge-merge.md's Output section) followed by
# its Tag/Flags/Storyline/Why lines and a nested bullet with the best tweet's
# handle, an em dash, and its permalink, then a `>` quote line. We only need
# the heading, the permalink (to resolve the id) and the storyline text.
PICK_HEADING_RE = re.compile(r"^##\s+\d+\.\s*(.+?)\s*$", re.M)
PICK_TWEET_LINE_RE = re.compile(r"^\s*-\s*(@\S+)\s*—\s*(https?://\S+)\s*$", re.M)


def parse_picks_md(path: Path) -> list:
    """picks.md into a list of {title, handle, url, id} dicts, one per pick,
    in file order. Dies naming the pick if it carries no permalink line --
    the write phase cannot resolve a note without one."""
    if not path.exists():
        die(
            "step 7 (write) cannot run: picks.md is missing at "
            f"{path}. It is written by step 6 (judge)."
        )
    text = path.read_text(encoding="utf-8")
    headings = list(PICK_HEADING_RE.finditer(text))
    picks = []
    for i, m in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[m.start():end]
        title = m.group(1).strip()
        tweet_m = PICK_TWEET_LINE_RE.search(block)
        if not tweet_m:
            die(f"step 7 (write) cannot run: pick '{title}' in picks.md has no tweet permalink line")
        url = tweet_m.group(2)
        id_m = STATUS_URL_RE.search(url)
        if not id_m:
            die(f"step 7 (write) cannot run: pick '{title}' has an unrecognised permalink: {url!r}")
        picks.append({
            "title": title,
            "handle": tweet_m.group(1),
            "url": url,
            "id": id_m.group(2),
        })
    return picks


def build_notes_block(run_dir: Path, picks: list) -> str:
    """{{NOTES}}: the full text of each PICKED tweet's notes/<id>.md, one
    block per tweet, headed by its id. The id is resolved from the pick's
    permalink (the last path segment), per the interface gap the write phase
    has to close: picks.md carries the permalink, notes are filed by id.

    Fails loudly, naming the pick and the missing id, when a pick has no
    matching note file -- never hands the writing agent a pick with no note,
    and never silently drops the pick (the finish-line check needs every
    figure in the brief to trace to that pick's note, which is impossible
    without one)."""
    notes_dir = run_dir / "notes"
    missing = []
    blocks = []
    for p in picks:
        note_path = notes_dir / f"{p['id']}.md"
        if not note_path.exists():
            missing.append(f"'{p['title']}' (permalink {p['url']}, expected note id {p['id']})")
            continue
        blocks.append(f"### {p['id']}\n\n" + note_path.read_text(encoding="utf-8").strip())
    if missing:
        die(
            "step 7 (write) cannot run: the following pick(s) have no note file "
            f"in {notes_dir}: " + "; ".join(missing)
        )
    return "\n\n".join(blocks) if blocks else "(no picks, no notes)"


def format_run_datetime(run_name: str) -> str:
    """The run folder's name (e.g. `2026-09-06-0954`, or with a `-2`/`-final`
    collision suffix `new_run_dir` may add) into `{{RUN_DATETIME}}`'s fixed
    shape: `6 September 2026 at 09:54 UTC`. The write prompt does no date
    maths itself, so this is the lane's job."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})", run_name)
    if not m:
        die(f"step 7 (write) cannot run: run folder name {run_name!r} is not YYYY-MM-DD-HHMM")
    year, month, day, hour, minute = m.groups()
    dt = datetime(int(year), int(month), int(day))
    return f"{dt.day} {dt.strftime('%B')} {dt.year} at {hour}:{minute} UTC"


# ---------------------------------------------------------------- the lane

def launch_entry(phase: str, path: Path, description: str) -> dict:
    return {"agent": AGENT_OF[phase],
            "prompt": f"Read {path} and follow it.",
            "description": description}


def attempts(prompts_dir: Path, pattern: str) -> int:
    """How many prompt files of one kind `next` has written: the attempts so
    far. The files are the record; nothing else counts them."""
    return len(list(prompts_dir.glob(pattern)))


REJECTED = ("\n\n## Your last attempt was rejected\n\n"
            "The file you wrote was set aside because code found this problem:\n\n"
            "    {problem}\n\n"
            "Write the file again, fixing exactly that.\n")
NO_FILE = ("\n\n## Your last attempt wrote no file\n\n"
           "Nothing was found at the output path afterwards. Write it this time.\n")


def write_prompt(prompts_dir: Path, name: str, text: str, attempt: int,
                 problem: str = None) -> Path:
    """One prompt file, with the last attempt's verdict appended on a retry."""
    if attempt > 1:
        text = text.rstrip() + (REJECTED.format(problem=problem) if problem else NO_FILE)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    path = prompts_dir / name
    path.write_text(text, encoding="utf-8")
    return path


def lane_result(phase: str, attempt: int, launches: list, notes: list) -> dict:
    return {"phase": phase, "attempt": attempt, "launch": launches, "notes": notes}


def lane_failed(reason: str, notes: list) -> dict:
    return {"phase": "failed", "launch": [], "notes": notes, "reason": reason}


def lane_read(run_dir: Path, settings: dict, prompts_dir: Path, notes: list):
    """Phase read: launches for the links without a usable note, two passes,
    then the unavailable notes code writes. None once every link has one."""
    links = parse_links_md(run_dir / "links.md")
    notes_dir = run_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    todo = links_without_notes(links, notes_dir)
    if todo:
        passes = max((int(m.group(1)) for p in prompts_dir.glob("read-p*-b*.md")
                      for m in [re.match(r"read-p(\d+)-b\d+\.md$", p.name)] if m),
                     default=0)
        if passes >= 2:
            for link in todo:
                write_unavailable_note(notes_dir, link)
            notes.append(f"{len(todo)} note(s) written here in code as status: "
                         f"unavailable, no agent read them: "
                         + ", ".join(l["id"] for l in todo))
        else:
            pass_no = passes + 1
            skipped = len(links) - len(todo)
            if skipped:
                notes.append(f"{skipped} link(s) already have a usable note")
            if pass_no == 2:
                notes.append(f"{len(todo)} note(s) missing after pass 1, re-reading once")
            batches = list(chunked(todo, settings["x_read_batch"]))
            template = load_prompt_template("read.md", 3, "read")
            launches = []
            for k, batch in enumerate(batches, start=1):
                values = {
                    "RUN_DIR": str(run_dir),
                    "NOTES_DIR": str(notes_dir),
                    "TASK_SPACE": TASK_SPACE.format(run=run_dir.name, pass_no=pass_no, k=k),
                    "BATCH_NOTE": (
                        f"This is batch {k} of {len(batches)}. Other batches hold "
                        f"other tweets, read by other sub-agents at the same time in "
                        f"their own task spaces; you read only the ones listed below, "
                        f"one at a time, in your own task space."
                    ),
                    "LINKS": "\n\n".join(link_block(l) for l in batch),
                    "ALLOWED_URLS": "\n".join(l["url"] for l in batch),
                }
                path = write_prompt(prompts_dir, f"read-p{pass_no}-b{k}.md",
                                    fill_template(template, values), 1)
                launches.append(launch_entry("read", path, f"x read p{pass_no} b{k}"))
            return lane_result("read", pass_no, launches, notes)
    validate_notes(links, notes_dir)
    return None


def lane_cluster(run_dir: Path, settings: dict, settings_path: Path,
                 prompts_dir: Path, notes: list):
    """Phase cluster: one agent under `x_cluster_chunk`, parts and a merge
    above it, two attempts each; then the score script. None once
    subjects.json is valid and scored."""
    kept = load_json(run_dir / "kept.json").get("kept") or []
    subjects_path = run_dir / "subjects.json"
    parts = list(chunked(kept, settings["x_cluster_chunk"]))
    problem = None

    if not kept:
        if not subjects_path.exists():
            write_json(subjects_path, {"subjects": []})
            notes.append("no kept tweet: nothing to group, subjects.json written empty")
    elif subjects_path.exists():
        problem = cluster_coverage_problem(kept, load_json_or_none(subjects_path))
        if problem:
            kind = "cluster-merge-a*.md" if len(parts) > 1 else "cluster-a*.md"
            n = attempts(prompts_dir, kind) or 1
            aside = run_dir / f"subjects.invalid-a{n}.json"
            subjects_path.rename(aside)
            notes.append(f"subjects.json set aside as {aside.name}: {problem}")

    if not subjects_path.exists():
        tweet_notes = load_notes(run_dir)
        if len(parts) <= 1:
            n = attempts(prompts_dir, "cluster-a*.md")
            if n >= 2:
                return lane_failed("cluster: no valid subjects.json after 2 attempts"
                                   + (f" ({problem})" if problem else ""), notes)
            template = load_prompt_template("cluster.md", 4, "cluster")
            values = {
                "RUN_DIR": str(run_dir),
                "TWEETS": "\n\n".join(tweet_block(t, tweet_notes) for t in kept),
                "PART_NOTE": "",
                "OUTPUT_PATH": str(subjects_path),
            }
            path = write_prompt(prompts_dir, f"cluster-a{n + 1}.md",
                                fill_template(template, values), n + 1, problem)
            return lane_result("cluster", n + 1,
                               [launch_entry("cluster", path, f"x cluster a{n + 1}")], notes)

        launches, attempt = [], 0
        part_template = load_prompt_template("cluster.md", 4, "cluster")
        for k, part in enumerate(parts, start=1):
            part_path = run_dir / f"cluster_part_{k}.json"
            doc = load_json_or_none(part_path)
            if isinstance(doc, dict) and isinstance(doc.get("subjects"), list):
                continue
            n = attempts(prompts_dir, f"cluster-part{k}-a*.md")
            if n >= 2:
                return lane_failed(f"cluster: part {k} wrote no valid "
                                   f"cluster_part_{k}.json after 2 attempts", notes)
            values = {
                "RUN_DIR": str(run_dir),
                "TWEETS": "\n\n".join(tweet_block(t, tweet_notes) for t in part),
                "PART_NOTE": f"This is part {k} of {len(parts)}. Other parts hold "
                             f"other sources. Group only what is in front of you; an "
                             f"event another part ran is merged later.",
                "OUTPUT_PATH": str(part_path),
            }
            path = write_prompt(prompts_dir, f"cluster-part{k}-a{n + 1}.md",
                                fill_template(part_template, values), n + 1)
            launches.append(launch_entry("cluster", path, f"x cluster part {k} a{n + 1}"))
            attempt = max(attempt, n + 1)
        if launches:
            return lane_result("cluster", attempt, launches, notes)

        n = attempts(prompts_dir, "cluster-merge-a*.md")
        if n >= 2:
            return lane_failed("cluster-merge: no valid subjects.json after 2 attempts"
                               + (f" ({problem})" if problem else ""), notes)
        by_id = {t["id"]: t for t in kept}
        part_blocks = []
        for k in range(1, len(parts) + 1):
            part_doc = load_json(run_dir / f"cluster_part_{k}.json")
            for subj in part_doc.get("subjects", []):
                lines = [f"[part {k}] {subj.get('subject', '')}"]
                for tid in subj.get("tweet_ids") or []:
                    t = by_id.get(tid)
                    lines.append("  " + tweet_block(t, tweet_notes).replace("\n", " | ")
                                 if t else f"  {tid} (unknown)")
                part_blocks.append("\n".join(lines))
        merge_template = load_prompt_template("cluster-merge.md", 4, "cluster (merge)")
        values = {
            "RUN_DIR": str(run_dir),
            "PARTS": str(len(parts)),
            "PART_SUBJECTS": "\n\n".join(part_blocks),
            "ALL_TWEET_IDS": "\n".join(t["id"] for t in kept),
            "OUTPUT_PATH": str(subjects_path),
        }
        path = write_prompt(prompts_dir, f"cluster-merge-a{n + 1}.md",
                            fill_template(merge_template, values), n + 1, problem)
        return lane_result("cluster-merge", n + 1,
                           [launch_entry("cluster", path, f"x cluster-merge a{n + 1}")], notes)

    subjects = load_json(subjects_path).get("subjects") or []
    if subjects and not all("velocity_rank" in s for s in subjects):
        run_script_step(5, "x_score.py", run_dir, settings_path, quiet=True)
    return None


def lane_judge(run_dir: Path, settings: dict, prompts_dir: Path, root: Path, notes: list):
    """Phase judge: one agent per subject without a valid verdict, two
    attempts each. None once every subject has a verdict or is given up."""
    subjects = load_json(run_dir / "subjects.json").get("subjects") or []
    if not subjects:
        return None
    by_id = {t["id"]: t for t in load_json(run_dir / "kept.json").get("kept") or []}
    tweet_notes = load_notes(run_dir)
    profile_date, profile_text, preferences_text, lens_text = find_lens_and_profile(root)
    template = load_prompt_template("judge.md", 6, "judge")
    launches, unjudged, attempt = [], [], 0
    for i, subj in enumerate(subjects, start=1):
        verdict_path = run_dir / f"judge_{i}.json"
        if load_json_or_none(verdict_path) is not None:
            continue
        n = attempts(prompts_dir, f"judge-{i}-a*.md")
        if n >= 2:
            unjudged.append(i)
            continue
        tweets = [by_id[tid] for tid in subj.get("tweet_ids") or [] if tid in by_id]
        measures = {k: subj.get(k) for k in
                    ("authors", "lists", "endorsements", "velocity", "velocity_rank", "cross_list")}
        values = {
            "RUN_DIR": str(run_dir),
            "SUBJECT": subj.get("subject", ""),
            "SCORE_TAG": subj.get("tag", ""),
            "FLAGS": ", ".join(subj.get("flags") or []),
            "MEASURES": json.dumps(measures, indent=2),
            "VELOCITY_RANK": str(subj.get("velocity_rank")),
            "CURIOUS_PERCENTILE": str(settings["x_curious_percentile"]),
            "TWEETS": "\n\n".join(tweet_block(t, tweet_notes) + f"\nurl: {t.get('url', '')}"
                                  for t in tweets),
            "PROFILE_DATE": profile_date,
            "PROFILE": profile_text,
            "PREFERENCES": preferences_text,
            "LENS": lens_text,
            "OUTPUT_PATH": str(verdict_path),
        }
        path = write_prompt(prompts_dir, f"judge-{i}-a{n + 1}.md",
                            fill_template(template, values), n + 1)
        launches.append(launch_entry("judge", path, f"x judge {i} a{n + 1}"))
        attempt = max(attempt, n + 1)
    if launches:
        return lane_result("judge", attempt, launches, notes)
    if unjudged and len(unjudged) == len(subjects):
        return lane_failed("judge: no subject got a verdict after 2 attempts", notes)
    if unjudged:
        notes.append(f"{len(unjudged)} subject(s) unjudged after two attempts: "
                     + ", ".join(str(i) for i in unjudged))
    return None


def lane_judge_merge(run_dir: Path, settings: dict, prompts_dir: Path, notes: list):
    """Phase judge-merge: every verdict into picks.md, within the
    `x_picks_max` ceiling -- the one judgment left after each subject was
    judged alone is which subjects the ceiling cuts, so it is an agent, not
    code. None once picks.md exists."""
    picks_path = run_dir / "picks.md"
    if picks_path.exists():
        return None
    n = attempts(prompts_dir, "judge-merge-a*.md")
    if n >= 2:
        return lane_failed("judge-merge: no picks.md after 2 attempts", notes)
    subjects = load_json(run_dir / "subjects.json").get("subjects") or []
    verdicts = []
    for i in range(1, len(subjects) + 1):
        path = run_dir / f"judge_{i}.json"
        if load_json_or_none(path) is not None:
            verdicts.append(path.read_text(encoding="utf-8"))
    template = load_prompt_template("judge-merge.md", 6, "judge (merge)")
    values = {
        "RUN_DIR": str(run_dir),
        "PICKS_MAX": str(settings["x_picks_max"]),
        "VERDICTS": "\n\n".join(verdicts) or "(no verdicts: no subject was judged)",
        "OUTPUT_PATH": str(picks_path),
    }
    path = write_prompt(prompts_dir, f"judge-merge-a{n + 1}.md",
                        fill_template(template, values), n + 1)
    return lane_result("judge-merge", n + 1,
                       [launch_entry("judge", path, f"x judge-merge a{n + 1}")], notes)


def lane_write(run_dir: Path, settings: dict, prompts_dir: Path, root: Path, notes: list):
    """Phase write: picks.md and the picked notes into brief.md. `done` once
    it exists."""
    output_path = run_dir / "brief.md"
    if output_path.exists():
        return {"phase": "done", "launch": [], "notes": notes}
    n = attempts(prompts_dir, "write-a*.md")
    if n >= 2:
        return lane_failed("write: no brief.md after 2 attempts", notes)
    picks_path = run_dir / "picks.md"
    picks = parse_picks_md(picks_path)
    notes_block = build_notes_block(run_dir, picks)
    subjects = load_json(run_dir / "subjects.json").get("subjects") or []
    template_path = HERE / "templates" / "x-brief.md"
    if not template_path.exists():
        die(f"step 7 (write) cannot run: templates/x-brief.md does not exist yet at {template_path}")
    _, _, preferences_text, lens_text = find_lens_and_profile(root)
    template = load_prompt_template("write.md", 7, "write")
    values = {
        "RUN_DIR": str(run_dir),
        "RUN_NAME": run_dir.name,
        "WINDOW_HOURS": str(settings["x_window_hours"]),
        "RUN_DATETIME": format_run_datetime(run_dir.name),
        "SUBJECTS_JUDGED": str(len(subjects)),
        "WORDS_PER_SENTENCE_MAX": str(settings["x_words_per_sentence_max"]),
        "OUTPUT_PATH": str(output_path),
        "PICKS": picks_path.read_text(encoding="utf-8"),
        "NOTES": notes_block,
        "TEMPLATE": template_path.read_text(encoding="utf-8"),
        "LENS": lens_text,
        "PREFERENCES": preferences_text,
    }
    path = write_prompt(prompts_dir, f"write-a{n + 1}.md",
                        fill_template(template, values), n + 1)
    return lane_result("write", n + 1,
                       [launch_entry("write", path, f"x write a{n + 1}")], notes)


def next_lane(run_dir: Path, settings: dict, settings_path: Path, root: Path) -> dict:
    """What the orchestrator must launch now, derived from the run folder.

    The phases are tried in order and each one answers, or falls through
    when it has nothing left to do. Called only when every launch the last
    call printed has returned: that is the orchestrator's one rule, and it
    is what keeps a prompt file from being launched twice."""
    run_dir = Path(run_dir)
    for name in ("links.md", "kept.json"):
        if not (run_dir / name).exists():
            die(f"the lane cannot start: {run_dir / name} is missing; "
                f"it is written by `x_run.py scrape`")
    prompts_dir = run_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    notes = []
    return (lane_read(run_dir, settings, prompts_dir, notes)
            or lane_cluster(run_dir, settings, settings_path, prompts_dir, notes)
            or lane_judge(run_dir, settings, prompts_dir, root, notes)
            or lane_judge_merge(run_dir, settings, prompts_dir, notes)
            or lane_write(run_dir, settings, prompts_dir, root, notes))


# ---------------------------------------------------------------- commands

def cmd_scrape(args, settings_path: Path) -> int:
    if args.run_dir:
        run_dir = Path(args.run_dir).resolve()
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_dir = new_run_dir(ROOT / "briefs" / "x")
    print(f"run folder: {run_dir}")
    run_script_step(1, "x_scrape.py", run_dir, settings_path)
    run_script_step(2, "x_filter.py", run_dir, settings_path)
    print(f"scraped: {run_dir}")
    return 0


def cmd_next(args, settings_path: Path, settings: dict) -> int:
    result = next_lane(Path(args.run_dir).resolve(), settings, settings_path, ROOT)
    # One line: ybs_run.py x-next reads the last non-empty line of stdout.
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scrape", help="steps 1 and 2: scrape the lists and filter, no agent")
    p.add_argument("--run-dir", default=None,
                   help="use this folder instead of creating a fresh one")
    p.add_argument("--settings", default=None,
                   help="path to settings.md (default: the root settings.md)")
    p = sub.add_parser("next", help="the lane: print what the orchestrator launches now")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--settings", default=None,
                   help="path to settings.md (default: the root settings.md)")
    args = ap.parse_args()

    settings_path = Path(args.settings).resolve() if args.settings else default_settings_path()
    settings = load_settings(settings_path)
    if args.cmd == "scrape":
        return cmd_scrape(args, settings_path)
    return cmd_next(args, settings_path, settings)


if __name__ == "__main__":
    sys.exit(main())
