# Plan: more than one X list

**Goal.** Yaron adds a second (and later a third) X list by typing one line in
`sources.md`, the same way he adds a news site. The X half reads every list in
that file, in one pass, and the brief is built from all of them together.

**Not in scope.** X account timelines (a profile page is a different page
shape), non-X feeds, and any speed ceiling: the run takes as long as the lists
take.

## What Yaron sees

`sources.md` gains a second section at the bottom:

```
## X lists

One line each: a name, then the list's link. Delete a line and that list is
not read any more.

1. Core - https://x.com/i/lists/2091834809903407159
2. Tech - https://x.com/i/lists/…
```

`settings.md` loses `x_list_url` (it moves to `sources.md`). `x_account` stays:
it is which login is allowed, not what is read.

## What changes in code

1. **`ybs_run.py read_sources`** becomes section-aware: lines under
   `## X lists` are not news sources and are never screened. A new
   `read_x_lists(root)` returns `[{name, slug, url}]`, and `ybs_run.py sources`
   prints both halves. Same shape of line, same forgiving parser.
2. **`x_scrape.py`** loops `scrape()` over the lists instead of calling it once.
   Per list: the same window and stop rules, the same guardrail (the browser
   must be on that list's URL and on @EgoismoEfficace, or the run stops).
   Between lists the browser navigates; nothing else changes in the page work.
3. **Dedupe across lists.** One tweet seen in two lists is one record. Its
   `list` field stays the first list that showed it (so nothing downstream
   breaks) and a new `lists` field carries every list it appeared in.
4. **`tweets.json` head.** `list_url` (one string) becomes `lists`
   (`[{name, url, tweets}]`). `account`, `scraped_at`, `window_hours` and
   `tweets` are unchanged. `page.txt` stays, and per-list text is saved beside
   it as `pages/<slug>.txt`, so a figure can still be traced to the page it
   came from.
5. **`x_score.py`** counts distinct lists from the new `lists` field, so a
   subject carried in two lists counts as two, not one. The hard-coded
   `"list": "B"` in `x_scrape.py` goes away.
6. **`x_checks.py`**: check 1 requires `lists` instead of `list_url` and that
   every tweet's `list` names one of them; check 2 applies the window rule per
   list, not to the merged pile.
7. **`x_wait_minutes_max`** stops being a speed target. It stays only as a
   safety timeout so a stuck browser cannot hang the brief forever, is raised
   to 30, and says so in its own row.

## Tests

- `read_sources` ignores the X section; `read_x_lists` reads it; a file with no
  X section is not an error (the X half then has nothing to do and says so).
- Two-list fixture: a tweet in both lists appears once, with both names.
- Per-list window: an old tweet in list two does not cut list one short.
- check 1 and check 2 on the new head, both pass and both fail for the right
  reason.
- The existing single-list fixture keeps passing, converted to the new head.

## Risks

- **The browser loop is the only part these tests cannot prove.** Navigating
  between lists, and the guardrail firing on the second list, need one live run
  with his session. That is the acceptance test, not a unit test.
- A tweet's `list` field is used by prompts as evidence; keeping it a single
  name (first seen) means no prompt has to change.
