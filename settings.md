# Settings

Every number the morning brief obeys lives here, and nowhere else. Change a
value in a table below and the scripts and every prompt change with it. One
file covers all three jobs: the article brief, the X list and the shows.

**Every number is a ceiling, never a floor.** A brief with two leads is right
when only two stories deserve to lead. Nothing in the pipeline fills a slot to
reach a number.

**How the scripts read this file.** They look only at the `##` headings:
`Numbers` and `Models` belong to the article brief, `X numbers`, `X fixed` and
`X models` to the X list, and `Shows numbers` and `Shows models` to the shows.
Each job reads its own headings and ignores the others', which is why two of
them may name a step `cluster`, or a number `retries_max`, without clashing.
A `#` heading below is a divider for you, not for them. Print what a script
actually sees with `python3 .claude/skills/ybs-brief/scripts/ybs_run.py
settings`, `python3 .claude/skills/ybs-brief/x-lists/x_settings.py`, or `python3
.claude/skills/ybs-shows/scripts/ybs_shows.py settings`.

# The article brief

## Numbers

| Setting | Value | What it means |
|---|---|---|
| agents_active_max | 15 | agents working at the same time in a pooled step |
| retries_max | 1 | times one agent may be launched again after a failure |
| screen_timeout_seconds | 540 | seconds one screen command may run before it counts as dead; the command stops itself just under this, and the value stays below the Bash tool's own ceiling |
| read_items_max | 45 | items that may be read in one run |
| read_wait_seconds | 10 | how long a reader waits for a blank page to show text before giving up; a page with text is copied at once |
| cluster_articles_max | 200 | articles one cluster call may take; a longer kept list is cut into parts and merged |
| triage_batch_size | 10 | articles one triage agent may sort; a batch may hold fewer |
| maybe_below_reads | 30 | MAYBEs may be added only while the READ count is under this, and only up to it |
| maybe_share_max | 50% | MAYBEs never exceed this share of the READ count |
| picks_max | 15 | stories that may reach the brief |
| lead_max | 5 | stories that may be tagged LEAD |
| worth_max | 5 | stories that may be tagged WORTH |
| update_picks_max | 20 | stories that may reach the afternoon update, new and moved together |
| new_item_articles_min | 10 | articles an afternoon item that follows no morning story must hold before it is read; the one floor in this table, and the note under it says so |
| achievements_max | 5 | human-achievement stories that may reach the evening report; zero is a valid result |
| words_per_sentence_max | 30 | words in one sentence of the brief |
| x_wait_minutes_max | 30 | safety timeout only: minutes step 10 keeps driving the X lane before the brief goes out without it. Not a speed target — raise it if the X lists take longer |

BODY has no setting: it is whatever is left of the picks after LEAD and WORTH.

`new_item_articles_min` is a floor, not a ceiling: it is the size at which a
story the morning did not have counts as big enough to be new. A war that
breaks at noon clears it; one column does not.

## Models

What each step runs at. **These are not ceilings.** A number above is a limit the
pipeline stays under; a model here is the setting the step actually uses, every
time. Raising one costs money on every article that step touches. Lowering one
trades judgment for cost, and a step that has quietly got worse still returns
something that looks right, so change one only with a corpus replay behind it.

The last column is what a change costs you: the steps with the largest agent
populations are where model choice decides the run's bill.

| Step | Model | Effort | Agents per run |
|---|---|---|---|
| screen | haiku | low | one per source |
| triage | sonnet | low | the largest population, and the one that grows with the source list |
| cluster | opus | medium | 1-2 |
| read | sonnet | medium | one per article read, capped by read_items_max |
| pick | opus | medium | 1 |
| check | haiku | low | one per picked note |
| counterpoint | opus | high | one per lead |
| write | opus | high | one per section of the brief (leads, body, worth attention), or of the update, or the one section of the evening report, all at once |

`pick`, `write` and `cluster` carry judgment that is expensive to get wrong: they
decide what the brief says. `check` and `screen` are narrow mechanical work.

`cluster` and `pick` went from `high` to `medium` on 2026-09-09 for speed. Not
yet replayed: the risk is a quieter judgment (a duplicate missed, a second read
not asked for). Put them back to `high` if a replay shows either, and say so in
`DEVLOG.md`.

# The X list

The X half runs as a lane of the same run and writes the section under Worth
Yaron's attention. Its steps, and the home of each rule it obeys, are listed in the header of
`.claude/skills/ybs-brief/x-lists/x_run.py`. Its agents are the orchestrator's,
like the article half's, and their model and effort reach them the same way:
through the agent files `build` renders from the `## X models` table.

