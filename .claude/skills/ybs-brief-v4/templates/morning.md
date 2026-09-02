# Morning brief (10:00) — agenda-setting

The skeleton only. A worked example, and what each section holds, is in
`BRIEF-STRUCTURE.md`, which reaches you in this prompt as its own block.

```
**Date:** <D Month YYYY at HH:MM>

## What leads

### 1. <Headline sentence, ends with a period.>

<the story>

1. [<Article headline>](<url>) — <Source>
2. [<Article headline>](<url>) — <Source>

#### COUNTERPOINT - <What improved, plainly stated.>

<what happened> <which principle makes this positive> <what it does not
establish>

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

## Mechanical rules

- The three `##` sections are fixed and always in this order. Leads and Worth
  stories are `###`; topics are `###` inside Secondary Topics, and their stories
  are `####`.
- A counterpoint is `#### COUNTERPOINT - <headline>`, inside the lead it bears
  on, after that lead's sources. Never a section of its own. A lead with no
  counterpoint simply has none.
- Links are real markdown links to URLs that appear in the notes. Never invent
  a URL, never link a story to an article that is not its own.
- **Never link Reuters.** List it as `<headline> — Reuters (no link)`.
- The final line must be exactly `{{AUDIT_LINE}}` and nothing else. Code
  replaces it. Never write an audit line yourself.
