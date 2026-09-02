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
  start --slot morning     create the run folder, compute the time window
  screen-sync --run DIR    fold every screen/<slug>.json into articles.json
  triage-list --run DIR    freeze the article list, print one launch line per article
  triage-check --run DIR   verify every article has its own one-line verdict file
  triage-replay --run DIR  replay the section filter over a finished run, and diff
  items-sync --run DIR     validate the cluster/select plan, build the read list
  read-list --run DIR      the article ids still to read, one launch line each
  check-sync --run DIR     apply figure-check verdicts; list redos or strikes
  picks-sync --run DIR     validate the pick reply, and trim it to picks_max
  event --run DIR ...      record something that happened (failure, retry, ...)
  audit-line --run DIR     build the audit line from run.json (never from a model)
  close --run DIR          write run-log.md and mark the run finished

Exit codes: 0 = ok, 1 = did the job but found a problem, 2 = bad usage / error.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TAGS = ("LEAD", "BODY", "WORTH")


# ---------------------------------------------------------------- basics

def project_root() -> Path:
    """<root>/.claude/skills/ybs-brief-v4/scripts/ybs_run.py -> <root>"""
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

# Filled by the audit-line command long after an agent has run, so `fill` and
# `build` leave it alone.
PASS_THROUGH = {"AUDIT_LINE"}

SCHEMA = {
    "path": {
        "screen": "<run_dir>/screen/<slug>.json",
        "verdict": "<run_dir>/triage/<id>.verdict.txt",
        "plan": "<run_dir>/items/plan.json",
        "plan_part": "<run_dir>/items/plan-part<k>.json",
        "page": "<run_dir>/pages/<id>.txt",
        "note": "<run_dir>/notes/<id>.md",
        "check": "<run_dir>/checks/<id>.txt",
        "picks": "<run_dir>/picks/picks.json",
        "counterpoint": "<run_dir>/picks/cp-<id>.md",
        "brief": "<run_dir>/brief.md",
        "profile": "shows/profile.json",
    },
    "launch": {
        "triage": ("<run_dir>\n"
                   "<id> | [<source>] (<section>) <headline> :: <description>\n"
                   "<id> | [<source>] (<section>) <headline> :: <description>"),
        "reader": "<id> | <source> | <url> | <run_dir>",
        "reader_saved": "<id> | <source> | <url> | <run_dir> | saved-page",
        "checker": "<id> | <run_dir>",
    },
    "taskspace": {
        "screen": "ybs screen <slug>",
        "read": "ybs read <id>",
        "counterpoint": "ybs cp <id>",
    },
    "sentinel": {
        "session_down": "SESSION_DOWN",
        "truncated": "PAGE_TRUNCATED",
        "no_case": "NONE",
        "no_figures": "no figures",
        "triage": "keep | drop",
        "check": "found | missing",
        "verdict": "READ | MAYBE | DROP",
    },
    "tag": {"all": "LEAD | BODY | WORTH"},
    "reason_type": {
        "all": "evidence | duplicate | no-development | relevance",
        "evidence": "its `WEAK SPOTS`, or a claim nothing supports",
        "duplicate": "the same event as a story you kept",
        "no-development": "nothing happened: a column, a feature, a recap",
        "relevance": "real enough, but not worth his morning",
    },
}


# What a part of a cut kept list is told, and what the full list is told (nothing).
PART_NOTE = ("This is part {k} of {n}. Other parts hold other sources. Group only "
             "what is in front of you; an event another paper ran is merged later.")


def skill_dir() -> Path:
    """<root>/.claude/skills/ybs-brief-v4/scripts/ybs_run.py -> the skill folder"""
    return Path(__file__).resolve().parents[1]


