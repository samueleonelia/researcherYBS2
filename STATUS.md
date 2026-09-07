# STATUS: researcherYBS2

_Updated: 2026-09-07 · X lists live in sources.md_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a morning news brief for Yaron Brook from six sources plus one X list, and `/ybs-shows` which keeps his show profile current.

**Right now:** `main` carries everything. The X pipeline runs in parallel with the articles and appends its section; live test 36.5 minutes, both parts present, every ceiling respected. Merged and pushed 2026-09-07 (tag `x-in-brief-merged`).

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
| More than one X list | ⚠️ untested live | reads every list in `sources.md`; the browser loop needs one real run |
| X inside `/ybs-brief` | ✅ working | `x-start` / `x-wait` / `x-merge`, section under Worth Yaron's attention |
| Show profile (`/ybs-shows`) | ✅ working | |
| Test suite | ⚠️ partial | 4 failures predate this repo, see bugs |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install on another Mac (`/setup`) | ✅ working | |
| Update in place (`/update`) | ✅ working | keeps runs/, shows/, preferences.md, two settings.md |
| His standing instructions | ✅ working | `preferences.md`, read by pick, write and the X judge/write |
| Settings | ✅ working | one root `settings.md` for brief + X; `/ybs-shows` keeps its own |

## Next up
1. Live acceptance run of the two-list scrape: `python3 x-lists/x_run.py --only 1`
2. Rename "List one" / "List two" in `sources.md` to what they actually are
3. Watch the seam between an article figure and a tweet figure on the same story (AfD 43.8% vs 44.5% on 09-07)
4. Decide whether `world news` and `u.s. news` join `_sections.md`
5. Fix the 4 old test failures and make `run-all.sh` run every file

## Known bugs
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `pick.md` asks for `NOTE_COUNT` and `NOTE_IDS`, which `fill` never provides (1 test fails)
- `tests/run-all.sh` stops at the first failing file, so two files never run
- X: the promoted-tweet rule has never fired on real data; `x_views_per_hour` is loose on purpose and unwatched

## Blocked on you
- What are the two X lists actually called? They are labelled "List one" and
  "List two" in `sources.md` right now.
- Say when to run the live two-list scrape (it drives your browser).
