# STATUS: researcherYBS2

_Updated: 2026-09-08 · preferences.md readable, instructions below the rule_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a morning news brief for Yaron Brook from six sources plus two X lists, and `/ybs-shows` which keeps his show profile current.

**Right now:** on `main`, pushed. Tests at baseline. Next live `/ybs-brief morning` still pending.

## Feature areas
| Area | State | Note |
|---|---|---|
| Screen sources (ego browser) | ✅ working | 6 sources, ~7 min |
| Triage (keep/drop) | ✅ working | batch 10 |
| Cluster + pick | ✅ working | |
| Read + figure check | ✅ working | |
| Counterpoints (leads only) | ✅ working | |
| Write the brief | ✅ working | template = shape, write.md = sentences |
| X lists (`x-lists/`) | ✅ working | FP and Economists, listed in `sources.md`; ~6 min on its own |
| Two-list scrape | ⚠️ untested live | the browser loop over two lists needs one real run |
| X inside `/ybs-brief` | ✅ working | `x-start` / `x-wait` / `x-merge`; effort now reaches the X agents |
| X login-wall stop | ✅ new, unit-tested | scraper dies with a named reason; never seen on real data yet |
| Show profile (`/ybs-shows`) | ✅ working | agents generated from templates, step 0 rebuilds |
| Settings | ✅ working | one root `settings.md`: brief, X, shows; numbers and models; live on next run |
| Test suite | ⚠️ partial | 4 failures predate this branch, see bugs |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install on another Mac (`/setup`) | ✅ working | |
| Update in place (`/update`) | ✅ working | keeps runs/, shows/, preferences.md; backs up settings.md, sources.md; retires old files |
| His standing instructions | ✅ working | `preferences.md`, one shared reader for pick, write and the X judge/write; instructions go below the `---` rule |

## Next up
1. Live `/ybs-brief morning` (proves `--effort` on X agents and the two-list scrape)
2. Watch the seam between an article figure and a tweet figure on the same story
3. Decide whether `world news` and `u.s. news` join `_sections.md`
4. Fix the 4 old test failures and make `run-all.sh` run every file

## Known bugs
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `pick.md` asks for `NOTE_COUNT` and `NOTE_IDS`, which `fill` never provides (1 test fails)
- `tests/run-all.sh` stops at the first failing file, so two files never run
- X: the promoted-tweet rule has never fired on real data; `x_views_per_hour` is loose on purpose and unwatched

## Blocked on you
- Say when to run the next live brief (it drives your browser).
