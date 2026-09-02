---
name: ybs-shows
description: Refresh the archive of Yaron Brook Show transcripts and rebuild the topic profile the morning brief reads. Lists the channel's latest streams in the ego browser, skips the excluded formats, saves the transcript of every show not yet archived, digests each one, and writes shows/profile.json. Use when asked to refresh the shows, update the topic profile, or when the user types /ybs-shows. Does NOT write a brief, does NOT send anything anywhere, and never schedules itself.
argument-hint: ""
---

# /ybs-shows — refresh the archive and the topic profile

You are the orchestrator. The brief knows what the show *covers* from its beats,
which change rarely. It knows what the show is *arguing about* from the topic
profile, which is only as good as the last time this skill ran.

You do not watch anything, read a transcript or write the profile yourself:
every step names the agent that does it, and every agent writes its own files.

## Where things live

| What | Home |
|---|---|
| the channel, the exclusions, every number | `settings.md`, printed by `ybs_shows.py settings` |
| the words and the dates as fetched | `shows/raw/<id>.txt` and `<id>.meta.json` |
| what the archive holds | `shows/shows.json` |
| one show's words | `shows/transcripts/<id>.md` |
| one show's digest | `shows/digests/<id>.md` |
| what the show is arguing about now | `shows/profile.json` |
| the same thing for a person to read | `shows/TOPIC-PROFILE.md`, rendered from the JSON |
| how long each theme has been away | `shows/ledger.json`, written only by the script |
| the profile before it is checked | `shows/new/profile-draft.json`, deleted once promoted |

`TOPIC-PROFILE.md` is generated. Never edit it by hand: `profile-sync` rewrites
it from the JSON.

The rolling pool works exactly as it does in `/ybs-brief-v4`: launch up to
`agents_active_max`, and each time one returns launch exactly one more. Never
poll; the completion notification is the signal.

---

## Step 0 — preflight

```bash
ego-browser --version
python3 .claude/skills/ybs-shows/scripts/ybs_shows.py start
```

`start` prints what the archive holds, when the profile was last built, and the
settings in force. If `ego-browser` is missing, stop.

## Step 1 — list the channel

One `ybs4-shows-list` agent.

```bash
python3 .claude/skills/ybs-shows/scripts/ybs_shows.py fill list
```

Read the file it names and pass that text as the agent's prompt. The agent writes
`shows/new/listing.json` itself.

The agent replies with one of three things, and they mean different things:

- `listed <n> shows of <m> on the page` — carry on.
- `LIST_EMPTY` — the page never rendered the grid. One retry, then stop and say
  so.
- `EXTRACTION_BROKEN 0 of <m>` — the videos are on the page but no title could
  be read off them, which is what a YouTube markup change looks like. **Do not
  retry**: a second run breaks the same way. Record it and stop:

  ```bash
  python3 .claude/skills/ybs-shows/scripts/ybs_shows.py event --type list_broken --detail "<the line the agent replied>"
  ```

Everything downstream depends on this listing.

Nothing in this skill may call the browser's `wait()`, and nothing may open a
page with `{ wait: true }`. Both wait for the page to fall quiet, and a YouTube
page never does: the command hangs until something kills it, which is what a
`wait()` in the listing did to the 2026-08-24 run. Pause with a plain timer
instead. The commands already do; leave them as they are.

## Step 2 — what is new

```bash
python3 .claude/skills/ybs-shows/scripts/ybs_shows.py new
python3 .claude/skills/ybs-shows/scripts/ybs_shows.py check
```

`new` records every listed show and marks the excluded titles so they are never
fetched.

`check` then asks the one question the rest of the run is built to answer: are
the newest shows on the page already the shows the live profile was built from?
It compares the page's newest `shows_for_profile` usable shows against the ids
in `profile.json`. The page's own order decides which those are, not the
archive's: the archive sorts on date, and a show listed a minute ago has none
yet.

- `"current": true` (`"next": "stop"`) — **the run is over.** Stop here. Report
  it the way Step 5 says to report, taking the date, the count and the range
  from the profile that is already on disk. Do not fetch, do not digest and do
  not rewrite the profile: every one of those steps would spend an agent to
  arrive at the file that is already there.
- `"current": false` (`"next": "continue"`) — carry on with Step 3. `added`
  names the shows the profile has never read and `gone` names the ones that have
  now aged out of the window.

- `"current": true` with `"next": "fetch-only"` — the profile matches the shows
  it can read, but `waiting_for_captions` names shows YouTube has not captioned
  yet. Run **only** this, which spends no agent and opens no page:

  ```bash
  python3 .claude/skills/ybs-shows/scripts/ybs_shows.py fetch --only <the ids>
  python3 .claude/skills/ybs-shows/scripts/ybs_shows.py check
  ```

  If the captions have arrived, the second `check` says `continue` and the run
  goes on from Step 3b. If they still have not, it says `fetch-only` again:
  stop there and report it, the way `"stop"` is reported. Never loop on this.

A show under `waiting_for_captions` is counted out of the newest fifteen. It has
to be: nothing in this skill can conjure captions YouTube has not made, so a show
left in would sit at the top of the page forever, the profile would never match
it, and every morning would rebuild the same profile to arrive back where it
started.

It exits non-zero when there is work left, the way `digest-sync` does. That is
not a failure.

A short listing never counts as "nothing changed": if the page gave back fewer
usable shows than the profile needs, it scrolled short, and `check` says so and
continues rather than skipping a real run on the strength of a page that failed
to load.

