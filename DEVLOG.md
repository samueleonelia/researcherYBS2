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
