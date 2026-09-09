# STATUS: researcherYBS2

_Updated: 2026-09-09 · no login marker, and a reader that waits for text_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a news brief for Yaron Brook from six sources plus two X lists, and `/ybs-shows` which keeps his show profile current.

**Right now:** on branch `no-marker-wait-for-text`, not merged, not pushed. Two fixes from the 09-09 morning run are in and unit-tested: the logged-in marker is gone from `sources.md` and the screener, and a reader now waits for the page to show text before it copies it. Neither has been through a live run yet. `main` still carries the afternoon update, also never run live.

## Feature areas
| Area | State | Note |
|---|---|---|
| Screen sources (ego browser) | ✅ working | one attempt per source; no login check any more, a source line is a name and a link |
| Triage (keep/drop) | ✅ working | batch 10 |
| Cluster + pick | ✅ working | opus/medium; replayed live 09-09, nothing trimmed |
| Read + figure check | ✅ changed, unit-tested | waits up to `read_wait_seconds` for text, then `PAGE_BLANK` |
| Counterpoints (leads only) | ✅ working | the afternoon has none: no LEAD tag |
| Write the brief | ✅ working | one writer per section, `write-stitch` joins them in code |
| X lists (`x-lists/`) | ✅ working | FP and Economists; the afternoon runs X exactly as the morning does |
| X inside `/ybs-brief` | ✅ working | `--retry` resumes the failed step; ran live 09-09 |
| Afternoon update (all four waves) | ✅ unit-tested | base run, `follows`, NEW/MOVED picks, own audit line; never run live |
| Show profile (`/ybs-shows`) | ✅ working | step 0 rebuilds the agent files |
| Settings | ✅ working | one root `settings.md`; `read_wait_seconds` is the newest row |
| Test suite | ⚠️ partial | 3 old failures, see bugs; the cluster-example crash stops the prompt suite early |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install (`/setup`) and update (`/update`) | ✅ working | `/update` keeps runs/, shows/, preferences.md |

## Next up
1. One live `/ybs-brief morning` on this branch, then merge it into `main`
2. One live `/ybs-brief afternoon` against a real morning run, timed
3. Push `main` and tag it, then tell Yaron to run `/update` and `/setup`
4. Fix the old test failures and make `run-all.sh` run every file

## Known bugs
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `tests/test-prompts-v4.py` hard-codes a profile name that `/ybs-shows` has since rotated, so the cluster-example test crashes and the merge example never runs
- `SKILL.md` states one number of its own instead of a `{{settings.*}}` placeholder (1 test fails)
- Guardian session in ego-browser is not logged in: sign-in wall on paid reads, undated links
- `tests/run-all.sh` stops at the first failing file, so two files never run
- The afternoon has never seen real data: the `no-move` drop and the new-story floor are untested against a real day

## Blocked on you
- Say when to run `/ybs-brief morning` live on this branch, so the two fixes get a real day behind them
- Say when to run the afternoon update live, on top of a morning run
