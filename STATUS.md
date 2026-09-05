# STATUS: researcherYBS2

_Updated: 2026-09-05 · /setup and /update added_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a morning news brief for Yaron Brook from six sources, plus `/ybs-shows` which keeps his show profile current.

**Right now:** The pipeline runs end to end. Write step has one template for the shape and one file for the sentence rules. Triage batch size raised 3 -> 10, not yet checked on a live run.

## Feature areas
| Area | State | Note |
|---|---|---|
| Screen sources (ego browser) | ✅ working | 6 sources, ~7 min |
| Triage (keep/drop) | ⚠️ partial | batch 10 set, untested live: see bugs |
| Cluster + pick | ✅ working | |
| Read + figure check | ✅ working | |
| Counterpoints (leads only) | ✅ working | |
| Write the brief | ✅ working | template = shape, write.md = sentences |
| Show profile (`/ybs-shows`) | ✅ working | |
| Test suite | ⚠️ partial | 4 failures predate this repo, see bugs |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install on another Mac (`/setup`) | ✅ working | tested in a clean sandbox home |
| Update in place (`/update`) | ✅ working | keeps runs/ and shows/; needs a public repo |

## Next up
1. On the next real run: compare triage verdicts against a past batch-3 run, watch for flips
2. Decide whether `world news` and `u.s. news` join `_sections.md` (skips ~67 agents a run)
3. Fix the 4 old test failures and make `run-all.sh` run every file
4. Add a `templates/midday.md` when the midday brief starts

## Known bugs
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `pick.md` asks for `NOTE_COUNT` and `NOTE_IDS`, which `fill` never provides (1 test fails)
- `tests/run-all.sh` stops at the first failing file, so two files never run
- `triage_batch_size` was raised to 10 without a live verdict diff (this session can't
  launch the project's own triage subagent outside the real skill run)

## Blocked on you
- Nothing.
