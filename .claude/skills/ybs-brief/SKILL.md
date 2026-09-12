---
name: ybs-brief
description: Produce a show-ready morning news brief for Yaron Brook from the sources in sources.md. Screens every source's front page in the ego browser with his logged-in sessions, groups the day's stories so one event is read once, reads each chosen article the way a person would, checks every figure against the page it came from, cuts the result to the picks the settings allow and writes the brief. Use when asked to run the morning brief, or when the user types /ybs-brief. Runs its own X-list engine at the same time and puts its section under the article brief. Does NOT send email, does NOT read show transcripts, and never schedules itself. `afternoon` writes what changed since that day's morning brief: new stories first, then the morning's stories that moved. `evening` writes the day's human achievements from the articles the two earlier runs kept, each labelled for how far it has got.
argument-hint: "morning | afternoon | evening"
---

# /ybs-brief — build one brief

You are the orchestrator. You run the steps below in order, launching subagents
to do the work. You do not screen, read, judge or write anything yourself: every
step names the agent that does it, and every agent writes its own files.

## Where things live

Nothing in this pipeline is stated twice. When you need a fact, take it from its
home; never copy it into a prompt or a reply.

| What | Home |
|---|---|
| every number | the project root's `settings.md`, printed by `ybs_run.py settings` |
| what the show covers | `prompts/_beats.md` |
| the sections code keeps without an agent | `prompts/_sections.md` |
| the five kinds of achievement | `prompts/_achievements.md` |
| how a story is read | `prompts/_lens.md` |
| the shape of the brief | `templates/<slot>.md`, and nothing else |
| how the brief's sentences are written | `prompts/write.md`, and nothing else |
| what he is arguing about now | `shows/profile.json`, rebuilt by `/ybs-shows` |
| how stories are judged, labelled and tagged | `prompts/_criteria.md` |
| the shape of a news item, and what code checks in it | `prompts/_item-shape.md` |
| what every agent must do | `prompts/_agent-rules.md` |
| file names, launch lines, sentinels | `ybs_run.py schema` |
| the rules of this pipeline | the hard rules at the end of this file |
| model and effort per agent | `settings.md`, the `## Models` table |
| the X list: its steps and where each rule lives | `.claude/skills/ybs-brief/x-lists/x_run.py`, whose header lists them |

The twelve agent files in `.claude/agents/ybs4-*.md` are **generated** from the
templates in `agents/` and the `## Models` and `## X models` tables in
`settings.md`. Edit either one; step 0 rebuilds the agent files at the start of
every run.

## Prompts

Every single-call step gets its prompt from `ybs_run.py fill <name> --run <dir>`,
which renders the prompt file with the fragments, the settings and the run's own
data already in it, writes it to `<run_dir>/prompts/`, and prints the path.
**Pass the path, not the text.** Every single-call agent (`screen`, `cluster`,
`pick`, `write`) and the counterpoint agent can read, so the prompt you pass is
one line: `Read <path> and follow it.` You never open the file yourself: nothing
is retyped, no figure can change on the way, and a 50 KB prompt costs you no
time. Never assemble a prompt by hand, and never paste a fragment into one.

`fill` exits 1 and names any placeholder it could not fill. That is the one
failure an agent cannot report, because it does not know what it was meant to
receive, so a non-zero exit stops the step.

The pooled steps take their instructions from the body of their agent file,
loaded when the agent launches. For triage, read and figure check the launch
line is the whole prompt you pass. For counterpoints the launch line is
`Read <path> and follow it.`, where the path is the file `fill counterpoint`
names for that story: the agent can read, so you never open that file. Either
way, pass it verbatim: do not add to it, do not explain it.

## Concurrency

Decided per step. `agents_active_max` in `settings.md` is the ceiling everywhere.

Browser agents may run at the same time: each opens one task space, works in it,
and closes it.

### The rolling pool

Used by triage, read, figure check and counterpoints.

1. Run the step's list command, or build the list as the step says. Every entry
   has a `launch` value, and **that value is the agent's whole prompt** (for
   triage it is a block of several lines, for a counterpoint the one-line
   `Read <path> and follow it.` naming its filled prompt file).
2. Launch up to `agents_active_max` of them as `Agent` calls **in one message**:
   `subagent_type` is the step's agent, `prompt` is that line verbatim,
   `description` is `<step> <id>`, `run_in_background: true`.
3. Hold two lists: *active* (launched, not yet returned) and *remaining*.
4. Each time a background agent finishes you are notified. On that message: drop
   it from *active*, note the id if it replied with a sentinel or an error, and
   **launch exactly one** entry from *remaining*. One return, one launch.
