#!/usr/bin/env python3
"""ybs_shows.py - bookkeeping for the show archive and the topic profile.

The archive lives in shows/. This script owns shows/shows.json and the stamps
in shows/profile.json; nothing else writes them. Like the brief's script it is
deterministic: no network, no AI, no page parsing. Agents open YouTube in a
browser and save what they see; this script names, cleans, counts and validates.

Commands
  settings                 print settings.md, the only home of every number
  start                    what the archive holds and what is missing
  fill NAME                render one prompt (list, profile)
  new                      shows on the channel that are not in the archive yet
  fetch                    get missing captions and dates with yt-dlp
  ingest                   turn saved caption files into readable transcripts
  digest-list              the shows the profile needs a digest for
  profile-sync             promote the agent's draft to profile.json and render it
  import-legacy DIR        seed the archive from an older folder of transcripts
  event --type T           record something that happened

Exit codes: 0 = ok, 1 = did the job but found a problem, 2 = bad usage / error.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path

VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|/live/|/shorts/)([A-Za-z0-9_-]{11})")
TIMESTAMP = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
NOISE = re.compile(r"\[(Music|Applause|Laughter|Ììà]*)\]", re.I)
DATE_IN_TEXT = re.compile(
    r"(?:Streamed live on|Premiered|Started streaming on)?\s*"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", re.I)
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


# ---------------------------------------------------------------- basics

def die(msg: str, code: int = 2):
    print(json.dumps({"error": msg}, indent=2, ensure_ascii=False))
    sys.exit(code)


def skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def project_root() -> Path:
    """<root>/.claude/skills/ybs-shows/scripts/ybs_shows.py -> <root>"""
    return Path(__file__).resolve().parents[4]


def shows_dir(args=None) -> Path:
    d = Path(args.shows).resolve() if getattr(args, "shows", None) else project_root() / "shows"
    d.mkdir(parents=True, exist_ok=True)
    return d


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON: {e}")


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_settings(path: Path = None) -> dict:
    """The settings.md table. Same shape the brief's settings use."""
    path = path or (skill_dir() / "settings.md")
    if not path.exists():
        die(f"no settings file at {path}")
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        key, raw = cells[0], cells[1]
        if key.lower() == "setting" or set(key) <= set("-: "):
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


SETTINGS = load_settings()


def video_id(url: str) -> str:
    m = VIDEO_ID.search(url or "")
    return m.group(1) if m else ""


def is_excluded(title: str) -> bool:
    """A show the profile must not learn from: an AMA or a dialogue episode."""
    t = (title or "").lower()
    return any(s.lower() in t for s in SETTINGS["excluded_titles"])


def archive(sd: Path) -> dict:
    return load_json(sd / "shows.json", {"shows": []})


def save_archive(sd: Path, data: dict):
    data["shows"].sort(key=lambda s: (s.get("date") or "", s.get("id")), reverse=True)
    write_json(sd / "shows.json", data)


def kept(sd: Path) -> list:
    """Archived shows the profile may learn from, newest first."""
    return [s for s in archive(sd)["shows"]
            if not s.get("excluded") and s.get("file")]


def draft_path(sd: Path) -> Path:
    """Where the profile agent writes. Never the live file.

    The morning brief reads shows/profile.json every day and refuses to run
    without it, so a half-written or rejected profile must never land there.
    The agent writes a draft, this script validates it, and only a draft that
    passes is promoted.
    """
    return sd / "new" / "profile-draft.json"


def ledger_path(sd: Path) -> Path:
    return sd / "ledger.json"


def theme_key(name: str) -> str:
    """A theme name reduced to what is stable about it, for matching runs."""
    stripped = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    return re.sub(r"\s+", " ", stripped).strip()


def theme_match(key: str, known) -> str:
    """The ledger key this theme is, allowing for how the agent worded it.

    The agent rewords freely between runs - "Iran war" one week, "Iran & the
    Strait of Hormuz war" the next - and a ledger that took those for two
    different themes would never let anything fade.

    What survives rewording is the words themselves, not their order or their
    number: a renamed theme keeps the old name's words and adds to them. So one
    name's words being wholly contained in the other's is the test, with a
    straight similarity score as a fallback for a spelling that merely drifted.
    """
    if key in known:
        return key
    words = set(key.split())
    best, score = "", 0.0
    for other in known:
        theirs = set(other.split())
        ratio = SequenceMatcher(None, key, other).ratio()
        if words and theirs and (words <= theirs or theirs <= words):
            ratio = max(ratio, 0.75)
        if ratio > score:
            best, score = other, ratio
    return best if score >= 0.75 else ""


# ------------------------------------------------------------ transcripts

def clean(text: str) -> list:
    """A transcript panel as saved by an agent -> the words that were said.

    The panel is a timestamp line then a line of speech, over and over. Some
    players repeat the previous line as the next one scrolls in, so the same
    rolling-duplicate rule the caption files needed applies here too.
    """
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or TIMESTAMP.match(line):
            continue
        line = NOISE.sub(" ", line)
        line = re.sub(r"^>>\s*", "", line).replace(">>", "")
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)

    out = []
    for line in lines:
        if out and (line == out[-1] or line in out[-1]):
            continue
        if out and out[-1] in line:
            out[-1] = line
            continue
        out.append(line)
    return out


