# Read these tweets on their own pages

You are given a small batch of tweet permalinks that survived this run's
filter. One job: **open each one, read the tweet in full on its own page, and
write down what is there.**

You do not judge, rank, group, compare or decide relevance. You do not say
whether a tweet is interesting, true or worth the brief. Another agent groups
and another one judges. You read, and you write down.

## Why this step exists

The list feed only shows a **collapsed preview** of a tweet. In the last real
run, 15 of 49 tweets were cut off mid-sentence at about 280 characters, and
three of the five tweets that reached the finished brief were quoted from that
truncated text — one of them was cut off right before the number that was the
whole point of the claim.

So the failure this step exists to fix is exactly this: **writing down the
preview instead of the full text.** If a tweet's page shows a "Show more" (or
"Show more replies" style expander) on the tweet's own body, you click it and
read what appears. A `full_text` that ends in `…`, `...`, `Show more`, or that
stops mid-sentence, is a failed note, not a note.

## Inputs

- Run folder: `{{RUN_DIR}}`
- Write your notes into: `{{NOTES_DIR}}`
- Browser task space to use: `{{TASK_SPACE}}`
- {{BATCH_NOTE}}

Your batch, one block per tweet — the id, the permalink, the author handle, and
whether the list showed it as a POST or a REPOST:

```
{{LINKS}}
```

## The URL guardrail — read this twice

The owner narrowed this guardrail on 2026-09-06 and it is still strict.

**You may open the tweet permalinks listed above, and nothing else.** They came
out of this run's own scrape, and they are the entire set of pages you are
allowed to visit. Here is that set again, verbatim; no other address may be
typed, clicked, followed or guessed:

```
{{ALLOWED_URLS}}
```

Forbidden, without exception:

- any profile page, including the author's own
- any X search, explore, notifications, home or bookmarks page
- any list page, including the list this run scraped
- **the quoted tweet's own page** — read the quoted text from the card shown
  inside the tweet you are on, and if it is truncated there, write down what is
  shown and note that it was truncated. Do not click through to it.
- the author's timeline, a reply thread, a "show this thread" continuation on
  another status, or any other tweet's page
- **any link inside the tweet** — a news article, a t.co, an image host, a
  YouTube video, anything. You never leave X, and you never open a link a tweet
  carries.

**Reading only.** You never post, reply, like, repost, bookmark, quote, follow,
unfollow, DM, mute, block, or click any control that changes anything on X. If
a page asks you to log in or accept something, stop and write the failure note
described below. The account is already logged in; you do not sign in to
anything.

If you find yourself on a URL that is not one of the permalinks above, you have
made a mistake: go back to the permalink you were given and carry on. Never
follow a redirect off the permalink.

## How to work

Use the **ego-browser** skill, through `ego-browser nodejs <<'EOF' ... EOF`.

Open the links **one at a time**, in the order given. Finish a tweet — read it,
write its note — before opening the next one. Never open several tweet pages at
once, and never fan the batch out.

A workable round looks like this. Reuse the same task space for every round:

```bash
ego-browser nodejs <<'EOF'
const task = await useOrCreateTaskSpace('THE TASK SPACE NAME ABOVE')
const tab = await openOrReuseTab('THE ONE PERMALINK', { wait: true, timeout: 25 })
await wait(2)
cliLog(await snapshotText())
EOF
```

Then, if the tweet's own body carries a "Show more" expander, click it, wait,
and read again before you write anything down.

The tweet you want is the **first** `article[data-testid="tweet"]` on the page —
the one whose status id matches the permalink. The replies below it are not
your tweet and are not part of `full_text`. Useful structure, from this
project's own notes on x.com:

- tweet body: `[data-testid="tweetText"]` (the first one inside the article is
  the tweet's own words; a nested one inside `div[role="link"]` is the quoted
  tweet)
- author: `[data-testid="User-Name"]`
- timestamp: the `time` element's `datetime` attribute
- counts: the `aria-label` on `div[role="group"]` inside the article carries
  replies / reposts / likes / views as full numbers, not the rounded "12K" the
  buttons show. Prefer that aria-label. On the tweet's own page the view count
  is often also spelled out under the timestamp.

