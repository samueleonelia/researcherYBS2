# X lists: decision logic and filtering

Goal: from one X list, find what is trending or curious inside Yaron's interest
areas, in the last 1-2 hours. No X API. Logged-in ego browser, same as the screener.

Account: @EgoismoEfficace, and no other. The scraper checks the handle first.

List (the only X URL the pipeline may open):
- https://x.com/i/lists/2091834809903407159

A second list may be added later; until then `list` is always `B`, `lists` is
always 1 and `cross_list` is always false. Keep the fields so nothing changes
shape when a list is added.

Principle: scripts count, agents group and judge, settings decide. An agent never
decides what "recent" or "enough" means.

## Pipeline

```
  list page ──> [1 SCRAPE] ──> tweets.json ──> [2 FILTER] ──> kept.json
  (script)                     (script)
                                                  │
                                                  v
                                            [3 CLUSTER] ──> subjects.json
                                            (agent, text only)
                                                  │
                                                  v
                                            [4 SCORE] ──> subjects + flags
                                            (script)
                                                  │
                                                  v
                                            [5 JUDGE] ──> picks
                                            (agent, profile + lens)
```

## 1. Scrape (script)

Scroll the list timeline from the top. Stop when `x_stop_after_old` tweets in a row are older
than the window by their timeline position (not their own timestamp, see below).

Per tweet record:

| field | from |
|---|---|
| id, url | status link |
| list | always B for now |
| author | handle |
| reposted_by | "X reposted" line, else empty |
| posted_at | `<time datetime>` of the tweet |
| seen_at | scrape time, UTC |
| text | tweet body, links stripped |
| card_title | link card title, if any |
| quoted_text | embedded quote tweet body |
| is_reply | "Replying to" present |
| has_link | any URL in body |
| replies, reposts, likes, views | full numbers from the action bar aria-label |

Window rule: a repost sits in the timeline at repost time, but its own
timestamp is the original's. So the window boundary is where the timeline
reaches non-repost tweets older than `x_window_hours`. Every tweet above
that line is in, reposts included.

## 2. Filter (script)

Drop, in this order:

1. promoted
2. is_reply = true
3. outside window (see rule above)
4. has_link = true — **any** link, however much commentary rides with it
5. text under `x_min_own_words` and no quoted_text (reactions, emoji)
6. below the engagement floor, which RISES WITH AGE. A tweet clears if any
   one of these holds, where `age_h` is its age in hours at `scraped_at`:

   ```
   reposts >= x_reposts_per_hour * age_h
   likes   >= x_likes_per_hour   * age_h
   views   >= x_views_per_hour   * age_h
   ```

Nothing else is dropped here. Relevance is not decided here.

Rule 4 changed on 2026-09-06. It used to keep a link that carried real
commentary. Samuele's call: a link post sends the reader off X, and the
pipeline cannot follow it, so it is not a story this pipeline can carry.

Rule 6 is new on the same date, and was corrected the same afternoon.

It began as an absolute floor, 10 reposts OR 100 likes at any age. Samuele
killed that after watching the Esh-Tech tweet: at scrape it was 5 minutes old
with 1 repost and 2 likes, so the floor dropped it - and it went on to 20
reposts. Reposts and likes are LAGGING indicators; at five minutes they
measure a tweet's age more than its merit. Worse, an absolute floor
systematically prefers OLDER tweets, which fights the one-hour window's whole
purpose: the GB News tweet cleared the floor with 33 reposts while running the
slowest of the five picks at 66 views per minute.

So the threshold now rises with age, as a rate. The longer a post has been
out, the more it must have earned. Checked against the 0954 run:

| pick | age | reposts | needs | verdict | old floor |
|---|---|---|---|---|---|
| Esh-Tech | 5 min | 1 | 0.9 | clears | dropped |
| Kyiv | 6 min | 13 | 1.0 | clears | cleared |
| GB News | 2.5 h | 33 | 24.6 | clears | cleared |
| Florida | 17.3 h | 623 | 172.8 | clears | cleared |
| Merz | 10 min | 0 | 1.7 | drops | dropped |

Esh-Tech survives, Merz still dies - 0 reposts and 1 like at ten minutes is
absence of traction, not youth. Across all 49 scraped, 19 clear the age-scaled
gate against 21 under the absolute floor.

