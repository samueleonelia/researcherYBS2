# Choose the evening's human achievements

Every article in front of you has been read to the end. What you are assembling
is the other half of the day: the things that got done, set beside the day's
troubles without being asked to cancel them out. Each story you keep is marked
for how far along it has got, and that mark is what stops an announcement from
reading like a cure.

## Inputs

- Date: `{{DATE}}` · slot: `{{SLOT}}`
- Tonight's notes. Each one opens with its id, its group, the topic it was read
  against and the link it came from, and each carries a `SCALE AND STAGE` line:

```
{{NOTES}}
```

## What he is arguing about now

Built on {{PROFILE_DATE}} out of the shows he recorded most recently.

{{PROFILE}}

## What he has asked for

Standing instructions in his own hand. Your judgement gives way to them, and
they give way to the hard rules at the foot of this page.

{{PREFERENCES}}

## What the brief is for

{{LENS}}

## The five kinds

{{ACHIEVEMENTS}}

## Ask each note two questions, in this order

**First: is it really one of the five?**

A headline promised one of them this morning, which is why the piece was read at
all. The note tells you whether the article paid that promise off. Where it did
not — the deed turns out on the page to be a memo, an intention, a hope — drop
the note as `not-achievement` and take it no further.

**Second: how far has it got?**

Give every story you keep exactly one label out of this table, and never two:

{{CRITERIA_LABELS}}

The rule printed under that table settles the hard cases. It is written once,
there, and not again here: read it and apply it as it stands. Two lines of the
note hold your answer. `SCALE AND STAGE` says how many, since when, and in what
state the thing is. `WEAK SPOTS` says what the article could not stand behind.
And one thing the table cannot tell you: where a note's `SCALE AND STAGE` comes
back "not stated", `Demonstrated` is out of reach, whatever else is claimed.

## How to choose

{{CRITERIA_FACTORS}}

## How many, and which ones

The report holds {{settings.achievements_max}} stories at the outside, and every
one you keep is tagged `ACHIEVEMENT`. Between two stories of otherwise equal
weight, take the one that has travelled further — `Demonstrated` ahead of
`Emerging`, `Emerging` ahead of `Speculative` — and then the one whose problem
is a problem he is arguing about now.

An empty list is a real answer. On a day when none of the five actually
happened, coming back with no picks at all is right, and filling the space with
a press release is the exact failure this report was built to prevent.

## Why you dropped it

Each note you do not keep needs a `reason_type` off this list and one line of
`reason` beneath it. A type that is not here is rejected by code:

- `evidence` — {{schema.reason_type.evidence}}.
- `duplicate` — {{schema.reason_type.duplicate}}.
- `no-development` — {{schema.reason_type.no-development}}.
- `relevance` — {{schema.reason_type.relevance}}.
- `not-achievement` — {{schema.reason_type.not-achievement}}.

## The checklist

Account for all {{NOTE_COUNT}} of the ids below, each of them either picked once
or dropped once. This is the list to work from; do not assemble your own:

```
{{NOTE_IDS}}
```

## Output

Reply with a single JSON object. Nothing around it: no fence, no preface, no
word to the reader afterwards.

```json
{
  "picks": [
    {"id": "a004", "tag": "ACHIEVEMENT", "label": "demonstrated", "why": "the clinic has treated 1,200 people since March and publishes its outcomes"},
    {"id": "a017", "tag": "ACHIEVEMENT", "label": "emerging", "why": "one city, one year of it running, and the waiting list is gone"},
    {"id": "a029", "tag": "ACHIEVEMENT", "label": "biographical", "why": "an engineer who kept the water on for a fortnight, and how he did it"}
  ],
  "dropped": [
    {"id": "a008", "reason_type": "not-achievement", "reason": "the headline said approved; the article says the file was submitted"},
    {"id": "a021", "reason_type": "duplicate", "reason": "the same trial as a004, from a paper with fewer of the numbers"},
    {"id": "a036", "reason_type": "evidence", "reason": "the yield figure comes from the firm alone and nobody has measured it"}
  ]
}
```

## Hard rules

{{PICK_RULES}}
