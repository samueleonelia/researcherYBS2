# Plan: the evening report of human achievements

Written 2026-09-10. Goal: `/ybs-brief evening` produces one `brief.md` that
shows **the constructive side of the day on its own**: the stories that show a
way out of the problems the morning and the afternoon reported, each one
labelled honestly for how far it has got, so a press release never reads as a
solved problem.

Samuele's own shape of it, in order (2026-09-10):

1. No screening.
2. Take every link the morning and the afternoon sent to triage **and kept**.
3. Dedup if needed.
4. Triage again, with a different question: keep only the five kinds below.
5. Cluster into news items.
6. Pick. 7. Read. 8. Write. Plus a third X round, as the morning runs it.

Decisions he took on 2026-09-10, binding here:

- Slot name **`evening`**.
- Pool = articles **kept at triage** in the morning and the afternoon. Dropped
  ones are not looked at again.
- Triage keeps an article only when its headline or description reports one of
  **five kinds**: technological innovation · medical and/or scientific
  progress · market adaptation over bureaucracy · institutional reform in
  favor of individual rights and free markets · heroic examples manifesting
  the greatness of human individuals and reason.
- **Labels at pick, not at triage.** The five labels in `_criteria.md`
  (Demonstrated, Emerging, Speculative, Historical, Biographical) are assigned
  by the pick agent from the note.
- **At most 5** stories. **Zero is a valid result**: the brief then says so in
  one sentence.
- **No** code-checked tie between a story and a problem of the day. The writer
  may say in prose which problem a story answers; nothing checks it.
- **No counterpoints.** The whole report is the counterpoint.
- The X pipeline runs exactly as in the morning and the afternoon.

## 1. The one design decision

**The evening is the same pipeline with a third slot, and the slot decides in
code.** Same `SKILL.md` steps, same agents, same pool, same retries, same
figure check, same stitch. Four things differ, and `ybs_run.py` settles all
four when it sees `slot: evening` in `run.json`:

- where the articles come from (the two earlier runs, not the front pages),
- what triage is asked (the five kinds, not the beats),
- what the pick is asked (which stories, and which label each one earns),
- what the template says the report looks like.

The one place the orchestrator itself branches is step 2: an evening run has no
screeners to launch, so `SKILL.md` says "for `evening`, step 2 is one command".
Everything else it does the same way, and the commands answer differently.

## 2. Where the articles come from