Two consequences to keep in view. A tweet seconds old needs almost nothing, so
the gate is effectively off at the very top of the window and velocity plus the
judge carry the weight there. And `x_views_per_hour` is the loosest of the
three, since views run orders of magnitude above the others; it is set high on
purpose and should be watched.

**NOT YET IMPLEMENTED.** `x_filter.py` still holds the absolute floor. This is
the spec for the next session.

The filter also writes `links.md`: every survivor as a permalink, marked
POST or REPOST, and nothing that failed a rule. That file is what the read
stage consumes.

## 2b. Read (agents, one tweet page each)

New on 2026-09-06, and the reason the single-URL guardrail was narrowed.

The feed shows a collapsed preview: 15 of 49 tweets in the 0954 run were cut
mid-sentence at ~280 characters, and three of the five picks quoted truncated
text. The fix is to read each surviving tweet on its own page.

A dispatcher splits `links.md` into batches of `x_read_batch` links and runs
one sub-agent per batch, up to `x_agents_active_max` at once. Each sub-agent
opens its links **one at a time** and writes `notes/<id>.md` per tweet:

| field | from |
|---|---|
| id, url, author | the link it was given |
| kind | POST or REPOST, carried from links.md |
| full_text | the tweet's complete text, expanded, never the preview |
| quoted | the quoted tweet's text, if the page shows one |
| media | a one-line description of any image or video |
| posted_at, replies, reposts, likes, views | re-read from the tweet's own page |

The sub-agent opens the tweet permalink and nothing else. Not the author's
profile, not the quoted tweet's own page, not a link inside the tweet. It
reads and writes down; it does not judge, rank or group.

Cluster and judge then work from `notes/`, not from the truncated feed text.

## 3. Cluster (agent, text only)

Input: kept tweets as id, author, text, quoted_text, card_title.
Job: group tweets that are about the same subject. Same job as cluster.md.tmpl.
Output: subject name, tweet ids. A tweet belongs to exactly one subject.
No counting, no ranking, no relevance.

## 4. Score (script)

Per subject compute:

| measure | how |
|---|---|
| authors | distinct author + reposted_by, both lists |
| lists | how many of A, B appear |
| endorsements | max over tweets of (reposts by list members) + quote count inside the subject |
| velocity | max over tweets of views ÷ minutes since posted_at |
| velocity_rank | velocity percentile inside this run's kept set |

Flags, each a setting, any one makes the subject TRENDING:

| flag | test | setting |
|---|---|---|
| CONVERGENCE | authors ≥ N | x_convergence_authors |
| ENDORSEMENT | endorsements ≥ M | x_endorsement_min |
| VELOCITY | velocity_rank ≥ P | x_velocity_percentile |

Bonus, recorded not scored: `cross_list = true` when lists = 2.

Subjects with no flag are SINGLETON candidates and go to step 5 too.

## 5. Judge (agent)

Input: subjects with flags and measures, shows/profile.json storylines,
prompts/_lens.md, preferences.md.

For each subject decide:

```
in interest area?        no ──> DROP
   │ yes
TRENDING flag?           yes ──> KEEP as TRENDING
   │ no
concrete claim?          no ──> DROP      (number, name, place, event; opinion alone is not a story)
   │ yes
velocity_rank ≥ x_curious_percentile?  no ──> DROP
   │ yes
                         KEEP as CURIOUS
```

Output per kept subject: subject, tag (TRENDING / CURIOUS), flags, the one
tweet that states it best, the storyline it touches. Ceiling: `x_picks_max`.

The judge never re-computes counts and never questions the window.

## Settings

The live table is `x-lists/settings.md`. This one is the proposal it started from.

| Setting | Value | What it means |
|---|---|---|
| x_window_hours | 2 | how far back the scrape goes |
| x_min_own_words | 6 | words a tweet must have beyond links to survive |
| x_convergence_authors | 3 | distinct list members on one subject |
| x_endorsement_min | 3 | list-member reposts or quotes of one tweet |
| x_velocity_percentile | 90 | views per minute rank inside the run |
| x_picks_max | 5 | subjects that may reach the brief |

Ceilings, not floors, like everything in settings.md.

## Later

- Save per-author velocity every run. After a week, "above normal for this
  account" becomes a fourth measurable flag.
- Record active-author count per run so the convergence threshold can be tuned
  to list size.
