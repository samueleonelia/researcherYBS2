# Plan: the afternoon update

Written 2026-09-09, revised the same day after Samuele's five-step description
and one verifier round. Goal: `/ybs-brief afternoon` produces one `brief.md`
that says **what changed since the morning brief**, and nothing else.

Samuele's own shape of it, in order:

1. Screen as usual.
2. Triage as usual.
3. Cluster **around the stories the morning brief ran**. Anything else becomes
   an item only when it is a big cluster: the morning was quiet, a war broke
   out at noon, and the afternoon front pages carry a pile of articles on it.
4. Read as usual.
5. The brief: **first what is totally new** (there may be nothing), **then the
   updates, in the morning brief's order**, and a morning story is written up
   only when there is an actual development or new data. Nothing new, nothing
   written. Signal over noise.

Plus, from the first description: every update is labelled as a development,
a confirmation, a reversal or a correction; and the morning's rules hold:
figures checked against the page, every ceiling a ceiling, nothing invented,
nothing written by hand. There is no "still open" list: what is relevant is
only what moved (Samuele, 2026-09-09).

## 1. The one design decision

**The afternoon is the same pipeline with a different slot, and the slot
decides in code.** The orchestrator follows the same `SKILL.md` steps in the
same order. Three things differ, and all three are settled by `ybs_run.py` when
it sees `slot: afternoon` in `run.json`:

- what the screen keeps (only what the morning did not see),
- what the cluster and the pick are asked (compare to the morning),
- what the template says the update looks like.

Why not a second skill: every hard rule, the pool, the retries, the figure
check, the screen gate and the stitch are already right, and a copy of the
skill would be a second place for each of them to rot. Why not branching prose
in `SKILL.md`: an orchestrator that has to remember which branch it is on makes
mistakes; one that runs the same commands and lets them answer differently does
not. `SKILL.md` gains three sentences.

## 2. What "since the morning" means

**The base run.** The latest run of today's local date with `slot: morning` and
`status: completed`. `start --slot afternoon` finds it, or takes one with
`--base <run_dir>`, and refuses to start without one: an afternoon update with
nothing to update is not a brief. `run.json` records it under `base`:
`run_id`, `run_dir`, `window_end_utc`, and the morning's time from its
template title (`10:00`).

**Base ids.** The morning and the afternoon both number their articles
`a001…`, so a bare id is ambiguous. Everywhere the afternoon refers to a
morning article, in a prompt, in `follows`, in a count, it is
written **`m:<id>`** (`m:a032`). Code strips the prefix to reach the base run's
files and refuses a bare id where a base id is expected.

**The window.** Local midnight to now, the same as the morning, **minus every
URL the morning already screened.** Not "from the morning's end": a story the
front page was not showing at 10:00 but was published at 08:00 is exactly what
the morning missed, and a from-the-end window would hide it. `screen-sync`
reads the base run's `articles.json` and drops any link whose canonical URL is
in it, counting them as `seen_this_morning`. Everything that survives is new to
the pipeline, and it goes through triage, cluster, read, pick and check exactly
as the morning's articles did.

**What is not caught, on purpose.** A live blog or an article the morning read
that was rewritten in place after 10:00 has the same URL, so it is dropped as
seen. The development it carries almost always also appears as a fresh dated
article on the front page, and that one is caught. Re-reading pages is a
second version, if a live run shows it is needed.

## 3. The steps, and what changes in each

| Step | Morning | Afternoon |
|---|---|---|
| 0 preflight | same | same |
| 1 start | `start --slot morning`, then `x-start` | `start --slot afternoon` finds the base; `x-start` answers `skipped` (the afternoon has no X section) |
| 2 screen | six screeners | same six; `screen-sync` also drops what the base saw |
| 3 triage | same | same |
| 4-5 cluster | one call, `cluster-select.md` | same file; a `{{SLOT_JOB}}` block names the morning's stories, an item may `follows` one, and a new item is read only when it is big |
| 6 read | pool | same; followers are read first |
| 7 pick | `pick.md` | `pick-update.md`, chosen by `fill pick` from the slot; `picks-sync` checks the afternoon tags and ceilings |
| 8 check | same | same |
| 9 counterpoints | one per LEAD | nothing: there is no LEAD tag, and `picks-sync` lists no leads |
| 10 write | three writers, `morning.md` | two writers, `afternoon.md`; `x-wait` and `x-merge` see `skipped` and do nothing; the audit line is the afternoon's |

