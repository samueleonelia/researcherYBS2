# Plan: the afternoon update

Written 2026-09-09. Goal: `/ybs-brief afternoon` produces one `brief.md` that
says **what changed since the morning brief**, and nothing else. Only real
developments, confirmations, reversals, corrections, and what the morning
missed. It ends with the stories still open and what would settle each one.
A story the morning ran that has not moved is never repeated.

Success, as Samuele set it:

1. Nothing repeated that has not moved.
2. Every update is labelled for what it is: a development, a confirmation, a
   reversal, a correction, or a story the morning missed.
3. It ends with the unresolved stories and what would settle them.
4. Same rules as the morning: figures checked against the page, every ceiling a
   ceiling, nothing invented, nothing written by hand.

## 1. The one design decision

**The afternoon is the same pipeline with a different slot, and the slot
decides in code.** The orchestrator follows the same `SKILL.md` steps in the
same order. Three things differ, and all three are settled by `ybs_run.py` when
it sees `slot: afternoon` in `run.json`:

- what the screen keeps (only what the morning did not see),
- what the cluster and the pick are asked (compare to the morning),
- what the template says the brief looks like (three new sections).

Why not a second skill: every hard rule, the pool, the retries, the figure
check, the screen gate and the stitch are already right, and a copy of the
skill would be a second place for each of them to rot. Why not branching prose
in `SKILL.md`: an orchestrator that has to remember which branch it is on makes
mistakes; one that runs the same commands and lets them answer differently does
not. `SKILL.md` gains two sentences, both at step 1.

## 2. What "since the morning" means

**The base run.** The latest run of today's local date with `slot: morning` and
`status: completed`. `start --slot afternoon` finds it, or takes one with
`--base <run_dir>`, and refuses to start without one: an afternoon update with
nothing to update is not a brief. `run.json` records it under `base`:
`run_id`, `run_dir`, `window_end_utc`, and the morning's time from its
template title (`10:00`).

**The window.** Local midnight to now, the same as the morning, **minus every
URL the morning already screened.** Not "from the morning's end": a story the
front page was not showing at 10:00 but was published at 08:00 is exactly
"anything the morning missed", and a from-the-end window would hide it.
`screen-sync` reads the base run's `articles.json` and drops any link whose
canonical URL is in it, counting them as `seen_this_morning`. Everything that
survives is new to the pipeline, and it goes through triage, cluster, read,
pick and check exactly as the morning's articles did.

**What is not caught, on purpose.** A live blog or an article the morning read
that was rewritten in place after 10:00 has the same URL, so it is dropped as
seen. The development it carries almost always also appears as a fresh dated
article on the front page, and that one is caught. Re-reading pages is a
second version, if a live run shows it is needed.

## 3. The steps, and what changes in each

| Step | Morning | Afternoon |
|---|---|---|
| 0 preflight | same | same |
| 1 start | `start --slot morning`, then `x-start` | `start --slot afternoon` finds the base; `x-start` answers `skipped` (reason: the afternoon has no X section) |
| 2 screen | six screeners | same six; `screen-sync` also drops what the base saw |
| 3 triage | same | same |
| 4-5 cluster | one call, `cluster-select.md` | same file; a `{{SLOT_JOB}}` block names the morning's stories, and an item may `follows` one |
| 6 read | pool | same; followed items are read first |
| 7 pick | `pick.md` | `pick-update.md`, chosen by `fill pick` from the slot; `picks-sync` checks the afternoon tags and ceilings |
| 8 check | same | same |
| 9 counterpoints | one per LEAD | nothing: there is no LEAD tag, and `picks-sync` lists no leads |
| 10 write | three writers, `morning.md` | three writers, `afternoon.md`; `x-wait` and `x-merge` see `skipped` and do nothing; the audit line is the afternoon's |

## 4. Changes, file by file

### 4.1 `settings.md`

Two rows under `## Numbers`, both ceilings:

| Setting | Value | What it means |
|---|---|---|
| update_picks_max | 10 | stories that may reach the afternoon update |
| watch_max | 5 | stories the afternoon update may list as still open |

The `## Models` table does not change: the afternoon's cluster, pick and write
run at the `cluster`, `pick` and `write` rows. The `write` row's last column
gains "or of the update (what moved, what the morning missed, still open)".

### 4.2 `templates/afternoon.md`

The whole shape of the update, the way `morning.md` is the whole shape of the
brief. Title line `# Afternoon update (16:00) — what changed since the morning`,
so `template_head` reads `16:00` out of it as it reads `10:00` today.

