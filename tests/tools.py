#!/usr/bin/env python3
"""Test the tools: ljs's options and REPL (tests/ljs.lucb, qjs.c) and the ljsc compiler (tests/ljsc, qjsc.c).

  - ljs: the options qjs has, with the outputs and exit statuses C qjs gives (pinned
    below; they were compared with C qjs 2026-06-04): -e, -I, -m, --std, --strict,
    --memory-limit, --stack-size, -s, -T, -d, -qd, errors printed as js_std_dump_error
    prints them, and the REPL (-i) driven through a pipe.
  - tests/repl.lucb, the REPL bytecode ljs embeds, is what ljsc generates from
    tests/repl.js today (the Makefile's `qjsc -s -c -o repl.c -m repl.js`).
  - ljsc: the programs of QuickJS's examples and a module with a chain of imports are
    compiled to executables (the default output), to a Luce file with main (-e, with a
    native module given by -M) and to bytecode only (-c), built with luce-base, run, and
    their output compared with running the source with ljs.

With QJSC=path/to/qjsc (C QuickJS's compiler), the -c output of the sources without regular
expressions is also compared byte for byte with qjsc's: luce-js writes the same bytecode.
(A regular expression literal differs: its compiled form is luce-regex's, not libregexp's.)

Usage: tests/tools.py [--no-build]
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
TOOLS = os.path.join(TESTS, "tools")
BUILD = os.path.join(ROOT, "build")
LJS = os.path.join(BUILD, "ljs")
LJSC = os.path.join(BUILD, "ljsc")
WORK = os.path.join(BUILD, "tools-tests")

failures = []


def check(name, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL':5}  {name}", flush=True)
    if not ok:
        failures.append(name)
        if detail:
            print("       " + detail.replace("\n", "\n       "))


def run(command, cwd=ROOT, stdin=None, timeout=300):
    result = subprocess.run(command, cwd=cwd, input=stdin, capture_output=True, timeout=timeout)
    return (result.returncode, result.stdout.decode(errors="replace"),
            result.stderr.decode(errors="replace"))


def build():
    for source, out in (("tests/ljs.lucb", LJS), ("tests/ljsc", LJSC)):
        print(f"building {os.path.relpath(out, ROOT)} ...", flush=True)
        if subprocess.run(["luce-base", "build", source, "-o", out], cwd=ROOT).returncode != 0:
            sys.exit(f"FAIL: cannot build {source}")


# mark: ljs =====================================================================================

HELP_HEAD = "luce-js (QuickJS version 2026-06-04)\nusage: ljs [options] [file [args]]\n"

# (name, arguments, files to write in WORK, expected exit status, expected stdout, expected
# stderr); None skips the comparison, a compiled regex must match
LJS_CASES = [
    ("-e syntax error", ["-e", "1+"], {}, 1, "",
     "SyntaxError: unexpected token in expression: ''\n    at <cmdline>:1:3\n"),
    ("exception backtrace", ["err.js"],
     {"err.js": 'function f(){ throw new TypeError("bad " + 1) }\nf()\n'}, 1, "",
     "TypeError: bad 1\n    at f (err.js:1:34)\n    at <eval> (err.js:2:2)\n"),
    ("--memory-limit", ["--memory-limit", "2M", "oom.js"],
     {"oom.js": "var a=[]; for(;;) a.push(new Array(1000).fill(1));\n"}, 1, "",
     "InternalError: out of memory\n    at <eval> (oom.js:1:46)\n"),
    ("--stack-size", ["--stack-size", "100k", "so.js"],
     {"so.js": "function r(n){return r(n+1)+1} r(0)\n"}, 1, "",
     re.compile(r"^InternalError: stack overflow\n    at r \(so.js:1:23\)\n")),
    ("-e", ["-e", "print(42)"], {}, 0, "42\n", ""),
    ("-q", ["-qe", "print(1)"], {}, 0, "", ""),
    ("-I include", ["-I", "inc.js", "-e", "print(g())"], {"inc.js": "function g() { return 'inc' }\n"},
     0, "inc\n", ""),
    ("-I failure", ["-I", "err.js", "-e", "1"], {}, 1, "", re.compile(r"^TypeError: bad 1\n")),
    ("--std", ["--std", "-e", "std.printf('%d\\n', 7); print(typeof os.open)"], {}, 0, "7\nfunction\n", ""),
    ("-m import.meta", ["-m", "-e", "print(import.meta.main)"], {}, 0, "undefined\n", ""),
    ("--strict", ["--strict", "-e", "try { undeclared = 1 } catch (e) { print(e.name) }"], {}, 0,
     "ReferenceError\n", ""),
    ("module autodetect", ["mod.js", "x", "y"], {"mod.js": "import * as os from 'os';\nprint(typeof os.now, scriptArgs.join())\n"},
     0, "function mod.js,x,y\n", ""),
    ("--script", ["--script", "mod.js"], {}, 1, "", re.compile(r"^SyntaxError: ")),
    ("unhandled rejection", ["-e", "Promise.reject(3)"], {}, 1, "", "Possibly unhandled promise rejection: 3\n"),
    ("--no-unhandled-rejection", ["--no-unhandled-rejection", "-e", "Promise.reject(3)"], {}, 0, "", ""),
    ("-s strips the source", ["-s", "-e", "print((function f() { return 1 }).toString())"], {}, 0,
     "function f() {\n    [native code]\n}\n", ""),
    ("--strip-source", ["--strip-source", "-e", "print((function f() { return 1 }).toString())"], {}, 0,
     "function f() {\n    [native code]\n}\n", ""),
    ("missing file", ["nonexist.js"], {}, 1, "", "nonexist.js: No such file or directory\n"),
    ("missing -e", ["-e"], {}, 2, "", "ljs: missing expression for -e\n"),
    ("-I without file", ["-I"], {}, 1, "", "expecting filename"),
    ("unknown option", ["-x"], {}, 1, re.compile("^" + re.escape(HELP_HEAD)), "ljs: unknown option '-x'\n"),
    ("unknown long option", ["--foo"], {}, 1, re.compile("^" + re.escape(HELP_HEAD)),
     "ljs: unknown option '--foo'\n"),
    ("invalid size suffix", ["--stack-size", "10x"], {}, 1, "", "ljs: invalid suffix: x\n"),
    ("-h", ["-h"], {}, 1, re.compile("^" + re.escape(HELP_HEAD) + r"(.|\n)*-q  --quit "), ""),
    ("-d", ["-d", "-e", "print(1)"], {}, 0,
     re.compile(r"^1\nQuickJS memory usage -- 2026-06-04 version, 64-bit, malloc limit: -1\n(.|\n)*\nNAME +COUNT +SIZE\nmemory allocated "), ""),
    ("-qd (make stats)", ["-qd"], {}, 0,
     re.compile(r"^QuickJS memory usage (.|\n)*\nInstantiation times \(ms\): \d+\.\d{3} = \d+\.\d{3}\+\d+\.\d{3}\+\d+\.\d{3}\+\d+\.\d{3}\n$"), ""),
    ("-T traces the allocations", ["-T", "-e", "print('x')"], {}, 0,
     re.compile(r"^A \d+ -> H[-+]\d{5,}\.\d+\n(.|\n)*^x\n(.|\n)*^F H[-+]\d{5,}\.\d+\n", re.M), ""),
]


def matches(expected, actual):
    if expected is None:
        return True
    if isinstance(expected, re.Pattern):
        return expected.search(actual) is not None
    return expected == actual


def test_ljs():
    os.makedirs(WORK, exist_ok=True)
    for name, args, files, status, out, err in LJS_CASES:
        for file, text in files.items():
            with open(os.path.join(WORK, file), "w") as f:
                f.write(text)
        code, stdout, stderr = run([LJS] + args, cwd=WORK)
        ok = code == status and matches(out, stdout) and matches(err, stderr)
        check(f"ljs {name}", ok, f"status {code}\nstdout: {stdout[:400]!r}\nstderr: {stderr[:400]!r}")


# The REPL through a pipe: one line at a time ('\r' is Enter in the raw mode it sets up),
# ended by \q. The expected fragments are what C qjs prints (colorized).
REPL_LINES = [b'1+2', b'let x = [1, "a", {b: 2}]', b'x', b'throw new Error("boom")',
              b'function f() {', b'return 42 }', b'f()', b'\\q']
REPL_EXPECTED = ['QuickJS - Type "\\h" for help\nqjs > ', "\n\x1b[37;1m3\n\x1b[0mqjs > ",
                 '\n\x1b[37;1m[ 1, "a", { b: 2 } ]\n\x1b[0mqjs > ',
                 "\n\x1b[31;1mError: boom\n    at <eval> (<evalScript>:1:16)\n\x1b[0mqjs > ",
                 "\n{  ... ", "\n\x1b[37;1m42\n\x1b[0mqjs > "]


def test_repl():
    for mode in (["-i"], []):
        p = subprocess.Popen([LJS] + mode, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=WORK)
        for line in REPL_LINES:
            p.stdin.write(line + b"\r")
            p.stdin.flush()
            time.sleep(0.3)
        try:
            out, err = p.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = p.communicate()
        text = out.decode(errors="replace")
        missing = [e for e in REPL_EXPECTED if e not in text]
        check(f"ljs {' '.join(mode) or '(no file)'} REPL", p.returncode == 0 and not missing,
              f"status {p.returncode}, missing {missing!r}\n{text[-600:]!r}\n{err.decode(errors='replace')[:300]}")


# mark: ljsc ====================================================================================

def test_repl_bytecode():
    fresh = os.path.join(WORK, "repl.lucb")
    code, _, err = run([LJSC, "-s", "-c", "-o", fresh, "-m", "repl.js"], cwd=TESTS)
    with open(os.path.join(TESTS, "repl.lucb")) as f:
        kept = f.read()
    with open(fresh) as f:
        current = f.read() if code == 0 else ""
    check("tests/repl.lucb is ljsc's output for tests/repl.js", code == 0 and kept == current,
          err or "regenerate it: cd tests && ../build/ljsc -s -c -o repl.lucb -m repl.js")


def package(directory, extra_files=()):
    """A package in `directory` that depends on this luce-js tree."""
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory)
    with open(os.path.join(directory, "package.prisma"), "w") as f:
        f.write('#prisma 4.0\ndef package "ljsc_test" {\n    str source = "."\n'
                f'    def dependency "luce-js" {{\n        str path = "{ROOT}"\n    }}\n}}\n')
    for file in extra_files:
        shutil.copy(os.path.join(TOOLS, file), directory)


def ljs_output(args):
    """What ljs prints running the source: the reference for the compiled programs."""
    return run([LJS] + args, cwd=TOOLS)


def test_ljsc():
    hello_opts = ["-fno-string-normalize", "-fno-map", "-fno-promise", "-fno-typedarray",
                  "-fno-typedarray", "-fno-regexp", "-fno-json", "-fno-eval", "-fno-proxy",
                  "-fno-date", "-fno-module-loader"]
    hello_module_opts = ["-fno-string-normalize", "-fno-map", "-fno-typedarray", "-fno-typedarray",
                         "-fno-regexp", "-fno-json", "-fno-eval", "-fno-proxy", "-fno-date", "-m"]

    # executables, as the Makefile builds examples/hello and examples/hello_module
    for name, opts, source, args in (
            ("hello", hello_opts, "hello.js", []),
            ("hello_module", hello_module_opts, "hello_module.js", []),
            ("imports_main", ["-N", "main_program", "-S", "2M"], "imports_main.js", ["a", "b"])):
        exe = os.path.join(WORK, name)
        code, out, err = run([LJSC, "-o", exe] + opts + [source], cwd=TOOLS)
        if code != 0:
            check(f"ljsc {name} (executable)", False, out + err)
            continue
        expected = ljs_output([source] + args)
        actual = run([exe] + args, cwd=TOOLS)
        check(f"ljsc {name} (executable)", expected[0] == 0 and actual == expected,
              f"ljs: {expected!r}\ncompiled: {actual!r}")

    # -e with a native module, as the Makefile makes test_fib.c: qjsc -e -M examples/fib.so,fib
    directory = os.path.join(WORK, "test_fib")
    package(directory, ["fib.lucb"])
    code, out, err = run([LJSC, "-e", "-M", "fib.so,fib", "-m", "-o",
                          os.path.join(directory, "test_fib.lucb"), "test_fib.js"], cwd=TOOLS)
    exe = os.path.join(directory, "test_fib")
    if code == 0:
        code, out, err = run(["luce-base", "build", os.path.join(directory, "test_fib.lucb"), "-o", exe])
    actual = run([exe]) if code == 0 else (code, out, err)
    check("ljsc -e -M test_fib (native module)", actual == (0, "Hello World\nfib(10)= 55\n", ""), repr(actual))

    # -c: only the bytecode, used from a program of ours; -p changes the prefix
    directory = os.path.join(WORK, "bytecode_only")
    package(directory)
    code, out, err = run([LJSC, "-c", "-p", "demo_", "-o", os.path.join(directory, "hello_data.lucb"),
                          "hello.js"], cwd=TOOLS)
    with open(os.path.join(directory, "main.lucb"), "w") as f:
        f.write("import js\nimport host\nimport hello_data\n\n"
                "pub func main(arguments: str[]) -> i32:\n"
                "    let rt = js.js_new_runtime() else return 1\n"
                "    let ctx = js.js_new_context(rt) else return 1\n"
                "    host.js_std_add_helpers(ctx, arguments) catch: return 1\n"
                "    host.js_std_eval_binary(ctx, &hello_data.demo_hello[0], hello_data.demo_hello_size, false)\n"
                "    js.js_free_context(ctx)\n    js.js_free_runtime(rt)\n    return 0\n")
    exe = os.path.join(directory, "main")
    if code == 0:
        code, out, err = run(["luce-base", "build", os.path.join(directory, "main.lucb"), "-o", exe])
    actual = run([exe]) if code == 0 else (code, out, err)
    check("ljsc -c -p (bytecode only)", actual == (0, "Hello World\n", ""), repr(actual))

    # the same bytecode as C qjsc
    qjsc = os.environ.get("QJSC")
    if qjsc:
        for opts, source in (([], "hello.js"), (["-m"], "hello_module.js"), (["-m"], "imports_main.js"),
                             (["-s", "-m"], "test_fib.js")):
            ours = os.path.join(WORK, "ours.lucb")
            theirs = os.path.join(WORK, "theirs.c")
            ok = run([LJSC, "-c", "-o", ours] + opts + [source], cwd=TOOLS)[0] == 0 and \
                run([qjsc, "-c", "-o", theirs] + opts + [source], cwd=TOOLS)[0] == 0
            if ok:
                hex_ours = re.findall(r"0x[0-9a-f]{2}", open(ours).read())
                hex_theirs = re.findall(r"0x[0-9a-f]{2}", open(theirs).read())
                names_ours = re.findall(r"pub let (\w+): u8", open(ours).read())
                names_theirs = re.findall(r"const uint8_t (\w+)\[", open(theirs).read())
                ok = hex_ours == hex_theirs and names_ours == names_theirs
            check(f"ljsc -c {' '.join(opts)} {source} is qjsc's bytecode", ok)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-build", action="store_true", help="use the existing build/ljs and build/ljsc")
    args = parser.parse_args()
    if not args.no_build:
        build()
    os.makedirs(WORK, exist_ok=True)
    test_ljs()
    test_repl()
    test_repl_bytecode()
    test_ljsc()
    print(f"\n{len(failures)} failed" if failures else "\nall passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
