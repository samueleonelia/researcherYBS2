---
name: setup
description: Install the two outside tools the morning brief needs (yt-dlp and Node) into the user's own folder, then check that this project can run: the tools, the agent files, the news sources, the show archive and the tests. Use when setting this project up on a new Mac, when a run says a tool is missing, or when the user types /setup. Needs no password, installs nothing system-wide, and changes no file in this project.
argument-hint: ""
---

# /setup — make this Mac ready to run the brief

One command does the work. You run it and report what it printed.

```bash
bash .claude/skills/setup/scripts/setup.sh "$(pwd)"
```

Run it from the project folder, so `$(pwd)` is the folder holding `sources.md`.

## What it does

Installs `yt-dlp` and Node into `~/.local`, adds that folder to the search path
in `~/.zshrc`, then prints three lists: the tools, the project's own checks, and
the tests. It needs no password and touches no file inside this project.

Everything is checked before it is done, so running it twice is safe, and no
failure stops it: the checklist at the end is the point.

## What you do with the output

Show the user the whole checklist, exactly as the script printed it, and then
say in one sentence whether they are ready. Do not summarise the lines away:
the `ok` / `MISSING` column is what they act on.

Three answers need a word from you:

- **The developer-tools dialog opened.** The script stopped on purpose. Tell the
  user to click Install in that dialog, wait for it, then run `/setup` again.
- **A line says MISSING.** Say which one and what it means, from the README's
  troubleshooting list. Do not try to install it another way.
- **The tests report a number other than 4.** Say so plainly and tell the user
  not to run a brief until Samuele has looked at it.

## Rules

1. **Run the script; do not do its job yourself.** Never install a tool with
   another command, never edit `~/.zshrc` yourself, never work around a failure.
2. **Never change a file in this project** to make a check pass.
3. **Report the checklist verbatim.** It is a list of facts about their Mac.
4. If the script says a step failed, the honest answer is that it failed.
