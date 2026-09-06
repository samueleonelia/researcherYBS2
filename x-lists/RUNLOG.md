# RUNLOG

One line per attempt. Newest at the bottom. Read GOAL.md first.

Attempts used this session: 10 / 25

| # | date | step | what changed | check result | next |
|---|---|---|---|---|---|
| 0 | 2026-09-06 | 0 | orchestrator wrote tests/fixtures/tweets.json by hand: 15 tweets, uniform fields, covering 2 reposts, 1 reply, 1 bare link, 1 link+commentary, 1 quote, 1 promoted, 1 short reaction, 3 out-of-window tail. Added `promoted` (bool) beyond the design's field table because filter rule 1 needs it and the table omits it. Also wrote plans/interfaces.md so steps 1-6 can build in parallel. | n/a, not an agent launch | launch wave 1: steps 1,2,3,4,5,6 in parallel |
| 1 | 2026-09-06 | 1 | build x_scrape.py (sonnet/high). Sole owner of the browser this wave. | running | verify checks 1,2 |
| 2 | 2026-09-06 | 2 | build x_filter.py (sonnet/medium), against the fixture. Built; 8 kept / 7 dropped on the fixture. Builder flagged one judgment call: it treats the window boundary as the FIRST non-repost older than the window, which ignores x_stop_after_old. | built, awaiting verdict | verifier 7 |
| 3 | 2026-09-06 | 4 | build x_score.py (sonnet/medium). Percentile = proportion-below inclusive; velocity minutes floored at 1; unknown tweet_ids silently skipped (flagged to verifier). | built, awaiting verdict | verifier 8 |
| 4 | 2026-09-06 | 3 | build prompts/cluster.md (opus/high). Built cluster.md + cluster-merge.md, placeholder-driven, no settings baked in. | built, check 4 needs a real run | verify at integration |
| 5 | 2026-09-06 | 5 | build prompts/judge.md (opus/high). Built judge.md (one subject each) + judge-merge.md (applies x_picks_max). Raised an interface gap: the chain must join subjects against kept.json so the judge gets each tweet url, else check 6 cannot pass. | built, check 6 needs a real run | relay gap to step 6 builder |
| 6 | 2026-09-06 | 6 | build x_run.py + x_settings.py + tests/ (sonnet/medium), against the contract. | running | verify check 7 |
| 7 | 2026-09-06 | 2 | verifier for check 3 (haiku/low), read-only, told to build a case that discriminates the two window wordings. | FAIL: x_stop_after_old never loaded or used; cuts at the first old non-repost, not at a run of x_stop_after_old. Discriminating input proved it. | orchestrator ruled the boundary in plans/interfaces.md; fresh builder, attempt 9 |
| 8 | 2026-09-06 | 4 | verifier for check 5 (haiku/low), read-only, with 4 named probes: unknown id, n=1 rank, zero-minute velocity, hard-coded settings. | PASS. Probes: unknown id silently skipped (acceptable only while check 4 is enforced in tests); zero-minute velocity floored, no blowup; no hard-coded settings. Probe b did NOT exercise a true n=1 run - it ranked inside 7 subjects - so the single-subject case is still untested. | commit x_score.py; retest n=1 at integration |
| 9 | 2026-09-06 | 2 | fresh builder for x_filter.py (sonnet/medium), given the verifier FAIL reason as-is plus the boundary ruling. Implemented the run-of-N boundary; reposts neither extend nor break the run. Fixture unchanged at 8 kept / 7 dropped. Builder correctly flagged that the verifier FAIL text's own "expected" line contradicted the ruling, and followed the ruling. | rebuilt, awaiting verdict | verifier 10 |
| 10 | 2026-09-06 | 2 | re-verifier for check 3 (haiku/low), given the orchestrator ruling as the named authority so it cannot re-fail on the same ambiguity, plus 4 required cases. | PASS on all 4 cases: isolated old tweet kept, repost neither breaks nor extends the run, short run drops nothing, run at position 0 drops everything. Rules applied first-match-wins, order preserved, settings read at run time. | commit x_filter.py |
