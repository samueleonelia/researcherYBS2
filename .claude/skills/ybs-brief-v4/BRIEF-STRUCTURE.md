# The structure of the morning brief

<!--
Maintainer notes. Everything above the marker below is for whoever edits this
file; only the text after it is injected into the write prompt.

Status: draft for v5 — under review, not yet built.
The single home for the brief's shape. templates/morning.md is the markdown
skeleton only; every rule about what goes where lives here.
Not here: sentence craft (prompts/write.md) · judgment and tags
(prompts/_criteria.md) · numbers (settings.md) · what counts as positive
(prompts/_principles.md).

Open decisions are marked with blockquotes below. They are questions for a
human, so they are stripped on injection too: an agent must never receive an
unresolved choice as if it were an instruction.
-->

<!-- STRUCTURE:BEGIN -->

## The shape

Every story in the brief is a heading, its story, then its numbered sources.
The same three parts everywhere, at every level.

```
**Date:** 25 August 2026 at 10:00

## What leads

### 1. The Supreme Court let Trump's mail-voting order proceed without ruling on whether it is legal.

The Court said Monday only that Democratic-run states sued too early in June.
New Postal Service rules take effect Tuesday if a second injunction is lifted.
States that do not comply would not have ballots sent. The Constitution gives
control of election procedure to the state legislatures and, for federal races,
to Congress. The president is not on that list, and the Court did not touch that
question. Officials call compliance impossible, but the article does not say what
makes the electronic system infeasible rather than merely rushed.

1. [Supreme Court allows Trump mail-voting order to take effect](https://apnews.com/article/...) — AP News
2. [States scramble as mail ballot rules land weeks before deadline](https://www.theguardian.com/...) — Guardian
3. Election officials say new envelope rules cannot be met in time — Reuters (no link)


#### COUNTERPOINT - A federal court blocked the deportation of noncitizens for their speech.

A federal judge ruled the First Amendment broadly bars the government from
deporting noncitizens over political speech, and quoted the reasoning at length.
This is P04: a court holding an agency to objective law it cannot rewrite at
will. It restrains one government power in one circuit. It does not settle the
question nationally, and the ruling can be appealed. Bears on the 200,000 visas.

1. [Judge rules speech-based deportations unconstitutional](https://apnews.com/article/...) — AP News



### 2. Trump raised tariffs on $20 billion of Canadian imports after weekend talks collapsed.

A tariff is a tax collected at the American border from the American importer.
Canada's only loss is a sale it can redirect. Susan Collins names the Maine
industries hit by her own government: lobster, blueberries and lumber. AP frames
the story almost entirely as electoral arithmetic. It gives no trade balance
figures and no estimate of who bears the cost.

1. [Trump hits Canada with new tariffs as talks collapse](https://apnews.com/article/...) — AP News
2. [Canada plans retaliation after tariff increase](https://www.theguardian.com/...) — Guardian

## Secondary Topics 

### U.S. immigration enforcement 

#### The State Department plans to revoke up to 200,000 tourist and business visas held by asylum seekers.

State said Monday it is working with Homeland Security to cancel B1 and B2 visas
issued between 2016 and 2026. A blanket ten-year retroactive revocation punishes
every lawful visa-holder in the category without adjudicating a single claim. The
200,000 figure is not an official number: it comes from AP, citing documents and
two unnamed officials, and State would not confirm it.

1. [US to revoke visas of asylum seekers](https://www.theguardian.com/us-news/...) — Guardian

#### ICE deported the wife of an active-duty Army sergeant to Honduras on Monday.

Cristy Maryori Villafranca-Trejo was detained on 11 July outside a Walmart near
Fort Bliss, Texas. A motion to reopen and a military parole-in-place application
were both still pending when she was removed. Her claim that she never knew about
the 2017 order rests solely on her husband's account.

1. [Army sergeant's wife deported to Honduras](https://apnews.com/article/...) — AP News

### The war in Ukraine

#### Putin signed a decree letting the Russian state seize companies judged too slow to protect attacked facilities.

It covers Wildberries, Ozon, and fuel and transport firms. This is the state
converting its own failure to defend the warehouses into a legal claim against
the owners. The 30% share fall is given with no baseline price or market cap.

1. [Ukraine war briefing: Ozon next in Kyiv's sights](https://www.theguardian.com/world/...) — Guardian
2. [Russian decree targets firms over damaged sites](https://www.bbc.com/news/...) — BBC

## Worth Yaron's attention

### Australia's recording industry body now bars largely AI-generated songs from its charts.

ARIA requires from this week that releases be "substantially human made". ARIA is
a private trade body setting the terms of its own product, so no artist's rights
are touched here. The BBC never says how much of the disputed track was actually
AI-generated, which is the whole factual dispute.

1. [ARIA bans AI-generated music from charts](https://www.bbc.com/news/articles/...) — BBC

{{AUDIT_LINE}}
```

