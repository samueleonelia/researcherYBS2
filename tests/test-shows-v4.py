#!/usr/bin/env python3
"""Checks the show archive's bookkeeping, without a browser and without a model.

Every test runs against a throwaway archive folder, so the real shows/ is never
touched. What is checked is the part no agent can be trusted with: which shows
are excluded, what a saved transcript panel turns into, and whether a profile
the agent wrote is well formed before the brief starts reading it.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".claude" / "skills" / "ybs-shows"
SCRIPT = SKILL / "scripts" / "ybs_shows.py"
FAILURES = []
sys.path.insert(0, str(SCRIPT.parent))
import ybs_shows as S                                        # noqa: E402


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f" {detail}"))
    if not cond:
        FAILURES.append(f"{name} {detail}")


def run(tmp, *args):
    r = subprocess.run([sys.executable, str(SCRIPT)] + [str(a) for a in args] +
                       ["--shows", str(tmp)], capture_output=True, text=True, cwd=ROOT)
    try:
        return json.loads(r.stdout), r.returncode
    except json.JSONDecodeError:
        return r.stdout, r.returncode


# ------------------------------------------------------------ settings

def test_settings():
    print("\nsettings")
    s = S.load_settings()
    check("the channel is a streams page", "youtube.com" in s["channel"])
    check("shows_for_profile is a number", isinstance(s["shows_for_profile"], int))
    check("the exclusions are a list of phrases",
          isinstance(s["excluded_titles"], list) and len(s["excluded_titles"]) >= 2)


def test_exclusions():
    print("\nwhich shows the profile may learn from")
    check("an AMA is excluded", S.is_excluded("AMA & Hangout | Yaron Brook Show"))
    check("a dialogue is excluded",
          S.is_excluded("Yaron & Nikos Dialogues: Free Will"))
    check("the case does not matter", S.is_excluded("ama & hangout — replay"))
    check("an ordinary show is kept",
          not S.is_excluded("Tariffs; Meta; ABC; Russia | Yaron Brook Show"))
    check("'ama' inside another word does not exclude",
          not S.is_excluded("Obamacare and the drug war | Yaron Brook Show"))


# ------------------------------------------------------- reading a panel

PANEL = """0:00
welcome to the yaron brook show
0:04
welcome to the yaron brook show today we talk about tariffs
0:09
[Music]
0:11
tariffs are a tax americans pay themselves
1:02:15
and that is the whole point
"""


def test_clean():
    print("\nturning a saved panel into words")
    lines = S.clean(PANEL)
    text = " ".join(lines)
    check("timestamps are gone", ":" not in text or "0:00" not in text)
    check("the music marker is gone", "[Music]" not in text)
    check("a rolling repeat is collapsed once",
          text.count("welcome to the yaron brook show") == 1)
    check("the longer line survives the collapse", "today we talk about tariffs" in text)
    check("later speech is kept", "and that is the whole point" in text)
    check("an hour-long timestamp is dropped too", "1:02:15" not in text)


def test_dates_and_ids():
    print("\ndates and ids")
    check("a streamed date is read",
          S.find_date("Streamed live on Aug 18, 2026") == "2026-08-18")
    check("a premiere date is read",
          S.find_date("Premiered Sep 3, 2026") == "2026-09-03")
    check("a bare date is read", S.find_date("Jan 7, 2026  1,204 views") == "2026-01-07")
    check("no date is empty, never a guess", S.find_date("Streamed 3 days ago") == "")
    check("a watch url gives its id",
          S.video_id("https://www.youtube.com/watch?v=RdW7wmHwW6w") == "RdW7wmHwW6w")
    check("a live url gives its id",
          S.video_id("https://www.youtube.com/live/RdW7wmHwW6w?feature=share") == "RdW7wmHwW6w")
    check("a page with no id gives nothing", S.video_id("https://example.com/x") == "")


# ------------------------------------------------------------- the flow

def test_agents():
    print("\nthe agents this skill launches")
    skill = (SKILL / "SKILL.md").read_text()
    found = sorted((ROOT / ".claude" / "agents").glob("ybs4-shows-*.md"))
    check("the skill has agents to launch", len(found) == 3, f"found {len(found)}")
    for f in found:
        body = f.read_text()
        check(f"{f.stem} declares a model", "\nmodel:" in body)
        check(f"{f.stem} declares an effort", "\neffort:" in body)
        check(f"{f.stem} is used by SKILL.md", f.stem in skill)
    for name in ("list", "profile"):
        check(f"prompts/{name}.md exists", (SKILL / "prompts" / f"{name}.md").exists())


def test_no_blocking_waits():
    """The bug that killed the 2026-08-24 run, kept out for good.

    The browser's own wait() waits for the page to fall quiet, and a YouTube
    page never does: it hangs until something kills the command. Opening with
    { wait: true } does the same. Every pause in this skill is a plain timer.
    """
    print("\nnothing that waits for a YouTube page to fall quiet")
    files = [SKILL / "prompts" / "list.md"]
    for f in files:
        blocks = re.findall(r"```bash\n(.*?)```", f.read_text(), re.S)
        # The comments warn against both by name; only the code is the offence.
        code = "\n".join(re.sub(r"//.*", "", b) for b in blocks)
        check(f"{f.name} never calls the browser's wait()",
              "await wait(" not in code)
        check(f"{f.name} never opens a page with wait: true",
              "wait: true" not in code)
        check(f"{f.name} pauses on a plain timer instead",
              "setTimeout" in code)


def test_new_and_ingest(tmp):
    print("\nwhat is new, and what ingest makes of it")
    (tmp / "new").mkdir(parents=True, exist_ok=True)
    (tmp / "new" / "listing.json").write_text(json.dumps({"videos": [
        {"id": "aaaaaaaaaaa", "title": "Tariffs; Iran | Yaron Brook Show",
         "url": "https://www.youtube.com/watch?v=aaaaaaaaaaa"},
        {"id": "bbbbbbbbbbb", "title": "AMA & Hangout | Yaron Brook Show",
         "url": "https://www.youtube.com/watch?v=bbbbbbbbbbb"},
    ]}))
    out, _ = run(tmp, "new")
    check("both shows are recorded", out["listed"] == 2 and out["new"] == 2)
    check("the AMA is never offered for fetching",
          [e["id"] for e in out["excluded"]] == ["bbbbbbbbbbb"])
    check("only the real show gets a launch line",
          [t["id"] for t in out["todo"]] == ["aaaaaaaaaaa"])
    check("a launch line carries id, url and archive",
          out["todo"][0]["launch"].count("|") == 2)

    (tmp / "raw").mkdir(parents=True, exist_ok=True)
    (tmp / "raw" / "aaaaaaaaaaa.txt").write_text(PANEL)
    (tmp / "raw" / "aaaaaaaaaaa.meta.json").write_text(json.dumps(
        {"title": "Tariffs; Iran | Yaron Brook Show",
         "info": "Streamed live on Aug 18, 2026  4,102 views"}))
    out, code = run(tmp, "ingest")
    check("the show is ingested", [d["id"] for d in out["ingested"]] == ["aaaaaaaaaaa"])
    check("ingest reports nothing missing", code == 0, str(out))
    md = (tmp / "transcripts" / "aaaaaaaaaaa.md").read_text()
    check("the transcript carries its source", "watch?v=aaaaaaaaaaa" in md)
    check("the transcript carries the date read off the page", "2026-08-18" in md)
    shows = json.loads((tmp / "shows.json").read_text())["shows"]
    by_id = {s["id"]: s for s in shows}
    check("the archive knows the words", by_id["aaaaaaaaaaa"]["words"] > 0)
    check("the AMA is still marked excluded", by_id["bbbbbbbbbbb"]["excluded"])
    check("the AMA has no transcript", not by_id["bbbbbbbbbbb"]["file"])

    # A second ingest must not do the first one's work again: the raw file it
    # read never changes, so the transcript it wrote is still right.
    before = (tmp / "transcripts" / "aaaaaaaaaaa.md").read_text()
    out, code = run(tmp, "ingest")
    check("an ingested show is not ingested twice",
          out["ingested"] == [] and out["already_done"] == 1, str(out))
    check("the transcript is left exactly as it was",
          (tmp / "transcripts" / "aaaaaaaaaaa.md").read_text() == before)
    out, _ = run(tmp, "ingest", "--force")
    check("--force rewrites it anyway",
          [d["id"] for d in out["ingested"]] == ["aaaaaaaaaaa"], str(out))
    (tmp / "transcripts" / "aaaaaaaaaaa.md").unlink()
    out, _ = run(tmp, "ingest")
    check("a transcript that went missing is written again",
          [d["id"] for d in out["ingested"]] == ["aaaaaaaaaaa"], str(out))

    out, _ = run(tmp, "digest-list")
    check("only the usable show needs a digest",
          [t["id"] for t in out["todo"]] == ["aaaaaaaaaaa"])
    out, code = run(tmp, "digest-sync")
    check("a missing digest is reported", code == 1 and out["missing"] == ["aaaaaaaaaaa"])
    (tmp / "digests").mkdir(parents=True, exist_ok=True)
    (tmp / "digests" / "aaaaaaaaaaa.md").write_text("# x\n\n## Topics\n\n- tariffs\n")
    out, code = run(tmp, "digest-sync")
    check("a written digest is recorded", code == 0 and not out["missing"])


def test_check(tmp):
    """The early exit: a run that has nothing to do must find that out cheaply."""
    print("\nis the profile already built from what the channel is showing")
    want = S.SETTINGS["shows_for_profile"]
    ids = [f"vid{i:08d}" for i in range(want)]

    def listing(vids):
        (tmp / "new").mkdir(parents=True, exist_ok=True)
        (tmp / "new" / "listing.json").write_text(json.dumps({"videos": [
            {"id": v, "title": t, "url": f"https://www.youtube.com/watch?v={v}"}
            for v, t in vids]}))

    def profile(vids):
        (tmp / "profile.json").write_text(json.dumps({"shows": vids}))

    ordinary = [(v, f"Show {v} | Yaron Brook Show") for v in ids]

    listing(ordinary)
    profile(ids)
    out, code = run(tmp, "check")
    check("an unchanged channel stops the run", out["current"] and code == 0, str(out))
    check("stopping is spelled out", out["next"] == "stop")

    # The order the page happens to be in is not a reason to rebuild.
    profile(list(reversed(ids)))
    out, code = run(tmp, "check")
    check("the same shows in another order still stop the run", out["current"])

    profile(ids)
    listing([("newshow0001", "Something New | Yaron Brook Show")] + ordinary)
    out, code = run(tmp, "check")
    check("one new show restarts the run", not out["current"] and code == 1)
    check("the new show is named", out["added"] == ["newshow0001"])
    check("the show it pushed out is named", out["gone"] == [ids[-1]])

    # An AMA is never fetched, so it cannot count as a show the profile missed.
    listing([("amanew00001", "AMA & Hangout with Contributors | Yaron Brook Show")] + ordinary)
    out, _ = run(tmp, "check")
    check("a new AMA does not restart the run", out["current"], str(out))

    # A page that scrolled short must never read as "nothing changed".
    listing(ordinary[:3])
    out, code = run(tmp, "check")
    check("a short listing keeps the run going", not out["current"] and code == 1)
    check("a short listing says it was short", "usable shows" in out["reason"])

    listing(ordinary)
    (tmp / "profile.json").unlink()
    out, code = run(tmp, "check")
    check("with no profile the run goes ahead", not out["current"] and code == 1)


GOOD = {
    "storylines": [{"rank": 1, "name": "Iran war with no way to end",
                    "shows": 9, "note": "he keeps asking what winning means"}],
    "themes": [{"rank": 1, "name": "Trump administration",
                "angle": "judged on results"},
               {"rank": 2, "name": "AI and technology", "angle": "nobody defends it"}],
    "moves": {"main": "the right has become as statist as the left",
              "secondary": ["economic power is not political power"]},
}


def test_profile_sync(tmp):
    print("\nthe profile the brief will read")
    bad = dict(GOOD)
    bad["themes"] = [{"rank": 1, "name": "A"}, {"rank": 3, "name": "B"}]
    (tmp / "profile.json").write_text(json.dumps(bad))
    out, code = run(tmp, "profile-sync")
    check("a gap in the ranking is caught", code == 1 and
          any("ranked" in p for p in out["problems"]), str(out))

    dup = json.loads(json.dumps(GOOD))
    dup["themes"][1]["name"] = "Trump administration"
    (tmp / "profile.json").write_text(json.dumps(dup))
    out, code = run(tmp, "profile-sync")
    check("the same theme twice is caught", code == 1 and
          any("twice" in p for p in out["problems"]), str(out))

    empty = json.loads(json.dumps(GOOD))
    empty["moves"] = {"main": "   "}
    (tmp / "profile.json").write_text(json.dumps(empty))
    out, code = run(tmp, "profile-sync")
    check("a profile with no main argument is caught", code == 1, str(out))

    (tmp / "profile.json").write_text(json.dumps(GOOD))
    out, code = run(tmp, "profile-sync")
    check("a well formed profile is accepted", code == 0, str(out))
    p = json.loads((tmp / "profile.json").read_text())
    check("the script stamps the date, not the agent", p.get("built_local_date"))
    check("the script stamps which shows it was built from",
          p.get("shows") == ["aaaaaaaaaaa"])
    md = (tmp / "TOPIC-PROFILE.md").read_text()
    check("the markdown is rendered from the json",
          "Iran war with no way to end" in md and "statist as the left" in md)
    check("the markdown says it is generated", "do not edit by hand" in md)


def test_draft_and_swap(tmp):
    """A draft that fails must never reach the file the brief reads."""
    print("\nthe draft the script promotes")
    live = tmp / "profile.json"
    draft = tmp / "new" / "profile-draft.json"
    draft.parent.mkdir(parents=True, exist_ok=True)

    live.write_text(json.dumps(GOOD))
    run(tmp, "profile-sync")
    good_live = live.read_text()

    broken = json.loads(json.dumps(GOOD))
    broken["themes"] = [{"rank": 1, "name": "A"}, {"rank": 3, "name": "B"}]
    draft.write_text(json.dumps(broken))
    out, code = run(tmp, "profile-sync")
    check("a broken draft is refused", code == 1, str(out))
    check("the live profile is left alone", live.read_text() == good_live)
    check("the refused draft stays for the agent to rewrite", draft.exists())

    fresh = json.loads(json.dumps(GOOD))
    fresh["storylines"][0]["name"] = "Something new entirely"
    draft.write_text(json.dumps(fresh))
    out, code = run(tmp, "profile-sync")
    check("a good draft is promoted", code == 0, str(out))
    check("the live profile now holds the draft",
          "Something new entirely" in live.read_text())
    check("the promoted draft is cleared away", not draft.exists())


def test_ledger(tmp):
    """A theme he did not reach for this fortnight fades; it does not vanish."""
    print("\nthe memory that lets a theme fade")
    draft = tmp / "new" / "profile-draft.json"
    draft.parent.mkdir(parents=True, exist_ok=True)
    limit = S.SETTINGS["themes_max_misses"]

    base = json.loads(json.dumps(GOOD))
    draft.write_text(json.dumps(base))
    run(tmp, "profile-sync")
    led = json.loads((tmp / "ledger.json").read_text())["themes"]
    check("the ledger starts from the first build", len(led) == len(base["themes"]))

    dropped_name = base["themes"][-1]["name"]
    thin = json.loads(json.dumps(base))
    thin["themes"] = thin["themes"][:-1]
    for i, e in enumerate(thin["themes"], start=1):
        e["rank"] = i

    for run_no in range(1, limit):
        draft.write_text(json.dumps(thin))
        out, _ = run(tmp, "profile-sync")
        check(f"an absent theme is carried, build {run_no}",
              dropped_name in out["fading"], str(out))

    p = json.loads((tmp / "profile.json").read_text())
    carried = [e for e in p["themes"] if e.get("fading")]
    check("a carried theme is ranked below the fresh ones",
          carried and carried[-1]["rank"] == len(p["themes"]))
    check("the ranking stays contiguous for the brief",
          [e["rank"] for e in p["themes"]] == list(range(1, len(p["themes"]) + 1)))

    draft.write_text(json.dumps(thin))
    out, _ = run(tmp, "profile-sync")
    check(f"gone after {limit} builds away", dropped_name in out["dropped"], str(out))
    led = json.loads((tmp / "ledger.json").read_text())["themes"]
    check("and gone from the ledger too",
          not any(e["name"] == dropped_name for e in led.values()))


def test_theme_rewording():
    """The agent rewords freely; the ledger must not read that as a new theme."""
    print("\nthe same theme, worded differently")
    same = [("Immigration", "Immigration & open borders"),
            ("Iran & the Strait of Hormuz war", "Iran war"),
            ("China", "China trade & tech competition")]
    for a, b in same:
        known = {S.theme_key(a): {}}
        check(f"{a!r} is matched by {b!r}",
              S.theme_match(S.theme_key(b), known) == S.theme_key(a))
    apart = [("China", "Free speech"), ("Big Tech", "Tariffs & trade"),
             ("Immigration", "Elections & primaries")]
    for a, b in apart:
        known = {S.theme_key(a): {}}
        check(f"{a!r} is not confused with {b!r}",
              S.theme_match(S.theme_key(b), known) == "")


def test_fetch_plan(tmp):
    """fetch must ask for exactly what is missing, and nothing that is not."""
    print("\nwhat fetch decides to go and get")
    data = json.loads((tmp / "shows.json").read_text())
    undated = {s["id"] for s in data["shows"] if not s.get("date") and not s.get("excluded")}
    excluded = {s["id"] for s in data["shows"] if s.get("excluded")}

    out, _ = run(tmp, "fetch", "--only", "nosuchvideo00")
    check("an id that is in no archive asks for nothing",
          out.get("transcripts") == [] and out.get("dates") == [], str(out)[:120])
    check("an excluded show is never fetched",
          not (excluded & {r["id"] for r in out.get("dates", [])}))
    check("the settings name the package fetch uses",
          out.get("package") == S.SETTINGS["transcript_package"], str(out.get("package")))
    check("fetch names the tool the dates depend on", "yt_dlp" in out, str(out)[:120])


def test_no_transcript_is_not_a_failure(tmp):
    """A show YouTube has not captioned yet must cost the run nothing.

    This is the bug that made a forty-four word rate-limit notice look like a
    transcript: the package answers every failure with the same complaint, and
    nothing was reading the flag that said it was a complaint at all.
    """
    print("\na show with no captions yet")
    want = S.SETTINGS["shows_for_profile"]
    ids = [f"cap{i:08d}" for i in range(want)]
    (tmp / "new").mkdir(parents=True, exist_ok=True)

    shows = [{"id": v, "title": f"Show {v} | Yaron Brook Show",
              "url": f"https://www.youtube.com/watch?v={v}", "date": "2026-08-01",
              "file": f"transcripts/{v}.md", "words": 20000,
              "excluded": False, "digest": ""} for v in ids]
    # The one that streamed last night and has no captions yet.
    shows.insert(0, {"id": "nocaps00001", "title": "Last Night | Yaron Brook Show",
                     "url": "https://www.youtube.com/watch?v=nocaps00001",
                     "date": "2026-08-24", "file": "", "words": 0,
                     "excluded": False, "digest": "", "no_transcript": "2026-08-25"})
    (tmp / "shows.json").write_text(json.dumps({"shows": shows}))
    (tmp / "profile.json").write_text(json.dumps({"shows": ids}))
    (tmp / "new" / "listing.json").write_text(json.dumps({"videos": [
        {"id": s["id"], "title": s["title"], "url": s["url"]} for s in shows]}))

    out, code = run(tmp, "check")
    check("a show with no captions does not restart the whole run",
          out["current"] and code == 0, str(out)[:160])
    check("the run is pointed at the cheap fetch, not at agents",
          out["next"] == "fetch-only", str(out.get("next")))
    check("the waiting show is named", out["waiting_for_captions"] == ["nocaps00001"])
    check("it is counted out of the profile's window",
          "nocaps00001" not in out["latest_on_page"])

    out, code = run(tmp, "ingest")
    check("ingest does not call it missing", out["still_missing"] == [], str(out)[:160])
    check("ingest calls it waiting", out["waiting_for_captions"] == ["nocaps00001"])
    check("ingest does not fail the run over it", code == 0)

    # The morning the captions arrive, the show rejoins the window by itself.
    shows[0]["file"] = "transcripts/nocaps00001.md"
    shows[0]["words"] = 21000
    shows[0].pop("no_transcript")
    (tmp / "shows.json").write_text(json.dumps({"shows": shows}))
    out, code = run(tmp, "check")
    check("once captioned it restarts the run", not out["current"] and code == 1)
    check("and it is the show that was added", out["added"] == ["nocaps00001"])


def test_transcript_guards():
    """Nothing the package returns is taken on trust as a transcript."""
    print("\nwhat counts as a transcript")
    floor = S.SETTINGS.get("transcript_words_min", 1000)
    check("settings carry a floor a real show clears", floor >= 100, str(floor))

    src = (SKILL / "scripts" / "ybs_shows.py").read_text(encoding="utf-8")
    check("the tool's own error flag is read", "isError" in src)
    check("the floor is applied, not just declared", "transcript_words_min" in src)

    # The exact notice that was once written to disk as a transcript.
    notice = ("MCP error -32603: YouTube rate limit detected.\nThis could be due to:\n"
              "1.\nToo many requests from your IP\n2.\nYouTube requiring CAPTCHA")
    check("the notice is far below the floor",
          len(notice.split()) < floor, str(len(notice.split())))


def test_captions_verdict():
    """Only yt-dlp's plain answer may be read as 'this show has no captions'."""
    print("\nasking yt-dlp whether captions exist")
    src = (SKILL / "scripts" / "ybs_shows.py").read_text(encoding="utf-8")
    check("the question is asked with --list-subs", "--list-subs" in src)
    check("both of yt-dlp's sentences are required",
          "has no automatic captions" in src and "has no subtitles" in src)
    check("an unanswered question is not a verdict", '{"known": False}' in src)


