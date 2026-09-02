#!/usr/bin/env python3
"""Checks that the prompts and the code agree, without calling any model.

Two kinds of check:

1. Every placeholder a prompt contains is one SKILL.md says it fills, and every
   placeholder SKILL.md promises appears in its prompt. A prompt asking for
   something nobody fills is the one failure an agent cannot report, because it
   does not know what it was meant to receive.

2. The worked examples inside the prompts are run through the same validators the
   real replies go through. If an example in a prompt would be rejected by the
   script, the prompt is teaching an agent to fail.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "ybs-brief-v4"
PROMPTS = SKILL / "prompts"
SCRIPT = SKILL / "scripts" / "ybs_run.py"
FAILURES = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f" {detail}"))
    if not cond:
        FAILURES.append(f"{name} {detail}")


def run(*args):
    r = subprocess.run([sys.executable, str(SCRIPT)] + [str(a) for a in args],
                       capture_output=True, text=True, cwd=ROOT)
    try:
        return json.loads(r.stdout), r.returncode
    except json.JSONDecodeError:
        return r.stdout, r.returncode


def fresh_run():
    """A run id names the second it started in, so two starts in one second
    collide. Real runs never do; a suite making runs back to back can."""
    for attempt in range(4):
        out, code = run("start", "--slot", "morning")
        if code == 0:
            return Path(out["run_dir"])
        time.sleep(1.1)
    raise SystemExit("could not start a test run")


def placeholders(text):
    return set(re.findall(r"\{\{([A-Z_]+)\}\}", text))


# ------------------------------------------------------- 1. placeholders

# The variables `fill` builds from a run's own files. Everything else a prompt
# asks for must be a fragment, a setting or a schema name.
RUN_VARS = {
    "DATE", "SLOT", "RUN_DIR", "WINDOW_START", "WINDOW_END",
    "SOURCE_NAME", "SLUG", "SOURCE_URL", "MARKER", "MARKER_JSON", "SOURCE_JSON",
    "ARTICLES", "NOTES", "PICKS", "COUNTERPOINTS", "TEMPLATE",
    "PART_NOTE", "PART_ITEMS", "PARTS",
    "ARTICLE_ID", "WHAT_HAPPENED", "PRINCIPLE", "ANGLE", "ITEM_POOL",
    "AUDIT_LINE",
}

ANY_PLACEHOLDER = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_.-]*)\}\}")


def namespace_names():
    """Every name the script can fill, asked of the script itself."""
    names = {"BEATS", "LENS", "CRITERIA_FACTORS", "CRITERIA_LABELS", "CRITERIA_TAGS",
             "AGENT_RULES", "AGENT_RULES_BROWSER", "AGENT_RULES_JSON", "AGENT_RULES_FILE",
             "ITEM_SHAPE", "PRINCIPLES",
             "PROFILE", "PROFILE_MOVES", "PROFILE_DATE", "PROFILE_SHOWS"}
    settings, _ = run("settings")
    names |= {f"settings.{k}" for k in settings}
    schema, _ = run("schema")
    for group, entries in schema.items():
        names |= {f"schema.{group}.{k}" for k in entries}
    return names


def test_placeholders():
    print("\nplaceholders")
    known = namespace_names() | RUN_VARS

    for f in sorted(PROMPTS.glob("*.md")):
        if f.name.startswith("_"):
            check(f"{f.name} is pasted verbatim, so holds no placeholders",
                  not ANY_PLACEHOLDER.findall(f.read_text()))
            continue
        unknown = set(ANY_PLACEHOLDER.findall(f.read_text())) - known
        check(f"{f.name}: every placeholder is one the script can fill",
              not unknown, f"nothing provides {sorted(unknown)}")

    tpl = (SKILL / "templates" / "morning.md").read_text()
    unknown = set(ANY_PLACEHOLDER.findall(tpl)) - known
    check("morning.md: every placeholder is one the script can fill", not unknown,
          f"nothing provides {sorted(unknown)}")
    check("morning.md carries the audit-line placeholder", "{{AUDIT_LINE}}" in tpl)

    # The template is the only statement of the brief's shape, and write.md the
    # only statement of its sentences. Neither may drift into the other's job.
    wr = (SKILL / "prompts" / "write.md").read_text()
    for s in ("What leads", "Secondary Topics", "Worth Yaron", "COUNTERPOINT -",
              "AUDIT_LINE"):
        check(f"write.md does not restate the shape ({s})", s not in wr)
    for s in ("words", "clause", "dash", "semicolon", "metaphor"):
        check(f"morning.md carries no sentence rule ({s})", s not in tpl)


def test_agent_files_are_generated():
    print("\nagent files are rendered, not written twice")
    out, code = run("build", "--check")
    check("every ybs4-*.md matches its template", code == 0,
          f"stale: {out.get('stale') if isinstance(out, dict) else out}")
    for f in sorted((ROOT / ".claude" / "agents").glob("ybs4-*.md")):
        if f.stem.startswith("ybs4-shows-"):
            continue                      # hand-written, and /ybs-shows owns them
        lines = f.read_text().splitlines()
        # Claude Code loads the frontmatter only when `---` is the very first
        # line, so the generated-file banner must sit below it, never above.
        check(f"{f.name} opens with its frontmatter", bool(lines) and lines[0] == "---")
        close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        after = lines[close + 1] if close is not None and close + 1 < len(lines) else ""
        check(f"{f.name} says it is generated, below the frontmatter",
              "Generated by ybs_run.py build" in after, f"line after the frontmatter: {after!r}")
    for t in sorted((SKILL / "agents").glob("*.md.tmpl")):
        left = set(ANY_PLACEHOLDER.findall(t.read_text())) & RUN_VARS
        check(f"{t.name} asks for no run data", not left, f"asks for {sorted(left)}")


SHINGLE = 12          # words; long enough that a shared run of them is a copy


def prose_sources():
    """Every file a person edits by hand. Rendered agent files are excluded:
    they are copies by design, which is what `build` is for."""
    files = [SKILL / "SKILL.md", SKILL / "settings.md"]
    files += sorted(PROMPTS.glob("*.md"))
    files += sorted((SKILL / "templates").glob("*.md"))
    files += sorted((SKILL / "agents").glob("*.md.tmpl"))
    return [f for f in files if f.exists()]


def strip_frontmatter(text):
    """An agent's --- block is per-agent configuration, not prose."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5:]
    return text


