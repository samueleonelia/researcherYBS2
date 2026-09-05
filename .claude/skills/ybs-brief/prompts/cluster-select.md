# Group the day's news, and decide what gets read

You see the articles that survived triage today, as a headline and the site's
own one-line description. Two jobs, in order.

**First: which of these are the same story?** Six papers covering one event is
one piece of news, not six. Grouping them is what tells us how big the day's
stories actually are, and it is the only signal of importance available before
anything is read.

**Second: is it worth reading?** Reading is the expensive step. Every item gets
the same two questions, whether six papers ran it or one: is this what he is
arguing about, and did something actually happen?

You read no articles and you open nothing. Judge from what is in front of you.

## Inputs

- Date: `{{DATE}}` · slot: `{{SLOT}}`
- Articles that survived triage, one per line with its description underneath:

```
{{ARTICLES}}
```

{{PART_NOTE}}

## What he is arguing about now

Rebuilt from his latest shows on {{PROFILE_DATE}}. This is the first filter: a
story that lands on one of these is what the brief is for.

{{PROFILE}}

## What the show covers at all

{{BEATS}}

## What the brief is for

{{LENS}}

## Job one: group them into news items

A **news item** is one event or development. It holds every article reporting it,
from however many sources. Most items hold exactly one article, and that is
normal, not a failure.

- Same subject, different event = **different items**. Two Israel stories on one
  day are usually two stories.
- Different framing, same event = **one item**. "Settlers kill Palestinian teen"
  and "Settler attacks shift to Palestinian-ruled areas" were the same day's
  settler violence seen two ways; grouping them was right.
- A live blog covering several things belongs to the item it is mostly about.

Every article you were given goes into exactly one item. None may be left out.

## Job two: judge every item

**Being covered by several papers is not a pass.** It is a signal of importance,
and the sort order uses it, but a story six papers ran that is off the beats is
dropped like any other. Every item gets a `profile` and a `verdict`.

**`profile`** is the name of the storyline or theme above that the item is
about, copied exactly as it is written there, or `null` if it is about none of
them. Copy the name character for character: code matches it against the
profile and rejects a name that is not there.

**`verdict`** is one of three:

- `READ` — something happened. A ruling, a fine, a firing, a finding, a
  decision, a vote, a death toll, a resignation, a filing.
- `MAYBE` — on a beat or a topic, but nothing happened: a column, a feature, an
  analysis, or a headline too thin to tell.
- `DROP` — off the beats entirely, or an accident, a local crime or a lifestyle
  piece with no policy or rights question in it.

You do not decide how many get read. Code takes the items in priority order —
the ones on a topic before the ones only on a beat — and stops where the
settings say to stop. Your job is to label each item honestly, and to order the
list so the most consequential item comes first: where two items are otherwise
equal, that order is the tie-break.

## Which articles to read inside an item

**An item with two or more articles.** Name one **primary**: the account to read
in full. Prefer the wire or the straightest factual telling, unless another
source clearly carries the actual development. Then, for each of the others, ask
one question: *does its headline or description promise a fact, a development or
an angle that the primary's description does not already carry?* If yes, put it
in `read` too. If it is the same story told again, leave it out.

**An item with one article.** `read` holds that article for a `READ` or a
`MAYBE`, and is empty for a `DROP`.

## Output

One JSON object and nothing else.

```json
{
  "items": [
    {
      "item_id": "i01",
      "name": "Pentagon fires the Stars and Stripes editors",
      "kind": "cluster",
      "verdict": "READ",
      "profile": null,
      "articles": ["a012", "a047"],
      "primary": "a012",
      "read": ["a012", "a047"],
      "why": "a047 adds the crew-conditions reporting that triggered it"
    },
    {
      "item_id": "i02",
      "name": "Dutch regulator fines Uber $966m",
      "kind": "single",
      "verdict": "READ",
      "profile": "Capitalism versus the mixed economy",
      "articles": ["a033"],
      "primary": "a033",
      "read": ["a033"],
      "why": "a fine with a number, and the regulator names the algorithm"
    },
    {
      "item_id": "i03",
      "name": "Column: the guardrails AI needs",
      "kind": "single",
      "verdict": "MAYBE",
      "profile": "Technology and AI as human progress",
      "articles": ["a058"],
      "primary": "a058",
      "read": ["a058"],
      "why": "on the AI topic, but an opinion piece: nothing happened"
    }
  ],
  "near_misses": [
    "a012 and a091: both about the Pentagon, but a firing and a budget request are different events"
  ]
}
```

{{ITEM_SHAPE}}

## Hard rules

1. Never decide how many items get read, and never mark one as taken. Code does
   that from the settings, and it will not read past its ceiling however many
   you label `READ`.
2. Do not rank the items for the brief, do not tag them, and do not choose what
   leads. That decision comes later, when the stories have been read.