def load_settings(path: Path = None) -> dict:
    """Read the settings.md tables.

    Under `## Numbers` a row is `| key | value | meaning |`. Values: digits are
    ints, `50%` is the int 50, `"a", "b"` is a list of strings, anything else is
    the text as written.

    Under `## Models` a row is `| step | model | effort | ... |`, and gives two
    keys, `<step>_model` and `<step>_effort`, so a template can ask for either.
    """
    path = path or (skill_dir() / "settings.md")
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
        "AGENT_RULES_BROWSER": fragment("agent-rules", "browser agents"),
        "AGENT_RULES_JSON": fragment("agent-rules", "json agents"),
        "PRINCIPLES": fragment("principles"),
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
             ".claude/skills/ybs-brief-v4/agents/{name}.md.tmpl — edit the "
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


def plan_problems(items: list, kept: set, known: set, rank: dict):
    """What is wrong with a cluster plan, in the words items-sync has always used.

    Shared by items-sync (the whole plan against the kept list) and by
    fill cluster-merge (each part against its own articles). Returns the
    problems and which item placed each article; it annotates nothing.
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


def picks_block(run_dir: Path) -> str:
    """Every picked note with its tag and its item's full article list."""
    picks = (load_json(run_dir / "picks" / "picks.json") or {}).get("picks") or []
    arts = {r["id"]: r for r in
            ((load_json(run_dir / "articles.json") or {}).get("articles") or [])}
    items = (load_json(run_dir / "items" / "plan.json") or {}).get("items") or []
    item_of = {a: it for it in items for a in (it.get("articles") or [])}
    out = []
    for p in picks:
        note = run_dir / "notes" / f"{p['id']}.md"
        if not note.exists():
            continue
        out.append(f"{p['id']} · {p.get('tag', '-')}")
        siblings = (item_of.get(p["id"], {}).get("articles") or [])
        out.append("SOURCES, the picked article first:")
        for a in [p["id"]] + [x for x in siblings if x != p["id"]]:
            r = arts.get(a, {})
            title = (r.get("title") or "").strip() or r.get("url", "-")
            out.append(f"- {title} · {r.get('source', '-')} · {r.get('url', '-')}")
        out.append(note.read_text(encoding="utf-8").strip())
        out.append("")
    if not out:
        die("no picked note has a file; nothing to write from")
    return "\n".join(out).strip()


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
    ns = namespace(need_profile=(name != "screen"))
    ns.update({
        "DATE": run["local_date"],
        "SLOT": run["slot"],
        "RUN_DIR": str(run_dir),
        "WINDOW_START": run["window_start_utc"],
        "WINDOW_END": run["window_end_utc"],
    })

    if name == "screen":
        if not args.source:
            die("fill screen needs --source <slug>")
        found = [(n, s) for n, s in run["sources"].items() if s["slug"] == args.source]
        if not found:
            die(f"no source with slug {args.source} in this run")
        sname, s = found[0]
        ns.update({"SOURCE_NAME": sname, "SLUG": s["slug"],
                   "SOURCE_URL": s["front_page"], "MARKER": s.get("marker") or "",
                   "MARKER_JSON": json.dumps(s.get("marker") or ""),
                   "SOURCE_JSON": json.dumps(sname)})
    elif name == "cluster-select":
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
                problems, placed = plan_problems(plan["items"], part_ids, part_ids, rank)
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
        tpl, tpl_missing = render((skill_dir() / "templates" /
                                   f"{run['slot']}.md").read_text(encoding="utf-8"), ns)
        if tpl_missing:
            die(f"{run['slot']}.md asks for {', '.join(tpl_missing)}, "
                f"which nothing provides")
        marker = "<!-- STRUCTURE:BEGIN -->"
        struct_src = (skill_dir() / "BRIEF-STRUCTURE.md").read_text(encoding="utf-8")
        if marker not in struct_src:
            die(f"BRIEF-STRUCTURE.md has no {marker} marker")
        struct_src = "\n".join(
            l for l in struct_src.split(marker, 1)[1].splitlines()
            if not l.lstrip().startswith(">"))
        structure, st_missing = render(struct_src, ns)
        if st_missing:
            die(f"BRIEF-STRUCTURE.md asks for {', '.join(st_missing)}, "
                f"which nothing provides")
        ns.update({"TEMPLATE": tpl,
                   "STRUCTURE": structure.strip(),
                   "PICKS": picks_block(run_dir),
                   "COUNTERPOINTS": counterpoints_block(run_dir)})

    text, missing = render(src.read_text(encoding="utf-8"), ns)
    suffix = f"-{args.source or args.article}" if (args.source or args.article) else ""
    if args.part:
        suffix = part_suffix
    out = Path(args.out) if args.out else run_dir / "prompts" / f"{name}{suffix}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(json.dumps({"prompt": name, "file": str(out), "unfilled": missing},
                     indent=2, ensure_ascii=False))
    return 1 if missing else 0

