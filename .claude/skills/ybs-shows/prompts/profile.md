# Write the topic profile

You are writing the file the morning brief reads every day to know what the show
is arguing about now.

## Inputs

The digests of the last {{SHOWS_FOR_PROFILE}} shows, newest first. Show ids:
{{SHOW_IDS}}

{{DIGESTS}}

## What to produce

**Write the file.** Use the Write tool to create `{{PROFILE_DRAFT}}`
holding exactly this shape and nothing else:

```json
{
  "storylines": [
    {"rank": 1, "name": "Iran war with no strategy, Hormuz still closed",
     "shows": 10, "note": "he keeps asking what winning would even mean"}
  ],
  "themes": [
    {"rank": 1, "name": "Trump administration",
     "angle": "judged on results, not on which side he is on"}
  ],
  "moves": {
    "main": "the right has become as statist as the left",
    "secondary": [
      "economic power is a trade you can walk away from; political power is the gun"
    ]
  }
}
```

- `storylines`: what is unfolding now, most-covered first. `shows` is how many
  of the digests mention it. `note` is one line on what he says about it.
- `themes`: the subjects he returns to across years, most-covered first.
  `angle` is one line on the position he takes.
- `moves.main`: the single argument he makes most often, in one line.
  `moves.secondary`: the other arguments he reaches for, one line each.

Rank each list from 1 with no gaps. Write no other fields: the script stamps the
date, the show ids and the stretch of shows itself.

This is a draft, not the live profile. The script checks it and only then puts
it where the morning brief reads it, so a draft that does not hold up costs
nothing: yesterday's profile stays in place and the brief keeps running.

Then reply with one line: `profile written, <n> storylines, <n> themes`.
