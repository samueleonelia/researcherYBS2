# Evening report (20:00) — human achievements

Everything about where a thing sits in the evening report is settled in this
file. A rule already set down by `morning.md` is pointed at by name and left
there, never copied across.

```
**Date:** <D Month YYYY at HH:MM>
**From:** {{POOL_LINE}}

## Human achievements

### <Label> - <Headline sentence, ends with a period.>

<the story>

1. [<Article headline>](<url>) — <Source>
2. [<Article headline>](<url>) — <Source>

{{X_SECTION}}
{{AUDIT_LINE}}
```

## Rules of the shape

- One section, always. Under it sit up to {{settings.achievements_max}}
  stories, the furthest along first, in the order the pick handed them over.
- Each heading starts with the story's label, capitalised, then ` - `, then the
  headline sentence. That label is the reader's honesty line: he sees how far a
  thing has got before he reads a line about it.
- Heading, then story, then numbered sources: the three-part form `morning.md`
  sets out, unchanged here.
- On a day whose pick chose nothing, code writes the head and a single sentence
  saying no human-achievement story turned up. That sentence lives in
  `ybs_run.py`, which is its one home, and is not quoted here.
- `{{X_SECTION}}` and `{{AUDIT_LINE}}` as in the morning: copy the two
  placeholders, write neither, and let code fill them.
- `{{POOL_LINE}}` belongs to code in the same way. It names the two runs this
  report was built from, each by its own clock time.