def paragraphs(lines, per=14):
    for i in range(0, len(lines), per):
        yield " ".join(lines[i:i + per])


def find_date(text: str) -> str:
    """The date YouTube prints under a stream, as YYYY-MM-DD. Empty if absent."""
    m = DATE_IN_TEXT.search(text or "")
    if not m:
        return ""
    month = MONTHS.get(m.group(1)[:3].lower())
    if not month:
        return ""
    return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(2)):02d}"


# --------------------------------------------------- fetching what is missing
#
# Two outside tools, because YouTube gives neither one everything.
#
# The captions are gated behind a proof-of-origin token the player generates:
# without it the caption URL answers 200 with an empty body, yt-dlp reports the
# automatic captions as missing, and the transcript panel in the browser is
# inert. The youtube-transcript package deals with that token, so it gets the
# words. It is an MCP server, but a script can speak to it directly, and that
# matters: a show runs to eighteen thousand words, and nothing that long should
# pass through a model that would have to copy it out again.
#
# yt-dlp cannot get those captions but does return the upload date, which the
# package never gives. It needs the browser's session to get past the bot check,
# and those cookies come from ego over CDP - never from the cookie file, which
# is encrypted and would put a password prompt in the middle of a run.

SENTENCE = re.compile(r"(?<=[.!?])\s+")


def have_ytdlp() -> str:
    """The yt-dlp version, or empty if it is not installed."""
    try:
        r = subprocess.run(["yt-dlp", "--version"], capture_output=True,
                           text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


EGO_COOKIES = """
const fs = await import('fs')
await useOrCreateTaskSpace('ybs cookies')
const r = await cdp('Network.getAllCookies')
const all = (r && r.cookies) || []
const keep = all.filter(c => /(^|\\.)(youtube|google)\\.com$/.test(c.domain.replace(/^\\./, '.')))
const lines = ['# Netscape HTTP Cookie File', '']
for (const c of keep) {
  const d = c.domain.startsWith('.') ? c.domain : '.' + c.domain
  lines.push([d, 'TRUE', c.path || '/', c.secure ? 'TRUE' : 'FALSE',
              Math.floor(c.expires > 0 ? c.expires : 2147483647), c.name, c.value].join('\\t'))
}
fs.writeFileSync(process.env.YBS_JAR, lines.join('\\n') + '\\n')
cliLog('cookies ' + keep.length)
await completeTaskSpace('ybs cookies', { keep: false })
"""


def ego_cookies(jar: Path) -> int:
    """Borrow the browser's YouTube session, without touching the cookie file.

    The file on disk is encrypted, and asking the system for the key puts a
    password prompt in front of a run that is supposed to be unattended. The
    browser will simply hand its cookies over if asked through CDP.
    """
    import os
    env = dict(os.environ, YBS_JAR=str(jar))
    try:
        r = subprocess.run(["ego-browser", "nodejs"], input=EGO_COOKIES,
                           capture_output=True, text=True, timeout=180, env=env)
    except (OSError, subprocess.SubprocessError):
        return 0
    m = re.search(r"cookies (\d+)", r.stdout or "")
    return int(m.group(1)) if m and jar.exists() else 0


def ytdlp_meta(vid: str, url: str, jar: Path) -> dict:
    """The title and the day it was streamed. No captions: yt-dlp cannot get those."""
    cmd = ["yt-dlp", "--skip-download", "--simulate", "--no-warnings",
           "--print", "%(id)s\t%(title)s\t%(upload_date)s"]
    if jar and jar.exists():
        cmd += ["--cookies", str(jar)]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return {"id": vid, "ok": False, "why": "yt-dlp timed out"}
    if r.returncode != 0:
        why = (r.stderr or r.stdout or "").strip().splitlines()
        return {"id": vid, "ok": False, "why": (why[-1] if why else "yt-dlp failed")[:200]}
    for line in (r.stdout or "").splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0] == vid:
            date = ""
            if re.fullmatch(r"\d{8}", parts[2]):
                date = f"{parts[2][:4]}-{parts[2][4:6]}-{parts[2][6:]}"
            return {"id": vid, "ok": True, "title": parts[1].strip(), "date": date}
    return {"id": vid, "ok": False, "why": "yt-dlp printed nothing for this id"}