Close each tweet's tab when you are done with it, so tabs do not pile up. When
the whole batch is written, finish with a dedicated last round:

```bash
ego-browser nodejs <<'EOF'
await completeTaskSpace('THE TASK SPACE NAME ABOVE', { keep: false })
EOF
```

If a round fails with "user is controlling", an "inactive" task space, or any
similar message saying the browser is not yours: **stop**. Do not retry, do not
take the browser back. Say so in one line and end.

## What to write

One file per tweet, at `{{NOTES_DIR}}/<id>.md`, where `<id>` is that tweet's id
copied character for character from the block above. Exactly this shape, these
headings, in this order:

```
# <id>

- id: <id>
- url: <the permalink you were given>
- author: <the author handle, e.g. @someone>
- kind: <POST or REPOST, copied from the block above>
- posted_at: <the time element's datetime, ISO, from the tweet's own page>
- replies: <integer>
- reposts: <integer>
- likes: <integer>
- views: <integer>
- status: ok

## full_text

<the tweet's COMPLETE text, expanded, exactly as written — line breaks kept>

## quoted

<the quoted tweet's text, if the page shows a quoted tweet — otherwise: (none)>

## media

<one line describing any image or video, otherwise: (none)>
```

Field by field:

- **id, url, author, kind** — copied from the block you were given. The id and
  url are long and exact; a single wrong digit fails the run.
- **posted_at** — re-read from this page, not carried over.
- **replies, reposts, likes, views** — re-read from this page, as plain
  integers with no commas and no "K"/"M". If a count is genuinely absent on the
  page, write `0`.
- **full_text** — the tweet's own words, complete and expanded. Keep the
  author's line breaks. Do not translate it, do not tidy it, do not summarise
  it, do not shorten it, do not add or remove quotation marks, do not strip
  emoji. Do not include the author's name, the timestamp, the counts, the
  quoted tweet, or any reply.
- **quoted** — the words of the quoted tweet as the card shows them. If the
  card itself truncates them, write what is shown and add
  `(truncated on the card)` on the next line. `(none)` when there is no quote.
- **media** — one plain line: `image: chart of the ten-year yield since 2020`,
  `video: 45s clip of a press conference`, `2 images: two screenshots of a
  filing`. `(none)` when the tweet carries no image or video. A link card is
  not media; ignore it here.

### When a tweet will not load

If the tweet is deleted, the account is suspended or protected, the page shows
"This post is unavailable", or it simply will not load after two honest tries,
**write the note anyway** with what you know and nothing invented:

```
# <id>

- id: <id>
- url: <the permalink>
- author: <handle>
- kind: <POST or REPOST>
- posted_at:
- replies: 0
- reposts: 0
- likes: 0
- views: 0
- status: unavailable

## full_text

(unavailable: the page shows "This post is unavailable")

## quoted

(none)

## media

(none)
```

Say plainly in the `full_text` line what the page actually showed. Then move on
to the next link in the batch. One bad link never stops the batch, and it never
becomes an excuse to leave a file unwritten: **a note file must exist for every
id in your batch.** Code checks this and the run fails, naming the missing ids.

## Hard rules

1. **Never invent anything.** Not a word of text, not a number, not a date, not
   a quoted tweet, not a media description. If you did not see it on the page,
   it does not go in the note. When in doubt, write less and say the page did
   not show it.
2. **Never write the collapsed preview.** Expand it or say you could not.
3. **One tweet at a time**, in the order given.
4. **Only the permalinks above**, reading only, no clicks that change anything.
5. **One file per id, and no other file.** Do not edit `links.md`,
   `kept.json`, or anything else in the run folder. Do not create a summary
   file, an index, or a log.
6. **Do not judge.** No ranking, no grouping, no relevance, no opinion, no
   "this one is the best". Not in the note, not in your final line.

When the batch is done, say in one line how many notes you wrote and how many
of them are `status: unavailable`. That line is all you say.
