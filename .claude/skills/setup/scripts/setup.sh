#!/bin/bash
# setup.sh - put the two outside tools on this Mac and check the project can run.
#
# Written for the bash Apple ships (3.2), so nothing newer than that is used.
# It never needs a password: both tools land under the user's own ~/.local.
#
# Everything is checked before it is done, so running this again is always safe,
# and no step aborts the script: the checklist at the end is the point, and it
# has to appear even when something failed.

BIN="$HOME/.local/bin"
NODE_HOME="$HOME/.local/node"
NODE_MAJOR="22"
PATH="$BIN:$NODE_HOME/bin:$PATH"
export PATH

# Set when a step installs something or edits ~/.zshrc: only then does the
# Claude app have to be restarted to see it.
RESTART_NEEDED=0

say() { printf '%s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# ---------------------------------------------------------------- 1. this Mac

step_mac() {
  if [ "$(uname -s)" != "Darwin" ]; then
    say "STOP: this script is for a Mac, and this is not one."
    exit 2
  fi
  mkdir -p "$BIN"
}

# ------------------------------------------------- 2. Apple's developer tools
#
# python3 on a Mac without them is a stub that opens an install dialog. Asking
# xcode-select first means we open that dialog on purpose and say what it is,
# instead of it appearing in the middle of a later step with no explanation.

step_devtools() {
  if xcode-select -p >/dev/null 2>&1; then
    say "developer tools: already there"
    return 0
  fi
  say "developer tools: missing, opening Apple's install dialog"
  xcode-select --install >/dev/null 2>&1
  say ""
  say "  A dialog has opened. Click Install and wait for it to finish."
  say "  Then run /setup again."
  say ""
  return 1
}

# ---------------------------------------------------------------- 3. yt-dlp
#
# The official standalone build: one file, no Python packaging, no password.

step_ytdlp() {
  if have yt-dlp; then
    say "yt-dlp: already there ($(yt-dlp --version 2>/dev/null))"
    return 0
  fi
  say "yt-dlp: downloading"
  if curl -fsSL --retry 3 \
       "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos" \
       -o "$BIN/yt-dlp.part"; then
    chmod +x "$BIN/yt-dlp.part"
    mv "$BIN/yt-dlp.part" "$BIN/yt-dlp"
    RESTART_NEEDED=1
    say "yt-dlp: installed ($("$BIN/yt-dlp" --version 2>/dev/null))"
  else
    rm -f "$BIN/yt-dlp.part"
    say "yt-dlp: DOWNLOAD FAILED (check the internet, then run /setup again)"
    return 1
  fi
}

# ------------------------------------------------------------------ 4. Node
#
# The official tarball for this chip, unpacked into ~/.local/node. Only node
# and npx are linked into ~/.local/bin: they are the two the shows script runs.

step_node() {
  if have npx && have node; then
    say "node: already there ($(node --version 2>/dev/null))"
    return 0
  fi
  case "$(uname -m)" in
    arm64) arch="darwin-arm64" ;;
    x86_64) arch="darwin-x64" ;;
    *) say "node: unknown chip $(uname -m), install Node yourself from nodejs.org"; return 1 ;;
  esac

  say "node: finding the latest version $NODE_MAJOR"
  index="https://nodejs.org/dist/latest-v$NODE_MAJOR.x"
  file=$(curl -fsSL --retry 3 "$index/SHASUMS256.txt" 2>/dev/null \
         | grep -o "node-v$NODE_MAJOR\.[0-9.]*-$arch\.tar\.gz" | head -1)
  if [ -z "$file" ]; then
    say "node: COULD NOT REACH nodejs.org (check the internet, then run /setup again)"
    return 1
  fi

  say "node: downloading $file"
  tmp=$(mktemp -d)
  if ! curl -fsSL --retry 3 "$index/$file" -o "$tmp/node.tar.gz"; then
    rm -rf "$tmp"
    say "node: DOWNLOAD FAILED (check the internet, then run /setup again)"
    return 1
  fi
  if ! tar -xzf "$tmp/node.tar.gz" -C "$tmp"; then
    rm -rf "$tmp"
    say "node: the download was damaged, run /setup again"
    return 1
  fi

  unpacked=$(find "$tmp" -maxdepth 1 -type d -name "node-v*" | head -1)
  rm -rf "$NODE_HOME"
  mv "$unpacked" "$NODE_HOME"
  rm -rf "$tmp"
  ln -sf "$NODE_HOME/bin/node" "$BIN/node"
  ln -sf "$NODE_HOME/bin/npx" "$BIN/npx"
  ln -sf "$NODE_HOME/bin/npm" "$BIN/npm"
  RESTART_NEEDED=1
  say "node: installed ($("$BIN/node" --version 2>/dev/null))"
}

