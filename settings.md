# Settings

Every number the morning brief obeys lives here, and nowhere else. Change a
value in a table below and the scripts and every prompt change with it. One
file covers both halves of the run: the article brief and the X list.
(`/ybs-shows` is a different job and keeps its own settings file, in
`.claude/skills/ybs-shows/`.)

**Every number is a ceiling, never a floor.** A brief with two leads is right
when only two stories deserve to lead. Nothing in the pipeline fills a slot to
reach a number.

**How the scripts read this file.** They look only at the `##` headings:
`Numbers` and `Models` belong to the article brief, `X numbers`, `X fixed` and
`X models` to the X list. Each half reads its own headings and ignores the
other's, which is why both halves may name a step `cluster` without clashing.
A `#` heading below is a divider for you, not for them. Print what a script
actually sees with `python3 .claude/skills/ybs-brief/scripts/ybs_run.py
settings` or `python3 x-lists/x_settings.py`.

# The article brief

## Numbers

| Setting | Value | What it means |
|---|---|---|
| agents_active_max | 15 | agents working at the same time in a pooled step |
| retries_max | 1 | times one agent may be launched again after a failure |
| read_items_max | 45 | items that may be read in one run |
| cluster_articles_max | 150 | articles one cluster call may take; a longer kept list is cut into parts and merged |
| triage_batch_size | 10 | articles one triage agent may sort; a batch may hold fewer |
| maybe_below_reads | 30 | MAYBEs may be added only while the READ count is under this, and only up to it |
| maybe_share_max | 50% | MAYBEs never exceed this share of the READ count |
| picks_max | 15 | stories that may reach the brief |
| lead_max | 5 | stories that may be tagged LEAD |
| worth_max | 5 | stories that may be tagged WORTH |
| words_per_sentence_max | 30 | words in one sentence of the brief |
| x_wait_minutes_max | 9 | minutes step 10 waits for the X run before the brief goes out without it |

BODY has no setting: it is whatever is left of the picks after LEAD and WORTH.

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
| cluster | opus | high | 1-2 |
| read | sonnet | medium | one per article read, capped by read_items_max |
| pick | opus | high | 1 |
| check | haiku | low | one per picked note |
| counterpoint | opus | high | one per lead |
| write | opus | high | 1 |

`pick`, `write` and `cluster` carry judgment that is expensive to get wrong: they
decide what the brief says. `check` and `screen` are narrow mechanical work.

# The X list

The X half runs beside the article half and writes the section under Worth
Yaron's attention. Its rules and guardrails are in `x-lists/GOAL.md`.

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
| x_agents_active_max | 8 | agents working at the same time in a pooled step |

### Retired

`x_min_reposts` and `x_min_likes` (an absolute floor) were replaced on
2026-09-06 by the three `x_*_per_hour` rates. Code that still reads the old
names is a bug, not a setting.

## X fixed

Not numbers, and not tunable by a run. Changing one is a design decision.

| Setting | Value |
|---|---|
| x_account | @EgoismoEfficace |
| x_list_url | https://x.com/i/lists/2091834809903407159 |

## X models

What each agent runs at. **These are not ceilings.** A model here is what the
step uses every time. The rule for changing one is in `x-lists/GOAL.md`,
section 3. The last column is where the bill comes from: the steps with many
agents per run decide the cost.

Build time (agents that write the pipeline):

| Agent | Model | Effort | Why |
|---|---|---|---|
| orchestrator (main session) | opus | medium | launches, reads verdicts, commits; does no work itself |
| build scrape | sonnet | high | the browser is the hard part; needs care, not judgment |
| build filter, score, run-chain | sonnet | medium | mechanical rules from a table |
| build cluster prompt, judge prompt, write prompt and template | opus | high | the prompt *is* the judgment |
| build tests | sonnet | medium | one per script |

Run time (agents that run on real tweets):

| Step | Model | Effort | Agents per run |
|---|---|---|---|
| cluster | opus | high | 1-2, one per chunk of `x_cluster_chunk` |
| read | sonnet | medium | one per batch of `x_read_batch` links, up to `x_agents_active_max` at once, each in its own ego task space |
| judge | opus | high | one per subject, up to `x_agents_active_max` at once |
| write | opus | high | 1; it writes what Yaron reads |
| verify, check 10 | sonnet | medium | one; reads the brief against the picks and the notes |
| verify, checks 1-5 | haiku | low | one per check; mechanical, from the JSON alone |
| verify, check 6 | sonnet | medium | one; needs to read the picks |
| verify, check 7 | haiku | low | one; runs the tests, reports pass or fail |
