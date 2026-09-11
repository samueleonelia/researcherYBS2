# Merge the parts into one set of subjects

This run's kept tweets were too many for one call, so the list was cut into
{{PARTS}} parts and each part was grouped into subjects on its own. You see
every subject every part made, with the tweets inside it. One job: **produce the
single set of subjects the run would have had if one agent had seen the whole
list.**

You open nothing and read nothing outside this prompt. The lines the parts saw
are all the evidence there is.

## Inputs

- Run folder: `{{RUN_DIR}}`
- The parts' subjects. Each subject's first line gives its part and its name;
  its tweet lines follow, as that part saw them — id, author, text, quoted text,
  card title:

```
{{PART_SUBJECTS}}
```

- Every tweet id in this run, in one list, so you can check your work:

```
{{ALL_TWEET_IDS}}
```

## The job

- Subjects from **different** parts that are about the same thing become one
  subject. Union their tweet ids and give the merged subject one name — either
  part's name, or a clearer one covering both.
- Subjects from the **same** part are **never** merged. That part already saw
  them side by side and decided they were different things.
- Every other subject passes through **unchanged**: same tweet ids, same name.
- Near-duplicate tweets that landed in different parts — the same story reposted,
  the same headline pasted twice — go into one subject, both ids kept.
- A subject that matches nothing in any other part stays as it is, alone. A
  single-tweet subject is a normal result, not a loose end.

The test for "the same thing" is the one the parts used: one event, one
announcement, one claim, one argument. Agreement is not the test — two people
fighting over one rate cut are one subject. Same topic, different thing, stays
two subjects.

## Output

Write **one file** and nothing else:

`{{OUTPUT_PATH}}`

It holds one JSON object, in exactly the shape a part used:

```json
{
  "subjects": [
    {
      "subject": "Fed pencils in two more cuts this year",
      "tweet_ids": ["1000000000000000001", "1000000000000000002", "1000000000000000009"]
    },
    {
      "subject": "Argentina lifts its capital controls",
      "tweet_ids": ["1000000000000000007"]
    }
  ]
}
```

No other key, at the top level or inside a subject. No commentary in the file,
no markdown fence around it, no notes, no scores, no record of which part a
subject came from. Create no other file and edit no existing one.

When you are done, say in one line how many subjects you merged into how many,
and confirm every id was placed. That line is all you say.

## Hard rules

1. **Every id in `{{ALL_TWEET_IDS}}` appears in exactly one of your subjects.**
   Not zero, not two. Check both ways before writing: nothing missing, nothing
   invented, nothing repeated. Code checks this against the run's kept list and
   the run fails if it does not hold.
2. Copy every id **character for character**. A single wrong digit fails the run.
3. **Never merge two subjects that came from the same part.**
4. **Do not count anything.** No tweet counts, no author counts, no totals, no
   engagement numbers, no ordering by size. Code does the counting.
5. **Do not rank the subjects** and do not order them by importance. Any order
   is fine.
6. **Do not judge relevance.** Nothing is dropped here for being trivial or
   off-topic. The judge decides later what reaches the brief.