# Every number this script obeys is a ceiling read from settings.md.
SETTINGS = load_settings()
POOL = SETTINGS["agents_active_max"]
TRIAGE_BATCH = SETTINGS["triage_batch_size"]
ITEM_FLOOR = SETTINGS["maybe_below_reads"]
MAX_PICKS = SETTINGS["picks_max"]
LEAD_MAX = SETTINGS["lead_max"]
WORTH_MAX = SETTINGS["worth_max"]
MAYBE_SHARE_MAX = SETTINGS["maybe_share_max"]
READ_ITEMS_MAX = SETTINGS["read_items_max"]
CLUSTER_MAX = SETTINGS["cluster_articles_max"]
RETRIES_MAX = SETTINGS["retries_max"]


# ---------------------------------------------------------------- sources

def read_sources(root: Path) -> list:
    """Read sources.md. One source per line, in any of these shapes:

        1. Guardian - https://www.theguardian.com/
        - Reason - https://reason.com/
        WSJ - https://www.wsj.com/ - Sign Out

    The list marker and its number are ignored, so nothing needs renumbering.
    A third part is the logged-in marker for a paid site: text that only appears
    on the page when the session is alive. Lines without a link are ignored,
    which is why the notes at the top of the file are harmless.
    """
    f = root / "sources.md"
    if not f.exists():
        die("sources.md not found at " + str(f))
    rows = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.startswith("    ") or line.startswith("\t"):
            continue
        s = re.sub(r"^\s*(\d+[.)]|[-*+])\s+", "", line.strip())
        if not s or s.startswith("#") or "http" not in s:
            continue
        parts = [p.strip() for p in re.split(r"\s+[-–—]\s+", s) if p.strip()]
        url = next((p for p in parts if p.startswith("http")), None)
        if not url or parts[0] == url:
            continue
        i = parts.index(url)
        rows.append({
            "name": " - ".join(parts[:i]),
            "slug": slugify(" - ".join(parts[:i])),
            "front_page": url,
            "marker": " - ".join(parts[i + 1:]) or "FREE",
        })
    if not rows:
        die("sources.md lists no sources (each line needs a name and a link)")
    return rows


def cmd_sources(args):
    print(json.dumps(read_sources(project_root()), indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- start

def cmd_start(args):
    root = project_root()
    now, local = utc_now(), datetime.now()
    local_date = local.strftime("%Y-%m-%d")

    # "Today" means since local midnight on this machine, not the last 24 hours.
    midnight_utc = local.replace(hour=0, minute=0, second=0,
                                 microsecond=0).astimezone(timezone.utc)

    run_id = f"{local_date}_{args.slot}_{local.strftime('%H%M%S')}"
    run_dir = root / "runs" / run_id
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
                                "marker": s["marker"], "status": "pending",
                                "listed": 0, "in_window": 0, "undated": 0,
                                "kept": 0, "retries": 0}
                    for s in read_sources(root)},
        "counts": {},
        "events": [],
    }
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
                      "sources": list(data["sources"])}, indent=2))
    return 0


# ---------------------------------------------------------------- screen-sync

