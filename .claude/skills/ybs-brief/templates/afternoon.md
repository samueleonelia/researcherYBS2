# Afternoon update (16:00) — what changed since the morning

This file is the whole shape of the update. Where a rule is the morning's, it is
not restated here: `morning.md` says it, and this file points at it.

```
**Date:** <D Month YYYY at HH:MM>
**Updates:** the morning brief of {{BASE_TIME}}

## New since the morning

### <Headline sentence, ends with a period.>

<the story>

1. [<Article headline>](<url>) — <Source>

## What moved

### <Kind> - <Headline sentence.>
**Follows:** <the morning brief's heading for this story, verbatim>

<what changed since the morning · what that does to the morning's story · what is still not established>

1. [<Article headline>](<url>) — <Source>

{{X_SECTION}}
{{AUDIT_LINE}}
```

## Rules of the shape

- The two sections are fixed and in this order. New first, because it is what he
  does not know yet. A section with nothing qualifying is omitted.
- `NEW` picks go under New since the morning. `MOVED` picks go under What moved,
  **in the order the morning brief ran them**, which code fixes before the
  writer sees them; the heading's first word is the pick's kind (Development,
  Confirmation, Reversal, Correction), then ` - `, then the headline sentence.
- Under What moved, the line directly beneath a heading is `**Follows:**` and
  then the morning brief's own heading for the story being carried forward,
  copied letter for letter. It is what he scans that brief for, so a heading put
  another way is no pointer at all, and `write-stitch` refuses one. A story under
  New since the morning follows nothing and carries no such line.
- Together the two sections hold at most `{{settings.update_picks_max}}`
  stories. A story's heading, body and sources take the three-part form
  `morning.md` gives, and nothing here repeats it.
- When no section has anything, code writes the head and one sentence saying
  nothing has moved since the morning. That sentence is a constant in
  `ybs_run.py`, so it has one home and this file does not quote it.
- `{{X_SECTION}}` and `{{AUDIT_LINE}}` as in the morning: the X run is the same
  as the morning's, its own two-hour window, and `x-merge` puts its section
  where the placeholder sits.
