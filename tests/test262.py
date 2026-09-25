#!/usr/bin/env python3
"""Fetch test262, build the luce-js test262 runner and run the suite.

The runner is tests/run_test262/, a port of QuickJS's run-test262.c. This script does what
upstream's Makefile targets test2-bootstrap and test2 do:

  - clone tc39/test262 at the commit QuickJS 2026-06-04 pins and apply QuickJS's
    tests/test262.patch (tests/test262.patch here), into a directory outside the
    repository (default: $LUCE_JS_TEST262 or ../.test262 next to the worktree), and point
    the tests/test262 symlink at it;
  - build build/run-test262 with `luce-base build ... --release`;
  - run it from tests/ with tests/test262.conf, whose known-errors file is
    tests/test262_errors.txt (QuickJS's own list; luce-js aims at exactly that list).

`--suite es5` runs the old ES5 suite instead, as upstream's `make test2o` does: the
es5-tests branch of tc39/test262 (QuickJS's doc/quickjs.texi) cloned into DIR/test262o and
linked from tests/test262o, run with tests/test262o.conf in the conf's default mode; its
known-errors file is tests/test262o_errors.txt (empty upstream).

Two ways to run:

  - split (the default for the whole suite): the sorted test list is cut into index ranges
    run by parallel single-threaded runner processes (`-T 1 -r - START STOP`). A Luce
    trap ends the whole process it happens in, so a runner that dies is restarted after
    the test it was running, and that test is reported as CRASH with the trap message.
    The error lines of all processes are merged; with -u the merged list is written to
    tests/test262_errors.txt in the runner's order.
  - direct (`--direct`, or any runner option after `--`): one runner process with its
    own threads, exactly `make test2`. Everything after `--` goes to the runner.

Usage:
  tests/test262.py [--fetch-only] [--no-build] [--dir DIR] [-j JOBS] [-u] [-a|-s]
  tests/test262.py [--no-build] --direct [-- runner options]
  tests/test262.py --suite es5 [--direct] [-u]

Examples:
  tests/test262.py                          # the whole suite, strict and sloppy, split
  tests/test262.py -u                       # ... and update tests/test262_errors.txt
  tests/test262.py -- -c test262.conf -a -E # only the tests of the errors file
  tests/test262.py -- -c test262.conf -f test262/test/built-ins/Array/length.js
  tests/test262.py -- -c test262.conf -a -d test262/test/built-ins/Proxy
  tests/test262.py --suite es5              # the ES5 suite (make test2o)
"""

import argparse
import concurrent.futures
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
RUNNER = os.path.join(ROOT, "build", "run-test262.exe" if sys.platform == "win32" else "run-test262")
LINK = os.path.join(TESTS, "test262")

# QuickJS 2026-06-04 Makefile: TEST262_COMMIT and TEST262_SINCE
TEST262_COMMIT = "5c8206929d81b2d3d727ca6aac56c18358c8d790"
TEST262_SINCE = "2025-09-01"
TEST262_URL = "https://github.com/tc39/test262.git"
# the old ES5 suite (QuickJS doc/quickjs.texi: git clone --single-branch --branch es5-tests)
TEST262O_BRANCH = "es5-tests"


class Suite:
    """What differs between the ES2015+ suite (test262) and the old ES5 one (test262o)."""
    def __init__(self, name, conf, errors, marker, default_mode):
        self.name = name                      # the checkout and link name
        self.conf = conf                      # the runner configuration, in tests/
        self.errors = errors                  # the known-errors file, in tests/
        self.marker = marker                  # a file that exists in a complete checkout
        self.default_mode = default_mode      # the mode option of a split run
        self.link = os.path.join(TESTS, name)
        self.error_line = re.compile(r"^" + name + r"/\S+\.js:\d+: ")


SUITES = {
    "test262": Suite("test262", "test262.conf", "test262_errors.txt", "features.txt", "-a"),
    "es5": Suite("test262o", "test262o.conf", "test262o_errors.txt", "test/harness/sta.js", ""),
}


def default_dir():
    return os.environ.get("LUCE_JS_TEST262") or os.path.join(os.path.dirname(ROOT), ".test262")


def run(command, cwd=None):
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"FAIL: {' '.join(command)} exited with {result.returncode}")


def fetch_es5(directory, suite):
    """Clone the es5-tests branch of test262, as QuickJS's documentation says."""
    checkout = os.path.join(directory, suite.name)
    if not os.path.exists(os.path.join(checkout, suite.marker)):
        os.makedirs(directory, exist_ok=True)
        run(["git", "clone", "--single-branch", "--branch", TEST262O_BRANCH, TEST262_URL, checkout])
    if os.path.islink(suite.link) or os.path.exists(suite.link):
        os.remove(suite.link)
    os.symlink(checkout, suite.link)


