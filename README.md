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

`tests/ljs.lucb` is a small `qjs`: `luce-base build tests/ljs.lucb -o build/ljs`, then
`build/ljs [--std] [-m] file.js [args]` or `build/ljs -e EXPR`.

Licensed under the MIT license, as QuickJS is; see `LICENSE`.
