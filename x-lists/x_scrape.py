#!/usr/bin/env python3
"""x_scrape.py -- step 1 of the X lists pipeline.

Scrolls the one allowed X list timeline from the top, in the logged-in ego
browser, and writes DIR/tweets.json plus DIR/page.txt. Standard library only.

Guardrails (see GOAL.md): only @EgoismoEfficace, only the one list URL, read
only, no login, sole owner of the browser for the duration of this script.
No number is hard-coded here -- every one is read from settings.md at run
time.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TASK_SPACE_NAME = "x-lists scrape"

# The design's field table, plus `promoted` (see plans/interfaces.md).
FIELDS = [
    "id", "url", "list", "author", "reposted_by", "posted_at", "seen_at",
    "text", "card_title", "quoted_text", "is_reply", "has_link", "promoted",
    "replies", "reposts", "likes", "views",
]


# --------------------------------------------------------------- settings

def _script_dir() -> Path:
    return Path(__file__).resolve().parent


ROW_RE = re.compile(r"^\|\s*([A-Za-z_][A-Za-z0-9_]*)\s*\|\s*([^|]+?)\s*\|")


def read_settings(path: Path) -> dict:
    """Every row of every markdown table in settings.md, key -> raw value."""
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if key in ("Setting",):  # header row
            continue
        if set(val) <= {"-"}:  # separator row
            continue
        values[key] = val
    return values


def require_int(values: dict, key: str) -> int:
    if key not in values:
        die(f"settings.md is missing '{key}'")
    try:
        return int(values[key])
    except ValueError:
        die(f"settings.md value for '{key}' is not an integer: {values[key]!r}")


def require_str(values: dict, key: str) -> str:
    if key not in values:
        die(f"settings.md is missing '{key}'")
    return values[key]


# ------------------------------------------------------------------ utils

def die(msg: str, code: int = 2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str):
    if not s:
        return None
    t = s.strip().replace("Z", "+00:00")
    t = re.sub(r"\.\d+(?=[+-])", "", t)
    try:
        d = datetime.fromisoformat(t)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def run_js(script: str, timeout: int = 60) -> str:
    """One ego-browser nodejs round trip. cliLog output lands on stderr."""
    try:
        r = subprocess.run(
            ["ego-browser", "nodejs"],
            input=script,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        die("ego-browser is not installed / not on PATH")
    except subprocess.TimeoutExpired:
        die("ego-browser nodejs timed out")
    if r.returncode != 0:
        die(f"ego-browser nodejs exited {r.returncode}: {r.stderr.strip()[:2000]}")
    return r.stderr.strip()


def run_js_json(script: str, timeout: int = 60):
    out = run_js(script, timeout=timeout)
    if not out:
        die("ego-browser nodejs produced no output")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        die(f"could not parse ego-browser output as JSON: {out[:2000]}")


# ------------------------------------------------------------- browser JS

# One browser-side pass: reads every tweet article currently in the DOM.
# Everything is computed inside the page, in one closure, then returned as
# plain JSON (per ego-browser's own guidance: one js() call, one IIFE).
EXTRACT_JS = r"""(() => {
  function textOf(el) {
    if (!el) return '';
    return el.innerText.replace(/\s+/g, ' ').trim();
  }
  function stripLinks(el) {
    if (!el) return '';
    const clone = el.cloneNode(true);
    clone.querySelectorAll('a').forEach(a => {
      const href = a.getAttribute('href') || '';
      if (href.startsWith('http')) a.remove();
    });
    return clone.innerText.replace(/\s+/g, ' ').trim();
  }
  function hasHttpLink(el) {
    if (!el) return false;
    return [...el.querySelectorAll('a')].some(a => (a.getAttribute('href') || '').startsWith('http'));
  }

  const arts = [...document.querySelectorAll('article[data-testid="tweet"]')];
  return arts.map(a => {
    const timeEl = a.querySelector('time');
    const statusLink = timeEl ? timeEl.closest('a[href*="/status/"]') : null;
    const href = statusLink ? statusLink.getAttribute('href') : '';

    const userNameBlock = a.querySelector('[data-testid="User-Name"]');
    const authorLink = userNameBlock ? userNameBlock.querySelector('a[href^="/"]') : null;
    const authorHandle = authorLink ? authorLink.getAttribute('href').replace(/^\//, '') : '';

    const socialEl = a.querySelector('[data-testid="socialContext"]');
    const socialText = socialEl ? socialEl.innerText : '';
    let repostedBy = '';
    if (socialEl && /reposted/i.test(socialText)) {
      const socialAnchor = socialEl.closest('a[href^="/"]');
      if (socialAnchor) repostedBy = socialAnchor.getAttribute('href').replace(/^\//, '');
    }

    const quoteBlock = a.querySelector('div[role="link"][tabindex="0"]');
    const quoteTextEl = quoteBlock ? quoteBlock.querySelector('[data-testid="tweetText"]') : null;

    // The first tweetText in DOM order is always the tweet's own body: the
    // quoted tweet's body (if any) lives nested one level down, after it.
    const mainTextEl = a.querySelector('[data-testid="tweetText"]');

    const card = a.querySelector('[data-testid="card.wrapper"]');

    const group = a.querySelector('div[role="group"]');
    const groupAria = group ? (group.getAttribute('aria-label') || '') : '';

    return {
      href,
      author_handle: authorHandle,
      reposted_by_handle: repostedBy,
      time_datetime: timeEl ? (timeEl.getAttribute('datetime') || '') : '',
      text: stripLinks(mainTextEl),
      has_link_in_text: hasHttpLink(mainTextEl),
      card_title: card ? textOf(card) : '',
      quoted_text: stripLinks(quoteTextEl),
      is_reply: a.innerText.includes('Replying to'),
      promoted: a.innerText.includes('Promoted'),
      group_aria: groupAria,
    };
  });
})()"""


def build_first_round_script() -> str:
    return f"""
const task = await useOrCreateTaskSpace({json.dumps(TASK_SPACE_NAME)});
await openOrReuseTab({json.dumps("URL_PLACEHOLDER")}, {{ wait: true, timeout: 25 }});
await wait(2);
// The design scrolls from the top: force it, even if this tab was already
// open and scrolled elsewhere from an earlier run.
await js(String.raw`window.scrollTo(0, 0)`);
await wait(1.5);
const info = await pageInfo();
const handle = await js(String.raw`(() => {{
  const btn = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
  if (!btn) return null;
  const spans = [...btn.querySelectorAll('span')].map(s => s.textContent.trim()).filter(Boolean);
  const at = spans.find(s => s.startsWith('@'));
  return at || null;
}})()`);
if (handle !== {json.dumps("ACCOUNT_PLACEHOLDER")}) {{
  cliLog(JSON.stringify({{ ok: false, reason: 'wrong_handle', handle }}));
}} else if (info.url && !info.url.startsWith({json.dumps("URL_PLACEHOLDER")})) {{
  cliLog(JSON.stringify({{ ok: false, reason: 'wrong_url', url: info.url }}));
}} else {{
  const tweets = await js(String.raw`{EXTRACT_JS}`);
  const pageText = await js(String.raw`(document.querySelector('[data-testid="primaryColumn"]') || document.body).innerText`);
  cliLog(JSON.stringify({{ ok: true, handle, tweets, pageText }}));
}}
"""


def build_scroll_round_script() -> str:
    return f"""
const task = await useOrCreateTaskSpace({json.dumps(TASK_SPACE_NAME)});
await scrollBy(2400);
await wait(1.5);
const tweets = await js(String.raw`{EXTRACT_JS}`);
const pageText = await js(String.raw`(document.querySelector('[data-testid="primaryColumn"]') || document.body).innerText`);
cliLog(JSON.stringify({{ ok: true, tweets, pageText }}));
"""


# ------------------------------------------------------------ record shape

COUNT_PATTERNS = {
    "replies": re.compile(r"([\d,]+)\s+repl(?:y|ies)", re.I),
    "reposts": re.compile(r"([\d,]+)\s+repost", re.I),
    "likes": re.compile(r"([\d,]+)\s+like", re.I),
    "views": re.compile(r"([\d,]+)\s+view", re.I),
}


def parse_counts(group_aria: str) -> dict:
    out = {}
    for key, pat in COUNT_PATTERNS.items():
        m = pat.search(group_aria or "")
        out[key] = int(m.group(1).replace(",", "")) if m else 0
    return out


def to_record(raw: dict, seen_at_iso: str) -> dict:
    href = raw.get("href") or ""
    path = href.split("?")[0].rstrip("/")
    tweet_id = path.rsplit("/", 1)[-1] if "/status/" in path else ""
    url = f"https://x.com{path}" if path else ""

    author = raw.get("author_handle") or ""
    author = "@" + author if author and not author.startswith("@") else author

    reposted_by = raw.get("reposted_by_handle") or ""
    reposted_by = ("@" + reposted_by) if reposted_by and not reposted_by.startswith("@") else reposted_by

    counts = parse_counts(raw.get("group_aria", ""))

    text = raw.get("text", "")
    card_title = raw.get("card_title", "")
    has_link = bool(raw.get("has_link_in_text")) or bool(card_title)

    return {
        "id": tweet_id,
        "url": url,
        "list": "B",
        "author": author,
        "reposted_by": reposted_by,
        "posted_at": raw.get("time_datetime", "") or "",
        "seen_at": seen_at_iso,
        "text": text,
        "card_title": card_title,
        "quoted_text": raw.get("quoted_text", ""),
        "is_reply": bool(raw.get("is_reply")),
        "has_link": has_link,
        "promoted": bool(raw.get("promoted")),
        "replies": counts["replies"],
        "reposts": counts["reposts"],
        "likes": counts["likes"],
        "views": counts["views"],
    }


# --------------------------------------------------------------- scrolling

def window_cutoff_index(records: list, window_hours: int, stop_after_old: int, now: datetime):
    """Index (exclusive) of the last record kept by the window rule. Reposts
    are never counted against the streak; the streak counts only consecutive
    non-repost tweets whose own timestamp is older than the window."""
    streak = 0
    for i, rec in enumerate(records):
        if rec["reposted_by"]:
            continue  # a repost never counts toward the old-streak
        posted = parse_iso(rec["posted_at"])
        age_hours = (now - posted).total_seconds() / 3600.0 if posted else 0.0
        if age_hours > window_hours:
            streak += 1
            if streak >= stop_after_old:
                # cut before the first tweet of this streak (reposts
                # interleaved within its span are excluded too).
                return _first_index_of_streak(records, streak_len=stop_after_old,
                                               end_index=i)
        else:
            streak = 0
    return len(records)


def _first_index_of_streak(records, streak_len, end_index):
    """Given that the non-repost streak ending at end_index (inclusive) has
    length streak_len, find the earliest overall list index that starts it,
    including any reposts interleaved within the streak's own span."""
    count = 0
    idx = end_index
    while idx >= 0 and count < streak_len:
        if not records[idx]["reposted_by"]:
            count += 1
        idx -= 1
    return idx + 1


def scrape(account: str, list_url: str, window_hours: int, stop_after_old: int,
           max_rounds: int = 150, stagnant_limit: int = 8):
    seen_order = []  # tweet ids, in first-seen (timeline) order
    by_id = {}
    page_texts = []  # one chunk of raw text per round, for page.txt

    def absorb(raw_tweets, seen_at_iso, page_text):
        if page_text:
            page_texts.append(page_text)
        added = 0
        for raw in raw_tweets:
            rec = to_record(raw, seen_at_iso)
            if not rec["id"]:
                continue
            if rec["id"] not in by_id:
                by_id[rec["id"]] = rec
                seen_order.append(rec["id"])
                added += 1
        return added

    seen_at_iso = iso(utc_now())
    script = build_first_round_script()
    script = script.replace(json.dumps("ACCOUNT_PLACEHOLDER"), json.dumps(account))
    script = script.replace(json.dumps("URL_PLACEHOLDER"), json.dumps(list_url))
    result = run_js_json(script)

    if not result.get("ok"):
        reason = result.get("reason", "unknown")
        if reason == "wrong_handle":
            die(f"logged-in handle is {result.get('handle')!r}, not {account!r} -- stopping")
        elif reason == "wrong_url":
            die(f"browser navigated to {result.get('url')!r}, not the allowed list URL -- stopping")
        else:
            die(f"first round failed: {result}")

    absorb(result["tweets"], seen_at_iso, result.get("pageText", ""))

    now_ref = utc_now()
    stagnant_rounds = 0
    rounds = 0
    while rounds < max_rounds:
        records = [by_id[i] for i in seen_order]
        cutoff = window_cutoff_index(records, window_hours, stop_after_old, now_ref)
        if cutoff < len(records):
            break  # window boundary reached inside what we've already seen

        rounds += 1
        seen_at_iso = iso(utc_now())
        result = run_js_json(build_scroll_round_script())
        if not result.get("ok"):
            die(f"scroll round {rounds} failed: {result}")
        added = absorb(result["tweets"], seen_at_iso, result.get("pageText", ""))
        if added == 0:
            stagnant_rounds += 1
            if stagnant_rounds >= stagnant_limit:
                break  # end of the list; nothing new loads any more
        else:
            stagnant_rounds = 0

    records = [by_id[i] for i in seen_order]
    cutoff = window_cutoff_index(records, window_hours, stop_after_old, now_ref)
    kept = records[:cutoff]
    page_text = "\n\n----- scroll round -----\n\n".join(page_texts)
    return kept, page_text


# ---------------------------------------------------------------------- io

def write_tweets_json(run_dir: Path, account: str, list_url: str, window_hours: int, tweets: list):
    payload = {
        "list_url": list_url,
        "account": account,
        "scraped_at": iso(utc_now()),
        "window_hours": window_hours,
        "tweets": tweets,
    }
    (run_dir / "tweets.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_page_text(run_dir: Path, text: str):
    (run_dir / "page.txt").write_text(text, encoding="utf-8")


# --------------------------------------------------------------------- cli

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="the run folder to write into")
    parser.add_argument("--settings", default=str(_script_dir() / "settings.md"),
                         help="path to settings.md (default: x-lists/settings.md)")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    settings_path = Path(args.settings).resolve()
    if not settings_path.exists():
        die(f"settings file not found: {settings_path}")
    values = read_settings(settings_path)

    account = require_str(values, "x_account")
    list_url = require_str(values, "x_list_url")
    window_hours = require_int(values, "x_window_hours")
    stop_after_old = require_int(values, "x_stop_after_old")
    tweets_min = require_int(values, "x_tweets_min")

    tweets, page_text = scrape(account, list_url, window_hours, stop_after_old)

    write_tweets_json(run_dir, account, list_url, window_hours, tweets)
    write_page_text(run_dir, page_text)

    ok = len(tweets) >= tweets_min
    print(
        f"x_scrape: wrote {len(tweets)} tweets to {run_dir / 'tweets.json'} "
        f"(min required: {tweets_min}, {'PASS' if ok else 'BELOW MINIMUM'})"
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