def fetch(directory):
    """Clone and patch test262 as `make test2-bootstrap` does."""
    patch = os.path.join(TESTS, "test262.patch")
    checkout = os.path.join(directory, "test262")
    if not os.path.exists(os.path.join(checkout, "features.txt")):
        os.makedirs(directory, exist_ok=True)
        # the files as committed, also on Windows (no CRLF conversion)
        run(["git", "clone", "-c", "core.autocrlf=false", "--single-branch",
             f"--shallow-since={TEST262_SINCE}", TEST262_URL, checkout])
        run(["git", "checkout", "-q", TEST262_COMMIT], cwd=checkout)
    else:
        run(["git", "reset", "-q", "--hard", TEST262_COMMIT], cwd=checkout)
    if sys.platform == "win32":
        # Windows has no `patch`, and a directory symlink needs a privilege: git applies
        # the patch and the link is a junction
        run(["git", "apply", "-p1", patch], cwd=checkout)
        if os.path.lexists(LINK):
            os.rmdir(LINK)
        run(["cmd", "/c", "mklink", "/J", LINK, checkout])
        return
    with open(patch, "rb") as f:
        print(f"+ patch -p1 < {patch}", flush=True)
        if subprocess.run(["patch", "-p1"], stdin=f, cwd=checkout).returncode != 0:
            sys.exit("FAIL: cannot apply tests/test262.patch")
    if os.path.islink(LINK) or os.path.exists(LINK):
        os.remove(LINK)
    os.symlink(checkout, LINK)


def build():
    os.makedirs(os.path.dirname(RUNNER), exist_ok=True)
    run(["luce-base", "build", "tests/run_test262", "-o", RUNNER, "--release"], cwd=ROOT)


def namelist_key(name):
    """The sort order of run-test262's namelist_cmp: digit runs compare as numbers."""
    return [(0, int(part), "") if part.isdigit() else (1, 0, part)
            for part in re.split(r"(\d+)", name) if part != ""]


def count_tests(suite):
    """An upper bound of the runner's test list: every .js file but the fixtures."""
    count = 0
    for _, _, files in os.walk(os.path.join(suite.link, "test")):
        count += sum(1 for f in files if f.endswith(".js") and not f.endswith("_FIXTURE.js"))
    return count


HEADER = re.compile(r"^(\d+): (\S+\.js)")
RESULT = re.compile(r"Result: (\d+)/(\d+) errors?(.*)")


class Totals:
    def __init__(self):
        self.lock = threading.Lock()
        self.failed = self.count = self.new = self.changed = self.fixed = 0
        self.lines = []      # error/status lines of the runners
        self.crashes = []    # (index, file, reason)


