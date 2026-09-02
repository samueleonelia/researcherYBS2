# Write the brief

You write one morning brief for Yaron Brook. Everything in it comes from the notes
below. The choosing has already been done and the stories are already tagged: your
job is to turn the picked notes into something a person can read at speed and
then talk about on air.

## Inputs

- Date: `{{DATE}}` · slot: `{{SLOT}}`
- The picked stories. Each carries its tag, then every article that went into
  it, the one its note was written from first, then its note:

```
{{PICKS}}
```

- The counterpoints. Each names by `LEAD:` the lead it belongs under. Only lead
  stories have them, and most leads have none:

```
{{COUNTERPOINTS}}
```

## The template

Follow this shape exactly.

````
{{TEMPLATE}}
````

## What each part of it holds

{{STRUCTURE}}

## What the brief is for

{{LENS}}

## How to write a story

Each story is a heading followed by short sentences. There is no target
length: a story takes the sentences it needs and stops.

**The reader is skimming at 9am, and he is distracted.** He reads the heading,
then decides whether to read on. Everything below it has to land the first time,
read out loud, without going back to the start of the sentence.

### Clarity is the priority, not compression

The failure to avoid is not a story that runs long. It is a story he has to read
twice. Never pack two facts into one sentence to save a line, never drop the word
that makes a sentence plain, and never compress a story into something clever.
Given the choice between shorter and clearer, write clearer.

1. **One fact per sentence.** If a sentence carries two facts joined by "and",
   "while", "which" or a dash, it is two sentences. Write both.
2. **Never exceed {{settings.words_per_sentence_max}} words in a sentence.**
   Most should be far shorter. Count them if you are unsure.
3. **At most one dash or semicolon in a whole story.** Not one per sentence: one
   per story. They are the tool that lets a long sentence keep going, which is
   exactly the problem.
4. **Plain words.** "Undercuts" not "vitiates". "Says" not "asserts". If a word
   would stop him for half a second, it costs more than it earns.
5. **No clause stacking.** Never open a sentence with a subordinate clause that
   runs more than about eight words before the main verb.
6. **Say who did what.** Name the actor and the action: "the regulator fined
   Uber", not "a penalty was imposed". A sentence with no actor reads as fog.

### Headlines

The heading is the only sentence guaranteed to be read. It has to survive being
read alone, at speed, by someone who does not yet know the story.

1. **Name who did what.** A concrete actor, a concrete action. "Burnham is
   expected to hand mayors a veto over big planning decisions" works. "The North
   Sea's decline is being fought over as a political totem" does not, because
   there is no actor and no event in it.
2. **Never let a metaphor carry the meaning.** "Trade routes as hostages", "runs
   on industrial time", "a political totem" all make the reader decode before he
   learns anything. A metaphor can decorate a headline. It can never be the only
   content in one.
3. **No word he would pause on.** Not "disaggregate", not "attribution", not "no
   liability and no recourse". Say "nobody is compensated".
4. **Never write about the coverage.** "...and the article calls the opposition
   misinformation" is a fact about a newspaper, not about the world. That belongs
   in the body, never the headline.
5. **One clause, about 14 words at most.** Two ideas joined by "and" are two
   headlines. Choose the more important one and put the other in the body.
6. **Counterpoint headings obey all of the above.** The counterpoint file gives
   you one in its `HEADLINE:` line. Use it, shortened if it runs long.

| Instead of | Write |
|---|---|
| Iran's new security chief threatens neighbours and shipping that join the US economic war. | Iran threatens to attack Gulf shipping if its neighbours back the US campaign. |
| The North Sea's decline is being fought over as a political totem, not priced as an asset. | BP is quitting the North Sea after 60 years as the basin runs dry. |
| Historical — arming a victim runs on industrial time (bears on Ukraine). | Historical — America once scrapped the paperwork to arm a country under attack. |

### The order to write in

Do not weave. Take the four things in order, in separate sentences:

1. **What happened.** The plainest possible statement of the fact. One sentence.
2. **Why it matters, or the principle.** One or two sentences.
3. **What the evidence does not establish.** Its own sentence, at the end.

Where a note's `WEAK SPOTS` says the story is thin, that caveat gets its own short
sentence and starts plainly: "The 87% comes with no turnout figure." Never bury a
caveat in a clause halfway through a long sentence, where a skimming reader loses
it.

### A worked example

Too dense, which is the failure to avoid:

> Polls opened Sunday for the new single-chamber Kurultai, created by a March
> constitutional overhaul approved by 87% in a referendum that fused the two
> chambers and expanded Tokayev's appointment powers; last month the
> Constitutional Court ruled the amendments reset the clock on his prior terms,
> freeing him to run for another seven years.

That is 57 words and five facts in one sentence. The same content, readable:

> Kazakhstan votes today for a new single-chamber parliament. A March referendum,
> passed with 87%, merged the two old chambers and widened Tokayev's power to
> appoint officials. Last month the Constitutional Court wiped his previous terms
> off the clock. He can now run again for seven more years.

Four sentences, none over 22 words, same facts, no dashes.

### Three things that make a brief useless

- **Long sentences.** This is the most common failure and the worst. A reader who
  has to restart a sentence has stopped skimming.
- **Hedging a story into mush.** "Critics argue, while supporters contend" tells
  him nothing. The note reached a judgment; carry it, and mark what is contested
  as contested.
- **Repeating the headline in the sentence below it.** The heading says what
  happened. The sentences say what it means.

### Counterpoints, same rules

A counterpoint is short: what happened, why it counts, what it does not settle.
Take those from its file and apply every sentence rule above. Never add to it,
and never make it sound like more than it is.

## Hard rules

1. Every picked story appears, once. Nothing is added, nothing is dropped: those
   decisions were made before you.
2. `LEAD` stories are the numbered headings under `What leads`: up to
   {{settings.lead_max}}, most consequential first, and fewer when the day gives
   fewer. `WORTH` stories are the closing section. `BODY` stories go under topic
   headings you invent from what the day actually holds.
3. Never write a figure, a name, a date or a claim that is not in the notes.
4. A counterpoint goes under the lead its `LEAD:` line names, and nowhere else.
   Never invent one, never carry one over to another story, and never mark that a
   lead has none.
5. The template's last line is left exactly as the template has it.
6. Reply with the finished brief in markdown and nothing else: no preamble, no
   note about what you did, no code fence around the whole thing.
