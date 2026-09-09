# Choose what the afternoon update carries

The morning brief went out hours ago and he has read it. Your job is the rest of
the day: of everything read since, what has actually moved, and what broke that
the morning never had at all. A story that has not moved does not belong in an
update, however big it was at ten.

You keep **at most {{settings.update_picks_max}}** stories, new and moved
together. That is a ceiling. On a quiet afternoon the right update is three
stories, or one, and code never asks you for a fuller one.

## Inputs

- Date: `{{DATE}}` · slot: `{{SLOT}}`
- The stories the morning brief ran, in the order it ran them, each with what
  its reader wrote at the time:

```
{{BASE_STORIES}}
```

- The stories the morning read and then chose not to run, with the reason:

```
{{BASE_DROPPED}}
```

- This afternoon's notes. Each is headed by its id, its group, the profile topic
  it was read for, its source URL, and, when it carries a morning story further,
  `follows m:<id>`:

```
{{NOTES}}
```

## What he is arguing about now

Rebuilt from his latest shows on {{PROFILE_DATE}}.

{{PROFILE}}

## What he has asked for

His standing instructions, written by him. Nothing here overrides the hard rules
at the bottom, and everything here overrides your own taste.

{{PREFERENCES}}

## What the brief is for

{{LENS}}

## Ask each note one question

**A note that follows a morning story: did it move?**

Keep it, tag it `MOVED`, and name which of four kinds of movement it carries:

- `development` — a new fact that changes what he would say about the story.
- `confirmation` — something the morning carried as contested or unsourced now
  has a second independent source behind it, or an official statement.
- `reversal` — the morning's fact is contradicted, by the actor himself or by
  the record.
- `correction` — the morning's figure or attribution was wrong, and this note
  says what the right one is.

When none of the four fits, the note is telling the morning's story again.
Drop it as `unchanged`.

**Two picks may not follow the same morning story.** Where two notes do, keep
the one carrying the movement and drop the other as `duplicate`. One morning
story gets one line in the update, or none.

**A note that follows nothing: is this the afternoon's new story?**

Keep it, tag it `NEW`, and give it no kind. A kind describes movement against
something he already read, and this is the first he hears of it.

A story the morning read and dropped is the one case to be slow about. That drop
was a decision somebody made with the whole article in front of them, and it
stands unless the note shows the story has grown past the reason it was dropped
for: the missing source turned up, the figure is on the record now, the thing
that had not happened has happened. A second headline about the same nothing
does not overturn it.

## How to choose

{{CRITERIA_FACTORS}}

## Why you dropped it

Every note you neither keep nor carry forward needs a `reason_type` from this
list, and one line of `reason` under it. Code checks the type:

- `evidence` — {{schema.reason_type.evidence}}.
- `duplicate` — {{schema.reason_type.duplicate}}.
- `no-development` — {{schema.reason_type.no-development}}.
- `relevance` — {{schema.reason_type.relevance}}.
- `unchanged` — {{schema.reason_type.unchanged}}.

## The checklist

These {{NOTE_COUNT}} ids are the whole afternoon. Account for every one of them,
and work from this list rather than one you assemble yourself:

```
{{NOTE_IDS}}
```

## Output

Reply with one JSON object. Nothing before it, nothing after it, no fence and no
explanation.

```json
{
  "picks": [
    {"id": "a007", "tag": "NEW", "why": "a general strike nobody was covering at ten, now on eleven front pages"},
    {"id": "a019", "tag": "MOVED", "kind": "development", "why": "the strait is closed to tankers, which the morning had only as a threat"},
    {"id": "a025", "tag": "MOVED", "kind": "reversal", "why": "the minister the morning quoted now denies the order was ever signed"},
    {"id": "a031", "tag": "MOVED", "kind": "correction", "why": "the death toll is 34, not 340: the morning's figure was a transcription error"}
  ],
  "dropped": [
    {"id": "a012", "reason_type": "unchanged", "reason": "the same account of the vote the morning already ran, with no new number"},
    {"id": "a020", "reason_type": "duplicate", "reason": "follows the same morning story as a019 and carries less of the movement"},
    {"id": "a044", "reason_type": "evidence", "reason": "one anonymous official, and nothing else stands behind the claim"},
    {"id": "a050", "reason_type": "relevance", "reason": "new since ten, and nothing turns on it for him"}
  ]
}
```

## Hard rules

{{PICK_RULES}}
