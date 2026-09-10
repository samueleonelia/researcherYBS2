#!/usr/bin/env python3
"""ybs_run.py - bookkeeping for the YBS brief pipeline (v2).

This script owns runs/<run-id>/run.json. Nothing else writes that file.
Everything here is deterministic: no network, no AI, no guessing, and -- unlike
v1 -- **no page parsing of any kind**. Pages are read by agents in a browser;
this script only counts, names, validates and logs what they report.

Commands
  settings                 print settings.md, the only home of every number
  schema [--key a.b]       print the file names, launch lines and sentinels
  build [--check]          render .claude/agents/ybs4-*.md from the templates
  fill NAME --run DIR      render one single-call prompt, run data included
  sources                  print the sources listed in sources.md as JSON
  start --slot SLOT        create the run folder, compute the time window; an
                           afternoon run also finds the morning it updates, and
                           an evening run the two runs it pools
  screen-sync --run DIR    fold every screen/<slug>.json into articles.json
  pool-sync --run DIR      the evening's own step 2: pool what the day's earlier
                           runs kept at triage into this run's articles.json
  triage-list --run DIR    freeze the article list, print one launch line per article
  triage-check --run DIR   verify every article has its own one-line verdict file
  triage-replay --run DIR  replay the section filter over a finished run, and diff
  items-sync --run DIR     validate the cluster/select plan, build the read list
  read-list --run DIR      the article ids still to read, one launch line each
  check-sync --run DIR     apply figure-check verdicts; list redos or strikes
  picks-sync --run DIR     validate the pick reply, and trim it to picks_max
  x-start --run DIR        launch the X-list pipeline in the background, once
  x-wait --run DIR         block until that X run is done, failed or out of time
  write-stitch --run DIR   join the section files into brief.md
  x-merge --run DIR        put the X run's brief under the article brief
  event --run DIR ...      record something that happened (failure, retry, ...)
  audit-line --run DIR     build the audit line from run.json (never from a model)
  close --run DIR          write run-log.md and mark the run finished

Exit codes: 0 = ok, 1 = did the job but found a problem, 2 = bad usage / error.
"""

import argparse
import json
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# The two outside tools (yt-dlp, npx) are installed by /setup into the user's own
# ~/.local, which is on the PATH of a terminal but not always of an app started
# from the Dock. Adding them here means a run works before the Claude app has
# been restarted, which is the one step of the install a person can forget.
import os
for _d in (Path.home() / ".local" / "bin", Path.home() / ".local" / "node" / "bin"):
    if _d.is_dir() and str(_d) not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = f"{_d}{os.pathsep}{os.environ.get('PATH', '')}"


# ---------------------------------------------------------------- basics

def project_root() -> Path:
    """<root>/.claude/skills/ybs-brief/scripts/ybs_run.py -> <root>"""
    return Path(__file__).resolve().parents[4]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# A bare date, numeric or Guardian-style (/2026/aug/24/ in a URL). It has no
# clock, so screen-sync compares it to the run's local date, never to the window.
DATE_ONLY = re.compile(r"^\d{4}-(\d{2}|[A-Za-z]{3})-\d{2}$")


def parse_iso(s: str):
    """Tolerant: handles Z, +00:00, milliseconds, a bare date, a <time datetime>
    without seconds, or a month-name date. None if unparseable."""
    if not s or not isinstance(s, str):
        return None
    t = s.strip().replace("Z", "+00:00")
    t = re.sub(r"\.\d+(?=[+-]|$)", "", t)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M%z", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%b-%d"):
        try:
            d = datetime.strptime(t, fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def canon(url: str) -> str:
    """Same article, one key: no fragment, no query, no trailing slash, no scheme."""
    u = url.split("#")[0].split("?")[0].rstrip("/")
    return re.sub(r"^https?://(www\.)?", "", u).lower()


def die(msg: str, code: int = 2):
    print("ERROR: " + msg, file=sys.stderr)
    sys.exit(code)


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def run_dir_of(args) -> Path:
    d = Path(args.run).resolve()
    if not (d / "run.json").exists():
        die(f"not a run folder (no run.json): {d}")
    return d


def load_run(run_dir: Path) -> dict:
    return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))


def save_run(run_dir: Path, data: dict):
    write_json(run_dir / "run.json", data)


def log_event(run_dir: Path, etype: str, detail: str = "", **extra):
    data = load_run(run_dir)
    ev = {"utc": iso(utc_now()), "type": etype, "detail": detail}
    ev.update({k: v for k, v in extra.items() if v is not None})
    data.setdefault("events", []).append(ev)
    save_run(run_dir, data)
    return ev


# ------------------------------------------------- settings, schema, filling
#
# One home per fact. Numbers live in settings.md, shared prose lives in the
# prompts/_*.md fragments, and every name a file or a launch line can have
# lives in SCHEMA below. Nothing else states any of them: prompts and agent
# files carry {{PLACEHOLDERS}} that `fill` and `build` replace.

PLACEHOLDER = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_.-]*)\}\}")

# Filled by code long after an agent has run, so `fill` and `build` leave both
# alone: the audit line by `audit-line`, the X section by `x-merge`.
PASS_THROUGH = {"AUDIT_LINE", "X_SECTION"}


# The sections of the brief, per slot, in the order their template prints them,
# and the pick tag that belongs in each. A slot is a different brief, not a
# different pipeline: the morning runs three sections, the afternoon two and the
# evening one, and every step that asks "which sections?" or "which tag?" asks
# these two tables rather than carrying its own answer. Tag -> section is by
# position, so the first `##` section of a template holds the first tag listed
# here.
WRITE_SECTIONS = {"morning": ("leads", "body", "worth"),
                  "afternoon": ("new", "moved"),
                  "evening": ("achievements",)}
TAG_OF_SECTION = {"morning": {"leads": "LEAD", "body": "BODY", "worth": "WORTH"},
                  "afternoon": {"new": "NEW", "moved": "MOVED"},
                  "evening": {"achievements": "ACHIEVEMENT"}}

# Every section name of every slot, morning's first. argparse builds `--section`
# before any run is known, so its choices are the union; cmd_fill is where a
# section that belongs to the other slot is refused.
ALL_SECTIONS = tuple(s for names in WRITE_SECTIONS.values() for s in names)


def sections_of(run: dict) -> tuple:
    """The sections this run's own slot writes, in the template's order."""
    slot = run.get("slot")
    if slot not in WRITE_SECTIONS:
        die(f"unknown slot {slot!r}; the slots are {', '.join(WRITE_SECTIONS)}")
    return WRITE_SECTIONS[slot]


def tag_of(run: dict, section: str) -> str:
    """The pick tag that belongs in one section of this run's slot."""
    return TAG_OF_SECTION[run["slot"]][section]


def tags_of(run: dict) -> tuple:
    """Every tag a pick of this run may carry, in the template's section order.

    The morning ranks a story, the afternoon says whether it is new or moved,
    and the evening only says a story is an achievement, so no two slots share a
    vocabulary. Reading the tags off the section table is how they cannot drift:
    a tag exists because a section holds it.
    """
    slot = run.get("slot")
    if slot not in WRITE_SECTIONS:
        die(f"unknown slot {slot!r}; the slots are {', '.join(WRITE_SECTIONS)}")
    return tuple(TAG_OF_SECTION[slot][s] for s in WRITE_SECTIONS[slot])


SCHEMA = {
    "path": {
        "screen": "<run_dir>/screen/<slug>.json",
        "screen_attempt": "<run_dir>/screen/<slug>.attempt.json",
        "verdict": "<run_dir>/triage/<id>.verdict.txt",
        "plan": "<run_dir>/items/plan.json",
        "plan_part": "<run_dir>/items/plan-part<k>.json",
        "page": "<run_dir>/pages/<id>.txt",
        "note": "<run_dir>/notes/<id>.md",
        "check": "<run_dir>/checks/<id>.txt",
        "picks": "<run_dir>/picks/picks.json",
        "counterpoint": "<run_dir>/picks/cp-<id>.md",
        "brief": "<run_dir>/brief.md",
        "brief_section": "<run_dir>/brief-<section>.md",
        "profile": "shows/profile.json",
    },
    "write": {
        "sections": {slot: " | ".join(names)
                     for slot, names in WRITE_SECTIONS.items()},
        "note": ("one writer per section, all launched at once; write-stitch "
                 "joins the section files into brief.md in the template's order"),
    },
    "launch": {
        "triage": ("<run_dir>\n"
                   "<id> | [<source>] (<section>) <headline> :: <description>\n"
                   "<id> | [<source>] (<section>) <headline> :: <description>"),
        # The evening asks the same agent a different question, and the first
        # line is where it is told which: the run directory, then the slot.
        "triage_evening": ("<run_dir> | evening\n"
                           "<id> | [<source>] (<section>) <headline> :: <description>\n"
                           "<id> | [<source>] (<section>) <headline> :: <description>"),
        "reader": "<id> | <source> | <url> | <run_dir>",
        "reader_saved": "<id> | <source> | <url> | <run_dir> | saved-page",
        "checker": "<id> | <run_dir>",
    },
    "taskspace": {
        "screen": "ybs screen <slug> a<attempt>",
        "read": "ybs read <id>",
        "counterpoint": "ybs cp <id>",
    },
    "sentinel": {
        "truncated": "PAGE_TRUNCATED",
        "blank": "PAGE_BLANK",
        "no_case": "NONE",
        "no_figures": "no figures",
        "triage": "keep | drop",
        "check": "found | missing",
        "verdict": "READ | MAYBE | DROP",
    },
    # The tags are per slot, because the briefs answer different questions: the
    # morning ranks a story, the afternoon says whether it is new or moved, the
    # evening says only that a story is an achievement. `kind` is the
    # afternoon's second label, on a MOVED pick only; `label` is the evening's,
    # on every pick, and it says how far the thing has actually got.
    "tag": {"morning": "LEAD | BODY | WORTH",
            "afternoon": "NEW | MOVED",
            "evening": "ACHIEVEMENT",
            "kind": "development | confirmation | reversal | correction",
            "label": ("demonstrated | emerging | speculative | historical | "
                      "biographical")},
    "x": {
        "run_dir": "x-lists/runs/<YYYY-MM-DD-HHMM>",
        "log": "<run_dir>/x/x-run.log",
        "brief": "<x_run_dir>/brief.md",
        "record": ("run.json 'x': run_dir, pid, log, started_utc, status, "
                   "retries, reason"),
        "status": "running | completed | failed | skipped | merged",
        "placeholder": "{{X_SECTION}}",
    },
    "reason_type": {
        "all": ("evidence | duplicate | no-development | relevance | unchanged | "
                "not-achievement"),
        "evidence": "its `WEAK SPOTS`, or a claim nothing supports",
        "duplicate": "the same event as a story you kept",
        "no-development": "nothing happened: a column, a feature, a recap",
        "relevance": "real enough, but not worth his morning",
        # The afternoon's own reason: the story is his, and it has not moved.
        "unchanged": ("the morning brief already carries this, and the note "
                      "adds nothing that moves it"),
        # The evening's own reason: the headline promised an achievement and
        # the article, read whole, turned out to hold none.
        "not-achievement": ("read in full, it reports none of the five kinds: "
                            "a plan, a pledge, a complaint or a setback"),
    },
}


# What a part of a cut kept list is told, and what the full list is told (nothing).
PART_NOTE = ("This is part {k} of {n}. Other parts hold other sources. Group only "
             "what is in front of you; an event another paper ran is merged later.")


def skill_dir() -> Path:
    """<root>/.claude/skills/ybs-brief/scripts/ybs_run.py -> the skill folder"""
    return Path(__file__).resolve().parents[1]


def load_settings(path: Path = None) -> dict:
    """Read the article brief's tables out of the root settings.md.

    The file holds the X list's tables too. Only two headings belong to this
    half, and every other section is skipped, which is why both halves may
    name a step `cluster` without clashing:

    Under `## Numbers` a row is `| key | value | meaning |`. Values: digits are
    ints, `50%` is the int 50, `"a", "b"` is a list of strings, anything else is
    the text as written.

    Under `## Models` a row is `| step | model | effort | ... |`, and gives two
    keys, `<step>_model` and `<step>_effort`, so a template can ask for either.
    """
    path = path or (project_root() / "settings.md")
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
        if section not in ("numbers", "models"):
            continue  # the X list's own sections; x_settings.py reads those
        if section == "models":
            if len(cells) < 3 or not cells[2]:
                die(f"settings.md: {key} has no effort")
            for suffix, value in (("_model", cells[1]), ("_effort", cells[2])):
                if key + suffix in out:
                    die(f"settings.md names {key + suffix} twice")
                out[key + suffix] = value
            continue
        if key in out:
            die(f"settings.md names {key} twice")
        if re.fullmatch(r"\d+", raw):
            out[key] = int(raw)
        elif re.fullmatch(r"\d+%", raw):
            out[key] = int(raw[:-1])
        elif '"' in raw:
            out[key] = re.findall(r'"([^"]*)"', raw)
        else:
            out[key] = raw
    if not out:
        die(f"{path} holds no settings")
    return out


def fragment(name: str, section: str = None) -> str:
    """The text of prompts/_<name>.md, or of one `## section` inside it."""
    path = skill_dir() / "prompts" / f"_{name}.md"
    if not path.exists():
        die(f"no fragment at {path}")
    text = path.read_text(encoding="utf-8").strip()
    if section is None:
        return text
    body, taking = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            taking = line[3:].strip().lower() == section.lower()
            continue
        if taking:
            body.append(line)
    if not body:
        die(f"{path} has no '## {section}' section")
    return "\n".join(body).strip()


def norm_category(text: str) -> str:
    """A publisher's section, lowercased and with its whitespace collapsed.

    `World News` and `World news` are the same section; a quarter of one
    source's output takes the wrong path without this.
    """
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def beat_categories() -> set:
    """The sections `_sections.md` lists as wholly on beat, normalised."""
    cats = {norm_category(ln[2:]) for ln in
            fragment("sections").splitlines() if ln.startswith("- ")}
    cats.discard("")
    if not cats:
        die("_sections.md lists no sections")
    return cats


def load_profile(shows_dir: Path = None) -> dict:
    """shows/profile.json: what the show is arguing about now.

    Returns the file's own fields plus `rank`, a name -> rank map with the
    running storylines above the themes.
    """
    shows_dir = shows_dir or (project_root() / "shows")
    path = shows_dir / "profile.json"
    if not path.exists():
        die(f"no topic profile at {path}. Run /ybs-shows first.")
    d = load_json(path)
    rank, n = {}, 0
    for group in ("storylines", "themes"):
        for entry in d.get(group) or []:
            n += 1
            rank[str(entry.get("name", "")).strip().lower()] = n
    d["rank"] = rank
    return d


def profile_text(profile: dict) -> str:
    """The profile as an agent reads it: storylines first, then themes."""
    lines = ["Running storylines, the ones carrying across shows:", ""]
    for e in profile.get("storylines") or []:
        shows = f" ({e['shows']} shows)" if e.get("shows") else ""
        note = f" — {e['note']}" if e.get("note") else ""
        lines.append(f"- {e['name']}{shows}{note}")
    lines += ["", "Themes, most covered first:", ""]
    for e in profile.get("themes") or []:
        angle = f" — {e['angle']}" if e.get("angle") else ""
        lines.append(f"- {e['name']}{angle}")
    return "\n".join(lines)


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


def preferences() -> str:
    """His own standing instructions, from preferences.md at the project root.

    His file, not the pipeline's, so every failure mode here is silence: it may
    be missing, it may be all comments, it may be empty. Any of those means he
    has asked for nothing in particular, and the brief runs the way it always
    has. What counts as a note and what counts as an instruction is decided
    by preference_lines, and nowhere else.
    """
    path = project_root() / "preferences.md"
    if not path.exists():
        return "He has not written any standing instructions."
    lines = preference_lines(path.read_text(encoding="utf-8"))
    if not lines:
        return "He has not written any standing instructions."
    return "\n".join("- " + ln.lstrip("-* ").strip() for ln in lines)


def namespace(shows_dir: Path = None, need_profile: bool = True) -> dict:
    """Everything a prompt or an agent file may ask for, apart from run data."""
    ns = {
        "BEATS": fragment("beats"),
        "LENS": fragment("lens"),
        "CRITERIA_FACTORS": fragment("criteria", "factors"),
        "CRITERIA_LABELS": fragment("criteria", "labels"),
        "CRITERIA_TAGS": fragment("criteria", "tags"),
        "AGENT_RULES": fragment("agent-rules", "every agent"),
        "AGENT_RULES_FILE": fragment("agent-rules", "file agents"),
        "ITEM_SHAPE": fragment("item-shape"),
        "ACHIEVEMENTS": fragment("achievements"),
        "PICK_RULES": fragment("pick-rules"),
        "AGENT_RULES_BROWSER": fragment("agent-rules", "browser agents"),
        "AGENT_RULES_JSON": fragment("agent-rules", "json agents"),
        "PRINCIPLES": fragment("principles"),
        "PREFERENCES": preferences(),
    }
    for key, value in load_settings().items():
        ns[f"settings.{key}"] = str(value)
    for group, entries in SCHEMA.items():
        for key, value in entries.items():
            ns[f"schema.{group}.{key}"] = value
    if need_profile:
        p = load_profile(shows_dir)
        ns["PROFILE"] = profile_text(p)
        ns["PROFILE_MOVES"] = profile_moves(p)
        ns["PROFILE_DATE"] = p.get("built_local_date", "unknown")
        ns["PROFILE_SHOWS"] = str(len(p.get("shows") or []))
    return ns


