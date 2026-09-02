---
name: ybs-brief-v4
description: Produce a show-ready morning news brief for Yaron Brook from the sources in sources.md. Screens every source's front page in the ego browser with his logged-in sessions, groups the day's stories so one event is read once, reads each chosen article the way a person would, checks every figure against the page it came from, cuts the result to the picks the settings allow and writes the brief. Use when asked to run the morning brief, or when the user types /ybs-brief-v4. Does NOT send email, does NOT read X, does NOT read show transcripts, and never schedules itself.
argument-hint: "morning"
---

# /ybs-brief-v4 — build one morning brief

You are the orchestrator. You run the steps below in order, launching subagents
to do the work. You do not screen, read, judge or write anything yourself: every
step names the agent that does it, and every agent writes its own files.

## Where things live

Nothing in this pipeline is stated twice. When you need a fact, take it from its
home; never copy it into a prompt or a reply.

| What | Home |
|---|---|
| every number | `settings.md`, printed by `ybs_run.py settings` |
| what the show covers | `prompts/_beats.md` |
| the sections code keeps without an agent | `prompts/_sections.md` |
| how a story is read | `prompts/_lens.md` |
| what he is arguing about now | `shows/profile.json`, rebuilt by `/ybs-shows` |
| how stories are judged, labelled and tagged | `prompts/_criteria.md` |
| the shape of a news item, and what code checks in it | `prompts/_item-shape.md` |
| what every agent must do | `prompts/_agent-rules.md` |
| file names, launch lines, sentinels | `ybs_run.py schema` |
| the rules of this pipeline | the hard rules at the end of this file |
| model and effort per agent | `settings.md`, the `## Models` table |

The eight agent files in `.claude/agents/ybs4-*.md` are **generated** from the
templates in `agents/`. Edit a template, then run `ybs_run.py build`.

## Prompts

Every single-call step gets its prompt from `ybs_run.py fill <name> --run <dir>`,
which renders the prompt file with the fragments, the settings and the run's own
data already in it, writes it to `<run_dir>/prompts/`, and prints the path. Read
that file and pass its text as the agent's prompt. Never assemble a prompt by
hand, and never paste a fragment into one.

**Except `pick` and `write`.** Those two prompts hold every note of the run, and
those two agents can read. Pass the *path* `fill` printed, not the text. You do
not open the file, so nothing is retyped and no figure can change on the way.

`fill` exits 1 and names any placeholder it could not fill. That is the one
failure an agent cannot report, because it does not know what it was meant to
receive, so a non-zero exit stops the step.

The pooled steps take their instructions from the body of their agent file,
loaded when the agent launches. For triage, read and figure check the launch
line is the whole prompt you pass. For counterpoints the prompt is the text of
the file `fill counterpoint` names for that story. Either way, pass it verbatim:
do not add to it, do not explain it.

## Concurrency

Decided per step. `agents_active_max` in `settings.md` is the ceiling everywhere.

Browser agents may run at the same time: each opens one task space, works in it,
and closes it.

### The rolling pool

Used by triage, read, figure check and counterpoints.

1. Run the step's list command, or build the list as the step says. Every entry
   has a `launch` value, and **that value is the agent's whole prompt** (for
   triage it is a block of several lines, for a counterpoint the text of its
   filled prompt file).
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

---

## Step 0 — preflight

```bash
ego-browser --version
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py settings
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py build --check
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py sources
```

If `sources` lists nothing, or a line has no link, stop and say which line.
If `ego-browser` is missing, stop: nothing here works without it.
If `build --check` reports a stale agent file, run `build` and say you did.

## Step 1 — start the run

```bash
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py start --slot morning
```

It prints `run_dir`, the window, the sources and the profile's date. Every later
command takes `--run <run_dir>`. The window is local midnight to now.

If it says there is no topic profile, stop and tell the user to run `/ybs-shows`.

## Step 2 — screen every source

**All sources in one message**, one `ybs4-screener` each.

For each source: `fill screen --run <run_dir> --source <slug>`, read the file it
names, and pass that text as the prompt.

Each screener writes `<run_dir>/screen/<slug>.json` itself and replies with one
summary line. Do not write that file yourself and do not paste its contents
anywhere.

- A screener that errors: one retry, logged with `event --type screen_retry
  --source <slug> --retry`, then `event --type screen_failed --source <slug>`.
  The run continues without that source.
- A screener that replies `SESSION_DOWN`: **no retry.** Record it with
  `event --type session_down --source <slug>` and continue. A dead login is for
  a human to fix, and retrying just collects teaser pages.

```bash
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py screen-sync --run <run_dir>
```

This assigns ids, merges duplicate URLs and drops anything dated outside the
window or carrying no date at all. The per-source count is in the output: a
source whose undated count approaches its listed count has stopped publishing
dates, and that is worth opening its screen file over.

## Step 3 — triage

```bash
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py triage-list --run <run_dir>
```

Freezes the article list, then does two things.

First it **sorts by section, in code**. An article filed under a section that is
wholly on beat is kept there and then, its verdict file written, and no agent is
spent on it: the sections are listed in `prompts/_sections.md`. A match admits;
**nothing is ever dropped by section.** Everything else — every generic
`article` and `opinion`, every off-beat and unrecognised section — goes to an
agent. `admitted_by_category` in the output is how many were settled this way.

