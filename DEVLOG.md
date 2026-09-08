# DEVLOG — researcherYBS2

## 2026-09-02 — repo init, write-prompt tidy

**Status:** branch `tidy-write-prompt`, merged to `main` and tagged `v4.1-single-source-template`.

**Done**
- `git init`; existing `.gitignore` kept (runs/, show archives, secrets).
- Audit of every file that reaches the write agent: 35 instructions stated in
  2+ files, 9 contradictions (example counterpoint under the wrong lead,
  "four things" listing three, never-invent stated four ways with the complete
  one missing).
- Fix: `templates/morning.md` = the only statement of the brief's shape;
  `prompts/write.md` = the only statement of the sentence rules;
  `BRIEF-STRUCTURE.md` deleted with its `{{STRUCTURE}}` injection; write agent
  card is protocol only and now receives `{{AGENT_RULES}}`.
- Guard test in `tests/test-prompts-v4.py`: write.md may not name a section,
  morning.md may not carry a sentence rule.

**Decisions**
- Reuters "no link" rule removed: the source list is exactly the pick's
  articles, so an outlet outside `sources.md` can never appear.
- Template stays separate from write.md because midday / afternoon briefs will
  get their own `templates/<slot>.md` and share the sentence rules.
- Triage batch size stays 3 for now; raising it to 10 is the next speed lever
  (75 batches -> 23, roughly 7.5 min -> 2-3 min).

**Open issues**
- 4 pre-existing test failures, not caused by this work: 3 in
  `test-bookkeeping-v4.py` (picks-sync refusing >15 picks, beat-over-topic
  check) and 1 in `test-prompts-v4.py` (`pick.md` asks for `NOTE_COUNT`,
  `NOTE_IDS`, which `fill` does not provide).
- `tests/run-all.sh` uses `set -e`, so it stops at the first file's failure
  and never runs the other two.
- `V5-UPDATES.md` lives only in the old `researcherYBS` folder and is stale.
- No GitHub remote yet.

**Next**
- Raise `triage_batch_size` to 10 and verify against a past run's verdicts.
- Consider adding `world news` / `u.s. news` to `_sections.md`.
- Fix the 4 pre-existing test failures.

## 2026-09-02 — GitHub remote, triage batch size

**Status:** `main`, pushed to `github.com/samueleonelia/researcherYBS2` (private).

**Done**
- Created the GitHub repo (private) and pushed `main` plus the
  `v4.1-single-source-template` tag.
- Raised `triage_batch_size` from 3 to 10 in `settings.md`
  (225 non-admitted articles: 75 batches -> 23). Rebuilt agent files, same 4
  pre-existing test failures, no new ones.

**Open issues**
- The batch-size change was **not verified with a live verdict diff**: this
  session cannot launch the project's own `ybs4-triage` subagent outside the
  running `/ybs-brief-v4` skill (only the fixed built-in agent types are
  available here). Reasoned safe from the agent's own rules instead (tiny
  input, one-word output, code re-batches malformed files, cross-contamination
  already forbidden explicitly) — but the next real run is the first live
  check.

**Next**
- On the next real `/ybs-brief-v4` run: compare its triage verdicts against a
  past batch-3 run's for the same articles, watch for flips.
- Consider adding `world news` / `u.s. news` to `_sections.md`.
- Fix the 4 pre-existing test failures.

## 2026-09-05 — skill renamed to /ybs-brief

**Status:** `main`, pushed.

**Done**
- Renamed the skill folder `.claude/skills/ybs-brief-v4` -> `.claude/skills/ybs-brief`
  and the name everywhere it is spoken: SKILL.md, agent templates and the
  generated agent files, `ybs_run.py` docstrings, the tests, the permission
  allow list in `.claude/settings.json`, the cross-reference in the shows
  skill, STATUS.md. Older DEVLOG entries keep the old name (history).
- Checked for side effects: no run folder references the name; the old
  `researcherYBS` folder is separate and untouched; `~/.claude.json` only
  logs the old path in a history list, harmless. Agent names stay `ybs4-*`
  and test files stay `*-v4.py`: internal only, nothing user-facing.
- `build --check` clean, preflight prints as before, tests: same 4 known
  failures, shows suite all green.

**Next**
- Install on Yaron's Mac (plan: one setup script, terminal Claude Code, a
  Desktop launcher; see `~/.claude/plans/i-have-to-install-humming-beacon.md`).