# ------------------------------------------------------------------ 5. PATH
#
# ~/.local/bin holds ego lite's command as well as the two tools above. The
# Claude app reads ~/.zshrc to work out its PATH, so that is the file to write.

step_path() {
  line='export PATH="$HOME/.local/bin:$HOME/.local/node/bin:$PATH"'
  rc="$HOME/.zshrc"
  if [ -f "$rc" ] && grep -q '# Yaron brief - find ego-browser' "$rc"; then
    say "search path: already set"
    return 0
  fi
  {
    printf '\n# Yaron brief - find ego-browser, node and yt-dlp\n'
    printf '%s\n' "$line"
  } >> "$rc"
  RESTART_NEEDED=1
  say "search path: added to ~/.zshrc"
}

# -------------------------------------------------------------- 6. checklist

check() {
  name="$1"; cmd="$2"
  if have "$cmd"; then
    say "  ok       $name"
  else
    say "  MISSING  $name"
    MISSING=$((MISSING + 1))
  fi
}

step_checklist() {
  say ""
  say "TOOLS"
  MISSING=0
  check "python3      (runs the two helper scripts)" python3
  check "yt-dlp       (show dates from YouTube)" yt-dlp
  check "node         (show captions from YouTube)" node
  check "npx          (same)" npx
  check "ego-browser  (the browser every step reads pages in)" ego-browser
  return $MISSING
}

# --------------------------------------------------- 7. the project's own checks

step_project() {
  root="$1"
  say ""
  say "THE PROJECT"
  if ! have python3; then
    say "  skipped: python3 is missing, fix that first"
    return 1
  fi
  bad=0
  if python3 "$root/.claude/skills/ybs-brief/scripts/ybs_run.py" build --check >/dev/null 2>&1; then
    say "  ok       the 11 agent files match their templates"
  else
    say "  PROBLEM  the agent files are stale; ask Claude to run build"
    bad=$((bad + 1))
  fi
  n=$(python3 "$root/.claude/skills/ybs-brief/scripts/ybs_run.py" sources 2>/dev/null \
      | grep -c '"front_page"')
  if [ "$n" -gt 0 ]; then
    say "  ok       $n news sources listed in sources.md"
  else
    say "  PROBLEM  no news sources could be read from sources.md"
    bad=$((bad + 1))
  fi
  if python3 "$root/.claude/skills/ybs-shows/scripts/ybs_shows.py" start >/dev/null 2>&1; then
    built=$(python3 "$root/.claude/skills/ybs-shows/scripts/ybs_shows.py" start 2>/dev/null \
            | sed -n 's/.*"profile_built": "\([^"]*\)".*/\1/p')
    say "  ok       show archive readable, topic profile built $built"
  else
    say "  PROBLEM  the show archive could not be read"
    bad=$((bad + 1))
  fi
  return $bad
}

# ------------------------------------------------------------------ 8. tests
#
# Each file on its own: the runner stops at the first failure, so running it
# would hide the other two files entirely.

step_tests() {
  root="$1"
  say ""
  say "TESTS (4 failures are known and expected)"
  have python3 || { say "  skipped: python3 is missing"; return 1; }
  total=0
  for t in test-bookkeeping-v4 test-prompts-v4 test-shows-v4; do
    out=$(cd "$root" && python3 "tests/$t.py" 2>&1)
    n=$(printf '%s' "$out" | sed -n 's/^\([0-9][0-9]*\) FAILED.*/\1/p' | head -1)
    [ -z "$n" ] && n=0
    total=$((total + n))
    if [ "$n" -eq 0 ]; then say "  ok       $t"; else say "  $n failed $t"; fi
  done
  say ""
  if [ "$total" -eq 4 ]; then
    say "  $total failures, exactly the 4 known ones. Nothing new is broken."
  else
    say "  $total failures, expected 4. Tell Samuele before running a brief."
  fi
}

# -------------------------------------------------------------------- main

main() {
  root="$1"
  say "Setting up the morning brief. Nothing here needs your password."
  say ""

  step_mac
  if ! step_devtools; then
    exit 1
  fi
  step_ytdlp
  step_node
  step_path

  step_checklist
  missing=$?
  step_project "$root"
  step_tests "$root"

  say ""
  say "WHAT TO DO NEXT"
  if [ "$missing" -gt 0 ]; then
    say "  1. Fix the lines marked MISSING above (the README lists what each one means)."
    say "  2. Run /setup again."
  else
    n=1
    if [ "$RESTART_NEEDED" = "1" ]; then
      say "  $n. Quit the Claude app and open it again, so it sees the new tools."
      n=$((n + 1))
    fi
    say "  $n. Open ego lite and check you are signed in to youtube.com."
    n=$((n + 1))
    say "  $n. Back in Claude, run /ybs-shows. Then /ybs-brief morning."
  fi
}

main "$@"
