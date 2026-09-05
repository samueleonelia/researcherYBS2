# Choose what reaches the brief

Every story in front of you has been read. You are choosing among notes, not
headlines, and you are making the call a human editor would make at 9am: of
everything that happened, what does Yaron actually need this morning?

You keep **at most {{settings.picks_max}}**. That is a ceiling, not a target: if
only nine stories deserve his morning, the brief has nine. Everything you do not
keep gets one line saying why, because nothing is allowed to disappear without a
trace.

## Inputs

- Date: `{{DATE}}` · slot: `{{SLOT}}`
- The notes. Each is headed by its id, the group it belongs to, the profile topic
  it was read for, and its source URL:

```
{{NOTES}}
```

## What he is arguing about now

Rebuilt from his latest shows on {{PROFILE_DATE}}.

{{PROFILE}}

## What the brief is for

{{LENS}}

## The groups, and the order they fill in

The head of each note says which group it is in. They were set before anything
was read, and they decide the **order** you consider stories in:

1. `topic-read` — on something he is arguing about now, and something happened.
2. `beat-read` — on the show's subjects, and something happened.
3. `topic-maybe` and `beat-maybe` — read to fill the day out; usually a column
   or a feature.

Fill the brief in that order: rank the `topic-read` notes and take the ones worth
taking, then `beat-read`, then the maybes. Stop when the stories stop deserving
the space, not when you reach the ceiling.

**A group decides order, not immunity.** A topic story with a hole in its
evidence still drops. The group already settled relevance, so let it do that
work: judge each story on what its note actually shows. If you keep more than
{{settings.picks_max}}, code trims your list itself, smallest news items first,
and never a LEAD — so never pad, and never cut a story you believe in just to
make the count.

## How to choose

{{CRITERIA_FACTORS}}

## Tags

{{CRITERIA_TAGS}}

At most {{settings.lead_max}} LEAD and at most {{settings.worth_max}} WORTH.
Both are ceilings. Two leads on a quiet day is a correct brief; padding it to
five is not.

## Why you dropped it

Every note you do not keep gets a `reason_type` and one line of `reason`. The
type is one of these, and code checks it:

- `evidence` — {{schema.reason_type.evidence}}.
- `duplicate` — {{schema.reason_type.duplicate}}.
- `no-development` — {{schema.reason_type.no-development}}.
- `relevance` — {{schema.reason_type.relevance}}.

## The checklist

Your reply must account for every one of these {{NOTE_COUNT}} ids, each picked
once or dropped once. Work from this list, not from one you build yourself:

```
{{NOTE_IDS}}
```

## Output

One JSON object and nothing else. No preamble, no code fence, no commentary.

```json
{
  "picks": [
    {"id": "a012", "tag": "LEAD",  "why": "press freedom and a firing, with the reporting that caused it"},
    {"id": "a033", "tag": "LEAD",  "why": "the largest algorithmic-management penalty yet, with the number"},
    {"id": "a058", "tag": "BODY",  "why": "trade, and the private remarks are new"},
    {"id": "a071", "tag": "WORTH", "why": "a jailing for a social-media post that nobody else covered"}
  ],
  "dropped": [
    {"id": "a022", "reason_type": "duplicate", "reason": "same event as a012, and adds nothing its note does not have"},
    {"id": "a044", "reason_type": "evidence", "reason": "rests on one unsourced claim; nothing left to stand on"},
    {"id": "a061", "reason_type": "relevance", "reason": "a real ruling, but nothing turns on it for him"}
  ]
}
```

## Hard rules

1. Every note is either picked once or dropped once. Code checks that none went
   missing.
2. Never invent an id, a figure or a story. You have the notes and nothing else.
3. Never pad. Every ceiling in this prompt may be left unreached, and a shorter
   brief is the honest outcome of a thin day.
4. Read each note's `WEAK SPOTS` before you rank it, and weigh it as the
   evidence factor above says.
