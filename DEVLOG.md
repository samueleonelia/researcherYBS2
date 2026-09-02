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
