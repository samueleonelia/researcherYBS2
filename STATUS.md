# STATUS: researcherYBS2

_Updated: 2026-09-12 · the X lane_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a news brief for Yaron Brook from six sources plus two X lists, and `/ybs-shows` which keeps his show profile current.

**Right now:** on branch `x-lane`, off `main`, not merged. The X half no longer spawns a second Claude Code: its four agents are the orchestrator's own, launched from what `x-next` prints, and the login failure that killed every X run since 09-10 cannot happen any more. Unit tests green; one live run reached the lane's read phase before being stopped by hand; a second is in progress.

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
| X lists (`.claude/skills/ybs-brief/x-lists/`) | 🔄 live test | FP and Economists; scrape and filter detached, the rest is the lane |
| X lane inside `/ybs-brief` | 🔄 live test | `x-next` prints the launches; one retry per phase; `--closing` at step 10 |
| Afternoon update | ✅ working | ran live 09-10 and 09-11; the X half failed both times on the old chain |
| Evening report | ✅ working | ran live 09-10, X merged |
| Show profile (`/ybs-shows`) | ✅ working | archive and profile refreshed 09-11 |
| Settings | ✅ working | one root `settings.md` |
| Test suite | ⚠️ partial | 4 old failures, see bugs; `/setup` names them instead of counting; `run-all.sh` stops at the first failing file |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install (`/setup`) and update (`/update`) | ✅ working | `/update` keeps briefs/, shows/, preferences.md |

## Next up
1. Read the live morning run: X section in `brief.md`, audit line `X: N picks from M subjects`, time from `run.json`
2. Merge `x-lane` into `main`, tag, push, tell Yaron to run `/update`
3. One live `/ybs-brief afternoon`: the first real test of the `**Follows:**` pointer
4. Fix the old test failures and make `run-all.sh` run every file

## Known bugs
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `SKILL.md` states one number of its own instead of a `{{settings.*}}` placeholder (1 test fails)
- A beat story picked over a passed-over topic story is not caught (1 test fails)
- Guardian session in ego-browser is not logged in: sign-in wall on paid reads, undated links
- `tests/run-all.sh` stops at the first failing file, so two files never run

## Blocked on you
- Say when to run the afternoon live