def profile_moves(profile: dict) -> str:
    moves = profile.get("moves") or {}
    lines = []
    if moves.get("main"):
        lines += ["His single most repeated argument:", "", moves["main"].strip()]
    secondary = moves.get("secondary") or []
    if secondary:
        lines += ["", "The moves he reaches for again and again:", ""]
        lines += [f"- {s}" for s in secondary]
    return "\n".join(lines).strip()


def render(text: str, ns: dict):
    """Substitute every {{PLACEHOLDER}}. Returns (text, unfilled names)."""
    missing = []

    def one(m):
        name = m.group(1)
        if name in PASS_THROUGH:
            return m.group(0)
        if name in ns:
            return str(ns[name])
        missing.append(name)
        return m.group(0)

    return PLACEHOLDER.sub(one, text), sorted(set(missing))

# ------------------------------------------------------------ build and fill

def cmd_settings(args):
    """Print the settings table as JSON, so a test can read what a prompt reads."""
    print(json.dumps(load_settings(), indent=2, ensure_ascii=False))
    return 0


def cmd_schema(args):
    """Print the names of files, launch lines and sentinels this pipeline uses."""
    if args.key:
        node = SCHEMA
        for part in args.key.split("."):
            if not isinstance(node, dict) or part not in node:
                die(f"no schema key {args.key}")
            node = node[part]
        print(node if isinstance(node, str) else
              json.dumps(node, indent=2, ensure_ascii=False))
        return 0
    print(json.dumps(SCHEMA, indent=2, ensure_ascii=False))
    return 0


GENERATED = ("<!-- Generated by ybs_run.py build from "
             ".claude/skills/ybs-brief/agents/{name}.md.tmpl — edit the "
             "template, not this file. -->")


def stamp(text: str, banner: str) -> str:
    """Put the generated-file banner *below* the frontmatter, never above it.

    Claude Code only reads an agent file's frontmatter when the opening `---`
    is the very first line. A banner above it makes the whole file invisible to
    the agent loader, and the failure is silent: the file is there, `build
    --check` is happy, and the agent simply does not exist.
    """
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[:i + 1] + [banner] + lines[i + 1:])
    return banner + "\n" + text


def cmd_build(args):
    """Render .claude/agents/ybs4-*.md from the templates in the skill folder.

    An agent file is static: Claude Code loads it as written, so a fragment
    cannot be pulled in at launch time. Rendering is how the beats, the lens
    and the shared agent rules stay in one place and still reach every agent.
    """
    tmpl_dir = skill_dir() / "agents"
    out_dir = project_root() / ".claude" / "agents"
    templates = sorted(tmpl_dir.glob("*.md.tmpl"))
    if not templates:
        die(f"no agent templates in {tmpl_dir}")
    ns = namespace(need_profile=False)
    stale, written = [], []
    for t in templates:
        name = t.name[:-len(".md.tmpl")]
        text, missing = render(t.read_text(encoding="utf-8"), ns)
        if missing:
            die(f"{t.name} asks for {', '.join(missing)}, which nothing provides")
        text = stamp(text, GENERATED.format(name=name))
        target = out_dir / f"ybs4-{name}.md"
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current == text:
            continue
        if args.check:
            stale.append(target.name)
        else:
            target.write_text(text, encoding="utf-8")
            written.append(target.name)
    if args.check:
        print(json.dumps({"templates": len(templates), "stale": stale},
                         indent=2, ensure_ascii=False))
        return 1 if stale else 0
    print(json.dumps({"templates": len(templates), "written": written},
                     indent=2, ensure_ascii=False))
    return 0


# --------------------------------------------------- run data for the prompts

def note_field(text: str, field: str) -> str:
    """One field out of a reader's note. Fields are `NAME:` headings."""
    out, taking = [], False
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z '’]+):\s*(.*)$", line)
        if m:
            taking = m.group(1).strip() == field
            if taking and m.group(2).strip():
                out.append(m.group(2).strip())
            continue
        if taking:
            out.append(line)
    return "\n".join(out).strip()


def kept_articles(run_dir: Path) -> list:
    """The articles kept at triage, in id order, read from triage/verdicts.json.

    verdicts.json is what triage-check writes and items-sync reads, so this is
    the third reader of one record. Re-parsing the verdict files here is how the
    cluster step once saw zero kept articles on every run: the files hold
    `<id> keep`, and a check for a line starting with `keep` never matched.
    """
    verdicts = load_json(run_dir / "triage" / "verdicts.json")
    if verdicts is None:
        die("no triage/verdicts.json; run triage-check first")
    kept = {a for a, v in verdicts.items() if v == "keep"}
    arts = (load_json(run_dir / "articles.json") or {}).get("articles") or []
    return [r for r in arts if r["id"] in kept]


def article_lines(records: list) -> str:
    """Articles as the cluster agent sees them: one line each, description under it."""
    lines = []
    for r in records:
        def clean(t):
            return re.sub(r"\s+", " ", t or "").strip()
        lines.append(f"{r['id']} [{clean(r['source'])}] "
                     f"({clean(r['category']) or '-'}) {clean(r['title'])}")
        desc = clean(r["description"])[:200]
        if desc:
            lines.append(f"     {desc}")
    if not lines:
        die("no article was kept at triage; nothing to cluster")
    return "\n".join(lines)


def articles_block(run_dir: Path) -> str:
    """Every article kept at triage, as the cluster agent sees it."""
    return article_lines(kept_articles(run_dir))


