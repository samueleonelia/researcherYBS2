# Plan: the X list inside /ybs-brief

Written 2026-09-07. Goal: one `/ybs-brief` run produces one `brief.md` that
carries the article brief on top and the X-list brief under it, with the two
pipelines running **at the same time**, not one after the other.

Success, as Samuele set it:

1. The whole brief is done in under 45 minutes.
2. The brief carries both the article analysis and the X analysis.
3. It respects the settings (both `settings.md` files).

## 1. What exists today

**The article pipeline** (`/ybs-brief`, `.claude/skills/ybs-brief/`): an
orchestrator follows `SKILL.md`, launches `ybs4-*` subagents through the Agent
tool, and every bookkeeping step is a command of `ybs_run.py`. Step 10 writes
`brief.md` from `templates/morning.md`, then `audit-line --append` fills
`{{AUDIT_LINE}}` and `close` writes `run-log.md`. Past runs took 34, 37, 42 and
60 minutes (the 60 was before triage batches went from 3 to 10).

**The X pipeline** (`x-lists/`): one command, `python3 x_run.py`, drives seven
steps on its own: scrape (script, ego browser), filter (script), read (headless
`claude -p` agents, up to `x_agents_active_max` at once, each in its own ego task
space), cluster, score, judge, write. It ends with `x-lists/runs/<UTC
date-HHMM>/brief.md`, in the shape of `templates/x-brief.md`. It takes about 6
minutes. All ten of its checks passed on 2026-09-06 and it ran clean again on
2026-09-07 after the handle fix. Its agents run at the models in
`x-lists/settings.md`, and they get their tool permissions from the user's
`defaultMode: auto` in `~/.claude/settings.json`, which a headless `claude -p`
inherits (verified today: `claude -p` works from inside a session too).

Two facts that shape the design:

- `x_run.py --run-dir DIR` accepts a folder chosen by the caller, as long as
  its **name** starts with `YYYY-MM-DD-HHMM`, because the write step parses the
  run's date and time for the brief header out of that name.
- `x_run.py` prints progress lines and exits non-zero (with `ERROR: ...` on
  stderr) when a step dies. `brief.md` in its run folder is the proof it
  finished.

## 2. The design in one picture

```
Step 1   start ─────────────────────────────┐
         x-start  ──> x_run.py (background, own process) ──> x-lists/runs/<X>/brief.md
Step 2-5 screen, triage, cluster            │  (about 6 min; the article side
Step 6   read      x-start --retry: launches only if X failed   is still screening and triaging)
Step 7-9 pick, check, counterpoints          │
Step 10  write ─> brief.md (articles)        │
         x-wait  <───────────────────────────┘   (returns at once when X is done)
         x-merge  : X section appended under the article brief
         audit-line, close
```

The X pipeline is **not** rewritten as Agent-tool subagents. It stays exactly
what it is, launched as one background process by a new `ybs_run.py` command.
Reasons: it works and is verified; its guardrails live in `x-lists/GOAL.md`
and nothing in `x-lists/` needs to change; and a separate process is the
simplest way to get true parallelism without the orchestrator juggling two
rolling pools.

The merge is done **by code**, not by the write agent. The X write agent already
produces a verified, show-ready section (check 10). Feeding X picks into the
article write prompt would mean re-verifying figures across two note formats and
would put a 30-item prompt in front of one agent. Concatenation keeps each
brief's own checks valid. (Alternative considered and rejected for now: one
write agent for both. Revisit only if the seam between the two parts reads
badly.)

## 3. Changes, file by file

Nothing in `x-lists/` changes. Everything below is on the article side.

### 3.1 `ybs_run.py`: three new commands, one new settings key, one audit bit

**`x-start --run <run_dir> [--retry]`**

- First runs the status test below. Refuses to launch when the run is
  `running` or `completed`, and says so in its JSON (`launched: false`). With
  `--retry` on a `failed` run it launches again, once: a second `--retry` is
  refused (rule 4). Without `--retry` it launches only when nothing is
  recorded yet.
- Computes the X run folder name the way `x_run.py` does: UTC
  `YYYY-MM-DD-HHMM`, with `-2`, `-3` on collision, under `x-lists/runs/`.