def shingles(text):
    """Runs of SHINGLE words, ignoring fenced blocks and placeholders."""
    out, fenced = {}, False
    words = []
    for line in strip_frontmatter(text).splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
            words = []
            continue
        if fenced or line.strip().startswith("|"):
            continue
        line = ANY_PLACEHOLDER.sub(" ", line)
        line = re.sub(r"[^a-z0-9 ]+", " ", line.lower())
        words += line.split()
    for i in range(len(words) - SHINGLE + 1):
        out.setdefault(" ".join(words[i:i + SHINGLE]), i)
    return set(out)


def test_nothing_is_said_twice():
    print("\nevery fact has one home")
    seen, clashes = {}, []
    for f in prose_sources():
        for sh in shingles(f.read_text()):
            if sh in seen and seen[sh] != f.name:
                clashes.append((seen[sh], f.name, sh))
            else:
                seen.setdefault(sh, f.name)
    shown = clashes[:8]
    check("no two files say the same thing", not clashes,
          "; ".join(f"{a} and {b}: '{t[:60]}...'" for a, b, t in shown) +
          (f" (+{len(clashes) - len(shown)} more)" if len(clashes) > len(shown) else ""))


def test_numbers_live_in_settings():
    print("\nevery number has one home")
    # Every integer setting of two digits or more, longest first so that 150
    # is matched whole and never as 15 or 50.
    settings, _ = run("settings")
    values = sorted({str(v) for v in settings.values() if isinstance(v, int) and v >= 10},
                    key=len, reverse=True)
    number_in_prose = re.compile(r"(?<![\w.$])(" + "|".join(values) + r")(?![\w%.])")
    for f in prose_sources():
        if f.name == "settings.md":
            continue
        hits, fenced = [], False
        for line in f.read_text().splitlines():
            if line.strip().startswith("```"):
                fenced = not fenced
                continue
            if fenced or line.strip().startswith("|"):
                continue
            if line.lstrip().startswith("#"):
                continue                      # a heading, e.g. "## Step 10"
            line = re.sub(r"^\s*\d+\.", "", line)   # an ordered-list marker
            line = ANY_PLACEHOLDER.sub(" ", line)
            hits += number_in_prose.findall(line)
        check(f"{f.name} states no setting of its own", not hits,
              f"found {sorted(set(hits))}; use a {{{{settings.*}}}} placeholder")


def test_shared_fragments():
    print("\nshared fragments")
    for name in ("_beats.md", "_lens.md"):
        t = (PROMPTS / name).read_text()
        check(f"{name} has no html comment", "<!--" not in t)
        check(f"{name} has no heading", not any(l.startswith("#") for l in t.splitlines()))
        check(f"{name} is not empty", len(t.strip()) > 200)
    beats = (PROMPTS / "_beats.md").read_text().lower()
    for word in ("national security", "objectivism", "immigration", "israel"):
        check(f"_beats.md still covers {word!r}", word in beats)


