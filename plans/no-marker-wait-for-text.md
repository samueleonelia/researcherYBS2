# Two changes: no login marker, and a reader that waits for text

_Written 2026-09-09 from Yaron's report of the same day: seven NYTimes reads
saved 0 characters twice each, and WSJ was stopped by a marker word that was
never on his page. Plan only: nothing here has been changed yet._

## The short version

1. **Remove the logged-in marker.** A sources.md line is a name and a link,
   nothing else. The screener runs the same command for every source and never
   decides whether a login is alive. A wrong marker stopped WSJ on a day the
   login was fine; the reader already notices a dead login where it matters, by
   reporting a truncated page.
2. **The reader waits for text before it copies the page.** Today it copies the
   moment the browser says "loaded". A site that runs a check before showing
   the article (NYT's "verify access") is blank at that moment, and the reader
   saves an empty file. The new rule is generic: check once a second until the
   page has text, up to a ceiling from settings.md, then copy. A page still
   blank at the ceiling is reported by name, `PAGE_BLANK`, and retried once
   like any other failed read.

Neither change names a site. Both hold for any source Yaron adds tomorrow.

Estimated work: about 2 hours, plus one replay of a single reader by hand and
one live run.

## Change 1 — the marker goes

### What exists

- `sources.md` lines 6–8 describe the third part.
- `ybs_run.py` `read_sources()` (about line 1561–1600) parses it into
  `marker`, defaulting to `FREE`; `start` copies it into `run.json` under
  `sources.<name>.marker` (line 1742); `fill screen` passes `MARKER` and
  `MARKER_JSON` into the prompt (lines 1352–1353); the sentinel table has
  `session_down` (line 243); `build_audit_line` counts `session_down` events
  as failures (line 3141).
- `prompts/screen.md` line 11 lists the marker as an input, lines 41–52 are
  the check, line 172 tells the screener what to do on `SESSION_DOWN`.
- `SKILL.md` lines 171–173 (no retry on `SESSION_DOWN`) and line 445 (same,
  in the rules list).
- Tests: `tests/test-prompts-v4.py` line 81 lists `MARKER` and `MARKER_JSON`
  among the placeholders `fill screen` must fill; `tests/test-bookkeeping-v4.py`
  lines 104–105 write a `SESSION_DOWN` screen file, line 1587 records a
  `SESSION_DOWN` event and expects it counted as a failure;
  `x-lists/tests/test_settings.py` line 126 has a Reason line with
  `- Sign Out` to prove the X parser skips the news section.

### What changes

**`sources.md`** — delete the paragraph at lines 6–8. The header says: one
line each, a name, then the link.

**`ybs_run.py`**
- `read_sources()`: the row has `name`, `slug`, `front_page` and no `marker`.
  A line with anything after the link is still read, because Yaron's copy will
  carry `- Sign Out` until he edits it, but the extra part is dropped and
  `start` prints one line: `sources.md: "WSJ" has a third part; it is no
  longer used, delete it`. That message comes from `read_sources` returning a
  list of notices beside the rows; `start` prints them. The docstring example
  loses its WSJ line.
- `start`: no `marker` key in `run.json`.
- `fill screen`: no `MARKER`, no `MARKER_JSON`.
- Sentinel table: `session_down` removed. `build_audit_line`: the
  `session_down` clause removed; `fail` in the type is the whole test.
- `read_x_lists` docstring: drop "minus the logged-in marker".

**`prompts/screen.md`** — remove the marker input line, the whole block
numbered 1 (the check), renumber 2 and 3 to 1 and 2, and remove the
`SESSION_DOWN` paragraph under Output.

**`SKILL.md`** — remove the `SESSION_DOWN` bullet at lines 171–173 and the
sentence at line 445.

**`README.md`** — the sources.md bullet under "Changing what it does" already
says one line each; add "a name and a link" so nobody looks for a third part.

**Tests**
- `test-prompts-v4.py`: drop `MARKER`, `MARKER_JSON` from the placeholder
  list; add a check that the rendered screen prompt contains neither
  `SESSION_DOWN` nor `marker`.
- `test-bookkeeping-v4.py`: the AP News screen file at lines 104–105 becomes
  `ok: false, error: "TIMEOUT"` so the "a failed screen has no links" branch
  is still exercised; line 1587's event becomes `screen_failed`, and the check
  text becomes "a failed screen counts as a failure". Add: `read_sources` on a
  line with a third part returns the row without it and one notice naming the
  source; a two-part line returns no notice.
- `x-lists/tests/test_settings.py` line 126: keep `- Sign Out` on the Reason
  line. It now proves the X parser ignores a stale third part too, and the
  test's purpose (news lines are skipped) is unchanged.

**Build** — `ybs_run.py build` regenerates `.claude/agents/ybs4-screener.md`
from its template; the template itself does not mention the marker, so no
edit there, only the rebuild.

## Change 2 — the reader waits for text

### What exists

`agents/reader.md.tmpl`, step 1, one command: open the tab with
`{ wait: true, timeout: 40 }`, read `document.body.innerText` once, save it,
log `chars`. Step 2 says a page under about 800 characters is `PAGE_TRUNCATED`.
`SKILL.md` step 6 (lines 278–291) says a `PAGE_TRUNCATED` reader writes no
note, so `read-list` offers the id again for its one retry, and a second miss
is retired with `event --type read_failed`.

### What changes

**`settings.md`** — one new row under "The article brief":
`read_wait_seconds | 10 | how long a reader waits for a blank page to show
text before giving up; a page with text is copied at once`. The settings
loader already exposes any row as `{{settings.<key>}}`; add the key to the
list of required keys if the loader keeps one.

**`agents/reader.md.tmpl`**, step 1 — the command becomes:

```bash
ego-browser nodejs <<'EOF'
const fs = await import('fs')
await useOrCreateTaskSpace('ybs read <id>')
await openOrReuseTab('<url>', { wait: true, timeout: 40 })
// "Loaded" is not "showing text". Some sites run a check before they draw the
// page and are blank for a second or two. Copy as soon as there is text; give
// up at the ceiling and say so.
let txt = '', waited = 0
for (;;) {
  txt = await js(String.raw`document.body ? document.body.innerText : ''`)
  if (txt.trim().length >= 800 || waited >= {{settings.read_wait_seconds}}) break
  await new Promise(r => setTimeout(r, 1000)); waited++
}
fs.writeFileSync('<run_dir>/pages/<id>.txt', txt)
const info = await pageInfo()
cliLog(JSON.stringify({ id: '<id>', chars: txt.length, waited, url: info.url, title: info.title }))
await completeTaskSpace('ybs read <id>', { keep: false })
EOF
```

800 is the same threshold step 2 already uses for "too short", so the loop
and the judgement agree. A page that has text at load costs zero extra seconds.

**`agents/reader.md.tmpl`**, step 2 — one new first bullet, before the three
truncation cases: if `chars` is under 800 after the wait, reply
`PAGE_BLANK: <the title the command printed>` and stop. It is the same failure
family as `PAGE_TRUNCATED` (no note, retried once), but it names a page that
never showed anything rather than one that showed too little, so the log tells
the two apart.

**`ybs_run.py`** — sentinel table gains `"blank": "PAGE_BLANK"`. `read-list`
needs nothing: it lists whatever has no note, which already covers this.

**`SKILL.md`** step 6 — the `PAGE_TRUNCATED` paragraph becomes "A reader that
replies `PAGE_TRUNCATED` or `PAGE_BLANK` ..." and one sentence: `PAGE_BLANK`
means the page never showed text within `read_wait_seconds`; the retry goes
through `read-list` exactly as for a truncated page, and the `read_failed`
detail carries the title the reader reported.

**Tests** — `test-prompts-v4.py`: the built reader agent contains
`read_wait_seconds`'s value and the word `PAGE_BLANK`; a settings file without
`read_wait_seconds` makes `build` fail with a message naming the key.

## Verification

1. `python3 .claude/skills/ybs-brief/scripts/ybs_run.py build`, then
   `tests/run-all.sh`. The suite's two known failures in picks-sync and the
   cluster example stay as they are; nothing new may fail.
2. `start --slot morning` on a scratch copy with a sources.md that still has
   `- Sign Out` on one line: the run starts, the notice is printed once, and
   `run.json` has no `marker`.
3. Reader command by hand, on this Mac, against one Guardian article and one
   NYT article: Guardian reports `waited: 0`; NYT reports either text with a
   small `waited`, or `PAGE_BLANK` with the title, never `chars: 0` silently.
4. One live `/ybs-brief morning`; the audit line shows no `session_down`, and
   any blank page is listed by name in the failures.

## What this does not do

- It does not detect a dead login at screening time. If a paid site logs
  Yaron out, the screener still lists its links and every read of them reports
  `PAGE_TRUNCATED`. The run's failure list shows that plainly, which is how the
  NYT problem was found. No count line, no threshold, no new alarm.
- It does not click through overlays. A cookie banner or subscribe box does
  not remove the article's text from the page, and the reader already reads
  around it. Only a page with no text at all gets the wait.
- It does not change screening speed or method: `browserFetch` of each link's
  head stays as it is.