## 2026-09-05 — /setup and /update, install without a terminal

**Status:** `main`, pushed.

**Done**
- `/setup` (`.claude/skills/setup/`): installs yt-dlp (official standalone
  build) and Node (official tarball for the chip) into `~/.local`, adds that
  folder to `~/.zshrc`, then prints three lists: the tools, the project's own
  checks (agent files, sources, archive) and the tests. No password, nothing
  system-wide, no file in this project touched. Written for bash 3.2, every
  step checked before it runs, no step aborts the script.
- `/update` (`.claude/skills/update/`): replaces the project from the published
  zip. `runs/` and `shows/` are never touched; new show digests are added but
  never overwrite; `sources.md` and the two `settings.md` are replaced with the
  user's copy kept as `.backup` only when it actually differed.
- Both Python scripts now prepend `~/.local/bin` and `~/.local/node/bin` to
  their own PATH, so a run works before the Claude app has been restarted (the
  app builds its PATH from `~/.zshrc` at launch). The `yt-dlp` missing-message
  now says "run /setup" instead of naming Homebrew.
- `README.md`: install, daily routine, the two editable files, troubleshooting.
- `.gitignore`: `.claude/worktrees/`.

**Decisions**
- Zip, not git, for Yaron's copy. On a git folder the desktop app gives every
  extra session its own worktree, and a brief written there would be hard to
  find. Without git every session works in the same folder.
- Desktop app, not the CLI: docs say a Local session runs on the files directly
  and the app includes Claude Code. The `.claude/agents` loading is the one
  thing the docs do not state outright; it is checked on the call.
- No Homebrew anywhere: it needs an admin password and a piped installer cannot
  ask for one. Both tools have official no-install downloads.

**Tested**
- Normal case on this Mac: every line ok, 4 known failures.
- Clean sandbox home (`env -i`, bare system PATH): downloaded and installed both
  tools, wrote the path line, correctly flagged the missing browser.
- PATH fix: with a bare system PATH the shows script still finds yt-dlp.
- `/update` against a local stand-in zip: a brief, a shows file and an edited
  `sources.md` all survived; the new file arrived; `.backup` written.

**Open**
- The repo is still private, so the zip URL 404s. Making it public is the next
  step, and the update path cannot be tested against the real URL until then.

**Next**
- Make the repo public, verify the zip URL, then the call (plan:
  `~/.claude/plans/i-have-to-install-humming-beacon.md`).

## 2026-09-05 — preferences.md, standing instructions in his own words

**Status:** `main`, pushed.

**Done**
- `preferences.md` at the project root: plain sentences, one per line, `#` lines
  are his own notes. Ships once with guidance and examples, all commented out,
  so a fresh copy behaves exactly as before.
- Read by `preferences()` in `ybs_run.py` and injected as `{{PREFERENCES}}` into
  `pick.md` and `write.md`, under a "What he has asked for" section that says
  his instructions outrank the agent's taste but never the hard rules. Missing
  file, empty file or all-comments file all render the same sentence: he has
  asked for nothing in particular.
- `/update` never overwrites it once he has one, and ships the empty one to
  anybody who does not. Its closing line names it alongside runs/ and shows/.
- `tests/test-prompts-v4.py` keeps a hardcoded list of fillable placeholders;
  `PREFERENCES` added there. Same 4 known failures, no new ones.

**Decisions**
- One file, not a learning system. He writes what he wants, or tells Claude to
  add a line. The automatic version, where the pipeline compares what the brief
  offered against what he actually covered on the show, is deliberately not
  built: today it would be a guess at what he wants to teach it.
- Root, not `prompts/_preferences.md`. The root is where his files live
  (`sources.md`), and `prompts/` is pipeline internals. The split is now: root =
  his, everything else = the machine's.
- Injected into pick and write only. Triage sees one article at a time with no
  context to apply a preference against.

**Next**
- The call. After two weeks of real briefs, revisit whether his corrections
  cluster into something worth automating.

## 2026-09-07 — the X list runs inside /ybs-brief

**Status:** branch `x-in-brief` (off `x-lists`), tagged `x-in-brief-v1`, pushed.
Neither branch is merged to `main` yet.

**Done**
- Plan in `plans/x-in-brief.md`, verified by a separate agent (no blocker, four
  should-fix items folded in), then implemented and tested by a third.
