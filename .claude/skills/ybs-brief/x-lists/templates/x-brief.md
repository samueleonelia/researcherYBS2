# X brief — what the list is moving on

This file is the whole shape of the X brief: nothing else says where a thing
goes. How the sentences are written lives in `prompts/write.md`, and nothing
here repeats that. There is no writing advice in this file.

## The shape

```
# What the list is moving on

**Run:** <run folder name> · **Window:** <N> hours, to <D Month YYYY at HH:MM UTC>

## TRENDING

### <n>. <Headline sentence, ends with a period.>

<the story>

- **Storyline:** <the storyline, copied word for word from this pick>
- **Flags:** <CONVERGENCE · ENDORSEMENT · VELOCITY — only the ones this pick has>
- **Source:** [@handle](<the tweet permalink>)

### <n>. <Headline sentence.>

<the story>

- **Storyline:** <...>
- **Flags:** <...>
- **Source:** [@handle](<the tweet permalink>)

## CURIOUS

### <n>. <Headline sentence.>

<the story>

- **Storyline:** <...>
- **Flags:** none
- **Source:** [@handle](<the tweet permalink>)

---

<n> picks from <n> subjects judged. TRENDING items carry a flag from the list. CURIOUS ones carry none.
```

## Rules of the shape

### The header

- The `#` title is exactly `What the list is moving on`. It never changes.
- One `**Run:**` line, exactly as above. The run folder name, the window in
  hours and the run's date and time all come from the write prompt's inputs.
  Nothing else goes on this line.

### The sections

- Two `##` sections, always in this order: `TRENDING`, then `CURIOUS`.
- A section with no picks is left out entirely: no heading, no placeholder, no
  "none". A run with only TRENDING picks has one section, and that is correct.
- A pick goes under the section its `Tag:` names, and under no other.

### The items

- Every pick in `picks.md` becomes exactly one item. Nothing is added, nothing
  is merged, nothing is split, nothing is dropped. That choosing happened
  before this step.
- Items are numbered `1.`, `2.`, `3.` … in one run of numbers that starts at 1
  in TRENDING and keeps counting into CURIOUS. The numbers do not restart.
- Inside a section, items stay in the order `picks.md` lists them.
- Every item is a `###` heading, then the story, then the same three bullets in
  the same order: `Storyline`, `Flags`, `Source`. Never a fourth bullet, never a
  missing one, never a different order.
- The heading is one sentence and ends with a period. The item number, then a
  space, then the sentence.
- The story is one or more plain paragraphs between the heading and the
  bullets. No sub-headings, no bullets, no blockquote, no bold inside it.

### The three bullets

- **Storyline** — the storyline name copied character for character from this
  pick. Never reworded, never shortened, never two of them.
- **Flags** — the flag words from this pick, in this order when the pick has
  more than one: `CONVERGENCE`, `ENDORSEMENT`, `VELOCITY`, joined by ` · `.
  A pick with no flag reads exactly `none`. No counts, no numbers, no
  explanation on this line: one word each.
- **Source** — one markdown link, the author handle as the link text and the
  tweet permalink as the target, both copied character for character from this
  pick. Exactly one source per item, and never a link to anything else.

### The last line

- A `---` rule, then one closing line, exactly in the shape above: how many
  picks the brief carries, how many subjects the run judged, and the one
  sentence saying what the two tags mean. Both numbers come from `picks.md`.
- Nothing after that line.

### A run with no picks

When `picks.md` has no picks, the brief is the title, the `**Run:**` line, and
one sentence saying the run produced nothing that reaches the brief. No
sections, no rule, no closing line. That is a correct brief, not a failure.

## A filled example

This is what the shape looks like once written. It is here so the target is
visible; it is not text to copy.

```
# What the list is moving on

**Run:** 2026-09-06-0954 · **Window:** 1 hours, to 6 September 2026 at 09:54 UTC

## TRENDING

### 1. Zelensky says his negotiating team is meeting Trump's envoys in Kyiv.

Zelensky posted that he had met his own negotiating team before seeing the US
president's envoys. He said Ukraine is ready for the conversation and wants the
end of the war brought closer. He named security guarantees as what Ukraine is
after. The post moved faster than almost anything else the list posted in the
window.

A negotiated end is worth something only if it leaves Ukraine able to defend
itself. A talk about talks is not that yet. The post says nothing about
territory, about what either side would concede, or about who would guarantee
anything.

- **Storyline:** Russia grinding down Ukraine while its own state rots
- **Flags:** VELOCITY
- **Source:** [@ZelenskyyUa](https://x.com/ZelenskyyUa/status/2096536036985774114)

### 2. Burnham says sanctioning Israel would put British national security at risk.

A broadcaster on the list reported Burnham warning that Israel sanctions risk
British national security. Members of the list converged on the warning within
the hour.

The argument being made is prudential, not moral. It says sanctions would cost
Britain, not that the case for them is wrong. The post gives no sanction, no
date and no mechanism, so what is actually being proposed is not on the record
here.

- **Storyline:** Israel, antisemitism and the double standard
- **Flags:** CONVERGENCE
- **Source:** [@GBNEWS](https://x.com/GBNEWS/status/2096500467123581235)

## CURIOUS

### 3. Florida has designated the Muslim Brotherhood and CAIR as terror organisations.

One account on the list reported the designation of both organisations by the
state of Florida. No other member of the list picked it up.

Naming an enemy is the first condition of acting against one, and a state
government has now done it where the federal government has not. The post
carries no legal instrument, no effective date and no statement of what the
designation actually changes.

- **Storyline:** Islamic totalitarianism and the refusal to name the enemy
- **Flags:** none
- **Source:** [@handle](https://x.com/handle/status/2096500000000000000)

---

3 picks from 36 subjects judged. TRENDING items carry a flag from the list. CURIOUS ones carry none.
```