## Step 3 — fetch the words and the dates

```bash
python3 .claude/skills/ybs-shows/scripts/ybs_shows.py fetch
```

No agents in this step, and no browser page to read. It fetches, for every show
that is missing them, the transcript and the date, and writes both itself.

There is no browser step here because there cannot be one. YouTube serves its
captions only against a token its own player makes: the caption URL answers with
an empty body, yt-dlp reports the automatic captions as missing, and the
"Show transcript" button is not even in the page's accessibility tree. A browser
agent tried this and reported shows it had never seen as shows without captions.

So the words come from `transcript_package`, which handles that token, and the
date comes from `yt-dlp`, which cannot get the words but does know when a show
was streamed. Neither transcript passes through an agent: eighteen thousand
words would have to be copied out again, and that is how a transcript quietly
loses half of itself.

`fetch` borrows the browser's YouTube session for yt-dlp, through ego and never
from the cookie file on disk, and deletes the copy when it is done. If a run
ever stops on a password prompt, something is reading that file: fix it, do not
type the password.

It answers in three buckets, and they are not the same thing:

- `transcripts` — the words are in hand.
- `no_transcript` — YouTube holds no captions for that show **yet**. A stream
  captioned hours after it ends is ordinary. This is never retried inside a run
  and never counts as a failure: `fetch` still exits 0. The show is marked in
  the archive, counted out of the profile's window, and picked up by a later
  run on the day its captions appear. Record it once and move on:

  ```bash
  python3 .claude/skills/ybs-shows/scripts/ybs_shows.py event --type no_transcript --show <id>
  ```

- `failed` — a real fault: a block, a timeout, a network error. Gets one more
  `fetch --only <id>`, then an `event`.

The difference is drawn by `yt-dlp --list-subs`, not by the transcript package,
which answers *every* failure with the same sentence: that it has hit a rate
limit and to try a VPN. It says that when a show simply has no captions, and
believing it sends a run chasing a block that was never there. Trust only
yt-dlp's plain "has no automatic captions / has no subtitles" for this.

Nothing the package returns is taken on trust as a transcript, either. A result
flagged `isError` is a failure whatever its text says, and anything shorter than
`transcript_words_min` is treated as no transcript at all. Both guards exist
because the error text was once written to disk as a forty-four word transcript
and reported as a success.

## Step 3b — ingest

```bash
python3 .claude/skills/ybs-shows/scripts/ybs_shows.py ingest
```

Turns what was fetched into readable transcripts, takes each show's date and
title from the same fetch, and updates the archive. It only writes the
transcripts that are not written yet: `already_done` counts the ones left
alone, and a show is re-done only if its transcript went missing or you pass
`--force`. `undated` must be empty when
this finishes: the archive sorts on date, so a show without one sinks below
every dated show and "the latest fifteen" quietly picks the wrong fifteen.

## Step 4 — digest each show

```bash
python3 .claude/skills/ybs-shows/scripts/ybs_shows.py digest-list
```

One launch line per show the profile needs and does not have a digest for. A
transcript is far too long for one agent to hold fifteen of them, so each show is
digested on its own.

**Run the rolling pool** with `ybs4-shows-digest`, then:

```bash
python3 .claude/skills/ybs-shows/scripts/ybs_shows.py digest-sync
```

Anything under `missing` goes through the pool once more.

## Step 5 — write the profile

One `ybs4-shows-profile` agent.

```bash
python3 .claude/skills/ybs-shows/scripts/ybs_shows.py fill profile
```

Read the file it names and pass that text as the prompt. The agent writes a
**draft**, `shows/new/profile-draft.json`, never the live profile. Then:

```bash
python3 .claude/skills/ybs-shows/scripts/ybs_shows.py profile-sync
```

It checks the draft's ranks and shape, carries over any theme fading out of the
ledger, stamps today's date and the shows it was built from, and only then
writes `shows/profile.json` and renders `TOPIC-PROFILE.md`.

A draft that does not hold up costs nothing: the live profile is untouched and
the morning brief keeps running on yesterday's. On a problem, tell the agent
exactly what the check said and let it rewrite the draft. One retry.

`fading` in the output names the themes carried this time; `dropped` names any
that have now been away too long.

Report to the user: how many shows were added, how many had no transcript, and
the date, show count and date range the profile now carries. Nothing else.

---

## Hard rules

1. **Never parse a video page in code.** Agents read pages in the browser; this
   script only names, cleans, counts and validates.
2. **A show whose title carries an excluded phrase is never fetched.** The
   exclusions are in `settings.md` and nowhere else.
3. **Never write a transcript, a digest or the profile by hand.** A step that
   cannot complete is recorded with `event` and reported.
4. **Never edit `TOPIC-PROFILE.md`.** It is rendered from `profile.json`.
   Never edit `ledger.json` either: the script owns it, and it is the only
   memory the profile has of a theme that has gone quiet.
5. **One retry, then honesty.** `no_transcript` is never retried: a show with no
   captions is waiting, not failing, and no number of tries makes captions.
6. **Never invent a show, a date or a topic.** A profile built from ten shows
   says ten.
7. **Never send anything anywhere.** No email, no posting, no scheduling.
8. Transcripts are auto-captions: they mishear names and numbers. Digests say
   what was discussed in their own words; they never reproduce passages, and the
   brief never quotes a figure from one.
