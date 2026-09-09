# STATUS: researcherYBS2

_Updated: 2026-09-09 · Tier B in, unreplayed_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a morning news brief for Yaron Brook from six sources plus two X lists, and `/ybs-shows` which keeps his show profile current.

**Right now:** on `main`, ahead of the push. Tier A (five speed fixes) and Tier B (shorter plans, medium judges, three writers) are both in and neither has had a live run. The next `/ybs-brief morning` is the timing test and the quality replay for all of it.

## Feature areas
| Area | State | Note |
|---|---|---|
| Screen sources (ego browser) | ✅ working | one attempt per source at a time, retry gated by `fill --retry`; untested live |
| Triage (keep/drop) | ✅ working | batch 10 |
| Cluster + pick | ⚠️ changed, unreplayed | opus/medium since 09-09; DROPs carry a one-word `why`, five near misses; watch for missed duplicates and missing second reads |
| Read + figure check | ✅ working | |
| Counterpoints (leads only) | ✅ working | |
| Write the brief | ⚠️ changed, unreplayed | three writers at once, one per section, `write-stitch` joins them in code; stitch reproduces the 09-08 brief byte for byte |
| X lists (`x-lists/`) | ✅ working | FP and Economists; 17-30 min with the read step |
| Two-list scrape | ⚠️ untested live | the browser loop over two lists needs one real run |
| X inside `/ybs-brief` | ✅ working | read step tolerates missing notes; `--retry` resumes the failed step; untested live |
| X login-wall stop | ✅ new, unit-tested | never seen on real data yet |
| Show profile (`/ybs-shows`) | ✅ working | agents generated from templates, step 0 rebuilds |
| Settings | ✅ working | one root `settings.md`; cluster and pick effort carry a dated note |
| Test suite | ⚠️ partial | 4 old failures, see bugs; the cluster-example crash stops the prompt suite early |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install on another Mac (`/setup`) | ✅ working | |
| Update in place (`/update`) | ✅ working | keeps runs/, shows/, preferences.md; backs up settings.md, sources.md |
| His standing instructions | ✅ working | `preferences.md`, instructions below the `---` rule |

## Next up
1. Live `/ybs-brief morning`, timed: target 25 min; compare its plan and brief with 09-08 (duplicates, second reads, whether the sections read as one brief)
2. If cluster or pick got quieter: effort back to `high` in `settings.md`, one line in DEVLOG
3. Blocking `ybs_run.py wait` so the orchestrator stops polling; Guardian sign-in wall gets no retry
4. Fix the old test failures and make `run-all.sh` run every file

## Known bugs
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `tests/test-prompts-v4.py` hard-codes a profile name that `/ybs-shows` has since rotated, so the cluster-example test crashes and the merge example never runs
- `pick.md` asks for `NOTE_COUNT` and `NOTE_IDS`, which `fill` never provides (1 test fails)
- Guardian session in ego-browser is not logged in: sign-in wall on reads, undated links
- `tests/run-all.sh` stops at the first failing file, so two files never run
- X: the promoted-tweet rule has never fired on real data; `x_views_per_hour` is loose on purpose and unwatched

## Blocked on you
- Say when to run the next live brief (it drives your browser).
