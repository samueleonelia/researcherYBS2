# Why the 2026-09-08 brief took 62 minutes, and what to change

_Written 2026-09-08 from the run `runs/2026-09-08_morning_212807` and the
session transcript that drove it. Observation and proposals only: nothing here
has been changed yet._

## The short version

The run took **62 min** against a 45-min ceiling. The article count was only a
little higher than the last 40-min run (153 kept vs 132). The agents' own work
grew by about **3 min**. The other **~19 min** went to three things:

1. the kept list crossed the 150-article cluster cap by 3, so cluster ran as
   two lopsided parts (145 + 8) plus a merge, and the orchestrator copied
   three big prompts through its own context to launch them: **+10 min**
2. the four counterpoint agents were launched one at a time, about 80 s apart,
   while each ran for under 90 s: **+5 min**
3. the Times of Israel screener gave up before its command finished and had to
   be run again: **+4.7 min**

Fixing those three brings a 153-article day back to about **45 min**. The X
pipeline did not cost wall time this run, but it came within 2 min of doing so,
and it is the next thing that will.

## Where the minutes went

Local times. The comparison run is `2026-09-07_morning_230949` (40 min).

| Phase | 09-07 (132 kept) | 09-08 (153 kept) | Difference |
|---|---|---|---|
| screen | 3.5 min | 8 min | +4.5 |
| triage | 5 | 5 | 0 |
| cluster + select | 10 | 20 | +10 |
| read | 6.5 | 7.5 | +1 |
| pick | 4 | 3.5 | 0 |
| checks + counterpoints | 6 | 9 | +3 |
| write | 5 | 7.5 | +2.5 |
| wait for X, merge | 0 | 2 | +2 |
| **total** | **40** | **62** | **+22** |

## The problems, biggest first

### 1. Cluster: a 3-article overshoot cost 10 minutes

`cluster_articles_max` is 150. The kept list was 153, so `fill cluster-select`
cut it into parts. The cut goes by source (best-fit by source name), which gave
**145 articles in part 1 and 8 in part 2**. Part 1 alone took 7 min, the same
as a single call would have. Then a merge agent took another 4.7 min to stitch
back a plan that part 1 had already essentially made.

On top of that, the cluster agent cannot read files (its template disallows
`Read`), so the orchestrator had to open each prompt and paste the text into
the launch: 3.7 min to read the two part prompts (51 KB + 15 KB), 4.2 min to
read the 69 KB merge prompt. That is 8 min of the orchestrator copying text
while no agent was working.

Timeline: triage done 21:41:07 · parts launched 21:44:49 and 21:45:30 · part 1
back 21:51:49 · merge launched 21:56:09 · plan accepted 22:00:54.

**Solution**

- Raise `cluster_articles_max` from 150 to **200** in `settings.md`. One call
  handled 132 articles in 10 min on 09-07; 153 would have taken about the same.
  The split should be for days that genuinely cannot fit one call, not a
  3-article overshoot.
- Let the cluster agent read its own prompt: remove `Read` from
  `disallowedTools` in `agents/cluster.md.tmpl`, and change SKILL.md steps 4-5
  to pass the **path** the way `pick` and `write` already do. Nothing is retyped,
  and the orchestrator stops spending minutes on 50-70 KB files.
- If the split ever triggers, make `part_cut` in `ybs_run.py` balance the parts
  (about N/n each) instead of best-fit by source. A 145/8 cut saves nothing and
  still pays for a merge.

Saves: ~8-10 min on a day like this one; ~3 min of prompt-copying on every day.

### 2. Counterpoints launched one at a time: 5 minutes

The four counterpoint prompts were all filled at 22:13:46. The agents were
launched at 22:15:11, 22:16:40, 22:19:00 and 22:20:22, and each finished in
20-90 s. The step took 7 min for under 2 min of agent work. The orchestrator
read each prompt file before launching it, even though the counterpoint agent
is allowed to `Read` and the orchestrator itself said "the agent can read, so
I pass paths".

**Solution**

- SKILL.md step 9: pass the path from `fill counterpoint`, not the file's text,
  and launch **every lead's agent in one message**, the way the rolling pool
  says to. The counterpoint agent already has `Read`; no template change.

Saves: ~5 min on every run with more than one lead.

### 3. Times of Israel screener gave up early: 4.7 minutes

The first screener ran for 161 s and replied "The task is running in the
background. Waiting for the screening command to complete..." with no file
written: it had put the long `ego-browser nodejs` command in the background and
returned. The retry (with one extra line telling it to wait) finished in 81 s.
The other five screeners were done by 21:31:20; screening closed at 21:36:00.

Also: the six screeners were launched one per message, 25 s apart
(21:29:01 to 21:31:09), because the orchestrator read each prompt file and
pasted it. SKILL.md says "all sources in one message". That is 2 min on every
run.

**Solution**

