# STATUS: researcherYBS2

_Updated: 2026-09-09 · the afternoon update is in, unreplayed live_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a news brief for Yaron Brook from six sources plus two X lists, and `/ybs-shows` which keeps his show profile current.

**Right now:** on `main`, ahead of the push. The morning brief ran live in `runs/2026-09-09_morning_142825`: 38 minutes, 0 retries, 0 failures, 15 picks. On top of it, `/ybs-brief afternoon` now exists: the same ten steps, a second slot, written and unit-tested but never run live.

## Feature areas
| Area | State | Note |
|---|---|---|
| Screen sources (ego browser) | ✅ working | one attempt per source at a time, retry gated by `fill --retry` |
| Triage (keep/drop) | ✅ working | batch 10 |
| Cluster + pick | ✅ working | opus/medium; replayed live 09-09, nothing trimmed |
| Read + figure check | ✅ working | |
| Counterpoints (leads only) | ✅ working | the afternoon has none: no LEAD tag |
| Write the brief | ✅ working | one writer per section, `write-stitch` joins them in code |
| X lists (`x-lists/`) | ✅ working | FP and Economists; the afternoon runs X exactly as the morning does |
| X inside `/ybs-brief` | ✅ working | `--retry` resumes the failed step; ran live 09-09 |
| Afternoon: base run + window | ✅ new, unit-tested | finds today's completed morning run or refuses; drops every URL it saw |
| Afternoon: cluster `follows` | ✅ new, unit-tested | `m:<id>`, follow-read first, a new item under the floor is never read |
| Afternoon: the update's pick | ✅ new, unit-tested | NEW / MOVED with a kind, one follower per morning story |
| Afternoon: write + audit | ✅ new, unit-tested | two sections, morning's order, its own audit line |
| Show profile (`/ybs-shows`) | ✅ working | step 0 rebuilds the agent files |
| Settings | ✅ working | one root `settings.md`; `new_item_articles_min` is its one floor |
| Test suite | ⚠️ partial | 4 old failures, see bugs; the cluster-example crash stops the prompt suite early |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install (`/setup`) and update (`/update`) | ✅ working | `/update` keeps runs/, shows/, preferences.md |

## Next up
1. One live `/ybs-brief afternoon` against a real morning run, timed (it drives your browser)
2. Push `main` and tag it, then tell Yaron to run `/update` and `/setup`
3. Fix the old test failures and make `run-all.sh` run every file

## Known bugs
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `tests/test-prompts-v4.py` hard-codes a profile name that `/ybs-shows` has since rotated, so the cluster-example test crashes and the merge example never runs
- `SKILL.md` states one number of its own instead of a `{{settings.*}}` placeholder (1 test fails)
- Guardian session in ego-browser is not logged in: sign-in wall on reads, undated links
- `tests/run-all.sh` stops at the first failing file, so two files never run
- The afternoon has never seen real data: the `no-move` drop and the new-story floor are untested against a real day

## Blocked on you
- Say when to run the afternoon update live, on top of today's morning run