## X numbers

| Setting | Value | What it means |
|---|---|---|
| x_window_hours | 2 | how far back the scrape goes, by timeline position |
| x_stop_after_old | 3 | non-repost tweets in a row older than the window before the scrape stops |
| x_min_own_words | 6 | words a tweet must have to survive the filter |
| x_reposts_per_hour | 10 | reposts per hour of age a tweet needs to pass the screen; OR-ed with the other two |
| x_likes_per_hour | 100 | likes per hour of age a tweet needs to pass the screen; OR-ed with the other two |
| x_views_per_hour | 20000 | views per hour of age a tweet needs to pass the screen; OR-ed with the other two |
| x_read_batch | 3 | tweet links one read sub-agent takes, opened one after the other, fresh context each sub-agent |
| x_convergence_authors | 3 | distinct list members on one subject; at or above flags CONVERGENCE |
| x_endorsement_min | 3 | list-member reposts plus quotes of one tweet; at or above flags ENDORSEMENT |
| x_velocity_percentile | 90 | views-per-minute rank inside the run; at or above flags VELOCITY |
| x_curious_percentile | 50 | velocity rank a subject with no flag needs to be kept as CURIOUS |
| x_picks_max | 5 | subjects that may reach the brief |
| x_tweets_min | 20 | tweets a scrape must return for the run to count as a pass |
| x_words_per_sentence_max | 30 | words in one sentence of the brief, same ceiling as the article brief |
| x_cluster_chunk | 60 | kept tweets one cluster agent may take; a longer list is cut into parts and merged |

### Retired

`x_min_reposts` and `x_min_likes` (an absolute floor) were replaced on
2026-09-06 by the three `x_*_per_hour` rates. Code that still reads the old
names is a bug, not a setting.

`x_agents_active_max` was retired on 2026-09-12: the X agents are launched
by the orchestrator and go through its one pool, whose ceiling is
`agents_active_max` in `## Numbers` above.

## X fixed

Not numbers, and not tunable by a run. Changing one is a design decision.

Which lists are read is **not** here: they are in `sources.md`, under
`## X lists`, one line each, the same way the news sites are listed. This row
is which login is allowed to read them.

| Setting | Value |
|---|---|
| x_account | @EgoismoEfficace |

## X models

What each agent runs at. **These are not ceilings.** A model here is what the
step uses every time. Raising one costs money on every tweet that step
touches. Lowering one trades judgment for cost, and a step that has quietly got
worse still returns something that looks right, so change one only with a
corpus replay behind it.

The last column is where the bill comes from: the steps with many agents per
run decide the cost.

| Step | Model | Effort | Agents per run |
|---|---|---|---|
| cluster | opus | high | one per chunk of `x_cluster_chunk`, plus one merge when there are several |
| read | sonnet | medium | one per batch of `x_read_batch` links, each in its own ego task space |
| judge | opus | high | one per subject, plus one merge |
| write | opus | high | 1; it writes what Yaron reads |

# The shows

`/ybs-shows` is its own job: it refreshes the archive of show transcripts and
rebuilds the topic profile the morning brief reads. It writes no brief and
sends nothing anywhere.

## Shows numbers

| Setting | Value | What it means |
|---|---|---|
| channel | https://www.youtube.com/@YaronBrook/streams | the page the show list is read from |
| shows_for_profile | 15 | most recent shows the topic profile is built from |
| excluded_titles | "AMA & Hangout", "Yaron & Nikos Dialogues" | a show whose title contains one of these is never used |
| agents_active_max | 10 | agents working at the same time in a pooled step |
| transcript_package | @sinco-lab/mcp-youtube-transcript@0.0.12 | fetches the captions YouTube will not serve any other way; npx downloads it on demand |
| transcript_words_min | 1000 | a transcript shorter than this is not a show; the fetch treats it as no transcript at all |
| list_scrolls_max | 8 | times the list page is scrolled before the listing is taken |
| themes_max_misses | 3 | builds a theme may be absent from before it is dropped from the profile |
| retries_max | 1 | times one agent may be launched again after a failure |

## Shows models

What each step runs at. **These are not ceilings.** A model here is what the
step uses every time. The last column is where the bill comes from: the digest
step is the one that grows with the archive.

| Step | Model | Effort | Agents per run |
|---|---|---|---|
| list | haiku | low | 1 |
| digest | opus | medium | one per show among the newest `shows_for_profile` that has no digest yet |
| profile | opus | high | 1 |