- Spawns `python3 x-lists/x_run.py --run-dir <that folder>` **detached**
  (`subprocess.Popen`, `start_new_session=True`, `stdin=DEVNULL`, cwd
  `x-lists/`), stdout and stderr to `<run_dir>/x/x-run.log`. Closing stdin
  matters: a child holding the Bash tool's pipe would keep the call hanging.
- The script path is read from the environment variable `YBS_X_RUN` when set
  (tests point it at a stub), else `x-lists/x_run.py`.
- Records in `run.json` under `x`: `run_dir`, `pid`, `log`, `started_utc`,
  `status: running`, `retries` (0, or 1 with `--retry`; a second `--retry` is
  refused, that is rule 4).
- Logs `event --type x_started` (or `x_retry` with `--retry`).
- If `x-lists/x_run.py` is missing, or `ego-browser` is not on PATH: prints
  `status: skipped` with the reason, records `x.status = skipped`, logs
  `x_skipped`. The brief goes on without X. Never a crash.
- Prints one JSON object: `status`, `x_run_dir`, `pid`, `log`.

**The status test** (one function, used by `x-start` and `x-wait`; there is
no separate status command, one fewer thing for the orchestrator to learn)

- `running` when the pid is still alive (`os.kill(pid, 0)`).
- `completed` when the pid is dead **and** `<x_run_dir>/brief.md` exists.
  The brief is written by the X write agent itself, which may edit it while
  the chain is still alive, so the file alone is not a finish signal; the
  chain exits milliseconds after that step, so waiting for the pid costs
  nothing.
- `failed` when the pid is dead and there is no brief, with `reason` = the
  last `ERROR:` line of the log, else the log's last non-empty line (a
  traceback ends without `ERROR:`).
- Updates `x.status` in `run.json`.

**`x-wait --run <run_dir>`** (blocking, the one place code waits)

- The status test, repeated every few seconds by the script (the
  orchestrator makes one call and gets one answer; it never polls itself),
  until `completed`, `failed`, or `x_wait_minutes_max` minutes have passed.
- The Bash tool kills a command at 10 minutes at most, and that kill would
  hit `ybs_run.py`, not the X process group. So `x_wait_minutes_max` is 9,
  and SKILL.md tells the orchestrator to call `x-wait` with the tool's
  `timeout` at its 600000 ms maximum. A hidden `--timeout-seconds` flag
  overrides the setting for the tests only.
- On timeout: kills the process group it started, records `x.status = failed`
  with reason `timeout after N minutes`, logs `x_failed`. No orphan `claude -p`
  processes are left heating the Mac.
- On `failed` (not timeout) it also logs `x_failed` with the reason, once.
- Prints the final JSON. Exit 0 in every case: X failing is a recorded fact,
  not a reason to stop the brief.

**`x-merge --run <run_dir>`**

- Reads `<x_run_dir>/brief.md`. Never edits that file.
- Turns it into a section:
  - the `# What the list is moving on` title becomes `## What the list is
    moving on`;
  - the `**Run:** <folder> · **Window:** ...` line becomes `**Window:** ...`
    only (the folder name means nothing to Yaron);
  - every other heading is demoted one level (`## TRENDING` → `###`, `### 1.`
    → `####`), so the X items sit like article stories under a section;
  - the `---` rule and the closing "N picks from M subjects judged" line stay
    as they are, they are the section's own footnote;
  - the no-picks case (title, run line, one sentence) is carried the same way.
- Replaces `{{X_SECTION}}` in `<run_dir>/brief.md` with that section. If the
  write agent dropped the placeholder, inserts before `{{AUDIT_LINE}}` (or the
  audit line itself, if already filled), else appends. Same fallback logic
  `audit-line` already uses.
- When `x.status` is `skipped` or `failed`: replaces the placeholder with
  nothing (no empty section, no "none": the audit line says why).
- Records counts: `x_picks`, `x_subjects` (parsed from the closing line;
  0 and 0 when the no-picks brief has no closing line), `x_tweets_read`
  (number of files in `<x_run_dir>/notes/`), and sets `x.status = merged`.
  Logs `x_merged`.
- The `Storyline`, `Flags` and `Source` bullets are kept as they are. They
  are short, the flags are the evidence the section rests on, and copying
  the section unchanged keeps the X pipeline's own check 10 valid for what
  Yaron reads. Revisit only if he says they are noise.
