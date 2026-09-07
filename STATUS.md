# STATUS: researcherYBS2

_Updated: 2026-09-07 · X list runs inside /ybs-brief_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a morning news brief for Yaron Brook from six sources plus one X list, and `/ybs-shows` which keeps his show profile current.

**Right now:** Branch `x-in-brief` (tagged `x-in-brief-v1`, pushed) runs the X pipeline in parallel with the articles and appends its section. Live test: 36.5 minutes, both parts present, every ceiling respected. Not merged to `main` yet.

## Feature areas
| Area | State | Note |
|---|---|---|
| Screen sources (ego browser) | ✅ working | 6 sources, ~7 min |
| Triage (keep/drop) | ✅ working | batch 10, two live runs clean |
| Cluster + pick | ✅ working | |
| Read + figure check | ✅ working | |
| Counterpoints (leads only) | ✅ working | |
| Write the brief | ✅ working | template = shape, write.md = sentences |
| X list (`x-lists/`) | ✅ working | all 10 checks pass; ~6 min on its own |
| X inside `/ybs-brief` | ✅ working | `x-start` / `x-wait` / `x-merge`, section under Worth Yaron's attention |
| Show profile (`/ybs-shows`) | ✅ working | |
| Test suite | ⚠️ partial | 4 failures predate this repo, see bugs |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install on another Mac (`/setup`) | ✅ working | |
| Update in place (`/update`) | ✅ working | keeps runs/, shows/, preferences.md, three settings.md |
| His standing instructions | ✅ working | `preferences.md`, read by pick, write and the X judge/write |

## Next up
1. Merge `x-in-brief` into `main` (it carries `x-lists` too), then push
2. Watch the seam between an article figure and a tweet figure on the same story (AfD 43.8% vs 44.5% on 09-07)
3. Decide whether `world news` and `u.s. news` join `_sections.md`
4. Fix the 4 old test failures and make `run-all.sh` run every file
5. Add a `templates/midday.md` when the midday brief starts

## Known bugs
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `pick.md` asks for `NOTE_COUNT` and `NOTE_IDS`, which `fill` never provides (1 test fails)
- `tests/run-all.sh` stops at the first failing file, so two files never run
- X: the promoted-tweet rule has never fired on real data; `x_views_per_hour` is loose on purpose and unwatched

## Blocked on you
- Say when to merge `x-in-brief` into `main`.