## 4. Changes, file by file

### 4.1 `settings.md`

Two rows under `## Numbers`:

| Setting | Value | What it means |
|---|---|---|
| update_picks_max | 15 | stories that may reach the afternoon update, new and moved together |
| new_item_articles_min | 10 | articles an afternoon item that follows no morning story must hold before it is read; the one floor in this table, and the note under it says so |

The note: "`new_item_articles_min` is a floor, not a ceiling: it is the size
at which a story the morning did not have counts as big enough to be new. A
war that breaks at noon clears it; one column does not."

The `## Models` table does not change: the afternoon's cluster, pick and write
run at the `cluster`, `pick` and `write` rows. The `write` row's last column
gains "or of the update".

### 4.2 `templates/afternoon.md`

The whole shape of the update, the way `morning.md` is the whole shape of the
brief. Title line `# Afternoon update (16:00) — what changed since the morning`,
so `template_head` reads `16:00` out of it as it reads `10:00` today.

```
**Date:** <D Month YYYY at HH:MM>
**Updates:** the morning brief of {{BASE_TIME}}

## New since the morning

### <Headline sentence, ends with a period.>

<the story>

1. [<Article headline>](<url>) — <Source>

## What moved

### <Kind> - <Headline sentence.>

<what changed since the morning · what that does to the morning's story · what is still not established>

1. [<Article headline>](<url>) — <Source>

{{X_SECTION}}
{{AUDIT_LINE}}
```

Rules of the shape, in the template's own words, none of them copied from
`morning.md` (the prompt tests refuse a twelve-word run shared by two files;
where a rule is the morning's, the template says "as `morning.md` says" and
does not restate it):

- The two sections are fixed and in this order. New first, because it is
  what he does not know yet. A section with nothing qualifying is omitted.
- `NEW` picks go under New since the morning. `MOVED` picks go under What
  moved, **in the order the morning brief ran them**, which code fixes before
  the writer sees them; the heading's first word is the pick's kind
  (Development, Confirmation, Reversal, Correction), then ` - `, then the
  headline sentence.
- Together the two sections hold at most `{{settings.update_picks_max}}`
  stories. A story's heading, body and sources take the three-part form
  `morning.md` gives, and nothing here repeats it.
- When no section has anything, code writes the head and one sentence
  saying nothing has moved since the morning. The sentence is a constant in
  `ybs_run.py` (`EMPTY_UPDATE_LINE`); the template does not quote it, so it
  has one home.
- `{{X_SECTION}}` and `{{AUDIT_LINE}}` as in the morning: code removes the
  first (the afternoon has no X section) and fills the second.

`{{BASE_TIME}}` is filled by code in both places the head is rendered: `fill
write` (through the namespace) and `write-stitch` (through `template_head`,
which gets the run and renders the head with the same namespace). `morning.md`
does not use it, and `fill` keeps refusing a template that asks for a name
nothing provides.

### 4.3 `prompts/cluster-select.md`, `cluster-merge.md`, `_item-shape.md`

`cluster-select.md` gains one placeholder, `{{SLOT_JOB}}`, between the inputs
and "What he is arguing about now". For a morning run it renders empty. For an
afternoon run it renders a block, built by code, that holds:

- the morning brief's stories, one line each, in the morning's order: `m:<id>
  · <tag> · <headline> · new this morning: <WHAT'S NEW>`, for every pick of
  the base run, from its notes;
- the stories the morning read and dropped, one line each: `m:<id> ·
  <headline> · <reason_type>: <reason>`;
- the rule: an article about one of those stories goes in an item with
  `follows: "m:<id>"`. Such an item is `READ` only when a headline or
  description promises something the morning line does not already carry: a
  figure, a decision, a denial, a correction, a reversal, a death toll. The
  same event told again is `DROP` with `why: "no-move"`;
- the rule for everything else: an item that follows nothing is read only
  when it is big, at least `new_item_articles_min` articles; smaller ones are
  labelled honestly (`READ`, `MAYBE`, `DROP` as the morning would) and code
  leaves them unread. Group them as carefully as the followers, because the
  size of the cluster is the whole test;
- one worked example of a follower item, inside this block. It is not in the
  file's ```json example, which the prompt tests run through `items-sync` on
  a morning run, where a non-null `follows` is rejected.