def ytdlp_has_captions(vid: str, url: str, jar: Path = None) -> dict:
    """Does YouTube admit to holding captions for this show at all?

    The transcript package answers every failure with the same sentence - that
    it has hit a rate limit, and to try a VPN - whether it was throttled, or the
    show simply has none yet. Those need opposite handling: one is retried, the
    other must never be. yt-dlp cannot fetch the words, but it will say plainly
    whether there are any, and that is the whole question here.
    """
    cmd = ["yt-dlp", "--skip-download", "--simulate", "--no-warnings", "--list-subs"]
    if jar and jar.exists():
        cmd += ["--cookies", str(jar)]
    cmd.append(url)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        return {"known": False}
    out = (r.stdout or "") + (r.stderr or "")
    # Only the two sentences it prints when it looked and found nothing count.
    # Anything else - a network error, a sign-in wall - leaves the question open,
    # and an open question is never answered with "this show has no captions".
    if re.search(rf"{re.escape(vid)} has no automatic captions", out) and \
       re.search(rf"{re.escape(vid)} has no subtitles", out):
        return {"known": True, "captions": False}
    if r.returncode == 0 and re.search(r"Available (automatic captions|subtitles)", out):
        return {"known": True, "captions": True}
    return {"known": False}


def mcp_transcript(vid: str, timeout: int = 300) -> dict:
    """The words, from the youtube-transcript package, spoken to directly.

    It is an MCP server, so this is the handshake it expects: initialize, say
    we are ready, then call the one tool. Its answer goes straight to a file.
    """
    pkg = SETTINGS["transcript_package"]
    try:
        proc = subprocess.Popen(["npx", "-y", pkg],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True)
    except OSError as e:
        return {"id": vid, "ok": False, "why": f"could not start npx: {e}"}

    def send(obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "ybs-shows", "version": "1"}}})
        send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
              "params": {"name": "get_transcript", "arguments": {"url": vid}}})
        proc.stdin.close()
        text = ""
        for line in proc.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") != 2:
                continue
            if msg.get("error"):
                return {"id": vid, "ok": False,
                        "why": str(msg["error"].get("message", "tool error"))[:200]}
            result = msg.get("result") or {}
            content = result.get("content") or []
            text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
            # A tool that fails answers with its complaint in the same place a
            # transcript would go, and flags it with isError. Reading only the
            # JSON-RPC "error" misses that entirely: the complaint arrives as
            # content, gets written to raw/<id>.txt, and a show with no captions
            # enters the archive as a forty-four word transcript. Whatever the
            # text says, isError means there are no words here.
            if result.get("isError"):
                return {"id": vid, "ok": False,
                        "why": (text.strip() or "the tool reported an error")[:200]}
            break
    except (OSError, ValueError) as e:
        return {"id": vid, "ok": False, "why": str(e)[:200]}
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass

    if not text.strip():
        return {"id": vid, "ok": False, "why": "the package returned nothing"}

    # It answers with a "# title" line and then one long paragraph. Split it back
    # into sentences so it arrives in the shape the transcript cleaner expects.
    title = ""
    body = text.strip()
    if body.startswith("# "):
        first, _, rest = body.partition("\n")
        title, body = first[2:].strip(), rest.strip()
    lines = [s.strip() for s in SENTENCE.split(body) if s.strip()]
    words = sum(len(l.split()) for l in lines)
    # The last guard, for whatever the package misreports next. A show runs to
    # tens of thousands of words; nothing near this floor is one, whatever the
    # words happen to say. Better to fetch it again tomorrow than to digest it.
    floor = SETTINGS.get("transcript_words_min", 1000)
    if words < floor:
        return {"id": vid, "ok": False,
                "why": f"only {words} words came back, below the {floor} a show runs to"}
    return {"id": vid, "ok": True, "title": title, "lines": lines,
            "words": words}


# ---------------------------------------------------------------- commands

def cmd_settings(args):
    print(json.dumps(SETTINGS, indent=2, ensure_ascii=False))
    return 0


def cmd_start(args):
    sd = shows_dir(args)
    for sub in ("raw", "transcripts", "digests", "new"):
        (sd / sub).mkdir(parents=True, exist_ok=True)
    shows = archive(sd)["shows"]
    prof = load_json(sd / "profile.json", {})
    k = kept(sd)
    print(json.dumps({
        "shows_dir": str(sd),
        "channel": SETTINGS["channel"],
        "excluded_titles": SETTINGS["excluded_titles"],
        "shows_for_profile": SETTINGS["shows_for_profile"],
        "agents_active_max": SETTINGS["agents_active_max"],
        "archived": len(shows),
        "usable_for_profile": len(k),
        "excluded": sum(1 for s in shows if s.get("excluded")),
        "yt_dlp": have_ytdlp() or "NOT INSTALLED (brew install yt-dlp)",
        "profile_built": prof.get("built_local_date", "never"),
        "profile_shows": len(prof.get("shows") or []),
    }, indent=2, ensure_ascii=False))
    return 0


