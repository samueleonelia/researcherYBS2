# STATUS: researcherYBS2

_Updated: 2026-10-09 · Yaron's patches 02-07 in main; one scheduled job at a time_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a news brief for Yaron Brook from six sources plus two X lists, `/ybs-shows` which keeps his show profile current, and `/autopilot` + `/ybs-daily` which run both on a schedule on his Mac and email him each brief's Google Drive link.

**Right now:** `main`, tagged `v4.6-yaron-patches`, pushed. On top of the automatic briefs (`v4.5-autopilot`): Yaron's patches 02-07 (X list tabs and reader spaces closed, 0-link screens retried, every ego space closed at `close`), `settings.md` now ships `x_account: @yaronbrook`, and `/ybs-daily` takes a lock so jobs fired together by a waking Mac run one at a time. `update.sh` rehearsed on a copy of v4.5. Nothing yet run on Yaron's Mac.

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
| Show profile (`/ybs-shows`) | ✅ working | asks for English captions since 10-02: YouTube's AI dubs had put Arabic tracks first |
| Settings | ✅ working | one root `settings.md` |
| Test suite | ⚠️ partial | 4 old failures, see bugs; `/setup` names them instead of counting; `run-all.sh` stops at the first failing file |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install (`/setup`) and update (`/update`) | ✅ working | `/update` keeps briefs/, shows/, preferences.md, and `.claude/settings.local.json` |
| Automatic briefs (`/autopilot`, `/ybs-daily`) | ✅ tested here | `daily-lock`: one job at a time; 4 daily tasks (shows 02:00, morning 05:30, afternoon 13:00, evening 19:00); brief to Drive `YBS briefs`, email = time + link + plug; auto mode as the folder default; never run on Yaron's Mac yet |

## Next up
1. Yaron: connect Gmail + Google Drive, then `/update`, `/setup`, `/autopilot`; check the test email arrives unread
2. His first real 05:30 morning email: confirm it arrived, and check the Drive Doc is complete (Claude copies a ~35 KB brief into the upload)
3. One live `/ybs-brief afternoon`: the first real test of the `**Follows:**` pointer
4. The 09-12 morning took 46.6 min, over the 45 ceiling: see whether the 55 judge agents at step 6 are the reason
5. Fix the old test failures and make `run-all.sh` run every file

## Known bugs
- On Samuele's Mac, X runs need `x_account` set back to his own handle locally: `main` ships Yaron's
- `picks-sync` trims an over-ceiling list (by design, per Yaron's Claude); its 2 tests still expect a refusal and should be updated
- `SKILL.md` states one number of its own instead of a `{{settings.*}}` placeholder (1 test fails)
- A beat story picked over a passed-over topic story is not caught (1 test fails)
- Guardian session in ego-browser is not logged in: sign-in wall on paid reads, undated links
- `tests/run-all.sh` stops at the first failing file, so two files never run

## Blocked on you
- Send Yaron the setup steps, and tell him the patches are in `main` (his `fixes-for-samuele` folder can go)
- Say when to run the afternoon live