```
**Date:** <D Month YYYY at HH:MM>
**Updates:** the morning brief of {{BASE_TIME}}

## What moved

### <Kind> - <Headline sentence, ends with a period.>

<what changed since the morning · what that does to the morning's story · what is still not established>

1. [<Article headline>](<url>) — <Source>

<up to {{settings.update_picks_max}} stories across this section and the next; Kind is Development, Confirmation, Reversal or Correction>

## What the morning missed

### <Headline sentence.>

<the story>

1. [<Article headline>](<url>) — <Source>

## Still open

1. **<the story, in a few words>.** <what is unresolved>. Settled by: <what would settle it>.

<up to {{settings.watch_max}} entries, no sources>

{{X_SECTION}}
{{AUDIT_LINE}}
```

Rules of the shape, in the template's own words: the three sections are fixed
and in this order; a section with nothing qualifying is omitted; every picked
story appears exactly once, `MOVED` under What moved with its `kind` as the
heading's first word, `MISSED` under What the morning missed; a story's
sources are exactly the articles the pick lists, as in the morning; Still open
is a numbered list, one line per entry, and carries no source list, because
each entry names a story the reader already has. `{{X_SECTION}}` stays in the
template so `x-merge` finds its placeholder and removes it, the way it does
today when X is skipped.

`{{BASE_TIME}}` is filled by code in both places the head is rendered: `fill
write` (through the namespace) and `write-stitch` (through `template_head`).
`morning.md` does not use it, and `fill` keeps refusing a template that asks
for a name nothing provides.

### 4.3 `prompts/cluster-select.md` and `_item-shape.md`

`cluster-select.md` gains one placeholder, `{{SLOT_JOB}}`, between the inputs
and "What he is arguing about now". For a morning run it renders empty. For an
afternoon run it renders a block, built by code, that says:

- the morning brief already ran these stories, one line each: `<base id> ·
  <tag> · <headline> · what's new this morning: <WHAT'S NEW>`, for every pick
  of the base run, from its notes;
- the morning read and dropped these, one line each: `<base id> · <headline>
  · <reason_type>: <reason>`;
- the rule: an article about one of those stories goes in an item with
  `follows: "<base id>"`. Such an item is `READ` only when a headline or
  description promises something the morning line does not already carry: a
  figure, a decision, a denial, a correction, a reversal, a death toll. The
  same event told again is `DROP` with `why: "no-move"`. An item that follows
  nothing is judged as the morning judges it.

`_item-shape.md` gains the field: `follows` is a base pick id or `null`; it is
`null` in every morning run, and code rejects anything else there. The JSON
example in `cluster-select.md` shows `"follows": null` on every item, and one
afternoon example line shows a follower. `cluster-merge.md` carries `follows`
through unchanged, and its `{{SLOT_JOB}}` is the same block.

### 4.4 `prompts/pick-update.md`

A new prompt, the afternoon's step 7. Same fragments as `pick.md` (lens,
preferences, criteria factors), same output discipline, a different job:

- Inputs: date and slot; **the morning's stories** (the `{{BASE_STORIES}}`
  block: for each base pick, id, tag, headline, URL, `WHAT HAPPENED`, `WHAT'S
  NEW`, `WEAK SPOTS`, `WHAT'S NOT HERE`, from the base run's notes); the
  morning's dropped list (`{{BASE_DROPPED}}`); the afternoon's notes
  (`{{NOTES}}`, the existing block, whose head line gains `follows <base id>`
  when the item follows one).
- The question for a note that follows a morning story: **did it move?** Keep
  it as `MOVED` with a `kind`: `development` (a new fact that changes what he
  would say), `confirmation` (a claim the morning carried as contested or
  unsourced now has a second, independent source or an official statement),
  `reversal` (the morning's fact is now contradicted by the actor or the
  record), `correction` (the morning's figure or attribution was wrong, and
  the note says what the right one is). A note that retells the morning is
  dropped with `reason_type: "unchanged"`.
- The question for a note that follows nothing: is it a story the morning
  should have had? Keep it as `MISSED`; a story that is real but not worth
  his afternoon drops with `relevance`, as in the morning. A story the
  morning **read and dropped** is `MISSED` only if the note shows it has moved
  past the reason it was dropped for; the dropped list is there so a
  deliberate morning decision is not undone by a second headline.
