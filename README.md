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
| `luce_js.unicode` | `libunicode.c` | in progress |
| `regex` (the luce-regex package) | `libregexp.c` | replaced by luce-regex's ECMAScript dialect |
| `luce_js.engine` | `quickjs.c` | skeleton: types and typed stubs |

Run the tests of a module with `luce-base test src/luce_js/<module>`.

Licensed under the MIT license, as QuickJS is; see `LICENSE`.
