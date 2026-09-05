# Is there a counterpoint inside this story?

The brief reports what happened, and most of what happens is bad. This step asks
one narrow question about one lead story:

**Do the other reports of this same event show a positive element, or an
improvement, bearing on the problem this lead describes?**

You look in one place only: the other articles covering the same news item as
the lead. Not elsewhere in the day's news. If the good news is in some unrelated
story, it is not a counterpoint to this one, and this step does not want it.

You are not being asked to find one. You are being asked to check. Most days,
for most leads, the answer is no, and reporting that is the right answer, not a
failure. A forced counterpoint is worse than none: it tells the reader the day
was better than it was.

## Inputs

- The lead: `{{ARTICLE_ID}}`
- What happened: {{WHAT_HAPPENED}}
- The principle the reader found: {{PRINCIPLE}}
- Run directory: `{{RUN_DIR}}`

The other articles reporting this same news item, and nothing else:

```
{{ITEM_POOL}}
```

A sibling marked `READ` carries the whole note a reader wrote from it and names
the page that reader saved. You may read that page. A sibling that was not read
gives you its headline, its description and its link.

## Step 1 — what is the problem here?

Say it to yourself in one sentence before you look at the siblings. Not the
topic, the problem. A lead about a president rewriting election procedure by
order is not about elections; the problem is an executive taking a power the law
places elsewhere. A lead about tariffs is not about Canada; the problem is a tax
laid on people who never agreed to it.

The counterpoint has to bear on that problem.

## Step 2 — the principles

{{PRINCIPLES}}

## Step 3 — is there a positive element in these reports?

The siblings report the same event, so most of what they carry is the same bad
news the lead carries, told again. You are looking for the part of the event
some outlet reported and the lead's own article did not: the limit somebody put
on it, the part that was struck down, the refusal, the exemption, the reversal,
the thing that worked.

Whatever you find has to pass all three:

1. **It bears on the lead's problem.** Not merely on the same event. A sibling
   adding detail to the damage is not a counterpoint. A court blocking part of
   the order the lead describes is.
2. **It is a positive instance of one of the principles above.** Name which one.
   If you cannot name it, you do not have one.
3. **It is real and it happened.** A bill introduced, a challenge filed, a
   promise to review, a company saying it will do better, an analyst predicting
   a reversal: none of these are counterpoints. Something has to have actually
   changed.

Nothing passing all three is the expected result. When that happens, use the
Write tool to put the single word `NONE` in
`{{RUN_DIR}}/picks/cp-{{ARTICLE_ID}}.md`, reply `{{ARTICLE_ID}} NONE`, and stop.
Do not weaken a test to get past it.

## Step 4 — confirm it on the page

Write the counterpoint **from what a page confirms**, never from a headline or a
description. Every figure you quote is checked against that page, exactly as a
reader's note is.

If the sibling you chose was read, its saved page is already named above: read
that file. If it was not read, open it, once, exactly as a reader does:

```bash
ego-browser nodejs <<'EOF'
const fs = await import('fs')
await useOrCreateTaskSpace('ybs cp {{ARTICLE_ID}}')
await openOrReuseTab('<THE URL OF THE SIBLING YOU CHOSE>', { wait: true, timeout: 40 })
const txt = await js(String.raw`document.body.innerText`)
fs.writeFileSync('{{RUN_DIR}}/pages/cp-{{ARTICLE_ID}}.txt', txt)
cliLog(JSON.stringify({ chars: txt.length, url: (await pageInfo()).url }))
await completeTaskSpace('ybs cp {{ARTICLE_ID}}', { keep: false })
EOF
```

If the page does not support what the headline promised, that candidate is gone.
Go back to the siblings once. If nothing else passes, the answer is `NONE`.

## Output

Use the Write tool to create `{{RUN_DIR}}/picks/cp-{{ARTICLE_ID}}.md` holding
exactly this form:

```
LEAD: {{ARTICLE_ID}}
HEADLINE: <one plain sentence: who did what. This becomes the heading in the brief.>
PRINCIPLE: <P0x> — <its name>
THE POSITIVE: <2-3 sentences: what actually happened, from the page you read>
WHY IT COUNTS: <1-2 sentences: why this is that principle's positive side>
WHAT IT DOES NOT ESTABLISH: <one sentence: the limit of it>
SOURCE: <the url of the sibling>
TITLE: <the article's headline, as the page gives it>
PUBLICATION: <the publication's name>
KEY FIGURES:
- <figure> — <what it measures>
```

Then reply with one line: `{{ARTICLE_ID}} written` or `{{ARTICLE_ID}} NONE`.

## Hard rules

1. **`NONE` is a good answer.** Never stretch a story to fill the slot. Never
   argue that something is positive if you had to work to see it.
2. **Only the siblings above are candidates.** They report the lead's own event,
   and they are the whole field. Never reach for another story from the day's
   news, and never use the lead's own article: a story is not its own
   counterpoint.
3. **At most one page opened.** You cannot search the web and do not need to:
   the siblings are listed above, with the pages of the ones already read.
4. **Every figure comes from the page you read.** A number you remember,
   inferred or converted will be struck.
5. `KEY FIGURES` is left empty when the page gives you no numbers worth
   repeating.
6. **Never write the argument the old step wrote.** No historical parallels, no
   cases from memory, no "this is what the principle predicts". One real thing
   inside today's event, and what it does not prove.
7. You write the file yourself. Reply with one line, never the counterpoint.
