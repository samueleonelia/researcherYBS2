#!/usr/bin/env python3
"""Unit tests for ybs_run.py. No network, no agents, no browser.

Every test builds a run folder, writes the JSON an agent would have produced --
correct in one case, deliberately broken in the next -- and asserts the script
either accepts it or names the exact problem. Exit 0 = all passed.
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
SCRIPT = ROOT / ".claude" / "skills" / "ybs-brief" / "scripts" / "ybs_run.py"
FAILURES = []


def run(*args, expect=None):
    r = subprocess.run([sys.executable, str(SCRIPT)] + [str(a) for a in args],
                       capture_output=True, text=True, cwd=ROOT)
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
                                           "error": "SESSION_DOWN", "links": []})
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
    run("event", "--run", rd, "--type", "SESSION_DOWN", "--source", "guardian", expect=0)
    line, _ = run("audit-line", "--run", rd, expect=0)
    check("a dead login counts as a failure however the type was spelled",
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


def main():
    rd = new_run()
    print(f"test run: {rd.name}")
    try:
        test_screen_sync(rd)
        test_dates()
        test_triage(rd)
        test_items(rd)
        test_selection()
        test_cluster_parts()
        test_read_list(rd)
        test_picks(rd)
        test_pick_groups()
        test_checks(rd)
        test_counterpoint_fill(rd)
        test_audit_and_close(rd)
    finally:
        shutil.rmtree(rd, ignore_errors=True)
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