- In `agents/screener.md.tmpl` (or `prompts/screen.md`): "Run the command in
  the foreground with the Bash tool's longest timeout (600000). Never run it in
  the background, and do not reply until it has printed its line." That is the
  line the retry added by hand; it belongs in the template so the first attempt
  behaves.
- Allow `Read` for the screener and pass the path, or have the orchestrator
  read all six prompts in one message and launch all six in the next. Either
  way, six launches in one turn.

Saves: ~2 min every run; ~4.7 min on a day a screener gives up.

### 4. X pipeline: died on 2 missing notes, restarted from zero

The first X run (21:28) read 113 of 115 tweets, then `validate_notes` killed
the whole run because two links had no note. The orchestrator noticed at 21:56
but, following SKILL.md, waited until step 6 (22:01) to relaunch. The relaunch
started from scratch: a new scrape, then 102 tweets read again (18.5 min at 8
agents in batches of 3), cluster, judge, write. It finished at 22:30:27. The
brief was ready at 22:28:28, so `x-wait` blocked for 2 min.

Two things this shows:

- X is not "6 minutes, always done before the brief" any more. Since the read
  step was added on 09-06 a run with ~100 tweets takes **17-30 min**. The
  memory note and the README-level assumption are stale.
- A run that had 98% of its notes was thrown away for the 2% it lacked, and the
  retry doubled the cost.

**Solution**

- `x_run.py` step 3: when `validate_notes` finds missing notes, send those links
  through one more read batch; whatever is still missing gets a note with
  `status: unavailable` and the run continues. Two missing tweets are a fact for
  the audit line, not a reason to stop.
- `x-start --retry` in `ybs_run.py`: relaunch with `--run-dir <same dir>
  --from <failed step>` instead of a fresh folder. `x_run.py` already supports
  both flags; nothing new to build.
- SKILL.md: let the orchestrator call `x-start --retry` the moment it sees the
  failure, not only at step 6. The one-retry ceiling still holds.
- `x_agents_active_max` 8 → **15**, matching the article side. The read step is
  the whole X clock; twice the agents is about half the time.

Saves: nothing on this run's clock, but without it the next slow-writer day
waits up to `x_wait_minutes_max` (30 min) for X.

### 5. The orchestrator polled instead of waiting

330 Bash calls in the session: 216 `tail` and 53 `ls | wc -l`, most of them
checking agent output files every few seconds while a pooled step ran. Hard
rule 9 says never poll. This did not stall an agent, but it pushed the session
to 2,079 messages, and a bloated orchestrator answers more slowly on every
return-then-launch cycle of the rolling pool, which sits on the critical path.

**Solution**

- Add a blocking `ybs_run.py wait --step <read|triage|check> --run <dir>` that
  returns when the step's file count stops growing or the pool is known drained,
  the way `x-wait` already blocks once for X. One call instead of forty. Then
  SKILL.md tells the orchestrator to use it and nothing else.

Saves: hard to measure; likely 1-3 min of orchestrator latency per run, and a
much smaller bill.

### 6. Guardian sign-in wall: 4 pointless retries

Four Guardian articles hit "Sign in now to carry on reading" and were sent
through the pool a second time, as step 6 says. A sign-in wall does not go away
on retry. Cost ~1.3 min. It also says the Guardian session in ego-browser is
not logged in (48 Guardian links were undated too).

**Solution**

- Reader template: a sign-in or registration wall replies a distinct sentinel
  (`SESSION_DOWN`, like the screener), and SKILL.md step 6 gives it no retry.
- Samuele logs in to the Guardian in ego-browser once.

### 7. Write took 7.5 min instead of 5

Same prompt size (76 KB), longer brief (42 KB vs 34 KB). Nothing to fix; the
writer wrote more. Noted so it is not mistaken for a regression.

## Plan, in order

| # | Change | Where | Minutes saved |
|---|---|---|---|
| 1 | `cluster_articles_max` 150 → 200 | `settings.md` | 8-10 on overshoot days |
| 2 | Cluster and screener agents get `Read`; skill passes paths for cluster, screen, counterpoint | `agents/*.tmpl`, `SKILL.md` | 3 every run, +5 for counterpoints |
| 3 | Counterpoints and screeners launched all in one message | `SKILL.md` steps 2 and 9 | 2 every run |
| 4 | Screener: foreground, full timeout, reply only when done | `agents/screener.md.tmpl` | 4.7 on bad days |
| 5 | X: tolerate missing notes, resume on retry, retry at once, 15 agents | `x_run.py`, `ybs_run.py`, `SKILL.md`, `settings.md` | avoids a 30-min wait |
| 6 | One blocking `wait` command instead of polling | `ybs_run.py`, `SKILL.md` | 1-3, plus cost |
| 7 | Sign-in wall: no retry; log the Guardian in | reader template, `SKILL.md` | 1 |

Items 1-4 are settings and prompt edits, about an hour of work plus one replay
run to verify. Item 5 is code in two scripts, an afternoon with tests. Items 6
and 7 can follow.

Also update the memory note on run durations: X now takes 17-30 min with the
read step, not 6.