- **Still open**: up to `{{settings.watch_max}}` entries, each `{"story":
  "<a base pick id or an afternoon note id>", "open": "<one line>",
  "settles": "<one line>"}`. `open` comes from what the notes leave
  unresolved (`WEAK SPOTS`, `WHAT'S NOT HERE`, a contested claim); `settles`
  names the fact, statement, ruling or figure that would close it. A story
  that moved may still be open. An entry is never a repeat of a story: it
  names it in a few words and says what is missing.
- Ceilings: at most `{{settings.update_picks_max}}` picks across both tags,
  `watch_max` entries. Every note picked once or dropped once, as today.
- Output: one JSON object: `picks` (`id`, `tag`, `kind` for MOVED, `why`),
  `dropped` (with the fifth reason type), `watch`.

`SCHEMA["reason_type"]` gains `unchanged`: "the morning brief already carries
this, and the note adds nothing that moves it". `SCHEMA["tag"]` becomes
per-slot: `morning: LEAD | BODY | WORTH`, `afternoon: MOVED | MISSED`, plus
`kind: development | confirmation | reversal | correction`.

### 4.5 `prompts/write.md`

Shared, unchanged in its rules. `{{SECTION_JOB}}` is where the afternoon's
writers learn their job, and `section_job()` in code becomes slot-aware:

- `moved`: "You write `## What moved`. For each story the picks give you the
  morning's line and the afternoon's note. The heading's first word is the
  pick's kind, capitalised, then ` - `, then the headline sentence. Write in
  this order: what changed since the morning, in one sentence; what that does
  to the morning's story; what is still not established. Never retell the
  morning's story: one clause saying what the morning had is the most it
  gets."
- `missed`: "You write `## What the morning missed`", the morning's story
  rules unchanged.
- `watch`: "You write `## Still open`. Your input is the watch list, not
  picks: each entry names a story, what is unresolved and what would settle
  it, with the note it came from. One numbered line per entry: the story in
  a few words in bold, the open question, then `Settled by:` and the fact
  that would settle it. No sources, no new facts, nothing the notes do not
  say."

`{{PICKS}}` for the `watch` writer is the watch block (each entry with the
note it cites); for `moved` it is the picks block with, above each afternoon
note, the base story's line (`THE MORNING HAD:` headline, `WHAT HAPPENED`,
`WHAT'S NEW`). `{{COUNTERPOINTS}}` says "None: the afternoon update carries no
counterpoints."

### 4.6 `ybs_run.py`

**`start`**: `--slot` accepts `afternoon`; `--base <run_dir>` optional. For
`afternoon`, find the base (today, morning, completed, latest) or die naming
what it looked for. Record `base` in `run.json` and print it.

**`screen-sync`**: with a base, load its `articles.json`, drop links by
canonical URL, count `seen_this_morning` per source and in total, and print
it. The window rule is otherwise unchanged.

**`fill`**: `SLOT_JOB` in the namespace for `cluster-select` and
`cluster-merge` (empty for morning, the block of 4.3 for afternoon);
`fill pick` renders `pick-update.md` for an afternoon run and still writes
`prompts/pick.md`, so step 7's launch line does not change; `BASE_STORIES`,
`BASE_DROPPED`, `BASE_TIME` for afternoon prompts; `fill write --section`
takes the slot's sections; `fill counterpoint` keeps refusing a non-LEAD
pick, which in the afternoon is every pick.

**Sections and tags per slot.** `WRITE_SECTIONS` and `TAG_OF_SECTION` become
one table keyed by slot: `morning: leads→LEAD, body→BODY, worth→WORTH`;
`afternoon: moved→MOVED, missed→MISSED, watch→(the watch list)`.
`template_headings`, `section_job`, `write-stitch` and the `--section` choices
read the run's slot. `schema` prints both lists under `write.sections`.