def cmd_fill(args):
    sd = shows_dir(args)
    src = skill_dir() / "prompts" / f"{args.prompt}.md"
    if not src.exists():
        die(f"no prompt at {src}")
    ns = {
        "CHANNEL": SETTINGS["channel"],
        "SHOWS_DIR": str(sd),
        "SCROLLS": str(SETTINGS["list_scrolls_max"]),
        "SHOWS_FOR_PROFILE": str(SETTINGS["shows_for_profile"]),
        "PROFILE_DRAFT": str(draft_path(sd)),
    }
    if args.prompt == "profile":
        picked = kept(sd)[:SETTINGS["shows_for_profile"]]
        if not picked:
            die("no transcript in the archive; run the transcript step first")
        missing = [s["id"] for s in picked if not s.get("digest")]
        if missing:
            die(f"these shows have no digest yet: {', '.join(missing)}")
        blocks = []
        for s in picked:
            text = (sd / s["digest"]).read_text(encoding="utf-8").strip()
            blocks.append(f"### {s['title']} ({s.get('date') or 'date unknown'})\n\n{text}")
        ns["DIGESTS"] = "\n\n".join(blocks)
        ns["SHOW_IDS"] = ", ".join(s["id"] for s in picked)

    text = src.read_text(encoding="utf-8")
    missing = []

    def one(m):
        name = m.group(1)
        if name in ns:
            return ns[name]
        missing.append(name)
        return m.group(0)

    text = re.sub(r"\{\{([A-Z_]+)\}\}", one, text)
    out = Path(args.out) if args.out else sd / "new" / f"prompt-{args.prompt}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(json.dumps({"prompt": args.prompt, "file": str(out),
                      "unfilled": sorted(set(missing))}, indent=2, ensure_ascii=False))
    return 1 if missing else 0


def cmd_new(args):
    """What the channel is showing that the archive does not have yet.

    Excluded titles are recorded and never fetched: an AMA or a dialogue is
    not a show the profile should learn from.
    """
    sd = shows_dir(args)
    listing = load_json(sd / "new" / "listing.json")
    if not listing:
        die("no new/listing.json; run the list agent first")
    data = archive(sd)
    known = {s["id"]: s for s in data["shows"]}
    todo, skipped, added = [], [], 0
    for v in listing.get("videos") or []:
        vid = v.get("id") or video_id(v.get("url", ""))
        if not vid:
            continue
        title = (v.get("title") or "").strip()
        url = v.get("url") or f"https://www.youtube.com/watch?v={vid}"
        if vid not in known:
            known[vid] = {"id": vid, "title": title, "url": url,
                          "date": "", "file": "", "words": 0,
                          "excluded": is_excluded(title), "digest": ""}
            data["shows"].append(known[vid])
            added += 1
        s = known[vid]
        if s.get("excluded"):
            skipped.append({"id": vid, "title": title})
            continue
        if s.get("file"):
            continue
        if (sd / "raw" / f"{vid}.txt").exists():
            continue
        todo.append({"id": vid, "title": title,
                     "launch": f"{vid} | {url} | {sd}"})
    save_archive(sd, data)
    print(json.dumps({"listed": len(listing.get("videos") or []), "new": added,
                      "excluded": skipped, "pool": SETTINGS["agents_active_max"],
                      "todo": todo}, indent=2, ensure_ascii=False))
    return 0


def cmd_check(args):
    """Is the live profile already built from the shows the channel is showing?

    Everything after this step is expensive: a transcript per new show, a digest
    agent per show the profile needs, and a profile agent that reads all of them.
    When the channel has published nothing new, every one of those steps does the
    same work again and arrives at the profile that is already on disk.

    The comparison is between the newest shows on the page and the ids the live
    profile records it was built from. It is done on the page's order, not the
    archive's: the archive sorts on date, and a show listed a moment ago has no
    date yet, so it would sink to the bottom and the archive would answer with
    the wrong fifteen.
    """
    sd = shows_dir(args)
    listing = load_json(sd / "new" / "listing.json")
    if not listing:
        die("no new/listing.json; run the list agent first")
    want = SETTINGS["shows_for_profile"]

    # An excluded title is never fetched and never reaches the profile, so it
    # cannot count towards the newest fifteen either.
    # A show YouTube holds no captions for cannot reach the profile however long
    # the run works at it, so it cannot count towards the newest fifteen either.
    # Left in, it would sit at the top of the page forever, the profile would
    # never match it, and every morning would rebuild the same profile from
    # scratch to arrive back where it started.
    waiting = {s["id"] for s in archive(sd)["shows"]
               if s.get("no_transcript") and not s.get("file")}

    usable, held = [], []
    for v in listing.get("videos") or []:
        if is_excluded(v.get("title") or ""):
            continue
        vid = v.get("id") or video_id(v.get("url", ""))
        if not vid:
            continue
        if vid in waiting:
            held.append(vid)
            continue
        usable.append(vid)
    latest = usable[:want]

    prof = load_json(sd / "profile.json", {})
    built = [s for s in (prof.get("shows") or []) if s]

    added = [i for i in latest if i not in set(built)]
    gone = [i for i in built if i not in set(latest)]

    if not built:
        current, reason = False, "no profile has been built yet"
    elif len(latest) < want:
        # A short listing is a listing that did not scroll far enough, not a
        # channel with fewer shows. Saying "nothing changed" from it would skip
        # a run on the strength of a page that failed to load.
        current = False
        reason = f"the page holds only {len(latest)} usable shows of the {want} the profile needs"
    elif added or gone:
        current = False
        reason = f"{len(added)} show(s) on the page the profile has not read"
    else:
        current, reason = True, "the profile was built from exactly these shows"

    # The profile can be current and a show still be waiting on its captions.
    # That is worth one cheap fetch - no agents, no page - because the day
    # YouTube finishes captioning it, that fetch is the whole run's trigger.
    if current and held:
        nxt = "fetch-only"
    elif current:
        nxt = "stop"
    else:
        nxt = "continue"

    print(json.dumps({
        "current": current,
        "next": nxt,
        "reason": reason,
        "shows_for_profile": want,
        "latest_on_page": latest,
        "waiting_for_captions": held,
        "profile_shows": built,
        "added": added,
        "gone": gone,
        "profile_built": prof.get("built_local_date", "never"),
    }, indent=2, ensure_ascii=False))
    return 0 if current else 1