def part_cut(records: list, cap: int) -> list:
    """Cut the kept list into parts of at most `cap` articles, deterministically.

    Units are sources: a paper's own articles stay together, so its live blog
    and its follow-up are judged side by side. A source that alone exceeds the
    cap is cut in id order into near-equal chunks. Units go largest first into
    the fullest part that still has room (best-fit decreasing), and a new part
    opens only when none has room, so no part ever exceeds the cap. Assigning
    to the emptiest of ceil(N / cap) parts, the obvious rule, breaks the cap:
    100/100/100 at 150 gives 200.
    """
    by_source = {}
    for r in records:
        by_source.setdefault(r["source"], []).append(r)
    units = []
    for name, rs in by_source.items():
        chunks = -(-len(rs) // cap)
        size = -(-len(rs) // chunks)
        for i in range(chunks):
            units.append((name, rs[i * size:(i + 1) * size]))
    units.sort(key=lambda u: (-len(u[1]), u[0]))
    parts = []
    for name, rs in units:
        room = [p for p in parts if sum(len(u[1]) for u in p) + len(rs) <= cap]
        if room:
            part = max(room, key=lambda p: sum(len(u[1]) for u in p))
        else:
            part = []
            parts.append(part)
        part.append((name, rs))
    return [[r for _, rs in part for r in rs] for part in parts]


SLOT_JOB_HEAD = """## The brief you are updating

This run is the afternoon update of that morning's brief. Every article in
front of you is one the morning never saw. Its stories are these, in the order
it ran them, each with what was new about it then:"""

SLOT_JOB_RULES = """**An article about one of those stories goes in an item that names it:**
`"follows": "m:<id>"`. Such an item is `READ` only when a headline or a
description promises something the morning's line does not already carry: a
figure, a decision, a denial, a correction, a reversal, a death toll. The same
event told again is `DROP`, with `why: "no-move"`.

**An item that follows nothing** is a story the morning did not have at all.
It is read only when it is big: at least {floor} articles reporting it.
Label the smaller ones as honestly as any other item, `READ`, `MAYBE` or
`DROP`, and code leaves them unread. Group them as carefully as the followers,
because the size of the cluster is the whole test of a story nobody was
covering at ten.

A follower item looks like this:

```json
{{
  "item_id": "i07",
  "name": "Centcom names the tankers and gives a crew count",
  "kind": "cluster",
  "verdict": "READ",
  "profile": null,
  "follows": "m:a149",
  "articles": ["a018", "a044"],
  "primary": "a018",
  "read": ["a018"],
  "why": "the morning had the strike; this names the ships and counts the crew"
}}
```"""


SLOT_JOB_EVENING_HEAD = """## What tonight's items are

This run is the evening report of human achievements. Every article in front
of you was kept this evening because its headline promised one of these five
kinds:"""

SLOT_JOB_EVENING_RULES = """**The verdict, in tonight's terms:**

- `READ` — the achievement is reported as an event: a result, an approval, a
  launch, a ruling, a rescue, a number.
- `MAYBE` — a column or a feature about one.
- `DROP` — an article that, seen beside the others, reports none of the five.

No item follows anything tonight, so `follows` stays `null` right through."""


def slot_job(run_dir: Path, run: dict) -> str:
    """What this run's slot adds to the cluster's job, or nothing.

    A morning run renders this empty: it groups a day of articles and there is
    no earlier brief to measure them against. An afternoon run renders the
    stories of the brief it updates, the rule for an article that carries one
    of them further, and the rule for everything else. An evening run renders
    the five kinds it was sorted by, and the same three verdicts asked about
    those kinds instead of the beats.
    """
    if run.get("slot") == "evening":
        return "\n\n".join([SLOT_JOB_EVENING_HEAD, fragment("achievements", "kinds"),
                            SLOT_JOB_EVENING_RULES])
    if run.get("slot") != "afternoon":
        return ""
    base = run.get("base") or {}
    base_dir = Path(base.get("run_dir") or "")
    picks = (load_json(base_dir / "picks" / "picks.json") or {}).get("picks") or []
    lines = []
    for p in picks:
        note = base_dir / "notes" / f"{p['id']}.md"
        text = note.read_text(encoding="utf-8") if note.exists() else ""

        def one(field):
            return re.sub(r"\s+", " ", note_field(text, field)).strip()

        headline = one("HEADLINE") or "-"
        whats_new = one("WHAT'S NEW") or "-"
        lines.append(f"m:{p['id']} · {p.get('tag') or '-'} · {headline}"
                     f" · new this morning: {whats_new}")
    if not lines:
        die(f"the run this update follows has no picks in "
            f"{base_dir / 'picks' / 'picks.json'}")
    return "\n\n".join([SLOT_JOB_HEAD, "\n".join(lines),
                        SLOT_JOB_RULES.format(floor=NEW_ITEM_ARTICLES_MIN)])


# What the update's pick is shown of each story the brief it follows ran. Four
# fields, in the note's own order: what was established, what was new then, what
# was already shaky, and what was missing. Together they are the thing an
# afternoon note is measured against, and nothing else in the base note is.
BASE_STORY_FIELDS = ("WHAT HAPPENED", "WHAT'S NEW", "WEAK SPOTS",
                     "WHAT'S NOT HERE")


def base_run_dir(run: dict) -> Path:
    """The folder of the brief this run updates."""
    return Path((run.get("base") or {}).get("run_dir") or "")


def base_stories(run: dict) -> str:
    """The stories of the brief being updated, in the order that brief ran them.

    An update cannot ask "did this move?" without the thing it is moving
    against, so every base pick arrives here whole: its id in the `m:<id>` form
    the update writes everywhere, its tag, its headline, its URL, and the four
    fields of its own note. The order is the base run's pick order, because the
    update is written in that order too.
    """
    base_dir = base_run_dir(run)
    picks = (load_json(base_dir / "picks" / "picks.json") or {}).get("picks") or []
    arts = {r["id"]: r for r in
            ((load_json(base_dir / "articles.json") or {}).get("articles") or [])}
    out = []
    for p in picks:
        aid = p.get("id")
        note = base_dir / "notes" / f"{aid}.md"
        text = note.read_text(encoding="utf-8") if note.exists() else ""
        headline = re.sub(r"\s+", " ", note_field(text, "HEADLINE")).strip()
        out.append(f"m:{aid} · {p.get('tag') or '-'} · {headline or '-'}")
        out.append(f"     {arts.get(aid, {}).get('url', '-')}")
        for field in BASE_STORY_FIELDS:
            value = note_field(text, field)
            out.append(f"{field}: {value}" if value else f"{field}: -")
        out.append("")
    if not out:
        die(f"the run this update follows has no picks in "
            f"{base_dir / 'picks' / 'picks.json'}")
    return "\n".join(out).strip()


def base_dropped(run: dict) -> str:
    """What the brief being updated read and then left out, and why.

    A morning drop was decided with the whole article in front of somebody, so
    the update's pick is shown it: a second headline about the same nothing must
    not quietly undo the decision. A morning that dropped nothing says so in one
    line, because an empty block in a prompt reads as a hole.
    """
    base_dir = base_run_dir(run)
    dropped = (load_json(base_dir / "picks" / "picks.json") or {}).get("dropped") or []
    lines = []
    for d in dropped:
        aid = d.get("id")
        note = base_dir / "notes" / f"{aid}.md"
        headline = ""
        if note.exists():
            headline = re.sub(
                r"\s+", " ", note_field(note.read_text(encoding="utf-8"),
                                        "HEADLINE")).strip()
        lines.append(f"m:{aid} · {headline or '-'} · "
                     f"{d.get('reason_type') or '-'}: {d.get('reason') or '-'}")
    if not lines:
        return "That brief dropped nothing: every story it read reached it."
    return "\n".join(lines)


BASE_ID = re.compile(r"^m:(.+)$")


def base_pick_ids(run: dict):
    """The morning picks an item of this run may follow.

    `None` in a morning run, which follows nothing at all; in an afternoon run
    the ids of the base run's own picks, and nothing else may be followed. The
    two are different answers, so the caller can tell "follows nothing" from
    "follows one of these".
    """
    if run.get("slot") != "afternoon":
        return None
    base = run.get("base") or {}
    picks = (load_json(Path(base.get("run_dir") or "") / "picks" / "picks.json")
             or {}).get("picks") or []
    return {p["id"] for p in picks if p.get("id")}


def plan_problems(items: list, kept: set, known: set, rank: dict, base_ids=None):
    """What is wrong with a cluster plan, in the words items-sync has always used.

    Shared by items-sync (the whole plan against the kept list) and by
    fill cluster-merge (each part against its own articles). Returns the
    problems and which item placed each article; it annotates nothing.

    `base_ids` is what `base_pick_ids` returned for the run: `None` for a
    morning run, where every item's `follows` must be null, or the base picks
    an afternoon item is allowed to name.
    """
    problems, placed = [], {}
    for it in items:
        iid = it.get("item_id", "?")
        ids = it.get("articles") or []
        if not ids:
            problems.append(f"{iid}: no articles")
        for aid in ids:
            if aid not in known:
                problems.append(f"{iid}: {aid} is not an article in this run")
            elif aid not in kept:
                problems.append(f"{iid}: {aid} was dropped at triage")
            elif aid in placed:
                problems.append(f"{iid}: {aid} is already in {placed[aid]}")
            else:
                placed[aid] = iid
        for aid in (it.get("read") or []):
            if aid not in ids:
                problems.append(f"{iid}: reads {aid}, which is not in the item")
        if it.get("kind") == "cluster" and len(ids) < 2:
            problems.append(f"{iid}: a cluster needs 2+ articles")

        verdict = (it.get("verdict") or "").upper()
        if verdict not in ("READ", "MAYBE", "DROP"):
            problems.append(f"{iid}: verdict {verdict or '(none)'!r} "
                            f"(every item needs READ, MAYBE or DROP)")

        name = (it.get("profile") or "").strip()
        if name and name.lower() not in rank:
            near = nearest_profile_name(name, rank)
            problems.append(f"{iid}: profile {name!r} is not in the profile"
                            + (f"; did you mean {near!r}?" if near else ""))

        follows = it.get("follows")
        if follows is not None:
            m = BASE_ID.match(follows) if isinstance(follows, str) else None
            if base_ids is None:
                problems.append(f"{iid}: follows {follows!r}, and a morning brief "
                                f"follows nothing; every item's follows is null")
            elif not m:
                problems.append(f"{iid}: follows {follows!r}; a story of the brief "
                                f"being updated is named m:<id>, as in m:a032")
            elif m.group(1) not in base_ids:
                problems.append(f"{iid}: follows {follows!r}, which the brief being "
                                f"updated did not pick")
    return problems, placed


def notes_block(run_dir: Path) -> tuple:
    """Every note that was written, headed by what the pick needs to rank it.

    Returns (block, ids): the ids are the notes the block holds, in order, so
    the pick prompt's checklist and its notes can never drift apart.
    """
    read = (load_json(run_dir / "items" / "read-list.json") or {}).get("read") or []
    arts = {r["id"]: r for r in
            ((load_json(run_dir / "articles.json") or {}).get("articles") or [])}
    out, ids = [], []
    for entry in read:
        aid = entry["id"]
        note = run_dir / "notes" / f"{aid}.md"
        if not note.exists():
            continue
        ids.append(aid)
        head = [aid, entry.get("group", "-"), entry.get("profile") or "-",
                arts.get(aid, {}).get("url", "-")]
        if entry.get("follows"):
            # Only an update has these, so a morning head line is what it was.
            head.append(f"follows {entry['follows']}")
        out.append(" · ".join(head))
        out.append(note.read_text(encoding="utf-8").strip())
        out.append("")
    if not out:
        die("no notes were written; nothing to pick from")
    return "\n".join(out).strip(), ids


def item_siblings(run_dir: Path, lead_id: str) -> list:
    """The other articles reporting the same news item as the lead.

    A counterpoint lives inside its lead's own item: the other outlets covering
    that same event are the only place a positive element about it can turn up.
    The lead itself is left out, a story never being its own counterpoint, so a
    lead whose item is a single article has no siblings at all.
    """
    items = (load_json(run_dir / "items" / "plan.json") or {}).get("items") or []
    item = next((it for it in items
                 if lead_id in (it.get("articles") or [])), None)
    if item is None:
        die(f"{lead_id} is in no item of items/plan.json; run items-sync first")
    ids = [a for a in (item.get("articles") or []) if a != lead_id]
    arts = {r["id"]: r for r in
            ((load_json(run_dir / "articles.json") or {}).get("articles") or [])}
    return [arts[a] for a in ids if a in arts]


def sibling_lines(run_dir: Path, records: list) -> str:
    """The lead's item as the counterpoint agent sees it.

    A sibling that was read carries its whole note and the page the reader
    saved, so the agent judges it on what the article said rather than on its
    headline. A sibling nobody read gives its headline, description and URL,
    and the agent opens it if it wants it.
    """
    lines = []
    for r in records:
        def clean(t):
            return re.sub(r"\s+", " ", t or "").strip()
        title = clean(r["title"]) or r["url"]
        lines.append(f"{r['id']} [{clean(r['source'])}] {title}")
        lines.append(f"     {r['url']}")
        desc = clean(r["description"])[:200]
        if desc:
            lines.append(f"     {desc}")
        note = run_dir / "notes" / f"{r['id']}.md"
        if note.exists():
            lines.append(f"     READ. The page it was read from: "
                         f"{run_dir}/pages/{r['id']}.txt")
            lines.append("     ---- its note ----")
            lines += ["     " + l if l.strip() else ""
                      for l in note.read_text(encoding="utf-8").strip().splitlines()]
            lines.append("     ---- end of note ----")
        lines.append("")
    return "\n".join(lines).strip()


def base_rank(run_dir: Path, run: dict) -> dict:
    """Where each pick of this run sits in the order the brief being updated ran.

    An update's second section is read against the brief it follows, so its
    stories come in that brief's order and not in the update's own. The rank of
    a pick is the rank of the story it follows; a pick following nothing sorts
    last, which in a checked run is a pick that does not belong here at all.
    One home for the order, so the writer's prompt and the stitch's check can
    never disagree about it.
    """
    base_dir = base_run_dir(run)
    base_picks = (load_json(base_dir / "picks" / "picks.json")
                  or {}).get("picks") or []
    rank = {f"m:{p['id']}": i for i, p in enumerate(base_picks) if p.get("id")}
    items = (load_json(run_dir / "items" / "plan.json") or {}).get("items") or []
    item_of = {a: it for it in items for a in (it.get("articles") or [])}
    last = len(rank)
    return {a: rank.get(it.get("follows"), last)
            for it in items for a in (it.get("articles") or [])}


def base_line(run: dict, aid: str) -> list:
    """The line the brief being updated ran for one of its own stories.

    Three fields and no more: what it said happened, and what was new in it
    then. That is the thing the update's writer measures the afternoon note
    against, and everything else in the base note would only invite a retelling.
    """
    base_dir = base_run_dir(run)
    note = base_dir / "notes" / f"{aid}.md"
    text = note.read_text(encoding="utf-8") if note.exists() else ""
    head = re.sub(r"\s+", " ", note_field(text, "HEADLINE")).strip()
    out = [f"THE MORNING HAD: {head or '-'}"]
    for field in ("WHAT HAPPENED", "WHAT'S NEW"):
        out.append(f"{field}: {note_field(text, field) or '-'}")
    return out


def picks_block(run_dir: Path, run: dict, tag: str = None) -> str:
    """Every picked note with its tag and its item's full article list.

    With a tag, only the picks carrying it: one section writer sees its own
    stories and nothing else. An update's moved stories arrive in the order the
    brief being updated ran them, each under the line that brief carried, so the
    writer can say what changed without going looking for what was there before.
    """
    picks = (load_json(run_dir / "picks" / "picks.json") or {}).get("picks") or []
    if tag:
        picks = [p for p in picks if (p.get("tag") or "").upper() == tag]
    arts = {r["id"]: r for r in
            ((load_json(run_dir / "articles.json") or {}).get("articles") or [])}
    items = (load_json(run_dir / "items" / "plan.json") or {}).get("items") or []
    item_of = {a: it for it in items for a in (it.get("articles") or [])}
    moved = run.get("slot") == "afternoon" and tag == "MOVED"
    if moved:
        rank = base_rank(run_dir, run)
        picks = sorted(picks, key=lambda p: rank.get(p["id"], len(rank)))
    out = []
    for p in picks:
        note = run_dir / "notes" / f"{p['id']}.md"
        if not note.exists():
            continue
        head = [p["id"], p.get("tag", "-")]
        if p.get("kind"):
            # An update's heading opens with the kind, so the writer is given it.
            head.append(str(p["kind"]).strip().lower())
        out.append(" · ".join(head))
        siblings = (item_of.get(p["id"], {}).get("articles") or [])
        out.append("SOURCES, the picked article first:")
        for a in [p["id"]] + [x for x in siblings if x != p["id"]]:
            r = arts.get(a, {})
            title = (r.get("title") or "").strip() or r.get("url", "-")
            out.append(f"- {title} · {r.get('source', '-')} · {r.get('url', '-')}")
        if moved:
            follows = item_of.get(p["id"], {}).get("follows") or ""
            m = BASE_ID.match(follows) if follows else None
            if m:
                out += base_line(run, m.group(1))
            out.append("THE AFTERNOON'S NOTE:")
        out.append(note.read_text(encoding="utf-8").strip())
        out.append("")
    if not out:
        die("no picked note has a file; nothing to write from")
    return "\n".join(out).strip()


# An update has no lead story, so it has no counterpoint either, and step 9
# never runs on one. Its writers are told that outright rather than handed an
# empty block, which reads as a hole.
NO_COUNTERPOINTS = "None: the afternoon update carries no counterpoints."


def counterpoints_block(run_dir: Path) -> str:
    """Every counterpoint that found something to argue."""
    out = []
    for f in sorted((run_dir / "picks").glob("cp-*.md")):
        text = f.read_text(encoding="utf-8").strip()
        if not text or text.upper() == SCHEMA["sentinel"]["no_case"]:
            continue
        out.append(text)
        out.append("")
    return "\n".join(out).strip() or "None. The brief runs without counterpoints."


# ------------------------------------------------- the brief, one section each
#
# The brief is written by one writer per section, all at once, and joined in
# code. The template stays the only statement of the shape: the section
# headings, their order and the date line are read out of it here, never
# restated. Which sections a run has, and which tag belongs in each, comes from
# the two slot tables above.


def template_source(run: dict) -> str:
    return (skill_dir() / "templates" / f"{run['slot']}.md").read_text(encoding="utf-8")


def template_block(tpl: str) -> list:
    """The lines inside the template's first code fence: the brief's shape."""
    lines, fenced = [], False
    for line in tpl.splitlines():
        if line.strip().startswith("```"):
            if fenced:
                break
            fenced = True
            continue
        if fenced:
            lines.append(line)
    if not lines:
        die("the template holds no fenced block; nothing says the brief's shape")
    return lines


def template_headings(tpl: str, run: dict) -> list:
    """The `##` section headings of the brief, in the template's order."""
    sections = sections_of(run)
    heads = [l[3:].strip() for l in template_block(tpl) if l.startswith("## ")]
    if len(heads) != len(sections):
        die(f"the template has {len(heads)} `##` sections; the sectioned write "
            f"expects {len(sections)} ({', '.join(sections)})")
    return heads


# A slot's template says the clock time of its own brief in its title line, as
# `(10:00)`. Two readers need it -- the date line of the head, and the afternoon
# recording which morning it updates -- so it is read in one place.
TEMPLATE_TIME = re.compile(r"\((\d{1,2}:\d{2})\)")


def template_time(tpl: str) -> str:
    """The time in a template's title line, or midnight when it has none."""
    m = TEMPLATE_TIME.search(tpl.splitlines()[0] if tpl else "")
    return m.group(1) if m else "00:00"


# The one sentence a brief carries when the update found nothing at all. It
# lives here rather than in the template because code writes it: no writer is
# ever launched on a run with no picks.
EMPTY_UPDATE_LINE = "Nothing has moved since the morning brief."


def head_vars(run: dict) -> dict:
    """What the head line of this run's template asks code for, if anything.

    Only an update has one: it names the brief it follows by that brief's own
    clock time, which `start` wrote down when it found it. A morning template
    asks for nothing, so this answers with nothing and `fill` keeps refusing a
    template that asks for a name nobody provides.
    """
    if run.get("slot") != "afternoon":
        return {}
    return {"BASE_TIME": (run.get("base") or {}).get("time") or "-"}


def template_head(tpl: str, run: dict) -> str:
    """The lines above the first section, with the date filled in.

    The template writes the date line as `<D Month YYYY at HH:MM>`; the day is
    the run's, the time is the slot's, taken from the template's own title. A
    placeholder in the head is filled from the same namespace `fill` uses, so
    the head the writer was shown and the head that is stitched are one text.
    """
    when = template_time(tpl)
    d = datetime.strptime(run["local_date"], "%Y-%m-%d")
    stamp = f"{d.day} {d.strftime('%B %Y')} at {when}"
    head = []
    for line in template_block(tpl):
        if line.startswith("## "):
            break
        head.append(re.sub(r"<[^>]*>", stamp, line))
    text, _ = render("\n".join(head).strip(), head_vars(run))
    return text


# How many writers a slot puts on one brief, in words, since the sentence that
# tells a writer how many are beside it reads better with a word than a digit.
WRITER_COUNT = {1: "One writer is", 2: "Two writers are", 3: "Three writers are"}

# What the update's second writer is told, and nothing else is. The first
# writer's job is the morning's, so it is not restated anywhere.
MOVED_JOB = [
    "- These stories reach you in the order the brief being updated ran them.",
    "  Keep that order: it is the order he read them in this morning.",
    "- Each one arrives twice. `THE MORNING HAD:` is the line that brief carried,",
    "  and under it is the afternoon's own note.",
    "- The heading opens with the pick's kind, capitalised, then ` - `, then the",
    "  headline sentence.",
    "- Write the story in this order: what changed since the morning, in one",
    "  sentence; what that does to the story he already has; what is still not",
    "  established.",
    "- Never tell the morning's story again. One clause saying what it had is the",
    "  most it gets.",
]


def section_job(run_dir: Path, run: dict, section: str, headings: list) -> str:
    """What one section writer is told about its job, and about the others.

    The other sections' stories are listed by headline so a writer does not
    retell a story another writer owns; that is all the cross-talk the
    parallel write keeps. How many writers there are, and whether this one is
    writing what moved, both come from the run's slot.
    """
    picks = (load_json(run_dir / "picks" / "picks.json") or {}).get("picks") or []
    sections = sections_of(run)
    mine = headings[sections.index(section)]
    n = len(sections)
    lines = [
        "## Your section",
        "",
        f"{WRITER_COUNT.get(n, f'{n} writers are')} at work on this brief at the "
        f"same time, one per section,",
        "from the same notes and the same template, and code joins the sections in",
        f"the template's order. You write **one section only: `## {mine}`**.",
        "",
        "- The picks above are every story of your section, and every one goes in.",
        f"- Reply with that section and nothing else. It starts with the `## {mine}`",
        "  line and ends with the last source line of its last story. No date line,",
        "  no other section, no placeholder line: those belong to code or to the",
        "  other writers.",
    ]
    if run.get("slot") == "afternoon" and section == "moved":
        lines += MOVED_JOB
    others = []
    for other, heading in zip(sections, headings):
        if other == section:
            continue
        for p in picks:
            if (p.get("tag") or "").upper() != tag_of(run, other):
                continue
            note = run_dir / "notes" / f"{p['id']}.md"
            head = note_field(note.read_text(encoding="utf-8"), "HEADLINE") \
                if note.exists() else ""
            others.append(f"  - {heading}: {head or p['id']}")
    if others:
        lines += ["- The other writers have these stories. Never retell one; where",
                  "  yours turns on it, one clause saying the brief covers it is enough:"]
        lines += others
    else:
        lines += ["- The other sections are empty today: yours is the whole brief",
                  "  below the date line."]
    return "\n".join(lines)


# ------------------------------------------------- the screen attempt record
#
# Two screens of one source at the same time is the one failure this pipeline
# cannot survive quietly: both fetch the same site at once, both slow each
# other down, and the slower one closes the faster one's task space and
# overwrites its file. So an attempt is recorded before a screener is given a
# prompt, and a second prompt for the same source is refused until the first
# attempt is provably over.

ATTEMPT_GRACE_SECONDS = 60      # a command may be a little past its own deadline


def attempt_path(run_dir: Path, slug: str) -> Path:
    return run_dir / "screen" / f"{slug}.attempt.json"


def screen_attempt(run_dir: Path, slug: str) -> dict:
    return load_json(attempt_path(run_dir, slug)) or {}


def file_attempt(reply: dict) -> int:
    """Which attempt wrote a screen file. Files written before attempts were
    recorded carry no number; they are the first and only attempt."""
    try:
        return int(reply.get("attempt") or 1)
    except (TypeError, ValueError):
        return 1


def attempt_over(run_dir: Path, slug: str, rec: dict, timeout: int):
    """Is the recorded attempt provably finished? Returns (yes, why not).

    Two proofs, and nothing else counts. Either the command wrote its file --
    a `seconds` field is only written on the last line of the command, so the
    file is its receipt -- or so much time has passed that the command has hit
    its own deadline and cannot still be running.
    """
    n = int(rec.get("attempt") or 0)
    reply = load_json(run_dir / "screen" / f"{slug}.json")
    if reply is not None and reply.get("seconds") is not None \
            and file_attempt(reply) == n:
        return True, ""
    started = parse_iso(rec.get("started_utc") or "")
    if started is None:
        return True, ""          # a record with no clock proves nothing; let it go
    age = (utc_now() - started).total_seconds()
    dead_at = timeout + ATTEMPT_GRACE_SECONDS
    if age >= dead_at:
        return True, ""
    return False, (f"{slug}: attempt {n} started {int(age)}s ago and has written no "
                   f"result yet, so it may still be fetching. Wait "
                   f"{int(dead_at - age)}s more, or until its screener replies, "
                   f"then run this again.")


def cmd_fill(args):
    """Render one single-call prompt, with its run data already in it.

    The orchestrator never formats an article list or pastes a fragment: it
    runs this, reads the file, and hands the text to the agent. An unfilled
    placeholder stops the run here instead of reaching an agent that cannot
    know what it was meant to receive.
    """
    run_dir = run_dir_of(args)
    run = load_run(run_dir)
    name = args.prompt
    src = skill_dir() / "prompts" / f"{name}.md"
    if not src.exists():
        die(f"no prompt at {src}")

    if args.part and name != "cluster-select":
        die("--part is only for cluster-select: it names one part of a cut kept list")
    if args.retry and name != "screen":
        die("--retry is only for screen: it is how a second screen of one source "
            "is allowed, and only once the first one is over")
    if args.section and name != "write":
        die("--section is only for write: it names the one section a writer produces")
    # argparse takes every slot's section names, since it is built before any
    # run is known. This is where a section of the other slot is refused.
    if args.section and args.section not in sections_of(run):
        die(f"--section {args.section} is not a section of a {run['slot']} run; "
            f"a {run['slot']} run writes {', '.join(sections_of(run))}")
    ns = namespace(need_profile=(name != "screen"))
    ns.update({
        "DATE": run["local_date"],
        "SLOT": run["slot"],
        "RUN_DIR": str(run_dir),
        "WINDOW_START": run["window_start_utc"],
        "WINDOW_END": run["window_end_utc"],
    })

    if name == "screen":
        if run.get("slot") == "evening":
            die(EVENING_NO_SCREEN)
        if not args.source:
            die("fill screen needs --source <slug>")
        found = [(n, s) for n, s in run["sources"].items() if s["slug"] == args.source]
        if not found:
            die(f"no source with slug {args.source} in this run")
        sname, s = found[0]
        slug = s["slug"]
        timeout = int(load_settings()["screen_timeout_seconds"])
        rec = screen_attempt(run_dir, slug)
        prev = int(rec.get("attempt") or 0)
        if prev and not rec.get("done"):
            if not args.retry:
                die(f"{slug}: attempt {prev} is recorded as started and not done. "
                    f"Never screen one source twice at the same time. Pass --retry "
                    f"once that attempt is over.", 1)
            over, why = attempt_over(run_dir, slug, rec, timeout)
            if not over:
                die(why, 1)
        attempt = prev + 1
        write_json(attempt_path(run_dir, slug),
                   {"slug": slug, "attempt": attempt, "started_utc": iso(utc_now()),
                    "token": f"{slug}-a{attempt}-{os.getpid()}", "done": False})
        ns.update({"SOURCE_NAME": sname, "SLUG": slug,
                   "SOURCE_URL": s["front_page"],
                   "SOURCE_JSON": json.dumps(sname),
                   "ATTEMPT": str(attempt),
                   "TASK_SPACE": f"ybs screen {slug} a{attempt}"})
    elif name == "cluster-select":
        ns["SLOT_JOB"] = slot_job(run_dir, run)
        records = kept_articles(run_dir)
        too_long = len(records) > CLUSTER_MAX
        parts = part_cut(records, CLUSTER_MAX) if too_long else [records]
        if args.part:
            m = re.fullmatch(r"(\d+)/(\d+)", args.part.strip())
            if not m:
                die("--part takes k/n, e.g. 2/3")
            k, n = int(m.group(1)), int(m.group(2))
            if not too_long:
                die(f"{len(records)} kept articles fit one call "
                    f"(cluster_articles_max is {CLUSTER_MAX}); there are no parts")
            if n != len(parts) or not 1 <= k <= n:
                die(f"the kept list cuts into {len(parts)} parts, not {n}")
            part_suffix = f"-part{k}of{n}"
            ns["ARTICLES"] = article_lines(parts[k - 1])
            ns["PART_NOTE"] = PART_NOTE.format(k=k, n=n)
        elif too_long:
            # Not a failure and not a file: a decision the orchestrator makes.
            print(json.dumps({"prompt": name, "too_long": True, "file": None,
                              "kept": len(records), "ceiling": CLUSTER_MAX,
                              "parts": len(parts),
                              "cut": [{"part": i, "articles": len(part),
                                       "sources": sorted({r["source"] for r in part})}
                                      for i, part in enumerate(parts, 1)]},
                             indent=2, ensure_ascii=False))
            return 0
        else:
            ns["ARTICLES"] = article_lines(records)
            ns["PART_NOTE"] = ""
    elif name == "cluster-merge":
        ns["SLOT_JOB"] = slot_job(run_dir, run)
        records = kept_articles(run_dir)
        if len(records) <= CLUSTER_MAX:
            die(f"{len(records)} kept articles fit one call "
                f"(cluster_articles_max is {CLUSTER_MAX}); there is nothing to merge")
        parts = part_cut(records, CLUSTER_MAX)
        n = len(parts)
        extra = sorted(f.name for f in (run_dir / "items").glob("plan-part*.json")
                       if int(re.search(r"plan-part(\d+)", f.name).group(1)) > n)
        if extra:
            die(f"{', '.join(extra)}: more part plans than the cut has parts ({n}); "
                f"the kept list changed after the parts were rendered")
        rank = load_profile()["rank"]
        blocks, near = [], []
        for k, part in enumerate(parts, 1):
            f = run_dir / "items" / f"plan-part{k}.json"
            plan = load_json(f)
            if not plan or "items" not in plan:
                die(f"no items/plan-part{k}.json with an 'items' list")
            part_ids = {r["id"] for r in part}
            in_plan = {a for it in plan["items"] for a in (it.get("articles") or [])}
            problems = [f"{a} is not in part {k}" for a in sorted(in_plan - part_ids)]
            if not problems:
                problems, placed = plan_problems(plan["items"], part_ids, part_ids,
                                                 rank, base_pick_ids(run))
                problems += [f"{a}: kept at triage but in no item"
                             for a in sorted(part_ids - set(placed))]
            if problems:
                print(json.dumps({"prompt": name, "ok": False, "part": k,
                                  "problems": problems}, indent=2, ensure_ascii=False))
                return 1
            by_id = {r["id"]: r for r in part}
            for it in plan["items"]:
                blocks.append(f"{k}/{it.get('item_id')} · {it.get('kind')} · "
                              f"{it.get('verdict')} · profile: {it.get('profile') or 'null'} · "
                              f"primary: {it.get('primary')} · "
                              f"read: {', '.join(it.get('read') or []) or '-'} · "
                              f"why: {it.get('why') or ''}")
                blocks.append(article_lines([by_id[a] for a in it["articles"]]))
                blocks.append("")
            near += [f"part {k}: {x}" for x in (plan.get("near_misses") or [])]
        if near:
            blocks += ["Near misses the parts reported:", ""] + [f"- {x}" for x in near]
        ns["PART_ITEMS"] = "\n".join(blocks).strip()
        ns["PARTS"] = str(n)
    elif name == "pick":
        ns["NOTES"], note_ids = notes_block(run_dir)
        ns["NOTE_IDS"] = " ".join(note_ids)
        ns["NOTE_COUNT"] = str(len(note_ids))
        if run.get("slot") == "afternoon":
            # The update asks a different question of the same notes -- did this
            # move? -- so it is a different prompt file. What it renders into
            # keeps the name `pick`, so step 7's launch line is one line in both
            # slots and the orchestrator never has to know which slot it is on.
            src = skill_dir() / "prompts" / "pick-update.md"
            ns["BASE_STORIES"] = base_stories(run)
            ns["BASE_DROPPED"] = base_dropped(run)
        elif run.get("slot") == "evening":
            # The evening's question is the third one: is this an achievement
            # now that the article has been read, and how far has it got? The
            # notes are the whole of what it needs to answer.
            src = skill_dir() / "prompts" / "pick-evening.md"
    elif name == "counterpoint":
        if not args.article:
            die("fill counterpoint needs --article <id>")
        note = run_dir / "notes" / f"{args.article}.md"
        if not note.exists():
            die(f"no note at {note}")
        picks = (load_json(run_dir / "picks" / "picks.json") or {}).get("picks") or []
        tag = next(((i.get("tag") or "").upper() for i in picks
                    if i.get("id") == args.article), None)
        if tag != "LEAD":
            die(f"{args.article} is tagged {tag or 'nothing'}; "
                "counterpoints run for LEAD stories only")
        siblings = item_siblings(run_dir, args.article)
        if not siblings:
            # One outlet reported this event and nobody else did: there is
            # nothing for an agent to check. Not a failure and not a prompt,
            # so this writes the answer itself and the orchestrator skips it.
            cp = run_dir / "picks" / f"cp-{args.article}.md"
            cp.parent.mkdir(parents=True, exist_ok=True)
            cp.write_text(SCHEMA["sentinel"]["no_case"] + "\n", encoding="utf-8")
            print(json.dumps({"prompt": name, "article": args.article,
                              "alone_in_item": True, "file": None,
                              "wrote": str(cp), "launch": False},
                             indent=2, ensure_ascii=False))
            return 0
        text = note.read_text(encoding="utf-8")
        ns.update({"ARTICLE_ID": args.article,
                   "WHAT_HAPPENED": note_field(text, "WHAT HAPPENED"),
                   "PRINCIPLE": note_field(text, "THE PRINCIPLE"),
                   "ITEM_POOL": sibling_lines(run_dir, siblings)})
    elif name == "write":
        # The template is rendered too, so it can name a setting without
        # restating its value. {{AUDIT_LINE}} passes through: code fills it in
        # once the brief is written.
        update = run.get("slot") == "afternoon"
        ns.update(head_vars(run))
        raw = template_source(run)
        tpl, tpl_missing = render(raw, ns)
        if tpl_missing:
            die(f"{run['slot']}.md asks for {', '.join(tpl_missing)}, "
                f"which nothing provides")
        section = args.section
        if section:
            # One writer per section. A section with no picks gets no writer:
            # the template omits an empty section, and write-stitch does too.
            tag = tag_of(run, section)
            picks = (load_json(run_dir / "picks" / "picks.json") or {}).get("picks") or []
            if not any((p.get("tag") or "").upper() == tag for p in picks):
                print(json.dumps({"prompt": name, "section": section, "empty": True,
                                  "file": None, "launch": False}, indent=2))
                return 0
            headings = template_headings(raw, run)
            ns.update({"TEMPLATE": tpl,
                       "PICKS": picks_block(run_dir, run, tag),
                       "COUNTERPOINTS": NO_COUNTERPOINTS if update
                       else (counterpoints_block(run_dir) if section == "leads"
                             else "None here. Counterpoints hang under the leads, "
                                  "and another writer is writing those."),
                       "SECTION_JOB": section_job(run_dir, run, section, headings)})
        else:
            ns.update({"TEMPLATE": tpl,
                       "PICKS": picks_block(run_dir, run),
                       "COUNTERPOINTS": NO_COUNTERPOINTS if update
                       else counterpoints_block(run_dir),
                       "SECTION_JOB": ""})

    text, missing = render(src.read_text(encoding="utf-8"), ns)
    suffix = f"-{args.source or args.article}" if (args.source or args.article) else ""
    if name == "screen" and attempt > 1:
        # A retry gets its own file. The first screener may still be holding the
        # old one open, and two attempts must share nothing at all.
        suffix += f"-a{attempt}"
    if args.part:
        suffix = part_suffix
    if args.section:
        suffix = f"-{args.section}"
    out = Path(args.out) if args.out else run_dir / "prompts" / f"{name}{suffix}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    result = {"prompt": name, "file": str(out), "unfilled": missing}
    if name == "screen":
        result["attempt"] = attempt
        result["task_space"] = ns["TASK_SPACE"]
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if missing else 0

# Every number this script obeys is a ceiling read from settings.md.
SETTINGS = load_settings()
POOL = SETTINGS["agents_active_max"]
TRIAGE_BATCH = SETTINGS["triage_batch_size"]
ITEM_FLOOR = SETTINGS["maybe_below_reads"]
MAX_PICKS = SETTINGS["picks_max"]
UPDATE_PICKS_MAX = SETTINGS["update_picks_max"]
ACHIEVEMENTS_MAX = SETTINGS["achievements_max"]
LEAD_MAX = SETTINGS["lead_max"]
WORTH_MAX = SETTINGS["worth_max"]
MAYBE_SHARE_MAX = SETTINGS["maybe_share_max"]
READ_ITEMS_MAX = SETTINGS["read_items_max"]
NEW_ITEM_ARTICLES_MIN = SETTINGS["new_item_articles_min"]
CLUSTER_MAX = SETTINGS["cluster_articles_max"]
RETRIES_MAX = SETTINGS["retries_max"]
X_WAIT_MINUTES = SETTINGS["x_wait_minutes_max"]


# ---------------------------------------------------------------- sources

# The heading in sources.md that divides the two halves. Everything under it is
# an X list; everything else is a news front page.
X_LISTS_HEADING = "x lists"


def read_sources(root: Path) -> tuple:
    """Read sources.md. One source per line, in either of these shapes:

        1. Guardian - https://www.theguardian.com/
        - Reason - https://reason.com/

    A line is a name and a link, and nothing else. The list marker and its
    number are ignored, so nothing needs renumbering. Lines without a link are
    ignored, which is why the notes at the top of the file are harmless.

    Returns `(rows, notices)`. A line that still carries a third part is read
    all the same -- an older copy of this file used one as a logged-in marker --
    but the part is dropped and the line earns a notice, which `start` prints.

    Lines under the `## X lists` heading are NOT news sources: they belong to
    the X half of the run and are read by `read_x_lists` instead. A front page
    is screened by an agent; an X list is scrolled by `x-lists/x_scrape.py`,
    and mixing the two would send a screener to x.com.
    """
    f = root / "sources.md"
    if not f.exists():
        die("sources.md not found at " + str(f))
    rows, notices = [], []
    section = ""
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("    ") or line.startswith("\t"):
            continue
        if line.strip().startswith("#"):
            section = line.strip().lstrip("#").strip().lower()
            continue
        if section == X_LISTS_HEADING:
            continue
        s = re.sub(r"^\s*(\d+[.)]|[-*+])\s+", "", line.strip())
        if not s or s.startswith("#") or "http" not in s:
            continue
        parts = [p.strip() for p in re.split(r"\s+[-–—]\s+", s) if p.strip()]
        url = next((p for p in parts if p.startswith("http")), None)
        if not url or parts[0] == url:
            continue
        i = parts.index(url)
        name = " - ".join(parts[:i])
        if parts[i + 1:]:
            notices.append(f'sources.md: "{name}" has a third part; it is no '
                           f'longer used, delete it')
        rows.append({
            "name": name,
            "slug": slugify(name),
            "front_page": url,
        })
    if not rows:
        die("sources.md lists no sources (each line needs a name and a link)")
    return rows, notices


def read_x_lists(root: Path) -> list:
    """Read the `## X lists` section of sources.md: `1. Name - https://x.com/...`.

    Same forgiving line shape as a news source. An empty or absent section is
    not an error: the X half then has nothing to read and says so.
    """
    f = root / "sources.md"
    if not f.exists():
        die("sources.md not found at " + str(f))
    rows, section = [], ""
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("    ") or line.startswith("\t"):
            continue
        if line.strip().startswith("#"):
            section = line.strip().lstrip("#").strip().lower()
            continue
        if section != X_LISTS_HEADING:
            continue
        s = re.sub(r"^\s*(\d+[.)]|[-*+])\s+", "", line.strip())
        if not s or "http" not in s:
            continue
        parts = [p.strip() for p in re.split(r"\s+[-–—]\s+", s) if p.strip()]
        url = next((p for p in parts if p.startswith("http")), None)
        if not url or parts[0] == url:
            continue
        i = parts.index(url)
        name = " - ".join(parts[:i])
        rows.append({"name": name, "slug": slugify(name), "url": url})
    return rows


def cmd_sources(args):
    rows, notices = read_sources(project_root())
    for n in notices:
        print(n, file=sys.stderr)
    print(json.dumps({"sources": rows,
                       "x_lists": read_x_lists(project_root())},
                      indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- start

def runs_root() -> Path:
    """Where the run folders live. `YBS_RUNS_DIR` overrides it, and only the
    tests set it, the way `YBS_X_RUN` overrides the X chain and for the same
    reason: an afternoon test needs an empty runs folder, or it would find the
    real morning runs of today and update one of those."""
    override = os.environ.get("YBS_RUNS_DIR")
    if override:
        return Path(override).expanduser()
    return project_root() / "runs"


def base_record(run_dir: Path, run: dict) -> dict:
    """What a later run keeps about an earlier one it is built on.

    Enough to find that run's own files again, plus the time its template puts
    on its brief, so the later one can say which brief it follows or pools.
    """
    tpl = (skill_dir() / "templates" / f"{run.get('slot')}.md").read_text(encoding="utf-8")
    return {"run_id": run.get("run_id"), "run_dir": str(run_dir),
            "window_end_utc": run.get("window_end_utc"),
            "time": template_time(tpl)}


def find_base(named: str, local_date: str, slot: str = "morning",
              optional: bool = False):
    """The earlier run of today a later one is built on.

    Either the one `--base` names, or the latest run of today's local date
    whose slot is `slot` and whose status is completed. Which slot is asked
    for is the caller's business: an afternoon update follows the morning, and
    an evening report is built on both.

    There is normally no fallback -- an afternoon update with nothing to
    update is not a brief -- so with none this dies, naming exactly what it
    looked for. `optional` is for the one base a run can do without: an
    evening with no afternoon behind it is still a report, and that call gets
    `None` instead of a death.
    """
    if named:
        d = Path(named).resolve()
        if not (d / "run.json").exists():
            die(f"not a run folder (no run.json): {d}")
        r = load_run(d)
        if r.get("slot") != slot:
            die(f"--base {d.name} is slot {r.get('slot')!r}; "
                f"this run is built on a {slot} run")
        if r.get("status") != "completed":
            die(f"--base {d.name} is {r.get('status')!r}; "
                f"this run is built on a completed {slot} run")
        if r.get("local_date") != local_date:
            die(f"--base {d.name} is of {r.get('local_date')}, and today is "
                f"{local_date}; it is built on today's {slot} brief")
        return base_record(d, r)

    found = []
    for d in sorted(runs_root().glob("*")):
        r = load_json(d / "run.json")
        if not r:
            continue
        if (r.get("local_date") == local_date and r.get("slot") == slot
                and r.get("status") == "completed"):
            found.append((r.get("started_utc") or "", d.name, d, r))
    if not found:
        if optional:
            return None
        die(f"no {slot} brief to update: nothing under {runs_root()} has "
            f"local_date {local_date}, slot {slot} and status completed. "
            f"Run the {slot} brief first, or name a run with --base.")
    _, _, d, r = sorted(found)[-1]
    return base_record(d, r)


def cmd_start(args):
    root = project_root()
    # Read the source list first, and say once what is stale in it. The notice
    # goes to stderr because stdout is this command's JSON and the skill parses
    # it; a line of prose in the middle would break the run rather than warn it.
    sources, notices = read_sources(root)
    for n in notices:
        print(n, file=sys.stderr)
    now, local = utc_now(), datetime.now()
    local_date = local.strftime("%Y-%m-%d")
    # The afternoon updates one named brief and the evening pools two, so the
    # bases are settled before the folder is made: a run that cannot say what
    # it is built on is not started at all. The evening's afternoon is the one
    # base a run may do without -- an evening with none is still a report --
    # so it is the only one that can come back empty.
    if args.base and args.slot == "morning":
        die("--base names the morning run a later run is built on; "
            "a morning run is built on nothing")
    base = base_afternoon = None
    if args.slot in ("afternoon", "evening"):
        base = find_base(args.base, local_date)
    if args.slot == "evening":
        base_afternoon = find_base(None, local_date, "afternoon", optional=True)

    # "Today" means since local midnight on this machine, not the last 24 hours.
    midnight_utc = local.replace(hour=0, minute=0, second=0,
                                 microsecond=0).astimezone(timezone.utc)

    run_id = f"{local_date}_{args.slot}_{local.strftime('%H%M%S')}"
    run_dir = runs_root() / run_id
    if run_dir.exists():
        die(f"run folder already exists: {run_dir}")
    for sub in ("screen", "triage", "items", "pages", "notes", "checks", "picks"):
        (run_dir / sub).mkdir(parents=True)

    data = {
        "run_id": run_id,
        "slot": args.slot,
        "local_date": local_date,
        "window_start_utc": iso(midnight_utc),
        "window_end_utc": iso(now),
        "started_utc": iso(now),
        "completed_utc": None,
        "status": "running",
        "sources": {s["name"]: {"slug": s["slug"], "front_page": s["front_page"],
                                "status": "pending",
                                "listed": 0, "in_window": 0, "undated": 0,
                                "kept": 0, "retries": 0}
                    for s in sources},
        "counts": {},
        "events": [],
    }
    if base:
        data["base"] = base
    if args.slot == "evening":
        # Written even when it is None: the evening's pool is two runs or one,
        # and pool-sync reads the answer here rather than looking again.
        data["base_afternoon"] = base_afternoon
    save_run(run_dir, data)
    profile = load_profile()
    data["profile_built"] = profile.get("built_local_date", "unknown")
    data["profile_shows"] = len(profile.get("shows") or [])
    save_run(run_dir, data)

    print(json.dumps({"run_dir": str(run_dir), "run_id": run_id,
                      "profile_built": data["profile_built"],
                      "profile_shows": data["profile_shows"], "slot": args.slot,
                      "window_start_utc": data["window_start_utc"],
                      "window_end_utc": data["window_end_utc"],
                      "base": base,
                      "base_afternoon": base_afternoon,
                      "sources": list(data["sources"])}, indent=2))
    return 0


# ---------------------------------------------------------------- screen-sync

# The evening never opens a front page: its articles were screened this
# morning and this afternoon. Both halves of the screen step say so in the
# same words, and this is the one place those words are written.
EVENING_NO_SCREEN = "an evening run pools two earlier runs; run pool-sync"


def cmd_screen_sync(args):
    """Fold every screen/<slug>.json a screener produced into one articles.json.

    Each file is the screener's own reply, kept verbatim. This command only
    dedups by canonical URL, applies the window, and assigns stable ids.
    A link with no publication date is DROPPED, and so is one dated outside the
    window. On 2026-08-22 all 189 undated links were hubs, section pages, author
    profiles or site furniture; not one was an article. The per-source count is
    recorded so a source that stops publishing dates shows up as a number.

    A run with a base drops one more thing: any link the base run already
    screened, by the same canonical URL. That is not a new rule but the
    duplicate rule again -- the pipeline has already had that URL -- and it is
    what makes the afternoon's window "today, minus what the morning saw".
    """
    run_dir = run_dir_of(args)
    data = load_run(run_dir)
    if data.get("slot") == "evening":
        die(EVENING_NO_SCREEN)
    if (run_dir / "triage" / "todo.json").exists():
        die("triage ids are already frozen; re-syncing would renumber them")

    start = parse_iso(data["window_start_utc"])
    end = parse_iso(data["window_end_utc"])
    articles, seen, problems, stale = [], {}, [], {}

    base = data.get("base") or {}
    base_seen = set()
    if base:
        base_arts = (load_json(Path(base["run_dir"]) / "articles.json")
                     or {}).get("articles") or []
        base_seen = {canon(a["url"]) for a in base_arts if a.get("url")}

    for name, sinfo in data["sources"].items():
        f = run_dir / "screen" / (sinfo["slug"] + ".json")
        reply = load_json(f)
        if reply is None:
            sinfo["status"] = "missing"
            problems.append(f"{name}: no screen/{sinfo['slug']}.json")
            continue
        # A first attempt that finished after its retry did leaves an older file
        # behind. It is a straggler, not a result: the retry is the record.
        rec = screen_attempt(run_dir, sinfo["slug"])
        latest = int(rec.get("attempt") or 0)
        wrote = file_attempt(reply)
        if latest and wrote < latest:
            sinfo["status"] = "stale"
            stale[name] = {"file_attempt": wrote, "latest_attempt": latest}
            problems.append(f"{name}: screen/{sinfo['slug']}.json was written by "
                            f"attempt {wrote}, and attempt {latest} is the record")
            continue
        if latest and wrote == latest and not rec.get("done"):
            rec["done"] = True
            rec["finished_utc"] = iso(utc_now())
            write_json(attempt_path(run_dir, sinfo["slug"]), rec)
        if reply.get("truncated"):
            problems.append(f"{name}: the screen ran out of time with "
                            f"{reply.get('not_fetched', 0)} links not fetched")
        if reply.get("ok") is False:
            sinfo["status"] = reply.get("error", "failed")
            problems.append(f"{name}: screener reported {sinfo['status']}")
            continue
        links = reply.get("links") or []
        sinfo["listed"] = len(links)
        kept = 0
        undated = 0
        old = 0
        for L in links:
            url = (L.get("url") or "").strip()
            if not url.startswith("http"):
                continue
            key = canon(url)
            if key in base_seen:
                old += 1                      # the base run already had it. Drop.
                continue
            if key in seen:
                seen[key]["also_in"].append(name)
                continue
            raw = (L.get("published") or "").strip()
            pub = parse_iso(raw)
            if pub is None:
                undated += 1                  # no date: not an article. Drop.
                continue
            if DATE_ONLY.match(raw):
                # No clock to place inside the window. A bare date parses to
                # midnight UTC, which falls before a local midnight anywhere west
                # of UTC; it is today's article or it is not.
                if pub.strftime("%Y-%m-%d") != data["local_date"]:
                    continue
            elif not (start <= pub <= end):
                continue                      # dated, and outside today: drop here
            rec = {
                "id": None, "source": name, "url": url,
                "title": (L.get("title") or "").strip(),
                "description": (L.get("description") or "").strip(),
                "category": (L.get("category") or "").strip(),
                "published": iso(pub),
                "also_in": [],
            }
            seen[key] = rec
            articles.append(rec)
            kept += 1
        sinfo["in_window"] = kept
        sinfo["undated"] = undated
        sinfo["seen_this_morning"] = old
        sinfo["status"] = "screened"

    articles.sort(key=lambda r: (r["source"], r["url"]))
    for i, r in enumerate(articles, 1):
        r["id"] = f"a{i:03d}"

    write_json(run_dir / "articles.json", {"articles": articles})
    data["counts"]["screened"] = len(articles)
    data["counts"]["sources_ok"] = sum(1 for s in data["sources"].values()
                                       if s["status"] == "screened")
    data["counts"]["undated"] = sum(s.get("undated", 0) for s in data["sources"].values())
    data["counts"]["seen_this_morning"] = sum(s.get("seen_this_morning", 0)
                                              for s in data["sources"].values())
    save_run(run_dir, data)

    out = {"articles": len(articles),
           "undated_dropped": data["counts"]["undated"],
           "undated_by_source": {n: s["undated"] for n, s in data["sources"].items()
                                 if s.get("undated")},
           "seen_this_morning": data["counts"]["seen_this_morning"],
           "seen_by_source": {n: s["seen_this_morning"]
                              for n, s in data["sources"].items()
                              if s.get("seen_this_morning")},
           "duplicates_merged": sum(len(r["also_in"]) for r in articles),
           "stale": stale,
           "sources_ok": data["counts"]["sources_ok"],
           "sources_total": len(data["sources"]), "problems": problems}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 1 if problems else 0


# ---------------------------------------------------------------- pool-sync

def cmd_pool_sync(args):
    """Build the evening's articles.json out of what the day's earlier runs kept.

    The evening screens nothing. Its pool is every article the morning, and the
    afternoon if there was one, sent to triage and kept -- read through
    `kept_articles()`, so "kept" here means exactly what it meant in that run:
    an agent's keep, a section's, or one the orchestrator gave up on. An
    article those runs dropped is not looked at again; an off-beat achievement
    is not for the show either.

    From there this is `screen-sync` again with the front pages taken out: the
    same canonical URL is one article, the second sighting only adds its source
    to `also_in`, and the ids are renumbered a001 upwards, the morning's
    articles first. Each record keeps its `origin`, the run and the id it came
    from, so a note or a page saved this morning can still be found. The pool
    size is recorded as `screened`, because it is the number every later step
    already asks for by that name.
    """
    run_dir = run_dir_of(args)
    data = load_run(run_dir)
    slot = data.get("slot")
    if slot != "evening":
        die(f"pool-sync is the evening's step 2; this run is slot {slot!r}, "
            f"and it screens its own sources: run screen-sync")
    if (run_dir / "triage" / "todo.json").exists():
        die("triage ids are already frozen; re-syncing would renumber them")

    articles, seen, pooled = [], {}, {"morning": 0, "afternoon": 0}
    duplicates, bases = 0, []
    for base_slot, base in (("morning", data.get("base")),
                            ("afternoon", data.get("base_afternoon"))):
        if not base:
            continue
        base_dir = Path(base["run_dir"])
        if not (base_dir / "triage" / "verdicts.json").exists():
            die(f"{base['run_id']} has no triage/verdicts.json: that run never "
                f"finished triage, so it never said what it kept")
        for r in kept_articles(base_dir):
            key = canon(r["url"])
            if key in seen:
                # The same URL in both runs. The morning had it first, so the
                # morning's origin stands and the second run is a co-sighting,
                # recorded the way screen-sync records one. A source the
                # record already names is not named again: it is one fact.
                known = [seen[key]["source"]] + seen[key]["also_in"]
                if r["source"] not in known:
                    seen[key]["also_in"].append(r["source"])
                duplicates += 1
                continue
            rec = dict(r)
            rec["id"] = None
            rec["also_in"] = list(r.get("also_in") or [])
            rec["origin"] = {"run_id": base["run_id"], "id": r["id"]}
            seen[key] = rec
            articles.append(rec)
            pooled[base_slot] += 1
        bases.append({"slot": base_slot, "run_id": base["run_id"],
                      "run_dir": str(base_dir), "pooled": pooled[base_slot]})

    for i, r in enumerate(articles, 1):
        r["id"] = f"a{i:03d}"

    write_json(run_dir / "articles.json", {"articles": articles})
    data["counts"].update({"pooled_morning": pooled["morning"],
                           "pooled_afternoon": pooled["afternoon"],
                           "pool_duplicates": duplicates,
                           "screened": len(articles)})
    save_run(run_dir, data)
    log_event(run_dir, "pool_built",
              f"{len(articles)} articles pooled: {pooled['morning']} from the "
              f"morning, {pooled['afternoon']} from the afternoon, "
              + plural(duplicates, "duplicate") + " merged",
              pooled_morning=pooled["morning"],
              pooled_afternoon=pooled["afternoon"],
              pool_duplicates=duplicates)

    print(json.dumps({"articles": len(articles),
                      "pooled_morning": pooled["morning"],
                      "pooled_afternoon": pooled["afternoon"],
                      "pool_duplicates": duplicates,
                      "bases": bases}, indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- triage

def gave_up(run_dir: Path) -> set:
    """Article ids the orchestrator gave up sorting; each is kept, never dropped."""
    return {e.get("article") for e in load_run(run_dir).get("events", [])
            if e.get("type") == "triage_gave_up" and e.get("article")}


def cmd_triage_list(args):
    """Freeze the article list, admit what the section already settles, and
    print one launch block per batch of what is left.

    Two stages. The section a publisher filed a story under is a string, and
    matching a string against a list is code's work: an article whose section
    is wholly on beat is kept here, and no agent is spent on it. A match
    admits; nothing else drops. Everything unmatched -- including every
    generic `article` and `opinion` -- goes to an agent, which reads the
    headline and the description.

    An evening run admits nothing by section. Its articles were sorted by
    section this morning, and that sorting is how they reached this pool; the
    question tonight is a different one, and no publisher's section answers
    it. Every article goes to an agent, and the launch block's first line
    tells the agent which question it is being asked.

    The agents work in batches of `triage_batch_size`, because most of what an
    agent costs is paid before it reads a word. A launch block IS the agent's
    whole prompt: its instructions live in .claude/agents/ybs4-triage.md.
    """
    run_dir = run_dir_of(args)
    arts = (load_json(run_dir / "articles.json") or {}).get("articles")
    if not arts:
        die("no articles.json; run screen-sync first")
    frozen = run_dir / "triage" / "todo.json"
    if not frozen.exists():
        write_json(frozen, {"ids": [r["id"] for r in arts], "total": len(arts)})

    ids = set(load_json(frozen)["ids"])
    given_up = gave_up(run_dir)
    evening = load_run(run_dir).get("slot") == "evening"
    beats = set() if evening else beat_categories()
    head = f"{run_dir} | evening" if evening else str(run_dir)

    def clean(text):
        return re.sub(r"\s+", " ", text or "").replace("|", "/").strip()

    lines, done, admitted = [], 0, []
    for r in arts:
        if r["id"] not in ids:
            continue
        verdict_file = run_dir / "triage" / f"{r['id']}.verdict.txt"
        if verdict_file.exists() or r["id"] in given_up:
            done += 1
            continue
        if norm_category(r.get("category")) in beats:
            # The section settles it. Write the verdict code just decided, so
            # this article looks to every later step exactly like one an agent
            # sorted -- triage-check counts it, kept_articles() picks it up.
            verdict_file.parent.mkdir(parents=True, exist_ok=True)
            verdict_file.write_text(f"{r['id']} keep category\n", encoding="utf-8")
            admitted.append(r["id"])
            done += 1
            continue
        desc = clean(r["description"])[:200]
        lines.append(f"{r['id']} | [{clean(r['source'])}] "
                     f"({clean(r['category']) or '-'}) {clean(r['title'])} :: {desc}")

    if admitted:
        log_event(run_dir, "triage_category",
                  f"{len(admitted)} admitted by section, no agent")

    todo = []
    for i in range(0, len(lines), TRIAGE_BATCH):
        chunk = lines[i:i + TRIAGE_BATCH]
        todo.append({"ids": [ln.split(" | ", 1)[0] for ln in chunk],
                     "launch": "\n".join([head] + chunk)})

    print(json.dumps({"pool": POOL, "total": len(ids), "done": done,
                      "admitted_by_category": len(admitted),
                      "batch_size": TRIAGE_BATCH, "batches": len(todo),
                      "todo": todo}, indent=2, ensure_ascii=False))
    return 0


def cmd_triage_replay(args):
    """Replay the section filter over a finished run and diff it against that
    run's own verdicts. Reads only; writes nothing, changes nothing.

    The filter never drops, so a keep an agent made can never be lost here and
    the count that matters is the other direction: articles this filter admits
    that the agent had dropped. Those are not errors -- the filter is allowed
    to be more generous -- but each one is an article the cluster step now
    carries, so the list is printed in full to be read.
    """
    run_dir = run_dir_of(args)
    arts = (load_json(run_dir / "articles.json") or {}).get("articles")
    if not arts:
        die("no articles.json in that run")

    was = {}
    for f in sorted((run_dir / "triage").glob("*.verdict.txt")):
        parts = f.read_text(encoding="utf-8").split()
        if len(parts) > 1:
            was[parts[0]] = parts[1].lower()
    if not was:
        die("that run has no verdict files to compare against")

    beats = beat_categories()
    admitted, agreed, flips, deferred = [], 0, [], 0
    for r in arts:
        if norm_category(r.get("category")) in beats:
            admitted.append(r["id"])
            if was.get(r["id"]) == "keep":
                agreed += 1
            else:
                flips.append({"id": r["id"], "category": r.get("category"),
                              "was": was.get(r["id"], "?"),
                              "title": (r.get("title") or "")[:90]})
        else:
            deferred += 1

    batches = -(-deferred // TRIAGE_BATCH)
    print(json.dumps({
        "articles": len(arts),
        "labelled_verdicts": len(was),
        "admitted_by_category": len(admitted),
        "agent_agreed": agreed,
        "kept_then_dropped_now": 0,   # the filter cannot drop
        "dropped_then_kept_now": len(flips),
        "deferred_to_agents": deferred,
        "batch_size": TRIAGE_BATCH,
        "batches": batches,
        "agents_then": len(was), "agents_now": batches,
        "flips": flips,
    }, indent=2, ensure_ascii=False))
    return 0


def cmd_triage_check(args):
    """Every frozen id needs its own verdict file, holding one line: <id> keep|drop."""
    run_dir = run_dir_of(args)
    frozen = load_json(run_dir / "triage" / "todo.json")
    if not frozen:
        die("triage ids are not frozen; run triage-list first")

    verdicts, failing, missing = {}, [], []
    by_category = 0
    for aid in frozen["ids"]:
        f = run_dir / "triage" / f"{aid}.verdict.txt"
        if not f.exists():
            missing.append(aid)
            continue
        lines = [ln for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if len(lines) > 1:
            failing.append({"id": aid, "problem": "more than one line"})
            continue
        parts = lines[0].split() if lines else []
        if not parts:
            failing.append({"id": aid, "problem": "empty verdict file"})
            continue
        got_id, verdict = parts[0], (parts[1].lower() if len(parts) > 1 else "")
        if got_id != aid:
            failing.append({"id": aid, "problem": f"verdict file names {got_id}"})
        elif verdict not in ("keep", "drop"):
            failing.append({"id": aid, "problem": f"verdict '{verdict}' is not keep or drop"})
        else:
            verdicts[aid] = verdict
            # third token: how the verdict was reached, written by triage-list
            if len(parts) > 2 and parts[2].lower() == "category":
                by_category += 1

    # A give-up is durable. Its event is the record, so a later triage-check (a
    # retry pass, a second give-up, a resume after a crash) still counts the
    # article as kept. A valid verdict file that turned up meanwhile wins.
    given_up = gave_up(run_dir)
    for aid in sorted(given_up & set(frozen["ids"])):
        verdicts.setdefault(aid, "keep")
        failing = [x for x in failing if x["id"] != aid]
        missing = [x for x in missing if x != aid]

    if args.give_up:
        aid = args.give_up
        if aid not in frozen["ids"]:
            die(f"no such article: {aid}")
        verdicts.setdefault(aid, "keep")   # an article that cannot be sorted is kept
        failing = [x for x in failing if x["id"] != aid]
        missing = [x for x in missing if x != aid]
        if aid not in given_up:
            log_event(run_dir, "triage_gave_up", f"{aid}: kept unsorted", article=aid)

    write_json(run_dir / "triage" / "verdicts.json", verdicts)
    kept = [a for a, v in verdicts.items() if v == "keep"]
    data = load_run(run_dir)
    data["counts"]["triaged"] = len(verdicts)
    data["counts"]["kept"] = len(kept)
    data["counts"]["kept_by_category"] = by_category
    save_run(run_dir, data)

    print(json.dumps({"verdicts": len(verdicts), "kept": len(kept),
                      "kept_by_category": by_category,
                      "dropped": len(verdicts) - len(kept),
                      "missing": missing[:40], "failing": failing[:40]},
                     indent=2, ensure_ascii=False))
    return 1 if (failing or missing) else 0


# ---------------------------------------------------------------- cluster / select

# Priority order, best first. An item that follows a story the brief being
# updated ran comes before anything else of its verdict: it is the update. The
# reading pools are these names split at the verdict, so a new group is added
# here and nowhere else.
GROUP_ORDER = ("follow-read", "topic-read", "beat-read",
               "follow-maybe", "topic-maybe", "beat-maybe")
READ_GROUPS = tuple(g for g in GROUP_ORDER if g.endswith("-read"))
MAYBE_GROUPS = tuple(g for g in GROUP_ORDER if g.endswith("-maybe"))


def cmd_items_sync(args):
    """Validate items/plan.json and build the read list.

    Every item, cluster or single, carries a verdict and says which profile
    topic it is about. Being covered by several papers is a signal of
    importance, not a pass: an off-beat cluster is dropped like anything else.

    Expected shape:
      {"items": [{"item_id": "i01", "name": "...", "kind": "cluster"|"single",
                  "verdict": "READ"|"MAYBE"|"DROP",
                  "profile": "<a storyline or theme name>" | null,
                  "articles": ["a003", ...], "primary": "a003",
                  "read": ["a003", ...], "why": "..."}],
       "near_misses": ["..."]}
    """
    run_dir = run_dir_of(args)
    plan = load_json(run_dir / "items" / "plan.json")
    if not plan or "items" not in plan:
        die("no items/plan.json with an 'items' list")
    verdicts = load_json(run_dir / "triage" / "verdicts.json") or {}
    kept = {a for a, v in verdicts.items() if v == "keep"}
    known = {r["id"] for r in (load_json(run_dir / "articles.json") or {}).get("articles", [])}
    profile = load_profile()
    rank = profile["rank"]
    base_ids = base_pick_ids(load_run(run_dir))

    problems, placed = plan_problems(plan["items"], kept, known, rank, base_ids)
    counts = {g: 0 for g in GROUP_ORDER}
    dropped = 0
    small_new = []

    for index, it in enumerate(plan["items"]):
        verdict = (it.get("verdict") or "").upper()
        name = (it.get("profile") or "").strip()
        it["_rank"] = rank.get(name.lower()) if name else None
        it["_index"] = index
        it["_group"] = None
        it["_small_new"] = False
        if verdict in ("READ", "MAYBE"):
            kind = ("follow" if it.get("follows") else
                    ("topic" if it["_rank"] else "beat"))
            it["_group"] = f"{kind}-{verdict.lower()}"
            counts[it["_group"]] += 1
            # An update's own test for a story the brief being updated never
            # had: it counts only when the day has piled up around it. The
            # item is still grouped and still counted honestly; it is only
            # kept out of the reading pools.
            if (base_ids is not None and not it.get("follows")
                    and len(it.get("articles") or []) < NEW_ITEM_ARTICLES_MIN):
                it["_small_new"] = True
                small_new.append(it.get("item_id"))
        elif verdict == "DROP":
            dropped += 1

    for aid in sorted(kept - set(placed)):
        problems.append(f"{aid}: kept at triage but in no item")

    if problems:
        print(json.dumps({"ok": False, "problems": problems}, indent=2,
                         ensure_ascii=False))
        return 1

    # Priority order, then clusters before singles, then how high the topic
    # ranks in the profile, then how many papers ran it, then the agent's own
    # ordering. Every number here is a ceiling: nothing is added to reach one.
    def order(it):
        return (GROUP_ORDER.index(it["_group"]),
                0 if it.get("kind") == "cluster" else 1,
                it["_rank"] or 9999,
                -len(it.get("articles") or []),
                it["_index"])

    reads = sorted([it for it in plan["items"]
                    if it["_group"] in READ_GROUPS and not it["_small_new"]],
                   key=order)
    taken = reads[:READ_ITEMS_MAX]
    skipped_for_cap = [it.get("item_id") for it in reads[READ_ITEMS_MAX:]]

    maybes_taken = []
    if len(taken) < ITEM_FLOOR:
        allowed = min(ITEM_FLOOR - len(taken),
                      len(taken) * MAYBE_SHARE_MAX // 100)
        allowed = min(allowed, READ_ITEMS_MAX - len(taken))
        pool = sorted([it for it in plan["items"]
                       if it["_group"] in MAYBE_GROUPS and not it["_small_new"]],
                      key=order)
        maybes_taken = pool[:max(0, allowed)]

    to_read, seen = [], set()
    for it in taken + maybes_taken:
        for aid in (it.get("read") or it.get("articles") or []):
            if aid in seen:
                continue
            seen.add(aid)
            to_read.append({"id": aid, "item": it.get("item_id"),
                            "group": it["_group"], "profile": it.get("profile") or None,
                            "follows": it.get("follows") or None,
                            "primary": aid == it.get("primary")})
    write_json(run_dir / "items" / "read-list.json", {"read": to_read})

    for it in plan["items"]:
        for k in ("_rank", "_index", "_group", "_small_new"):
            it.pop(k, None)
    write_json(run_dir / "items" / "plan.json", plan)

    run = load_run(run_dir)
    run.setdefault("counts", {}).update(
        {"items": len(plan["items"]), "items_by_group": counts,
         "items_dropped": dropped, "items_taken": len(taken) + len(maybes_taken),
         "maybes_taken": len(maybes_taken), "to_read": len(to_read),
         "small_new_items": len(small_new)})
    save_run(run_dir, run)

    print(json.dumps({"ok": True, "items": len(plan["items"]),
                      "by_group": counts, "dropped": dropped,
                      "read_items_max": READ_ITEMS_MAX,
                      "reads_taken": len(taken), "skipped_for_cap": skipped_for_cap,
                      "maybes_taken": len(maybes_taken),
                      "small_new_items": len(small_new),
                      "articles_to_read": len(to_read),
                      "profile_built": profile.get("built_local_date", "unknown")},
                     indent=2, ensure_ascii=False))
    return 0


def nearest_profile_name(name: str, rank: dict) -> str:
    """The profile name closest to what the agent wrote, so one rerun fixes it."""
    words = set(re.findall(r"[a-z]+", name.lower()))
    best, score = "", 0
    for other in rank:
        overlap = len(words & set(re.findall(r"[a-z]+", other)))
        if overlap > score:
            best, score = other, overlap
    return best if score else ""


def cmd_read_list(args):
    """The ids still to read, one launch line each, for a rolling pool of ten.

    An id is done when its note exists (so this is safe after a crash) or when a
    read_failed event has retired it (change C: a reader that replies
    PAGE_TRUNCATED writes no note, so the id comes back here for its one retry).
    """
    run_dir = run_dir_of(args)
    plan = load_json(run_dir / "items" / "read-list.json")
    if not plan:
        die("no items/read-list.json; run items-sync first")
    arts = {r["id"]: r for r in (load_json(run_dir / "articles.json") or {}).get("articles", [])}
    retired = {e.get("article") for e in load_run(run_dir).get("events", [])
               if e.get("type") == "read_failed"}
    todo = []
    for r in plan["read"]:
        aid = r["id"]
        if (run_dir / "notes" / f"{aid}.md").exists() or aid in retired:
            continue
        a = arts.get(aid)
        if a:
            todo.append({"id": aid, "source": a["source"], "url": a["url"],
                         "title": a["title"], "item": r["item"],
                         "launch": f"{aid} | {a['source']} | {a['url']} | {run_dir}"})
    print(json.dumps({"pool": POOL, "todo": len(todo), "list": todo},
                     indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- figure check

def cmd_check_sync(args):
    """Apply the checkers' verdicts, over the notes the brief will actually use.

    The pick runs first (step 7), so the targets are the picked notes plus every
    counterpoint that is not NONE. checks/<id>.txt holds one line per figure,
    "<figure text> ... found|missing", or the single line "no figures".
    Pass 1 lists what needs its one re-read. Pass 2 strikes what is still missing
    and marks the note. A note is never dropped for a bad figure.

    Both passes run twice in a run (step 8 over the notes, step 9 over the
    counterpoints), so a strike must be final: a target with a figures_struck
    event is skipped on every later pass, and the struck count is cumulative.
    The events are the record; a check file stays the checker's.
    """
    run_dir = run_dir_of(args)
    picks = load_json(run_dir / "picks" / "picks.json")
    if not picks or "picks" not in picks:
        die("no picks/picks.json; the pick runs before the figure check in v3")

    targets = []
    for it in picks["picks"]:
        f = run_dir / "notes" / f"{it['id']}.md"
        if f.exists():
            targets.append(f)
    for f in sorted((run_dir / "picks").glob("cp-*.md")):
        if f.read_text(encoding="utf-8").strip() != "NONE":
            targets.append(f)

    struck_before = {e.get("article") for e in load_run(run_dir).get("events", [])
                     if e.get("type") == "figures_struck"}
    arts = {r["id"]: r for r in (load_json(run_dir / "articles.json") or {}).get("articles", [])}
    redo, struck, clean, unchecked, already = [], [], 0, [], []

    for note in targets:
        aid = note.stem
        if aid in struck_before:
            already.append(aid)          # struck on an earlier pass: the note is final
            continue
        f = run_dir / "checks" / f"{aid}.txt"
        if not f.exists():
            unchecked.append(aid)
            continue
        body = f.read_text(encoding="utf-8").strip()
        if body.lower() == "no figures" or not body:
            clean += 1                       # the note carries no figures at all
            continue
        missing = [ln.rsplit(None, 1)[0].strip()
                   for ln in body.splitlines()
                   if ln.strip().lower().endswith("missing")]
        if not missing:
            clean += 1
            continue
        if args.pass_no == 1:
            entry = {"id": aid, "missing": missing}
            a = arts.get(aid)
            if a:                        # a counterpoint is never re-read
                entry["launch"] = f"{aid} | {a['source']} | {a['url']} | {run_dir} | saved-page"
            redo.append(entry)
            continue
        text = note.read_text(encoding="utf-8")
        for m in missing:
            text = "\n".join(ln for ln in text.splitlines() if m not in ln)
        text = text.rstrip() + f"\n\nfigures: {len(missing)} unverified, removed\n"
        note.write_text(text, encoding="utf-8")
        struck.append({"id": aid, "removed": missing})
        log_event(run_dir, "figures_struck", f"{aid}: {len(missing)} unverified", article=aid)

    data = load_run(run_dir)
    data["counts"].update({"notes": len(list((run_dir / "notes").glob("*.md"))),
                           "checked": len(targets), "notes_clean": clean,
                           "notes_struck": len(struck_before | {x["id"] for x in struck})})
    save_run(run_dir, data)
    print(json.dumps({"pass": args.pass_no, "checked": len(targets), "clean": clean,
                      "unchecked": unchecked, "redo": redo, "struck": struck,
                      "already_struck": already},
                     indent=2, ensure_ascii=False))
    return 1 if (unchecked or redo) else 0


# ---------------------------------------------------------------- pick

REASON_TYPES = tuple(SCHEMA["reason_type"]["all"].split(" | "))
# The second label an update puts on a story it kept: how the story moved. Only
# a MOVED pick carries one, and the four are the whole vocabulary.
KINDS = tuple(SCHEMA["tag"]["kind"].split(" | "))

# The second word the evening puts on a pick: how far the thing has actually
# got, from a result people are living with down to something only announced.
# Every pick of an evening run carries one, and the five are the whole
# vocabulary.
LABELS = tuple(SCHEMA["tag"]["label"].split(" | "))

# The ceiling each slot's pick answers to, under the name settings.md gives it,
# so the trim can say which row of the file it obeyed.
PICKS_CEILING = {"morning": ("picks_max", MAX_PICKS),
                 "afternoon": ("update_picks_max", UPDATE_PICKS_MAX),
                 "evening": ("achievements_max", ACHIEVEMENTS_MAX)}

# How a story of the update's second section opens: the kind it was picked with,
# capitalised, then ` - `. The stitch is where that is checked, and the kinds
# come from the same one list the pick is checked against.
KIND_HEADING = re.compile(r"^### (?:" + "|".join(k.capitalize() for k in KINDS)
                          + r") - \S")


def cmd_picks_sync(args):
    """Validate picks/picks.json against the slot's tags and ceilings, then trim.

    Every ceiling here is a ceiling. A brief with two leads is right when only
    two stories deserve to lead, so nothing checks for a minimum. An update with
    no picks at all is right too: nothing moved between the two briefs.

    A reply over the ceiling is not a failure: code trims it, discarding the
    smallest stories first. A LEAD is never trimmed. Among the rest, the pick
    whose news item holds the fewest articles goes first; ties fall to the
    lower group, then to the pick the agent ranked last. Trimmed picks move to
    a "trimmed" list in the file, so a re-run of this check is a no-op.

    An afternoon run answers to the same shape with the update's own vocabulary:
    `NEW` and `MOVED` instead of the morning's three tags, `update_picks_max`
    instead of `picks_max`, a `kind` on every MOVED pick, and the item's
    `follows` agreeing with the tag. It trims a NEW before a MOVED, because the
    movement is the thing an update exists to carry. The brief being updated is
    only ever read here, never written.

    An evening run answers to the shape a third time, in the report's own
    vocabulary: one tag, `ACHIEVEMENT`, `achievements_max` instead of
    `picks_max`, and a `label` on every pick saying how far the thing has got.
    No pick carries a kind and no item follows anything, because the evening
    reports today's own achievements and not the movement of an earlier story.

    Expected shape:
      {"picks": [{"id": "a003", "tag": "LEAD", "why": "..."}],
       "dropped": [{"id": "a007", "reason_type": "evidence", "reason": "..."}],
       "trimmed": [{"id": "a009", "tag": "BODY", "articles": 1, "reason": "..."}]}
    ("trimmed" is written by this command, never by the agent.)
    """
    run_dir = run_dir_of(args)
    p = load_json(run_dir / "picks" / "picks.json")
    if not p or "picks" not in p:
        die("no picks/picks.json with a 'picks' list")
    run = load_run(run_dir)
    slot = run.get("slot")
    afternoon = slot == "afternoon"
    evening = slot == "evening"
    tags = tags_of(run)
    over, ceiling = PICKS_CEILING[slot]
    notes = {f.stem for f in (run_dir / "notes").glob("*.md")}
    groups = {r["id"]: r.get("group") for r in
              ((load_json(run_dir / "items" / "read-list.json") or {}).get("read") or [])}
    # The plan is where an article's news item lives, and with it both the size
    # of the story and, in an update, the morning story it follows.
    items = (load_json(run_dir / "items" / "plan.json") or {}).get("items") or []
    item_of = {a: it for it in items for a in (it.get("articles") or [])}

    problems, seen = [], set()
    counts = {t: 0 for t in tags}
    followed = {}                    # base story -> the one pick that follows it

    # What one slot asks of one pick, beyond the tag every slot checks. Each
    # slot's rules sit in one place, so a reader of the afternoon's never has
    # to hold the evening's in mind. The morning asks nothing more: a rank is
    # the whole of what it says about a story.
    def afternoon_pick(aid, it, tag):
        """NEW or MOVED, with the kind and the item's `follows` agreeing."""
        kind = (it.get("kind") or "").strip().lower()
        follows = item_of.get(aid, {}).get("follows")
        if tag == "MOVED":
            if kind not in KINDS:
                problems.append(f"{aid}: kind {kind or '(none)'!r} is not one of "
                                f"{SCHEMA['tag']['kind']}")
            if not follows:
                problems.append(f"{aid}: tagged MOVED, and its item follows no "
                                f"story of the brief being updated")
            elif follows in followed:
                # One base story, one update line. Two would read as two
                # separate developments of the same thing.
                problems.append(f"{aid} and {followed[follows]} both follow "
                                f"{follows}; keep the one carrying the movement")
            else:
                followed[follows] = aid
        else:
            if kind:
                problems.append(f"{aid}: tagged NEW and given kind {kind!r}; a "
                                f"kind says how a story of the brief moved, and "
                                f"nothing of this one was in it")
            if follows:
                problems.append(f"{aid}: tagged NEW, and its item follows "
                                f"{follows}; a story that follows one of the "
                                f"brief's own is MOVED")

    def evening_pick(aid, it, tag):
        """ACHIEVEMENT, with a label saying how far the thing has got."""
        label = (it.get("label") or "").strip().lower()
        if label not in LABELS:
            problems.append(f"{aid}: label {label or '(none)'!r} is not one of "
                            f"{SCHEMA['tag']['label']}")
        kind = (it.get("kind") or "").strip().lower()
        if kind:
            problems.append(f"{aid}: given kind {kind!r}; a kind says how a "
                            f"story of an earlier brief moved, and an evening "
                            f"story moved nothing: it says how far it has got, "
                            f"in its label")
        follows = item_of.get(aid, {}).get("follows")
        if follows:
            problems.append(f"{aid}: its item follows {follows}; an evening "
                            f"story follows nothing, it is an achievement "
                            f"reported today")

    slot_pick = {"afternoon": afternoon_pick, "evening": evening_pick}.get(slot)

    for it in p["picks"]:
        aid, tag = it.get("id"), (it.get("tag") or "").upper()
        if aid not in notes:
            problems.append(f"{aid}: picked but has no note")
        if aid in seen:
            problems.append(f"{aid}: picked twice")
        seen.add(aid)
        if tag not in tags:
            problems.append(f"{aid}: tag '{tag}' is not {SCHEMA['tag'][slot]}")
        else:
            counts[tag] += 1
        if slot_pick and tag in tags:
            slot_pick(aid, it, tag)
    if slot == "morning":
        if counts["LEAD"] > LEAD_MAX:
            problems.append(f"{counts['LEAD']} LEAD stories; at most {LEAD_MAX}")
        if counts["WORTH"] > WORTH_MAX:
            problems.append(f"{counts['WORTH']} WORTH stories; at most {WORTH_MAX}")

    dropped = {}
    for d in p.get("dropped", []):
        aid = d.get("id")
        dropped[aid] = (d.get("reason") or "").strip()
        rtype = (d.get("reason_type") or "").strip().lower()
        if not dropped[aid]:
            problems.append(f"{aid}: dropped with no reason")
        if rtype not in REASON_TYPES:
            problems.append(f"{aid}: reason_type {rtype or '(none)'!r} is not one of "
                            f"{SCHEMA['reason_type']['all']}")
    trimmed_before = {t.get("id") for t in p.get("trimmed", [])}
    for aid in sorted(notes - seen - set(dropped) - trimmed_before):
        problems.append(f"{aid}: neither picked nor dropped")

    # A reply over the ceiling is trimmed, never failed — but only a reply that
    # passed every check above, so a rejected reply reaches the rerun intact.
    trimmed_now = []
    if not problems and len(p["picks"]) > ceiling:
        if slot == "morning" and counts["LEAD"] > ceiling:
            die(f"{counts['LEAD']} LEAD picks but picks_max is {ceiling}; "
                "lead_max in settings.md must not exceed picks_max")
        order = {it["id"]: i for i, it in enumerate(p["picks"])}

        def trim_key(it):
            tag = (it.get("tag") or "").upper()
            # The morning keeps every LEAD, which is why they are out of
            # `cuttable` below. The afternoon has no untouchable tag, so the
            # tag is the first thing sorted on instead: a NEW goes before a
            # MOVED, because an update is for what moved. The evening has one
            # tag and nothing to rank by it, so every pick starts level here
            # and the size of the story decides.
            new_first = 0 if (afternoon and tag == "NEW") else 1
            n_articles = len(item_of.get(it["id"], {}).get("articles") or [it["id"]])
            g = groups.get(it["id"])
            g_rank = GROUP_ORDER.index(g) if g in GROUP_ORDER else len(GROUP_ORDER)
            return (new_first, n_articles, -g_rank, -order[it["id"]])

        cuttable = sorted((it for it in p["picks"]
                           if slot != "morning"
                           or (it.get("tag") or "").upper() != "LEAD"),
                          key=trim_key)
        for it in cuttable[:len(p["picks"]) - ceiling]:
            trimmed_now.append({
                "id": it["id"], "tag": (it.get("tag") or "").upper(),
                "articles": len(item_of.get(it["id"], {}).get("articles") or [it["id"]]),
                "reason": f"trimmed by code: over {over}, fewest articles first"})
        cut_ids = {t["id"] for t in trimmed_now}
        p["picks"] = [it for it in p["picks"] if it["id"] not in cut_ids]
        p["trimmed"] = p.get("trimmed", []) + trimmed_now
        write_json(run_dir / "picks" / "picks.json", p)
        log_event(run_dir, "picks_trimmed",
                  f"{len(trimmed_now)} trimmed to {ceiling}: "
                  + ", ".join(sorted(cut_ids)))
        seen = {it["id"] for it in p["picks"]}
        counts = {t: 0 for t in tags}
        for it in p["picks"]:
            counts[(it.get("tag") or "").upper()] += 1

    mix = {"topic": 0, "beat": 0, "maybe": 0}
    if afternoon:
        # An update's own mix question is how much of it came from the brief it
        # follows, so the followers are counted as themselves rather than
        # falling into the beat bucket they would otherwise land in.
        mix["follow"] = 0
    for aid in seen:
        g = groups.get(aid) or ""
        if afternoon and g.startswith("follow"):
            mix["follow"] += 1
        else:
            mix["maybe" if g.endswith("maybe") else
                ("topic" if g.startswith("topic") else "beat")] += 1

    data = load_run(run_dir)
    record = {"picks": len(p["picks"]), "picks_dropped": len(dropped),
              "picks_mix": mix, "picks_trimmed": len(p.get("trimmed", []))}
    if afternoon:
        by_kind = {k: 0 for k in KINDS}
        for it in p["picks"]:
            kind = (it.get("kind") or "").strip().lower()
            # A kind outside the four is already a problem above; the counts
            # record what the run really holds and invent no bucket for it.
            if (it.get("tag") or "").upper() == "MOVED" and kind in by_kind:
                by_kind[kind] += 1
        record.update({"new": counts["NEW"], "moved": counts["MOVED"],
                       "moved_by_kind": by_kind})
    elif evening:
        by_label = {l: 0 for l in LABELS}
        for it in p["picks"]:
            label = (it.get("label") or "").strip().lower()
            # A label outside the five is already a problem above; the counts
            # record what the run really holds and invent no bucket for it.
            if label in by_label:
                by_label[label] += 1
        record.update({"achievements": counts["ACHIEVEMENT"],
                       "achievements_by_label": by_label})
    else:
        record.update({"leads": counts["LEAD"], "worth": counts["WORTH"],
                       "body": counts["BODY"]})
    data["counts"].update(record)
    save_run(run_dir, data)
    print(json.dumps({"picks": len(p["picks"]), "by_tag": counts, "mix": mix,
                      "dropped": len(dropped),
                      "trimmed": sorted(t["id"] for t in p.get("trimmed", [])),
                      "leads": [i["id"] for i in p["picks"]
                                if (i.get("tag") or "").upper() == "LEAD"],
                      "problems": problems[:20]}, indent=2, ensure_ascii=False))
    return 1 if problems else 0


# ---------------------------------------------------------------- the X run
#
# The X-list pipeline is one command of its own, `x-lists/x_run.py`, and nothing
# here reaches inside it: this launches it, waits for it, and copies the brief it
# wrote under the article brief. Every number it obeys lives in
# `settings.md` under `## X numbers`; the only number here is how long step 10
# waits.

X_POLL_SECONDS = 2          # how often x-wait looks; the run takes minutes
X_KILL_GRACE_SECONDS = 5    # between SIGTERM and SIGKILL on a timeout
X_LOG_MARK = "=== x-start"   # one launch's output starts below this line


def x_lists_dir() -> Path:
    return project_root() / "x-lists"


def x_script() -> Path:
    """The X chain's entry point. `YBS_X_RUN` overrides it, and only the tests
    set it: a stub there is how they exercise this without a browser."""
    override = os.environ.get("YBS_X_RUN")
    if override:
        return Path(override).expanduser()
    return x_lists_dir() / "x_run.py"


def new_x_run_dir() -> Path:
    """x-lists/runs/<YYYY-MM-DD-HHMM>, UTC, with -2, -3 on a collision.

    The same name `x_run.py` gives itself, because its write step reads the
    run's date and time out of the folder name.
    """
    root = x_lists_dir() / "runs"
    base = utc_now().strftime("%Y-%m-%d-%H%M")
    candidate, n = root / base, 2
    while candidate.exists():
        candidate = root / f"{base}-{n}"
        n += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def pid_age_seconds(pid: int):
    """How long the process holding this pid has been running, or None."""
    try:
        r = subprocess.run(["ps", "-o", "etime=", "-p", str(pid)],
                           capture_output=True, text=True, timeout=5)
    except Exception:
        return None
    m = re.match(r"^\s*(?:(\d+)-)?(?:(\d+):)?(\d+):(\d+)\s*$", r.stdout)
    if not m:
        return None
    days, hours, mins, secs = (int(x or 0) for x in m.groups())
    return ((days * 24 + hours) * 60 + mins) * 60 + secs


def x_alive(pid, started_utc: str = None) -> bool:
    """Is the X run still going?

    `os.kill(pid, 0)` alone would be fooled by a pid the system has handed to
    someone else, so the process's own age is checked against the moment we
    recorded launching it: a process older than that is not ours. `ps` may
    answer nothing on some machine, and then the pid is taken at face value --
    the window for a reused pid inside one morning is small.
    """
    if not isinstance(pid, int):
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, ValueError):
        return False
    except PermissionError:
        return False        # someone else's process, so not the run we started
    age = pid_age_seconds(pid)
    started = parse_iso(started_utc) if started_utc else None
    if age is not None and started is not None:
        ours = (utc_now() - started).total_seconds()
        if age > ours + 60:
            return False    # running before we launched: the pid was reused
    return True


def x_reason(log: Path) -> str:
    """Why an X run that wrote no brief stopped: its last `ERROR:` line, else
    the last thing it printed. A traceback ends without an `ERROR:`.

    A retry appends to the same log, so only what the last launch wrote counts:
    the first run's error is not the second run's reason.
    """
    if not log.exists():
        return "the X run left no log"
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    marks = [i for i, ln in enumerate(lines) if ln.startswith(X_LOG_MARK)]
    if marks:
        lines = lines[marks[-1] + 1:]
    lines = [ln.rstrip() for ln in lines if ln.strip()]
    if not lines:
        return "the X run wrote nothing to its log"
    errors = [ln for ln in lines if ln.lstrip().startswith("ERROR:")]
    return (errors[-1] if errors else lines[-1]).strip()[:300]


X_STEP_LINE = re.compile(r"^--\s*step\s+([1-7])\s*\(")


def x_failed_step(log: Path):
    """Which step of the X chain the last launch got to, or None.

    The chain prints one `-- step N (name): ...` line as it enters a step, so
    the highest N it printed is the step that failed. Only the last launch's
    section of the log counts -- a retry appends to the same file, and the
    first run's steps are not this one's. None means the log does not say, and
    the caller starts a fresh run rather than guessing.
    """
    if not log or not Path(log).exists():
        return None
    lines = Path(log).read_text(encoding="utf-8", errors="replace").splitlines()
    marks = [i for i, ln in enumerate(lines) if ln.startswith(X_LOG_MARK)]
    if marks:
        lines = lines[marks[-1] + 1:]
    steps = [int(m.group(1)) for ln in lines
             for m in [X_STEP_LINE.match(ln.strip())] if m]
    return max(steps) if steps else None


def x_state(run_dir: Path) -> dict:
    """The one status test, used by x-start, x-wait and x-merge.

    `running` while the pid is alive. `completed` once it is gone **and** the X
    run wrote its brief: the write agent edits that file while the chain is
    still up, so the file alone is not a finish signal. `failed` when it is gone
    and there is no brief. `skipped`, `failed` and `merged` are settled facts and
    are never recomputed.
    """
    data = load_run(run_dir)
    x = data.get("x")
    if not x:
        return {"status": "none"}
    if x.get("status") in ("skipped", "failed", "merged"):
        return x
    before = x.get("status")
    if x_alive(x.get("pid"), x.get("started_utc")):
        x["status"] = "running"
    elif (Path(x["run_dir"]) / "brief.md").exists():
        x["status"] = "completed"
    else:
        x["status"] = "failed"
        x["reason"] = x_reason(Path(x["log"]))
    if x["status"] != before:
        data["x"] = x
        save_run(run_dir, data)
    return x


def x_out(state: dict, **extra) -> int:
    """Every X command prints one JSON object, and none of them stops the brief."""
    out = {"status": state.get("status", "none"),
           "x_run_dir": state.get("run_dir"), "pid": state.get("pid"),
           "log": state.get("log"), "reason": state.get("reason")}
    out.update(extra)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def cmd_x_start(args):
    """Launch the X-list pipeline in its own process, once.

    Detached (`start_new_session`) so it outlives this command, and with its
    stdin closed: a child holding on to the Bash tool's pipe would keep the
    orchestrator's call hanging until the chain finished, which is the one thing
    running it in parallel is for.

    `--retry` after a failure resumes the failed run rather than starting over.
    The folder that run left behind is reused, and the chain is launched with
    `--from N` at the step its log says it reached, so the scrape, the filter
    and every note already written are kept: a step 3 failure used to cost a
    fresh scrape and 29 minutes of re-reading. If the folder is gone, or the
    log does not say which step failed, a fresh run starts from step 1 as
    before and the printed JSON says so (`"resumed": false` with a note).
    """
    run_dir = run_dir_of(args)
    state = x_state(run_dir)
    status = state.get("status")

    if status in ("running", "completed", "merged"):
        return x_out(state, launched=False,
                     note=f"an X run is already {status}; nothing was launched")
    if status == "skipped":
        return x_out(state, launched=False,
                     note="X was skipped for this run; nothing was launched")
    if status == "failed":
        if not args.retry:
            return x_out(state, launched=False,
                         note="the X run failed; only --retry launches again")
        if state.get("retries", 0) >= RETRIES_MAX:
            return x_out(state, launched=False,
                         note=f"already retried {state['retries']} time(s); "
                              f"retries_max is {RETRIES_MAX}")

    retries = state.get("retries", 0) + 1 if status == "failed" else 0
    data = load_run(run_dir)

    def skip(reason):
        data["x"] = {"status": "skipped", "reason": reason, "retries": retries,
                     "run_dir": None, "pid": None, "log": None,
                     "started_utc": iso(utc_now())}
        save_run(run_dir, data)
        log_event(run_dir, "x_skipped", reason)
        return x_out(data["x"], launched=False)

    script = x_script()
    if not script.exists():
        return skip(f"no X pipeline at {script}")
    # The browser check is for the real chain only. `YBS_X_RUN` names a stub,
    # and a stub needs no browser.
    if not os.environ.get("YBS_X_RUN") and not shutil.which("ego-browser"):
        return skip("ego-browser is not on the PATH")

    # A retry resumes the failed run's own folder from the step it died on,
    # when the folder is still there and its log says which step that was.
    resume_dir, resume_step, resume_note = None, None, None
    if retries:
        old_dir = Path(state["run_dir"]) if state.get("run_dir") else None
        if not old_dir or not old_dir.is_dir():
            resume_note = ("the failed run's folder is gone, so this retry "
                           "starts a fresh run from step 1")
        else:
            step = x_failed_step(state.get("log"))
            if not step:
                resume_note = (f"{old_dir.name}'s log does not say which step "
                               "failed, so this retry starts a fresh run from step 1")
            else:
                resume_dir, resume_step = old_dir, step

    x_dir = resume_dir or new_x_run_dir()
    cmd = [sys.executable, str(script), "--run-dir", str(x_dir)]
    if resume_step:
        cmd += ["--from", str(resume_step)]
    log_path = run_dir / "x" / "x-run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log:
        # Append, so a retry keeps the first run's log, and mark where this
        # launch begins so its own last line is the one that explains it.
        log.write(f"{X_LOG_MARK} {iso(utc_now())} ===\n")
        log.flush()
        proc = subprocess.Popen(
            cmd,
            cwd=str(x_lists_dir()), stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
            # Unbuffered, so the log reads in the order things happened: the
            # chain's progress goes to stdout and its errors to stderr, and a
            # buffered stdout would land after them, on top of the reason.
            env={**os.environ, "PYTHONUNBUFFERED": "1"})

    data = load_run(run_dir)
    data["x"] = {"run_dir": str(x_dir), "pid": proc.pid, "log": str(log_path),
                 "started_utc": iso(utc_now()), "status": "running",
                 "retries": retries}
    save_run(run_dir, data)
    if retries:
        where = (f"resumed {x_dir.name} from step {resume_step}" if resume_dir
                 else f"fresh {x_dir.name}")
        log_event(run_dir, "x_retry", f"{where} as pid {proc.pid}", retry=True)
    else:
        log_event(run_dir, "x_started", f"{x_dir.name} as pid {proc.pid}")

    extra = {}
    if retries:
        extra["resumed"] = bool(resume_dir)
        if resume_dir:
            extra["from_step"] = resume_step
        else:
            extra["note"] = resume_note
    return x_out(data["x"], launched=True, **extra)


def cmd_x_wait(args):
    """Block until the X run is done, failed, or out of time.

    The orchestrator calls this once and gets one answer; the polling is here so
    that no agent ever sits in a loop. `--timeout-seconds` is for the tests,
    which run the real settings table and so cannot inject a shorter wait.
    """
    run_dir = run_dir_of(args)
    state = x_state(run_dir)
    if state.get("status") in ("none", "skipped", "merged", "completed"):
        return x_out(state, waited_seconds=0)
    if state.get("status") == "failed":
        return x_out(x_note_failure(run_dir, state), waited_seconds=0)

    limit = args.timeout_seconds or X_WAIT_MINUTES * 60
    started = time.monotonic()
    while state.get("status") == "running":
        left = limit - (time.monotonic() - started)
        if left <= 0:
            break
        time.sleep(min(X_POLL_SECONDS, left))
        state = x_state(run_dir)

    waited = round(time.monotonic() - started, 1)

    if state.get("status") == "running":
        # Out of time. Nothing this run started outlives step 10: the whole
        # process group goes, so no headless agent is left heating the Mac.
        pid = state.get("pid")
        try:
            group = os.getpgid(pid)
            os.killpg(group, signal.SIGTERM)
            for _ in range(X_KILL_GRACE_SECONDS * 2):
                time.sleep(0.5)
                if not x_alive(pid, state.get("started_utc")):
                    break
            else:
                os.killpg(group, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, TypeError):
            pass
        spent = (f"{limit // 60} minutes" if limit >= 60 else f"{limit} seconds")
        state["status"] = "failed"
        state["reason"] = f"timeout after {spent}"
        data = load_run(run_dir)
        data["x"] = state
        save_run(run_dir, data)

    if state.get("status") == "failed":
        state = x_note_failure(run_dir, state)
    return x_out(state, waited_seconds=waited)


def x_note_failure(run_dir: Path, state: dict) -> dict:
    """Record a failed X run once, however x-wait came to see it. The audit line
    counts it as a failure from here, and a retry is launched from x-start."""
    events = load_run(run_dir).get("events", [])
    logged = sum(1 for e in events if e.get("type") == "x_failed")
    if logged <= state.get("retries", 0):
        log_event(run_dir, "x_failed", state.get("reason", ""))
    return state


def x_section(brief_text: str) -> str:
    """The X run's own brief, as a section of the article brief.

    Every heading drops one level, so the X items sit under one `##` heading
    the way an article story does, and the run folder name comes off the header
    line: it means nothing to Yaron. Nothing else is touched. The bullets, the
    rule and the closing line are the section's own, and they carry the X
    pipeline's own checks with them.
    """
    out = []
    for line in brief_text.strip().splitlines():
        if re.match(r"^#{1,5} ", line):
            out.append("#" + line)
            continue
        if line.startswith("**Run:**"):
            rest = [p.strip() for p in line.split("·") if p.strip()
                    and not p.strip().startswith("**Run:**")]
            if rest:
                out.append(" · ".join(rest))
            continue
        out.append(line)
    return "\n".join(out).strip()


X_COUNTS = re.compile(r"(\d+)\s+picks?\s+from\s+(\d+)\s+subjects", re.I)


def cmd_write_stitch(args):
    """Join the section files into brief.md, in the template's order.

    Every section that has picks must have its file, start with its own `##`
    heading, hold no other section and no placeholder, and carry the URL of
    every article picked for it: the template says the sources are exactly
    the picked articles, and this is where that is checked. A section with no
    picks is omitted, as the template says. On any problem nothing is written
    and the section to rerun is named.
    """
    run_dir = run_dir_of(args)
    run = load_run(run_dir)
    raw = template_source(run)
    headings = template_headings(raw, run)
    picks = (load_json(run_dir / "picks" / "picks.json") or {}).get("picks") or []
    if not picks:
        if run.get("slot") != "afternoon":
            die("no picks.json with picks; nothing to stitch")
        # An update that picked nothing is the true answer to a quiet afternoon,
        # not a failure: the head, one sentence, and the two lines code still
        # fills after this, so x-merge and audit-line work as they always do.
        brief = run_dir / "brief.md"
        brief.write_text("\n\n".join([template_head(raw, run), EMPTY_UPDATE_LINE,
                                      SCHEMA["x"]["placeholder"], "{{AUDIT_LINE}}"])
                         + "\n", encoding="utf-8")
        log_event(run_dir, "brief_stitched", "nothing moved since the morning")
        print(json.dumps({"ok": True, "brief": str(brief), "sections": [],
                          "ignored": [], "empty": True,
                          "note": EMPTY_UPDATE_LINE}, indent=2, ensure_ascii=False))
        return 0
    arts = {r["id"]: r for r in
            ((load_json(run_dir / "articles.json") or {}).get("articles") or [])}
    parts, problems, used, skipped = [template_head(raw, run)], [], [], []
    for section, heading in zip(sections_of(run), headings):
        tagged = [p for p in picks if (p.get("tag") or "").upper() == tag_of(run, section)]
        f = run_dir / f"brief-{section}.md"
        if not tagged:
            if f.exists():
                skipped.append(f.name)
            continue
        if not f.exists():
            problems.append(f"{section}: {len(tagged)} picks and no {f.name}")
            continue
        text = f.read_text(encoding="utf-8").strip()
        if text.startswith("```"):        # a writer that fenced its whole reply
            text = re.sub(r"^```[^\n]*\n|\n```$", "", text).strip()
        if not text.startswith(f"## {heading}"):
            problems.append(f"{section}: {f.name} does not start with '## {heading}'")
        foreign = [l for l in text.splitlines()
                   if l.startswith("## ") and l.strip() != f"## {heading}"]
        if foreign:
            problems.append(f"{section}: {f.name} holds another section: {foreign[0]}")
        if "{{" in text:
            problems.append(f"{section}: {f.name} carries a placeholder line; "
                            f"code writes those")
        for p in tagged:
            url = (arts.get(p["id"]) or {}).get("url")
            if url and url not in text:
                problems.append(f"{section}: {p['id']} is picked for it but its "
                                f"URL is not in {f.name}: {url}")
        if run.get("slot") == "afternoon" and section == "moved":
            # Two things the update's second section alone must get right: every
            # story says how it moved, and they run in the order he read them in.
            for line in text.splitlines():
                if line.startswith("### ") and not KIND_HEADING.match(line):
                    problems.append(
                        f"{section}: {f.name} has a story whose heading does not "
                        f"open with {' | '.join(k.capitalize() for k in KINDS)} "
                        f"and ' - ': {line.strip()}")
            rank = base_rank(run_dir, run)
            at = [(text.find((arts.get(p["id"]) or {}).get("url") or ""), p["id"])
                  for p in sorted(tagged, key=lambda p: rank.get(p["id"], len(rank)))]
            at = [(pos, aid) for pos, aid in at if pos >= 0]
            if [pos for pos, _ in at] != sorted(pos for pos, _ in at):
                problems.append(
                    f"{section}: {f.name} runs its stories in another order; the "
                    f"brief being updated ran them "
                    f"{', '.join(aid for _, aid in at)}")
        parts.append(text)
        used.append(f.name)
    if problems:
        print(json.dumps({"ok": False, "problems": problems}, indent=2, ensure_ascii=False))
        return 1
    parts += [SCHEMA["x"]["placeholder"], "{{AUDIT_LINE}}"]
    brief = run_dir / "brief.md"
    brief.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    log_event(run_dir, "brief_stitched", f"{len(used)} sections: {', '.join(used)}")
    print(json.dumps({"ok": True, "brief": str(brief), "sections": used,
                      "ignored": skipped}, indent=2, ensure_ascii=False))
    return 0


def cmd_x_merge(args):
    """Put the X run's brief under the article brief, in code.

    The X write agent already produced a verified, show-ready section, so this
    copies it rather than feeding its picks to another writer. The X run's own
    brief.md is read and never written.
    """
    run_dir = run_dir_of(args)
    brief = run_dir / "brief.md"
    if not brief.exists():
        die("no brief.md to merge into")
    state = x_state(run_dir)
    status = state.get("status")

    if status == "merged":
        return x_out(state, merged=False, note="this run's X section is already in")

    text = brief.read_text(encoding="utf-8")
    section, picks, subjects, tweets = "", 0, 0, 0

    if status == "completed":
        x_brief = Path(state["run_dir"]) / "brief.md"
        if not x_brief.exists():
            die(f"no X brief at {x_brief}")
        section = x_section(x_brief.read_text(encoding="utf-8"))
        m = X_COUNTS.search(section)       # the no-picks brief has no closing line
        if m:
            picks, subjects = int(m.group(1)), int(m.group(2))
        notes = Path(state["run_dir"]) / "notes"
        tweets = len([f for f in notes.iterdir() if f.is_file()]) if notes.is_dir() else 0
    elif status not in ("failed", "skipped"):
        # running, or no X run at all: nothing to merge and nothing to clear.
        return x_out(state, merged=False,
                     note=f"the X run is {status}; nothing was merged")

    # Placement, the way audit-line places its own line: the placeholder if the
    # write agent kept it, else above the audit line, else at the end.
    placeholder = SCHEMA["x"]["placeholder"]
    body = section + "\n\n" if section else ""
    if placeholder in text:
        text = re.sub(r"^[ \t]*" + re.escape(placeholder) + r"[ \t]*\n?",
                      body, text, count=1, flags=re.M)
    elif section:
        anchor = ("{{AUDIT_LINE}}" if "{{AUDIT_LINE}}" in text else
                  next((ln for ln in text.splitlines()
                        if AUDIT_OPENING.match(ln)), None))
        if anchor:
            text = text.replace(anchor, section + "\n\n" + anchor, 1)
        else:
            text = text.rstrip() + "\n\n" + section + "\n"
    brief.write_text(text, encoding="utf-8")

    data = load_run(run_dir)
    if status == "completed":
        state["status"] = "merged"
        data["counts"].update({"x_picks": picks, "x_subjects": subjects,
                               "x_tweets_read": tweets})
    data["x"] = state
    save_run(run_dir, data)
    log_event(run_dir, "x_merged",
              f"{picks} picks from {subjects} subjects, {tweets} tweets read"
              if status == "completed" else f"nothing to merge: {status}")
    return x_out(state, merged=status == "completed", x_picks=picks,
                 x_subjects=subjects, x_tweets_read=tweets)


def x_audit_bit(run_dir: Path) -> str:
    """What the audit line says about X, or nothing when the run never had it."""
    d = load_run(run_dir)
    x = d.get("x")
    if not x:
        return ""
    status = x.get("status")
    if status == "merged":
        c = d.get("counts", {})
        return (f"X: {c.get('x_picks', 0)} picks from "
                f"{c.get('x_subjects', 0)} subjects, "
                f"{c.get('x_tweets_read', 0)} tweets read")
    if status in ("failed", "skipped"):
        return f"X: none ({status}: {x.get('reason', 'no reason recorded')})"
    return f"X: {status}"


# ---------------------------------------------------------------- log, audit, close

def cmd_event(args):
    run_dir = run_dir_of(args)
    ev = log_event(run_dir, args.type, args.detail or "",
                   source=args.source, article=args.article,
                   retry=True if args.retry else None)
    print(json.dumps(ev, ensure_ascii=False))
    return 0


def audit_opening(run: dict) -> str:
    """How the audit line opens: which brief this is, and which one it updates.

    A morning brief's line has opened `Audit: ` since v1 and still does. An
    update says so in the same breath, and names the run it followed, so a
    brief in a folder can be told from the brief above it without opening
    anything else.
    """
    if run.get("slot") == "afternoon":
        base = (run.get("base") or {}).get("run_id") or "an unrecorded run"
        return f"Audit (afternoon, updates {base}): "
    return "Audit: "


# Both openings, for the one reader that has to find a line already written:
# x-merge, placing its section above it. One home for the shape.
AUDIT_OPENING = re.compile(r"^Audit(?: \([^)]*\))?: ")


def plural(n: int, word: str) -> str:
    """`1 development`, `2 developments`. Counts read as prose or not at all."""
    return f"{n} {word}" + ("" if n == 1 else "s")


def build_audit_line(run_dir: Path) -> str:
    d = load_run(run_dir)
    c = d.get("counts", {})
    evs = d.get("events", [])
    retries = sum(1 for e in evs if e.get("retry"))
    failures = [e for e in evs if "fail" in e.get("type", "").lower()]
    cps = [f for f in (run_dir / "picks").glob("cp-*.md")
           if f.read_text(encoding="utf-8").strip() != "NONE"]
    und = {n: s["undated"] for n, s in d.get("sources", {}).items() if s.get("undated")}
    g = c
    mix = c.get("picks_mix", {})
    profile_built = d.get("profile_built") or "unknown date"
    undated_bit = f"{sum(und.values())} undated links dropped"
    if und:
        undated_bit += " (" + ", ".join(f"{n} {k}" for n, k in sorted(und.items())) + ")"
    update = d.get("slot") == "afternoon"
    by_group = g.get("items_by_group", {})
    if update:
        # An update counts different things, because different things are the
        # question: what the morning had not already seen, how much of the day
        # was carried forward rather than found, and how the stories moved.
        screened_bit = (f"{c.get('screened', 0)} articles new since the morning "
                        f"({c.get('seen_this_morning', 0)} already seen)")
        items_bit = (
            f"{sum(by_group.values())} news items "
            f"({by_group.get('follow-read', 0) + by_group.get('follow-maybe', 0)} "
            f"following a morning story, "
            f"{c.get('small_new_items', 0)} new but too small to read)")
        kinds = c.get("moved_by_kind", {})
        picks_bits = [
            f"{c.get('new', 0)} new",
            f"{c.get('moved', 0)} moved ("
            + ", ".join(plural(kinds.get(k, 0), k) for k in KINDS) + ")",
        ]
    else:
        screened_bit = f"{c.get('screened', 0)} articles in window"
        items_bit = (f"{sum(by_group.values())} news items "
                     f"({by_group.get('topic-read', 0)} on a current topic)")
        picks_bits = [
            f"{c.get('picks', 0)} in the brief ({c.get('leads', 0)} leads, "
            f"{c.get('worth', 0)} worth attention)",
            f"picks by group: {mix.get('topic', 0)} topic, {mix.get('beat', 0)} beat, "
            f"{mix.get('maybe', 0)} maybe",
        ]
    bits = [
        f"{c.get('sources_ok', 0)} of {len(d.get('sources', {}))} sources screened",
        screened_bit,
        undated_bit,
        f"{c.get('kept', 0)} kept at triage"
        + (f" ({c['kept_by_category']} by section, no agent)"
           if c.get("kept_by_category") else ""),
        items_bit,
        f"{c.get('notes', 0)} read",
        f"{c.get('notes_struck', 0)} notes with a figure removed",
    ]
    bits += picks_bits
    bits.append(f"profile of {profile_built}")
    if not update:
        # An update has no lead, so it never ran a counterpoint to report.
        bits.append(f"{len(cps)} counterpoints")
    x_bit = x_audit_bit(run_dir)
    if x_bit:
        bits.append(x_bit)
    bits += [
        f"{retries} retries",
        f"{len(failures)} failures",
    ]
    split = [e for e in evs if e.get("type") == "cluster_split"]
    if split:
        bits.append(f"clustered in {split[-1].get('detail') or 'parts'}")
    return audit_opening(d) + " · ".join(bits) + "."


def cmd_audit_line(args):
    run_dir = run_dir_of(args)
    line = build_audit_line(run_dir)
    if args.append:
        brief = run_dir / "brief.md"
        if not brief.exists():
            die("no brief.md to append to")
        t = brief.read_text(encoding="utf-8")
        t = t.replace("{{AUDIT_LINE}}", line) if "{{AUDIT_LINE}}" in t \
            else t.rstrip() + "\n\n" + line + "\n"
        brief.write_text(t, encoding="utf-8")
    print(line)
    return 0


def cmd_close(args):
    run_dir = run_dir_of(args)
    d = load_run(run_dir)
    d["completed_utc"] = iso(utc_now())
    d["status"] = "completed"
    d["audit_line"] = build_audit_line(run_dir)
    save_run(run_dir, d)
    lines = [f"# Run {d['run_id']}", "",
             f"- slot: {d['slot']}",
             f"- window: {d['window_start_utc']} to {d['window_end_utc']}",
             f"- started: {d['started_utc']}  completed: {d['completed_utc']}", "",
             "## Counts", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(d.get("counts", {}).items())]
    lines += ["", "## Events", ""]
    lines += [f"- {e['utc']} · {e['type']} · {e.get('detail', '')}"
              for e in d.get("events", [])] or ["- none"]
    lines += ["", d["audit_line"], ""]
    (run_dir / "run-log.md").write_text("\n".join(lines), encoding="utf-8")
    print(d["audit_line"])
    return 0


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Bookkeeping for the YBS brief pipeline")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def with_run(p):
        p.add_argument("--run", required=True)
        return p

    sub.add_parser("settings").set_defaults(fn=cmd_settings)

    p = sub.add_parser("schema")
    p.add_argument("--key")
    p.set_defaults(fn=cmd_schema)

    p = sub.add_parser("build")
    p.add_argument("--check", action="store_true")
    p.set_defaults(fn=cmd_build)

    p = with_run(sub.add_parser("fill"))
    p.add_argument("prompt")
    p.add_argument("--source")
    p.add_argument("--article")
    p.add_argument("--part", metavar="K/N",
                   help="render part K of the N parts a too-long kept list cuts into")
    p.add_argument("--retry", action="store_true",
                   help="screen one source again, once its first attempt is over")
    p.add_argument("--section", choices=list(ALL_SECTIONS),
                   help="write only: the one section this writer produces")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_fill)

    sub.add_parser("sources").set_defaults(fn=cmd_sources)

    p = sub.add_parser("start")
    p.add_argument("--slot", default="morning", choices=list(WRITE_SECTIONS))
    p.add_argument("--base", metavar="RUN_DIR",
                   help="afternoon and evening: the morning run this one is "
                        "built on; without it the latest completed morning run "
                        "of today")
    p.set_defaults(fn=cmd_start)

    with_run(sub.add_parser("screen-sync")).set_defaults(fn=cmd_screen_sync)
    with_run(sub.add_parser("pool-sync")).set_defaults(fn=cmd_pool_sync)
    with_run(sub.add_parser("triage-list")).set_defaults(fn=cmd_triage_list)
    with_run(sub.add_parser("triage-replay")).set_defaults(fn=cmd_triage_replay)

    p = with_run(sub.add_parser("triage-check"))
    p.add_argument("--give-up", metavar="ID")
    p.set_defaults(fn=cmd_triage_check)

    with_run(sub.add_parser("items-sync")).set_defaults(fn=cmd_items_sync)
    with_run(sub.add_parser("read-list")).set_defaults(fn=cmd_read_list)

    p = with_run(sub.add_parser("check-sync"))
    p.add_argument("--pass", dest="pass_no", type=int, default=1, choices=[1, 2])
    p.set_defaults(fn=cmd_check_sync)

    with_run(sub.add_parser("picks-sync")).set_defaults(fn=cmd_picks_sync)

    p = with_run(sub.add_parser("x-start"))
    p.add_argument("--retry", action="store_true",
                   help="launch again after a failed X run, once")
    p.set_defaults(fn=cmd_x_start)

    p = with_run(sub.add_parser("x-wait"))
    # Hidden: the tests read the same settings.md the run does, so a short wait
    # can only come from here.
    p.add_argument("--timeout-seconds", type=int, default=0, help=argparse.SUPPRESS)
    p.set_defaults(fn=cmd_x_wait)

    with_run(sub.add_parser("write-stitch")).set_defaults(fn=cmd_write_stitch)
    with_run(sub.add_parser("x-merge")).set_defaults(fn=cmd_x_merge)

    p = with_run(sub.add_parser("event"))
    p.add_argument("--type", required=True)
    p.add_argument("--detail")
    p.add_argument("--source")
    p.add_argument("--article")
    p.add_argument("--retry", action="store_true")
    p.set_defaults(fn=cmd_event)

    p = with_run(sub.add_parser("audit-line"))
    p.add_argument("--append", action="store_true")
    p.set_defaults(fn=cmd_audit_line)

    with_run(sub.add_parser("close")).set_defaults(fn=cmd_close)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
