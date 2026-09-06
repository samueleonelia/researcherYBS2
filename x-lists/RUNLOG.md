# RUNLOG

One line per attempt. Newest at the bottom. Read GOAL.md first.

Attempts used this session: 17 / 25

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
| 11 | 2026-09-06 | 6 | verifier for check 7 (haiku/low), read-only, told to run the suite AND judge whether it tests anything: coverage of checks 1-5, independence of x_checks.py from x_filter.py, mocked vs real. | PASS. 45 tests, exit 0. x_checks.py is genuinely independent of x_filter.py; filter and score tests really shell out; only the claude -p calls are mocked, and nothing asserts an unexercised path. | commit the chain and tests || 12 | 2026-09-06 | 1 | verifier for check 1 (haiku/low) on runs/2026-09-06-0950-final: schema completeness, plus data sanity and a 3-record spot-check against page.txt so figures are real, not invented. | PASS. 54 records vs min 20, every field on every record, correct list URL and account, ids agree with urls, 3 spot-checks found verbatim in page.txt. Two soft spots: 1 record with empty text, 1 record with all four metrics at 0. | note the 2 soft records; await check 2 |
| 13 | 2026-09-06 | 1 | verifier for check 2 (haiku/low) on the same run: longest run of consecutive old non-reposts must not reach x_stop_after_old; reposts with old timestamps expected and allowed. | PASS. Longest run of consecutive old non-reposts is 2, under the threshold of 3. 11 old reposts, correctly allowed. Scrape confirmed to start at the top of the timeline, freshest first. | run the chain end to end for checks 4 and 6 |

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
| 14 | 2026-09-06 | all | runner agent (sonnet/medium): one `python3 x_run.py` end to end, real claude -p calls, forbidden from editing anything or deleting a run folder. Launched from an agent because the orchestrator may not open the browser. | exit 0, runs/2026-09-06-0954. 49 scraped, 42 kept, 36 subjects (5 TRENDING, 31 SINGLETON), 5 picks, 8 cut by ceiling. All 5 steps ran, cluster and judge for real. Two things to scrutinise: all 7 drops were rule 2, and 42 tweets became 36 subjects. | verifiers 15, 16, 17 || 15 | 2026-09-06 | 3 | verifier for check 4 (haiku/low) on the real run: id coverage recomputed independently, plus a read of the clustering for over-splitting, since 42 tweets became 36 subjects and thin subjects weaken CONVERGENCE. | PASS. 42 kept ids, 42 placed, 0 missing, 0 duplicated, 0 invented. 32 single / 3 double / 1 four-tweet subject. Over-splitting investigated and dismissed with reasons: the thin subjects are genuinely distinct events, and CONVERGENCE did fire on the 4-source Labour subject. | all 7 checks PASS; hold the tag |
| 16 | 2026-09-06 | 5 | verifier for check 6 (sonnet/medium) on the real run: ceiling, tags, flags copied not invented, every quote matched against the run's own tweet text, and the CURIOUS pick's rank arithmetic. | PASS. All 5 quotes match kept.json character-for-character, no invented quote. Flags copied exactly. CURIOUS pick rank 83.33 >= 50 with empty flags. 13 KEEP verdicts -> 5 picks -> 8 cut, picks a strict subset, nothing padded in. All 5 rest on a concrete claim, none on opinion alone. | await check 4 |
| 17 | 2026-09-06 | 2 | re-verifier for check 3 (haiku/low) on REAL data, not the fixture. Sent because all 7 drops were rule 2 and rules 1, 4, 5 fired on nothing: asked to establish whether nothing qualified or a rule is silently dead. | PASS. Recomputed the filter independently: 42 kept / 7 dropped, matching exactly. Rules 4 and 5 had no inputs because all 3 short tweets carried quoted_text; word counts ran min 3, median 29, max 54. Rule 1 had no inputs because 0 tweets were promoted - which does NOT distinguish a clean timeline from a broken promoted heuristic. | record rule 1 as unproven on real data |

## Redesign, 2026-09-06 (Samuele)

After reading the brief, Samuele found two real bugs the seven checks did not
catch, and changed the design:

- **`text` fell back to `card_title`.** The GB News pick was a bare link share
  whose body field held the link-card headline, so it read as 9 words of
  commentary and rule 4 never fired. 1 of 49 in the 0954 run.
- **Tweet text is captured collapsed.** 15 of 49 tweets cut mid-sentence at
  ~280 chars; three of five picks quoted truncated text. Check 6 compared the
  brief against `kept.json`, which itself held the truncated text, so the
  check could not see it. That is a gap in how check 6 was specified, not a
  verifier failing.

His three decisions:

1. **The single-URL guardrail is narrowed, not removed.** A read stage may open
   a tweet permalink that came out of this run's own scrape. Still forbidden:
   profiles, search, other lists, the quoted tweet's page, links inside tweets.
2. **Rule 4 is now: drop any tweet with a link**, however much commentary.
3. **New rule 6, an engagement floor:** reposts < `x_min_reposts` (10) AND
   likes < `x_min_likes` (100). Either alone clears it. Both editable.

Simulated against the 0954 data: 49 scraped -> 14 survivors (was 42). Three of
the five picks die - the bare-link one, and the two the orchestrator had already
flagged as weak. Both of those had been flagged VELOCITY on near-zero
engagement (0rt/1lk and 1rt/2lk), because velocity is views/minute and a very
fresh tweet scores high on almost no interaction. The engagement floor closes
that hole. Rule 4 also makes the card_title bug moot: that tweet now dies for
having a link at all.

## Finish line

All seven checks in GOAL.md section 2 have a PASS from a fresh read-only
verifier that was not the builder:

| check | what | verdict | judged on |
|---|---|---|---|
| 1 | tweets.json schema and minimum | PASS | real run, 3 records spot-checked against page.txt |
| 2 | window rule | PASS | real run |
| 3 | five filter rules | PASS | fixture, 4 synthetic cases, and recomputed on real data |
| 4 | every kept id in exactly one subject | PASS | real run |
| 5 | subject measures and flags | PASS | scratch run |
| 6 | picks.md | PASS | real run, all 5 quotes matched character-for-character |
| 7 | tests/ | PASS | 45 tests, exit 0 |

`x-lists-v1` is NOT tagged. GOAL.md says to tag when checks 1-7 pass, and it
also says a run that reaches the goal by bending a guardrail has failed. Two
guardrails were bent (see above). The orchestrator will not decide its own way
past that; the tag is Samuele's call.

## Open items, carried forward

Not check failures. Recorded so they are not lost between sessions.

1. **Rule 1 (promoted) has never fired on real data.** The 2026-09-06-0954 run
   contained 0 promoted tweets, so the scraper's promoted heuristic is
   unproven end to end. It cannot be told apart from a heuristic that never
   detects anything. Worth a targeted test against a timeline known to carry
   an ad, or a scrape-side assertion.
2. **Three settings loaders exist.** `x_settings.py` is the shared one, but
   `x_filter.py` and `x_score.py` each carry their own copy, written in
   parallel before it existed. One table, three readers, is the drift the
   settings rule exists to prevent. Consolidate.
3. **The single-subject velocity_rank case is untested.** The check 5 verifier
   believed it had probed n=1 but ranked inside 7 subjects. If a lone subject
   ranks at 100 it trivially trips VELOCITY and every one-subject run comes out
   TRENDING.
4. **Two soft records in the 0950 scrape**: one with empty text, one with all
   four engagement metrics at 0, out of 54. Both plausible; a growing share
   would mean a parsing gap.

| 19 | 2026-09-06 | 2 | builder for x_filter.py (sonnet/medium): rule 4 becomes any-link, new rule 6 engagement floor, plus links.md marking POST or REPOST. Given the orchestrator's expected numbers so it cannot quietly fit itself to a wrong answer. | running | verify checks 3 and 8 |
| 20 | 2026-09-06 | 2b | builder for the read stage (opus/high): prompts/read.md, the dispatcher in x_run.py, and rewiring cluster and judge to read notes/ instead of the truncated feed text. Told to decide serial vs parallel browser access rather than guess, and NOT to drive the real browser while other agents work. | running | verify check 9 |