def cmd_fetch(args):
    """Get what the archive is missing: the words, the dates, or both.

    This took the place of a browser step that could not be made to work. The
    transcript panel never opened - the button is not even in the page's
    accessibility tree - and, worse, it filed a show it had never seen as a show
    without captions.
    """
    sd = shows_dir(args)
    want_words, want_date = [], []
    for s in archive(sd)["shows"]:
        if s.get("excluded"):
            continue
        url = s.get("url") or f"https://www.youtube.com/watch?v={s['id']}"
        if args.only and s["id"] not in set(args.only):
            continue
        if not s.get("file") and not (sd / "raw" / f"{s['id']}.txt").exists():
            want_words.append((s["id"], url))
        if not s.get("date"):
            want_date.append((s["id"], url))

    version = have_ytdlp()
    if want_date and not version:
        die("yt-dlp is not installed, and the dates need it. "
            "Install it with: brew install yt-dlp")

    (sd / "raw").mkdir(parents=True, exist_ok=True)
    pool = max(1, SETTINGS["agents_active_max"])
    words_done, dates_done, failed = [], [], []
    no_captions = []
    urls = {vid: url for vid, url in want_words}

    if want_words:
        with ThreadPoolExecutor(max_workers=min(pool, len(want_words))) as ex:
            for r in ex.map(lambda j: mcp_transcript(j[0]), want_words):
                if not r.get("ok"):
                    # Before filing this as a failure, ask the one question the
                    # package cannot answer: were there ever any captions? A show
                    # streamed hours ago often has none yet, and that is not a
                    # fault to retry - it is a show to fetch again another day.
                    vid = r["id"]
                    verdict = ytdlp_has_captions(vid, urls.get(vid, ""))
                    if verdict.get("known") and not verdict.get("captions"):
                        no_captions.append({"id": vid, "why": "YouTube holds no captions for it yet"})
                    else:
                        failed.append(r)
                    continue
                (sd / "raw" / f"{r['id']}.txt").write_text(
                    "\n".join(r["lines"]) + "\n", encoding="utf-8")
                meta = sd / "raw" / f"{r['id']}.meta.json"
                have = load_json(meta, {}) or {}
                have.update({"id": r["id"], "title": r.get("title") or have.get("title", "")})
                write_json(meta, have)
                words_done.append({"id": r["id"], "words": r["words"]})

    if want_date:
        jar = sd / "raw" / ".cookies.txt"
        n = ego_cookies(jar)
        try:
            with ThreadPoolExecutor(max_workers=min(pool, len(want_date))) as ex:
                for r in ex.map(lambda j: ytdlp_meta(j[0], j[1], jar), want_date):
                    if not r.get("ok"):
                        failed.append(r)
                        continue
                    meta = sd / "raw" / f"{r['id']}.meta.json"
                    have = load_json(meta, {}) or {}
                    have.update({"id": r["id"], "date": r.get("date", ""),
                                 "title": have.get("title") or r.get("title", "")})
                    write_json(meta, have)
                    dates_done.append({"id": r["id"], "date": r.get("date", "")})
        finally:
            # The browser's live session: never left lying about on disk.
            if jar.exists():
                jar.unlink()
        if not n and any(f["id"] in {d[0] for d in want_date} for f in failed):
            failed.append({"id": "-", "ok": False,
                           "why": "no cookies came back from ego; YouTube will "
                                  "answer 'sign in to confirm you're not a bot'"})

    # Record which shows have no captions, so the steps after this one can leave
    # them alone instead of spending an agent on them every morning. The mark is
    # the day it was checked, and it is cleared the moment a transcript arrives.
    if no_captions or words_done:
        data = archive(sd)
        got = {r["id"] for r in words_done}
        none_yet = {r["id"] for r in no_captions}
        today = utc_now().strftime("%Y-%m-%d")
        for s in data["shows"]:
            if s["id"] in got:
                s.pop("no_transcript", None)
            elif s["id"] in none_yet:
                s["no_transcript"] = today
        save_archive(sd, data)

    failed.sort(key=lambda r: r["id"])
    no_captions.sort(key=lambda r: r["id"])
    print(json.dumps({"yt_dlp": version or "not installed",
                      "package": SETTINGS["transcript_package"],
                      "transcripts": sorted(words_done, key=lambda r: r["id"]),
                      "dates": sorted(dates_done, key=lambda r: r["id"]),
                      "no_transcript": no_captions,
                      "failed": failed}, indent=2, ensure_ascii=False))
    # A show still waiting on its captions is not a failure and must not stop the
    # run: nothing here can be retried into working. Only a real fault exits 1.
    return 1 if failed else 0