- Refuses to run twice (the placeholder is gone after the first merge).

**Settings**: `x_wait_minutes_max | 9 | minutes step 10 waits for the X run
before the brief goes out without it` in `.claude/skills/ybs-brief/settings.md`.
Every X number stays in `x-lists/settings.md`; the table there says so already.

**Audit line**: one new bit, before the retries count:
`X: 5 picks from 20 subjects, 24 tweets read` or `X: none (failed: <reason>)`
or `X: none (skipped: <reason>)`. `x_failed` already counts as a failure
(`build_audit_line` matches "fail" in the type).

**`PASS_THROUGH`** gains `X_SECTION`, so `fill` and `build` leave it alone the
way they leave `AUDIT_LINE`.

### 3.2 `templates/morning.md`

`{{X_SECTION}}` on its own line right before `{{AUDIT_LINE}}`, and the "Last
line" rule becomes "Last lines": both placeholders are copied exactly, code
fills both, the write agent never writes either. The "three `##` sections
are fixed" rule gets one sentence: the write agent writes three, and code
appends a fourth from the X run. Nothing else in the shape moves: the X
section lands after Worth Yaron's attention, as asked.

### 3.3 `SKILL.md`

- Description: "Does NOT read X" becomes "Runs the X-list pipeline in
  `x-lists/` in parallel and appends its section under the article brief".
- "Where things live": a row for the X pipeline (`x-lists/`, its own
  `settings.md`, its own `GOAL.md` guardrails).
- **Step 1** gains a second command right after `start`: `x-start`. Say what
  `skipped` means (the brief goes on without X) and that nothing about X is
  touched again until step 6.
- **Step 6**, first line, right after `read-list`: `x-start --retry`. It
  launches only when the first run has failed, once; on `running` or
  `completed` it does nothing and says so. One note for the orchestrator: a
  failure inside a pooled X step can take a while to surface, because the
  chain waits for its other agents to finish before it exits, so `running`
  at step 6 is not proof that all is well. Nothing to do about it there.
- **Step 10**: after the brief is written to `brief.md`: `x-wait` (Bash
  `timeout: 600000`), then `x-merge`, then `audit-line --append`, then
  `close`. Report the audit line and the path, as today.
- **Hard rules**: rule 2 gets one sentence: the X pipeline's models are in
  `x-lists/settings.md`, through `x_run.py`, never through the Agent tool.
  New rule 13: the orchestrator never opens X, never runs `x_run.py` by hand,
  and never starts a second X run while one is recorded as running; `x-start`
  is the only door and one retry is the ceiling.

### 3.4 Tests

`tests/test-bookkeeping-v4.py`, with a stub `x_run.py` injected through an
environment variable (`YBS_X_RUN`, read only by `x-start`, defaulting to the
real path) so no test touches the browser or the network:

- `x-start` records `x.run_dir`, `pid`, `log`; refuses a second start while
  running; `--retry` twice is refused; a missing script gives `skipped`.
- the status test walks `running` → `completed` when the stub writes
  `brief.md` and exits 0, stays `running` while the brief exists but the
  stub is alive, and → `failed` when the stub exits 1, with the `ERROR:`
  reason (and with the last line when there is no `ERROR:`).
- `x-wait` returns `completed` promptly, and `failed` with `timeout` when
  the stub sleeps past `--timeout-seconds 2`, with the stub's process group
  gone afterwards. (The tests run the real settings table; they cannot
  inject a setting, which is why the flag exists.)
- `x-merge`: heading demotion, run-line rewrite, placement at `{{X_SECTION}}`,
  the fallback when the placeholder is missing, the empty replacement on
  `failed`/`skipped`, the counts, the no-picks brief, and refusing a second
  merge.
- Audit line carries the X bit in the three shapes.

`tests/test-prompts-v4.py`: `X_SECTION` joins the pass-through list, and the
template check asserts `{{X_SECTION}}` sits before `{{AUDIT_LINE}}`.

The 4 pre-existing failures stay pre-existing; the new tests must not add to
them.

### 3.5 Housekeeping

- `.claude/skills/update/scripts/update.sh`: `x-lists/settings.md` joins
  `KEEP_BACKUP`, so an update never silently resets the X numbers.
