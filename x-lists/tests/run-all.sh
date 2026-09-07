#!/usr/bin/env bash
# Every x-lists test, from x-lists/. Runs each file, reports pass/fail per
# file, and exits non-zero if any failed. Never touches the root tests/.
set -u
cd "$(dirname "$0")/.."

tests=(
  tests/test_settings.py
  tests/test_checks.py
  tests/test_chain.py
  tests/test_check10.py
)

failed=0
for t in "${tests[@]}"; do
  echo "== $t =="
  if python3 "$t"; then
    echo "-- PASS: $t"
  else
    echo "-- FAIL: $t"
    failed=1
  fi
  echo
done

if [ "$failed" -eq 0 ]; then
  echo "all x-lists tests passed"
else
  echo "x-lists tests FAILED"
fi
exit $failed
