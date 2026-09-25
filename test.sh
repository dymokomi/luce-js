#!/bin/sh
# Run every test of luce-js: the unit tests of each module, then QuickJS's own JavaScript
# tests through the ljs runner (tests/run.py). Stops at the first failing step.
set -e
cd "$(dirname "$0")"

for module in cutils dtoa engine host; do
    echo "== luce-base test src/luce_js/$module"
    luce-base test "src/luce_js/$module"
done

echo "== tests/run.py"
python3 tests/run.py "$@"
