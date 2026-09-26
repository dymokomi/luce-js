#!/bin/sh
# Run every test of luce-js: the unit tests of each module, then QuickJS's own JavaScript
# tests through the ljs runner (tests/run.py). Stops at the first failing step.
set -e
cd "$(dirname "$0")"

# Every fragment is laid out as the pinned compiler's formatter lays it out (tests/repl.lucb is ljsc's output, compared as
# generated).
echo "== luce-base fmt --check"
for file in $(git ls-files '*.lucb' | grep -v '^tests/repl.lucb$'); do
    luce-base fmt "$file" --check > /dev/null || { echo "$file is not formatted (luce-base fmt $file --write)"; exit 1; }
done

for module in cutils dtoa engine host; do
    echo "== luce-base test src/luce_js/$module"
    luce-base test "src/luce_js/$module"
done

echo "== tests/run.py"
python3 tests/run.py "$@"

echo "== tests/tools.py"
python3 tests/tools.py