def test_agents_match_skill():
    print("\nagents")
    # The brief's own agents. ybs4-shows-* belong to /ybs-shows and are checked
    # by that skill's suite.
    agents = {f.stem: f.read_text()
              for f in (ROOT / ".claude" / "agents").glob("ybs4-*.md")
              if not f.stem.startswith("ybs4-shows-")}
    skill = (SKILL / "SKILL.md").read_text()
    for name, body in sorted(agents.items()):
        check(f"{name} declares a model", re.search(r"^model:\s*\S+", body, re.M) is not None)
        check(f"{name} declares an effort", re.search(r"^effort:\s*\S+", body, re.M) is not None)
        check(f"{name} is used by SKILL.md", name in skill)
    check("SKILL.md sets no model inline",
          not re.search(r"model\s*[:=]\s*[\"']?(haiku|sonnet|opus)", skill, re.I))

    # v3: the three fan-out agents carry their own instructions, so a launch is
    # one line. These checks are what stop that quietly rotting back.
    want = {"ybs4-screener": ("haiku", "low"), "ybs4-triage": ("sonnet", "low"),
            "ybs4-cluster": ("opus", "high"), "ybs4-reader": ("sonnet", "medium"),
            "ybs4-checker": ("haiku", "low"), "ybs4-pick": ("opus", "high"),
            "ybs4-counterpoint": ("opus", "high"), "ybs4-write": ("opus", "high")}
    for name, (model, effort) in sorted(want.items()):
        body = agents.get(name, "")
        got = (re.search(r"^model:\s*(\S+)", body, re.M),
               re.search(r"^effort:\s*(\S+)", body, re.M))
        check(f"{name} is {model}/{effort}",
              bool(got[0]) and got[0].group(1) == model
              and bool(got[1]) and got[1].group(1) == effort,
              f"got {got[0] and got[0].group(1)}/{got[1] and got[1].group(1)}")

    for name in ("ybs4-triage", "ybs4-reader", "ybs4-checker"):
        body = agents.get(name, "")
        deny = re.search(r"^disallowedTools:(.*)$", body, re.M)
        deny = {t.strip() for t in (deny.group(1) if deny else "").split(",")}
        check(f"{name} may use Write (it writes its own result file)",
              "Write" not in deny, ", ".join(sorted(deny))[:80])
        check(f"{name} takes a one-line launch, not a filled prompt",
              "{{" not in body)
    check("triage and checker still cannot run Bash",
          all("Bash" in re.search(r"^disallowedTools:(.*)$", agents[n], re.M).group(1)
              for n in ("ybs4-triage", "ybs4-checker")))
    check("the counterpoint agent cannot search the web",
          all(t in re.search(r"^disallowedTools:(.*)$",
                             agents["ybs4-counterpoint"], re.M).group(1)
              for t in ("WebSearch", "WebFetch")))
    check("the counterpoint agent may write its own file",
          "Write" not in {t.strip() for t in re.search(
              r"^disallowedTools:(.*)$", agents["ybs4-counterpoint"], re.M
          ).group(1).split(",")})

    beats = (PROMPTS / "_beats.md").read_text().strip()
    lens = (PROMPTS / "_lens.md").read_text().strip()
    check("ybs4-triage carries _beats.md verbatim", beats in agents.get("ybs4-triage", ""))
    check("ybs4-reader carries _lens.md verbatim", lens in agents.get("ybs4-reader", ""))
    check("ybs4-reader can report a truncated page",
          "PAGE_TRUNCATED" in agents.get("ybs4-reader", ""))
    check("ybs4-checker has a word for a note with no figures",
          "no figures" in agents.get("ybs4-checker", ""))
    for gone in ("triage.md", "reader.md", "figure-check.md"):
        check(f"{gone} is not a v3 prompt (it lives in the agent)",
              not (PROMPTS / gone).exists())


# ------------------------------------------------------- 2. worked examples

def json_examples(path):
    """Every ```json fenced block in a prompt."""
    return re.findall(r"```json\n(.*?)```", path.read_text(), re.S)


def test_examples_are_valid_json():
    print("\nworked examples parse")
    for f in sorted(PROMPTS.glob("*.md")):
        if f.name == "README.md":
            continue
        for i, block in enumerate(json_examples(f), 1):
            try:
                json.loads(block)
                check(f"{f.name} example {i} is valid JSON", True)
            except json.JSONDecodeError as e:
                check(f"{f.name} example {i} is valid JSON", False, str(e)[:80])


