# Group this run's tweets into subjects

You see the tweets that survived the filter for one X-list run, as an id, an
author, the tweet's own words, the words of anything it quotes, and the title of
any link card it carries. One job: **say which of these tweets are about the
same subject.**

That is the whole job. You do not count anything, you do not rank anything, and
you do not decide whether a subject matters. Code counts, and a later agent
judges. Grouping is what makes counting possible at all: five list members
posting about one thing is one subject with five tweets, and only your grouping
can tell the code that.

You open nothing and read nothing outside this prompt. The text in front of you
is all the evidence there is.

## Inputs

- Run folder: `{{RUN_DIR}}`
- The tweets, one block each — id, author, then the text, the quoted text and
  the card title where there are any:

```
{{TWEETS}}
```

{{PART_NOTE}}

## What a subject is

A **subject** is one thing being talked about: one event, one announcement, one
claim, one argument. It holds every tweet that is about that thing, whoever
posted it and whatever they think of it.

- **Agreement is not the test.** Two people fighting over the same rate cut are
  on one subject. A supporter and a critic of the same bill are on one subject.
- **Same topic, different thing = different subjects.** Two tweets about the Fed
  on the same morning are usually two subjects: the cut itself and next month's
  jobs print are not one thing.
- **A quote tweet goes with the thing it is quoting**, not with whatever the
  quoter's other tweets are about. The quoted words are yours to use.
- **A repost is a tweet like any other.** Group it by what it says.
- **A link card title is evidence.** When the tweet's own words are thin, the
  card title often says what it is about.
- **Most subjects hold exactly one tweet.** That is normal and expected, not a
  failure. Do not stretch a subject to make it bigger.

## Near-duplicates

Two tweets carrying the same claim in near-identical words — a repost of the
same story, the same headline pasted twice, two people quoting the same line —
belong to **one subject**. Do not drop either one and do not merge them into a
single id: both ids go into that subject's `tweet_ids`.

## A tweet that fits nowhere

Put it in **its own subject**, alone. Never leave a tweet out, never invent a
"miscellaneous" or "other" bucket to sweep several unrelated tweets into, and
never drop a tweet because it looks unimportant. Importance is not your call.

## Naming a subject

A short, plain, specific noun phrase that says what the thing is — the way you
would name it out loud. "Fed pencils in two more cuts this year", not "Monetary
policy" and not "Tweets about the Fed". A name that could sit on top of ten
different days is too vague.

## Output

Write **one file** and nothing else:

`{{OUTPUT_PATH}}`

It holds one JSON object, in exactly this shape:

```json
{
  "subjects": [
    {
      "subject": "Fed pencils in two more cuts this year",
      "tweet_ids": ["1000000000000000001", "1000000000000000002"]
    },
    {
      "subject": "Argentina lifts its capital controls",
      "tweet_ids": ["1000000000000000007"]
    }
  ]
}
```

No other key, at the top level or inside a subject. No commentary in the file,
no markdown fence around it, no notes, no scores. Create no other file and edit
no existing one.

When you are done, say in one line how many subjects you made and confirm every
id was placed. That line is all you say.

## Hard rules

1. **Every id you were given appears in exactly one subject.** Not zero, not
   two. Before writing, check your list of ids against the input, both ways:
   nothing missing, nothing invented, nothing repeated. Code checks this and the
   run fails if it does not hold.
2. Copy every id **character for character** from the input. They are long
   numeric strings; a single wrong digit fails the run.
3. **Do not count anything.** No tweet counts, no author counts, no totals, no
   engagement numbers, no ordering by size. Code does the counting.
4. **Do not rank the subjects** and do not order them by importance. Any order
   is fine.
5. **Do not judge relevance.** A subject you find trivial, off-topic or wrong is
   grouped and written like every other. The judge decides later what reaches
   the brief.
6. Do not add, invent, split or rewrite the text of a tweet, and do not merge
   two ids into one.
