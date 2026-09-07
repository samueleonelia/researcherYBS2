#!/usr/bin/env python3
"""x_scrape.py -- step 1 of the X lists pipeline.

Scrolls every X list named in sources.md, one after the other, from the top,
in the logged-in ego browser, and writes DIR/tweets.json plus DIR/page.txt and
DIR/pages/<slug>.txt. Standard library only.

Guardrails. This script may operate on one X account only -- the handle in
`x_account` in the root settings.md -- and it may open no X URL other than the
list URLs named under `## X lists` in the root sources.md. It reads: it never
posts, replies, likes, reposts, follows, or DMs, never logs in or enters a
password, and never touches account settings; the ego browser already holds
the session, and if it is logged out this script stops and says so. It is the
sole owner of the browser for the duration of the run, and it deletes nothing.
Each list is checked on arrival -- the logged-in handle and the URL the browser
landed on -- so the guardrail holds for the second list exactly as for the
first.
No number is hard-coded here -- every one is read from the root settings.md
at run time, through x_settings.py.
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from x_settings import (load_settings, default_settings_path,  # noqa: E402
                          default_sources_path, read_x_lists)

TASK_SPACE_NAME = "x-lists scrape"

# The design's field table, plus `promoted` (see plans/interfaces.md).
FIELDS = [
    "id", "url", "list", "lists", "author", "reposted_by", "posted_at",
    "seen_at", "text", "card_title", "quoted_text", "is_reply", "has_link",
    "promoted", "replies", "reposts", "likes", "views",
]


# --------------------------------------------------------------- settings

def read_settings(path: Path) -> dict:
    """The X half of settings.md, key -> value, through the shared loader.

    One loader for the whole pipeline: the root settings.md holds the article
    brief's tables too, and only `## X numbers`, `## X fixed` and `## X models`
    belong to us.
    """
    return load_settings(path)


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
  // Primary: X now renders this button icon-only, with the logged-in handle
  // encoded in the avatar container's testid instead of visible text.
  const avatar = btn.querySelector('[data-testid^="UserAvatar-Container-"]');
  if (avatar) {{
    const raw = avatar.getAttribute('data-testid').replace('UserAvatar-Container-', '').trim();
    if (raw) return '@' + raw.replace(/^@/, '');
  }}
  // Fallback: the old span-scan, kept in case X reverts the markup. Still
  // scoped to the button so it can never pick up a tweet author's handle.
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


def build_close_script() -> str:
    """Close the tab this list was read in.

    Between two lists the browser must start clean: the next list opens its own
    tab, so a scroll round can never land on the tab of the list before it, and
    a run does not leave a pile of tabs behind."""
    return f"""
const task = await useOrCreateTaskSpace({json.dumps(TASK_SPACE_NAME)});
try {{ await closeTab(); }} catch (e) {{ }}
cliLog(JSON.stringify({{ ok: true }}));
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


def to_record(raw: dict, seen_at_iso: str, list_name: str = "") -> dict:
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
        "list": list_name,
        "lists": [list_name] if list_name else [],
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


# ----------------------------------------------------------- blocked page

# A scroll round that adds no new tweet is normal at the end of a list, so the
# page text alone decides whether the list ended or X stopped us. Every needle
# below is a full sentence or a whole button label that X's own blocking pages
# print as page chrome, chosen so an ordinary timeline cannot carry it even
# when a tweet talks about being rate-limited or quotes "something went wrong":
# each is longer than the phrase a person would type, and names X itself or the
# rest of X's sentence. Matching is case-insensitive; needles stop before any
# apostrophe, because X writes curly ones and copies of its text write straight
# ones. Ordinary tweet words ("rate limit", "captcha", "login") are deliberately
# NOT here: on their own they fire on a normal timeline.
BLOCK_PATTERNS = [
    # The logged-out wall: the sign-in screen's headline and the two lines X
    # prints to a signed-out visitor. A logged-in list page prints none of
    # them. "log in to x" is deliberately absent: that is how a person writes
    # it in a tweet ("I had to log in to X twice today"), while X's own
    # headline says "Sign in to X".
    ("login wall", [
        "sign in to x",
        "people on x are the first to know",
        "sign up to get your own personalized timeline",
    ]),
    # The human check. Full sentences from the challenge page; a tweet saying
    # "captcha" does not carry any of them.
    ("captcha", [
        "verify you are human",
        "prove you are not a robot",
        "complete a security check",
        "authenticate your account",
    ]),
    # The limit page. "rate limit" alone is a thing people tweet about, so the
    # needle carries X's whole sentence.
    ("rate limit", [
        "rate limit exceeded",
        "you are over the daily limit",
        "too many requests",
    ]),
    # X's generic error card. The bare phrase is quotable, so both needles
    # carry the clause that follows it on the card and nowhere else.
    ("something went wrong", [
        "something went wrong. try reloading",
        "something went wrong, but don",
    ]),
]


def blocking_page_reason(page_text: str):
    """Name the wall X is showing on this page text, or None if there is none.

    Runs on the text the scrape already collected for page.txt: no extra
    browser call. Only called for a round that added no new tweet."""
    low = (page_text or "").lower()
    for name, needles in BLOCK_PATTERNS:
        for needle in needles:
            if needle in low:
                return f"{name} (page says {needle!r})"
    return None


