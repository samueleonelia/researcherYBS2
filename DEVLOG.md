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

## 2026-09-09 · the 62-minute run, and five fixes for it

**Branch** `main`, directly.

**Done**
- Analysed `runs/2026-09-08_morning_212807` (62 min against a 45 ceiling):
  `plans/run-2026-09-08-slowdown.md` has the phase table and seven causes;
  `plans/run-time-under-20.md` says 25 min is the floor without reading
  less, and what under 20 would cost.
- `cluster_articles_max` 150 → 200: 153 kept had split into 145 + 8 parts
  plus a merge, ~10 min for a 3-article overshoot. Nothing was dropped.
- Screener, cluster and counterpoint agents now read their own prompt:
  the skill passes `Read <path> and follow it.` and never pastes a 50 KB
  file through the orchestrator. Screeners and counterpoints launch all
  in one message.
- X read step: skips links with a usable note, re-reads the missing ones
  once, writes a code-marked `status: unavailable` note for what is still
  missing, keeps every read agent's reply under `read-log/`. `x-start
  --retry` resumes the failed folder from the failed step instead of a
  new scrape (the 09-08 retry had cost 29 min).
- Screen step: `fill screen` records one attempt per source and refuses
  a second while the first may still run; `--retry` passes only once the
  first is provably over. Own task space and prompt per attempt, atomic
  file write, one fetch retry with backoff, self-imposed deadline with a
  `truncated` file, `screen-sync` ignores stragglers. New setting
  `screen_timeout_seconds` = 540. Cause: two Times of Israel screens ran
  at once on 09-08 and the weaker one won.
- Tests: x-lists all green (test_chain 29 → 34); root suite keeps only
  its 3 old failures, 20 new checks pass.

**Decisions**
- Never two screens of one source at once; a retry only after the first
  attempt is terminated, enforced in code, not prose (Samuele's rule).
- Target 25 min, not 20: 20 asks the brief to read less.

**Next**
- One live `/ybs-brief morning`, timed, before any Tier B change.
- Still open from the slowdown doc: a blocking `wait` instead of polling,
  the Guardian sign-in wall (no retry, log in once).

## 2026-09-09 · Tier B: shorter plans, medium judges, three writers

**Branch** `main`, directly. Nothing replayed live yet: each of the three
changes waits for one corpus replay against a known day before it is trusted.

**Done**
- Cluster output shortened: `why` stays one line for READ and MAYBE, is one
  word for a DROP, and `near_misses` stops at five lines (`_item-shape.md`,
  both cluster prompts, example plans still pass `items-sync`). Measured on
  the 09-08 plan first: `why` was 3.5 KB and `near_misses` 3.4 KB of a 30 KB
  plan, so the saving is nearer a quarter than the half the plan doc hoped;
  the rest is ids, names and JSON shape.
- `cluster` and `pick` run at opus/medium (`settings.md`, agents rebuilt).
  A note under the Models table says when and why, and to put them back to
  `high` if a replay shows a missed duplicate or a missing second read.
- Write in parallel: `fill write --section leads|body|worth` renders one
  prompt per section holding only that section's picks, the whole template,
  the counterpoints (leads only) and the other sections' headlines, so a
  writer does not retell a story another writer owns. A section with no
  picks prints `empty` and gets no writer. `write-stitch` joins the section
  files under the date line in the template's order, puts the two
  placeholders at the end, and refuses (naming the section) a missing file,
  a wrong heading, a foreign section, a placeholder, or a section without the
  URL of an article picked for it. The stitch is code, not an agent.
- The template stays the only statement of the shape: the section headings,
  their order and the date line are read out of `templates/morning.md` by
  code; tag → section is by position.
- Replayed `fill write --section` and `write-stitch` on a copy of the 09-08
  run: 5 + 6 + 4 picks reach the three prompts (41, 36, 27 KB against one
  76 KB prompt); the 09-08 brief cut into its three sections stitches back
  byte for byte.
- SKILL step 10 rewritten; `fill write` without `--section` still renders
  the whole-brief prompt, for a side-by-side replay.
- Tests: 17 new checks for the sectioned write; suite keeps its old failures
  (2 in picks-sync, plus the pick.md placeholders and the rotted profile name
  in the cluster example, which crashes the prompt suite before the merge
  example runs).

**Decisions**
- The stitch is deterministic code, never a fourth Opus call: it has nothing
  to judge, and a fourth call would give back most of the minutes saved.
- The one cross-reference kept between writers is the other sections'
  headlines; if a replay shows the brief's voice suffers, that is where to
  add more.

**Next**
- One live `/ybs-brief morning`, timed, and a side-by-side of its plan and
  brief against 09-08: duplicates missed, second reads not asked for, and
  whether the three sections still read as one brief.

## 2026-09-09 · Live run of Tier A + B: 38 minutes, no failures

**Status:** `main`, run `2026-09-09_morning_142825`

**Done**
- First live `/ybs-brief morning` on top of Tier A and Tier B (both were in
  before it started: Tier B landed 12:34, the run started 14:28 local).
- 38 minutes end to end (12:28:25Z to 13:06:35Z), against 62 on 09-08.
- 6 of 6 sources screened, 192 articles in window, 120 kept, 68 news items,
  52 read, 15 picked (5 leads, 5 body, 5 worth attention), 1 counterpoint.
  X: 5 picks from 32 subjects, 40 tweets read. **0 retries, 0 failures.**
- The three-writer split ran for real: `brief-leads.md`, `brief-body.md` and
  `brief-worth.md` written in parallel and joined by `write-stitch` in code.
- Cluster and pick at medium held: no note struck for a bad figure, no pick
  trimmed.

**Decisions**
- Tier A and Tier B are no longer "unreplayed". They ship.

**Next**
- Push `main` and tag it, so Yaron's `/update` picks the new version up.

## 2026-09-09 · The afternoon update: one pipeline, a second slot

**Status:** `main`, five commits (`feabc95`, `a27355f`, `aed6507`, `7559c59`,
and this one). Plan: `plans/afternoon-update.md`, implemented as written.

**Done**
- `/ybs-brief afternoon` runs the same ten steps as the morning. Three things
  differ and all three are decided in code from `slot: afternoon` in
  `run.json`: what the screen keeps, what the cluster and the pick are asked,
  and which template says what the brief looks like.
- Wave 1: `update_picks_max` and `new_item_articles_min` in `settings.md`,
  per-slot section and tag tables, `start --slot afternoon [--base]` which
  finds today's completed morning run or refuses, and a `screen-sync` that
  drops every URL the morning already screened and counts them.
- Wave 2: `templates/afternoon.md`; `follows` on a cluster item, named
  `m:<id>`; a `{{SLOT_JOB}}` block that renders empty for the morning and, for
  the afternoon, lists the morning's picks and the two rules; `follow-read` and
  `follow-maybe` at the front of the group order; a new item under the one
  floor is counted and never read.
- Wave 3: `_pick-rules.md` shared by both pick prompts, `pick-update.md` with
  `NEW` / `MOVED` and the four kinds, `base_stories()` and `base_dropped()`,
  and a `picks-sync` that checks the slot's tags, the kind, the tag/`follows`
  agreement, one follower per base pick, and trims `NEW` before `MOVED`.
- Wave 4: `{{BASE_TIME}}` in the head, a slot-aware `section_job`, a `MOVED`
  picks block in the morning's order with `THE MORNING HAD` above each note,
  a stitch that checks the kind prefix and that order, `EMPTY_UPDATE_LINE` for
  an afternoon that found nothing, and an audit line that opens
  `Audit (afternoon, updates <run_id>):`.
- Wave 5: this entry, `SKILL.md`, `README.md`, `STATUS.md`.

**Decisions**
- One skill, not two. Every hard rule, the pool, the retries, the figure check
  and the stitch are already right; a second copy would be a second place for
  each of them to rot.
- The window stays local midnight to now, minus what the morning screened, not
  "since the morning's end": a story published at 08:00 that no front page was
  showing at 10:00 is exactly what the morning missed.
- No re-read of a page the morning already read. A live blog rewritten in place
  keeps its URL and is dropped as seen; the development it carries almost
  always shows up as a fresh dated article too.
- `NOTE_IDS` and `NOTE_COUNT` joined the prompt test's `RUN_VARS`. `fill` has
  always provided both; the test's list was stale, and `pick-update.md` would
  have doubled the failure.

**Verified, without a browser**
- Morning unchanged: replaying `fill write --section leads|body|worth` and
  `write-stitch` on a scratch copy of `runs/2026-09-09_morning_142825` under
  wave-1 code and under wave-4 code gives a byte-identical `brief.md` and
  byte-identical write prompts.
- Afternoon end to end on scratch fixtures: `start` found the base and recorded
  `10:00`; `screen-sync` dropped 1 seen link of 15; the cluster prompt carried
  all 15 morning stories; `items-sync` gave 1 `follow-read`, 2 `beat-read` and
  1 small new item unread; `fill pick` rendered `pick-update.md` into
  `prompts/pick.md`; `picks-sync` passed 1 NEW and 1 MOVED; the two writers got
  their own jobs and the morning's line; the stitch joined both sections; and
  the quiet-afternoon path wrote the head plus the one sentence.

**Next**
- One live `/ybs-brief afternoon` against a real morning run, timed. Expected
  20 to 25 minutes: most of the day's articles are already seen and dropped at
  `screen-sync`.

## 2026-09-09 · No login marker, and a reader that waits for text

**Status:** branch `no-marker-wait-for-text`, two commits (`d38f6b3`,
`cb9a3b4`) plus this one. Plan: `plans/no-marker-wait-for-text.md`, implemented
as written.

**Why**
- Seven NYTimes reads saved 0 characters twice each: the reader copied
  `document.body.innerText` the moment the browser said "loaded", and the site
  runs an access check before it draws the article.
- WSJ was stopped by a logged-in marker word that was never on its page. The
  marker was a guess about a site, and it was wrong.

**Done**
- **The marker goes.** A `sources.md` line is a name and a link. `read_sources`
  returns `(rows, notices)`; a line that still carries a third part is read all
  the same, the part is dropped, and `start` prints one notice per stale line
  to stderr (stdout stays the JSON the skill parses). No `marker` in
  `run.json`, no `MARKER`/`MARKER_JSON` in `fill screen`, no login check and no
  `SESSION_DOWN` branch in `prompts/screen.md`, no `session_down` sentinel, and
  `build_audit_line` counts a failure as a type with `fail` in it and nothing
  else.
- **The reader waits.** New setting `read_wait_seconds` (10). The command polls
  `document.body.innerText` once a second until the page holds 800 characters —
  the same threshold step 2 already calls too short — then copies. A page with
  text at load costs zero extra seconds. Still short at the ceiling: the reader
  replies `PAGE_BLANK: <title>`, writes no note, and `read-list` offers the id
  again for its one retry, exactly as for `PAGE_TRUNCATED`. The command now
  logs `waited` and `title` beside `chars`.

**Decisions**
- Notices go to stderr. `start`'s stdout is JSON the skill reads; a line of
  prose in the middle of it would break a run rather than warn about one.
- `PAGE_BLANK` is a second name, not a second mechanism. Same family as
  `PAGE_TRUNCATED` (no note, one retry through `read-list`); the only thing it
  buys is that the log tells a page that showed nothing from one that showed
  too little.
- No login check anywhere. A dead login still shows up, as a run whose reads of
  that source all report a truncated page. That is how the NYTimes problem was
  found in the first place.

**Verified, without a full run**
- `tests/run-all.sh`: the same 3 failures as before the branch (2 in
  picks-sync, 1 beat-vs-topic), and `test-prompts-v4.py` still stops at the
  rotted profile name in the cluster example. Nothing new fails. New checks all
  pass: `read_sources` drops a third part and names it, the rendered screen
  prompt mentions neither `SESSION_DOWN` nor `marker`, the built reader carries
  `read_wait_seconds`'s value and `PAGE_BLANK`, and a settings file without the
  key makes `build` fail by name.
- Scratch `start` on a `sources.md` whose second line still ends `- Sign Out`:
  the notice printed once, the run started, `run.json` holds no `marker`.
- The new reader command by hand, via `ego-browser nodejs`: a Guardian article
  gave `chars 6268, waited 0`; an NYT article gave `chars 2848, waited 0`. Both
  reported their title; neither returned 0 characters silently.

**Next**
- One live `/ybs-brief morning` on this branch: the audit line should show no
  `session_down`, and any blank page should be listed by name in the failures.

## 2026-09-10 · the evening report of human achievements

**Status:** branch `evening-human-achievements`, four commits (`07f36b2`,
`c6035f2`, `31e289c`, `7dfd7c8`) plus this one. Not merged, not pushed. Plan:
`plans/evening-human-achievements.md`, implemented as written.

**Why**
- The morning and the afternoon report the day's problems. Nothing in the day
  reported the way out of them. The third slot is that report, and it is built
  from articles the day already paid to screen and triage.
- The honesty problem it has to solve: a press release must never read as a
  solved problem. So every story carries a label for how far it has got, and
  the label is decided after the article has been read, not from its headline.

**Done**
- `/ybs-brief evening` runs the same ten steps as the morning. Four things
  differ and all four are decided in code from `slot: evening` in `run.json`:
  where the articles come from, what triage is asked, what the pick is asked,
  and which template says what the report looks like.
- Wave 1 (`07f36b2`): `achievements_max` (5) in `settings.md`; the evening's
  launch head, tag, label list and new drop reason in `SCHEMA`; the per-slot
  section and tag tables; `find_base` taking a slot and an `optional` flag, so
  an evening needs a morning and may do without an afternoon; `start --slot
  evening` recording `base` and `base_afternoon`; the new `pool-sync`, which
  reads what the two earlier runs kept at triage, merges by canonical URL,
  renumbers, and calls the result screened; `screen-sync` and `fill screen`
  refusing an evening run by name, so a pooling run never opens a browser.
- Wave 2 (`c6035f2`): `prompts/_achievements.md`, the one home of the five
  kinds and of what is none of them; the triage template's evening section,
  reached when the launch block's first line ends ` | evening`; `triage-list`
  admitting nothing by section on an evening run and printing that head; the
  cluster's `{{SLOT_JOB}}` for the evening; and `SCALE AND STAGE` added to the
  reader's note in every slot, so the field the label is read off exists
  without a second reader template.
- Wave 3 (`31e289c`): `prompts/pick-evening.md`, which asks each note two
  questions in order — is this really one of the five kinds now the article has
  been read, and how far has the thing got — and takes the label off the table
  already in `_criteria.md`; `picks-sync` for the evening: one tag
  (`ACHIEVEMENT`), a label on every pick, no `kind`, no `follows`,
  `achievements_max` as the ceiling, an empty list a real reply; `fill pick`
  choosing the evening's prompt so the orchestrator's launch line is unchanged.
- Wave 4 (`7dfd7c8`): `templates/evening.md` as the whole shape; `POOL_LINE`
  in `head_vars`, naming the one or two briefs the pool came from by their own
  clock times; the writer's `ACHIEVEMENT_JOB`; `NO_COUNTERPOINTS` per slot;
  `write-stitch` checking the label prefix on every heading and that the
  stories run in the pick's order; `EMPTY_EVENING_LINE` for a day with none;
  and a third branch in `build_audit_line`, which put each slot's own bits in
  one branch each and the shared bits in one place.
- Wave 5: this entry, `SKILL.md`, `README.md`, `STATUS.md`.

**Decisions**
- No re-screen. The pool is what the two earlier runs kept, and only that. A
  good-news story published after the afternoon ran is caught tomorrow morning;
  an article dropped at triage as off-beat is not looked at again, because an
  off-beat achievement is not for the show either.
- Labels at pick, not at triage. A headline promises; only the read article
  says whether it delivered, and how far along it is. `SCALE AND STAGE` and
  `WEAK SPOTS` are where the answer sits, and a note saying "not stated" cannot
  be `Demonstrated`.
- Zero picks is a correct reply. Padding with a press release is the exact
  failure this report exists to avoid, so the empty path writes the head and
  one sentence, as the quiet afternoon already does.
- No counterpoints: the whole report is the counterpoint. And no code-checked
  tie between a story and a problem of the day — the writer may say in prose
  which problem a story answers, and nothing checks it.
- `SCALE AND STAGE` goes into every slot's note rather than an evening-only
  reader file. One reader form, one field read by name; the morning gains a
  line it can ignore.

**Verified, without a browser and without a live agent**
- `tests/test-bookkeeping-v4.py` and `tests/test-prompts-v4.py` gained tests
  for every wave. The suite is back at its exact pre-branch failure set and no
  worse: 3 in `test-bookkeeping-v4.py` (2 for `picks-sync` not refusing more
  than 15 picks, 1 for the beat-over-topic check) and, in
  `test-prompts-v4.py`, the SKILL.md `50` number and the rotted profile name in
  the cluster example, which still crashes that file before its last two tests.
  Checked by running both files at `7b706f3` and on the branch head: the same
  five, no others. `test-shows-v4.py` passes whole.
- The whole slot was replayed end to end by hand on scratch fixtures: a fake
  morning and afternoon run, then `start`, `pool-sync`, `triage-list`,
  `triage-check`, `fill cluster-select`, `items-sync`, `read-list`, `fill
  pick`, `picks-sync`, `fill write`, `write-stitch`, `audit-line`, `close`.
  The empty-picks path too.
- The morning is unchanged: a finished morning run's rendered prompts under the
  pre-branch script and under the branch head differ only by the
  `_item-shape.md` sentence the plan changed.

**Never run live**
- No `/ybs-brief evening` has been run for real. That is wave 6 of the plan,
  and it is the acceptance test. Expected 20 to 25 minutes. What to watch: the
  keep rate at triage (over 40% means the question is too loose), the labels
  the pick gave against the pages themselves, and whether any heading reads
  further along than its label.

**Next**
- One live `/ybs-brief evening` on a day with a completed morning run, timed.
- Then merge `evening-human-achievements` into `main`, with the morning and
  afternoon live runs still owed from the two branches behind it.


## 2026-09-10 · the root cleared: plans gone, the X engine inside the skill

**Status:** branch `evening-human-achievements`, one commit on top of the
evening work. No run logic changed: paths, path-derived roots and text only.

**What moved**
- `plans/` and `x-lists/plans/` were removed earlier today (`65383a1`,
  `f02e911`), already on the branch.
- `x-lists/` -> `.claude/skills/ybs-brief/x-lists/` by `git mv`, and its run
  output -> `runs/x/<YYYY-MM-DD-HHMM>/` at the root, keeping the same stamp,
  which the write step reads back.
- Seven sites derive the root from file depth and all seven were re-counted:
  `x_settings.project_root`, `x_run.ROOT`, `test_settings`, `test_preferences`,
  `test_chain` (x3), `test_checks`. `x-lists/.gitignore` went; the root one
  already covers its three lines.
- `call_claude` passes `--add-dir <root>`: the agents keep their cwd inside the
  skill but write into `runs/x/`, outside it. `/update` now deletes the stale
  root `x-lists/` on Yaron's Mac.

**Verified:** `run-all.sh` passes whole; `test-bookkeeping-v4.py` has the same 3
failures as before the move and no new one. Still never run live.