5. **Never more than `agents_active_max` active.** Never poll, never sleep, never
   re-read a result file to find out whether an agent has finished: the
   notification is the signal.
6. When *remaining* is empty, let *active* drain, then run the step's sync
   command. **The sync command is the record; the replies are not.**
7. Whatever the sync lists as missing or failing gets one more pass through the
   pool; log each relaunch with `event --type <step>_retry --article <id>
   --retry`, which is what the audit line counts. After that, record the failure
   with `event --type <step>_failed --article <id>` and move on.

### The X lane

The X lists are a lane of the same run, not a job of their own. `x-start`
(step 1) scrapes and filters them in a process of its own, and that is the
only work that runs detached. Every X agent after that is yours to launch,
and one command says which:

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py x-next --run <run_dir>
```

It prints a `phase` and a `launch` list. Each entry is one `Agent` call:
`subagent_type` is its `agent`, `prompt` is its `prompt` verbatim (always
`Read <path> and follow it.`), `description` is its `description`,
`run_in_background: true`. Launch them as entries of the rolling pool that is
running, or start a pool with them when none is: the ceiling
`agents_active_max` counts article and X agents together.

| phase | agent | it writes |
|---|---|---|
| read | `ybs4-x-reader` | one note per tweet, in its own ego task space |
| cluster, cluster-merge | `ybs4-x-cluster` | the subjects file, or one part of it |
| judge, judge-merge | `ybs4-x-judge` | one verdict per subject, then the picks |
| write | `ybs4-x-write` | the X section's own brief |

The lane is **idle** when every launch `x-next` printed has returned. Call
`x-next` again only then, and every time then, until it prints `done` or
`failed`. Never call it while one of its launches is still out, and never
launch the same prompt file twice: the command counts every file it wrote as
an attempt, and a second launch of one steals a retry.

`phase: scraping` with an empty list means the scrape is still running: carry
on with the article step and ask again at the next checkpoint. The checkpoints
are the start of step 6, after `read-list`, and the start of steps 7, 8, 9 and
10, plus every moment in between when the lane goes idle.

A lane that fails before there is a `links.md` is a scrape that died, and it
gets one relaunch: `x-start --run <run_dir> --retry`. A failure inside the lane
is final: each phase already had its second attempt, and the audit line
carries the reason.

---

## Step 0 — preflight

```bash
ego-browser --version
python3 .claude/skills/ybs-brief/scripts/ybs_run.py settings
python3 .claude/skills/ybs-brief/scripts/ybs_run.py build
python3 .claude/skills/ybs-brief/scripts/ybs_run.py sources
```

If `sources` lists no news source, or a line has no link, stop and say which
line. `x_lists` in the same output is the X half's own list of lists, from
`sources.md`'s `## X lists` section; it is never screened by an agent.
If `ego-browser` is missing, stop: nothing here works without it.

## Step 1 — start the run

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py start --slot <slot>
```

The slot is the word the user typed, `morning`, `afternoon` or `evening`.

It prints `run_dir`, the window, the sources and the profile's date. Every later
command takes `--run <run_dir>`. The window is local midnight to now.

For `afternoon` it also names the morning run it updates, under `base`. It
refuses when today has no completed morning run: then stop and say so, because
an update with nothing to update is not a brief.

For `evening` it names the morning run and, when there is one, the afternoon run
it pools from; it refuses when today has no completed morning run.

If it says there is no topic profile, stop and tell the user to run `/ybs-shows`.

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py x-start --run <run_dir>
```

This scrapes and filters the X lists in a process of their own, working while
you screen and triage. `skipped` means this copy has no X pipeline, or no
browser to run it in: the brief goes on without that section. Either way X is
not touched again until step 6, where the X lane starts launching its agents
through you.

## Step 2 — screen every source

**For `evening` there is no screen.** Run `pool-sync --run <run_dir>` and go to
step 3; launch no screener.

**All sources in one message**, one `ybs4-screener` each.

Run `fill screen --run <run_dir> --source <slug>` for every source in **one Bash
call**, one command per source. Each prints a path. Then launch every screener
in **one message**: six sources, six `Agent` calls in the same message, each
with the prompt `Read <path> and follow it.` and `run_in_background: true`. Do
not open the prompt files, and do not launch one screener per turn.

Each screener writes `<run_dir>/screen/<slug>.json` itself and replies with one
summary line. Do not write that file yourself and do not paste its contents
anywhere.

**Never two screens of one source at the same time.** Two copies fetch the same
site at once, and the slower one closes the faster one's task space and lands on
top of its file. So you never launch a second screener on your own judgement.

