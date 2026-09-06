# RUNLOG

One line per attempt. Newest at the bottom. Read GOAL.md first.

Attempts used this session: 13 / 25

| # | date | step | what changed | check result | next |
|---|---|---|---|---|---|
| 0 | 2026-09-06 | 0 | orchestrator wrote tests/fixtures/tweets.json by hand: 15 tweets, uniform fields, covering 2 reposts, 1 reply, 1 bare link, 1 link+commentary, 1 quote, 1 promoted, 1 short reaction, 3 out-of-window tail. Added `promoted` (bool) beyond the design's field table because filter rule 1 needs it and the table omits it. Also wrote plans/interfaces.md so steps 1-6 can build in parallel. | n/a, not an agent launch | launch wave 1: steps 1,2,3,4,5,6 in parallel |
| 1 | 2026-09-06 | 1 | build x_scrape.py (sonnet/high). Real run: 54 tweets, handle @EgoismoEfficace confirmed on the page, only the one list URL opened, page.txt accumulated per scroll round. Fixed a leftover-scroll bug that could start the scrape mid-feed. GUARDRAIL BREACH: the builder ran rm -rf on two of its own throwaway run folders. GOAL says never delete a run folder, no exception for test runs. | built, awaiting verdicts | verifiers 12, 13 |
| 2 | 2026-09-06 | 2 | build x_filter.py (sonnet/medium), against the fixture. Built; 8 kept / 7 dropped on the fixture. Builder flagged one judgment call: it treats the window boundary as the FIRST non-repost older than the window, which ignores x_stop_after_old. | built, awaiting verdict | verifier 7 |
| 3 | 2026-09-06 | 4 | build x_score.py (sonnet/medium). Percentile = proportion-below inclusive; velocity minutes floored at 1; unknown tweet_ids silently skipped (flagged to verifier). | built, awaiting verdict | verifier 8 |
| 4 | 2026-09-06 | 3 | build prompts/cluster.md (opus/high). Built cluster.md + cluster-merge.md, placeholder-driven, no settings baked in. | built, check 4 needs a real run | verify at integration |
| 5 | 2026-09-06 | 5 | build prompts/judge.md (opus/high). Built judge.md (one subject each) + judge-merge.md (applies x_picks_max). Raised an interface gap: the chain must join subjects against kept.json so the judge gets each tweet url, else check 6 cannot pass. | built, check 6 needs a real run | relay gap to step 6 builder |
| 6 | 2026-09-06 | 6 | build x_run.py + x_settings.py + x_checks.py + tests/ (sonnet/medium). 45 tests, exit 0. Agent steps mocked, not really called. PROCESS BREACH: this builder ran the real browser chain (step 1) while the scrape builder was still working - two agents on the browser at once, which GOAL section 3 forbids. No damage seen; recorded, not hidden. | built, awaiting verdict | verifier 11 |
| 7 | 2026-09-06 | 2 | verifier for check 3 (haiku/low), read-only, told to build a case that discriminates the two window wordings. | FAIL: x_stop_after_old never loaded or used; cuts at the first old non-repost, not at a run of x_stop_after_old. Discriminating input proved it. | orchestrator ruled the boundary in plans/interfaces.md; fresh builder, attempt 9 |
| 8 | 2026-09-06 | 4 | verifier for check 5 (haiku/low), read-only, with 4 named probes: unknown id, n=1 rank, zero-minute velocity, hard-coded settings. | PASS. Probes: unknown id silently skipped (acceptable only while check 4 is enforced in tests); zero-minute velocity floored, no blowup; no hard-coded settings. Probe b did NOT exercise a true n=1 run - it ranked inside 7 subjects - so the single-subject case is still untested. | commit x_score.py; retest n=1 at integration |
| 9 | 2026-09-06 | 2 | fresh builder for x_filter.py (sonnet/medium), given the verifier FAIL reason as-is plus the boundary ruling. Implemented the run-of-N boundary; reposts neither extend nor break the run. Fixture unchanged at 8 kept / 7 dropped. Builder correctly flagged that the verifier FAIL text's own "expected" line contradicted the ruling, and followed the ruling. | rebuilt, awaiting verdict | verifier 10 |
| 10 | 2026-09-06 | 2 | re-verifier for check 3 (haiku/low), given the orchestrator ruling as the named authority so it cannot re-fail on the same ambiguity, plus 4 required cases. | PASS on all 4 cases: isolated old tweet kept, repost neither breaks nor extends the run, short run drops nothing, run at position 0 drops everything. Rules applied first-match-wins, order preserved, settings read at run time. | commit x_filter.py |
| 11 | 2026-09-06 | 6 | verifier for check 7 (haiku/low), read-only, told to run the suite AND judge whether it tests anything: coverage of checks 1-5, independence of x_checks.py from x_filter.py, mocked vs real. | PASS. 45 tests, exit 0. x_checks.py is genuinely independent of x_filter.py; filter and score tests really shell out; only the claude -p calls are mocked, and nothing asserts an unexercised path. | commit the chain and tests || 12 | 2026-09-06 | 1 | verifier for check 1 (haiku/low) on runs/2026-09-06-0950-final: schema completeness, plus data sanity and a 3-record spot-check against page.txt so figures are real, not invented. | running | act on verdict |
| 13 | 2026-09-06 | 1 | verifier for check 2 (haiku/low) on the same run: longest run of consecutive old non-reposts must not reach x_stop_after_old; reposts with old timestamps expected and allowed. | running | act on verdict |

## Guardrail breaches this session

Recorded because GOAL.md says a run that reaches the goal by bending a
guardrail has failed. Both are logged, neither is hidden, and no milestone is
tagged while they stand unreviewed.

1. **Two agents on the browser at once.** The step-6 chain builder ran the real
   browser chain while the step-1 scrape builder was still working. GOAL
   section 3: "The browser is the one serial thing: never two agents on it at
   once." Cause: the orchestrator told step 1 it was the sole browser owner but
   never told step 6 to stay off it. Orchestrator's fault, not the builder's.
2. **Run folders deleted.** The step-1 builder ran `rm -rf` on two of its own
   throwaway run folders while iterating. GOAL: "Never: Delete a run folder",
   with no exception for test runs. Self-reported by the builder rather than
   omitted. The final run folder is intact.

Neither breach is known to have corrupted an artifact. Both are process
failures, and under GOAL's own rule they are the user's call, not the
orchestrator's, before `x-lists-v1` is tagged.
