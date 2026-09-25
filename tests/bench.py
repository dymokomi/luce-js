#!/usr/bin/env python3
"""Time the benchmarks of tests/bench/ with ljs (built --release) against C QuickJS's qjs.

Each benchmark runs `--runs` times with each engine; the best wall time is reported, with
ljs/qjs as the ratio. `--save FILE` writes the times as JSON, `--compare FILE` adds a
column with the ljs times of an earlier run and the speed-up since.

QJS names the qjs binary and LUCE_BASE the compiler (defaults: qjs, luce-base on the PATH).

Usage: tests/bench.py [--no-build] [--qjs PATH] [--runs N] [--save F] [--compare F] [bench ...]
"""

import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH = os.path.join(ROOT, "tests", "bench")
LJS = os.path.join(ROOT, "build", "ljs-release")
QJS = os.environ.get("QJS", "qjs")
# the compiler that builds ljs (LUCE_BASE, default luce-base on the PATH)
LUCE_BASE = os.environ.get("LUCE_BASE", "luce-base")


def build():
    print("building build/ljs-release ...", flush=True)
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    r = subprocess.run([LUCE_BASE, "build", "tests/ljs.lucb", "-o", LJS, "--release"], cwd=ROOT)
    if r.returncode != 0:
        sys.exit("FAIL: cannot build ljs")


def best_time(cmd, runs):
    best = None
    for _ in range(runs):
        t0 = time.perf_counter()
        r = subprocess.run(cmd, cwd=BENCH, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        dt = time.perf_counter() - t0
        if r.returncode != 0:
            sys.exit(f"FAIL: {' '.join(cmd)}: {r.stderr.decode(errors='replace').strip()}")
        best = dt if best is None else min(best, dt)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--qjs", default=QJS)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--save")
    ap.add_argument("--compare")
    ap.add_argument("names", nargs="*")
    args = ap.parse_args()
    if not args.no_build:
        build()
    names = args.names or sorted(f[:-3] for f in os.listdir(BENCH) if f.endswith(".js"))
    before = {}
    if args.compare:
        with open(args.compare) as f:
            before = json.load(f)
    results = {}
    head = f"{'benchmark':<18} {'qjs s':>7} {'ljs s':>7} {'ljs/qjs':>8}"
    if before:
        head += f" {'before s':>9} {'speed-up':>9}"
    print(head)
    for name in names:
        q = best_time([args.qjs, name + ".js"], args.runs)
        l = best_time([LJS, name + ".js"], args.runs)
        results[name] = {"qjs": q, "ljs": l}
        line = f"{name:<18} {q:7.3f} {l:7.3f} {l / q:8.1f}"
        if name in before:
            b = before[name]["ljs"]
            line += f" {b:9.3f} {b / l:9.2f}"
        print(line, flush=True)
    if args.save:
        with open(args.save, "w") as f:
            json.dump(results, f, indent=1)


if __name__ == "__main__":
    main()
