# luce-js

A JavaScript engine written in **luce-base**: a faithful port of Fabrice Bellard's
[QuickJS](https://bellard.org/quickjs/) (version 2026-06-04) — the same bytecode compiler,
interpreter, garbage collector and built-in library, spelled in luce-base. It is meant to be
the JavaScript engine of the Luce web browser.

Status: **complete port, being hardened.** All of `quickjs.c` is ported and QuickJS's own
test files pass, and test262 fails exactly the 58 tests C QuickJS fails (83,558 run).
Known limits: the interpreter is 1.1-8x slower than C QuickJS (geometric mean 2.86 over
upstream's microbench.js with Luce 0.8.12); what is left is mostly compiler work
(`docs/PERFORMANCE.md`, `docs/COMPILER-REQUESTS.md`). The default JavaScript stack limit is 4 MB
instead of QuickJS's 1 MB. The port's layout, organization and conventions: `docs/PORTING.md`;
compiler problems still worked around: `docs/compiler-issues/`.

**Picking up the work** (luce-js and the luce-browser port built on it): `docs/HANDOFF.md`.

Embedding, in short:

```luce
import js

let rt = js.js_new_runtime() else trap("out of memory")
let ctx = js.js_new_context(rt) else trap("out of memory")
let v = try js.js_eval_text(ctx, "[1, 2, 3].map(x => x * 2).join()", "<input>", 0)
```

The engine is QuickJS's C API with `JS_` spelled `js_` (`JS_NewObject` is `js_new_object`);
a JavaScript exception is a Luce failure (`!`) and the thrown value is `js_get_exception(ctx)`.
An embedder using `host` calls `host.js_std_set_worker_new_context_func` with its
context constructor, as qjs does, so that `os.Worker` can make each worker thread's context.

**Native modules.** QuickJS loads a module whose name ends with `.so` as a shared library;
luce-base has no dlopen-style modules, so an embedder links its native modules in and
registers each one's init function (QuickJS's `js_init_module`) before loading scripts:

```luce
import host

discard(host.js_register_native_module("fib", fib.js_init_module_fib))
```

The default module loader (`host.js_module_loader`) then creates the module when a program
imports `"./fib.so"` (from any directory: the file name without `.so` names it) or the bare
name `"fib"`. `examples/` holds QuickJS's examples: `fib.lucb` and `point.lucb` (a native
class with accessors and a method) are ports of `fib.c` and `point.c`, and `ljs` registers
them and `tests/bjson.lucb` (the `bjson` module of `tests/test_bjson.js`), so
`build/ljs examples/test_point.js` runs as `qjs examples/test_point.js` does.

| Module | Port of | State |
| --- | --- | --- |
| `luce_js.cutils` | `cutils.c`, `list.h` | ported, tested |
| `luce_js.dtoa` | `dtoa.c` | ported, bit-exact with C on the pinned tables |
| `regex` (the luce-regex package) | `libregexp.c` | replaced by luce-regex's ECMAScript dialect |
| `libunicode` (the luce-regex package) | `libunicode.c` | ported in luce-regex |
| `luce_js.engine` | `quickjs.c` | ported |
| `luce_js.host` | `quickjs-libc.c` (POSIX, and Windows as its `_WIN32` branches) | helpers, module loader, event loop (timers, signals, read/write handlers, worker message ports), `std`, `os` with `os.Worker`, registered native modules in place of `.so` |

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

`tests/ljs.lucb` is `qjs`: `luce-base build tests/ljs.lucb -o build/ljs`, then
`build/ljs [options] file.js [args]`, `build/ljs -e EXPR`, or `build/ljs` for QuickJS's
REPL; every qjs option is there (`ljs -h`; `ljs -qd` is `make stats`, `ljs --std
tests/microbench.js` is `make microbench`). `tests/ljsc/` is `qjsc`: `luce-base build
tests/ljsc -o build/ljsc`, then `build/ljsc -o prog file.js` compiles a script or a module
(and the modules it imports) to bytecode and builds a program running it; `-e` writes that
program as a Luce file, `-c` only the bytecode as Luce byte arrays (`ljsc -h`).
`python3 tests/test262.py --suite es5` runs the old ES5 test262 as `make test2o` does
(2/11261 errors, the same as QuickJS).

Licensed under the MIT license, as QuickJS is; see `LICENSE`.
