#!/usr/bin/env python3
"""Build the ljs runner and run QuickJS's own tests with it.

The tests are upstream's tests/*.js (copied into tests/js/, MIT, see tests/js/LICENSE),
run the way upstream's Makefile `test:` target runs them with qjs: one process per file,
from the repository root, `--std` for test_builtin.js. A file passes when ljs exits with
status 0.

Files that cannot pass yet are listed in KNOWN_FAILURES with the reason; they are
reported as XFAIL and do not fail the run. A known failure that passes is reported as
XPASS so that its entry can be removed. Any other failure fails the run.

Usage: tests/run.py [--no-build] [--timeout SECONDS] [test_name ...]
"""

import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LJS = os.path.join(ROOT, "build", "ljs")

# (file, extra ljs options), in the order of upstream's Makefile. test_worker.js needs
# os.Worker, which the host does not port.
TESTS = [
    ("test_closure.js", []),
    ("test_language.js", []),
    ("test_builtin.js", ["--std"]),
    ("test_loop.js", []),
    ("test_bigint.js", []),
    ("test_cyclic_import.js", []),
    ("test_std.js", []),
    ("test_rw_handler.js", []),
]

# file -> why it cannot pass yet. Keep the classification: (a) needs an unported region,
# (b) a port bug, (c) a compiler bug, (d) a host feature deliberately not ported.
KNOWN_FAILURES = {
}


def build():
    print("building build/ljs ...", flush=True)
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    result = subprocess.run(["luce-base", "build", "tests/ljs.lucb", "-o", LJS], cwd=ROOT)
    if result.returncode != 0:
        print("FAIL: cannot build ljs")
        sys.exit(1)


def first_error_line(output):
    """The first line that says what went wrong: a trap, an exception or an assertion."""
    lines = [line for line in output.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("trap:") or "Error" in line or "assertion" in line or "exception" in line:
            return line.strip()
    return lines[0].strip() if lines else ""


def run_test(name, options, timeout):
    path = os.path.join("tests", "js", name)
    command = [LJS] + options + [path]
    started = time.time()
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout}s", time.time() - started
    output = result.stdout + result.stderr
    if result.returncode == 0:
        return True, "", time.time() - started
    reason = first_error_line(output)
    if result.returncode < 0:
        reason = f"killed by signal {-result.returncode}: {reason}"
    return False, reason, time.time() - started


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-build", action="store_true", help="use the existing build/ljs")
    parser.add_argument("--timeout", type=int, default=600, help="seconds per test file")
    parser.add_argument("tests", nargs="*", help="run only these test files")
    args = parser.parse_args()

    if not args.no_build:
        build()

    selected = [t for t in TESTS if not args.tests or t[0] in args.tests
                or t[0].removesuffix(".js") in args.tests]
    counts = {"PASS": 0, "FAIL": 0, "XFAIL": 0, "XPASS": 0}
    for name, options in selected:
        passed, reason, seconds = run_test(name, options, args.timeout)
        known = KNOWN_FAILURES.get(name)
        if passed:
            status = "XPASS" if known else "PASS"
        else:
            status = "XFAIL" if known else "FAIL"
        counts[status] += 1
        line = f"{status:5}  {name:24} {seconds:6.1f}s"
        if reason:
            line += f"  {reason}"
        print(line, flush=True)
        if status == "XFAIL":
            print(f"{'':7}known: {known}")
        elif status == "XPASS":
            print(f"{'':7}passes now: remove it from KNOWN_FAILURES")

    print(f"\n{len(selected)} files: {counts['PASS']} passed, {counts['FAIL']} failed, "
          f"{counts['XFAIL']} known failures, {counts['XPASS']} unexpected passes")
    sys.exit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()