A screener that errors, or that returns with no file, gets one retry, and the
retry starts here:

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py fill screen --run <run_dir> --source <slug> --retry
```

That command is the gate. It refuses, and exits 1, while the first attempt may
still be running, and its message says how long is left to wait. When it
succeeds it prints a new prompt file and a new attempt number, and the screener
you launch with that file works in a task space of its own. Launch it, then log
the relaunch with `event --type screen_retry --source <slug> --retry`. If the
retry fails as well, record `event --type screen_failed --source <slug>` and let
the run go on without that source.

Wait for the gate. Do not launch a screener from a prompt file `fill --retry`
has not just printed.

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py screen-sync --run <run_dir>
```

This assigns ids, merges duplicate URLs and drops anything dated outside the
window or carrying no date at all. The per-source count is in the output: a
source whose undated count approaches its listed count has stopped publishing
dates, and that is worth opening its screen file over.

It also reports a `stale` key. A name in there is a file an earlier attempt
finished writing after its retry had already delivered; the newer attempt is
what counts, and the older file is ignored.

## Step 3 — triage

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py triage-list --run <run_dir>
```

Freezes the article list, then does two things.

First it **sorts by section, in code**. An article filed under a section that is
wholly on beat is kept there and then, its verdict file written, and no agent is
spent on it: the sections are listed in `prompts/_sections.md`. A match admits;
**nothing is ever dropped by section.** Everything else — every generic
`article` and `opinion`, every off-beat and unrecognised section — goes to an
agent. `admitted_by_category` in the output is how many were settled this way.

On an evening run nothing is admitted by section: every article goes to an
agent, and the launch block's first line says `| evening`.

What is left is cut into batches of `triage_batch_size`, and each `todo` entry
is one batch: an `ids` list and a `launch` block holding the run directory and
one line per article.

**Run the rolling pool** with `ybs4-triage`, one agent per batch, description
`triage <first>..<last>`. Each agent writes **one verdict file per article** in
its batch; you write nothing.

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py triage-check --run <run_dir>
```

Anything under `missing` or `failing` goes through the pool once more (delete a
failing verdict file first, so `triage-list` lists it again). A batch is only a
launch line, never a unit of record: one bad article is re-batched with whatever
else is unsorted, and the rest of its batch stands. If an article still
cannot be sorted, `triage-check --give-up <article-id>` keeps it, one id per
call; a give-up is remembered by every later `triage-check` and `triage-list`.
**An article that cannot be sorted is kept, never dropped.**

## Step 4 and 5 — cluster and select

`fill cluster-select --run <run_dir>` prints either a `file` or `too_long`,
never both.

**A file:** one `ybs4-cluster` agent, one call, prompt `Read <path> and follow
it. Reply with the JSON only.` Write its JSON reply to `<run_dir>/items/plan.json`.

**`too_long`:** the kept list is over `cluster_articles_max`, and the output
says how it was cut into parts. For every part, `fill cluster-select --run
<run_dir> --part <k>/<n>`, all parts in one Bash call; each prints a path.
Launch the parts as the rolling pool launches anything: up to
`agents_active_max` in one message, one more as each returns, one
`ybs4-cluster` each with the prompt `Read <path> and follow it. Reply with the
JSON only.`, `run_in_background: true`,
description `cluster part <k>/<n>`: the replies arrive as notifications, and
the description is how each reply finds its file. Write each reply to
`<run_dir>/items/plan-part<k>.json`. When every part has returned, `fill
cluster-merge --run <run_dir>`. If it rejects a part, that part's agent gets
one rerun quoting the problems, its file is rewritten, and `fill cluster-merge`
runs again; a part rejected twice ends the step the same way a rejected plan
does, below. Then one `ybs4-cluster` call with the path `fill cluster-merge`
printed, the same one-line prompt; write its JSON reply to
`<run_dir>/items/plan.json` and log it with
`event --type cluster_split --detail "<n> parts"`.

Then:

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py items-sync --run <run_dir>
```

It rejects an article that is in two items or in none, a cluster with one
article, a `read` list naming an article outside its item, and a profile name
that matches nothing in the profile. Any of those: one rerun of the call that
produced the plan, the single call or the merge, telling the agent exactly what
the check said. If the plan is still rejected, `event --type cluster_failed` and
stop: the run has no plan, and a plan is never written by hand.

## Step 6 — read

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py read-list --run <run_dir>
python3 .claude/skills/ybs-brief/scripts/ybs_run.py x-next --run <run_dir>
```