**The base runs.** `start --slot evening` finds today's latest completed
`morning` run, exactly as the afternoon does, and refuses without one. It also
looks for today's latest completed `afternoon` run and takes it if there is
one; an evening with no afternoon behind it is still a report. `run.json`
records `base` (the morning, same record as the afternoon's) and
`base_afternoon` (the same shape, or `null`). `--base <run_dir>` names the
morning, as today.

**The pool.** A new command, `pool-sync --run <run_dir>`, replaces the screen
step. It reads each base run's `triage/verdicts.json` and `articles.json`
through `kept_articles()`, so "kept" means exactly what every later step of
that run meant by it: verdict `keep`, whether an agent, the section or a
give-up decided it. It merges by canonical URL (`canon()`), the same way
`screen-sync` merges duplicates, and writes the evening's own `articles.json`:

- ids renumbered `a001…` in order, morning first, then afternoon, each in its
  base run's id order;
- every record carries `origin: {"run_id": "<base run_id>", "id": "<old id>"}`;
  a URL found in both runs keeps the morning's origin and adds the afternoon's
  source to `also_in`;
- counts in `run.json`: `pooled_morning`, `pooled_afternoon`,
  `pool_duplicates`, `screened` (the pool size, so `triage-list` and the audit
  line read the number they always read).

`screen-sync` and `fill screen` refuse an evening run by name ("an evening run
pools two earlier runs; run pool-sync"). Nothing in the evening touches a
browser before the reads.

**Not done, on purpose.** The evening does not re-screen. A good-news story
published after the afternoon ran is caught tomorrow morning. A morning
article that was dropped at triage as off-beat is not looked at again: an
off-beat achievement is not for the show either.

## 3. The steps, and what changes in each

| Step | Morning | Evening |
|---|---|---|
| 0 preflight | same | same |
| 1 start | `start --slot morning`, `x-start` | `start --slot evening` finds the two bases; `x-start` as in the morning |
| 2 screen | six screeners, `screen-sync` | **no screener**: `pool-sync`, one command |
| 3 triage | beats question; sections admit by code | five-kinds question; **nothing admitted by section**; same agent, same batches, same `triage-check` |
| 4-5 cluster | `cluster-select.md` | same file; `{{SLOT_JOB}}` says what the evening's items are; `follows` is `null` |
| 6 read | pool | same; the note gains one field (see 4.4) |
| 7 pick | `pick.md` | `pick-evening.md`, chosen by `fill pick` from the slot; every pick carries a `label` |
| 8 check | same | same |
| 9 counterpoints | one per LEAD | nothing: no LEAD tag |
| 10 write | three writers, `morning.md` | one writer, `evening.md`; `x-wait`, `x-merge`, the evening's audit line |

## 4. Changes, file by file

### 4.1 `settings.md`

One row under `## Numbers`:

| Setting | Value | What it means |
|---|---|---|
| achievements_max | 5 | human-achievement stories that may reach the evening report; zero is a valid result |

`## Models` does not change: triage, cluster, read, pick, check and write run at
their existing rows. The `write` row's last column gains "or the one section of
the evening report".

### 4.2 `prompts/_achievements.md`

New fragment, the one home of the five kinds, rendered as `{{ACHIEVEMENTS}}`
by `namespace()`. Two sections, so each reader pulls the part it needs:

- `## kinds`: the five kinds, one line each, with a one-line gloss:
  technological innovation (a thing that works, ships, or is measured working);
  medical and scientific progress (a result, an approval, a trial with people
  in it, a discovery); market adaptation over bureaucracy (people or firms
  routing around a rule, a shortage or a failing service, and it working);
  institutional reform for individual rights and free markets (a law struck,
  a rule repealed, a court siding with the individual, a monopoly opened);
  heroic examples (one identifiable person, what they did, and that reason or
  courage is the point).
- `## not`: what is none of the five, said once so triage and pick agree: a
  plan, a pledge, a funding round, a company's own forecast, a politician's
  promise, a poll, a market rally, a setback averted by luck, or the same bad
  news with a hopeful last paragraph. The one exception is an announced thing
  that is already running somewhere, which is a kind, labelled `Speculative`
  or `Emerging` later by the pick.

### 4.3 The triage agent, `agents/triage.md.tmpl`

The agent file is built once, before any run is known, so the slot reaches the
agent through the launch block. `SCHEMA["launch"]["triage_evening"]` is
`<run_dir> | evening` on the first line, then the same article lines. The
template gains one section, **"The evening's question"**, rendered from
`{{ACHIEVEMENTS}}` (both parts), opening: "When the first line of your block
ends in ` | evening`, the beats have already been settled by an earlier run,
and this section replaces the rule above." The rule:

```
keep   if the headline or description reports one of the five kinds
drop   if it reports none of them, or only something under "not"
```

"When in doubt, keep" stays; the doubt is now "is this one of the five?".
Three worked examples inside that section: a keep (a drug approved after a
trial, filed under Health), a drop (a minister promising a reform), and a keep
that the pick will later call `Speculative` (a plant announced with a first
line already running). `triage-list` on an evening run admits nothing by
section, writes no `category` verdicts, and prints the evening launch block;
`triage-check` is unchanged, because a verdict file is a verdict file.

### 4.4 The reader, `agents/reader.md.tmpl`

The note gains one field, in every slot, between `WHAT'S NEW` and `WEAK SPOTS`:

```
SCALE AND STAGE: <one sentence: how many people or units, since when, and whether it is running, in trial, approved, announced or promised; or "not stated">
```

One field for all three slots rather than an evening-only note: the reader
file has one form, `note_field()` reads it by name, the morning gains a line
it can ignore, and the pick has what the label needs without a second reader
template. The `KEY FIGURES` rule is untouched: a number in `SCALE AND STAGE`
is repeated there if the brief is to print it.

### 4.5 `prompts/cluster-select.md`, `cluster-merge.md`, `_item-shape.md`

No new placeholder. `slot_job()` renders a block for the evening as it does
for the afternoon (empty for the morning): "This is the evening report of
human achievements. Every article in front of you was kept this evening
because its headline promised one of these five kinds:" then `{{ACHIEVEMENTS}}`
kinds, then the verdict rule in the evening's terms: `READ` when the
achievement is reported as an event (a result, an approval, a launch, a
ruling, a rescue, a number); `MAYBE` for a column or a feature about one;
`DROP` for an article that, seen beside the others, reports none of the five.
`follows` is `null` on every item. `_item-shape.md`'s sentence becomes "In a
morning or an evening run it is `null` on every item, and code rejects
anything else there." `base_pick_ids()` already returns `None` for any slot
but `afternoon`, so `items-sync` rejects a non-null `follows` and applies no
small-new rule in the evening with no code change there.

### 4.6 `prompts/pick-evening.md`

A new prompt, the evening's step 7, rendered into `prompts/pick.md` by `fill
pick` when the slot is `evening`, so the orchestrator's launch line does not
change. It pulls `{{LENS}}`, `{{PREFERENCES}}`, `{{CRITERIA_FACTORS}}`,
`{{PICK_RULES}}`, `{{ACHIEVEMENTS}}` and, for the first time anywhere,
`{{CRITERIA_LABELS}}`. Its job:

- Inputs: date and slot; the notes (`{{NOTES}}`, the existing block, each
  note now carrying `SCALE AND STAGE`); the checklist (`{{NOTE_IDS}}`,
  `{{NOTE_COUNT}}`).
- For each note, two questions in order. **Is it one of the five kinds, now
  that the article has been read?** A headline promised it; the note says
  whether the article delivered. If not, drop it as `not-achievement`. **How
  far has it got?** Assign exactly one label from the table. The rule already
  written there holds: a proposal, a financing announcement, a prototype or a
  company's own claim is `Speculative`, never `Demonstrated`; when two labels
  fit, take the weaker. `SCALE AND STAGE` and `WEAK SPOTS` are where the
  answer is; a note whose `SCALE AND STAGE` says "not stated" cannot be
  `Demonstrated`.
- Ceiling: at most `{{settings.achievements_max}}`, tag `ACHIEVEMENT` on every
  pick. Prefer, where two stories are otherwise equal, the one further along
  (`Demonstrated` over `Emerging` over `Speculative`), and the one whose
  problem is one he is arguing about now. Zero picks is a correct reply on a
  day with none; padding with a press release is the failure this report
  exists to avoid.
- Output: `picks` (`id`, `tag`, `label`, `why`), `dropped` (`reason_type`,
  `reason`) with the five reason types written out by their
  `{{schema.reason_type.*}}` names (the four of `pick.md` plus the new one).

`SCHEMA["reason_type"]` gains `not-achievement`: "read in full, it reports none
of the five kinds: a plan, a pledge, a complaint or a setback". `SCHEMA["tag"]`
gains `evening: ACHIEVEMENT` and `label: demonstrated | emerging | speculative |
historical | biographical`. `LABELS` in code is read off that string, as
`KINDS` is.

### 4.7 `templates/evening.md`

The whole shape of the report. Title line `# Evening report (20:00) — human
achievements`, so `template_time` reads `20:00`.

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

Rules of the shape, in the template's words and not the morning's (the
said-twice test refuses a shared twelve-word run; where a rule is the
morning's, this file says "as `morning.md` says"):

- One section, always. Up to `{{settings.achievements_max}}` stories, the
  furthest along first: the pick's order is kept.
- Every heading opens with the story's label, capitalised, then ` - `, then
  the headline sentence. The label is the reader's honesty line: he sees how
  far a thing has got before he reads a word about it.
- A story's heading, body and sources take the three-part form `morning.md`
  gives.
- When nothing was picked, code writes the head and one sentence saying no
  human-achievement story was found today. The sentence is a constant in
  `ybs_run.py` (`EMPTY_EVENING_LINE`); the template does not quote it.
- `{{X_SECTION}}` and `{{AUDIT_LINE}}` as in the morning.

`{{POOL_LINE}}` is filled by `head_vars()`: "the morning brief of 10:00 and
the afternoon update of 16:00", or "the morning brief of 10:00" when there was
no afternoon; the times come from the base records, as `BASE_TIME` does.

### 4.8 `prompts/write.md`

Shared, unchanged in its rules. `section_job()` gains an `ACHIEVEMENT_JOB`
list beside `MOVED_JOB`, added when the slot is `evening`:

- The heading opens with the pick's label, capitalised, then ` - `, then the
  headline sentence. The label is given in the pick's head line; never change
  it.
- Write in this order: what was achieved and by whom, one sentence; how far it
  has got, in the terms of `SCALE AND STAGE`, with its numbers; which problem
  it answers, one sentence, only when the note makes it plain; what is not yet
  established, its own sentence, always. A `Speculative` story's last sentence
  says in plain words that nobody has been helped yet.
- Never make a story sound further along than its label. "Could", "aims to"
  and "is expected to" are the words for `Speculative`; "does" and "has" are
  for `Demonstrated`.

`picks_block()` puts the label in the pick's head line the way it puts the
afternoon's kind. `NO_COUNTERPOINTS` becomes per slot, `"None: the {name}
carries no counterpoints."`, with a short name per slot (`afternoon update`,
`evening report`); the morning keeps its block.

### 4.9 `ybs_run.py`

**Per-slot tables.** `WRITE_SECTIONS["evening"] = ("achievements",)`,
`TAG_OF_SECTION["evening"] = {"achievements": "ACHIEVEMENT"}`. `start
--slot` and `fill --section` follow from the tables as today.

**`start`**: `find_base(named, local_date, slot="morning")` gains the slot
argument and an `optional` flag; for `evening` it is called twice: morning
required, afternoon optional (`None` when today has none). `run.json` gets
`base` and `base_afternoon`. `--base` with `--slot morning` still dies.

**`pool-sync`**: as in section 2. Dies when a base run has no
`triage/verdicts.json` (that run never finished triage). Logs
`pool_built` with the three counts.

**`screen-sync`, `fill screen`**: die by name on an evening run.

**`triage-list`**: no category admission and the evening launch head when the
slot is `evening`. Everything else, including batches and the freeze, as today.

**`fill`**: `SLOT_JOB` for the evening (4.5); `fill pick` chooses
`pick-evening.md` for the slot; `ACHIEVEMENTS` joins `namespace()` so `build`
renders it into the triage template; `head_vars()` answers `POOL_LINE` for
the evening; `fill counterpoint` keeps refusing a non-LEAD pick, which in the
evening is every pick.

**`picks-sync`**: tags from the slot; for `evening`: ceiling
`achievements_max`, every pick needs a `label` in `LABELS`, no `kind`
allowed, no `follows` (the items have none), `picks` may be empty, trim over
the ceiling fewest articles first as the afternoon does; counts recorded:
`achievements`, `achievements_by_label`. `picks_mix` keeps its three morning
buckets. `leads` in the output is empty, so step 9 has nothing to launch.

**`write-stitch`**: with no picks on an evening run, the head plus
`EMPTY_EVENING_LINE`, as the afternoon's empty path; with picks, every `###`
under Human achievements must open with a label from `LABELS` (`LABEL_HEADING`,
built as `KIND_HEADING` is) and the stories must run in the pick's order
(URL positions ascending in `picks.json` order). `template_head` fills
`{{POOL_LINE}}` through `head_vars`.

**`x-start`, `x-wait`, `x-merge`**: unchanged. They read nothing about the
slot.

**`build_audit_line`** for an evening run: `Audit (evening, from <morning
run_id>[ and <afternoon run_id>]): no source screened · N articles pooled (M
from the morning, K from the afternoon, D duplicates merged) · J kept at
triage · I news items · R read · S notes with a figure removed · P human
achievements (a demonstrated, b emerging, c speculative, d historical, e
biographical) · profile of … · X: … · retries · failures.` No undated bit, no
by-section bit, no counterpoints bit. `audit_opening()` gains the evening
form; `AUDIT_OPENING` already matches any parenthesised opening.

**`schema`**: prints the new launch head, the evening tag, the labels, the
new reason type and the evening section, all from the tables above.

### 4.10 `SKILL.md`

- Front matter: `argument-hint: "morning | afternoon | evening"`; the
  description gains one sentence: "`evening` writes the day's human
  achievements from the articles the two earlier runs kept, each labelled for
  how far it has got."
- Where things live: one row, "the five kinds of achievement" → `prompts/_achievements.md`.
- Step 1: "For `evening` it names the morning run and, when there is one, the
  afternoon run it pools from; it refuses when today has no completed morning
  run."
- Step 2: one paragraph at the top: "**For `evening` there is no screen.** Run
  `pool-sync --run <run_dir>` and go to step 3; launch no screener."
- Step 3: "On an evening run nothing is admitted by section: every article
  goes to an agent, and the launch block's first line says `| evening`."
- Step 9: "An evening run has no leads either."
- Step 10: unchanged wording; "the run's slot" already covers it.

### 4.11 Tests

`tests/test-bookkeeping-v4.py`, in a runs folder of its own via
`YBS_RUNS_DIR`, reusing `build_morning()` and adding `build_afternoon()`
and verdict files to the fixtures:

- `start --slot evening` refuses without a completed morning run; takes the
  afternoon when there is one and records `base_afternoon: null` when not.
- `pool-sync`: ids renumbered morning first; `origin` on every record; a URL
  in both runs merged once with the afternoon source in `also_in`; dropped
  articles absent; counts; dies on a base without `verdicts.json`.
- `screen-sync` and `fill screen` refuse an evening run.
- `triage-list` evening: a `politics` article is not admitted; launch block
  first line ends `| evening`.
- `items-sync` evening: a non-null `follows` rejected; no `small_new_items`.
- `picks-sync` evening: `ACHIEVEMENT` only; missing or unknown `label`
  rejected; a `kind` rejected; over 5 trimmed smallest first; empty picks
  accepted; `not-achievement` accepted as a reason; counts by label; `leads`
  empty.
- `fill pick` renders `pick-evening.md` into `prompts/pick.md`; `fill write
  --section leads` refused; `fill counterpoint` refuses an `ACHIEVEMENT` pick.
- `write-stitch` evening: label prefix and pick order checked;
  `{{POOL_LINE}}` filled both ways; `EMPTY_EVENING_LINE` when nothing picked.
- `audit-line` evening shape, with and without an afternoon base.

`tests/test-prompts-v4.py`: `RUN_VARS` gains `POOL_LINE`; `ACHIEVEMENTS` is a
namespace name; `evening.md` goes through the placeholder check and its one
`##` heading matches the slot's section; `pick-evening.md`'s JSON example
passes `picks-sync` on an evening fixture (the labels in the example are the
lowercase strings the schema lists); the said-twice test stays green; the
triage agent file carries the five kinds after `build`. The pre-existing
failures (2 in `picks-sync` over 15 picks, 1 beat-vs-topic, the rotted profile
name that stops the cluster example) are noted before the first wave and are
not this plan's to fix.

### 4.12 `README.md`, `DEVLOG.md`, `STATUS.md`

README's `/ybs-brief` line gains the third slot. The usual entries.

## 5. What is deliberately not in this version

- **No re-screen.** See section 2.
- **No tie to a day story in code.** Samuele, 2026-09-10.
- **No cap on `Speculative` stories.** The label is the honesty; a day of five
  press releases is a day the label does its work. If a live run shows the
  report filling with them, that is a `## Numbers` row, not a redesign.
- **No evening-specific models.** Same rows.

## 6. Order of work, and the tests between

Each wave: change, `tests/run-all.sh` (expect only the four known failures),
commit.

1. `settings.md`, `SCHEMA` (launch head, tag, label, reason type, sections),
   per-slot tables, `find_base` with slot and optional, `start`, `pool-sync`,
   the two refusals; bookkeeping tests. Commit.
2. `_achievements.md`, `namespace()`, `triage.md.tmpl`, `triage-list` evening
   path, `reader.md.tmpl` field, `slot_job()` evening block, `_item-shape.md`
   sentence; tests. Commit.
3. `pick-evening.md`, `picks-sync` evening, `fill pick`; tests. Commit.
4. `templates/evening.md`, `head_vars`, `section_job`, `picks_block`,
   `NO_COUNTERPOINTS` per slot, `write-stitch`, `EMPTY_EVENING_LINE`, audit
   line; tests. Commit.
5. `SKILL.md`, README, DEVLOG, STATUS. Commit.
6. One live `/ybs-brief evening` on a day with a completed morning run (and,
   if there is one, an afternoon), timed from `run.json`. Expected 20 to 25
   minutes: about 180 articles reach triage in 18 batches (about 3 minutes at
   15 agents), one cluster call, and a read pool of 20 to 45 articles. What
   to look at: the keep rate at triage (over 40% means the question is too
   loose), the labels the pick gave against the pages, and whether any
   heading reads further along than its label.

## 7. Estimates

| | |
|---|---|
| Build | one session, five commits |
| Run | 20 to 25 minutes |
| Cost per run | triage on about 180 articles at sonnet/low, then a pool of reads like a quiet morning |