What is left is cut into batches of `triage_batch_size`, and each `todo` entry
is one batch: an `ids` list and a `launch` block holding the run directory and
one line per article.

**Run the rolling pool** with `ybs4-triage`, one agent per batch, description
`triage <first>..<last>`. Each agent writes **one verdict file per article** in
its batch; you write nothing.

```bash
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py triage-check --run <run_dir>
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

**A file:** one `ybs4-cluster` agent, one call. Write its JSON reply to
`<run_dir>/items/plan.json`.

**`too_long`:** the kept list is over `cluster_articles_max`, and the output
says how it was cut into parts. For every part, `fill cluster-select --run
<run_dir> --part <k>/<n>` and read the file it names. Launch the parts as the
rolling pool launches anything: up to `agents_active_max` in one message, one
more as each returns, one `ybs4-cluster` each, `run_in_background: true`,
description `cluster part <k>/<n>`: the replies arrive as notifications, and
the description is how each reply finds its file. Write each reply to
`<run_dir>/items/plan-part<k>.json`. When every part has returned, `fill
cluster-merge --run <run_dir>`. If it rejects a part, that part's agent gets
one rerun quoting the problems, its file is rewritten, and `fill cluster-merge`
runs again; a part rejected twice ends the step the same way a rejected plan
does, below. Then one `ybs4-cluster` call with the merge
prompt; write its JSON reply to `<run_dir>/items/plan.json` and log it with
`event --type cluster_split --detail "<n> parts"`.

Then:

```bash
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py items-sync --run <run_dir>
```

It rejects an article that is in two items or in none, a cluster with one
article, a `read` list naming an article outside its item, and a profile name
that matches nothing in the profile. Any of those: one rerun of the call that
produced the plan, the single call or the merge, telling the agent exactly what
the check said. If the plan is still rejected, `event --type cluster_failed` and
stop: the run has no plan, and a plan is never written by hand.

## Step 6 — read

```bash
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py read-list --run <run_dir>
```

**Run the rolling pool** with `ybs4-reader`. Each reader opens its article in its
own ego task space, saves the page and writes its own note; you write neither.

A reader that replies `PAGE_TRUNCATED` could not see the whole article — a
registration prompt, a sign-in box, a subscribe overlay. It writes no note, so
`read-list` will list it again. Note the id and carry on; do not relaunch it
inside the pool.

When the pool drains, run `read-list` again: whatever it lists has no note. Send
those through the pool once more. Anything still listed after that retry:

```bash
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py event --run <run_dir> --type read_failed --article <id> --detail "<what it replied>"
```

which retires it, so the next `read-list` no longer offers it.

## Step 7 — pick

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
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py picks-sync --run <run_dir>
```

It enforces the LEAD and WORTH ceilings in `settings.md` and that every note is
either picked or dropped with a reason. A reply over `picks_max` is not a
failure: the command trims it itself, smallest news items first and never a
LEAD, and records what it cut. One rerun on failure, quoting the check.

## Step 8 — check the figures

The pick has already run, so the figures worth checking are the ones the brief
will print: **the picked notes**, not every note.

Build the list yourself — one line per picked id, `<id> | <run_dir>` — and **run
the rolling pool** with `ybs4-checker`. Each checker reads the note and the saved
page and writes its own check file.

```bash
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py check-sync --run <run_dir> --pass 1
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

**LEAD stories only.** A counterpoint hangs under a lead, so `fill counterpoint`
refuses any other tag: `a051 is tagged BODY; counterpoints run for LEAD stories
only`. That is the rule, not an error to work around.

Each agent looks in one place: the other articles of its lead's own news item.
The question is whether those reports carry a positive element bearing on the
lead's problem. Nowhere else in the day counts.

For each lead, `fill counterpoint --run <run_dir> --article <id>` and read the
file it names: that text is the story's launch line. Then **run the rolling
pool** with `ybs4-counterpoint`. Each agent writes its own counterpoint file.

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

One `ybs4-write` agent. `fill write --run <run_dir>` prints a path, and that path
is all you pass:

```
Read <run_dir>/prompts/write.md and follow it. Reply with the finished brief in
markdown, and nothing else.
```

Write the reply to `<run_dir>/brief.md`, then:

```bash
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py audit-line --run <run_dir> --append
python3 .claude/skills/ybs-brief-v4/scripts/ybs_run.py close --run <run_dir>
```

`audit-line` replaces the placeholder the template ends with. Report the audit
line and the path to `brief.md` to the user. Nothing else.

---

## Hard rules

1. **Never parse a page in code.** No selectors, no per-site rules, no HTML
   handling outside a browser.
2. **Model and effort come from `settings.md`**, through the built agent files.
   Never pass `model` to the Agent tool, never state an effort in a prompt. To
   change what a step runs at, edit the `## Models` table and run `build`.
3. **Never write a pooled agent's result file.** You launch, you count, you run
   the sync command. For the single-call steps, match the reply to its file by
   the agent's label, never by reading the content and guessing.
4. **One retry, then honesty.** Any agent may be retried once. After that the
   failure is recorded with `event` and shows up in the audit line.
   `SESSION_DOWN` is never retried.
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
12. **Every number in `settings.md` is a ceiling, never a floor.** No step fills
    a slot to reach a number.
