# Interfaces

The orchestrator fixes these so every step can be built in parallel without
seeing another step's code. A builder reads this plus its own design section.
Do not change a name here; if one looks wrong, stop and say so.

## Run folder

`x-lists/runs/<YYYY-MM-DD>-<HHMM>/` — created by `x_run.py`, UTC, one per run.
Everything a run writes goes inside it. `runs/` is gitignored; never commit it.

## Commands

Every script lives in `x-lists/`, takes `--run-dir DIR`, and takes
`--settings PATH` defaulting to `x-lists/settings.md`. Each prints one summary
line to stdout and exits 0 on success, non-zero on failure.

| command | reads | writes |
|---|---|---|
| `python3 x_scrape.py --run-dir DIR` | the list page | `DIR/tweets.json`, `DIR/page.txt` |
| `python3 x_filter.py --run-dir DIR` | `DIR/tweets.json` | `DIR/kept.json` |
| cluster agent | `DIR/kept.json` | `DIR/subjects.json` |
| `python3 x_score.py --run-dir DIR` | `DIR/kept.json`, `DIR/subjects.json` | `DIR/subjects.json` (rewritten, enriched) |
| judge agent | `DIR/subjects.json` | `DIR/picks.md` |
| `python3 x_run.py` | `settings.md` | the whole run folder |

## Settings

Read from the markdown table in `x-lists/settings.md`, at run time, by name.
No number from that table is ever hard-coded in a script or a prompt.

## tweets.json

```json
{ "list_url": str, "account": str, "scraped_at": iso-Z,
  "window_hours": int, "tweets": [ tweet ] }
```

A `tweet` carries exactly the fields in `tests/fixtures/tweets.json`: the
design's field table plus `promoted` (boolean), which filter rule 1 needs and
the design's table omits. Empty string / 0 / false are allowed; a missing key
is not. `text` has links stripped. `posted_at` is the tweet's own
`<time datetime>`, even for a repost.

## kept.json

```json
{ "run": str, "kept_at": iso-Z,
  "kept": [ tweet ],
  "dropped": [ { "id": str, "rule": 1..5 } ] }
```

`kept` holds whole tweet records, unchanged, in timeline order. Every input
tweet appears in exactly one of `kept` or `dropped`. `rule` is the first rule
that dropped it, in the design's order.

## subjects.json

After cluster:

```json
{ "subjects": [ { "subject": str, "tweet_ids": [ str ] } ] }
```

After score, each subject also carries: `authors` (int), `lists` (int),
`endorsements` (int), `velocity` (float), `velocity_rank` (float, percentile
0-100), `cross_list` (bool), `flags` (list of "CONVERGENCE" / "ENDORSEMENT" /
"VELOCITY"), `tag` ("TRENDING" when flags is non-empty, else "SINGLETON").
Score preserves `subject` and `tweet_ids` untouched.

## picks.md

Markdown. At most `x_picks_max` subjects. Per pick: the subject, its tag
(TRENDING or CURIOUS), its flags, the one tweet that states it best (author,
url, text) and the storyline it touches. Fewer is right when fewer deserve it.

## Agent steps

`x_run.py` runs the two agent steps by filling the prompt and shelling out to
the `claude` CLI headless (`claude -p`), at the model the Models table in
`settings.md` names for that step. The prompts are plain `.md` files in
`x-lists/prompts/` with `{{PLACEHOLDER}}` slots; nothing is registered in
`.claude/`, which is outside `x-lists/` and off limits.

## The window boundary — orchestrator ruling, 2026-09-06

The design and GOAL.md state the window rule at different levels of precision,
and a verifier proved the two readings give different answers. Settled here so
scrape, filter and tests all obey one rule:

> Walk the timeline in order. The boundary is the position of the FIRST tweet in
> the first run of `x_stop_after_old` consecutive **non-repost** tweets whose own
> `posted_at` is older than `x_window_hours` before `scraped_at`. Every tweet
> above that line is in the window — reposts included, and an isolated old
> non-repost included. Every tweet from that line down is out.

Why this reading and not "cut at the first old non-repost":

- It is what GOAL.md check 2 says in as many words ("cut at the first
  `x_stop_after_old` non-repost tweets older than `x_window_hours`"), and the
  design's own wording is the loose one ("non-repost tweets", plural).
- It gives `x_stop_after_old` a job. Under the other reading the setting is dead
  in the filter, and a setting no code obeys is a setting that lies.
- It is the point of the "3 in a row": one stale tweet resurfacing mid-timeline
  must not end the window. That is the failure the run of three exists to stop.

The cost, stated plainly: an isolated tweet older than the window can sit above
the line and be kept. That is deliberate — position, not the tweet's own clock,
is what the design measures. Samuele can overrule it by changing this section.

`x_stop_after_old` therefore does two jobs, and both scripts read it:
`x_scrape.py` stops scrolling at that line, `x_filter.py` cuts rule 3 at it.
