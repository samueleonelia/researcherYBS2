# STATUS: researcherYBS2

_Updated: 2026-10-10 · sources.md is the user's file: any half may be empty_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a news brief for Yaron Brook from six sources plus two X lists, `/ybs-shows` which keeps his show profile current, and `/autopilot` + `/ybs-daily` which run both on a schedule on his Mac and email him each brief's Google Drive link.

**Right now:** `main`, tagged `v4.11-sources-optional`, pushed. `sources.md` is the user's file: tests and `/setup` only check it exists, an empty file means no search and no email, a missing half is skipped (news-only: no X section; X-only: the brief is the X section), and `/update` never overwrites it (from the update after his next one: his installed v4.10 `/update` still swaps it once, keeping a `.backup`). Two independent reviews: the full case is unchanged on 10 real runs. Rehearsal folder: shows ran 12:02 on v4.10 (1 new show, English), morning 05:43 tomorrow with trimmed sources.

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
| Test suite | ✅ working | every test passes since 10-10; `/setup` treats any failure as new |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install (`/setup`) and update (`/update`) | ✅ working | `/update` keeps briefs/, shows/, preferences.md, sources.md and `.claude/settings.local.json`; settings.md is replaced with a `.backup` |
| Optional halves (`sources.md`) | ✅ reviewed | `halves` command; empty = nothing, news-only = no X, X-only = X brief; no email for a sources choice |
| Automatic briefs (`/autopilot`, `/ybs-daily`) | ✅ rehearsed | `daily-lock`: one job at a time; 4 daily tasks (shows 02:00, morning 05:30, afternoon 13:00, evening 19:00); brief to Drive `YBS briefs`, email = time + link + plug; auto mode as the folder default; never run on Yaron's Mac yet |

## Next up
1. Yaron: connect Gmail + Google Drive, then `/update`, `/setup`, `/autopilot`; check the test email arrives unread
2. His first real 05:30 morning email: confirm it arrived, and check the Drive Doc is complete (Claude copies a ~35 KB brief into the upload)
3. One live `/ybs-brief afternoon`: the first real test of the `**Follows:**` pointer
4. The 09-12 morning took 46.6 min, over the 45 ceiling: see whether the 55 judge agents at step 6 are the reason

## Known bugs
- On Samuele's Mac, X runs need `x_account` set back to his own handle locally: `main` ships Yaron's
- Guardian session in ego-browser is not logged in: sign-in wall on paid reads, undated links

## Blocked on you
- Send Yaron the reply drafted in Gmail (patches thread)
- Delete the rehearsal: its 5 scheduled tasks (`ybs-daily-*`, `ybs-daily-test`) and `../rehearsalYaron`
- Say when to run the afternoon live
