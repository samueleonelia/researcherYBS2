# STATUS: researcherYBS2

_Updated: 2026-09-02 · commit a110bba_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief-v4`) that builds a morning news brief for Yaron Brook from six sources, plus `/ybs-shows` which keeps his show profile current.

**Right now:** The pipeline runs end to end (last full run 2 Sep in the old `researcherYBS` folder). The write step now has one template for the shape and one file for the sentence rules, nothing duplicated.

## Feature areas
| Area | State | Note |
|---|---|---|
| Screen sources (ego browser) | ✅ working | 6 sources, ~7 min |
| Triage (keep/drop) | ✅ working | batch of 3, ~7.5 min; batch of 10 not yet tried |
| Cluster + pick | ✅ working | |
| Read + figure check | ✅ working | |
| Counterpoints (leads only) | ✅ working | |
| Write the brief | ✅ working | template = shape, write.md = sentences |
| Show profile (`/ybs-shows`) | ✅ working | |
| Test suite | ⚠️ partial | 4 failures predate this repo, see bugs |
| Git remote | ❌ broken | no GitHub remote yet |

## Next up
1. Set `triage_batch_size` to 10, replay a past run, compare verdicts
2. Decide whether `world news` and `u.s. news` join `_sections.md` (skips ~67 agents a run)
3. Fix the 4 old test failures and make `run-all.sh` run every file
4. Add a `templates/midday.md` when the midday brief starts

## Known bugs
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `pick.md` asks for `NOTE_COUNT` and `NOTE_IDS`, which `fill` never provides (1 test fails)
- `tests/run-all.sh` stops at the first failing file, so two files never run

## Blocked on you
- Create a GitHub remote so milestones can be pushed
