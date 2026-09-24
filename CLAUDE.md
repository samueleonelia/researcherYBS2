# researcherYBS2

## What this is
A Claude Code project that builds Yaron Brook's morning news brief (plus afternoon/evening updates) and keeps a profile of his show's recent topics. Ships as an installable package for Yaron himself (see README.md's "Install" section): he downloads a zip, opens it in the Claude app, and runs `/setup`.

## Relationship to researcherYBS
This is the active successor to the sibling repo `../researcherYBS/`. Evidence found in this repo:
- DEVLOG.md (2026-09-01): calls a file that "lives only in the old `researcherYBS` folder" stale.
- DEVLOG.md (2026-09-05): confirms "the old `researcherYBS` folder is separate and untouched" while renaming this repo's skill folder from `ybs-brief-v4` to `ybs-brief`.
- researcherYBS still carries older `ybs-brief-v3` / `ybs-brief-v4` skills; this repo has the current single `ybs-brief`.
- Per the parent `yaronBrook/CLAUDE.md`: researcherYBS's last commit is 2026-09-01 with no GitHub remote; this repo's last commit is 2026-09-12 with a remote configured (`github.com/samueleonelia/researcherYBS2`, private).

## What's inside
- `.claude/skills/`: `ybs-brief` (morning/afternoon/evening news brief, includes its own X-list engine), `ybs-shows` (refreshes the show transcript archive and topic profile), `setup` (installs yt-dlp/Node, checks the project), `update` (pulls the newest GitHub zip, preserves `briefs/`, `shows/`, and the user's edited `preferences.md`).
- `briefs/`: one dated folder per brief run, each with `brief.md`.
- `shows/`: transcript archive and `profile.json` topic profile, built by `/ybs-shows`.
- `preferences.md`, `sources.md`, `settings.md`: the three user-editable config files (brief preferences, news sources + X lists, numeric settings/models per stage).
- `tests/`: `run-all.sh` and the test suites `/setup` checks against.
- No `AGENTS.md` or `CLAUDE.local.md` in this repo.

## Tools and connectors
None configured for this folder in `~/.claude.json`. The brief work runs through the `ego-browser` skill (ego lite, signed into YouTube) rather than an MCP connector.

## Rules
- Currently on `main`, tag `v4.4-x-lane`, pushed. Treat `main` as the version `/update` distributes to Yaron — verify tests before pushing.
- Known test failures are pre-existing and named in STATUS.md/DEVLOG.md (`picks-sync` >15 refusal, `SKILL.md`'s hard-coded number, a beat-vs-topic check); `/setup` reports only a *new* failure as something to flag.
- `/update` must never overwrite `preferences.md`, `briefs/`, or `shows/`.

## Remember
<!-- Things Samuele explicitly asked Claude to remember for this project. Claude adds items here when told "remember X". -->