`_item-shape.md` gains the field: `follows` is `null` or a base id in the
`m:<id>` form; it is `null` in every morning run, and code rejects anything
else there. The file's ```json example shows `"follows": null` on every item.
`cluster-merge.md` carries `follows` through unchanged and takes the same
`{{SLOT_JOB}}` block.

### 4.4 `prompts/pick-update.md`

A new prompt, the afternoon's step 7. It pulls the same fragments as `pick.md`
(lens, preferences, criteria factors) and, for the sentences the two prompts
would otherwise share (every note picked once or dropped once; never invent;
never pad; read `WEAK SPOTS` first; the drop reasons), a new fragment
`_pick-rules.md` that both files pull in as `{{PICK_RULES}}`. `pick.md` loses
those sentences to the fragment and keeps only its own. The prompt's job:

- Inputs: date and slot; **the morning's stories** (`{{BASE_STORIES}}`: for
  each base pick, in the morning's order, `m:<id>`, tag, headline, URL, `WHAT
  HAPPENED`, `WHAT'S NEW`, `WEAK SPOTS`, `WHAT'S NOT HERE`, from the base
  run's notes); the morning's dropped list (`{{BASE_DROPPED}}`); the
  afternoon's notes (`{{NOTES}}`, the existing block, whose head line gains
  `follows m:<id>` when the item follows a morning story).
- For a note that follows a morning story: **did it move?** Keep it as
  `MOVED` with a `kind`: `development` (a new fact that changes what he would
  say), `confirmation` (a claim the morning carried as contested or unsourced
  now has a second independent source or an official statement), `reversal`
  (the morning's fact is now contradicted by the actor or the record),
  `correction` (the morning's figure or attribution was wrong, and the note
  says what the right one is). A note that retells the morning is dropped
  with `reason_type: "unchanged"`.
- For a note that follows nothing: is this the big new story of the
  afternoon? Keep it as `NEW`. A story the morning **read and dropped** is
  `NEW` only if the note shows it has moved past the reason it was dropped
  for; the dropped list is there so a deliberate morning decision is not
  undone by a second headline.
- Ceilings: at most `{{settings.update_picks_max}}` picks across both tags.
  Every note picked once or dropped once, as today.
- Output: one JSON object: `picks` (`id`, `tag`, `kind` for MOVED, `why`),
  `dropped` (with the fifth reason type).

`SCHEMA["reason_type"]` gains `unchanged`: "the morning brief already carries
this, and the note adds nothing that moves it". `SCHEMA["tag"]` becomes
per-slot: `morning: LEAD | BODY | WORTH`, `afternoon: NEW | MOVED`, plus
`kind: development | confirmation | reversal | correction`.

### 4.5 `prompts/write.md`

Shared, unchanged in its rules. `{{SECTION_JOB}}` is where the afternoon's
writers learn their job, and `section_job()` in code becomes slot-aware:

- `new`: "You write `## New since the morning`", the morning's story rules
  unchanged.
- `moved`: "You write `## What moved`. The picks come in the morning's order;
  keep it. For each story you have the morning's line and the afternoon's
  note. The heading's first word is the pick's kind, capitalised, then ` - `,
  then the headline sentence. Write in this order: what changed since the
  morning, in one sentence; what that does to the morning's story; what is
  still not established. Never retell the morning's story: one clause saying
  what the morning had is the most it gets."

`{{PICKS}}` for the `moved` writer is the picks block in base order with, above each afternoon note, the morning's line (`THE
MORNING HAD:` headline, `WHAT HAPPENED`, `WHAT'S NEW`). `{{COUNTERPOINTS}}`
says "None: the afternoon update carries no counterpoints."

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
`BASE_DROPPED`, `BASE_TIME` for afternoon prompts; `PICK_RULES` from the new
fragment for both slots; `fill counterpoint` keeps refusing a non-LEAD pick,
which in the afternoon is every pick.

**Sections and tags per slot.** `WRITE_SECTIONS` and `TAG_OF_SECTION` become
one table keyed by slot: `morning: leads→LEAD, body→BODY, worth→WORTH`;
`afternoon: new→NEW, moved→MOVED`. The argparse
`--section` choices are the union of both slots' names, evaluated before the
run is known; `cmd_fill` rejects a section that is not in the run's slot.
`template_headings`, `section_job` and `write-stitch` read the run's slot.
`schema` prints both lists under `write.sections`.

