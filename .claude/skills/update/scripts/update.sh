#!/bin/bash
# update.sh - replace this project's files with the newest published version.
#
# A zip, not git: the project is installed as a plain folder, and git would also
# make the Claude app work on a private copy in extra sessions.
#
# Written for the bash Apple ships (3.2). Nothing here needs a password.

ZIP="https://github.com/samueleonelia/researcherYBS2/archive/refs/heads/main.zip"

# The user's own work. Never replaced, never read, never deleted.
KEEP_DIRS="runs shows"

# The files the user is allowed to edit. The new version wins, but their copy
# is kept beside it, so an edit is never silently lost.
KEEP_BACKUP=".claude/skills/ybs-brief/settings.md
.claude/skills/ybs-shows/settings.md
sources.md"

say() { printf '%s\n' "$1"; }

main() {
  root="$1"
  if [ ! -f "$root/sources.md" ]; then
    say "STOP: $root does not look like the project (no sources.md)."
    exit 2
  fi

  say "Downloading the newest version."
  tmp=$(mktemp -d) || { say "STOP: could not make a temporary folder."; exit 2; }
  if ! curl -fsSL --retry 3 "$ZIP" -o "$tmp/main.zip"; then
    rm -rf "$tmp"
    say "DOWNLOAD FAILED. Nothing was changed. Check the internet and try again."
    exit 1
  fi
  if ! unzip -q "$tmp/main.zip" -d "$tmp"; then
    rm -rf "$tmp"
    say "The download was damaged. Nothing was changed. Try again."
    exit 1
  fi
  new=$(find "$tmp" -maxdepth 1 -type d -name "researcherYBS2-*" | head -1)
  if [ -z "$new" ] || [ ! -f "$new/sources.md" ]; then
    rm -rf "$tmp"
    say "The download did not contain the project. Nothing was changed."
    exit 1
  fi

  # The files the user may edit: compare first, so we only speak up on a real
  # difference. Their copy is moved aside before the new one lands on it.
  backed_up=""
  for f in $KEEP_BACKUP; do
    if [ -f "$root/$f" ] && [ -f "$new/$f" ]; then
      if ! cmp -s "$root/$f" "$new/$f"; then
        cp "$root/$f" "$root/$f.backup"
        backed_up="$backed_up $f"
      fi
    fi
  done

  # Copy everything except the user's own folders. -R over the top: files that
  # only exist here (their notes, an old plan) are left alone.
  say "Replacing the project files."
  for item in "$new"/* "$new"/.[!.]*; do
    [ -e "$item" ] || continue
    name=$(basename "$item")
    skip=0
    for k in $KEEP_DIRS; do [ "$name" = "$k" ] && skip=1; done
    [ "$skip" -eq 1 ] && continue
    cp -R "$item" "$root/"
  done

  # shows/ is kept whole, but a new version may ship new digests, and those are
  # part of the code, not of his archive. Only files he does not have are added.
  if [ -d "$new/shows/digests" ]; then
    mkdir -p "$root/shows/digests"
    added=0
    for d in "$new"/shows/digests/*.md; do
      [ -e "$d" ] || continue
      if [ ! -f "$root/shows/digests/$(basename "$d")" ]; then
        cp "$d" "$root/shows/digests/"
        added=$((added + 1))
      fi
    done
    [ "$added" -gt 0 ] && say "Added $added new show summaries."
  fi

  rm -rf "$tmp"

  say ""
  say "DONE. Your briefs in runs/ and your show archive in shows/ were not touched."
  if [ -n "$backed_up" ]; then
    say ""
    say "These files had your own changes in them. The new version is now in place,"
    say "and your old copy is beside it, ending in .backup:"
    for f in $backed_up; do say "  $f"; done
    say "Ask Claude to compare them if you want your changes back."
  fi
  say ""
  say "Now run /setup once: a new version may need a tool you do not have yet."
}

main "$@"