def cmd_ingest(args):
    """Saved panels -> readable transcripts, and the archive updated."""
    sd = shows_dir(args)
    data = archive(sd)
    known = {s["id"]: s for s in data["shows"]}
    done, empty, kept_as_is = [], [], []
    for raw in sorted((sd / "raw").glob("*.txt")):
        vid = raw.stem
        s = known.get(vid)
        if s is None:
            s = {"id": vid, "title": vid, "url": f"https://www.youtube.com/watch?v={vid}",
                 "date": "", "file": "", "words": 0, "excluded": False, "digest": ""}
            data["shows"].append(s)
            known[vid] = s
        # A transcript already written is already right: the raw file it came
        # from never changes once fetched. Rewriting it every run reads like
        # work being done on shows that have been in the archive for weeks.
        if (not args.force and s.get("file") and s.get("words")
                and (sd / s["file"]).exists()):
            kept_as_is.append(vid)
            continue
        lines = clean(raw.read_text(encoding="utf-8", errors="replace"))
        if not lines:
            empty.append(vid)
            continue
        meta = load_json(sd / "raw" / f"{vid}.meta.json", {}) or {}
        if meta.get("title"):
            s["title"] = meta["title"].strip()
        s["date"] = s.get("date") or meta.get("date") or find_date(meta.get("info", ""))
        s["excluded"] = is_excluded(s["title"])
        words = sum(len(l.split()) for l in lines)
        rel = f"transcripts/{vid}.md"
        header = (f"# {s['title']}\n\nSource: {s['url']}\n\n"
                  f"Date: {s['date'] or 'unknown'}\n\nWords: {words:,}\n\n---\n\n")
        (sd / rel).parent.mkdir(parents=True, exist_ok=True)
        (sd / rel).write_text(header + "\n\n".join(paragraphs(lines)) + "\n",
                              encoding="utf-8")
        s["file"], s["words"] = rel, words
        done.append({"id": vid, "words": words, "excluded": s["excluded"]})
    # A show's date and real title come from the meta file, which the transcript
    # agent writes whether or not the show had captions. Sweeping it separately
    # is what lets a backfill visit date a show it could not transcribe.
    dated = []
    for meta_file in sorted((sd / "raw").glob("*.meta.json")):
        vid = meta_file.name[:-len(".meta.json")]
        s = known.get(vid)
        if s is None:
            continue
        meta = load_json(meta_file, {}) or {}
        before = (s.get("title"), s.get("date"))
        if meta.get("title"):
            s["title"] = meta["title"].strip()
        if not s.get("date"):
            s["date"] = meta.get("date") or find_date(meta.get("info", ""))
        s["excluded"] = is_excluded(s["title"])
        if (s.get("title"), s.get("date")) != before:
            dated.append({"id": vid, "date": s.get("date") or ""})

    save_archive(sd, data)
    # A show with no captions is not missing a transcript, it is waiting for one.
    # Listing it as missing every run reads as a fault that never gets fixed, and
    # nothing here can fix it: only YouTube can.
    waiting = [s["id"] for s in data["shows"]
               if not s.get("excluded") and not s.get("file")
               and not s.get("no_transcript")]
    no_captions = [s["id"] for s in data["shows"]
                   if not s.get("excluded") and not s.get("file")
                   and s.get("no_transcript")]
    undated = [s["id"] for s in data["shows"] if not s.get("date")]
    print(json.dumps({"ingested": done, "already_done": len(kept_as_is),
                      "empty": empty, "updated": dated,
                      "still_missing": waiting,
                      "waiting_for_captions": no_captions,
                      "undated": undated},
                     indent=2, ensure_ascii=False))
    return 1 if (empty or waiting) else 0


def cmd_digest_list(args):
    """One launch line per show the profile needs a digest for.

    A transcript runs to tens of thousands of words, so no one agent reads the
    whole archive. Each show is digested on its own and the profile is written
    from the digests.
    """
    sd = shows_dir(args)
    picked = kept(sd)[:SETTINGS["shows_for_profile"]]
    todo = []
    for s in picked:
        if s.get("digest") and (sd / s["digest"]).exists():
            continue
        todo.append({"id": s["id"], "title": s["title"],
                     "launch": f"{s['id']} | {sd}"})
    print(json.dumps({"for_profile": len(picked), "pool": SETTINGS["agents_active_max"],
                      "todo": todo}, indent=2, ensure_ascii=False))
    return 0