def scrape(account: str, list_url: str, window_hours: int, stop_after_old: int,
           list_name: str = "", max_rounds: int = 150, stagnant_limit: int = 8):
    """Scroll ONE list from the top and return its tweets in timeline order.

    Called once per list in sources.md. Each call re-checks the logged-in
    handle and the URL it landed on, so the guardrail holds for the second
    list exactly as it does for the first."""
    seen_order = []  # tweet ids, in first-seen (timeline) order
    by_id = {}
    page_texts = []  # one chunk of raw text per round, for page.txt

    def absorb(raw_tweets, seen_at_iso, page_text):
        if page_text:
            page_texts.append(page_text)
        added = 0
        for raw in raw_tweets:
            rec = to_record(raw, seen_at_iso, list_name)
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
        round_text = result.get("pageText", "")
        added = absorb(result["tweets"], seen_at_iso, round_text)
        if added == 0:
            # Nothing new: either the list ended, or X is showing a wall. The
            # page text says which, and a wall stops the run with its name.
            blocked = blocking_page_reason(round_text)
            if blocked:
                die(f"{list_name or list_url}: scroll round {rounds} added no new "
                    f"tweet and X is showing a {blocked} -- stopping")
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

def merge_lists(scraped: list) -> tuple:
    """Merge what each list returned into one timeline-ordered pile.

    `scraped` is [(list_row, tweets)] in the order the lists were read. A tweet
    carried by two lists is ONE record: the first list that showed it keeps the
    `list` field (so every prompt and every note reads the same as before), and
    every list it appeared in is added to `lists`, which is what makes a subject
    carried by two lists count as two.

    Returns (tweets, per_list_counts).
    """
    by_id, order, counts = {}, [], []
    for row, tweets in scraped:
        seen_here = 0
        for rec in tweets:
            seen_here += 1
            first = by_id.get(rec["id"])
            if first is None:
                by_id[rec["id"]] = rec
                order.append(rec["id"])
                continue
            if row["name"] not in first["lists"]:
                first["lists"].append(row["name"])
        counts.append({"name": row["name"], "url": row["url"], "tweets": seen_here})
    return [by_id[i] for i in order], counts


def write_tweets_json(run_dir: Path, account: str, lists: list, window_hours: int, tweets: list):
    payload = {
        "lists": lists,
        "account": account,
        "scraped_at": iso(utc_now()),
        "window_hours": window_hours,
        "tweets": tweets,
    }
    (run_dir / "tweets.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_page_text(run_dir: Path, per_list: list):
    """One page.txt per list under pages/, plus the joined page.txt every
    later step already reads, so a figure still traces to the page it came
    from."""
    pages = run_dir / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    chunks = []
    for row, text in per_list:
        (pages / f"{row['slug']}.txt").write_text(text, encoding="utf-8")
        chunks.append(f"===== {row['name']} ({row['url']}) =====\n\n{text}")
    (run_dir / "page.txt").write_text("\n\n".join(chunks), encoding="utf-8")


# --------------------------------------------------------------------- cli

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, help="the run folder to write into")
    parser.add_argument("--settings", default=str(default_settings_path()),
                         help="path to settings.md (default: the root settings.md)")
    parser.add_argument("--sources", default=None,
                         help="path to sources.md, which lists the X lists "
                               "(default: the root sources.md)")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    settings_path = Path(args.settings).resolve()
    if not settings_path.exists():
        die(f"settings file not found: {settings_path}")
    values = read_settings(settings_path)

    account = require_str(values, "x_account")
    window_hours = require_int(values, "x_window_hours")
    stop_after_old = require_int(values, "x_stop_after_old")
    tweets_min = require_int(values, "x_tweets_min")

    sources_path = Path(args.sources).resolve() if args.sources else default_sources_path()
    lists = read_x_lists(sources_path)

    scraped, pages = [], []
    for row in lists:
        print(f"x_scrape: reading {row['name']} ({row['url']})", flush=True)
        tweets, page_text = scrape(account, row["url"], window_hours,
                                    stop_after_old, list_name=row["name"])
        print(f"x_scrape: {row['name']}: {len(tweets)} tweets in window", flush=True)
        scraped.append((row, tweets))
        pages.append((row, page_text))
        if row is not lists[-1]:
            # Not fatal: a tab that will not close costs a tab, not the run.
            try:
                run_js_json(build_close_script())
            except SystemExit:
                print(f"x_scrape: could not close the tab for {row['name']}", flush=True)

    tweets, counts = merge_lists(scraped)

    write_tweets_json(run_dir, account, counts, window_hours, tweets)
    write_page_text(run_dir, pages)

    ok = len(tweets) >= tweets_min
    per_list = ", ".join(f"{c['name']}: {c['tweets']}" for c in counts)
    print(
        f"x_scrape: wrote {len(tweets)} tweets from {len(counts)} list(s) "
        f"({per_list}) to {run_dir / 'tweets.json'} "
        f"(min required: {tweets_min}, {'PASS' if ok else 'BELOW MINIMUM'})"
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
