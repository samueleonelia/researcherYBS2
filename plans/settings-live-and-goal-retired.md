# Plan: every knob in one file, every knob live, GOAL.md retired

**Goal.** Yaron opens one file, `settings.md`, to change any number or any model
in the project, and the change takes effect on the next run with nothing else
to do. Nothing a run obeys is stated in a file he cannot find, and no rule a run
obeys lives in a build-time document.

**Not in scope.** Scheduling, more than one brief a day, and anything in the
X pipeline's behaviour. Nothing an agent does at run time changes; only where
its instructions are kept.

## What is wrong today

1. **A model change in `settings.md` is not live by itself.** The `## Models`
   table reaches the agents only through `ybs_run.py build`, which rewrites
   `.claude/agents/ybs4-*.md`. Step 0 of `/ybs-brief` runs `build --check` and
   tells the orchestrator to run `build` if anything is stale. That works when
   the orchestrator reads carefully; it is one conditional instruction away
   from a silent no-op.
2. **`/ybs-shows` has no model setting at all.** Its three agents carry a
   hand-written `model:` and `effort:` in `.claude/agents/ybs4-shows-*.md`,
   with no table and no `build`. Yaron cannot change them.
3. **The shows numbers hide in `.claude/skills/ybs-shows/settings.md`.** A dot
   folder he will never open, not named in the README's "three files are
   yours", and a second file for `/update` to back up.
4. **`x-lists/GOAL.md` is still pointed at as a rule book.** It was the
   contract for the sessions that *built* the X pipeline: attempt budget,
   commit rules, builder-and-verifier rules, a step table. Three of its rules
   still matter at run time (which account, which URLs, reading only), and
   those already live in `x_scrape.py` and `prompts/read.md`. Yet
   `settings.md` (twice), the brief's `SKILL.md`, `x_checks.py`, `x_scrape.py`,
   `x_run.py` and one test still cite it as the authority. The `## X models`
   table also carries a "Build time" table and four "verify" rows that no
   run-time code reads: `x_run.py` has seven steps and no verifier agent.

## What Yaron sees afterwards

- `settings.md` has three dividers: `# The article brief`, `# The X list`,
  `# The shows`. Each has a numbers table and a models table. The X list keeps
  its `## X fixed` table. Nothing else in the project holds a number or a model.
- He edits a model row, runs the skill, and the run uses it. No other step.
- `x-lists/GOAL.md` and `x-lists/RUNLOG.md` are gone from the working tree
  (history keeps them). Nothing points at them.
- The README's "three files are yours to edit" stays true, and now says that
  the shows' numbers and every model are in `settings.md` too.

## What changes

### A. Models are live on every run

1. **`/ybs-brief` step 0** runs `ybs_run.py build` unconditionally instead of
   `build --check` plus an instruction. `build` already writes only what
   changed and prints the list, so it is safe to run every time. `--check`
   stays for the tests.
2. **`/ybs-shows` gets the same machinery.** New `.claude/skills/ybs-shows/
   agents/{list,digest,profile}.md.tmpl`, made from the three current agent
   files with `model:` and `effort:` replaced by placeholders. New
   `ybs_shows.py build [--check]`, a copy of the brief's `cmd_build` shape,
   rendering `.claude/agents/ybs4-shows-*.md` with the generated-file stamp.
   Step 0 of the shows skill runs `build` after `start`. The generated files
   stay committed, as the brief's do, so a fresh clone works before any run.

### B. One `settings.md`

3. **Move the shows table into the root file** under a `# The shows` divider
   as `## Shows numbers`, and add a `## Shows models` table:

   | Step | Model | Effort | Agents per run |
   |---|---|---|---|
   | list | haiku | low | 1 |
   | digest | sonnet | medium | one per show not yet archived |
   | profile | opus | high | 1 |

   These are the values the agent files carry today; nothing changes at run
   time.
4. **`ybs_shows.py load_settings`** reads the root `settings.md` and only the
   `## Shows numbers` and `## Shows models` headings, the way `x_settings.py`
   scopes its headings. `agents_active_max` and `retries_max` exist in all
   three halves; heading scope is what keeps them apart. A missing heading is
   a hard error, not a fallback.
