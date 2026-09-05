# Morning brief (10:00) — agenda-setting

This file is the whole shape of the brief: nothing else says where a thing goes.
How the sentences are written lives in `prompts/write.md`, and nothing here
repeats that.

```
**Date:** <D Month YYYY at HH:MM>

## What leads

### 1. <Headline sentence, ends with a period.>

<the story>

1. [<Article headline>](<url>) — <Source>
2. [<Article headline>](<url>) — <Source>

#### COUNTERPOINT - <Headline sentence.>

<the counterpoint>

1. [<Article headline>](<url>) — <Source>

### 2. <Headline sentence.>

<the story>

1. [<Article headline>](<url>) — <Source>

<up to {{settings.lead_max}} leads, most consequential first>

## Secondary Topics

### <Topic invented from the day>

#### <Headline sentence.>

<the story>

1. [<Article headline>](<url>) — <Source>

## Worth Yaron's attention

### <Headline sentence.>

<the story>

1. [<Article headline>](<url>) — <Source>

<up to {{settings.worth_max}} items in this section>

{{AUDIT_LINE}}
```

## Rules of the shape

### Sections

- The three `##` sections are fixed and always in this order. A section with
  nothing qualifying is omitted: no placeholder, no "none".
- Every ceiling is a ceiling, never a floor. Two leads on a two-lead day is right.
- Leads are numbered, most consequential first, up to {{settings.lead_max}}.
  Worth Yaron's attention holds up to {{settings.worth_max}}.
- Topics under Secondary Topics are invented from the day. There is no fixed
  list: a topic exists only on a day that has stories for it.
- Every picked story appears exactly once, under the section its tag names:
  `LEAD` in What leads, `BODY` under a topic, `WORTH` in Worth Yaron's attention.
  Nothing is added and nothing is dropped; those decisions were made before you.

### Stories

- Every story is a heading, then the story, then its numbered sources. The same
  three parts at every level.
- Leads and Worth stories are `###`. Topics are `###` inside Secondary Topics,
  and their stories are `####`.
- The heading is one sentence and ends with a period.
- The sources are exactly the articles the pick lists, in that order: the one
  the note was written from first, then the rest of its item. Nothing added,
  nothing dropped, never an article from another story. Headline and URL exactly
  as given.

### Counterpoints

- `#### COUNTERPOINT - <headline sentence>`, inside the lead its `LEAD:` line
  names, after that lead's sources. Never a section of its own, never under any
  other story.
- Its one source is the article its file names.
- A lead with no counterpoint simply has none, and nothing marks the absence.

### Last line

- `{{AUDIT_LINE}}`, exactly as above. Code replaces it; never write an audit
  line yourself.