- `README.md`: one paragraph on the X section and where its settings live.
- `.claude/settings.json` allow list: `Bash(python3 x-lists/x_run.py:*)` and
  `Bash(bash x-lists/tests/run-all.sh)`, so a future session can run them
  without a prompt. (Not needed for the run itself: `ybs_run.py` is already
  allowed and spawns X.)
- `DEVLOG.md` entry and `STATUS.md` rewrite at the end.
- Branch `x-in-brief` off `x-lists`; small commits; tag `x-in-brief-v1` when
  the live test passes.

## 4. Timing and load

| when | article side | X side |
|---|---|---|
| 0-7 min | 6 screeners in the browser | scrape (1 task space), then up to 8 readers (8 task spaces), cluster, judge, write |
| 7-12 min | triage (no browser), cluster | done, or finishing |
| 12-30 min | up to 15 readers in the browser | idle |
| 30-40 min | pick, check, counterpoints, write | idle |
| 40-41 min | x-wait (instant), x-merge, audit, close | |

So X adds well under a minute to the wall clock. The 45-minute target is
therefore decided by the article pipeline alone, which has run 34 to 42
minutes since triage batches went to 10. That is the number the test measures.

Peak browser load is the first seven minutes: up to 14 ego task spaces at
once (6 screeners + 8 X readers; the scrape runs before the readers), against
15 today during the article read step. The task-space names never collide
(`x-lists scrape`, `x-lists read <run> batch <i>`, `ybs screen <slug>`). Same order of magnitude, but two pipelines in one browser is the
one new thing the live test has to prove. The knob if it hurts is
`x_agents_active_max` in `x-lists/settings.md` (8 → 4 costs X about a minute).

CPU: up to 8 headless `claude -p` processes alongside the session. The Mac has
overheated before from leftover connectors, so `x-wait`'s timeout kill matters:
nothing X starts outlives step 10.

## 5. What can go wrong, and what happens then

| failure | handled by | brief |
|---|---|---|
| X not logged in / handle wrong | `x_run.py` dies at step 1 | `x-start --retry` at step 6 sees `failed`, launches once, then `X: none (failed: ...)` |
| X page blocked or empty | same | same |
| a `claude -p` agent hangs | `x_run.py` has a 30-min per-call timeout; `x-wait` has its own ceiling | timeout kill (SIGTERM to the group, then SIGKILL), `X: none (failed: timeout ...)` |
| X finishes with no picks | its brief says so in one sentence | section carried as-is |
| write agent drops `{{X_SECTION}}` | `x-merge` fallback placement | X section still lands before the audit line |
| `x-lists/` absent (Yaron's copy before the update) | `x-start` → `skipped` | `X: none (skipped: ...)` |

Never: a second scrape while one is running, an X URL opened by the
orchestrator, a hand-written X section, an edit to the X run's own `brief.md`.

## 6. Order of work

1. **Verify this plan** (Fable, medium): read it against `ybs_run.py`,
   `x_run.py`, `SKILL.md`, the template and the tests. Look for a claim that is
   wrong, a step that cannot work, a rule it breaks, a simpler way. Report
   only what would change the plan.
2. **Implement** (Opus, high): section 3 in full, tests green (same 4 old
   failures at most), `build --check` clean, commits on `x-in-brief`.
3. **Live test** (Sonnet, high, as orchestrator): one real `/ybs-brief morning`
   run, timed from `run.json`, then read `brief.md` against the three success
   parameters: under 45 minutes, both parts present, picks and X picks within
   their ceilings, sentences within `words_per_sentence_max`.
4. DEVLOG, STATUS, tag, push.

## 7. Verifier round (Fable, medium, 2026-09-07)

No blocker. Four should-fix items, all folded in above: the tests cannot
inject a setting (hence `--timeout-seconds`); the Bash tool's 10-minute cap
(hence 9 minutes and the explicit tool timeout); `brief.md` alone is not a
finish signal (hence pid dead **and** brief); the detached child needs
`stdin=DEVNULL`. Its simplification, dropping the separate status command in
favour of `x-start --retry` doing the check, is taken. Confirmed sound:
`--run-dir` end to end, PATH and permissions for the nested `claude -p`,
`killpg` reaching the browser and agent children, the pass-through handling,
the merge shape, the task-space names, and that no `x-lists/GOAL.md`
guardrail is bent.