def run_range(suite, mode_args, start, stop, totals, empty_errors, timeout):
    """Run the tests [start, stop]; restart after a test that kills the runner."""
    while start <= stop:
        command = [RUNNER, "-c", suite.conf] + mode_args + ["-T", "1", "-r", "-"]
        if empty_errors:
            # every error is reported as new, as with -u
            command += ["-e", empty_errors]
        command += [str(start), str(stop)]
        timed_out = False
        try:
            result = subprocess.run(command, cwd=TESTS, capture_output=True, text=True,
                                    errors="replace", timeout=timeout)
            stdout, stderr, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            stderr = e.stderr.decode(errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
            code, timed_out = None, True
        last_index, last_file = None, None
        lines = []
        failed_runs = 0
        for line in stdout.splitlines():
            m = HEADER.match(line)
            if m:
                last_index, last_file = int(m.group(1)), m.group(2)
            elif suite.error_line.match(line):
                lines.append(line)
            elif line == "  FAILED":
                failed_runs += 1
        result_line = None if timed_out else RESULT.search(stderr)
        with totals.lock:
            totals.lines += lines
            if result_line:
                totals.failed += int(result_line.group(1))
                totals.count += int(result_line.group(2))
                rest = result_line.group(3)
                for key in ("new", "changed", "fixed"):
                    m = re.search(r"(\d+) " + key, rest)
                    if m:
                        setattr(totals, key, getattr(totals, key) + int(m.group(1)))
            else:
                # the counts of a runner that died are lost; keep its failures
                totals.failed += failed_runs
        if result_line:
            return
        # the runner died (a trap or a signal) or hung in the test it announced last
        if last_index is None:
            sys.exit(f"FAIL: the runner died before its first test: {command}\n{stderr[-2000:]}")
        if timed_out:
            reason = f"TIMEOUT after {timeout}s"
        else:
            trap = [l for l in stderr.splitlines() if "trap:" in l]
            others = [l for l in stderr.splitlines() if l.strip() and not re.fullmatch(r"[.!\-]*( \d+/\d+/\d+)?", l.strip())]
            reason = trap[-1][trap[-1].index("trap:"):] if trap else (others[-1] if others else "")
            reason += f" (exit status {code})"
        with totals.lock:
            totals.crashes.append((last_index, last_file, reason))
        start = last_index + 1


UNEXPECTED = re.compile(r"^(\S+:\d+: (?:strict mode: )?)unexpected error: ")


def run_split(suite, mode_args, jobs, chunk, update, timeout):
    total = count_tests(suite)
    totals = Totals()
    empty_errors = None
    if update:
        handle, empty_errors = tempfile.mkstemp(prefix="test262-errors-")
        os.close(handle)
    ranges = [(s, min(s + chunk - 1, total)) for s in range(0, total + 1, chunk)]
    started = time.time()
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        futures = [pool.submit(run_range, suite, mode_args, s, e, totals, empty_errors, timeout) for s, e in ranges]
        for n, future in enumerate(concurrent.futures.as_completed(futures), 1):
            future.result()
            print(f"\r{n}/{len(ranges)} ranges, {totals.failed}/{totals.count} errors, "
                  f"{len(totals.crashes)} crashes", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    crash_lines = [f"{name}:1: CRASH: {reason}" for _, name, reason in sorted(totals.crashes)]
    if update:
        os.remove(empty_errors)
        # the lines the runner writes with -u: no "unexpected error: " prefix
        errors = [UNEXPECTED.sub(r"\1", l) for l in totals.lines
                  if " previous error: " not in l and ": unknown feature: " not in l]
        with open(os.path.join(TESTS, suite.errors), "w") as f:
            for line in sorted(errors + crash_lines, key=namelist_key):
                f.write(line + "\n")
    else:
        for line in sorted(totals.lines, key=namelist_key) + crash_lines:
            print(line)
    summary = f"Result: {totals.failed}/{totals.count} errors"
    if totals.crashes:
        summary += f", {len(totals.crashes)} crashes"
    if not update:
        for key in ("new", "changed", "fixed"):
            if getattr(totals, key):
                summary += f", {getattr(totals, key)} {key}"
    print(summary + f" ({time.time() - started:.0f}s, {jobs} processes)", file=sys.stderr)
    if update:
        return 0
    return 1 if totals.new or totals.changed or totals.fixed or totals.crashes else 0


def main():
    argv = sys.argv[1:]
    runner_args = None
    if "--" in argv:
        split = argv.index("--")
        runner_args = argv[split + 1:]
        argv = argv[:split]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--suite", choices=["test262", "es5"], default="test262",
                        help="test262 (default) or es5, the old ES5 suite of make test2o")
    parser.add_argument("--fetch-only", action="store_true", help="only clone and patch test262")
    parser.add_argument("--no-build", action="store_true", help="use the existing build/run-test262")
    parser.add_argument("--dir", default=default_dir(), help="where test262 is cloned")
    parser.add_argument("--direct", action="store_true", help="one runner process (make test2)")
    parser.add_argument("-j", "--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--chunk", type=int, default=400, help="tests per runner process")
    parser.add_argument("--timeout", type=int, default=600, help="seconds per runner process")
    parser.add_argument("-u", "--update", action="store_true",
                        help="update the known-errors file (tests/test262_errors.txt)")
    parser.add_argument("-a", dest="mode", action="store_const", const="-a", default=None,
                        help="strict and sloppy (the default of test262)")
    parser.add_argument("-s", dest="mode", action="store_const", const="-s", help="strict only")
    parser.add_argument("--default-mode", dest="mode", action="store_const", const="",
                        help="the mode of the configuration file (the default of es5)")
    args = parser.parse_args(argv)
    suite = SUITES[args.suite]

    if not os.path.exists(os.path.join(suite.link, suite.marker)) or args.fetch_only:
        if args.suite == "es5":
            fetch_es5(args.dir, suite)
        else:
            fetch(args.dir)
    if args.fetch_only:
        return
    if not args.no_build:
        build()
    if args.direct or runner_args is not None:
        if runner_args is None:
            # make test2 / make test2o
            runner_args = ["-t", "-c", "test262.conf", "-a"] if args.suite == "test262" else \
                ["-t", "-m", "-c", suite.conf]
        command = [RUNNER] + runner_args
        print("+ (cd tests && " + " ".join(command) + ")", flush=True)
        sys.exit(subprocess.run(command, cwd=TESTS).returncode)
    mode = args.mode if args.mode is not None else suite.default_mode
    mode_args = [mode] if mode else []
    sys.exit(run_split(suite, mode_args, args.jobs, args.chunk, args.update, args.timeout))


if __name__ == "__main__":
    main()
