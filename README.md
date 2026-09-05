# Yaron Brook morning brief

Two skills that build the morning news brief, and two that keep the setup working.

- `/ybs-brief morning` — reads the day's news and writes the brief
- `/ybs-shows` — refreshes what the show has been arguing about lately
- `/setup` — installs the tools this needs, and checks everything works
- `/update` — gets the newest version of this project

## Install (once)

1. Download the project: <https://github.com/samueleonelia/researcherYBS2/archive/refs/heads/main.zip>
2. Double-click the zip in Downloads. Drag the folder into your home folder (the one
   with your name) and rename it `researcherYBS2`.
3. Open the Claude app, **Code** tab, **Local**, **Select folder**, pick that folder.
   Say yes to "trust this folder".
4. Type `/setup` and send. Answer yes when Claude asks to run a command.
5. Quit the Claude app and open it again.

The ego lite browser must be installed and signed in to YouTube. `/setup` will tell you
if it cannot find it.

## Every morning

Open the Claude app, Code tab, the project folder. A fresh chat is fine.

1. `/ybs-shows` — usually answers in a minute that nothing changed
2. `/ybs-brief morning` — takes 20 to 30 minutes

The brief lands in `runs/`, in a folder named for today, as `brief.md`. Claude prints
the exact path when it finishes.

ego lite has to be open while a brief runs.

## Changing what it does

Two files are yours to edit:

- `sources.md` — which news sites are read
- `.claude/skills/ybs-brief/settings.md` — how many stories reach the brief, and more

`/update` may replace them with a newer version. When it does, it keeps your copy
beside it ending in `.backup` and says so.

## Getting the newest version

Type `/update`, then `/setup`. Your briefs in `runs/` and your show archive in
`shows/` are never touched.

## When something is wrong

- **`/setup` is not in the `/` list** — the wrong folder is open. Pick the folder that
  contains `sources.md`.
- **A dialog about "command line developer tools"** — click Install, wait, `/setup` again.
- **`ego-browser MISSING`** — open ego lite and finish its first-run setup, then `/setup`.
- **`yt-dlp` or `node MISSING`** — the download failed. Check the internet, `/setup` again.
- **Tools say ok but a run cannot find them** — quit and reopen the Claude app.
- **A YouTube sign-in or bot-check error** — sign in to youtube.com inside ego lite.
- **A run stops saying the usage limit is reached** — that is the Claude plan, not this
  project. Upgrade, then run it again from the start.

`/setup` reports 4 failing tests. That is expected and known.
