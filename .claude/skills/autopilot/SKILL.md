---
name: autopilot
description: Set up the automatic briefs on this Mac, once. Checks that Gmail and Google Drive are connected, lets their tools run without a prompt, agrees the four daily times with the user, creates (or updates) the four scheduled tasks that run /ybs-daily, and sends one test email. Use when the user types /autopilot, wants the briefs to arrive by email by themselves, or wants to change their times or switch one off. Run it again at any time to change the schedule; it never makes a task twice.
argument-hint: ""
---

# /autopilot — the briefs run by themselves

Run once, by the user, in the Claude app's **Code** tab, from the project
folder. After it, every brief runs on a schedule on this Mac and arrives in
the user's Gmail as an email, unread, with the brief saved to their Google
Drive. The scheduled tasks live on this Mac, not in the project, which is why
`/update` cannot install them and this skill exists.

Speak to the user plainly: short sentences, no file names they do not need.

## Step 1 — the right folder

```bash
pwd && ls sources.md
```

A scheduled task runs in the folder this session is in. If `sources.md` is not
there, stop: tell the user to open the project folder (the one holding
`sources.md`) in the Code tab and run `/autopilot` again. Keep the `pwd`: it
goes into every task.

## Step 2 — Gmail and Google Drive

The connector tools may be deferred. Load them with ToolSearch: search
`gmail send message`, `gmail search threads`, `google drive create file` and
`drive search files`, and load what comes back. Find them by what they do,
exactly as `/ybs-daily` step 0 describes; never type a server id.

If either one is missing, stop and tell the user:

> In the Claude app: **Settings → Connectors**. Connect **Gmail** and
> **Google Drive**, both with the same Google account. Then come back here
> and type `/autopilot` again.

## Step 3 — let the two connectors run unattended

A scheduled run has nobody to click "Allow". The app's own "Always allow"
switch for a connector resets after every app update, so it cannot be
trusted with a run at five in the morning. A permission rule in the
project's `.claude/settings.local.json` survives app updates and `/update`
alike.

A tool is named `mcp__<server>__<tool>`. Take the two server ids from this
session's own tool names: the Gmail server's and the Drive server's. Then
read `.claude/settings.local.json` if it exists, and write it back with these
two entries in `permissions.allow`:

```
mcp__<gmail server>__*
mcp__<drive server>__*
```

Then the permission mode. Scheduled runs use the **default** mode, not the
one picked in a chat's mode menu. A rule can only allow a command it names,
and a brief runs hundreds of steps: one worded a little differently from its
rule, and a run that started at five in the morning waits for a click until
someone comes. Auto mode avoids that: Claude's own safety check approves
routine steps and still stops risky ones.

Read `permissions.defaultMode` in `.claude/settings.local.json`, then in
`~/.claude/settings.json`; the first one set wins. If it is `auto`, say so in
one line and go on. If not, ask the user with AskUserQuestion, in plain words:
the scheduled briefs need auto mode as this folder's default; it applies to
this project folder only, and sessions here will ask less. Two answers:

- **Turn it on:** set `permissions.defaultMode` to `auto` in this project's
  `.claude/settings.local.json`.
- **Not now:** change nothing, and tell them the scheduled runs may stop on
  an "Allow" prompt; step 6 will show it.

Only the user's answer turns it on; never set it without asking.

Keep every key and every entry already in the file. Add an entry only if it
is not there yet. Never touch `.claude/settings.json`: that one ships with
the project, and `/update` replaces it.

## Step 4 — the times

Show the user the schedule, in this Mac's own time, every day:

| Job | Time | What arrives |
|---|---|---|
| shows | 02:00 | nothing, unless it fails: it refreshes what the show has been arguing about |
| morning | 05:30 | the morning brief, about three quarters of an hour later |
| afternoon | 13:00 | what changed since the morning |
| evening | 19:00 | the good news of the day |

Ask with AskUserQuestion whether to keep these times, or change one, or
switch one off. When they change something, show the table again and ask
once more, until they say it is right.

Say this when it applies, once:

- The afternoon and the evening are built on that day's morning brief.
  Switching the morning off means they fail every day: switch them off too.
- The shows job feeds the morning. Keep it earlier than the morning.

## Step 5 — the scheduled tasks

Load the scheduled-tasks tools with ToolSearch (`scheduled task`), then call
the list tool first. A task this project made before has one of these ids:

