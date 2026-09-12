# STATUS: researcherYBS2

_Updated: 2026-09-12 · the X lane_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a news brief for Yaron Brook from six sources plus two X lists, and `/ybs-shows` which keeps his show profile current.

**Right now:** `main`, tagged `v4.4-x-lane`, pushed: the X lane is what `/update` downloads. The X half no longer spawns a second Claude Code: its four agents are the orchestrator's own, launched from what `x-next` prints, so neither the expired-login failure (this Mac) nor the missing-permission failure (Yaron's) can happen. One live morning run went through the whole lane clean on 09-12: X: 5 picks from 55 subjects, 68 tweets read, 0 retries.

## Feature areas
| Area | State | Note |
|---|---|---|
| Screen sources (ego browser) | ✅ working | one attempt per source; an evening run refuses to screen at all |
| Pool the day (`pool-sync`) | ✅ working | ran live in the 09-10 evening report |
| Triage (keep/drop) | ✅ working | batch 10; the evening asks for five kinds of achievement and admits nothing by section |
| Cluster + pick | ✅ working | opus/medium; `pick-evening.md` picks and labels, ceiling `achievements_max` = 5 |
| Read + figure check | ✅ working | waits up to `read_wait_seconds` for text, then `PAGE_BLANK`; the note carries `SCALE AND STAGE` |
| Counterpoints (leads only) | ✅ working | neither the afternoon nor the evening has any: no LEAD tag |
| Write the brief | ✅ working | one writer per section; `write-stitch` joins them and checks each slot's own heading rules |
| Afternoon `**Follows:**` pointer | ✅ unit-tested | new today: the morning heading, verbatim, checked at the stitch; no writer has produced one yet |
| X lists (`.claude/skills/ybs-brief/x-lists/`) | ✅ working | FP and Economists; scrape and filter detached, the rest is the lane |
| X lane inside `/ybs-brief` | ✅ working | ran live 09-12, every phase on its first attempt; `--closing` at step 10 |
| Afternoon update | ✅ working | ran live 09-10 and 09-11; the X half failed both times on the old chain |
| Evening report | ✅ working | ran live 09-10, X merged |
| Show profile (`/ybs-shows`) | ✅ working | archive and profile refreshed 09-11 |
| Settings | ✅ working | one root `settings.md` |
| Test suite | ⚠️ partial | 4 old failures, see bugs; `/setup` names them instead of counting; `run-all.sh` stops at the first failing file |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install (`/setup`) and update (`/update`) | ✅ working | `/update` keeps briefs/, shows/, preferences.md |

## Next up
1. Yaron runs `/update`, then `/setup`, then a morning brief
2. One live `/ybs-brief afternoon`: the first real test of the `**Follows:**` pointer
3. The 09-12 morning took 46.6 min, over the 45 ceiling: see whether the 55 judge agents at step 6 are the reason
4. Fix the old test failures and make `run-all.sh` run every file

## Known bugs
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `SKILL.md` states one number of its own instead of a `{{settings.*}}` placeholder (1 test fails)
- A beat story picked over a passed-over topic story is not caught (1 test fails)
- Guardian session in ego-browser is not logged in: sign-in wall on paid reads, undated links
- `tests/run-all.sh` stops at the first failing file, so two files never run

## Blocked on you
- Say when to run the afternoon live
