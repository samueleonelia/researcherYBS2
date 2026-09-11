# STATUS: researcherYBS2

_Updated: 2026-09-11 · setup names the known failures_

<!-- Rewrite this file in place. Never append. History belongs in DEVLOG.md. Keep under 60 lines. -->

**What this is:** A Claude Code skill (`/ybs-brief`) that builds a news brief for Yaron Brook from six sources plus two X lists, and `/ybs-shows` which keeps his show profile current.

**Right now:** on branch `afternoon-follows-pointer`, off `evening-human-achievements`, not merged, not pushed. Every story under an afternoon's `## What moved` now carries a `**Follows:**` line holding the morning brief's own heading, verbatim, so he can scan that brief for the story being carried forward instead of reading a paraphrase. Behind it sits `evening-human-achievements` (the evening report, plus the root clear-out: `plans/` gone, the X engine under the skill, output in `briefs/`), and behind that the afternoon update on `main`. All three slots have now run live at least once; the X half has been failing since 09-10 on an expired `claude -p` login.

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
| X lists (`.claude/skills/ybs-brief/x-lists/`) | ⚠️ broken | FP and Economists; the engine is fine, the `claude -p` login it runs under is expired |
| X inside `/ybs-brief` | ⚠️ broken | same login; `--retry` resumes the failed step once the login is back |
| Afternoon update | ✅ working | ran live 09-10 and 09-11; article half clean, X half failed both times |
| Evening report | ✅ working | ran live 09-10, X merged |
| Show profile (`/ybs-shows`) | ✅ working | archive and profile refreshed 09-11 |
| Settings | ✅ working | one root `settings.md` |
| Test suite | ⚠️ partial | 4 old failures, see bugs; `/setup` names them instead of counting; `run-all.sh` stops at the first failing file |
| Git remote | ✅ working | github.com/samueleonelia/researcherYBS2 (private) |
| Install (`/setup`) and update (`/update`) | ✅ working | `/update` keeps briefs/, shows/, preferences.md |

## Next up
1. Fix the expired `claude -p` login, then one `/ybs-brief afternoon` live: the first real test of whether a writer copies the morning heading or tidies it
2. One live `/ybs-brief morning` for the no-marker and wait-for-text fixes
3. Merge `afternoon-follows-pointer` into `evening-human-achievements`, then that into `main`, push and tag, then tell Yaron to run `/update`
4. Fix the old test failures and make `run-all.sh` run every file

## Known bugs
- The X engine cannot run: `claude -p` exits 1 on an expired login, so every run since 09-10 carries `x: failed`
- `picks-sync` does not refuse more than 15 picks (2 tests fail)
- `SKILL.md` states one number of its own instead of a `{{settings.*}}` placeholder (1 test fails)
- A beat story picked over a passed-over topic story is not caught (1 test fails)
- Guardian session in ego-browser is not logged in: sign-in wall on paid reads, undated links
- `tests/run-all.sh` stops at the first failing file, so two files never run

## Blocked on you
- Renew the `claude -p` login the X engine runs under; nothing X-side can be tested until then
- Say when to run the morning and the afternoon live, so the three branches can be merged