def in_window():
    """v3 drops a link with no date, so the fixture needs a real one."""
    return (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")


def plan_example_through_items_sync(prompt, run_dir):
    """Run a prompt's worked-example plan through items-sync on a fresh run."""
    ex = json_examples(PROMPTS / prompt)
    if not ex:
        check(f"{prompt} has a worked example", False)
        return None, 1
    plan = json.loads(ex[0])
    ids = sorted({a for it in plan["items"] for a in it["articles"]})

    (run_dir / "screen" / "guardian.json").write_text(json.dumps({
        "source": "Guardian", "ok": True,
        "links": [{"url": f"https://www.theguardian.com/x/{i}", "title": f"story {i}",
                   "description": "d", "category": "World",
                   "published": in_window()} for i in ids]}))
    run("screen-sync", "--run", run_dir)
    real = [a["id"] for a in json.loads((run_dir / "articles.json").read_text())["articles"]]
    swap = dict(zip(ids, real))

    text = json.dumps(plan)
    for old, new in swap.items():
        text = text.replace(f'"{old}"', f'"{new}"')
    plan = json.loads(text)

    run("triage-list", "--run", run_dir)
    for a in real:
        (run_dir / "triage" / f"{a}.verdict.txt").write_text(f"{a} keep\n")
    run("triage-check", "--run", run_dir)

    (run_dir / "items" / "plan.json").write_text(json.dumps(plan))
    return run("items-sync", "--run", run_dir)


def test_cluster_example_passes_items_sync(run_dir):
    print("\ncluster example survives items-sync")
    out, code = plan_example_through_items_sync("cluster-select.md", run_dir)
    check("the example plan is accepted by items-sync", code == 0,
          str(out.get("problems") if isinstance(out, dict) else out)[:200])
    check("the example's items land in the groups the profile implies",
          isinstance(out, dict) and out["by_group"]["topic-read"] >= 1
          and out["by_group"]["topic-maybe"] >= 1, str(out)[:200])
    # Two READ items are taken, and the cluster among them reads two accounts,
    # so three articles come from the READs and the taken MAYBE adds its one.
    check("under the floor, the script takes the MAYBE the agent labelled",
          isinstance(out, dict) and out["maybes_taken"] == 1
          and out["articles_to_read"] == 4, str(out)[:300])


def test_merge_example_passes_items_sync(run_dir):
    print("\nmerge example survives items-sync")
    out, code = plan_example_through_items_sync("cluster-merge.md", run_dir)
    check("the merged example plan is accepted by items-sync", code == 0,
          str(out.get("problems") if isinstance(out, dict) else out)[:200])


def test_pick_example_passes_picks_sync(run_dir):
    print("\npick example survives picks-sync")
    ex = json_examples(PROMPTS / "pick.md")
    if not ex:
        return check("pick.md has a worked example", False)
    picks = json.loads(ex[0])
    ids = [p["id"] for p in picks["picks"]] + [d["id"] for d in picks["dropped"]]
    for f in (run_dir / "notes").glob("*.md"):
        f.unlink()
    for aid in ids:
        (run_dir / "notes" / f"{aid}.md").write_text(f"HEADLINE: {aid}\n")
    (run_dir / "picks" / "picks.json").write_text(json.dumps(picks))
    out, code = run("picks-sync", "--run", run_dir)
    # The example deliberately shows only 3 LEAD and 1 WORTH, so it must fail on
    # the WORTH count and on nothing else. That is what makes it a good example:
    # it shows the shape without pretending to be a whole day.
    probs = out.get("problems", []) if isinstance(out, dict) else []
    check("the example's shape is accepted (tags, ids, reasons all valid)",
          all("WORTH" in p for p in probs), str(probs)[:200])


def main():
    print("prompt/code agreement")
    test_placeholders()
    test_shared_fragments()
    test_nothing_is_said_twice()
    test_numbers_live_in_settings()
    test_agent_files_are_generated()
    test_agents_match_skill()
    test_examples_are_valid_json()

    run_dir = fresh_run()
    try:
        test_cluster_example_passes_items_sync(run_dir)
        test_pick_example_passes_picks_sync(run_dir)
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)

    run_dir = fresh_run()                            # a second run: ids are frozen per run
    try:
        test_merge_example_passes_items_sync(run_dir)
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED")
        for f in FAILURES:
            print("  - " + f)
        return 1
    print("all passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