The X lane's first checkpoint. What `x-next` prints joins the same pool as the
article readers, under the same ceiling; `scraping` means it has nothing yet.

**Run the rolling pool** with `ybs4-reader`. Each reader opens its article in its
own ego task space, saves the page and writes its own note; you write neither.

A reader that replies `PAGE_TRUNCATED` or `PAGE_BLANK` did not get the article.
`PAGE_TRUNCATED` means a registration prompt, a sign-in box or a subscribe
overlay stood where the rest of it should be. `PAGE_BLANK` means the page never
showed text within `read_wait_seconds`; the retry goes through `read-list`
exactly as for a truncated page, and the `read_failed` detail carries the title
the reader reported. Either way it writes no note, so `read-list` will list it
again. Note the id and carry on; do not relaunch it inside the pool.

When the pool drains, run `read-list` again: whatever it lists has no note. Send
those through the pool once more. Anything still listed after that retry:

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py event --run <run_dir> --type read_failed --article <id> --detail "<what it replied>"
```

which retires it, so the next `read-list` no longer offers it.

## Step 7 — pick

X lane: if it is idle, `x-next` and launch what it prints.

The pick runs **before** the figure check. A struck figure cannot change which
stories are picked: the pick judges evidence from each note's `WEAK SPOTS`, which
the reader wrote, and a bad figure never drops a note.

One `ybs4-pick` agent, one call. `fill pick --run <run_dir>` prints a path, and
that path is all you pass:

```
Read <run_dir>/prompts/pick.md and follow it. Reply with the JSON only.
```

Write its JSON to `<run_dir>/picks/picks.json`, then:

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py picks-sync --run <run_dir>
```

It checks the slot's own tags and ceilings, and that every note is either
picked or dropped with a reason. A reply over the slot's ceiling is not a
failure: the command trims it itself, smallest news items first, and records
what it cut. One rerun on failure, quoting the check.

## Step 8 — check the figures

X lane: if it is idle, `x-next` and launch what it prints.

The pick has already run, so the figures worth checking are the ones the brief
will print: **the picked notes**, not every note.

Build the list yourself — one line per picked id, `<id> | <run_dir>` — and **run
the rolling pool** with `ybs4-checker`. Each checker reads the note and the saved
page and writes its own check file.

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py check-sync --run <run_dir> --pass 1
```

It reads the picks, so it must run after `picks-sync`. Anything under `redo` gets
**one** fresh `ybs4-reader`, launched with the `launch` line pass 1 printed for
it: it ends in `saved-page`, which tells the reader to skip the browser and
re-read the page it saved. Then re-check those ids through the pool and run
`check-sync --pass 2`, which strikes what is still missing and marks the note.
Anything under `already_struck` was settled on an earlier pass; leave it alone.

**A note is never dropped for a bad figure.** Five good figures and one bad one
is still the best account of that story; the brief just loses one number.

## Step 9 — counterpoints

X lane: if it is idle, `x-next` and launch what it prints.

**LEAD stories only.** A counterpoint hangs under a lead, so `fill counterpoint`
refuses any other tag: `a051 is tagged BODY; counterpoints run for LEAD stories
only`. That is the rule, not an error to work around. Neither the afternoon nor the
evening has a lead, so on those slots this step launches nothing.

Each agent looks in one place: the other articles of its lead's own news item.
The question is whether those reports carry a positive element bearing on the
lead's problem. Nowhere else in the day counts.

Run `fill counterpoint --run <run_dir> --article <id>` for **every lead in one
Bash call**, one command per lead. Each prints a path, and that story's launch
line is `Read <path> and follow it.`: do not open the file, the agent reads it.
Then **run the rolling pool** with `ybs4-counterpoint`: **all the leads' agents
in one message**. Five leads is five `Agent` calls in the same message, never
one per turn; a counterpoint agent runs for a minute, and launching them one
at a time cost more than the agents did. Each agent writes its own
counterpoint file.

Two answers arrive without an agent. When the lead is alone in its item, `fill`
prints `"alone_in_item": true` with `"launch": false` and no prompt file: it has
already written `NONE` itself, and there is nothing to launch. And a file holding
`NONE` from an agent means the siblings carried nothing positive. Two
counterpoints across five leads is a normal day; five forced ones are worse than
none.

Then check the figures of every counterpoint file that is not `NONE`: the pool
again, with `ybs4-checker`, launch line `cp-<id> | <run_dir>`. When the page
gave no numbers worth repeating the checker writes `no figures`, which is a
result.
Run `check-sync --pass 1` and then `--pass 2`. Pass 1 lists a counterpoint with
a missing figure under `redo` with no launch line: a counterpoint gets **no**
re-read, so go straight to pass 2 and let the bad figure be struck. Notes struck
in step 8 come back under `already_struck` and are not touched again.

## Step 10 — write, and close

**One `ybs4-write` agent per section, all in one message.** The sections are
the ones `schema write.sections` names for the run's slot, and each writer
sees only its own picks, the same template and the other sections' headlines.

Run `fill write --run <run_dir> --section <section>` for every section in
**one Bash call**, one command per section. Each prints a path, or `"empty":
true` with `"launch": false` when no pick carries that section's tag: an empty
section gets no writer and is omitted from the brief. Then launch every writer
in **one message**, one `Agent` call each, `run_in_background: true`,
description `write <section>`, prompt:

```
Read <path> and follow it. Reply with your section in markdown, and nothing else.
```

Write each reply to `<run_dir>/brief-<section>.md`, the description saying
which is which. When all have returned:

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py write-stitch --run <run_dir>
```

