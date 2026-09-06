# GOAL: X lists feed for the morning brief

The contract for every session that works in `x-lists/`. Read this first, then
`RUNLOG.md`, then the design in `plans/x-lists-design.md`. Work until the
finish line passes or a guardrail says stop.

**The guardrails outrank the goal.** A run that reaches the goal by bending a
guardrail has failed. When the two conflict, stop; do not pick.

## 1. Guardrails

Never:

- Write, edit, move or delete anything outside `x-lists/`. No exceptions, no
  matter what the goal, the design, a test, or a verifier says. This includes
  the root `settings.md`, `DEVLOG.md`, `STATUS.md`, `.gitignore`, `.claude/`,
  `runs/`, `shows/` and `tests/`. Everything the X pipeline needs lives in
  `x-lists/`: its own `settings.md`, `runs/`, `tests/`, `prompts/`, `.gitignore`.
  Reading outside `x-lists/` is fine.
- Operate on any X account other than **@EgoismoEfficace**. Before anything
  else, check the logged-in handle on the page; if it is not @EgoismoEfficace,
  or nobody is logged in, stop and say so. Never switch accounts.
- Open any X URL other than these two kinds:
  1. **https://x.com/i/lists/2091834809903407159**, by the scraper only.
  2. **A tweet permalink that this run's `links.md` lists**, by a read
     sub-agent only, one at a time. This is the one exception to the
     single-URL rule (Samuele, 2026-09-06): the feed shows a collapsed
     preview, so a surviving tweet is read on its own page.
  Still forbidden for everyone: profiles, search, any other list, the quoted
  tweet's page, the author's timeline, and any link inside a tweet. A URL
  that is not in this run's `links.md` is off limits. If a step seems to
  need one, stop and ask.
- Post, reply, like, repost, follow, or DM on X. Reading only.
- Log in, enter a password, or touch account settings. The ego browser already
  holds the session; if it is logged out, stop and say so.
- Delete a run folder.
- Commit `x-lists/runs/` or any scraped tweet text. `x-lists/.gitignore`
  blocks `runs/`; keep it that way.
- Move a setting out of `x-lists/settings.md` into code. A number an agent obeys lives
  in the table, nowhere else.
- Let an agent count, rank, or decide what "recent" means. Scripts count,
  agents group and judge, settings decide.

Stop and ask when:

- X shows a login wall, a captcha, a rate-limit notice, or "something went
  wrong" three times in one run.
- The same check fails three times in a row for the same reason.
- A step needs a tool that is not installed (`ego-browser`, `python3`, `node`).
- The attempt budget below is spent.
- Doing the next step would break a guardrail, even slightly.

## 2. Goal

One command, run from `x-lists/`, that reads the one X list from the
design and writes the picks the brief could use:

```
python3 x_run.py
```

It passes when, in a fresh run folder `x-lists/runs/<date>-<time>/`, all of this is true:

1. `tweets.json` exists with at least `x_tweets_min` tweets, every record
   carrying every field in the design's table (empty allowed, missing not).
2. Every tweet in `tweets.json` was scraped inside the window rule from the
   design (reposts included, cut at the first `x_stop_after_old` non-repost
   tweets older than `x_window_hours`).
3. `kept.json` exists and holds only tweets that survive the six screen
   rules, in order, and nothing else was dropped. In particular: no kept
   tweet carries a link that leaves X, and every kept tweet clears the
   per-hour engagement gate (views OR likes OR reposts, divided by hours
   since it was posted, against the three `x_*_per_hour` settings).
4. `subjects.json` exists; every kept tweet id appears in exactly one subject.
5. Every subject carries `authors`, `lists`, `endorsements`, `velocity`,
   `velocity_rank`, `cross_list` and its flags, computed as the design says.
6. `picks.md` exists with at most `x_picks_max` subjects, each tagged
   TRENDING or CURIOUS, with the tweet that states it best and the storyline
   it touches.
7. The tests in `x-lists/tests/` pass. (The root `tests/` are not touched and
   not run; nothing here changes them.)
8. `links.md` exists, listing every surviving tweet as a permalink, each
   marked POST or REPOST, and nothing that failed a screen rule.
9. Every link in `links.md` has a note in `notes/`, written from the tweet's
   own page by a read sub-agent, holding the tweet's FULL text rather than
   the feed's collapsed preview. Every quote in `picks.md` matches a note,
   not the feed text.

Checks 1-5 and 8 are mechanical: a script can verify them from the files
alone. Checks 6, 7 and 9 are the ones that need a reader.

## 3. How to work