5. **Delete `.claude/skills/ybs-shows/settings.md`.** Update every pointer:
   the shows `SKILL.md` "Where things live" table, `update.sh`'s
   `KEEP_BACKUP` (drop the line), the settings-file intro paragraph in the root
   `settings.md`, the README, `STATUS.md`.

### C. Retire `GOAL.md`

6. **Every run-time rule in GOAL.md section 1 is confirmed to have a home, or
   gets one.** The implementer walks the list and records the home of each:
   - only `x_account` may read: `x_scrape.py` (handle check per list, dies on
     `wrong_handle`), setting in `## X fixed`;
   - only list URLs from `sources.md`, by the scraper: `x_scrape.py`;
   - only permalinks from `links.md`, one at a time, never off X, never a
     profile, search, quoted page or thread: `prompts/read.md`, "never open"
     list and "one at a time";
   - reading only, no login, no settings: `prompts/read.md`; the scraper is
     code and cannot click;
   - never delete a run folder: `x_run.py` never does; `read.md` rule 5 for
     agents;
   - never commit `x-lists/runs/`: `x-lists/.gitignore`;
   - stop on login wall, captcha, rate limit: check whether `x_scrape.py`
     dies on these; if it scrolls on silently, add the stop.
   Anything found missing is written into the file that owns it, not into a
   new rule book.
7. **The finish-line checks (section 2) become the docstrings of
   `x_checks.py`.** Each `check_N` states its own check in full, and the
   module docstring no longer cites GOAL.md. Checks 6, 9 and 10, which need a
   reader, are stated in the prompt that enforces them (`judge.md`,
   `read.md`, `write.md`) or, where nothing enforces them at run time, noted in
   the `x_run.py` header as what the tests cover.
8. **The model-change rule (section 3, "cheapest model that passes") moves
   into the `## X models` intro** in `settings.md`, in the same words the
   article `## Models` intro already uses. The "Build time" table and the four
   "verify" rows are deleted: no run reads them.
9. **Rewrite every citation** to state the rule instead of pointing:
   `x_run.py` lines 40, 78-79, 392, 575; `x_scrape.py` line 8; `x_checks.py`
   line 2; `x-lists/tests/test_chain.py` line 339; `settings.md` lines 70 and
   114; `.claude/skills/ybs-brief/SKILL.md` line 33, which becomes "the X list:
   its steps | `x-lists/x_run.py`, whose header lists them".
10. **`git rm x-lists/GOAL.md x-lists/RUNLOG.md`.** Both are build history and
    git keeps them. `x-lists/plans/` stays: design documents are history too,
    but they are the only account of *why* the field table and the window rule
    look the way they do.

## Tests

- `tests/test-shows-v4.py`: `load_settings` reads the root file; the three
  model keys exist; `build --check` exits 0 on a clean tree and 1 after a
  model cell is edited in a temp copy.
- `tests/test-prompts-v4.py`: keep the existing `build --check` test.
- `x-lists/tests/test_settings.py`: unchanged keys still load; the deleted
  verify and build-time keys are gone (a test that named one is updated).
- `grep -rn GOAL.md` over the project, outside `.git/` and `DEVLOG.md`, returns
  nothing.
- `zsh tests/run-all.sh` and `bash x-lists/tests/run-all.sh` end with the same
  four known failures as before and no new one.
- A live `/ybs-shows` run, which usually reports nothing new, proves step 0's
  `build` and the moved settings.

## Order of work

1. B (move the shows table, new loader, delete the old file) — the loader is
   the only code with risk.
2. A (templates, `build`, step 0 of both skills).
3. C (walk the guardrails, rewrite citations, delete the two files).
4. README, STATUS.md, DEVLOG.md.

About three hours of agent time. C is the longest because of the guardrail
walk in item 6, and the one step where something may turn up missing.

## Open question for Samuele

None blocking. One choice made here: the X list's model-change rule joins the
X models intro rather than a shared paragraph, so each half of `settings.md`
still reads on its own.