- `ybs_run.py` gained `x-start`, `x-wait` and `x-merge`. Step 1 starts
  `x-lists/x_run.py` as one detached process (its own process group, stdin
  closed, log in `<run_dir>/x/x-run.log`); step 6 offers it one relaunch if it
  failed; step 10 waits for it (9 minutes at most, then the group is killed),
  turns its brief into a fourth `##` section under Worth Yaron's attention,
  and the audit line gains an `X:` bit. `{{X_SECTION}}` in the template is a
  pass-through like the audit line. Nothing in `x-lists/` changed.
- Live test with a Sonnet orchestrator at high effort, headless
  (`claude -p "/ybs-brief morning" --model sonnet --effort high`):
  run `2026-09-07_morning_125113`, 10:51:13Z to 11:27:44Z, **36.5 minutes**.
  X started 3 s after the run, scraped 78 tweets beside the six screeners,
  kept 24, read all 24, judged 21 subjects, wrote its brief by 10:56:56Z.
  Merged brief: 15 picks (5 leads, 4 worth), 5 X picks (3 TRENDING, 2 CURIOUS),
  longest sentence 25 words, 0 failures, no stray process left behind.
- 43 new bookkeeping tests, a pass-through test; same 4 old failures, no new.
- `update.sh` keeps `x-lists/settings.md` with a `.backup`; README says where
  the X section comes from; two allow-list entries for the X script and tests.

**Decisions**
- The X pipeline stays a separate process, not Agent-tool subagents: it is
  verified as is, its guardrails live in `x-lists/GOAL.md`, and one detached
  process is the simplest true parallelism.
- The merge is code, not the write agent: the X write step already passes its
  own check 10, and concatenation keeps both briefs' checks valid.
- `completed` means the X process is gone AND its brief exists; the file
  alone is not enough because the X write agent may still be editing it.
- Storyline and Flags bullets are kept in the merged section for now.

**Seen on the test, not failures**
- Lead 1 and X item 2 give different AfD percentages (43.8% from an article,
  44.5% from a tweet). Each traces to its own note. Worth a look at whether
  the seam should be smoothed: a later write step that sees both, or nothing.
- The Times of Israel screener timed out once and succeeded on retry.

**Next**
- Merge `x-in-brief` (which contains `x-lists`) into `main` when Samuele says.
- Watch `x_views_per_hour` and the AfD-style seam over a few real mornings.

## 2026-09-07 — `x-in-brief` merged into `main`

**Done**
- Merged `x-in-brief` into `main` with a merge commit (`7e661b4`). It carries
  the whole `x-lists/` pipeline as well, since `x-lists` was its base.
- Re-ran the tests on `main` after the merge: every `x-lists` test passes; the
  main suite shows the same 4 pre-existing failures and no new ones.
- Tagged `x-in-brief-merged` and pushed `main` to `origin`.

**Next**
- Watch `x_views_per_hour` and the AfD-style seam over a few real mornings.
- Fix the 4 old test failures and make `tests/run-all.sh` run every file.

## 2026-09-07 — one `settings.md`, at the project root

**Done**
- The article brief's `settings.md` and `x-lists/settings.md` are one file at
  the project root. Samuele asked for it: two files meant knowing which of two
  places to open to change a number.
- No setting renamed. Each half reads only its own `##` headings: `Numbers`
  and `Models` for the article brief, `X numbers`, `X fixed` and `X models`
  for the X list. `#` headings divide the file for the reader and are ignored
  by the loaders.
- `ybs_run.py` and `x_settings.py` default to `<root>/settings.md` and skip the
  other half's sections. `x_scrape.py` dropped its own table parser and goes
  through `x_settings.py` like every other X script.
- `update.sh` backs up one file instead of two; README, both SKILL.md files and
  `x-lists/GOAL.md` say where a number lives now.
- New tests on both sides that the halves stay apart. All x-lists tests pass;
  the main suite keeps the same 4 pre-existing failures and gains none.

**Decisions**
- Section-scoped reading instead of renaming keys. Both halves name a step
  `cluster`, `read` and `write`; renaming them would have touched every prompt
  and template. Filtering by heading touched two loaders.
- `/ybs-shows` keeps its own `settings.md`. It is a separate job, run on its
  own; Samuele reversed an earlier "merge all three" answer.

**Next**
- Decide whether the X list URL moves into `sources.md` (see the note below).

## 2026-09-07 — more than one X list