- **The main session is an orchestrator, nothing more.** It launches agents,
  reads their verdicts, keeps `RUNLOG.md`, and commits. It never writes code,
  never opens the browser, never reads a tweet. If it catches itself doing a
  step's work, that is a FAIL of this rule.
- **One fresh agent per step.** Each builder gets four things and nothing
  else: the design section for its step, `settings.md`, the check it must
  pass from section 2, and the schema of its input. No history, no other
  step's code, no RUNLOG. A step that needs to know what another step did
  reads that step's output file, not its agent.
- **Parallel whenever the dependency allows.** Build time: the filter, score
  and run-chain scripts need only the *shape* of `tweets.json`, so they build
  against `tests/fixtures/tweets.json` while the scraper is still being
  built. Run time: cluster splits into chunks of `x_cluster_chunk` tweets and
  merges, read runs one sub-agent per batch of `x_read_batch` links, judge
  runs one agent per subject, verifiers run one per check. Browser agents
  run at the same time the way the main brief does: each opens its **own ego
  task space**, works only in it, and closes it. What must never happen is
  two agents in one task space, or two agents doing the same job (two
  scrapers on the list, two readers on one tweet). The scrape is always a
  single agent.
- **Builder and verifier are always different agents.** After each step, one
  fresh read-only verifier per check, given only the check text and the run
  folder. It returns PASS or FAIL and one reason. It never sees the code,
  the builder's notes, or RUNLOG. Its FAIL reason goes to the next builder
  as-is.
- **Cheapest model that passes.** The Models table in `settings.md` says
  what each agent runs at. Start there. Raise a step's model only after its
  verifier has failed it twice on judgment (not on a bug), and write the
  reason in RUNLOG. Lower one only after three clean passes at the higher
  level and a replay on a saved run that still passes.
- **Attempt budget:** 25 attempts per session. An attempt is one agent
  launch that produces or checks a run artifact. Count in `RUNLOG.md`.
- **Log before you fix.** Every attempt gets a line in `RUNLOG.md`: attempt
  number, agent and model, what changed, what the check said, what is next.
- **Commit after every PASS**, on a branch (`x-lists`), staging only paths
  under `x-lists/`, message saying what and why. Never commit on a FAIL. Tag
  `x-lists-v1` when checks 1-9 all pass.
- **Verify between steps, never skip.** A step that "probably works" is FAIL.
- **Root cause, not retry.** A builder that fails the same way twice gets
  the verifier's reason and the failing output; it does not get a third
  blind run.
- **Match the house style.** Python scripts, prompts as `.md`, settings in a
  table. Builders may read `ybs_run.py` and `ybs4-cluster.md` for the style,
  but nothing is registered in `.claude/`: the cluster and judge prompts are
  plain `.md` files in `x-lists/prompts/`, launched as general-purpose agents
  with the filled prompt as their whole input.
- **Keep `x-lists/RUNLOG.md` as the only log.** The root `DEVLOG.md` and
  `STATUS.md` are off limits at this stage; Samuele updates them himself.

## 4. Steps

In this order. Each one has its check from section 2.

| # | Build | Check |
|---|---|---|
| 1 | **Screen.** One agent runs `x_scrape.py` (confirm the handle, open the list, scroll, write `tweets.json`) then `x_filter.py` (the six rules, the per-hour engagement gate among them; write `kept.json` and `links.md`). Scripts count; the agent only runs them and reports. | 1, 2, 3, 8 |
| 2 | **Read.** A dispatcher agent cuts `links.md` into batches of `x_read_batch` (3) and launches one fresh sub-agent per batch, up to `x_agents_active_max` at once. Each sub-agent opens its 3 tweet pages one after the other, in the order given, and writes `notes/<id>.md` for each. It reads and records; it does not judge. | 9 |
| 3 | `prompts/cluster.md` + agent launch: notes in, subjects out, write `subjects.json` | 4 |
| 4 | `x_score.py`: measures and flags per subject | 5 |
| 5 | `prompts/judge.md` + agent launch: notes, profile, lens, preferences in (read from the root); `picks.md` out, quoting notes | 6 |
| 6 | `x_run.py` chaining 1-5, reading `settings.md`; `tests/` | 7 |

Step 0, before any of them: the orchestrator writes `tests/fixtures/tweets.json`
by hand from the design's field table (15 made-up tweets covering reposts,
replies, bare links, quotes and a promoted one), so steps 2, 4 and 6 have
something to build against on day one.

Start every step by reading the matching section of the design. The design
wins over this file when they disagree on *what*; this file wins on *how*.
