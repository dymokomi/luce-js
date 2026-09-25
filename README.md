# luce-js

A JavaScript engine written in **luce-base**: a faithful port of Fabrice Bellard's
[QuickJS](https://bellard.org/quickjs/) (version 2026-06-04) — the same bytecode compiler,
interpreter, garbage collector and built-in library, spelled in luce-base. It is meant to be
the JavaScript engine of the Luce web browser.

Status: **in progress**. The support libraries are ported and tested; the engine is being
ported region by region (see `docs/PORTING.md`).

| Module | Port of | State |
| --- | --- | --- |
| `luce_js.cutils` | `cutils.c`, `list.h` | ported, tested |
| `luce_js.dtoa` | `dtoa.c` | ported, bit-exact with C on the pinned tables |
| `regex` (the luce-regex package) | `libregexp.c` | replaced by luce-regex's ECMAScript dialect |
| `libunicode` (the luce-regex package) | `libunicode.c` | ported in luce-regex |
| `luce_js.engine` | `quickjs.c` | ported |

| `luce_js.host` | `quickjs-libc.c` (parts) | helpers, module loader, job/timer loop, `std`, `os` |

Run the tests of a module with `luce-base test src/luce_js/<module>`; `./test.sh` runs every
module's tests and then QuickJS's own JavaScript tests (`tests/run.py`).

**test262**: luce-js passes test262 exactly as QuickJS does. `tests/test262.py` clones
tc39/test262 at the commit QuickJS 2026-06-04 pins (outside the repository), applies
QuickJS's `tests/test262.patch`, builds `build/run-test262` (`tests/run_test262/`, a port
of QuickJS's `run-test262.c`) and runs the suite with QuickJS's `tests/test262.conf`;
the expected failures are QuickJS's own list, `tests/test262_errors.txt` (58 lines; the
conf, errors and patch files are copied from QuickJS, MIT). Result:
`58/83558 errors, 3356 excluded, 6000 skipped`, the same as QuickJS. By default the run is
split over processes so that a trap in one test cannot hide the others; `--direct` (or
runner options after `--`) runs one threaded runner exactly as `make test2` does.

`tests/ljs.lucb` is a small `qjs`: `luce-base build tests/ljs.lucb -o build/ljs`, then
`build/ljs [--std] [-m] file.js [args]` or `build/ljs -e EXPR`.

Licensed under the MIT license, as QuickJS is; see `LICENSE`.