def cmd_digest_sync(args):
    """Record which digests exist. Anything still missing is listed."""
    sd = shows_dir(args)
    data = archive(sd)
    for s in data["shows"]:
        rel = f"digests/{s['id']}.md"
        if (sd / rel).exists():
            s["digest"] = rel
    save_archive(sd, data)
    picked = kept(sd)[:SETTINGS["shows_for_profile"]]
    missing = [s["id"] for s in picked if not s.get("digest")]
    print(json.dumps({"for_profile": len(picked),
                      "with_digest": len(picked) - len(missing),
                      "missing": missing}, indent=2, ensure_ascii=False))
    return 1 if missing else 0


def validate_profile(p: dict) -> list:
    """What must be true of any profile, drafted or live."""
    problems = []
    for group in ("storylines", "themes"):
        entries = p.get(group)
        if not isinstance(entries, list) or not entries:
            problems.append(f"{group} is empty")
            continue
        seen = set()
        for i, e in enumerate(entries, start=1):
            name = str(e.get("name", "")).strip()
            if not name:
                problems.append(f"{group}[{i}] has no name")
            if name.lower() in seen:
                problems.append(f"{group} names {name!r} twice")
            seen.add(name.lower())
            if e.get("rank") != i:
                problems.append(f"{group}[{i}] is ranked {e.get('rank')}, "
                                f"and the list must be ranked in order")
    if not ((p.get("moves") or {}).get("main") or "").strip():
        problems.append("moves.main is empty: the argument he repeats most")
    return problems


def merge_themes(sd: Path, themes: list, today: str) -> tuple:
    """This build's themes, plus the ones fading out of the ledger.

    A theme is a subject he returns to over years, but each build only sees the
    last few weeks of shows. Without a memory a theme he simply did not reach
    for this fortnight would vanish outright, so the ledger carries it at a
    lower rank and drops it only after it has been absent several builds
    running. Storylines get none of this: they are what is unfolding now, and
    they are meant to turn over.
    """
    limit = SETTINGS["themes_max_misses"]
    led = load_json(ledger_path(sd), {"themes": {}}) or {"themes": {}}
    known = dict(led.get("themes") or {})

    hit = set()
    for e in themes:
        key = theme_key(e.get("name", ""))
        if not key:
            continue
        match = theme_match(key, known) or key
        known[match] = {"name": e.get("name", ""), "angle": e.get("angle", ""),
                        "misses": 0, "last_seen": today}
        hit.add(match)

    carried, dropped = [], []
    for key, entry in list(known.items()):
        if key in hit:
            continue
        entry["misses"] = int(entry.get("misses", 0)) + 1
        if entry["misses"] >= limit:
            known.pop(key)
            dropped.append(entry.get("name", key))
        else:
            carried.append(entry)

    write_json(ledger_path(sd), {"themes": known})

    carried.sort(key=lambda e: (e["misses"], e.get("name", "")))
    out = [dict(e) for e in themes]
    for e in carried:
        out.append({"name": e.get("name", ""), "angle": e.get("angle", ""),
                    "fading": True, "missed_runs": e["misses"]})
    for i, e in enumerate(out, start=1):
        e["rank"] = i
    return out, carried, dropped


def show_range(picked: list) -> dict:
    """The stretch of shows a profile was built from, not just how many.

    Fifteen shows is a fortnight in a busy month and two months in a quiet one,
    and nothing downstream can tell the difference without this.
    """
    dates = sorted(s["date"] for s in picked if s.get("date"))
    return {"first": dates[0] if dates else "",
            "last": dates[-1] if dates else "",
            "undated": sum(1 for s in picked if not s.get("date"))}


def cmd_profile_sync(args):
    """Promote the agent's draft to the live profile, or refuse to.

    The stamps are the script's job, not the agent's: the date the profile was
    built and the shows it was built from are facts about the run.
    """
    sd = shows_dir(args)
    path = sd / "profile.json"
    draft = draft_path(sd)

    # A draft is the normal path. Falling back to the live file keeps a re-run
    # after a successful promotion idempotent.
    source = draft if draft.exists() else path
    p = load_json(source)
    if not p:
        die(f"no {draft}; the profile agent writes it")

    problems = validate_profile(p)
    if problems:
        print(json.dumps({"ok": False, "read": str(source), "problems": problems},
                         indent=2, ensure_ascii=False))
        return 1

    picked = kept(sd)[:SETTINGS["shows_for_profile"]]
    today = datetime.now().astimezone().strftime("%Y-%m-%d")

    themes, carried, dropped = merge_themes(sd, p.get("themes") or [], today)
    p["themes"] = themes
    p["built_utc"] = utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    p["built_local_date"] = today
    p["shows"] = [s["id"] for s in picked]
    p["range"] = show_range(picked)

    write_json(path, p)
    render_profile_md(sd, p)
    if draft.exists():
        draft.unlink()

    print(json.dumps({"ok": True, "storylines": len(p["storylines"]),
                      "themes": len(p["themes"]),
                      "fading": [e["name"] for e in p["themes"] if e.get("fading")],
                      "dropped": dropped,
                      "shows": len(p["shows"]), "range": p["range"],
                      "built": p["built_local_date"],
                      "markdown": str(sd / "TOPIC-PROFILE.md")},
                     indent=2, ensure_ascii=False))
    return 0