def cmd_screen_sync(args):
    """Fold every screen/<slug>.json a screener produced into one articles.json.

    Each file is the screener's own reply, kept verbatim. This command only
    dedups by canonical URL, applies the window, and assigns stable ids.
    A link with no publication date is DROPPED, and so is one dated outside the
    window. On 2026-08-22 all 189 undated links were hubs, section pages, author
    profiles or site furniture; not one was an article. The per-source count is
    recorded so a source that stops publishing dates shows up as a number.
    """
    run_dir = run_dir_of(args)
    data = load_run(run_dir)
    if (run_dir / "triage" / "todo.json").exists():
        die("triage ids are already frozen; re-syncing would renumber them")

    start = parse_iso(data["window_start_utc"])
    end = parse_iso(data["window_end_utc"])
    articles, seen, problems = [], {}, []

    for name, sinfo in data["sources"].items():
        f = run_dir / "screen" / (sinfo["slug"] + ".json")
        reply = load_json(f)
        if reply is None:
            sinfo["status"] = "missing"
            problems.append(f"{name}: no screen/{sinfo['slug']}.json")
            continue
        if reply.get("ok") is False:
            sinfo["status"] = reply.get("error", "failed")
            problems.append(f"{name}: screener reported {sinfo['status']}")
            continue
        links = reply.get("links") or []
        sinfo["listed"] = len(links)
        kept = 0
        undated = 0
        for L in links:
            url = (L.get("url") or "").strip()
            if not url.startswith("http"):
                continue
            key = canon(url)
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
        sinfo["status"] = "screened"

    articles.sort(key=lambda r: (r["source"], r["url"]))
    for i, r in enumerate(articles, 1):
        r["id"] = f"a{i:03d}"

    write_json(run_dir / "articles.json", {"articles": articles})
    data["counts"]["screened"] = len(articles)
    data["counts"]["sources_ok"] = sum(1 for s in data["sources"].values()
                                       if s["status"] == "screened")
    data["counts"]["undated"] = sum(s.get("undated", 0) for s in data["sources"].values())
    save_run(run_dir, data)

    out = {"articles": len(articles),
           "undated_dropped": data["counts"]["undated"],
           "undated_by_source": {n: s["undated"] for n, s in data["sources"].items()
                                 if s.get("undated")},
           "duplicates_merged": sum(len(r["also_in"]) for r in articles),
           "sources_ok": data["counts"]["sources_ok"],
           "sources_total": len(data["sources"]), "problems": problems}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 1 if problems else 0


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
    beats = beat_categories()

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
                     "launch": "\n".join([str(run_dir)] + chunk)})

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

