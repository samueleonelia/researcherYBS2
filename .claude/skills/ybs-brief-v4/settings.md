# Settings

Every number the brief obeys lives here, and nowhere else. Change a value in
this table and the script and every prompt change with it.

**Every number is a ceiling, never a floor.** A brief with two leads is right
when only two stories deserve to lead. Nothing in the pipeline fills a slot to
reach a number.

## Numbers

| Setting | Value | What it means |
|---|---|---|
| agents_active_max | 15 | agents working at the same time in a pooled step |
| retries_max | 1 | times one agent may be launched again after a failure |
| read_items_max | 45 | items that may be read in one run |
| cluster_articles_max | 150 | articles one cluster call may take; a longer kept list is cut into parts and merged |
| triage_batch_size | 3 | articles one triage agent may sort; a batch may hold fewer |
| maybe_below_reads | 30 | MAYBEs may be added only while the READ count is under this, and only up to it |
| maybe_share_max | 50% | MAYBEs never exceed this share of the READ count |
| picks_max | 15 | stories that may reach the brief |
| lead_max | 5 | stories that may be tagged LEAD |
| worth_max | 5 | stories that may be tagged WORTH |
| words_per_sentence_max | 30 | words in one sentence of the brief |

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