**Done, not yet proven live**
- The X lists live in `sources.md` now, under `## X lists`, one line each, the
  same shape as a news source. `x_list_url` left `settings.md`. Two lists are
  configured: the original one and `2091829768081506382` (names are placeholder
  labels, "List one" and "List two", until Samuele renames them).
- `x_scrape.py` reads them one after the other in the same browser, checking the
  handle and the landed URL per list and closing each tab before the next.
- A tweet in two lists is one record: `list` keeps the first list that showed
  it, the new `lists` field carries every one. `cross_list` is `>= 2`, not `== 2`.
- `tweets.json` head: `lists` (name, url, tweets) replaces `list_url`. Check 1
  validates it and refuses a tweet naming a list nothing scraped; check 2
  applies the window rule per list, so an old run at the end of one list cannot
  cut the next one short.
- `x_wait_minutes_max` is a safety timeout now, not a speed target: 30 minutes.
  Samuele's ruling: the 9-minute target was a goal given to the builder, not a
  rule of the skill.

**Open**
- **The acceptance test is a live run.** Nothing here proves the browser loop:
  two lists opened in sequence, the guardrail firing on the second, the tabs
  closing. Run `python3 x-lists/x_run.py --only 1` with ego open and X logged in.
- The section title is still "What the list is moving on", singular, and check
  10 enforces it. Worth deciding whether it becomes "the lists".

## 2026-09-07 — one settings.md, models live, GOAL.md retired

Branch `one-settings`. Plan: `plans/settings-live-and-goal-retired.md`, verified
ALL GOOD after four verifier rounds, then carried out by agents, one per item.

**Done**
- `/ybs-shows` numbers and a new models table live in the root `settings.md`
  under `# The shows`; the skill-local `settings.md` is gone. `ybs_shows.py`
  reads only its two headings, dies on a missing heading or duplicate key.
- Shows agents are generated: `.claude/skills/ybs-shows/agents/shows-*.md.tmpl`
  plus `ybs_shows.py build [--check]`. Step 0 of both skills runs `build`
  unconditionally, so a model edit is live on the next run with nothing else.
- `x_run.py` passes `--effort` to `claude -p` (it never did) and fails loudly
  on a missing `*_model` / `*_effort` row instead of a silent default.
- `x_scrape.py` stops with a named reason when a scroll round adds nothing and
  the page shows a login wall, captcha, rate limit or "Something went wrong".
- `update.sh` retires files a new version no longer ships: the old shows
  settings file is renamed `.backup`, `GOAL.md` and `RUNLOG.md` are deleted.
- `x-lists/GOAL.md` and `RUNLOG.md` removed. Every citation now states the
  rule in place: `x_scrape.py` docstring, `read.md` rule 5, `x_checks.py`
  per-check docstrings, `x_run.py` header table of the ten checks, the X
  models intro in `settings.md`. Build-time and verify rows deleted.
- Tests: same 4 known failures, none new; all x-lists tests green; both
  `build --check` clean. Live `/ybs-shows` (sonnet, headless): 2 new shows,
  1 digested, profile rebuilt from 15 shows.

**Decisions**
- Templates named `shows-*.md.tmpl` so the copied `cmd_build` writes
  `ybs4-shows-*.md` under the existing names.
- `x-lists/plans/` kept: the only account of why the field table and the
  window rule look as they do. Old plan docs may still mention GOAL.md.
- Scheduling and more than one brief a day are future work; nothing in the
  tree blocks them now.

**Next**
- Merge `one-settings` into `main`, push, tag.
- One live `/ybs-brief morning` to see `--effort` reach the X agents.

## 2026-09-08 · preferences.md readable in preview, X reader fixed

**Branch** `preferences-comments`, merged into `main`.

**Done**
- `preferences.md` is now a readable note above a `---` rule, with his
  instructions below it. Only what is under the first `---` reaches a
  prompt; `#` lines and `<!-- -->` comments stay notes. (A first pass hid
  the help in one HTML comment; unreadable in source view, replaced.)
- Bug: `x_run.py` pasted the whole file, help block included, into the X
  judge and X write prompts. The article reader stripped `#` lines, the X
  reader stripped nothing. Both now call the same `preference_lines`.
- `x-lists/tests/test_preferences.py` pins the two copies to identical
  source and checks the real file leaks no example as an instruction.
- Tests: x-lists all green; root suite same 4 known failures.

**Decision**
- The learning loop stays `preferences.md`: one sentence per correction,
  written by a person. No CLAUDE.md, no self-editing prompts.