| Job | taskId | title |
|---|---|---|
| shows | `ybs-daily-shows` | YBS shows refresh |
| morning | `ybs-daily-morning` | YBS morning brief |
| afternoon | `ybs-daily-afternoon` | YBS afternoon update |
| evening | `ybs-daily-evening` | YBS evening report |

The app keeps each task on the Mac as a skill file named by its id, so an id
never repeats the name of a skill in this project: a task called `ybs-shows`
could stand in for the real `/ybs-shows`.

For each job:

- **On, and no task yet:** create it, with the taskId and title above,
  `cronExpression` = `<minute> <hour> * * *` in local time (05:30 is
  `30 5 * * *`), `notifyOnCompletion: false`, a one-line `description`, and
  this prompt, with `<pwd>` and `<slot>` filled in:

  ```
  Project folder: <pwd>
  Work in that folder; change into it first if this session is not already there.
  Invoke the ybs-daily skill with the argument <slot>. If the Skill tool does not
  list ybs-daily, read <pwd>/.claude/skills/ybs-daily/SKILL.md and follow it with
  that argument. Do not do anything else.
  ```

- **On, and the task exists:** update it with the same `cronExpression`,
  prompt and `enabled: true`. Never create a second one.
- **Off, and the task exists:** update it with `enabled: false`.
- **Off, and no task:** nothing.

The slot of the shows task is `shows`. Then call the list tool again and
check every task is there with the right time and the right on or off.

## Step 6 — the test run

Prove it on this Mac the way the briefs will run: a scheduled task, with
nobody at the keyboard. Never send the test email from this session: a send
from here proves nothing about a run at five in the morning.

The time two minutes from now, with its offset:

```bash
python3 -c "from datetime import datetime,timedelta;print((datetime.now().astimezone()+timedelta(minutes=2)).replace(microsecond=0).isoformat())"
```

A task with id `ybs-daily-test` may exist from an earlier `/autopilot`
(the list in step 5 shows it). If it does, update it with that `fireAt`.
If not, create it: taskId `ybs-daily-test`, title `YBS test email`,
`fireAt` that time, `notifyOnCompletion: false`, a one-line description, and
the prompt of step 5 with the slot `test`. It runs once and switches itself
off.

Tell the user: in about three minutes an email titled `YBS autopilot: test
email` arrives, from a run nobody is watching, and it goes to the address
every brief will go to. Then ask with AskUserQuestion whether it arrived in
their inbox, unread:

- **Yes:** good, go on.
- **Arrived, but already read:** a Gmail filter is marking mail they send
  themselves as read. In Gmail: **Settings → See all settings → Filters and
  Blocked Addresses**, and look for a filter on their own address that marks
  as read. Remove that action, or every brief will arrive read.
- **Not there:** check Spam and wait a minute. Then call the run list for
  `ybs-daily-test`. A run still `running` with no activity for minutes is
  waiting for an "Allow" click: tell the user to open **Scheduled → YBS test
  email** in the sidebar, approve what it asks, and type `/autopilot` again.
  A run that `failed`: say its error and stop.

## Step 7 — what the user keeps doing

Tell them, plainly:

1. **Keep the Claude app open.** The tasks run only while it is. A run missed
   while it was closed runs as soon as it opens again.
2. **Keep the Mac awake and plugged in.** **System Settings → Battery →
   Options**: turn on "Prevent automatic sleeping on power adapter when the
   display is off". (A Mac with no battery: **System Settings → Energy**,
   "Prevent automatic sleeping when the display is off".) The screen may
   still turn off.
3. **ego lite stays signed in**, as for any brief.
4. **To change a time or switch a job off**, type `/autopilot` again.

---

## Hard rules

1. **Run from the project folder.** The tasks run where this session runs.
2. **Never type a server id.** Read both from this session's own tool names.
3. **Never drop anything from `settings.local.json`.** Add the two entries,
   and auto mode only when the user says yes; keep the rest.
4. **Never make a task twice.** List first; update what exists.
5. **The test email is sent by the scheduled test run, never by this
   session,** to the user's own address, once.
6. **The task prompt only names `/ybs-daily`.** Everything a run does lives
   in the project, so `/update` can fix it; nothing else goes in the prompt.
7. **Never start a brief here.** This skill sets things up; the tasks run
   the briefs.