GROUP_ORDER = ("topic-read", "beat-read", "topic-maybe", "beat-maybe")


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

    problems, placed = plan_problems(plan["items"], kept, known, rank)
    counts = {g: 0 for g in GROUP_ORDER}
    dropped = 0

    for index, it in enumerate(plan["items"]):
        verdict = (it.get("verdict") or "").upper()
        name = (it.get("profile") or "").strip()
        it["_rank"] = rank.get(name.lower()) if name else None
        it["_index"] = index
        it["_group"] = None
        if verdict in ("READ", "MAYBE"):
            it["_group"] = f"{'topic' if it['_rank'] else 'beat'}-{verdict.lower()}"
            counts[it["_group"]] += 1
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

    reads = sorted([it for it in plan["items"] if it["_group"] in ("topic-read", "beat-read")],
                   key=order)
    taken = reads[:READ_ITEMS_MAX]
    skipped_for_cap = [it.get("item_id") for it in reads[READ_ITEMS_MAX:]]

    maybes_taken = []
    if len(taken) < ITEM_FLOOR:
        allowed = min(ITEM_FLOOR - len(taken),
                      len(taken) * MAYBE_SHARE_MAX // 100)
        allowed = min(allowed, READ_ITEMS_MAX - len(taken))
        pool = sorted([it for it in plan["items"]
                       if it["_group"] in ("topic-maybe", "beat-maybe")], key=order)
        maybes_taken = pool[:max(0, allowed)]

    to_read, seen = [], set()
    for it in taken + maybes_taken:
        for aid in (it.get("read") or it.get("articles") or []):
            if aid in seen:
                continue
            seen.add(aid)
            to_read.append({"id": aid, "item": it.get("item_id"),
                            "group": it["_group"], "profile": it.get("profile") or None,
                            "primary": aid == it.get("primary")})
    write_json(run_dir / "items" / "read-list.json", {"read": to_read})

    for it in plan["items"]:
        for k in ("_rank", "_index", "_group"):
            it.pop(k, None)
    write_json(run_dir / "items" / "plan.json", plan)

    run = load_run(run_dir)
    run.setdefault("counts", {}).update(
        {"items": len(plan["items"]), "items_by_group": counts,
         "items_dropped": dropped, "items_taken": len(taken) + len(maybes_taken),
         "maybes_taken": len(maybes_taken), "to_read": len(to_read)})
    save_run(run_dir, run)

    print(json.dumps({"ok": True, "items": len(plan["items"]),
                      "by_group": counts, "dropped": dropped,
                      "read_items_max": READ_ITEMS_MAX,
                      "reads_taken": len(taken), "skipped_for_cap": skipped_for_cap,
                      "maybes_taken": len(maybes_taken),
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


def cmd_picks_sync(args):
    """Validate picks/picks.json against the ceilings, then trim to picks_max.

    Every ceiling here is a ceiling. A brief with two leads is right when only
    two stories deserve to lead, so nothing checks for a minimum.

    A reply over picks_max is not a failure: code trims it, discarding the
    smallest stories first. A LEAD is never trimmed. Among the rest, the pick
    whose news item holds the fewest articles goes first; ties fall to the
    lower group, then to the pick the agent ranked last. Trimmed picks move to
    a "trimmed" list in the file, so a re-run of this check is a no-op.

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
    notes = {f.stem for f in (run_dir / "notes").glob("*.md")}
    groups = {r["id"]: r.get("group") for r in
              ((load_json(run_dir / "items" / "read-list.json") or {}).get("read") or [])}

    problems, seen = [], set()
    counts = {t: 0 for t in TAGS}
    for it in p["picks"]:
        aid, tag = it.get("id"), (it.get("tag") or "").upper()
        if aid not in notes:
            problems.append(f"{aid}: picked but has no note")
        if aid in seen:
            problems.append(f"{aid}: picked twice")
        seen.add(aid)
        if tag not in TAGS:
            problems.append(f"{aid}: tag '{tag}' is not {SCHEMA['tag']['all']}")
        else:
            counts[tag] += 1
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
    if not problems and len(p["picks"]) > MAX_PICKS:
        if counts["LEAD"] > MAX_PICKS:
            die(f"{counts['LEAD']} LEAD picks but picks_max is {MAX_PICKS}; "
                "lead_max in settings.md must not exceed picks_max")
        items = (load_json(run_dir / "items" / "plan.json") or {}).get("items") or []
        item_of = {a: it for it in items for a in (it.get("articles") or [])}
        order = {it["id"]: i for i, it in enumerate(p["picks"])}

        def trim_key(it):
            n_articles = len(item_of.get(it["id"], {}).get("articles") or [it["id"]])
            g = groups.get(it["id"])
            g_rank = GROUP_ORDER.index(g) if g in GROUP_ORDER else len(GROUP_ORDER)
            return (n_articles, -g_rank, -order[it["id"]])

        cuttable = sorted((it for it in p["picks"]
                           if (it.get("tag") or "").upper() != "LEAD"), key=trim_key)
        for it in cuttable[:len(p["picks"]) - MAX_PICKS]:
            trimmed_now.append({
                "id": it["id"], "tag": (it.get("tag") or "").upper(),
                "articles": len(item_of.get(it["id"], {}).get("articles") or [it["id"]]),
                "reason": "trimmed by code: over picks_max, fewest articles first"})
        cut_ids = {t["id"] for t in trimmed_now}
        p["picks"] = [it for it in p["picks"] if it["id"] not in cut_ids]
        p["trimmed"] = p.get("trimmed", []) + trimmed_now
        write_json(run_dir / "picks" / "picks.json", p)
        log_event(run_dir, "picks_trimmed",
                  f"{len(trimmed_now)} trimmed to {MAX_PICKS}: "
                  + ", ".join(sorted(cut_ids)))
        seen = {it["id"] for it in p["picks"]}
        counts = {t: 0 for t in TAGS}
        for it in p["picks"]:
            counts[(it.get("tag") or "").upper()] += 1

    mix = {"topic": 0, "beat": 0, "maybe": 0}
    for aid in seen:
        g = groups.get(aid) or ""
        mix["maybe" if g.endswith("maybe") else
            ("topic" if g.startswith("topic") else "beat")] += 1

    data = load_run(run_dir)
    data["counts"].update({"picks": len(p["picks"]), "leads": counts["LEAD"],
                           "worth": counts["WORTH"], "body": counts["BODY"],
                           "picks_dropped": len(dropped), "picks_mix": mix,
                           "picks_trimmed": len(p.get("trimmed", []))})
    save_run(run_dir, data)
    print(json.dumps({"picks": len(p["picks"]), "by_tag": counts, "mix": mix,
                      "dropped": len(dropped),
                      "trimmed": sorted(t["id"] for t in p.get("trimmed", [])),
                      "leads": [i["id"] for i in p["picks"]
                                if (i.get("tag") or "").upper() == "LEAD"],
                      "problems": problems[:20]}, indent=2, ensure_ascii=False))
    return 1 if problems else 0


# ---------------------------------------------------------------- log, audit, close

def cmd_event(args):
    run_dir = run_dir_of(args)
    ev = log_event(run_dir, args.type, args.detail or "",
                   source=args.source, article=args.article,
                   retry=True if args.retry else None)
    print(json.dumps(ev, ensure_ascii=False))
    return 0


def build_audit_line(run_dir: Path) -> str:
    d = load_run(run_dir)
    c = d.get("counts", {})
    evs = d.get("events", [])
    retries = sum(1 for e in evs if e.get("retry"))
    failures = [e for e in evs if "fail" in e.get("type", "").lower()
                or e.get("type", "").lower() == "session_down"]
    cps = [f for f in (run_dir / "picks").glob("cp-*.md")
           if f.read_text(encoding="utf-8").strip() != "NONE"]
    und = {n: s["undated"] for n, s in d.get("sources", {}).items() if s.get("undated")}
    g = c
    mix = c.get("picks_mix", {})
    profile_built = d.get("profile_built") or "unknown date"
    undated_bit = f"{sum(und.values())} undated links dropped"
    if und:
        undated_bit += " (" + ", ".join(f"{n} {k}" for n, k in sorted(und.items())) + ")"
    bits = [
        f"{c.get('sources_ok', 0)} of {len(d.get('sources', {}))} sources screened",
        f"{c.get('screened', 0)} articles in window",
        undated_bit,
        f"{c.get('kept', 0)} kept at triage"
        + (f" ({c['kept_by_category']} by section, no agent)"
           if c.get("kept_by_category") else ""),
        f"{sum(g.get('items_by_group', {}).values())} news items "
        f"({g.get('items_by_group', {}).get('topic-read', 0)} on a current topic)",
        f"{c.get('notes', 0)} read",
        f"{c.get('notes_struck', 0)} notes with a figure removed",
        f"{c.get('picks', 0)} in the brief ({c.get('leads', 0)} leads, {c.get('worth', 0)} worth attention)",
        f"picks by group: {mix.get('topic', 0)} topic, {mix.get('beat', 0)} beat, "
        f"{mix.get('maybe', 0)} maybe",
        f"profile of {profile_built}",
        f"{len(cps)} counterpoints",
        f"{retries} retries",
        f"{len(failures)} failures",
    ]
    split = [e for e in evs if e.get("type") == "cluster_split"]
    if split:
        bits.append(f"clustered in {split[-1].get('detail') or 'parts'}")
    return "Audit: " + " · ".join(bits) + "."


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
    p.add_argument("--out")
    p.set_defaults(fn=cmd_fill)

    sub.add_parser("sources").set_defaults(fn=cmd_sources)

    p = sub.add_parser("start")
    p.add_argument("--slot", default="morning", choices=["morning"])
    p.set_defaults(fn=cmd_start)

    with_run(sub.add_parser("screen-sync")).set_defaults(fn=cmd_screen_sync)
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