**`items-sync`**: `follows` must be `null` in a morning run and, in an
afternoon run, `null` or a base pick id (the base run's `picks.json`); the
`_group` of a follower is `follow-read` or `follow-maybe`. `GROUP_ORDER` gains
those two at the front of their kind: `follow-read, topic-read, beat-read,
follow-maybe, topic-maybe, beat-maybe`. The read list carries `follows` on each
entry, and `notes_block` prints it in the head line.

**`picks-sync`**: tags from the slot. For an afternoon run: `MOVED` needs a
`kind` from the four; a `MOVED` pick's item must `follows` a base id and a
`MISSED` pick's item must not; `watch` is at most `watch_max` entries, each
with a `story` that is a base pick id or an afternoon note id and non-empty
`open` and `settles`; over `update_picks_max` is trimmed fewest articles
first, `MISSED` before `MOVED`. `picks_mix` gains `follow`. Counts recorded:
`moved` by kind, `missed`, `watch`. `leads` in the output is empty, so step 9
has nothing to launch.

**`write-stitch`**: sections from the slot; the `watch` section is required
when `watch` is non-empty and is skipped when it is empty; the URL check runs
for `moved` and `missed` and not for `watch`; every `###` under What moved must
start with one of the four kinds. `template_head` fills `{{BASE_TIME}}`.

**`x-start`**: for an afternoon run, `skip("the afternoon has no X section")`
before any other check. `x-wait` and `x-merge` already handle `skipped`.
`x_audit_bit` returns nothing when the skip reason is the slot, so the audit
line does not report X for a run that never had it.

**`build_audit_line`** for an afternoon run: `Audit (afternoon, updates
<base run_id>): 6 of 6 sources screened · N articles new since the morning
(M already seen) · undated … · kept … · items (F following a morning story) ·
read · notes with a figure removed · K moved (a developments, b confirmations,
c reversals, d corrections) · L missed · W still open · profile of … ·
retries · failures.`

### 4.7 `SKILL.md`

- Front matter: `argument-hint: "morning | afternoon"`; the description gains
  one sentence: "`afternoon` writes what changed since that day's morning
  brief."
- Step 1: `start --slot <slot>`; "For `afternoon` it names the morning run it
  updates, or refuses when today has no completed morning run: then stop and
  say so." The `x-start` paragraph gains: "`skipped` is also the afternoon's
  answer: the update has no X section."
- Step 7: "`picks-sync` checks the slot's tags and ceilings" instead of naming
  LEAD and WORTH.
- Step 10: the sections are "the ones `schema write.sections` names for the
  run's slot". Nothing else changes.

### 4.8 Tests

`tests/test-bookkeeping-v4.py`:

- `start --slot afternoon` refuses without a completed morning run today;
  takes `--base`; records `base`.
- `screen-sync` drops what the base saw and counts it.
- `items-sync`: `follows` rejected in a morning run; a `follows` naming a
  non-pick rejected; followers grouped `follow-read` first in the read list.
- `picks-sync` afternoon: tags, `kind`, `follows` consistency, `watch`
  shape and ceiling, `unchanged` reason, trim order, `leads` empty.
- `fill pick` writes `prompts/pick.md` from `pick-update.md` in an afternoon
  run; `fill counterpoint` refuses a `MOVED` pick.
- `write-stitch` afternoon: three sections, `watch` optional, kind prefix
  checked, `{{BASE_TIME}}` filled.
- `x-start` afternoon: `skipped`, and the audit line carries no X bit.
- `audit-line` afternoon shape.

`tests/test-prompts-v4.py`: the afternoon prompts render with no unfilled
placeholder from a fixture base run; `cluster-select` for a morning run
renders `{{SLOT_JOB}}` empty; the afternoon template's headings match the
slot's sections.

### 4.9 `DEVLOG.md`, `STATUS.md`, `README.md`

The usual entries. README's one line on `/ybs-brief` gains the slot.

## 5. What is deliberately not in this version

- **No X section in the afternoon.** The X pipeline's window is "the last two
  hours", not "since the morning", and it has no notion of a base run; an
  afternoon X section would be a second morning section, not an update.
- **No re-read of pages the morning read.** See section 2.
- **No good-news report.** That is the second piece, and it is its own plan.
- **No afternoon-specific models.** If a replay shows the update's pick needs
  `high`, that is a `## Models` row, not a code change.

## 6. Order of work, and the tests between

1. `settings.md`, `SCHEMA`, per-slot tables, `start`, `screen-sync`;
   bookkeeping tests for those. Commit.
2. `templates/afternoon.md`, `{{SLOT_JOB}}`, `_item-shape.md`, `items-sync`,
   `read-list`, `notes_block`; tests. Commit.
3. `pick-update.md`, `picks-sync`, `fill pick`; tests. Commit.
4. `section_job`, `picks_block` for `moved` and `watch`, `write-stitch`,
   `template_head`, `x-start` skip, audit line; tests. Commit.
5. `SKILL.md`, README, DEVLOG, STATUS. Commit.
6. One live `/ybs-brief afternoon` against today's morning run, timed from
   `run.json`. Expected: about 20 to 25 minutes, since most of the day's
   articles are already seen and dropped at `screen-sync`.
