#!/usr/bin/env zsh
# Every v4 test, from the project root. Any failure stops the run.
set -e
cd "$(dirname "$0")/.."
python3 tests/test-bookkeeping-v4.py
python3 tests/test-prompts-v4.py
python3 tests/test-shows-v4.py
echo "all v4 tests passed"