---

## The rules behind the shape

### Sections

| Section | Level | Holds | Ceiling |
|---|---|---|---|
| `## What leads` | `##` | the day's agenda-setting stories, numbered | `lead_max` |
| `## Secondary Topics` | `##` | one `###` per topic, topics invented from the day | — |
| `## Worth Yaron's attention` | `##` | the story a well-read person would have missed | `worth_max` |

The three `##` sections are fixed and always in this order. Everything variable
is below them: topics are `###` inside Secondary Topics, and a `#### COUNTERPOINT`
sits inside the lead it bears on.

1. **No empty sections.** Nothing qualifying means the section is omitted — no
   placeholder, no "none found".
2. **Ceilings are never floors.** Two leads is right on a two-lead day.
3. **Topics are invented from the day.** No fixed list. `### The war in Ukraine`
   exists on a day with Ukraine stories and not otherwise.
4. **Leads are ordered by consequence**, most consequential first.
5. The last line is the audit line, written by code, never by an agent.

### Every story

- **The heading is the headline sentence.** `###` for a lead (numbered: `### 1.`)
  and for a Worth story; `####` for a story inside a topic. One clause, ~14
  words, a concrete actor doing a concrete action. It must survive being read
  alone by someone who does not know the story.
- **The story** is what happened · why it matters · what the evidence does not
  establish, in that order, never woven together. The third part is mandatory:
  where a note's `WEAK SPOTS` says the story is thin, that caveat gets its own
  sentence. A story he cannot lean on must not read as one he can.
- **The sources** are a numbered list of every article that went into the story,
  including ones grouped but never read. Today those vanish from the brief; here
  they are visible as corroboration.
  - **Item 1 is always the article the story was written from** — the picked
    article, whose note is the story. The rest of its item follows.
  - **Reuters is listed, never linked:** `<headline> — Reuters (no link)`.
  - Real headlines and real URLs from the run's own data. Never invented.

### Counterpoints

For each **LEAD only**, one agent answers one question: do the other reports of
this lead's own event show a positive element or an improvement bearing on the
problem it describes?

**The task is to check, not to find.** Most days, for most leads, the answer is
no. Reporting that is the correct outcome, not a failure.

**Where it looks:** inside the lead's own news item, and nowhere else. The other
outlets covering that event are the whole field. What one of them reported and
the lead's article did not — the part struck down, the limit imposed, the
exemption, the refusal — is where a counterpoint comes from. Good news from an
unrelated story is not a counterpoint to this one. A lead whose item is a single
article has none by construction.

**What qualifies** — all three, judged against `prompts/_principles.md`:

1. It bears on the lead's **problem**, not merely on the same event.
2. It is a positive instance of a **named principle**, not just pleasant news.
3. It is **real and reported today** — not a proposal, promise, prototype or
   financing announcement.

Failing any one means that lead has no counterpoint. A counterpoint is the
positive story plus a short why: which principle makes it positive, and what it
does not establish. No long argument, no historical case.

**Never force optimism.** The "does not establish" sentence is mandatory here
exactly as it is on a story.

**Where it sits:** `#### COUNTERPOINT - <headline sentence>`, inside the lead it
bears on, after that lead's own source list. It is never a section of its own.
A lead with no counterpoint simply has none, and nothing marks the absence.
