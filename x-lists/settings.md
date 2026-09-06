# Settings

Every number the X pipeline obeys lives here, and nowhere else. Change a value
in this table and the scripts and prompts change with it. This is the X
pipeline's own file; the root `settings.md` is not read and not touched.

**Every number is a ceiling, never a floor.** A run with two picks is right when
only two subjects deserve it. Nothing here fills a slot to reach a number.

## Numbers

| Setting | Value | What it means |
|---|---|---|
| x_window_hours | 1 | how far back the scrape goes, by timeline position |
| x_stop_after_old | 3 | non-repost tweets in a row older than the window before the scrape stops |
| x_min_own_words | 6 | words a tweet must have to survive the filter |
| x_min_reposts | 10 | reposts a tweet needs to clear the engagement floor; OR-ed with x_min_likes |
| x_min_likes | 100 | likes a tweet needs to clear the engagement floor; OR-ed with x_min_reposts |
| x_read_batch | 5 | tweet links one read sub-agent takes, opened one at a time |
| x_convergence_authors | 3 | distinct list members on one subject; at or above flags CONVERGENCE |
| x_endorsement_min | 3 | list-member reposts plus quotes of one tweet; at or above flags ENDORSEMENT |
| x_velocity_percentile | 90 | views-per-minute rank inside the run; at or above flags VELOCITY |
| x_curious_percentile | 50 | velocity rank a subject with no flag needs to be kept as CURIOUS |
| x_picks_max | 5 | subjects that may reach the brief |
| x_tweets_min | 20 | tweets a scrape must return for the run to count as a pass |
| x_cluster_chunk | 60 | kept tweets one cluster agent may take; a longer list is cut into parts and merged |
| x_agents_active_max | 8 | agents working at the same time in a pooled step |

## Fixed

Not numbers, and not tunable by a run. Changing one is a design decision.

| Setting | Value |
|---|---|
| x_account | @EgoismoEfficace |
| x_list_url | https://x.com/i/lists/2091834809903407159 |

## Models

What each agent runs at. **These are not ceilings.** A model here is what the
step uses every time. The rule for changing one is in `GOAL.md`, section 3.
The last column is where the bill comes from: the steps with many agents per
run decide the cost.

Build time (agents that write the pipeline):

| Agent | Model | Effort | Why |
|---|---|---|---|
| orchestrator (main session) | opus | medium | launches, reads verdicts, commits; does no work itself |
| build scrape | sonnet | high | the browser is the hard part; needs care, not judgment |
| build filter, score, run-chain | sonnet | medium | mechanical rules from a table |
| build cluster prompt, judge prompt | opus | high | the prompt *is* the judgment |
| build tests | sonnet | medium | one per script |

Run time (agents that run on real tweets):

| Step | Model | Effort | Agents per run |
|---|---|---|---|
| cluster | opus | high | 1-2, one per chunk of `x_cluster_chunk` |
| judge | opus | high | one per subject, up to `x_agents_active_max` at once |
| verify, checks 1-5 | haiku | low | one per check; mechanical, from the JSON alone |
| verify, check 6 | sonnet | medium | one; needs to read the picks |
| verify, check 7 | haiku | low | one; runs the tests, reports pass or fail |
