# luce-js

A JavaScript engine written in **luce-base**: a faithful port of Fabrice Bellard's
[QuickJS](https://bellard.org/quickjs/) (version 2026-06-04) — the same bytecode compiler,
interpreter, garbage collector and built-in library, spelled in luce-base. It is meant to be
the JavaScript engine of the Luce web browser.

Status: **complete port, being hardened.** All of `quickjs.c` is ported and QuickJS's own
test files pass (`test_std.js` still needs `os.exec`); test262 conformance runs are under way.
Known limits: the interpreter is about 20x slower than C QuickJS until the luce-base native
backend compiles dense `match` to jump tables, and deep recursion reaches ~700 levels in the
default 1 MB JavaScript stack (C QuickJS: 1000-2000). How the port was done and its
conventions: `docs/PORTING.md`; compiler problems met on the way: `docs/compiler-issues/`.

Embedding, in short:

```luce
import js

let rt = js.js_new_runtime() else trap("out of memory")
let ctx = js.js_new_context(rt) else trap("out of memory")
let v = try js.js_eval_text(ctx, "[1, 2, 3].map(x => x * 2).join()", "<input>", 0)
```

The engine is QuickJS's C API with `JS_` spelled `js_` (`JS_NewObject` is `js_new_object`);
a JavaScript exception is a Luce failure (`!`) and the thrown value is `js_get_exception(ctx)`.

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
