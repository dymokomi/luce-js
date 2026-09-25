#!/usr/bin/env python3
"""Time the benchmarks of tests/bench/ with ljs (built --release) against C QuickJS's qjs.

Each benchmark runs `--runs` times with each engine; the best wall time is reported, with
ljs/qjs as the ratio. `--save FILE` writes the times as JSON, `--compare FILE` adds a
column with the ljs times of an earlier run and the speed-up since.

`--micro` runs upstream's tests/bench/microbench.js (QuickJS's tests/microbench.js) with
each engine instead, and reports its time per operation of each microbenchmark (the names
given select microbenchmarks by prefix, as microbench.js does), with the geometric mean of
the ratios. A full run takes about four minutes.

QJS names the qjs binary and LUCE_BASE the compiler (defaults: qjs, luce-base on the PATH).

Usage: tests/bench.py [--no-build] [--qjs PATH] [--runs N] [--save F] [--compare F] [bench ...]
       tests/bench.py --micro [--no-build] [--qjs PATH] [--save F] [--compare F] [name ...]
"""

import argparse
import json
import math
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


def micro_times(engine, names):
    """The time per operation (ns) of each microbenchmark of microbench.js run by `engine`."""
    cmd = [engine, "--std", "microbench.js", "-s", ""] + names
    r = subprocess.run(cmd, cwd=BENCH, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        sys.exit(f"FAIL: {' '.join(cmd)}: {r.stderr.decode(errors='replace').strip()}")
    times = {}
    for line in r.stdout.decode().splitlines()[1:]:
        cols = line.split()
        if len(cols) == 3 and cols[0] != "total":
            times[cols[0]] = float(cols[2])
    return times


def micro(args, before):
    q = micro_times(args.qjs, args.names)
    l = micro_times(LJS, args.names)
    head = f"{'microbenchmark':<24} {'qjs ns':>9} {'ljs ns':>9} {'ljs/qjs':>8}"
    if before:
        head += f" {'before ns':>10} {'speed-up':>9}"
    print(head)
    results = {}
    logs = []
    for name in q:
        if name not in l:
            continue
        results[name] = {"qjs": q[name], "ljs": l[name]}
        ratio = l[name] / q[name]
        logs.append(math.log(ratio))
        line = f"{name:<24} {q[name]:9.2f} {l[name]:9.2f} {ratio:8.1f}"
        if name in before:
            b = before[name]["ljs"]
            line += f" {b:10.2f} {b / l[name]:9.2f}"
        print(line)
    if logs:
        print(f"{'geometric mean':<24} {'':9} {'':9} {math.exp(sum(logs) / len(logs)):8.2f}")
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--qjs", default=QJS)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--save")
    ap.add_argument("--compare")
    ap.add_argument("--micro", action="store_true")
    ap.add_argument("names", nargs="*")
    args = ap.parse_args()
    if os.sep in args.qjs:
        # the benchmarks run in tests/bench
        args.qjs = os.path.abspath(args.qjs)
    if not args.no_build:
        build()
    before = {}
    if args.compare:
        with open(args.compare) as f:
            before = json.load(f)
    if args.micro:
        results = micro(args, before)
        if args.save:
            with open(args.save, "w") as f:
                json.dump(results, f, indent=1)
        return
    names = args.names or sorted(f[:-3] for f in os.listdir(BENCH)
                                 if f.endswith(".js") and f != "microbench.js")
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