def render_profile_md(sd: Path, p: dict):
    """The profile as a person reads it. profile.json stays the home."""
    r = p.get("range") or {}
    span = ""
    if r.get("first") and r.get("last"):
        span = f", {r['first']} to {r['last']}"
    if r.get("undated"):
        span += f" ({r['undated']} with no date)"
    out = ["# Yaron Brook Show — topic profile", "",
           f"Built {p['built_local_date']} from {len(p['shows'])} shows{span}. "
           f"Written by /ybs-shows from shows/profile.json; do not edit by hand.",
           "", "## Running storylines, the ones carrying across shows", ""]
    for e in p["storylines"]:
        shows = f" — {e['shows']} shows" if e.get("shows") else ""
        note = f". {e['note']}" if e.get("note") else ""
        out.append(f"{e['rank']}. **{e['name']}**{shows}{note}")
    out += ["", "## Themes, most covered first", ""]
    for e in p["themes"]:
        line = f"{e['rank']}. **{e['name']}** — {e.get('angle', '')}".rstrip(" —")
        if e.get("fading"):
            runs = e.get("missed_runs", 1)
            line += f" _(fading: not in the last {runs} build{'s' if runs != 1 else ''})_"
        out.append(line)
    moves = p.get("moves") or {}
    out += ["", "## The argument he repeats most", "", moves.get("main", "").strip()]
    if moves.get("secondary"):
        out += ["", "Secondary moves:", ""]
        out += [f"- {s}" for s in moves["secondary"]]
    (sd / "TOPIC-PROFILE.md").write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def cmd_import_legacy(args):
    """Seed the archive from a folder of transcripts written before this skill."""
    sd = shows_dir(args)
    src = Path(args.dir).resolve()
    if not src.is_dir():
        die(f"no folder at {src}")
    data = archive(sd)
    known = {s["id"]: s for s in data["shows"]}
    added = []
    for f in sorted(src.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        title = text.splitlines()[0].lstrip("# ").strip() if text else f.stem
        m = re.search(r"^Source:\s*(\S+)", text, re.M)
        vid = video_id(m.group(1) if m else "")
        if not vid or vid in known:
            continue
        rel = f"transcripts/{vid}.md"
        (sd / rel).parent.mkdir(parents=True, exist_ok=True)
        (sd / rel).write_text(text, encoding="utf-8")
        body = text.split("---", 1)[-1]
        s = {"id": vid, "title": title, "url": m.group(1) if m else "",
             "date": "", "file": rel, "words": len(body.split()),
             "excluded": is_excluded(title), "digest": ""}
        data["shows"].append(s)
        known[vid] = s
        added.append({"id": vid, "title": title})
    save_archive(sd, data)
    print(json.dumps({"imported": added, "archived": len(data["shows"])},
                     indent=2, ensure_ascii=False))
    return 0


def cmd_event(args):
    sd = shows_dir(args)
    path = sd / "events.json"
    d = load_json(path, {"events": []})
    d["events"].append({"utc": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "type": args.type, "detail": args.detail or "",
                        "show": args.show or ""})
    write_json(path, d)
    print(json.dumps(d["events"][-1], indent=2, ensure_ascii=False))
    return 0


def main():
    ap = argparse.ArgumentParser(description="Bookkeeping for the YBS show archive")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--shows", help="archive folder (defaults to shows/)")
        return p

    common(sub.add_parser("settings")).set_defaults(fn=cmd_settings)
    common(sub.add_parser("start")).set_defaults(fn=cmd_start)

    p = common(sub.add_parser("fill"))
    p.add_argument("prompt")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_fill)

    common(sub.add_parser("new")).set_defaults(fn=cmd_new)
    common(sub.add_parser("check")).set_defaults(fn=cmd_check)
    pf = common(sub.add_parser("fetch"))
    pf.add_argument("--only", nargs="*", help="limit to these video ids")
    pf.set_defaults(fn=cmd_fetch)
    pi = common(sub.add_parser("ingest"))
    pi.add_argument("--force", action="store_true",
                    help="rewrite transcripts that are already written")
    pi.set_defaults(fn=cmd_ingest)
    common(sub.add_parser("digest-list")).set_defaults(fn=cmd_digest_list)
    common(sub.add_parser("digest-sync")).set_defaults(fn=cmd_digest_sync)
    common(sub.add_parser("profile-sync")).set_defaults(fn=cmd_profile_sync)

    p = common(sub.add_parser("import-legacy"))
    p.add_argument("dir")
    p.set_defaults(fn=cmd_import_legacy)

    p = common(sub.add_parser("event"))
    p.add_argument("--type", required=True)
    p.add_argument("--detail")
    p.add_argument("--show")
    p.set_defaults(fn=cmd_event)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
