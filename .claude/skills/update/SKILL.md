---
name: update
description: Update this project to the newest version published on GitHub, keeping the user's own briefs and show archive untouched and backing up the two files they are allowed to edit. Use when the user asks for the latest version, when Samuele says an update is ready, or when the user types /update. Downloads a zip, does not use git, and never sends anything anywhere.
argument-hint: ""
---

# /update — get the newest version of the project

One command does the work. You run it and report what it printed.

```bash
bash .claude/skills/update/scripts/update.sh "$(pwd)"
```

Run it from the project folder, so `$(pwd)` is the folder holding `sources.md`.

## What it does

Downloads the newest zip from GitHub and replaces the project's files with it.

Three things are never overwritten:

- `runs/` — every brief ever made here
- `shows/` — the transcripts, digests and topic profile
- `sources.md` and the two `settings.md` files — if the user's copy differs from
  the new one, the script writes the new one and keeps theirs alongside as
  `<name>.backup`, and says so.

## What you do with the output

Report what changed, in the script's own words. If it kept a `.backup`, say
which file and that their old version is beside it, so they can compare the two
or ask you to put theirs back.

If the download failed, say so. Nothing was changed in that case.

After a successful update, tell the user to run `/setup` once, because a new
version may need a tool they do not have yet.

## Rules

1. **Run the script; do not do its job yourself.** Never download files another
   way, never copy them by hand, never merge two versions of a file yourself.
2. **Never touch `runs/` or `shows/`.**
3. If the script reports a problem, report the problem. Do not retry silently.
