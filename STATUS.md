# STATUS: researcherYBS2

_Updated: 2026-09-10 · the evening report, and the root cleared_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a news brief for Yaron Brook from six sources plus two X lists, and `/ybs-shows` which keeps his show profile current.

**Right now:** on branch `evening-human-achievements`, not merged, not pushed. Two things sit on it. First, the third slot: `/ybs-brief evening` pools the articles the morning and the afternoon kept at triage, asks a different question of them, and writes one report of the day's human achievements with every story labelled for how far it has got. Second, the root was cleared today: `plans/` is gone, the X engine moved to `.claude/skills/ybs-brief/x-lists/` and its output to `runs/x/`. That move is done in the working tree and committed by the orchestrator as one commit. Both are unit-tested and replayed on scratch fixtures, **never run live**. Behind them sit the no-marker/wait-for-text fixes from the branch before, and the afternoon update on `main`, also never run live.

## Feature areas
| Area | State | Note |
|---|---|---|
| Screen sources (ego browser) | ✅ working | one attempt per source; an evening run refuses to screen at all |
| Pool the day (`pool-sync`) | ✅ unit-tested | the evening's step 2: what the two earlier runs kept, merged by URL; never run live |
| Triage (keep/drop) | ✅ working | batch 10; the evening asks for five kinds of achievement and admits nothing by section |
| Cluster + pick | ✅ working | opus/medium; `pick-evening.md` picks and labels, ceiling `achievements_max` = 5 |
| Read + figure check | ✅ changed, unit-tested | waits up to `read_wait_seconds` for text, then `PAGE_BLANK`; the note now carries `SCALE AND STAGE` |
| Counterpoints (leads only) | ✅ working | neither the afternoon nor the evening has any: no LEAD tag |
| Write the brief | ✅ working | one writer per section; `write-stitch` joins them and checks the evening's label prefix and order |
| X lists (`.claude/skills/ybs-brief/x-lists/`) | ✅ working | FP and Economists; moved under the skill today, output now `runs/x/` |
| X inside `/ybs-brief` | ✅ working | `--retry` resumes the failed step; ran live 09-09, before the move |
| Afternoon update | ✅ unit-tested | base run, `follows`, NEW/MOVED picks, own audit line; never run live |
| Evening report | ✅ unit-tested | pool, five kinds, labels, one section, empty-day sentence, own audit line; never run live |
| Show profile (`/ybs-shows`) | ✅ working | step 0 rebuilds the agent files |
| Settings | ✅ working | one root `settings.md`; `achievements_max` is the newest row |
| Test suite | ⚠️ partial | 5 old failures, see bugs; the cluster-example crash stops the prompt suite early |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install (`/setup`) and update (`/update`) | ✅ working | `/update` keeps runs/, shows/, preferences.md, and now deletes the old root `x-lists/` |

## Next up
1. One live `/ybs-brief evening` on a day with a completed morning run, timed (expect 20 to 25 min). It is also the first live test of the moved X engine.
2. One live `/ybs-brief morning` for the no-marker and wait-for-text fixes
3. One live `/ybs-brief afternoon` against a real morning run, timed
4. Merge this branch into `main`, push and tag, then tell Yaron to run `/update`
5. Fix the old test failures and make `run-all.sh` run every file

## Known bugs
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `tests/test-prompts-v4.py` hard-codes a profile name that `/ybs-shows` has since rotated, so the cluster-example test crashes and the last two tests never run
- `SKILL.md` states one number of its own instead of a `{{settings.*}}` placeholder (1 test fails)
- A beat story picked over a passed-over topic story is not caught (1 test fails)
- Guardian session in ego-browser is not logged in: sign-in wall on paid reads, undated links
- `tests/run-all.sh` stops at the first failing file, so two files never run
- Neither the afternoon nor the evening has seen real data: the `no-move` drop, the new-story floor, the triage keep rate and the pick's labels are all untested against a real day

## Blocked on you
- Say when to run `/ybs-brief evening` live, on top of a morning run
- Say when to run the morning and the afternoon live, so the three branches can be merged