It joins the sections in the template's order under the date line and puts the
two placeholders at the end. It refuses, naming the section, when a section
file is missing, starts with the wrong heading, holds another section or a
placeholder, or lacks the URL of an article picked for it. Rerun that one
writer, quoting the problem, rewrite its file, and stitch again; a section
rejected twice is recorded with `event --type write_failed --detail
"<section>"` and the run stops, because a brief is never written by hand.

Then drive the X lane to its end:

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py x-next --run <run_dir> --closing
```

Launch what it prints, wait for the returns, run it again with `--closing`,
until it prints `done` or `failed`. `--closing` starts the `x_wait_minutes_max`
clock on its first call; when the clock runs out the lane is failed and the
brief goes out without it. Give every `--closing` call the Bash tool's
`timeout: 600000`, its highest: while the scrape is still running this is the
one call that waits, and the wait is deliberately shorter than that. Whatever
it ends on, the next commands run: a lane that failed or ran out of time is a
fact the audit line carries, never a reason to hold the brief.

```bash
python3 .claude/skills/ybs-brief/scripts/ybs_run.py x-merge --run <run_dir>
python3 .claude/skills/ybs-brief/scripts/ybs_run.py audit-line --run <run_dir> --append
python3 .claude/skills/ybs-brief/scripts/ybs_run.py close --run <run_dir>
```

`x-merge` puts the X section under the last article section, and `audit-line`
replaces the placeholder the template ends with. Report the audit line and the
path to `brief.md` to the user. Nothing else.

---

## Hard rules

1. **Never parse a page in code.** No selectors, no per-site rules, no HTML
   handling outside a browser.
2. **Model and effort come from `settings.md`**, through the built agent files.
   Never pass `model` to the Agent tool, never state an effort in a prompt. To
   change what a step runs at, edit the `## Models` table: step 0's `build`
   rebuilds the agent files, so there is nothing else to do. The
   X lane's models are its own: they live in the same `settings.md` under
   `## X models`, and reach its agents the same way, through the built
   `ybs4-x-*` files. Each half reads only its own headings, so a step named
   `cluster` in both tables is two different settings.
3. **Never write a pooled agent's result file.** You launch, you count, you run
   the sync command. For the single-call steps, match the reply to its file by
   the agent's label, never by reading the content and guessing.
4. **One retry, then honesty.** Any agent may be retried once. After that the
   failure is recorded with `event` and shows up in the audit line.
5. **A reader never reads a page it did not save itself**, and never a page saved
   for a different article.
6. **The figure check never drops a note**, and never edits one except to strike
   an unverified figure.
7. **Never invent a URL, a figure or a story.** If a step returns less than the
   brief needs, the brief is shorter and the audit line says why.
8. **Prompts come from `fill`.** A non-zero exit stops the step.
9. **Never more than `agents_active_max` agents active at once**, and one return
   launches exactly one replacement. Never poll for a result: the completion
   notification is the signal.
10. Never write `brief.md`, a note, a page or a screen file by hand to make a
    step pass. A step that cannot complete is recorded as failed.
11. **Never send anything anywhere.** No email, no posting, no scheduling. This
    skill produces one file and reports where it is.
12. **Every number in `settings.md` is a ceiling**, apart from the one its
    table marks as a floor. No step fills a slot to reach a number.
13. **`x-start` and `x-next` are the only doors to X.** Never open the list
    yourself, never run `x_run.py` by hand, never write an X prompt or an X
    result file, and never write the X section yourself. One relaunch of the
    scrape is the ceiling, and `x-start --retry` is where it happens; inside
    the lane, `x-next` decides every retry.
