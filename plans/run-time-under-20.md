# Can the brief run in under 20 minutes, and what would it cost?

_Written 2026-09-08, from the timings in `plans/run-2026-09-08-slowdown.md`.
Proposals only: nothing has been changed._

## The short answer

**About 25 minutes is the floor without changing what the brief reads or how it
judges. Under 20 is possible, but only by reading fewer articles or judging
with cheaper models, and the X list has to be made faster too.**

The pipeline's guarantees against the ChatGPT problem (sources skipped, articles
assumed instead of read, an unexplained choice of what to read) are not what
makes it slow. Those guarantees are files: a screen file per source, a verdict
file per article, a saved page and a note per read, a check file per figure, a
pick file with a reason for every drop. They cost seconds. The time goes to
(a) the orchestrator, which spends a turn on every launch and every poll, and
(b) three single Opus calls that write long JSON or a long brief.

## Where a run's time actually goes

Agent work in the 09-08 run, when the orchestrator is not counted:

| Step | Agents' own time | What sets it |
|---|---|---|
| screen | ~1.5 min | 6 sources in parallel; slowest source wins |
| triage | ~0.5 min | 22 batches of 13 s each, 15 at a time |
| cluster | 7-10 min | **one Opus/high call writing a ~30 KB JSON plan** |
| read | ~4 min | 65 articles, 15 at a time, 30-60 s each |
| pick | ~3 min | **one Opus/high call over 61 notes** |
| checks + counterpoints | ~2 min | small agents in parallel |
| write | 5-7 min | **one Opus/high call writing a 35-42 KB brief** |
| **sum** | **~25 min** | |

The 09-08 run took 62 min, so 37 min was orchestrator overhead: reading
prompts to paste them, launching agents one per turn, and polling. A 40-min
run still carries about 15 min of it.

The three bold rows are 15-20 min on their own. An Opus call that has to
produce 10,000 tokens of output takes 4-7 min however fast the input is read.
That is the floor the current design sits on.

## Three tiers

### Tier A: no quality cost. About 30-35 min.

Every change here removes orchestrator time. No agent reads less, judges less
or checks less.

1. The seven fixes in `plans/run-2026-09-08-slowdown.md` (cluster cap, paths
   instead of pasted prompts, all launches of a step in one message, screener
   waits, X resumes instead of restarting, no polling).
2. **Move the pooled steps into code.** `x_run.py` already runs its read, cluster
   and judge pools in a Python thread pool calling `claude -p`, with no
   orchestrator turn per agent. Do the same for triage, read, check and
   counterpoint: `ybs_run.py read --run <dir>` launches the readers, waits, and
   prints the sync. The orchestrator makes about 12 calls per run instead of
   460. The agent files, prompts, sentinels and sync checks stay exactly as they
   are; only who presses the launch button changes.
3. `agents_active_max` 15 → 30 for read (the browser handles it: readers each
   open one task space). Read drops from 4 min to about 2.
4. `triage_batch_size` 10 → 20. Half the launches, same verdicts.

Expected: screen 2 + triage 1 + cluster 8 + read 2 + pick 3 + checks 2 +
write 6 = 24 min of agent time, plus ~1 min per step of orchestrator glue:
**~30-33 min**. X at 15 agents finishes in ~15 min, well inside.

### Tier B: small, measurable cost. About 22-26 min.

These change how the three Opus calls work, not what they see. Each needs one
corpus replay against a known day before it is trusted.

5. **Shorter cluster output.** Today every item, including every DROP, carries a
   `why` sentence, and the plan is ~30 KB. Keep `why` for READ and MAYBE, allow
   one word for DROP, drop `near_misses` to five lines. Output roughly halves;
   the call goes from 8 min to about 4. The grouping logic is unchanged; what
   is lost is the written reason for dropping a story nobody will read.
6. **Cluster and pick at Opus/medium instead of high.** Likely 30-40% faster.
   The risk is a quieter judgment: a duplicate missed, a second read not
   requested. Only a replay says whether that happens.
7. **Write in parallel.** One writer per section (leads, body, worth attention)
   from the same notes and template, then a short stitch. Write drops from
   6 min to ~3. Risk: the sections stop talking to each other (a lead and a body
   item on the same event no longer cross-reference). The template is already
   slot-based, so this is smaller than it sounds, but it is a real change to
   the brief's voice.

Expected: **~22-26 min** on a 150-article day.

### Tier C: visible cost. Under 20 min.

8. `read_items_max` 45 → 30, and no second reads inside an item (primary only).
   Read time and pick time both fall. The brief is built from ~30 articles
   instead of ~60. Coverage shrinks; the audit trail still says exactly which
   ones and why.
9. Sonnet for cluster and pick. Fast, cheap, and the settings file already
   warns: a step that gets quietly worse still returns something that looks
   right.
10. Fewer sources, or a shorter window.

Expected: **16-20 min**, with a thinner brief.

## What this does to the ChatGPT problem

The three failures the skill was built against, and which tier touches them:

| Failure | Guarantee today | Tier A | Tier B | Tier C |
|---|---|---|---|---|
| Not all sources read | one screen file per source, or a logged failure | untouched | untouched | touched only if sources are cut (10) |
| Brief built on assumptions, not the article | a saved page and a note per read; figures checked against the page | untouched | untouched | untouched |
| Reads chosen by whim, not an agreed logic | cluster plan with a verdict and reason per item; pick file with a reason per drop | untouched | reasons shortened for DROPs (5); judgment possibly quieter (6) | fewer reads (8), cheaper judge (9): the logic is still written down, but it runs on less |

So: Tier A gives back most of the time and gives up nothing. Tier B is where
speed starts to trade against judgment, in small ways a replay can measure.
Tier C is where the brief starts to look like the ChatGPT one, except that it
tells you what it skipped.

## Recommendation

Do Tier A first and measure. It is the same work either way, and it is the part
that decides whether 20 is even in reach: if Tier A lands at 30, Tier B gets
you to about 24, and the last 4 minutes cost coverage. If Tier A lands at 27,
Tier B alone may reach 20 on an average day.

Set the target at **25 minutes, not 20**. Twenty asks the brief to read less or
think less; twenty-five asks the orchestrator to stop wasting time.

## The X side

X has to fit too: it runs beside the articles and the brief waits for it. Today
a 100-tweet run takes 17-30 min, almost all in the read step (8 agents, batches
of 3). At `x_agents_active_max` 15 it is ~12-15 min; at 20, under 10. Nothing
else in X needs to change for a 25-min brief. For 20, the judge step (one
Opus agent per subject, 55 today) needs the clustering fix already noted in
`x-lists/plans/clustering-findings.md`.

## Order of work

1. Tier A items 1-4: settings and skill edits first (an afternoon), then the
   code pools (a day, with tests). Replay one day and time it.
2. If the result is over 25: Tier B item 5 (shorter cluster output), replay,
   compare plans side by side.
3. Only then decide on 6 and 7, one at a time, each with its own replay.
4. Tier C is a choice about the brief, not an engineering task. It waits for
   Samuele to say the brief may read less.