**`items-sync`**: `follows` must be `null` in a morning run and, in an
afternoon run, `null` or `m:<id>` where `<id>` is a pick of the base run's
`picks.json`; a follower's `_group` is `follow-read` or `follow-maybe`.
`GROUP_ORDER` gains those two at the front of their kind: `follow-read,
topic-read, beat-read, follow-maybe, topic-maybe, beat-maybe`. In an afternoon
run an item with `follows: null` and fewer than `new_item_articles_min`
articles is never taken for reading, whatever its verdict; the output counts
them as `small_new_items`. The read list carries `follows` on each entry, and
`notes_block` prints it in the head line.

**`picks-sync`**: tags from the slot. For an afternoon run: `MOVED` needs a
`kind` from the four; a `MOVED` pick's item must `follows` a base id and a
`NEW` pick's item must not; over `update_picks_max` is trimmed fewest
articles first, `NEW` before `MOVED`; `picks` may be empty, and that is not a
failure. `picks_mix` gains `follow`. Counts recorded: `new`, `moved` by kind.
`leads` in the output is empty, so step 9 has nothing to launch.
The morning's `picks.json` is never written.

**`picks_block`** for `moved` orders the picks by the base run's pick order,
so the writer and the stitch agree on it.

**`write-stitch`**: sections from the slot; every `###` under What moved
must start with one of the four kinds, and the `moved` URLs must appear in
base order; with no picks at all the brief is the head plus
`EMPTY_UPDATE_LINE`, and the stitch says so in its output instead of dying.
`template_head` takes the run and fills `{{BASE_TIME}}`.

**`x-start`**: for an afternoon run, `skip("the afternoon has no X section")`
before any other check. `x-wait` and `x-merge` already handle `skipped`.
`x_audit_bit` returns nothing when the skip reason is the slot, so the audit
line does not report X for a run that never had it.

**`build_audit_line`** for an afternoon run: `Audit (afternoon, updates
<base run_id>): 6 of 6 sources screened · N articles new since the morning
(M already seen) · undated … · kept … · items (F following a morning story,
S new but too small to read) · read · notes with a figure removed · K new ·
L moved (a developments, b confirmations, c reversals, d corrections) ·
profile of … · retries · failures.`

### 4.7 `SKILL.md`

- Front matter: `argument-hint: "morning | afternoon"`; the description gains
  one sentence: "`afternoon` writes what changed since that day's morning
  brief: new stories first, then the morning's stories that moved."
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
- `items-sync`: `follows` rejected in a morning run; a bare id or a non-pick
  rejected in an afternoon run; followers grouped `follow-read` first; a small
  new item is not read and is counted.
- `picks-sync` afternoon: tags, `kind`, `follows` consistency, `unchanged`
  reason, trim order, empty picks accepted, `leads` empty, the base's
  `picks.json` untouched.
- `fill pick` writes `prompts/pick.md` from `pick-update.md` in an afternoon
  run; `fill counterpoint` refuses a `MOVED` pick; `fill write --section
  leads` is refused in an afternoon run.
- `write-stitch` afternoon: two sections, kind prefix and base order
  checked, `{{BASE_TIME}}` filled, `EMPTY_UPDATE_LINE` when nothing was
  picked.
- `x-start` afternoon: `skipped`, and the audit line carries no X bit.
- `audit-line` afternoon shape.

`tests/test-prompts-v4.py`: `RUN_VARS` gains `SLOT_JOB`, `BASE_STORIES`,
`BASE_DROPPED`, `BASE_TIME`; `PICK_RULES` is a fragment name the namespace
already answers for; the afternoon prompts render with no unfilled placeholder
from a fixture base run; `cluster-select` for a morning run renders
`{{SLOT_JOB}}` empty; `afternoon.md` goes through the same placeholder check
as `morning.md` and its headings match the slot's sections; the said-twice
test stays green, which is what the fragment and the "as `morning.md` says"
wording are for.

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
3. `_pick-rules.md`, `pick-update.md`, `pick.md` trimmed, `picks-sync`, `fill
   pick`; tests. Commit.
4. `section_job`, `picks_block` for `moved`, `write-stitch`,
   `template_head`, `x-start` skip, audit line; tests. Commit.
5. `SKILL.md`, README, DEVLOG, STATUS. Commit.
6. One live `/ybs-brief afternoon` against today's morning run, timed from
   `run.json`. Expected: about 20 to 25 minutes, since most of the day's
   articles are already seen and dropped at `screen-sync`.
