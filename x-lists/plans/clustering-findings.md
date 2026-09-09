# Finding: tweet clustering produces almost only singletons

_Written 2026-09-08, from the live run `2026-09-07_morning_230949`
(X run `x-lists/runs/2026-09-07-2109`). Observation only — nothing here has
been changed in the code._

## The short version

The X cluster step groups 90 tweets into 77 subjects. **68 of those 77 hold
exactly one tweet.** The step is doing almost no grouping.

That on its own would be harmless. It is not harmless, because **the judge step
runs one `opus/high` agent per subject.** So a run that clusters badly does not
just produce a flat list — it produces a large bill. Tonight: **77 Opus agents
to choose 5 picks.**

## What the run actually did

```
scrape   261 tweets from 2 lists (FP 135, Economists 136)
filter   kept 90, dropped 171   (by rule: 6→52, 4→64, 2→42, 5→7, 3→6)
read     90 notes, 0 failures            sonnet/medium, 30 batches of 3
cluster  2 parts of 60 → 53 + 25 subjects → merged to 77   opus/high
score    12 TRENDING, 65 SINGLETON                          script
judge    77 subjects → 32 KEEP, 45 DROP   opus/high, ONE AGENT PER SUBJECT
write    5 picks                                            opus/high
```

Subject sizes after the merge:

| Tweets in the subject | Subjects |
|---|---|
| 1 | **68** |
| 2 | 7 |
| 3 | 1 |
| 5 | 1 |

The single 5-tweet subject was "Britain to announce a trade ban on Israeli West
Bank settlements" — a real convergence, correctly found.

## It is not a one-night result

| Run | Tweets read | Subjects | Ratio |
|---|---|---|---|
| x-lists standalone, 2026-09-06 | — | 36 (5 TRENDING, **31 SINGLETON**) | 86% singleton |
| `2026-09-07_morning_125113` | 24 | 21 | 0.88 |
| `2026-09-07_morning_140312` | 7 | 7 | 1.00 |
| `2026-09-07_morning_230949` | 90 | 77 | 0.86 |

The ratio has been between 0.86 and 1.00 on every run on disk. **What changed
tonight is volume, not behaviour**: the second list plus an evening window took
the read population from 7 to 90, and the judge population from 7 to 77.

## Why it happens

A tweet is not an article. Six news sites covering one day genuinely overlap —
they all cover the Hormuz blockade, so those reports belong in one item. Two X
lists inside a **two-hour window** mostly do not: list members post about
whatever they are each thinking about, and convergence on a single subject is
the exception the `CONVERGENCE` flag exists to catch.