def test_sentences():
    """The package answers in prose; it has to arrive as lines to be cleaned."""
    print("\nprose split back into lines")
    body = "First one. Second one! Third one? Fourth one."
    parts = [s for s in S.SENTENCE.split(body) if s.strip()]
    check("a sentence per line", len(parts) == 4, str(parts))
    check("clean() then dedupes as always",
          S.clean("\n".join(parts + [parts[-1]])) == parts, str(S.clean("\n".join(parts))))


def test_import_legacy(tmp):
    print("\nseeding from an older folder")
    old = tmp / "old"
    old.mkdir(parents=True, exist_ok=True)
    (old / "01-something.md").write_text(
        "# An older show | Yaron Brook Show\n\n"
        "Source: https://www.youtube.com/watch?v=ccccccccccc\n\n---\n\nwords words\n")
    out, _ = run(tmp, "import-legacy", str(old))
    check("the older show is imported",
          [i["id"] for i in out["imported"]] == ["ccccccccccc"])
    check("its transcript is copied in",
          (tmp / "transcripts" / "ccccccccccc.md").exists())
    out, _ = run(tmp, "import-legacy", str(old))
    check("importing twice adds nothing", out["imported"] == [])


def main():
    test_settings()
    test_exclusions()
    test_clean()
    test_dates_and_ids()
    test_agents()
    test_no_blocking_waits()
    tmp = Path(tempfile.mkdtemp(prefix="ybs-shows-test-"))
    try:
        test_new_and_ingest(tmp)
        check_tmp = Path(tempfile.mkdtemp(prefix="ybs-shows-check-"))
        try:
            test_check(check_tmp)
        finally:
            shutil.rmtree(check_tmp, ignore_errors=True)
        caps_tmp = Path(tempfile.mkdtemp(prefix="ybs-shows-caps-"))
        try:
            test_no_transcript_is_not_a_failure(caps_tmp)
        finally:
            shutil.rmtree(caps_tmp, ignore_errors=True)
        test_profile_sync(tmp)
        test_fetch_plan(tmp)
        test_transcript_guards()
        test_captions_verdict()
        test_import_legacy(tmp)
        test_theme_rewording()
        test_sentences()
        draft_tmp = Path(tempfile.mkdtemp(prefix="ybs-shows-draft-"))
        ledger_tmp = Path(tempfile.mkdtemp(prefix="ybs-shows-ledger-"))
        try:
            test_draft_and_swap(draft_tmp)
            test_ledger(ledger_tmp)
        finally:
            shutil.rmtree(draft_tmp, ignore_errors=True)
            shutil.rmtree(ledger_tmp, ignore_errors=True)
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
