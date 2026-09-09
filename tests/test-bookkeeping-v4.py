#!/usr/bin/env python3
"""Unit tests for ybs_run.py. No network, no agents, no browser.

Every test builds a run folder, writes the JSON an agent would have produced --
correct in one case, deliberately broken in the next -- and asserts the script
either accepts it or names the exact problem. Exit 0 = all passed.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".claude" / "skills" / "ybs-brief" / "scripts" / "ybs_run.py"
FAILURES = []


def run(*args, expect=None, env=None):
    r = subprocess.run([sys.executable, str(SCRIPT)] + [str(a) for a in args],
                       capture_output=True, text=True, cwd=ROOT,
                       env={**os.environ, **env} if env else None)
    if expect is not None and r.returncode != expect:
        FAILURES.append(f"{' '.join(str(a) for a in args[:2])}: exit {r.returncode}, "
                        f"expected {expect}\n    {r.stderr.strip()[:200]}")
    try:
        return json.loads(r.stdout), r
    except json.JSONDecodeError:
        return r.stdout, r


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAILURES.append(f"{name} {detail}")


def has(out, needle):
    return any(needle in p for p in out.get("problems", []))


def live_topic():
    """A storyline name from the live profile. items-sync matches names exactly
    and /ybs-shows rewrites the profile, so a hard-coded name rots."""
    profile = json.loads((ROOT / "shows" / "profile.json").read_text())
    return profile["storylines"][0]["name"]


def new_run():
    """A run id names the second it started in, so two runs in the same second
    collide. Real runs never do; a test making several in a row does."""
    for attempt in range(4):
        r = subprocess.run([sys.executable, str(SCRIPT), "start", "--slot", "morning"],
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode == 0:
            return Path(json.loads(r.stdout)["run_dir"])
        if "already exists" not in r.stderr:
            FAILURES.append(f"start: exit {r.returncode}\n    {r.stderr.strip()[:200]}")
            break
        time.sleep(1.1)
    raise SystemExit("could not start a test run")


def now_iso(offset_hours=0):
    return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


NO_DATE = object()          # a link the front page gave no date for


def link(url, title, desc="a description long enough to matter", cat="world", pub=None):
    return {"url": url, "title": title, "description": desc, "category": cat,
            "published": None if pub is NO_DATE else (pub or now_iso(-1))}


# ---------------------------------------------------------------- tests

def test_screen_sync(rd):
    print("\nscreen-sync")
    write(rd / "screen" / "guardian.json", {"source": "Guardian", "ok": True, "links": [
        link("https://www.theguardian.com/world/2026/x/a", "A"),
        link("https://www.theguardian.com/world/2026/x/b", "B"),
        link("https://www.theguardian.com/world/2026/x/b?utm=1", "B again"),   # duplicate
        link("https://www.theguardian.com/world/2026/x/old", "Old", pub=now_iso(-96)),
        link("https://www.theguardian.com/world/2026/x/d", "D"),
        link("https://www.theguardian.com/world/2026/x/undated", "Undated", pub=NO_DATE),
    ]})
    write(rd / "screen" / "reason.json", {"source": "Reason", "ok": True, "links": [
        link("https://reason.com/2026/x/c", "C", cat="policy"),
    ]})
    write(rd / "screen" / "ap-news.json", {"source": "AP News", "ok": False,
                                           "error": "TIMEOUT", "links": []})
    out, _ = run("screen-sync", "--run", rd)
    check("keeps in-window, drops stale and undated", out["articles"] == 4,
          f"got {out['articles']}")
    check("merges the duplicate url", out["duplicates_merged"] == 1)
    check("drops the undated link", out["undated_dropped"] == 1)
    check("counts undated per source", out["undated_by_source"] == {"Guardian": 1},
          str(out.get("undated_by_source")))
    check("records undated on the source record",
          json.loads((rd / "run.json").read_text())["sources"]["Guardian"]["undated"] == 1)
    check("reports the failed source", any("AP News" in p for p in out["problems"]))
    ids = [a["id"] for a in json.loads((rd / "articles.json").read_text())["articles"]]
    check("assigns stable ids", ids == ["a001", "a002", "a003", "a004"], str(ids))


def build_morning(root, run_id, started, status="completed", links=(), picks=()):
    """One morning run, written by hand, inside a runs folder of a test's own.

    Enough of a finished run for an afternoon one to follow it: the record, the
    articles it screened and, when `picks` names any, the stories its brief ran
    with a note each. Those notes are what the update reads back.
    """
    d = root / run_id
    for sub in ("screen", "triage", "items", "pages", "notes", "checks", "picks"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    write(d / "run.json", {
        "run_id": run_id, "slot": "morning",
        "local_date": datetime.now().strftime("%Y-%m-%d"),
        "window_start_utc": now_iso(-8), "window_end_utc": started,
        "started_utc": started, "completed_utc": started,
        "status": status, "sources": {}, "counts": {}, "events": []})
    write(d / "articles.json", {"articles": [
        {"id": f"a{i:03d}", "source": "Guardian", "url": u, "title": "t",
         "description": "d", "category": "world", "published": started,
         "also_in": []} for i, u in enumerate(links, 1)]})
    if picks:
        write(d / "picks" / "picks.json",
              {"picks": [{"id": a, "tag": "LEAD", "why": "it led"} for a in picks],
               "dropped": []})
        for a in picks:
            (d / "notes" / f"{a}.md").write_text(
                f"HEADLINE: the morning's story {a}\n"
                f"WHAT HAPPENED: what {a} established at ten\n"
                f"WHAT'S NEW: what {a} carried at ten\n", encoding="utf-8")
    return d


def test_afternoon_base():
    """The afternoon is an update of one named morning brief.

    `start --slot afternoon` refuses without one, records the one it found, and
    `screen-sync` then drops every link that morning already screened. The whole
    test runs inside a runs folder of its own, named by YBS_RUNS_DIR, so it
    neither sees nor leaves anything among the real runs.
    """
    print("\nstart --slot afternoon: the base run")
    tmp = Path(tempfile.mkdtemp(prefix="ybs-runs-"))
    env = {"YBS_RUNS_DIR": str(tmp)}
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        _, r = run("start", "--slot", "afternoon", expect=2, env=env)
        check("with no morning run today, the afternoon refuses to start",
              "no morning brief to update" in r.stderr, r.stderr.strip()[:200])
        check("and says exactly what it looked for",
              today in r.stderr and "slot morning" in r.stderr
              and "status completed" in r.stderr, r.stderr.strip()[:240])

        # A morning run of today, finished. Two of them: the later one wins.
        def morning(run_id, started, status="completed", links=()):
            return build_morning(tmp, run_id, started, status, links)

        early = morning("2026-x_morning_080000", now_iso(-4),
                        links=["https://www.theguardian.com/x/early"])
        late = morning("2026-x_morning_100000", now_iso(-2), links=[
            "https://www.theguardian.com/world/2026/x/a",
            "https://reason.com/2026/x/c"])
        unfinished = morning("2026-x_morning_110000", now_iso(-1),
                             status="running")

        out, _ = run("start", "--slot", "afternoon", expect=0, env=env)
        rd = Path(out["run_dir"])
        base = out["base"]
        check("it finds the latest completed morning run of today",
              base["run_dir"] == str(late), str(base))
        check("an unfinished morning run is not taken",
              base["run_dir"] != str(unfinished), str(base))
        check("the base carries the run id and the morning's window end",
              base["run_id"] == "2026-x_morning_100000"
              and base["window_end_utc"] == json.loads(
                  (late / "run.json").read_text())["window_end_utc"], str(base))
        check("and the time the morning template puts on its brief",
              base["time"] == "10:00", str(base.get("time")))
        check("run.json records the same base",
              json.loads((rd / "run.json").read_text())["base"] == base)

        _, r = run("start", "--slot", "afternoon", "--base", unfinished,
                   expect=2, env=env)
        check("--base refuses a morning run that never completed",
              "completed" in r.stderr and unfinished.name in r.stderr,
              r.stderr.strip()[:200])

        time.sleep(1.1)          # a run id names the second it started in
        out, _ = run("start", "--slot", "afternoon", "--base", early,
                     expect=0, env=env)
        rd2 = Path(out["run_dir"])
        check("--base takes the run it names, not the latest",
              Path(out["base"]["run_dir"]) == early.resolve(), str(out["base"]))

        # screen-sync on the afternoon run: the base's two URLs are gone, and
        # what neither the morning nor another source had is kept.
        write(rd / "screen" / "guardian.json", {
            "source": "Guardian", "ok": True, "links": [
                link("https://www.theguardian.com/world/2026/x/a", "Seen at ten"),
                link("https://www.theguardian.com/world/2026/x/new", "New at four"),
            ]})
        write(rd / "screen" / "reason.json", {
            "source": "Reason", "ok": True, "links": [
                link("https://reason.com/2026/x/c?utm=1", "Seen at ten too"),
                link("https://reason.com/2026/x/fresh", "Fresh"),
            ]})
        out, _ = run("screen-sync", "--run", rd)
        check("what the morning screened is dropped, the rest kept",
              out["articles"] == 2, str(out["articles"]))
        check("the drops are counted in total", out["seen_this_morning"] == 2,
              str(out.get("seen_this_morning")))
        check("and per source",
              out["seen_by_source"] == {"Guardian": 1, "Reason": 1},
              str(out.get("seen_by_source")))
        check("the source record carries the count beside undated",
              json.loads((rd / "run.json").read_text())["sources"]["Reason"]
              ["seen_this_morning"] == 1)
        urls = [a["url"] for a in
                json.loads((rd / "articles.json").read_text())["articles"]]
        check("the two survivors are the ones the morning never had",
              sorted(urls) == ["https://reason.com/2026/x/fresh",
                               "https://www.theguardian.com/world/2026/x/new"],
              str(urls))
        check("the other afternoon run is untouched",
              not (rd2 / "articles.json").exists())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_screen_attempts():
    """Two screens of one source at the same time is the failure this guards.

    `fill screen` records an attempt before it hands anyone a prompt, and a
    second prompt for the same slug is refused until that attempt is provably
    over: either its file is on disk, or it has outlived the command's own
    timeout. Nothing here runs a browser; the files a screener would have
    written are written by hand.
    """
    print("\nfill screen: one attempt at a time")
    settings = json.loads(subprocess.run(
        [sys.executable, str(SCRIPT), "settings"], capture_output=True,
        text=True, cwd=ROOT).stdout)
    timeout = settings["screen_timeout_seconds"]
    rd = new_run()
    slug = "guardian"
    rec = rd / "screen" / f"{slug}.attempt.json"
    try:
        out, _ = run("fill", "screen", "--run", rd, "--source", slug, expect=0)
        check("the first fill is attempt 1", out.get("attempt") == 1, str(out)[:120])
        check("and records the attempt as open",
              rec.exists() and json.loads(rec.read_text())["done"] is False)

        _, r = run("fill", "screen", "--run", rd, "--source", slug, expect=1)
        check("a second fill without --retry is refused",
              slug in r.stderr and "--retry" in r.stderr, r.stderr.strip()[:160])

        _, r = run("fill", "screen", "--run", rd, "--source", slug, "--retry", expect=1)
        check("--retry while the first attempt is young says how long to wait",
              "may still be fetching" in r.stderr or "Wait" in r.stderr,
              r.stderr.strip()[:160])

        # The screener finishes: its file carries the attempt it belongs to.
        write(rd / "screen" / f"{slug}.json",
              {"source": "Guardian", "ok": True, "attempt": 1, "seconds": 61,
               "links": []})
        out, _ = run("fill", "screen", "--run", rd, "--source", slug, "--retry",
                     expect=0)
        check("--retry after the matching file lands is attempt 2",
              out.get("attempt") == 2, str(out)[:120])
        check("and the retry gets a task space of its own",
              out.get("task_space") == f"ybs screen {slug} a2",
              str(out.get("task_space")))
        first = (rd / "prompts" / f"screen-{slug}.md").read_text()
        second = Path(out["file"]).read_text()
        check("the two prompts name two different task spaces",
              f"ybs screen {slug} a1" in first and f"ybs screen {slug} a2" in second)
        check("and the retry is a file of its own", out["file"] != str(
            rd / "prompts" / f"screen-{slug}.md"))
    finally:
        shutil.rmtree(rd, ignore_errors=True)

    print("\nfill screen: an attempt that outlived its own timeout")
    rd = new_run()
    slug = "reason"
    rec = rd / "screen" / f"{slug}.attempt.json"
    try:
        run("fill", "screen", "--run", rd, "--source", slug, expect=0)
        old = json.loads(rec.read_text())
        old["started_utc"] = now_iso(-(timeout + 120) / 3600.0)
        rec.write_text(json.dumps(old))
        out, _ = run("fill", "screen", "--run", rd, "--source", slug, "--retry",
                     expect=0)
        check("past the timeout and the grace, --retry goes ahead with no file",
              out.get("attempt") == 2, str(out)[:120])
    finally:
        shutil.rmtree(rd, ignore_errors=True)

    print("\nfill --retry belongs to screen alone")
    rd = new_run()
    try:
        _, r = run("fill", "pick", "--run", rd, "--retry", expect=2)
        check("--retry on another prompt is a usage error",
              "only for screen" in r.stderr, r.stderr.strip()[:120])
    finally:
        shutil.rmtree(rd, ignore_errors=True)


def test_screen_stragglers():
    """A first attempt that finishes after its retry did must not win."""
    print("\nscreen-sync: the straggler loses")
    rd = new_run()
    try:
        write(rd / "screen" / "guardian.attempt.json",
              {"slug": "guardian", "attempt": 2, "started_utc": now_iso(),
               "done": False})
        write(rd / "screen" / "guardian.json", {
            "source": "Guardian", "ok": True, "attempt": 1, "seconds": 274,
            "links": [link("https://www.theguardian.com/world/2026/x/late", "Late")]})
        write(rd / "screen" / "reason.json", {
            "source": "Reason", "ok": True, "seconds": 40,
            "links": [link("https://reason.com/2026/x/c", "C")]})
        out, _ = run("screen-sync", "--run", rd)
        check("the older attempt's file is ignored",
              out["stale"].get("Guardian") == {"file_attempt": 1, "latest_attempt": 2},
              str(out.get("stale")))
        check("and screen-sync says so in its problems",
              any("Guardian" in p and "attempt" in p for p in out["problems"]),
              str(out["problems"])[:160])
        check("a file with no attempt number is still read as the first one",
              out["articles"] == 1, f"got {out['articles']}")

        # The retry lands: its file matches the record, and the record closes.
        write(rd / "screen" / "guardian.json", {
            "source": "Guardian", "ok": True, "attempt": 2, "seconds": 54,
            "links": [link("https://www.theguardian.com/world/2026/x/a", "A")]})
        (rd / "articles.json").unlink()
        out, _ = run("screen-sync", "--run", rd)
        check("the matching attempt is taken", out["stale"] == {} and
              out["articles"] == 2, str(out)[:160])
        check("and screen-sync marks the attempt done",
              json.loads((rd / "screen" / "guardian.attempt.json").read_text())
              ["done"] is True)
    finally:
        shutil.rmtree(rd, ignore_errors=True)


def test_screen_prompt_is_safe_to_retry():
    """The rendered command, not the prose: the four things it must now do."""
    print("\nthe rendered screen command")
    rd = new_run()
    try:
        out, _ = run("fill", "screen", "--run", rd, "--source", "bbc", expect=0)
        text = Path(out["file"]).read_text()
        for name, needle in (("writes to a .tmp file first", "OUT + '.tmp'"),
                             ("renames it into place", "fs.renameSync"),
                             ("tries a failed fetch a second time", "go < 2"),
                             ("waits before the next url after an error", "backoff = 1000"),
                             ("carries its own deadline", "DEADLINE"),
                             ("puts the attempt in the file", "attempt: ATTEMPT"),
                             ("names its own task space", "ybs screen bbc a1")):
            check(f"it {name}", needle in text)
        check("no placeholder is left unfilled", out["unfilled"] == [], str(out))
    finally:
        shutil.rmtree(rd, ignore_errors=True)


def test_dates():
    """The three date shapes a screener can hand over besides a timestamp: a
    <time datetime> without seconds, a Guardian-style /2026/aug/24/ URL date,
    and a bare date. A bare date has no clock, so it counts as in window when
    it is today's local date, wherever on the globe the machine is."""
    print("\nscreen-sync: date shapes")
    rd = new_run()
    try:
        now = datetime.now(timezone.utc)
        today = datetime.now().strftime("%Y-%b-%d").lower()
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        write(rd / "screen" / "guardian.json", {"source": "Guardian", "ok": True, "links": [
            link("https://www.theguardian.com/x/no-seconds", "No seconds",
                 pub=(now - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M")),
            link("https://www.theguardian.com/x/month-name", "Month name", pub=today),
            link("https://www.theguardian.com/x/yesterday", "Yesterday", pub=yesterday),
            link("https://www.theguardian.com/x/undated", "Undated", pub=NO_DATE),
        ]})
        out, _ = run("screen-sync", "--run", rd)
        check("a datetime without seconds and a month-name date of today both count",
              out["articles"] == 2, str(out))
        check("yesterday's bare date is out, the undated link is undated",
              out["undated_dropped"] == 1, str(out))
    finally:
        shutil.rmtree(rd, ignore_errors=True)


def test_triage(rd):
    """A batch of articles per agent, one verdict file each."""
    print("\ntriage")
    settings, _ = run("settings", expect=0)
    batch = settings["triage_batch_size"]
    out, _ = run("triage-list", "--run", rd, expect=0)
    check("batches every article, none done yet",
          out["todo"] and sum(len(e["ids"]) for e in out["todo"]) == 4
          and out["done"] == 0, str(out.get("done")))
    check("no batch is over the ceiling in settings.md",
          all(len(e["ids"]) <= batch for e in out["todo"]),
          str([len(e["ids"]) for e in out["todo"]]))
    check("says which batch size it used", out["batch_size"] == batch, str(out))
    check("none of these sections is on beat, so no agent was skipped",
          out["admitted_by_category"] == 0, str(out))
    check("freezes the id list", (rd / "triage" / "todo.json").exists())
    launch = out["todo"][0]["launch"]
    head, *rows = launch.splitlines()
    check("the block opens with the run directory", head == str(rd), head[:120])
    check("one row per article in the batch",
          len(rows) == len(out["todo"][0]["ids"]), launch[:160])
    check("a row carries id, source, category and title",
          rows[0].startswith("a001 | ") and "[Guardian]" in rows[0]
          and "(world)" in rows[0], rows[0][:120])
    check("a row has no pipe from the article text",
          rows[0].count("|") == 1, rows[0][:120])

    out, r = run("fill", "cluster-select", "--run", rd, expect=2)
    check("the cluster prompt cannot be filled before triage-check",
          r.returncode == 2 and "verdicts.json" in r.stderr, r.stderr[:120])

    (rd / "triage" / "a001.verdict.txt").write_text("a001 keep\n")
    (rd / "triage" / "a002.verdict.txt").write_text("a002 drop\n")
    out, _ = run("triage-check", "--run", rd, expect=1)
    check("names the articles with no verdict", set(out["missing"]) == {"a003", "a004"},
          str(out["missing"]))

    out, _ = run("triage-list", "--run", rd, expect=0)
    check("re-listing skips what is already judged",
          sum(len(e["ids"]) for e in out["todo"]) == 2 and out["done"] == 2,
          str(out["done"]))

    (rd / "triage" / "a003.verdict.txt").write_text("a001 keep\n")
    (rd / "triage" / "a004.verdict.txt").write_text("a004 maybe\n")
    out, _ = run("triage-check", "--run", rd, expect=1)
    probs = {f["id"]: f["problem"] for f in out["failing"]}
    check("catches a verdict naming another article", "names a001" in probs.get("a003", ""))
    check("catches the bad word", "not keep or drop" in probs.get("a004", ""))

    (rd / "triage" / "a003.verdict.txt").write_text("a003 keep\na003 keep\n")
    out, _ = run("triage-check", "--run", rd, expect=1)
    probs = {f["id"]: f["problem"] for f in out["failing"]}
    check("catches a two-line verdict", probs.get("a003") == "more than one line")

    (rd / "triage" / "a003.verdict.txt").write_text("a003 keep\n")
    (rd / "triage" / "a004.verdict.txt").unlink()
    out, _ = run("triage-check", "--run", rd, "--give-up", "a004", expect=0)
    check("giving up on one article keeps it", out["kept"] == 3 and out["dropped"] == 1)

    out, _ = run("triage-check", "--run", rd, expect=0)
    check("the give-up survives the next triage-check",
          out["kept"] == 3 and not out["missing"], str(out))
    out, _ = run("triage-list", "--run", rd, expect=0)
    check("a given-up article is not listed again", out["done"] == 4 and not out["todo"],
          str(out.get("todo")))
    out, _ = run("fill", "cluster-select", "--run", rd, expect=0)
    text = Path(out["file"]).read_text() if isinstance(out, dict) else ""
    check("the cluster prompt lists every kept article, the given-up one included",
          "\na001 [" in text and "\na003 [" in text and "\na004 [" in text,
          str(out)[:200])
    check("and none that was dropped at triage", text and "\na002 [" not in text)

    # The bug this guards against: a second give-up used to erase the first,
    # because verdicts.json was rebuilt from the files alone every time.
    (rd / "triage" / "a003.verdict.txt").unlink()
    out, _ = run("triage-check", "--run", rd, "--give-up", "a003", expect=0)
    check("a second give-up does not erase the first",
          out["kept"] == 3 and not out["missing"], str(out))
    run("triage-check", "--run", rd, "--give-up", "a004", expect=0)
    events = [e["article"] for e in json.loads((rd / "run.json").read_text())["events"]
              if e["type"] == "triage_gave_up"]
    check("one give-up event per article, however often it is repeated",
          events == ["a004", "a003"], str(events))
    (rd / "triage" / "a003.verdict.txt").write_text("a003 keep\n")


def test_items(rd):
    print("\nitems-sync")
    good = {"items": [
        {"item_id": "i01", "name": "A and C", "kind": "cluster", "verdict": "READ",
         "profile": None, "articles": ["a001", "a003"], "primary": "a001",
         "read": ["a001", "a003"]},
        {"item_id": "i02", "name": "Undated", "kind": "single", "verdict": "READ",
         "profile": None, "articles": ["a004"], "primary": "a004", "read": ["a004"]},
    ], "near_misses": []}

    bad = json.loads(json.dumps(good))
    bad["items"][1]["articles"] = ["a002"]        # dropped at triage
    bad["items"][1]["read"] = ["a002"]
    bad["items"][1]["primary"] = "a002"
    write(rd / "items" / "plan.json", bad)
    out, _ = run("items-sync", "--run", rd, expect=1)
    check("rejects an article dropped at triage", has(out, "a002 was dropped at triage"))
    check("notices the kept article left out", has(out, "a004: kept at triage but in no item"))

    dup = json.loads(json.dumps(good))
    dup["items"][1]["articles"] = ["a001", "a004"]
    write(rd / "items" / "plan.json", dup)
    out, _ = run("items-sync", "--run", rd, expect=1)
    check("rejects the same article in two items", has(out, "already in i01"))

    noverdict = json.loads(json.dumps(good))
    del noverdict["items"][0]["verdict"]
    write(rd / "items" / "plan.json", noverdict)
    out, _ = run("items-sync", "--run", rd, expect=1)
    check("a cluster with no verdict is rejected too", has(out, "i01: verdict"))

    unknown = json.loads(json.dumps(good))
    unknown["items"][0]["profile"] = "Iran war with no strategy that nobody named"
    write(rd / "items" / "plan.json", unknown)
    out, _ = run("items-sync", "--run", rd, expect=1)
    check("an invented profile topic is rejected", has(out, "is not in the profile"))
    check("and the nearest real name is offered", has(out, "did you mean"))

    write(rd / "items" / "plan.json", good)
    out, _ = run("items-sync", "--run", rd, expect=0)
    check("accepts a clean plan", out["by_group"]["beat-read"] == 2, str(out))
    check("builds the read list", out["articles_to_read"] == 3)
    read = json.loads((rd / "items" / "read-list.json").read_text())["read"]
    check("every article carries its group", all(r["group"] == "beat-read" for r in read))


def test_items_afternoon():
    """An update's own clustering rules: who may be followed, and what is read.

    Three items, and every rule of the afternoon turns on which is which: one
    that follows the morning's story, one new story big enough to be read, and
    one new story too small. Everything runs inside a runs folder of its own,
    named by YBS_RUNS_DIR, so the real runs are neither read nor written.
    """
    print("\nitems-sync: following the morning, and the size of a new story")
    settings, _ = run("settings", expect=0)
    floor = settings["new_item_articles_min"]
    tmp = Path(tempfile.mkdtemp(prefix="ybs-runs-"))
    env = {"YBS_RUNS_DIR": str(tmp)}
    try:
        build_morning(tmp, "2026-x_morning_100000", now_iso(-6),
                      links=["https://www.theguardian.com/x/seen-at-ten"],
                      picks=["a001"])

        def prepared(slot, n):
            """A run of `slot` with n articles, all kept at triage."""
            out, _ = run("start", "--slot", slot, expect=0, env=env)
            rd = Path(out["run_dir"])
            write(rd / "screen" / "guardian.json", {
                "source": "Guardian", "ok": True,
                "links": [link(f"https://www.theguardian.com/{slot}/{i:03d}",
                               f"story {i}") for i in range(n)]})
            run("screen-sync", "--run", rd)
            run("triage-list", "--run", rd, expect=0)
            for a in json.loads((rd / "articles.json").read_text())["articles"]:
                (rd / "triage" / f"{a['id']}.verdict.txt").write_text(
                    f"{a['id']} keep\n")
            run("triage-check", "--run", rd, expect=0)
            return rd

        def item(iid, ids, follows=None, verdict="READ"):
            return {"item_id": iid, "name": iid, "profile": None,
                    "kind": "cluster" if len(ids) > 1 else "single",
                    "verdict": verdict, "follows": follows, "articles": ids,
                    "primary": ids[0], "read": [ids[0]], "why": "x"}

        # 1. A morning run follows nothing at all.
        rd = prepared("morning", 2)
        write(rd / "items" / "plan.json", {"items": [
            item("i01", ["a001"], follows="m:a001"), item("i02", ["a002"])],
            "near_misses": []})
        out, _ = run("items-sync", "--run", rd, expect=1)
        check("a morning item may not follow anything",
              has(out, "a morning brief follows nothing"), str(out)[:200])

        # 2. The afternoon, with the morning behind it.
        time.sleep(1.1)          # a run id names the second it started in
        rd = prepared("afternoon", floor + 2)
        ids = [a["id"] for a in
               json.loads((rd / "articles.json").read_text())["articles"]]
        follower, small, big = ids[0], ids[1], ids[2:]
        plan = {"items": [item("i01", [follower], follows="m:a001"),
                          item("i02", [small]),
                          item("i03", big)], "near_misses": []}

        bare = json.loads(json.dumps(plan))
        bare["items"][0]["follows"] = "a001"
        write(rd / "items" / "plan.json", bare)
        out, _ = run("items-sync", "--run", rd, expect=1)
        check("a bare id is refused: a story of the morning is named m:<id>",
              has(out, "m:<id>"), str(out)[:200])

        stranger = json.loads(json.dumps(plan))
        stranger["items"][0]["follows"] = "m:a404"
        write(rd / "items" / "plan.json", stranger)
        out, _ = run("items-sync", "--run", rd, expect=1)
        check("an id the morning brief never picked is refused",
              has(out, "did not pick"), str(out)[:200])

        write(rd / "items" / "plan.json", plan)
        out, _ = run("items-sync", "--run", rd, expect=0)
        check("a follower is its own group",
              out["by_group"]["follow-read"] == 1
              and out["by_group"]["beat-read"] == 2, str(out)[:200])
        check(f"a new item under {floor} articles is counted, not read",
              out["small_new_items"] == 1, str(out)[:200])
        check("the counts of the run say so too",
              json.loads((rd / "run.json").read_text())
              ["counts"]["small_new_items"] == 1)
        read = json.loads((rd / "items" / "read-list.json").read_text())["read"]
        check("the follower is read before the new story is",
              [r["id"] for r in read] == [follower, big[0]],
              str([r["id"] for r in read]))
        check("and it carries the morning story it follows",
              read[0]["follows"] == "m:a001" and read[1]["follows"] is None,
              str(read))
        check("the small new story is read by nobody",
              small not in [r["id"] for r in read], str(read))

        # The head line of a note says what it follows, and that reaches the pick.
        for r in read:
            (rd / "notes" / f"{r['id']}.md").write_text(
                f"HEADLINE: story {r['id']}\n", encoding="utf-8")
        out, _ = run("fill", "pick", "--run", rd, expect=0)
        text = Path(out["file"]).read_text()
        check("a follower's note is headed with the story it follows",
              f"{follower} · follow-read" in text and "· follows m:a001" in text,
              text[text.find(follower):][:160])
        check("and a note that follows nothing is headed as it always was",
              f"{big[0]} · beat-read" in text and text.count("· follows ") == 1,
              str(text.count("· follows ")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def selection_run(n_articles, build):
    """A run whose articles are all kept, so selection can be tested on its own.

    `build(ids)` returns the plan's items. screen-sync reports the five sources
    this fixture leaves unscreened, so its exit code is not asserted here.
    """
    rd = new_run()
    ids = [f"a{i:03d}" for i in range(1, n_articles + 1)]
    write(rd / "screen" / "guardian.json", {
        "source": "Guardian", "ok": True,
        "links": [{"url": f"https://www.theguardian.com/x/{i}", "title": f"story {i}",
                   "description": "d", "category": "World", "published": now_iso(-1)}
                  for i in ids]})
    run("screen-sync", "--run", rd)
    run("triage-list", "--run", rd, expect=0)
    for i in ids:
        (rd / "triage" / f"{i}.verdict.txt").write_text(f"{i} keep\n")
    run("triage-check", "--run", rd, expect=0)
    write(rd / "items" / "plan.json", {"items": build(ids), "near_misses": []})
    return rd


def one_each(make):
    """One article per item: the common shape for these tests."""
    return lambda ids: [make(k, aid) for k, aid in enumerate(ids)]


def test_selection():
    """The heart of v4: what gets read, in what order, and where it stops."""
    print("\nselection: priority, the cap and the MAYBE rule")
    settings, _ = run("settings", expect=0)
    cap = settings["read_items_max"]
    floor = settings["maybe_below_reads"]
    share = settings["maybe_share_max"]
    topic = live_topic()

    # 1. More READs than the cap: the cap holds and topic stories go first.
    def make(k, aid):
        on_topic = k >= cap        # the later half is on a profile topic
        return {"item_id": f"i{k:02d}", "name": f"item {k}", "kind": "single",
                "verdict": "READ", "profile": topic if on_topic else None,
                "articles": [aid], "primary": aid, "read": [aid]}
    rd = selection_run(cap + 10, one_each(make))
    try:
        out, _ = run("items-sync", "--run", rd, expect=0)
        check(f"never reads more than {cap} items", out.get("ok") and out["reads_taken"] == cap, str(out))
        check("the overflow is named, not silently dropped",
              out.get("ok") and len(out["skipped_for_cap"]) == 10, str(out))
        read = json.loads((rd / "items" / "read-list.json").read_text())["read"]
        check("every topic story is read before any beat story is",
              all(r["group"] == "topic-read" for r in read[:10]),
              str([r["group"] for r in read[:12]]))
    finally:
        shutil.rmtree(rd, ignore_errors=True)

    # 2. Few READs: MAYBEs may only top up to half the READ count.
    reads = 20
    def make2(k, aid):
        is_read = k < reads
        return {"item_id": f"i{k:02d}", "name": f"item {k}", "kind": "single",
                "verdict": "READ" if is_read else "MAYBE", "profile": None,
                "articles": [aid], "primary": aid, "read": [aid]}
    rd = selection_run(reads + 30, one_each(make2))
    try:
        out, _ = run("items-sync", "--run", rd, expect=0)
        check(f"{reads} READs allow at most {reads * share // 100} MAYBEs",
              out.get("ok") and out["maybes_taken"] == reads * share // 100, str(out))
    finally:
        shutil.rmtree(rd, ignore_errors=True)

    # 3. Enough READs already: no MAYBE is taken at all.
    def make3(k, aid):
        return {"item_id": f"i{k:02d}", "name": f"item {k}", "kind": "single",
                "verdict": "READ" if k < floor else "MAYBE", "profile": None,
                "articles": [aid], "primary": aid, "read": [aid]}
    rd = selection_run(floor + 5, one_each(make3))
    try:
        out, _ = run("items-sync", "--run", rd, expect=0)
        check("at the floor, no MAYBE is taken", out.get("ok") and out["maybes_taken"] == 0, str(out))
    finally:
        shutil.rmtree(rd, ignore_errors=True)

    # 4. Same group: a story several papers ran is read before a lone one.
    def build(ids):
        return [
            {"item_id": "i00", "name": "lone", "kind": "single", "verdict": "READ",
             "profile": None, "articles": [ids[0]], "primary": ids[0], "read": [ids[0]]},
            {"item_id": "i01", "name": "shared", "kind": "cluster", "verdict": "READ",
             "profile": None, "articles": ids[1:3], "primary": ids[1], "read": [ids[1]]},
        ]
    rd = selection_run(3, build)
    try:
        run("items-sync", "--run", rd, expect=0)
        read = json.loads((rd / "items" / "read-list.json").read_text())["read"]
        check("within a group the shared story is read first",
              read[0]["item"] == "i01", str([r["item"] for r in read]))
    finally:
        shutil.rmtree(rd, ignore_errors=True)


def test_cluster_parts():
    """A kept list over cluster_articles_max is cut into parts by source, each
    part clustered alone, then merged. No part goes over the ceiling, a source
    is split only when it alone exceeds it, and every article is in exactly one
    part. The merge refuses a part plan that strays outside its part."""
    print("\ncluster in parts")
    settings, _ = run("settings", expect=0)
    cap = settings["cluster_articles_max"]

    def screened(rd, counts):
        for slug, (name, n) in counts.items():
            write(rd / "screen" / f"{slug}.json", {"source": name, "ok": True, "links": [
                link(f"https://{slug}.example/{i:03d}", f"{name} {i}") for i in range(n)]})
        run("screen-sync", "--run", rd)
        run("triage-list", "--run", rd, expect=0)
        arts = json.loads((rd / "articles.json").read_text())["articles"]
        for a in arts:
            (rd / "triage" / f"{a['id']}.verdict.txt").write_text(f"{a['id']} keep\n")
        run("triage-check", "--run", rd, expect=0)
        return arts

    def ids_in(path):
        return re.findall(r"^(a\d{3}) \[", Path(path).read_text(), re.M)

    def singles(ids, near=None):
        return {"items": [{"item_id": f"i{n:02d}", "name": f"item {aid}", "kind": "single",
                           "verdict": "READ", "profile": None, "articles": [aid],
                           "primary": aid, "read": [aid], "why": "x"}
                          for n, aid in enumerate(ids, 1)], "near_misses": near or []}

    # 1. Three sources, none over the ceiling, six over it together.
    rd = new_run()
    try:
        a, b = cap * 2 // 5, cap // 3
        arts = screened(rd, {"guardian": ("Guardian", a), "reason": ("Reason", b),
                             "bbc": ("BBC", cap + 6 - a - b)})
        out, _ = run("fill", "cluster-select", "--run", rd, expect=0)
        check("over the ceiling, fill names the parts instead of a file",
              isinstance(out, dict) and out.get("too_long") and out.get("file") is None
              and out.get("parts") == 2, str(out)[:200])
        cut = out["cut"]
        check("no part is over the ceiling", all(c["articles"] <= cap for c in cut), str(cut))
        check("the parts add up to the kept list",
              sum(c["articles"] for c in cut) == len(arts), str(cut))
        check("a source under the ceiling is never split",
              sum(len(c["sources"]) for c in cut) == 3, str(cut))
        seen = []
        for k in (1, 2):
            out, _ = run("fill", "cluster-select", "--run", rd, "--part", f"{k}/2", expect=0)
            text = Path(out["file"]).read_text()
            ids = ids_in(out["file"])
            check(f"part {k} renders its own articles and says which part it is",
                  len(ids) == cut[k - 1]["articles"] and f"part {k} of 2" in text
                  and "{{" not in text, str(out)[:200])
            seen += ids
        check("every article is in exactly one part",
              sorted(seen) == sorted(x["id"] for x in arts) and len(seen) == len(set(seen)))
        _, r = run("fill", "cluster-select", "--run", rd, "--part", "1/3", expect=2)
        check("a wrong part count is refused", r.returncode == 2, r.stderr[:100])
        _, r = run("fill", "pick", "--run", rd, "--part", "1/2", expect=2)
        check("--part on any other prompt is refused, not crashed",
              r.returncode == 2 and "--part is only for cluster-select" in r.stderr,
              r.stderr[:100])

        part_ids = {k: ids_in(rd / "prompts" / f"cluster-select-part{k}of2.md") for k in (1, 2)}
        write(rd / "items" / "plan-part1.json", singles(part_ids[1][:-1] + [part_ids[2][0]]))
        out, _ = run("fill", "cluster-merge", "--run", rd, expect=1)
        check("a part plan holding another part's article is refused",
              isinstance(out, dict) and out.get("part") == 1
              and any("not in part 1" in x for x in out["problems"]), str(out)[:200])
        write(rd / "items" / "plan-part1.json", singles(part_ids[1], ["a and b: near"]))
        _, r = run("fill", "cluster-merge", "--run", rd, expect=2)
        check("a missing part plan stops the merge",
              r.returncode == 2 and "plan-part2" in r.stderr, r.stderr[:100])
        write(rd / "items" / "plan-part2.json", singles(part_ids[2]))
        out, _ = run("fill", "cluster-merge", "--run", rd, expect=0)
        text = Path(out["file"]).read_text() if isinstance(out, dict) else ""
        check("the merge prompt shows every part's items and near misses",
              "1/i01 ·" in text and "2/i01 ·" in text and "part 1: a and b: near" in text
              and "{{" not in text, str(out)[:200])
        write(rd / "items" / "plan.json", singles([x["id"] for x in arts]))
        out, _ = run("items-sync", "--run", rd, expect=0)
        check("a merged plan is accepted like any other", out.get("ok") is True, str(out)[:200])
    finally:
        shutil.rmtree(rd, ignore_errors=True)

    # 2. One source alone over the ceiling: it is cut in id order, nothing else is.
    rd = new_run()
    try:
        arts = screened(rd, {"guardian": ("Guardian", cap + 10), "reason": ("Reason", 5)})
        out, _ = run("fill", "cluster-select", "--run", rd, expect=0)
        cut = out["cut"]
        check("only the source over the ceiling is split, and no part is over it",
              all(c["articles"] <= cap for c in cut)
              and sum(len(c["sources"]) for c in cut) == 3, str(cut))
        g = [x["id"] for x in arts if x["source"] == "Guardian"]
        chunks = []
        for k in range(1, len(cut) + 1):
            out, _ = run("fill", "cluster-select", "--run", rd, "--part", f"{k}/{len(cut)}", expect=0)
            chunks.append([i for i in ids_in(out["file"]) if i in set(g)])
        check("the split source keeps id order inside every part",
              sorted(sum(chunks, [])) == g and all(c == sorted(c) for c in chunks), str(cut))
    finally:
        shutil.rmtree(rd, ignore_errors=True)


def test_read_list(rd):
    """v3: a plain list with a launch line each, no waves."""
    print("\nread-list")
    out, _ = run("read-list", "--run", rd, expect=0)
    check("three articles to read", out["todo"] == 3, str(out["todo"]))
    settings, _ = run("settings", expect=0)
    check("the pool is the ceiling settings.md sets",
          out["pool"] == settings["agents_active_max"], str(out["pool"]))
    e = out["list"][0]
    check("the launch line is id, source, url and run dir",
          e["launch"] == f"{e['id']} | {e['source']} | {e['url']} | {rd}", e["launch"][:120])

    (rd / "notes" / "a001.md").write_text("KEY FIGURES: 19 bodies\n")
    out, _ = run("read-list", "--run", rd, expect=0)
    check("skips an article already read", out["todo"] == 2)

    run("event", "--run", rd, "--type", "read_failed", "--article", "a003",
        "--detail", "PAGE_TRUNCATED twice", expect=0)
    out, _ = run("read-list", "--run", rd, expect=0)
    check("retires an article that failed its retry", out["todo"] == 1
          and all(x["id"] != "a003" for x in out["list"]), str(out["todo"]))


def test_checks(rd):
    """The pick runs first, so only the picked notes and the counterpoints are
    checked. This test sets its own picks: it is checking check-sync, not pick."""
    print("\ncheck-sync")
    write(rd / "picks" / "picks.json", {
        "picks": [{"id": "a001", "tag": "LEAD"}, {"id": "a003", "tag": "LEAD"},
                  {"id": "a004", "tag": "WORTH"}],
        "dropped": [{"id": "a009", "reason_type": "duplicate",
                     "reason": "same event as a003"}]})
    for aid in ("a003", "a004"):
        (rd / "notes" / f"{aid}.md").write_text(
            f"HEADLINE: {aid}\nKEY FIGURES:\n- 19 bodies found\n- 73 total this year\n")
    # a001 is picked and carries no figures at all; a009 is read but not picked
    (rd / "notes" / "a001.md").write_text("HEADLINE: a001\nKEY FIGURES:\n")
    (rd / "notes" / "a009.md").write_text(
        "HEADLINE: a009\nKEY FIGURES:\n- 5 unpicked figures\n")
    (rd / "picks" / "cp-a001.md").write_text(
        "STORY: a001\nTHE ARGUMENT: x\nKEY FIGURES:\n- 68% to 34% of GDP\n")
    (rd / "picks" / "cp-a003.md").write_text("NONE\n")

    out, _ = run("check-sync", "--run", rd, "--pass", 1, expect=1)
    check("checks the picked notes and the real counterpoint",
          set(out["unchecked"]) == {"a001", "a003", "a004", "cp-a001"},
          str(out["unchecked"]))
    check("ignores a note that was read but not picked", "a009" not in out["unchecked"])
    check("ignores a counterpoint that is NONE", "cp-a003" not in out["unchecked"])

    (rd / "checks" / "a001.txt").write_text("no figures\n")
    (rd / "checks" / "a003.txt").write_text("19 bodies found\n73 total this year missing\n")
    (rd / "checks" / "a004.txt").write_text("19 bodies found\n73 total this year\n")
    (rd / "checks" / "cp-a001.txt").write_text("68% to 34% of GDP missing\n")
    out, _ = run("check-sync", "--run", rd, "--pass", 1, expect=1)
    check("'no figures' counts as clean", out["clean"] >= 2, f"clean={out['clean']}")
    check("pass 1 asks for a redo, strikes nothing",
          {r["id"] for r in out["redo"]} == {"a003", "cp-a001"} and not out["struck"],
          str(out["redo"]))
    redo = {r["id"]: r for r in out["redo"]}
    check("a redo carries the saved-page launch line for its article",
          redo["a003"].get("launch", "").startswith("a003 | ")
          and redo["a003"].get("launch", "").endswith(f"| {rd} | saved-page"),
          str(redo["a003"]))
    check("and none for a counterpoint, which is never re-read",
          "launch" not in redo["cp-a001"])

    out, _ = run("check-sync", "--run", rd, "--pass", 2, expect=0)
    text = (rd / "notes" / "a003.md").read_text()
    check("pass 2 strikes the figure", "73 total this year" not in text)
    check("pass 2 marks the note", "1 unverified, removed" in text)
    check("pass 2 keeps the note and its good figure",
          "19 bodies found" in text and (rd / "notes" / "a003.md").exists())
    cp = (rd / "picks" / "cp-a001.md").read_text()
    check("pass 2 strikes inside a counterpoint too",
          "68% to 34% of GDP" not in cp and "THE ARGUMENT" in cp)
    check("counts what it checked, not every note",
          json.loads((rd / "run.json").read_text())["counts"]["checked"] == 4,
          str(json.loads((rd / "run.json").read_text())["counts"].get("checked")))

    # Step 9 runs both passes again over the counterpoints. A note struck in
    # step 8 must come out of that untouched: no second re-read, no second
    # footer, no second event, and the struck count must not go down.
    out, _ = run("check-sync", "--run", rd, "--pass", 1, expect=0)
    check("a struck note is not offered for a second re-read",
          set(out["already_struck"]) == {"a003", "cp-a001"} and out["redo"] == [],
          str(out))
    out, _ = run("check-sync", "--run", rd, "--pass", 2, expect=0)
    text = (rd / "notes" / "a003.md").read_text()
    events = json.loads((rd / "run.json").read_text())["events"]
    check("a second pass 2 strikes nothing twice",
          text.count("unverified, removed") == 1 and not out["struck"]
          and sum(1 for e in events if e["type"] == "figures_struck"
                  and e.get("article") == "a003") == 1, str(out))
    check("the struck count is cumulative, not the last pass's",
          json.loads((rd / "run.json").read_text())["counts"]["notes_struck"] == 2,
          str(json.loads((rd / "run.json").read_text())["counts"].get("notes_struck")))


def test_counterpoint_fill(rd):
    """A counterpoint looks inside its lead's own news item, and only a LEAD
    gets one. The fixture's plan has i01 = a001 + a003 and i02 = a004 alone."""
    print("\nfill counterpoint")
    picks_before = (rd / "picks" / "picks.json").read_text()
    write(rd / "picks" / "picks.json", {
        "picks": [{"id": "a001", "tag": "LEAD"}, {"id": "a003", "tag": "BODY"},
                  {"id": "a004", "tag": "LEAD"}],
        "dropped": []})
    (rd / "notes" / "a001.md").write_text(
        "HEADLINE: a001\nWHAT HAPPENED: the order was signed\n"
        "THE PRINCIPLE: an executive taking a power the law places elsewhere\n")

    _, r = run("fill", "counterpoint", "--run", rd, "--article", "a003", expect=2)
    check("a BODY story is refused", "counterpoints run for LEAD stories only"
          in r.stderr, r.stderr.strip()[:120])

    out, _ = run("fill", "counterpoint", "--run", rd, "--article", "a001", expect=0)
    text = Path(out["file"]).read_text()
    check("the lead's own sibling is the pool", "a003 [" in text, text[-600:])
    check("the lead itself is not in its own pool", "a001 [" not in text)
    check("a story from another item is not in the pool", "a004 [" not in text,
          text[-600:])
    check("a sibling that was read carries its note",
          "---- its note ----" in text and "19 bodies found" in text, text[-800:])
    check("no placeholder is left unfilled", out["unfilled"] == [], str(out))

    out, _ = run("fill", "counterpoint", "--run", rd, "--article", "a004", expect=0)
    check("a lead alone in its item gets no prompt and no agent",
          out["file"] is None and out["alone_in_item"] and out["launch"] is False,
          str(out))
    check("and fill writes the NONE itself",
          (rd / "picks" / "cp-a004.md").read_text().strip() == "NONE")

    (rd / "picks" / "picks.json").write_text(picks_before)


def test_picks(rd):
    """v4: every number is a ceiling, and relevance may not be skipped over."""
    print("\npicks-sync")
    for aid in ("a001", "a003", "a004"):
        (rd / "notes" / f"{aid}.md").write_text(f"HEADLINE: {aid}\n")

    write(rd / "picks" / "picks.json", {"picks": [{"id": "a001", "tag": "LEAD"}],
                                        "dropped": []})
    out, _ = run("picks-sync", "--run", rd, expect=1)
    check("one lead is not too few: no minimum anywhere",
          not has(out, "1 LEAD"), str(out.get("problems")))
    check("catches a note neither picked nor dropped", has(out, "a003: neither picked"))

    write(rd / "picks" / "picks.json", {
        "picks": [{"id": "a001", "tag": "LEAD"}, {"id": "a003", "tag": "LEAD"}],
        "dropped": [{"id": "a004", "reason_type": "evidence", "reason": ""}]})
    out, _ = run("picks-sync", "--run", rd, expect=1)
    check("catches a drop with no reason", has(out, "a004: dropped with no reason"))

    write(rd / "picks" / "picks.json", {
        "picks": [{"id": "a001", "tag": "LEAD"}, {"id": "a003", "tag": "LEAD"}],
        "dropped": [{"id": "a004", "reason_type": "meh", "reason": "not for me"}]})
    out, _ = run("picks-sync", "--run", rd, expect=1)
    check("a made-up reason type is rejected", has(out, "reason_type 'meh'"))

    write(rd / "picks" / "picks.json", {
        "picks": [{"id": "a001", "tag": "LEAD"}, {"id": "a003", "tag": "WORTH"}],
        "dropped": [{"id": "a004", "reason_type": "duplicate",
                     "reason": "same event as a001"}]})
    out, _ = run("picks-sync", "--run", rd, expect=0)
    check("two picks and one honest drop is a valid brief",
          out["picks"] == 2 and out["by_tag"]["LEAD"] == 1, str(out))

    over = {"picks": [{"id": f"a{i:03d}", "tag": "BODY"} for i in range(1, 17)],
            "dropped": []}
    write(rd / "picks" / "picks.json", over)
    out, _ = run("picks-sync", "--run", rd, expect=1)
    check("refuses more than 15 picks", has(out, "16 picks"))

    lead_heavy = {"picks": [{"id": f"a{i:03d}", "tag": "LEAD"} for i in range(1, 7)],
                  "dropped": []}
    write(rd / "picks" / "picks.json", lead_heavy)
    out, _ = run("picks-sync", "--run", rd, expect=1)
    check("refuses more leads than the ceiling", has(out, "6 LEAD stories"))


def afternoon_run(tmp, env, ids, follows, groups=None):
    """An afternoon run with a plan and a read list written by hand.

    picks-sync reads three things: the notes on disk, the plan (for the size of
    each story and the morning story it follows) and the read list (for the
    group each pick came from). Writing those directly keeps this about the
    pick and nothing else -- no screen, no triage, no cluster.

    `follows` maps an article id to the base story its item carries forward, or
    leaves it out for a story the brief being updated never had. `ids` may name
    a count of articles instead of just an id, as `(id, n)`.
    """
    out, _ = run("start", "--slot", "afternoon", expect=0, env=env)
    rd = Path(out["run_dir"])
    pairs = [(x, 1) if isinstance(x, str) else x for x in ids]
    items, read = [], []
    for k, (aid, n) in enumerate(pairs):
        siblings = [aid] + [f"{aid}-s{j}" for j in range(1, n)]
        items.append({"item_id": f"i{k:02d}", "name": aid,
                      "kind": "cluster" if n > 1 else "single",
                      "verdict": "READ", "profile": None,
                      "follows": follows.get(aid), "articles": siblings,
                      "primary": aid, "read": [aid], "why": "x"})
        read.append({"id": aid, "item": f"i{k:02d}",
                     "group": (groups or {}).get(
                         aid, "follow-read" if follows.get(aid) else "beat-read"),
                     "profile": None, "follows": follows.get(aid),
                     "primary": True})
        (rd / "notes" / f"{aid}.md").write_text(f"HEADLINE: {aid}\n",
                                                encoding="utf-8")
    write(rd / "items" / "plan.json", {"items": items, "near_misses": []})
    write(rd / "items" / "read-list.json", {"read": read})
    write(rd / "articles.json", {"articles": [
        {"id": a, "source": "Guardian", "url": f"https://example.com/{a}",
         "title": f"headline of {a}", "description": "d", "category": "world",
         "published": now_iso(-1), "also_in": []}
        for it in items for a in it["articles"]]})
    return rd, [aid for aid, _ in pairs]


def test_picks_afternoon():
    """The update's own pick: two tags, a kind on what moved, one line per story.

    Everything runs inside a runs folder of its own, named by YBS_RUNS_DIR, so
    the morning being updated is one this test wrote and the real runs are
    neither read nor written.
    """
    print("\npicks-sync: the afternoon's two tags")
    settings, _ = run("settings", expect=0)
    ceiling = settings["update_picks_max"]
    tmp = Path(tempfile.mkdtemp(prefix="ybs-runs-"))
    env = {"YBS_RUNS_DIR": str(tmp)}
    base_ids = [f"a{100 + i:03d}" for i in range(1, ceiling)]
    try:
        base = build_morning(
            tmp, "2026-x_morning_100000", now_iso(-6),
            links=[f"https://www.theguardian.com/m/{i}" for i in base_ids],
            picks=base_ids)
        base_before = (base / "picks" / "picks.json").read_text()

        # Five afternoon stories: three carrying a morning story forward (two of
        # them the same one), two the morning never had.
        follows = {"a001": "m:a101", "a002": "m:a101", "a003": "m:a102"}
        rd, ids = afternoon_run(tmp, env, ["a001", "a002", "a003", "a004", "a005"],
                                follows)

        def picks(*kept):
            """A reply keeping these picks and dropping every other note."""
            kept_ids = {p["id"] for p in kept}
            return {"picks": list(kept),
                    "dropped": [{"id": a, "reason_type": "unchanged",
                                 "reason": "the morning brief already has it"}
                                for a in ids if a not in kept_ids]}

        write(rd / "picks" / "picks.json",
              picks({"id": "a001", "tag": "LEAD", "why": "x"}))
        out, _ = run("picks-sync", "--run", rd, expect=1)
        check("the morning's tags are not the afternoon's",
              has(out, "tag 'LEAD' is not NEW | MOVED"), str(out.get("problems")))

        write(rd / "picks" / "picks.json",
              picks({"id": "a001", "tag": "MOVED", "why": "x"}))
        out, _ = run("picks-sync", "--run", rd, expect=1)
        check("a MOVED story must say how it moved",
              has(out, "is not one of development"), str(out.get("problems")))

        write(rd / "picks" / "picks.json",
              picks({"id": "a004", "tag": "MOVED", "kind": "development",
                     "why": "x"}))
        out, _ = run("picks-sync", "--run", rd, expect=1)
        check("a MOVED story whose item follows nothing is refused",
              has(out, "a004: tagged MOVED"), str(out.get("problems")))

        write(rd / "picks" / "picks.json",
              picks({"id": "a001", "tag": "NEW", "why": "x"}))
        out, _ = run("picks-sync", "--run", rd, expect=1)
        check("and a NEW story whose item follows one is refused too",
              has(out, "a001: tagged NEW, and its item follows m:a101"),
              str(out.get("problems")))

        write(rd / "picks" / "picks.json",
              picks({"id": "a004", "tag": "NEW", "kind": "reversal", "why": "x"}))
        out, _ = run("picks-sync", "--run", rd, expect=1)
        check("a kind on a NEW story is a contradiction, not a detail",
              has(out, "a004: tagged NEW and given kind"), str(out.get("problems")))

        write(rd / "picks" / "picks.json",
              picks({"id": "a001", "tag": "MOVED", "kind": "development", "why": "x"},
                    {"id": "a002", "tag": "MOVED", "kind": "confirmation", "why": "x"}))
        out, _ = run("picks-sync", "--run", rd, expect=1)
        check("two picks may not follow one morning story, and both are named",
              has(out, "a002 and a001 both follow m:a101"), str(out.get("problems")))

        write(rd / "picks" / "picks.json",
              picks({"id": "a001", "tag": "MOVED", "kind": "development", "why": "x"},
                    {"id": "a003", "tag": "MOVED", "kind": "confirmation", "why": "x"},
                    {"id": "a004", "tag": "NEW", "why": "x"}))
        out, _ = run("picks-sync", "--run", rd, expect=0)
        check("a clean update is accepted, with the unchanged reason",
              out["picks"] == 3 and out["by_tag"] == {"NEW": 1, "MOVED": 2},
              str(out))
        check("nothing leads an update, so step 9 has nothing to launch",
              out["leads"] == [], str(out.get("leads")))
        check("the mix counts what came from the morning's own stories",
              out["mix"] == {"topic": 0, "beat": 1, "maybe": 0, "follow": 2},
              str(out.get("mix")))
        counts = json.loads((rd / "run.json").read_text())["counts"]
        check("run.json records the new stories and the moved ones by kind",
              counts["new"] == 1 and counts["moved"] == 2
              and counts["moved_by_kind"] == {"development": 1, "confirmation": 1,
                                              "reversal": 0, "correction": 0},
              str({k: counts.get(k) for k in ("new", "moved", "moved_by_kind")}))

        write(rd / "picks" / "picks.json", picks())
        out, _ = run("picks-sync", "--run", rd, expect=0)
        check("an update that picked nothing is not a failure: nothing moved",
              out["picks"] == 0 and out["leads"] == [] and not out["problems"],
              str(out))

        check("the brief being updated is never written to",
              (base / "picks" / "picks.json").read_text() == base_before)

        # Over the ceiling: a NEW goes before a MOVED, and the smallest first.
        print("\npicks-sync: trimming an update")
        time.sleep(1.1)          # a run id names the second it started in
        moved = [f"a{i:03d}" for i in range(1, ceiling)]
        follows = {aid: f"m:{b}" for aid, b in zip(moved, base_ids)}
        rd2, _ = afternoon_run(
            tmp, env, moved + [("n001", 5), ("n002", 1), ("n003", 3)], follows)
        write(rd2 / "picks" / "picks.json", {
            "picks": [{"id": a, "tag": "MOVED", "kind": "development", "why": "x"}
                      for a in moved]
                     + [{"id": n, "tag": "NEW", "why": "x"}
                        for n in ("n001", "n002", "n003")],
            "dropped": []})
        out, _ = run("picks-sync", "--run", rd2, expect=0)
        check(f"an update is cut back to {ceiling} stories",
              out["picks"] == ceiling, str(out.get("picks")))
        check("the new stories go first, the smallest of them before the rest",
              out["trimmed"] == ["n002", "n003"], str(out.get("trimmed")))
        check("and every story that moved is still there",
              out["by_tag"] == {"NEW": 1, "MOVED": ceiling - 1}, str(out.get("by_tag")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_pick_prompt_per_slot():
    """`fill pick` renders the slot's own prompt into the same file.

    Step 7's launch line names `prompts/pick.md` in both slots, so the file the
    orchestrator hands over never changes name. What is inside it does: the
    morning asks which stories reach the brief, the afternoon asks which of them
    moved. A `fill counterpoint` on an update is refused, because an update has
    no lead for one to hang under.
    """
    print("\nfill pick: one file, one prompt per slot")
    tmp = Path(tempfile.mkdtemp(prefix="ybs-runs-"))
    env = {"YBS_RUNS_DIR": str(tmp)}
    try:
        build_morning(tmp, "2026-x_morning_100000", now_iso(-6),
                      links=["https://www.theguardian.com/m/1"], picks=["a101"])

        rd, _ = afternoon_run(tmp, env, ["a001", "a002"], {"a001": "m:a101"})
        out, _ = run("fill", "pick", "--run", rd, expect=0)
        check("the afternoon writes its prompt to prompts/pick.md",
              Path(out["file"]) == (rd / "prompts" / "pick.md").resolve(),
              str(out.get("file")))
        text = Path(out["file"]).read_text()
        check("and it is the update's prompt, not the morning's",
              "Ask each note one question" in text and "at 9am" not in text,
              text[:160])
        check("the morning's stories are in it, with the fields the note carried",
              "m:a101 · LEAD · the morning's story a101" in text
              and "WHAT'S NEW: what a101 carried at ten" in text,
              text[text.find("m:a101"):][:200])
        check("and its dropped list says the morning dropped nothing",
              "That brief dropped nothing" in text)
        check("no placeholder is left unfilled", out["unfilled"] == [], str(out))

        write(rd / "picks" / "picks.json", {
            "picks": [{"id": "a001", "tag": "MOVED", "kind": "development",
                       "why": "x"}],
            "dropped": [{"id": "a002", "reason_type": "unchanged",
                         "reason": "the morning brief already has it"}]})
        _, r = run("fill", "counterpoint", "--run", rd, "--article", "a001",
                   expect=2, env=env)
        check("a MOVED story gets no counterpoint",
              "counterpoints run for LEAD stories only" in r.stderr,
              r.stderr.strip()[:160])

        time.sleep(1.1)          # a run id names the second it started in
        out, _ = run("start", "--slot", "morning", expect=0, env=env)
        rd = Path(out["run_dir"])
        write(rd / "items" / "read-list.json", {"read": [
            {"id": "a001", "item": "i00", "group": "beat-read", "profile": None,
             "follows": None, "primary": True}]})
        (rd / "notes" / "a001.md").write_text("HEADLINE: a001\n", encoding="utf-8")
        out, _ = run("fill", "pick", "--run", rd, expect=0)
        text = Path(out["file"]).read_text()
        check("a morning run still gets the morning's own pick prompt",
              "at 9am" in text and "Ask each note one question" not in text,
              text[:160])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_pick_groups():
    """A beat story may not be taken while a topic story was passed over."""
    print("\npicks-sync: the groups decide the order")
    topic = live_topic()

    def make(k, aid):
        return {"item_id": f"i{k:02d}", "name": f"item {k}", "kind": "single",
                "verdict": "READ", "profile": topic if k == 0 else None,
                "articles": [aid], "primary": aid, "read": [aid]}
    rd = selection_run(2, one_each(make))
    try:
        run("items-sync", "--run", rd, expect=0)
        for aid in ("a001", "a002"):
            (rd / "notes" / f"{aid}.md").write_text(f"HEADLINE: {aid}\n")

        write(rd / "picks" / "picks.json", {
            "picks": [{"id": "a002", "tag": "BODY"}],
            "dropped": [{"id": "a001", "reason_type": "relevance",
                         "reason": "not his morning"}]})
        out, _ = run("picks-sync", "--run", rd, expect=1)
        check("a beat story picked over a passed-over topic story is caught",
              has(out, "dropped for relevance"), str(out.get("problems")))

        write(rd / "picks" / "picks.json", {
            "picks": [{"id": "a002", "tag": "BODY"}],
            "dropped": [{"id": "a001", "reason_type": "evidence",
                         "reason": "its only figure is unsourced"}]})
        out, _ = run("picks-sync", "--run", rd, expect=0)
        check("dropping a topic story on its evidence is allowed", out["picks"] == 1,
              str(out.get("problems")))

        write(rd / "picks" / "picks.json", {
            "picks": [{"id": "a001", "tag": "LEAD"}, {"id": "a002", "tag": "BODY"}],
            "dropped": []})
        out, _ = run("picks-sync", "--run", rd, expect=0)
        check("the mix is counted for the audit line",
              out["mix"] == {"topic": 1, "beat": 1, "maybe": 0}, str(out.get("mix")))
    finally:
        shutil.rmtree(rd, ignore_errors=True)


def test_write_sections(rd):
    """One writer per section, each seeing only its picks, joined in code."""
    print("\nwrite: one prompt per section, and the stitch")
    picks_before = (rd / "picks" / "picks.json").read_text()
    arts = {a["id"]: a for a in json.loads((rd / "articles.json").read_text())["articles"]}
    ids = sorted(arts)[:3]
    for aid in ids:
        (rd / "notes" / f"{aid}.md").write_text(f"HEADLINE: story {aid}\nKEY FIGURES:\n")
    write(rd / "picks" / "picks.json", {
        "picks": [{"id": ids[0], "tag": "LEAD"}, {"id": ids[1], "tag": "LEAD"},
                  {"id": ids[2], "tag": "WORTH"}], "dropped": []})

    out, _ = run("fill", "write", "--run", rd, "--section", "leads", expect=0)
    text = Path(out["file"]).read_text()
    check("the leads prompt holds the leads and not the worth story",
          f"{ids[0]} · LEAD" in text and f"{ids[1]} · LEAD" in text
          and f"{ids[2]} · WORTH" not in text)
    check("and names the other sections' stories by headline", f"story {ids[2]}" in text)
    check("and asks for one section only, by the template's heading",
          "one section only: `## What leads`" in text)
    out, _ = run("fill", "write", "--run", rd, "--section", "body", expect=0)
    check("a section with no picks gets no prompt and no writer",
          out.get("empty") is True and out.get("launch") is False, str(out))
    out, _ = run("fill", "write", "--run", rd, "--section", "worth", expect=0)
    check("the worth prompt says counterpoints are another writer's",
          "another writer is writing those" in Path(out["file"]).read_text())
    _, r = run("fill", "pick", "--run", rd, "--section", "worth")
    check("--section is refused on any prompt but write", r.returncode == 2)

    def src(a):
        return f"1. [{arts[a]['title']}]({arts[a]['url']}) — Guardian"
    (rd / "brief-leads.md").write_text(
        f"## What leads\n\n### 1. One.\n\nStory.\n\n{src(ids[0])}\n\n"
        f"### 2. Two.\n\nStory.\n\n{src(ids[1])}\n")
    out, _ = run("write-stitch", "--run", rd, expect=1)
    check("refuses while a section with picks has no file",
          any("no brief-worth.md" in p for p in out["problems"]), str(out))
    check("and writes no brief", not (rd / "brief.md").exists())
    (rd / "brief-worth.md").write_text(
        f"```markdown\n## Worth Yaron's attention\n\n### Three.\n\nStory.\n\n{src(ids[2])}\n```\n")
    (rd / "brief-body.md").write_text("## Secondary Topics\n\nstray\n")
    out, _ = run("write-stitch", "--run", rd, expect=0)
    text = (rd / "brief.md").read_text()
    check("joins the sections in the template's order under the date line",
          re.match(r"\*\*Date:\*\* \d{1,2} [A-Z][a-z]+ \d{4} at \d\d:\d\d\n", text)
          and 0 < text.find("## What leads") < text.find("## Worth Yaron"), text[:200])
    check("a fence a writer put around its section is stripped", "```" not in text)
    check("the empty section is left out and its stray file ignored",
          "## Secondary Topics" not in text and out["ignored"] == ["brief-body.md"], str(out))
    check("ends with the X and audit placeholders, in that order",
          text.rstrip().endswith("{{X_SECTION}}\n\n{{AUDIT_LINE}}"), text[-80:])
    check("the stitch is an event of the run",
          any(e["type"] == "brief_stitched"
              for e in json.loads((rd / "run.json").read_text())["events"]))

    (rd / "brief-worth.md").write_text(
        "## Worth Yaron's attention\n\n### Three.\n\nStory.\n\n"
        "1. [x](https://example.com/x) — Guardian\n\n{{AUDIT_LINE}}\n")
    out, _ = run("write-stitch", "--run", rd, expect=1)
    probs = " ".join(out["problems"])
    check("a section missing a picked article's URL is refused",
          ids[2] in probs and arts[ids[2]]["url"] in probs, probs[:200])
    check("a placeholder inside a section is refused", "placeholder" in probs, probs[:200])
    (rd / "brief-leads.md").write_text(f"## Secondary Topics\n\n{src(ids[0])}\n{src(ids[1])}\n")
    out, _ = run("write-stitch", "--run", rd, expect=1)
    check("a section under the wrong heading is refused",
          any("does not start with '## What leads'" in p for p in out["problems"]), str(out))
    check("a refusal leaves the last good brief alone",
          "## What leads" in (rd / "brief.md").read_text())

    for f in ("brief-leads.md", "brief-body.md", "brief-worth.md", "brief.md"):
        (rd / f).unlink(missing_ok=True)
    (rd / "picks" / "picks.json").write_text(picks_before)


def script_const(name):
    """One string constant read out of ybs_run.py, so no test restates it."""
    m = re.search(r'^%s = "(.*)"$' % name, SCRIPT.read_text(), re.M)
    return m.group(1) if m else None


def afternoon_written(tmp, env):
    """An update with its pick made: two stories that moved and one that is new.

    The morning it follows ran three stories, and the two that moved carry the
    second and the first of them, in that order, so every check below on the
    order of the update is a real one: reading the picks as they were written
    would put them the other way round.
    """
    build_morning(tmp, "2026-x_morning_100000", now_iso(-6),
                  links=[f"https://www.theguardian.com/m/{i}" for i in (1, 2, 3)],
                  picks=["a101", "a102", "a103"])
    rd, _ = afternoon_run(tmp, env, ["a001", "a002", "a003"],
                          {"a001": "m:a102", "a002": "m:a101"})
    write(rd / "picks" / "picks.json", {
        "picks": [{"id": "a001", "tag": "MOVED", "kind": "development", "why": "x"},
                  {"id": "a002", "tag": "MOVED", "kind": "confirmation", "why": "x"},
                  {"id": "a003", "tag": "NEW", "why": "x"}],
        "dropped": []})
    return rd


def section_file(rd, name, heading, stories):
    """One writer's reply, written by hand: a heading, then its stories."""
    out = [f"## {heading}", ""]
    for head, aid in stories:
        out += [f"### {head}", "", "The story.", "",
                f"1. [headline of {aid}](https://example.com/{aid}) — Guardian", ""]
    (rd / f"brief-{name}.md").write_text("\n".join(out), encoding="utf-8")


def test_write_afternoon():
    """The update's two writers, and the stitch that joins them.

    Everything runs inside a runs folder of its own, named by YBS_RUNS_DIR, so
    the morning being updated is one this test wrote.
    """
    print("\nwrite: the afternoon's two sections")
    tmp = Path(tempfile.mkdtemp(prefix="ybs-runs-"))
    env = {"YBS_RUNS_DIR": str(tmp)}
    try:
        rd = afternoon_written(tmp, env)

        _, r = run("fill", "write", "--run", rd, "--section", "leads", expect=2)
        check("a morning section is refused in an update",
              "is not a section of a afternoon run" in r.stderr, r.stderr.strip()[:200])

        out, _ = run("fill", "write", "--run", rd, "--section", "moved", expect=0)
        text = Path(out["file"]).read_text()
        check("no placeholder is left unfilled in the update's write prompt",
              out["unfilled"] == [], str(out))
        check("the head of the brief names the morning it updates, by its time",
              "**Updates:** the morning brief of 10:00" in text,
              text[text.find("**Updates:**"):][:80])
        check("the moved writer is asked for its own section",
              "one section only: `## What moved`" in text)
        check("two writers, not three, are at work on an update",
              "Two writers are at work" in text)
        check("and it is told the heading opens with the kind",
              "opens with the pick's kind" in text)
        check("an update carries no counterpoints, and says so",
              "the afternoon update carries no counterpoints" in text)
        check("each moved story arrives with the line the morning had",
              "THE MORNING HAD: the morning's story a101" in text
              and "WHAT HAPPENED: what a101 established at ten" in text,
              text[text.find("THE MORNING HAD"):][:200])
        check("the moved stories come in the morning's order, not the pick's",
              0 < text.find("a002 · MOVED") < text.find("a001 · MOVED"),
              f"a002 at {text.find('a002 · MOVED')}, a001 at {text.find('a001 · MOVED')}")
        check("and each one carries the kind its heading has to open with",
              "a001 · MOVED · development" in text, text[text.find("a001 ·"):][:60])
        check("the new story is another writer's", "a003 · NEW" not in text)

        out, _ = run("fill", "write", "--run", rd, "--section", "new", expect=0)
        text = Path(out["file"]).read_text()
        check("the new writer gets the story the morning never had",
              "a003 · NEW" in text and "a001 · MOVED" not in text)

        # The stitch: the kind on every heading, and the morning's order.
        section_file(rd, "new", "New since the morning",
                     [("Something the morning did not have.", "a003")])
        section_file(rd, "moved", "What moved",
                     [("Something was confirmed.", "a002"),
                      ("Something developed.", "a001")])
        out, _ = run("write-stitch", "--run", rd, expect=1)
        check("a moved story whose heading does not say how it moved is refused",
              any("does not open with Development" in p for p in out["problems"]),
              str(out.get("problems")))

        section_file(rd, "moved", "What moved",
                     [("Development - Something developed.", "a001"),
                      ("Confirmation - Something was confirmed.", "a002")])
        out, _ = run("write-stitch", "--run", rd, expect=1)
        check("and so is a section that runs them in another order",
              any("in another order" in p for p in out["problems"]),
              str(out.get("problems")))

        section_file(rd, "moved", "What moved",
                     [("Confirmation - Something was confirmed.", "a002"),
                      ("Development - Something developed.", "a001")])
        out, _ = run("write-stitch", "--run", rd, expect=0)
        text = (rd / "brief.md").read_text()
        check("the update joins in the template's order, new first",
              0 < text.find("## New since the morning") < text.find("## What moved"),
              text[:200])
        check("its head says which brief it updates",
              "**Updates:** the morning brief of 10:00" in text, text[:200])
        check("and it ends with the X and audit placeholders",
              text.rstrip().endswith("{{X_SECTION}}\n\n{{AUDIT_LINE}}"), text[-80:])

        # Nothing picked at all: the true answer to a quiet afternoon.
        write(rd / "picks" / "picks.json", {"picks": [], "dropped": []})
        out, _ = run("write-stitch", "--run", rd, expect=0)
        text = (rd / "brief.md").read_text()
        empty = script_const("EMPTY_UPDATE_LINE")
        check("an update that picked nothing is a brief, not a failure",
              out["ok"] and out["empty"] is True and out["sections"] == [], str(out))
        check("and it is the head, the one sentence, and nothing else",
              bool(empty) and empty in text and "## " not in text
              and "**Updates:** the morning brief of 10:00" in text, repr(text))
        check("with the two lines code still fills after it",
              text.rstrip().endswith("{{X_SECTION}}\n\n{{AUDIT_LINE}}"), repr(text[-60:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_write_stitch_morning_still_dies():
    """A morning brief with no picks is still a failure, as it always was."""
    print("\nwrite-stitch: a morning with nothing in it")
    tmp = Path(tempfile.mkdtemp(prefix="ybs-runs-"))
    env = {"YBS_RUNS_DIR": str(tmp)}
    try:
        out, _ = run("start", "--slot", "morning", expect=0, env=env)
        rd = Path(out["run_dir"])
        write(rd / "picks" / "picks.json", {"picks": [], "dropped": []})
        _, r = run("write-stitch", "--run", rd, expect=2)
        check("no picks and no brief in a morning run",
              "nothing to stitch" in r.stderr and not (rd / "brief.md").exists(),
              r.stderr.strip()[:160])
        _, r = run("fill", "write", "--run", rd, "--section", "new", expect=2)
        check("and an update's section is refused in a morning run",
              "is not a section of a morning run" in r.stderr, r.stderr.strip()[:200])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_audit_afternoon():
    """The update's audit line counts what an update is judged on."""
    print("\naudit-line: the afternoon's own shape")
    tmp = Path(tempfile.mkdtemp(prefix="ybs-runs-"))
    env = {"YBS_RUNS_DIR": str(tmp)}
    try:
        rd = afternoon_written(tmp, env)
        run("picks-sync", "--run", rd, expect=0)
        data = json.loads((rd / "run.json").read_text())
        data["counts"].update({
            "sources_ok": 6, "screened": 12, "seen_this_morning": 30, "kept": 9,
            "notes": 4, "notes_struck": 1, "small_new_items": 1,
            "items_by_group": {"follow-read": 2, "follow-maybe": 1, "beat-read": 2}})
        data["sources"] = {f"s{i}": {} for i in range(6)}
        write(rd / "run.json", data)

        line, _ = run("audit-line", "--run", rd, expect=0)
        check("it opens by naming the brief it updates",
              line.startswith("Audit (afternoon, updates 2026-x_morning_100000): "),
              repr(line)[:120])
        check("it counts what is new against what the morning already saw",
              "12 articles new since the morning (30 already seen)" in line,
              repr(line)[:300])
        check("it says how many items carried a morning story and how many were "
              "too small",
              "5 news items (3 following a morning story, 1 new but too small to "
              "read)" in line, repr(line)[:400])
        check("it counts the new stories and the moved ones by kind",
              "1 new · 2 moved (1 development, 1 confirmation, 0 reversals, "
              "0 corrections)" in line, repr(line)[:500])
        check("an update reports no counterpoints, having none to run",
              "counterpoints" not in line, repr(line)[:500])
        check("and no picks-by-group bit, which is the morning's question",
              "picks by group" not in line, repr(line)[:500])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_audit_and_close(rd):
    print("\naudit + close")
    run("event", "--run", rd, "--type", "reader_failed", "--detail", "a003 timed out",
        "--article", "a003", "--retry", expect=0)
    line, _ = run("audit-line", "--run", rd, expect=0)
    check("audit line is one line and mentions retries",
          isinstance(line, str) and line.count("\n") <= 1 and "1 retries" in line, repr(line)[:120])
    check("counts the real counterpoint, not the NONE", "1 counterpoints" in line,
          repr(line)[:200])
    check("reports which groups the picks came from", "picks by group:" in line,
          repr(line)[:300])
    check("reports how fresh the topic profile was", "profile of " in line,
          repr(line)[:300])
    check("reports the undated links it dropped",
          "1 undated links dropped (Guardian 1)" in line, repr(line)[:200])
    run("event", "--run", rd, "--type", "screen_failed", "--source", "guardian", expect=0)
    line, _ = run("audit-line", "--run", rd, expect=0)
    check("a failed screen counts as a failure",
          "3 failures" in line, repr(line)[:300])
    (rd / "brief.md").write_text("# Brief\n\nsome text\n\n{{AUDIT_LINE}}\n")
    run("audit-line", "--run", rd, "--append", expect=0)
    check("fills the template placeholder",
          "{{AUDIT_LINE}}" not in (rd / "brief.md").read_text()
          and "Audit:" in (rd / "brief.md").read_text())
    out, _ = run("close", "--run", rd, expect=0)
    check("writes run-log.md", (rd / "run-log.md").exists())
    check("run.json says completed",
          json.loads((rd / "run.json").read_text())["status"] == "completed")


# ---------------------------------------------------------------- the X run
#
# Nothing here touches the browser, the network or the real x_run.py: YBS_X_RUN
# points x-start at a stub that does in a second what the chain does in six
# minutes. The X run folders the stubs create are removed again, and they are
# the only thing under x-lists/ these tests ever write.

X_BRIEF = """# What the list is moving on

**Run:** 2026-09-06-1246 · **Window:** 2 hours, to 6 September 2026 at 12:46 UTC

## TRENDING

### 1. A member of the list said something worth hearing.

The story, in a paragraph.

- **Storyline:** a storyline name, copied word for word
- **Flags:** CONVERGENCE · VELOCITY
- **Source:** [@handle](https://x.com/handle/status/1)

## CURIOUS

### 2. One account reported something nobody else did.

The second story.

- **Storyline:** another storyline
- **Flags:** none
- **Source:** [@other](https://x.com/other/status/2)

---

2 picks from 7 subjects judged. TRENDING items carry a flag from the list. CURIOUS ones carry none.
"""

X_BRIEF_EMPTY = """# What the list is moving on

**Run:** 2026-09-06-1246 · **Window:** 2 hours, to 6 September 2026 at 12:46 UTC

The window held nothing that reaches the brief.
"""

STUB = """#!/usr/bin/env python3
import sys, time
from pathlib import Path
argv = sys.argv[1:]
run_dir = Path(argv[argv.index("--run-dir") + 1])
run_dir.mkdir(parents=True, exist_ok=True)
print("stub: step 1 (scrape)")
BRIEF
NOTES
time.sleep(SLEEP)
TAIL
sys.exit(CODE)
"""


def stub(where, name, brief=None, notes=0, sleep=0.0, code=0, tail=()):
    """One throwaway x_run.py, doing only what a test needs it to do."""
    body = ("(run_dir / 'brief.md').write_text(%r, encoding='utf-8')" % brief
            if brief else "")
    notes_body = ("\n".join([
        "(run_dir / 'notes').mkdir(exist_ok=True)",
        "[(run_dir / 'notes' / (str(i) + '.md')).write_text('note')"
        " for i in range(" + str(notes) + ")]"]) if notes else "")
    tail_body = "\n".join("print(%r, file=sys.stderr)" % ln for ln in tail)
    text = (STUB.replace("BRIEF", body).replace("NOTES", notes_body)
            .replace("SLEEP", str(sleep)).replace("TAIL", tail_body)
            .replace("CODE", str(code)))
    path = Path(where) / name
    path.write_text(text, encoding="utf-8")
    return {"YBS_X_RUN": str(path)}


def x_dirs_of(rd):
    """The X run folder this run started, so the test can take it away again."""
    x = json.loads((rd / "run.json").read_text()).get("x") or {}
    return Path(x["run_dir"]) if x.get("run_dir") else None


def drop_x(*dirs):
    for d in dirs:
        if d and d.parent.name == "runs" and d.parent.parent.name == "x-lists":
            shutil.rmtree(d, ignore_errors=True)


def test_x_start(tmp):
    print("\nx-start")
    rd, started = new_run(), []
    try:
        env = stub(tmp, "slow.py", brief=X_BRIEF, sleep=6)
        out, _ = run("x-start", "--run", rd, expect=0, env=env)
        started.append(Path(out["x_run_dir"]))
        check("launches and says so", out["status"] == "running" and out["launched"],
              str(out))
        check("the X run folder is named for the minute, under x-lists/runs",
              re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{4}(-\d+)?", Path(out["x_run_dir"]).name)
              is not None and Path(out["x_run_dir"]).parent.parent.name == "x-lists",
              out["x_run_dir"])
        x = json.loads((rd / "run.json").read_text())["x"]
        check("records the folder, the pid and the log",
              x["run_dir"] == out["x_run_dir"] and isinstance(x["pid"], int)
              and Path(x["log"]).exists(), str(x))
        check("logs that it started",
              any(e["type"] == "x_started"
                  for e in json.loads((rd / "run.json").read_text())["events"]))

        out, _ = run("x-start", "--run", rd, expect=0, env=env)
        check("refuses a second start while one is running",
              out["status"] == "running" and out["launched"] is False, str(out))
        check("the brief written early is not a finish signal: the pid decides",
              (Path(x["run_dir"]) / "brief.md").exists()
              and out["status"] == "running", str(out))
        out, _ = run("x-wait", "--run", rd, expect=0, env=env)
        check("x-wait returns completed once the stub is gone",
              out["status"] == "completed", str(out))
        out, _ = run("x-start", "--run", rd, "--retry", expect=0, env=env)
        check("a completed run is never relaunched", out["launched"] is False, str(out))
    finally:
        drop_x(*started)
        shutil.rmtree(rd, ignore_errors=True)


def test_x_failure(tmp):
    print("\nx-start / x-wait: failure")
    rd, started = new_run(), []
    try:
        env = stub(tmp, "boom.py", code=1,
                   tail=["Traceback (most recent call last):",
                         "ERROR: step 1 (scrape) failed: not signed in to X"])
        run("x-start", "--run", rd, expect=0, env=env)
        started.append(x_dirs_of(rd))
        out, _ = run("x-wait", "--run", rd, expect=0, env=env)
        check("a stub that writes no brief is failed", out["status"] == "failed", str(out))
        check("the reason is the log's last ERROR line",
              out["reason"].endswith("not signed in to X"), str(out.get("reason")))
        check("and the failure is an event",
              any(e["type"] == "x_failed"
                  for e in json.loads((rd / "run.json").read_text())["events"]))

        out, _ = run("x-start", "--run", rd, expect=0, env=env)
        check("a failed run is not relaunched without --retry",
              out["launched"] is False, str(out))

        env2 = stub(tmp, "quiet.py", code=1, tail=["  File \"x_run.py\", line 3",
                                                   "KeyError: 'x_window_hours'"])
        out, _ = run("x-start", "--run", rd, "--retry", expect=0, env=env2)
        started.append(Path(out["x_run_dir"]))
        check("--retry launches once", out["launched"] and out["status"] == "running",
              str(out))
        check("and counts the retry",
              json.loads((rd / "run.json").read_text())["x"]["retries"] == 1)
        out, _ = run("x-wait", "--run", rd, expect=0, env=env2)
        check("with no ERROR line the reason is the log's last line",
              out["reason"].startswith("KeyError"), str(out.get("reason")))
        out, _ = run("x-start", "--run", rd, "--retry", expect=0, env=env2)
        check("a second --retry is refused", out["launched"] is False, str(out))
    finally:
        drop_x(*started)
        shutil.rmtree(rd, ignore_errors=True)


RESUME_STUB = '''#!/usr/bin/env python3
import sys
from pathlib import Path
argv = sys.argv[1:]
run_dir = Path(argv[argv.index("--run-dir") + 1])
run_dir.mkdir(parents=True, exist_ok=True)
with (run_dir / "argv.txt").open("a", encoding="utf-8") as f:
    f.write(" ".join(argv) + "\\n")
print("-- step 1 (scrape): 40 tweet(s)")
print("-- step 2 (filter): 4 survivor(s)")
print("-- step 3 (read): 4 link(s) in 2 batch(es) of 2")
print("ERROR: step 3 (read) finished but 2 link(s) in links.md have no note",
      file=sys.stderr)
sys.exit(1)
'''


def resume_stub(where, name):
    path = Path(where) / name
    path.write_text(RESUME_STUB, encoding="utf-8")
    return {"YBS_X_RUN": str(path)}


def test_x_retry_resumes(tmp):
    """--retry after a failure re-runs the SAME folder from the step that
    failed, instead of scraping and re-reading everything (the 2026-09-08 run
    cost 29 minutes that way)."""
    print("\nx-start --retry: resuming the failed run")
    rd, started = new_run(), []
    try:
        env = resume_stub(tmp, "step3-fail.py")
        out, _ = run("x-start", "--run", rd, expect=0, env=env)
        first = Path(out["x_run_dir"])
        started.append(first)
        out, _ = run("x-wait", "--run", rd, expect=0, env=env)
        check("the stub failed at step 3", out["status"] == "failed", str(out))

        out, _ = run("x-start", "--run", rd, "--retry", expect=0, env=env)
        check("--retry says it resumed, and from which step",
              out.get("resumed") is True and out.get("from_step") == 3, str(out))
        check("and it reused the failed run's own folder",
              out["x_run_dir"] == str(first), str(out))
        run("x-wait", "--run", rd, expect=0, env=env)
        argv = (first / "argv.txt").read_text().splitlines()
        check("the chain was launched a second time, from step 3",
              len(argv) == 2 and "--from 3" in argv[1], str(argv))
        check("the retry event says what it resumed",
              any(e["type"] == "x_retry" and "resumed" in e.get("detail", "")
                  and "step 3" in e.get("detail", "")
                  for e in json.loads((rd / "run.json").read_text())["events"]),
              str(json.loads((rd / "run.json").read_text())["events"][-1]))
    finally:
        drop_x(*started)
        shutil.rmtree(rd, ignore_errors=True)


def test_x_retry_falls_back_to_a_fresh_run(tmp):
    """No folder to resume, no resuming: the retry starts over from step 1,
    exactly as it did before, and says so."""
    print("\nx-start --retry: nothing to resume")
    rd, started = new_run(), []
    try:
        env = resume_stub(tmp, "step3-fail-2.py")
        out, _ = run("x-start", "--run", rd, expect=0, env=env)
        first = Path(out["x_run_dir"])
        started.append(first)
        run("x-wait", "--run", rd, expect=0, env=env)
        shutil.rmtree(first, ignore_errors=True)

        out, _ = run("x-start", "--run", rd, "--retry", expect=0, env=env)
        started.append(Path(out["x_run_dir"]))
        check("a missing folder falls back to a fresh run",
              out.get("resumed") is False and out["launched"], str(out))
        check("and the note says why", "folder is gone" in (out.get("note") or ""),
              str(out.get("note")))
        check("and a folder was made for it", Path(out["x_run_dir"]).is_dir(), str(out))
        run("x-wait", "--run", rd, expect=0, env=env)
        # A fresh folder holds only this launch's argv -- and within the same
        # minute it may even be given the deleted folder's name, so counting
        # the launches is the honest test, not comparing the two names.
        argv = (Path(out["x_run_dir"]) / "argv.txt").read_text().splitlines()
        check("and it was launched from the top, with no --from",
              len(argv) == 1 and "--from" not in argv[0], str(argv))
    finally:
        drop_x(*started)
        shutil.rmtree(rd, ignore_errors=True)


def test_x_skipped():
    print("\nx-start: no pipeline to start")
    rd = new_run()
    try:
        out, _ = run("x-start", "--run", rd, expect=0,
                     env={"YBS_X_RUN": str(ROOT / "no-such-x_run.py")})
        check("a missing X pipeline is skipped, never a crash",
              out["status"] == "skipped" and out["launched"] is False, str(out))
        check("and the reason names the missing file",
              "no-such-x_run.py" in (out.get("reason") or ""), str(out))
        line, _ = run("audit-line", "--run", rd, expect=0)
        check("the audit line says X was skipped", "X: none (skipped:" in line,
              repr(line)[:200])
    finally:
        shutil.rmtree(rd, ignore_errors=True)


def test_x_timeout(tmp):
    print("\nx-wait: out of time")
    rd, started = new_run(), []
    try:
        env = stub(tmp, "hang.py", sleep=90)
        out, _ = run("x-start", "--run", rd, expect=0, env=env)
        started.append(Path(out["x_run_dir"]))
        pid = out["pid"]
        out, _ = run("x-wait", "--run", rd, "--timeout-seconds", 2, expect=0, env=env)
        check("a run that never ends is failed on time",
              out["status"] == "failed" and "timeout" in (out.get("reason") or ""),
              str(out))
        time.sleep(0.5)
        alive = subprocess.run(["ps", "-p", str(pid)], capture_output=True).returncode == 0
        check("and its process group is gone, not left running", not alive)
    finally:
        drop_x(*started)
        shutil.rmtree(rd, ignore_errors=True)


BRIEF_BODY = ("# Morning brief\n\n## What leads\n\n### 1. A story.\n\ntext\n\n")


def merged_run(tmp, brief, notes=3, tail="{{X_SECTION}}\n{{AUDIT_LINE}}\n"):
    """A run whose stub has already finished, its brief.md waiting to be merged."""
    rd = new_run()
    env = stub(tmp, "done-%s.py" % notes, brief=brief, notes=notes)
    run("x-start", "--run", rd, expect=0, env=env)
    run("x-wait", "--run", rd, expect=0, env=env)
    (rd / "brief.md").write_text(BRIEF_BODY + tail)
    return rd


def test_x_merge(tmp):
    print("\nx-merge")
    rd = merged_run(tmp, X_BRIEF)
    xdir = x_dirs_of(rd)
    try:
        out, _ = run("x-merge", "--run", rd, expect=0)
        text = (rd / "brief.md").read_text()
        check("says what it merged", out["merged"] and out["status"] == "merged", str(out))
        check("the X title becomes a section of the brief",
              "\n## What the list is moving on\n" in text, text[-900:])
        check("its sections drop a level", "\n### TRENDING\n" in text
              and "\n### CURIOUS\n" in text, text[-900:])
        check("its items drop a level too", "\n#### 1. A member" in text, text[-900:])
        check("the run folder name is dropped, the window kept",
              "**Run:**" not in text and "**Window:** 2 hours" in text, text[-900:])
        check("the bullets and the closing line are carried as they are",
              "- **Flags:** CONVERGENCE · VELOCITY" in text
              and "2 picks from 7 subjects judged." in text, text[-900:])
        check("the X section lands above the audit line",
              text.find("## What the list") < text.find("{{AUDIT_LINE}}"))
        check("nothing is left of the placeholder", "{{X_SECTION}}" not in text)
        counts = json.loads((rd / "run.json").read_text())["counts"]
        check("counts the picks, the subjects and the tweets read",
              (counts["x_picks"], counts["x_subjects"], counts["x_tweets_read"])
              == (2, 7, 3), str(counts))
        check("the X run's own brief is not touched",
              (xdir / "brief.md").read_text() == X_BRIEF)
        out, _ = run("x-merge", "--run", rd, expect=0)
        check("refuses to merge twice", out["merged"] is False, str(out))
        check("and the section is in the brief once",
              (rd / "brief.md").read_text().count("## What the list") == 1)
        line, _ = run("audit-line", "--run", rd, expect=0)
        check("the audit line carries the counts",
              "X: 2 picks from 7 subjects, 3 tweets read" in line, repr(line)[:300])
    finally:
        drop_x(xdir)
        shutil.rmtree(rd, ignore_errors=True)


def test_x_merge_shapes(tmp):
    print("\nx-merge: the other shapes")
    # The write agent dropped the placeholder.
    rd = merged_run(tmp, X_BRIEF, notes=1, tail="{{AUDIT_LINE}}\n")
    xdir = x_dirs_of(rd)
    try:
        run("x-merge", "--run", rd, expect=0)
        text = (rd / "brief.md").read_text()
        check("without the placeholder it still lands above the audit line",
              0 < text.find("## What the list") < text.find("{{AUDIT_LINE}}"), text[-400:])
    finally:
        drop_x(xdir)
        shutil.rmtree(rd, ignore_errors=True)

    # The audit line is already filled in.
    rd = merged_run(tmp, X_BRIEF, notes=1, tail="")
    xdir = x_dirs_of(rd)
    try:
        run("audit-line", "--run", rd, "--append", expect=0)
        run("x-merge", "--run", rd, expect=0)
        text = (rd / "brief.md").read_text()
        check("an audit line already written is still the last line",
              0 < text.find("## What the list") < text.find("Audit: "), text[-400:])
    finally:
        drop_x(xdir)
        shutil.rmtree(rd, ignore_errors=True)

    # A run that found nothing worth carrying.
    rd = merged_run(tmp, X_BRIEF_EMPTY, notes=0)
    xdir = x_dirs_of(rd)
    try:
        out, _ = run("x-merge", "--run", rd, expect=0)
        text = (rd / "brief.md").read_text()
        check("a run with no picks is carried the same way, at zero",
              "## What the list is moving on" in text
              and "nothing that reaches the brief" in text
              and (out["x_picks"], out["x_subjects"]) == (0, 0), str(out))
    finally:
        drop_x(xdir)
        shutil.rmtree(rd, ignore_errors=True)

    # A failed run leaves no section at all: the audit line says why.
    rd = new_run()
    env = stub(tmp, "gone.py", code=1, tail=["ERROR: the list would not load"])
    try:
        run("x-start", "--run", rd, expect=0, env=env)
        xdir = x_dirs_of(rd)
        run("x-wait", "--run", rd, expect=0, env=env)
        (rd / "brief.md").write_text(BRIEF_BODY + "{{X_SECTION}}\n{{AUDIT_LINE}}\n")
        out, _ = run("x-merge", "--run", rd, expect=0)
        text = (rd / "brief.md").read_text()
        check("a failed X run leaves no heading and no placeholder",
              "{{X_SECTION}}" not in text and "What the list" not in text
              and out["merged"] is False, text[-300:])
        check("the brief is otherwise untouched",
              text == BRIEF_BODY + "{{AUDIT_LINE}}\n", repr(text[-200:]))
        line, _ = run("audit-line", "--run", rd, expect=0)
        check("and the audit line says X failed, with the reason",
              "X: none (failed: ERROR: the list would not load)" in line,
              repr(line)[:300])
    finally:
        drop_x(xdir)
        shutil.rmtree(rd, ignore_errors=True)


def test_x_afternoon(tmp):
    """The update runs the X pipeline exactly as the morning does.

    Same launch, same merge, same bit in the audit line: the only thing the slot
    changes is what the audit line says around it.
    """
    print("\nx-start and x-merge: the afternoon")
    runs = Path(tempfile.mkdtemp(prefix="ybs-runs-"))
    env = {"YBS_RUNS_DIR": str(runs)}
    xdir = None
    try:
        rd = afternoon_written(runs, env)
        env = {**env, **stub(tmp, "afternoon.py", brief=X_BRIEF, notes=2)}
        out, _ = run("x-start", "--run", rd, expect=0, env=env)
        xdir = Path(out["x_run_dir"])
        check("an update launches the X run the way the morning does",
              out["status"] == "running", str(out))
        run("x-wait", "--run", rd, expect=0, env=env)

        section_file(rd, "new", "New since the morning",
                     [("Something the morning did not have.", "a003")])
        section_file(rd, "moved", "What moved",
                     [("Confirmation - Something was confirmed.", "a002"),
                      ("Development - Something developed.", "a001")])
        run("write-stitch", "--run", rd, expect=0)
        run("x-merge", "--run", rd, expect=0)
        text = (rd / "brief.md").read_text()
        check("the X section lands above the audit line of an update",
              0 < text.find("## What the list") < text.find("{{AUDIT_LINE}}"),
              text[-300:])
        run("audit-line", "--run", rd, "--append", expect=0)
        text = (rd / "brief.md").read_text()
        check("and the update's audit line carries the X bit",
              "Audit (afternoon, updates " in text
              and "X: 2 picks from 7 subjects, 2 tweets read" in text,
              text[-300:])

        # An audit line already written is still what x-merge aims above, and
        # an update's opens with more than the word Audit.
        state = json.loads((rd / "run.json").read_text())
        state["x"]["status"] = "completed"
        write(rd / "run.json", state)
        (rd / "brief.md").write_text(
            "**Date:** 9 September 2026 at 16:00\n\n## What moved\n\ntext\n\n"
            + [l for l in text.splitlines() if l.startswith("Audit (")][0] + "\n")
        run("x-merge", "--run", rd, expect=0)
        after = (rd / "brief.md").read_text()
        check("an update's audit line already written is still the last line",
              0 < after.find("## What the list") < after.find("Audit (afternoon"),
              after[-300:])
    finally:
        drop_x(xdir)
        shutil.rmtree(runs, ignore_errors=True)


def test_sources_halves():
    """sources.md holds the news front pages and, at the bottom, the X lists.
    A screener agent must never be sent to x.com, so the two halves are read
    by two commands and the X section is invisible to `read_sources`."""
    print("\nsources: news pages and X lists stay apart")
    out, _ = run("sources")
    news = out["sources"]
    xlists = out["x_lists"]
    check("the news sources are there", len(news) >= 1, str(len(news)))
    check("no news source is an X list",
          not [s for s in news if "x.com" in s["front_page"]],
          str([s["front_page"] for s in news if "x.com" in s["front_page"]]))
    check("the X lists are read separately", len(xlists) >= 1, str(xlists))
    for row in xlists:
        check(f"{row['name']} is an x.com list", "x.com/i/lists/" in row["url"], row["url"])
        check(f"{row['name']} has a slug", bool(row["slug"]), str(row))


def load_script():
    """Import ybs_run itself. `read_sources` takes a root, so a scratch
    sources.md can be read without a scratch copy of the whole project."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ybs_run_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_sources_third_part():
    """An older sources.md ended a paid site's line with a word that proved the
    login was alive. Nothing reads it any more. The line still works, the extra
    part is dropped, and the reader of the file is told once to delete it."""
    print("\nsources: a stale third part is dropped and named")
    mod = load_script()
    tmp = Path(tempfile.mkdtemp(prefix="ybs-sources-"))
    try:
        (tmp / "sources.md").write_text(
            "# Sources\n\n1. Guardian - https://www.theguardian.com/\n"
            "2. Paper - https://example.com/news/ - Sign Out\n", encoding="utf-8")
        rows, notices = mod.read_sources(tmp)
        check("both lines are read", len(rows) == 2, str(rows))
        check("no row carries a marker",
              not [r for r in rows if "marker" in r], str(rows))
        check("the third part is not part of the link",
              rows[1]["front_page"] == "https://example.com/news/", str(rows[1]))
        check("the third part is not part of the name",
              rows[1]["name"] == "Paper", str(rows[1]))
        check("one notice, naming the source", len(notices) == 1
              and '"Paper"' in notices[0] and "delete it" in notices[0],
              str(notices))
        check("a two-part line earns no notice",
              "Guardian" not in " ".join(notices), str(notices))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_settings_halves():
    """One settings.md holds both halves of the run. This script must read the
    article brief's `## Numbers` and `## Models` and nothing else: the X list
    names a step `cluster` too, and its rows would quietly overwrite ours."""
    print("\nsettings: the two halves stay apart")
    out, _ = run("settings")
    check("the article numbers are there", out["picks_max"] == 15, str(out.get("picks_max")))
    check("the article models are there", out["counterpoint_model"] == "opus",
          str(out.get("counterpoint_model")))
    # The X half's cluster row is opus/high; the article brief's is medium.
    check("cluster is the article brief's own row", out["cluster_effort"] == "medium",
          str(out.get("cluster_effort")))
    for key in ("x_window_hours", "x_picks_max", "x_account", "judge_model",
                "verify_check_7_model"):
        check(f"the X list's {key} is not read here", key not in out, str(out.get(key)))
    check("except x_wait_minutes_max, which is ours", out["x_wait_minutes_max"] == 30,
          str(out.get("x_wait_minutes_max")))


def main():
    rd = new_run()
    print(f"test run: {rd.name}")
    try:
        test_settings_halves()
        test_sources_halves()
        test_sources_third_part()
        test_screen_sync(rd)
        test_afternoon_base()
        test_screen_attempts()
        test_screen_stragglers()
        test_screen_prompt_is_safe_to_retry()
        test_dates()
        test_triage(rd)
        test_items(rd)
        test_items_afternoon()
        test_selection()
        test_cluster_parts()
        test_read_list(rd)
        test_picks(rd)
        test_picks_afternoon()
        test_pick_prompt_per_slot()
        test_pick_groups()
        test_checks(rd)
        test_counterpoint_fill(rd)
        test_write_sections(rd)
        test_write_afternoon()
        test_write_stitch_morning_still_dies()
        test_audit_afternoon()
        test_audit_and_close(rd)
    finally:
        shutil.rmtree(rd, ignore_errors=True)
    tmp = tempfile.mkdtemp(prefix="ybs-x-stub-")
    try:
        test_x_start(tmp)
        test_x_failure(tmp)
        test_x_retry_resumes(tmp)
        test_x_retry_falls_back_to_a_fresh_run(tmp)
        test_x_skipped()
        test_x_timeout(tmp)
        test_x_merge(tmp)
        test_x_merge_shapes(tmp)
        test_x_afternoon(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
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