So the singleton rate is not a bug in the cluster prompt. **It is what the
input looks like.** The cluster agent's own output is good — the subject names
it produced were sharp and correctly scoped ("Ben Gvir attacks the High Court
over Red Cross visits to Nukhba prisoners", "Martenson says China can simply
wait out America as the global order fractures").

## The correction worth recording

An earlier reading of this said the article half "clusters properly" and the X
half does not. **That overstates it.** The same run's article half:

| | Items | Multi-article | Single |
|---|---|---|---|
| Article half | 94 (from 132 articles) | 17 (18%) | 77 |
| X half | 77 (from 90 tweets) | 9 (12%) | 68 |

Both halves are mostly singletons. 18% vs 12% is a difference of degree, not of
kind.

## The real asymmetry is what happens next

This is the finding that matters.

| | Article half | X half |
|---|---|---|
| Units after clustering | 94 items | 77 subjects |
| Who selects | **one** `ybs4-pick` agent, one call, sees every note | **77** judge agents, one per subject |
| Model | opus/high × 1 | opus/high × 77 |

The article half solved this problem already: it hands the whole set to a single
Opus agent that sees everything at once and returns the picks. The X half asks
Opus, seventy-seven separate times, whether one tweet is interesting — and no
one of those agents can see the others.

That also costs judgment, not just money: a per-subject judge cannot weigh two
subjects against each other, so the ceiling has to be applied afterwards by a
merge step rather than by the agent doing the choosing.

`x_curious_percentile` does **not** reduce the population. In
`x_run.py:step_judge` it is passed into each prompt as a threshold the judge
applies to itself:

```python
curious_percentile = settings["x_curious_percentile"]
...
run_pool([make_job(i, s) for i, s in enumerate(subjects)], max_workers)
```

Every subject is judged. The percentile filters inside the agent, after the
agent has already been paid for.

## What the junk costs

The filter is engagement-only. Rules 1–4 drop promoted posts, replies,
out-of-window and link-carrying tweets; rule 5 drops fewer than
`x_min_own_words` (6); rule 6 drops anything under the per-hour engagement
floor. **Nothing asks what a tweet is about.**

Two of the highest-engagement survivors tonight, both from the Economists list:

- "Huge shoutout to my mom for not strangling me when things got tough."
  — 207k likes, 2.4M views
- "we don't talk enough about this" — 58k likes (exactly 6 words, clears rule 5
  by one word)

Both were read by a Sonnet agent, clustered by an Opus agent, and judged by an
Opus agent, before being correctly dropped.

**The pipeline's output was right.** All 5 final picks were substantive
(CENTCOM blockade vessel counts, Bombardier, Kushner on Gaza, the UK settlement
trade ban, US data-centre construction spending). This is a cost problem, not a
quality problem.

## Options

Ranked. None of these has been implemented or tested.

1. **Judge in one call, like the article half does.** One `opus/high` agent over
   all 77 subjects, returning the picks directly, instead of 77 agents plus a
   merge. Biggest saving, and it lets the selector compare subjects against each
   other. Largest change.
2. **Pre-filter the judge population by score.** Judge all `TRENDING` subjects
   (12 tonight) plus only the singletons above `x_curious_percentile`, rather
   than passing the percentile into every agent. Small code change, keeps the
   current shape.
3. **Add a topical gate before the read step.** One cheap Haiku pass over the 90
   filter survivors: "could this matter to a show about politics, economics and
   foreign policy?" Cuts the read *and* the cluster *and* the judge populations
   at once.
4. **Split `x_agents_active_max`.** `x_read_active_max` stays 8 (browser-bound,
   one login against x.com); `x_judge_active_max` goes higher — judging is
   text-only, no browser, no rate limit. Does not reduce cost, only wall-clock.
   Reasoning in full below.
5. **Re-scope the Economists list.** It is not economists: it is a mixed
   political and culture list, and it supplied both of the junk examples above
   as well as genuinely useful material. Either curate it, or accept it and let
   option 3 do the filtering.

Options 2 and 3 are additive and could ship together. Option 1 makes 2 partly
redundant.

## On `x_agents_active_max` (option 4 in full)

Asked during the run: can the ceiling be raised? The answer turns on the fact
that **one setting governs three stages with different constraints.**

| Stage | Opens a browser? | Hits x.com | Safe to widen? |
|---|---|---|---|
| read | yes, one ego task space per batch | **yes, every agent, from one login** | risky |
| cluster | no | no | safe, but only 1–2 parts exist |
| judge | no | no | **safe, and it is the deep one** |

### Why 8 and not 15

The article half runs 15 browser agents happily — but across **six different
domains**. The X read step points all of its agents at **one domain, from one
account** (`x_account = @EgoismoEfficace`). Fifteen tabs against x.com at once
is how the login wall gets tripped — the exact failure `x_scrape.py` was taught
to name and stop on. That asymmetry, not caution in general, is why the X
ceiling is lower than the article one.

### Raising it does not make the brief arrive sooner

X is not the critical path. Tonight the X half finished at 23:29; the brief was
written at 23:49. `x-wait` returned immediately, as the skill says it usually
does. Read was 30 batches at 8 wide — 4 waves, about 7 minutes. At 15 it would
be 2 waves, about 3.5 minutes: **3.5 minutes saved on a step that was holding
nothing up**, against a real rate-limit risk.

### The correction

That reasoning was drawn from the **read** step, and on the read step it stands.
It is wrong about the step that actually takes the time. **The judge step is 77
agents deep** — ten waves at 8 wide — and it is text-only: no browser, no tab,
no request to x.com. Widening *there* carries none of the risk described above.

So the split is worth more than "leave it at 8" implied:

- `x_read_active_max` → **8** (unchanged, browser-bound)
- `x_judge_active_max` → **15** (text-only; roughly halves the judge stage)

This is wall-clock only. It does not reduce the number of Opus judges — that is
what options 1, 2 and 3 are for.

### Two facts worth keeping

- **Editing `settings.md` mid-run changes nothing.** `x_run.py` loads settings
  once in `main()` (`x_run.py:895`) at process start. A value edited while a run
  is going is read by the next run, not the current one.
- **Revisit at three or four lists.** Two lists gave 90 tweets to read. Four
  would give roughly 180 — 60 batches, 8 waves — and X could become the critical
  path. At that point raising the read ceiling buys something real, and the
  rate-limit question has to be answered rather than avoided.

## Open question

Whether the cluster step earns its place at all. If 68 of 77 subjects are one
tweet each, the step is mostly renaming tweets into subjects. Dropping it and
judging tweets directly would lose the 9 real groupings — including tonight's
5-tweet UK settlement convergence, which is exactly the signal the list is read
for. Probably it stays. Worth deciding on purpose rather than by default.
