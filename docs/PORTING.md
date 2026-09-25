# The luce-js port of QuickJS

luce-js is a port of Fabrice Bellard's QuickJS (upstream `bellard/quickjs`, version
2026-06-04, commit `04be246`) to luce-base. It is a **faithful port**: the same data
structures, the same algorithms, the same bytecode, the same atoms, the same order of
functions, and the same comments where they still apply. It is not a redesign. When in
doubt, do what the C does, spelled the way luce-base spells it.

This document describes how the port is laid out and the conventions every change keeps.
The language reference is `../luce-base/docs/language/base.md`; the standard library
reference is `../luce-base/docs/LIBRARY.md`.

## Layout

| C source | Luce module | Directory |
| --- | --- | --- |
| `cutils.c`, `cutils.h`, `list.h` | `luce_js.cutils` | `src/luce_js/cutils/` |
| `dtoa.c`, `dtoa.h` | `luce_js.dtoa` | `src/luce_js/dtoa/` |
| `libunicode.c`, `libunicode-table.h` | `libunicode` (luce-regex package) | `../luce-regex/src/luce_regex/unicode/` |
| `libregexp.c`, `libregexp-opcode.h` | not ported: the `regex` module of the luce-regex dependency (engine `regexp_bridge.lucb`) | `../luce-regex` |
| `quickjs.c`, `quickjs.h`, `quickjs-atom.h`, `quickjs-opcode.h` | `luce_js.engine` (exported as `js`) | `src/luce_js/engine/` |
| `quickjs-libc.c` (POSIX, without workers) | `luce_js.host` (exported as `host`) | `src/luce_js/host/` |
| `qjs.c` (without the REPL) | the `ljs` program | `tests/ljs.lucb` |
| `run-test262.c` | the `run-test262` program | `tests/run_test262/` |

Every module is a directory whose `ORDER` file lists its fragments (language §16.1). The
fragments of one module share one scope, exactly like the one C file they came from, so a
`static` C function is a private Luce function visible to every fragment of its module.
Another module's declarations are reached with `import luce_js.cutils as cutils` in the
module's first fragment (imports in `module.lucb` apply to every fragment) and must be `pub`.
`luce_js.cutils` also holds the few helpers every module shares: the C library binding and
C strings as `str` views (`c_str_view`, `c_str_equals`).

- Keep each fragment focused and under about 600 lines. Split along the C source's own
  sections, in the C source's order. Generated tables (`atoms_table`, `opcodes_table`) and
  test vector tables are exempt.
- Every fragment starts with a header box saying what it owns and which C lines it came
  from:

```luce
#==============================================================================================
#
#   atoms - The atom table: interning strings and symbols as 32-bit ids
#
#   DESCRIPTION:
#       Port of quickjs.c "JSAtom support" (lines 2868-3815).
#
#==============================================================================================
```

- Fragments over 150 lines use `# mark: Name ====...` section comments (97 columns).
- Keep QuickJS's explanatory comments (as `#` comments), and give every `pub` declaration
  a `##` doc line.
- Tests live in `tests*.lucb` fragments at the end of the module's `ORDER` (tests may use
  private declarations), named after what they test. Run a module's tests with
  `luce-base test src/luce_js/<module>`.
- `luce-base check src/luce_js/<module> -W` prints no warning for any module or test
  program: no unused private function, local or import, and no unreachable statement. The
  debug dumps QuickJS compiles only under `DUMP_*` options are not ported. A per-target
  return is written `if os.macos: ... else: ...` so the branch ruled out is pruned
  silently.

## Names

- Functions: snake_case of the C name. A `JS_` prefix becomes `js_`; a `js_` prefix is kept;
  leading underscores are dropped and `_raw` is appended. Where a public `JS_X` and an
  internal `js_x` would get the same name, the internal one gets `_internal`. camelCase boundaries become
  underscores; `UInt`, `BigInt`, `JSON`, `RegExp`, `UTF8` read as one word each.
  - `JS_NewObject` → `js_new_object`, `JS_GetPropertyUint32` → `js_get_property_uint32`,
    `__JS_AtomToValue` → `js_atom_to_value_raw`, `js_array_lastIndexOf` →
    `js_array_last_index_of`, `js_bigint_asUintN` → `js_bigint_as_uint_n`,
    `JS_AddIntrinsicRegExp` → `js_add_intrinsic_reg_exp`, `JS_ThrowTypeError` →
    `js_throw_type_error` (and the builtin `js_throw_type_error` →
    `js_throw_type_error_internal`).
  - `JS_ATOM_NULL` (no atom) is `no_atom`; the atom of the text "null" (`JS_ATOM_null`)
    is `atom_null_keyword`. Every other `JS_ATOM_x` is `atom_x`.
  - The complete table of every quickjs.c function whose name changes is
    `docs/namemap.txt` (`CName luce_name`). Use it; do not invent names.
  - quickjs.h's macros and inline functions follow the same rule: `JS_VALUE_GET_INT` →
    `js_value_get_int`, `JS_MKVAL` → `js_mkval`, `JS_NewInt32` → `js_new_int32`,
    `JS_FreeValue` → `js_free_value`, `JS_IsException` → `js_is_exception`. The value
    constants are functions: `JS_UNDEFINED` → `js_undefined()`, `JS_NULL` → `js_null()`,
    `JS_TRUE`/`JS_FALSE` → `js_true()`/`js_false()`, `JS_EXCEPTION` → `js_exception()`.
- Types: drop the `JS` prefix and keep PascalCase: `JSObject` → `Object`, `JSRuntime` →
  `Runtime`, `JSContext` → `Context`, `JSString` → `String`, `JSValue` → `Value`,
  `JSShape` → `Shape`, `JSFunctionDef` → `FunctionDef`. Non-prefixed types keep their
  names (`DynBuf`, `CharRange`, `REParseState`). `JSAtom` is `type Atom = u32`.
- Struct fields keep their C names.
- Constants (`#define` values and plain `enum` members): lower snake_case with the
  `JS_` prefix dropped: `JS_PROP_WRITABLE` → `prop_writable`, `JS_ATOM_length` →
  `atom_length`, `UTF8_CHAR_LEN_MAX` → `utf8_char_len_max`, `LRE_FLAG_GLOBAL` →
  `lre_flag_global`.
- An enum that C code `switch`es over becomes an integer-backed Luce enum, because a
  `match` pattern can only be a literal or an enum case, never a named constant:
  `enum Tag as i64`, `enum ClassId as u16`, `enum Op as u8` (the bytecode opcodes),
  `enum REOp as u8`, `enum TokenType as i32`, ... Cases are lower snake_case
  (`Tag.object`, `ClassId.array`, `Op.push_i32`). Compare with `==`; for `<`/`>=` cast
  both sides to the backing integer: `(u16)p.class_id >= (u16)ClassId.uint8c_array`.
- A name that is a reserved word or a core name gets a trailing underscore: the union
  member `func` → `func_`, the class `JS_CLASS_ERROR` → `ClassId.error_`, the opcode
  `OP_return` → `Op.return_`, the format `u8` → `OpFormat.u8_`.
- Core names cannot be declared (`hash`, `format`, `print`, `error`, `str`, `char`, `pad`,
  `hex`, `bin`, `bool`, `i32`, ...): a local named `hash` becomes `h`, a parameter `str`
  becomes `text`, a case `int` becomes `integer`. Locals may not shadow anything visible,
  including functions of the module: rename the local.

## Types

| C | Luce |
| --- | --- |
| `int`, `int32_t` | `i32` |
| `unsigned`, `uint32_t` | `u32` |
| `int64_t`, `uint64_t`, `int16_t`, ... | `i64`, `u64`, `i16`, ... |
| `size_t` / `ssize_t`, `intptr_t` | `usize` / `isize` |
| `BOOL` (quickjs's `int`) | `bool` |
| `double`, `float` | `f64`, `f32` |
| `char` (bytes of text) | `u8` |
| `T *` that may be `NULL` | `T*?` |
| `T *` that is never `NULL` by invariant | `T*` |
| `const T *` | `const T*` / `const T*?` |
| `void *opaque` | `void*?` |
| `T *buf, int len` pairs | a span `T[]` / `const T[]` where the function indexes it; a pointer where the C code walks it with `p++` |
| `T a[N]` | `T[N]` |
| function pointer typedef | `type Name = func(A, B) -> R`; nullable as `Name?` |
| bit-field `uint8_t x : 1` | a separate `bool` (or `u8`) field |
| anonymous struct/union member | a named struct/union type, `Outer_field` style name as PascalCase (`ObjectFunc`) |
| flexible array member `T tab[]` | omit it; reach it by pointer arithmetic past `sizeof(Struct)` |
| `union` | Luce `union` (C semantics) |
| `struct list_head` intrusive lists | `cutils.ListHead` and its functions; `container_of` is `(T*)((u8*)p - offsetof(T, field))` |

## Integer semantics

C and luce-base disagree in three places; get these right, they are where ports break.

1. **Overflow.** Luce's `+ - *` trap on overflow. C unsigned arithmetic wraps: use `+%`,
   `-%`, `*%` wherever the C operands are unsigned and wrapping is possible or intended
   (hashes, PRNGs, checksums, `len - 1` on a possibly-zero unsigned). Signed C overflow is
   undefined, so a trapping `+` on signed values is correct and catches real bugs.
2. **Promotion.** C promotes `u8`/`u16` operands to `int`. Luce computes in the operand
   type. Write the widening where the C result could exceed the narrow type:
   `(i32)a - (i32)b`, not `a - b` on two `u8`s.
3. **Conversions.** Luce widens implicitly only within one signedness. Everything else is
   written: `(T)x` is C's cast (truncation, reinterpretation, float→int saturating);
   `T(x)` is the checked conversion that traps. Use `(T)x` where C converts implicitly or
   casts; use `f64(x)` for int→double. Integer division is `//`; `%` is C's remainder.
   Shifts: a shift count ≥ the width traps (it is UB in C anyway); `<<` discards bits.

`bool` is not an integer: `(i32)flag`, `(bool)n`, and `n != 0` are written.

## Memory

- The C library's `malloc`, `realloc`, `free`, `memcpy`, `memmove`, `memset`, `memcmp`,
  `strlen` are bound once in `luce_js.cutils` (`cutils.malloc(...)`, ...). Port code that
  calls them calls these. Nothing in the port uses Luce's `new`/`alloc` for engine data:
  QuickJS's memory accounting and its own small-block allocator (quickjs.c "JS malloc")
  are ported as they are.
- Pointer arithmetic `p + n` takes `usize`/`isize`; `p[i]` on a pointer is unchecked, as
  in C. Indexing a span or array is checked: prefer spans where the C code has a length.
- `sizeof(T)`, `offsetof(T, f)` work as in C.

## Errors and control flow

- `goto` does not exist. Restructure: cleanup labels become `defer`/`errdefer` or a
  small helper; retry labels become loops; `goto done` out of nested loops becomes a
  labeled `break`. Never change behaviour to make the structure easier.
- `switch` becomes `match` (integer patterns are literals; ranges `'0'..='9'`; several
  values `1, 2, 3:`; a `_` arm). C fallthrough is duplicated code or a shared helper.
- The support libraries (`cutils`, `dtoa`, luce-regex's `libunicode`) keep QuickJS's C contracts:
  a function that returns `-1` on failure still returns an `i32` status. Their callers are
  C-shaped code in the engine, and that keeps the port reviewable line by line.
- In the engine, a JavaScript exception is a Luce failure: a C function that returns
  `JS_EXCEPTION`, or `-1` "exception", or `NULL` "exception pending", is fallible in Luce
  (`-> Value!`, `-> bool!`, `-> i32!`, `-> Object*!`) and fails with
  `error(exception, "")` after storing the thrown value in `rt.current_exception` exactly
  as C does. `if (JS_IsException(v)) goto fail;` becomes `try`, and the `fail:` cleanup
  becomes `errdefer`. Where C inspects or clears the exception, use `catch`.
- `printf`-style formats (`JS_ThrowTypeError(ctx, "%s is not a function", name)`) become
  `fmt` parameters and interpolation: `throw_type_error(ctx, f"{name} is not a function")`.

## How the engine is organized

`src/luce_js/engine/ORDER` lists the fragments in quickjs.c's order. Each header gives the
C lines it ports; in broad groups:

- **Declarations**: `module` (imports, the error code, engine-wide limits), `value` and
  `refcount` (JSValue and reference counts), `api_types` (quickjs.h's public types, class
  and function-list tables), `types_runtime`, `types_bytecode`, `types_object` (the structs
  of quickjs.c), `compiler_types` (the parser's and compiler's), and the generated
  `atoms_table` and `opcodes_table` (`tools/engine_tables.py` from quickjs-atom.h and
  quickjs-opcode.h).
- **Runtime**: atoms, QuickJS's own small-block allocator (`malloc`, `malloc_api`), the
  runtime and contexts, classes, strings and ropes, shapes and objects, the garbage
  collector (`gc`, `object_free`), `memory_usage`, exceptions and the `js_throw_*` helpers.
- **The object model**: prototypes, property reads (`property_get`), own properties,
  `define_property*`, global variables, property writes (`property_set*`,
  `property_add_delete`, `fast_arrays`), conversions, the value printer, BigInt
  (`bigint_*`), and the slow paths of the operators.
- **The interpreter**: `interpreter_support` (InterpState and the macros of
  JS_CallInternal), `interpreter` (js_call_internal and its dispatch loop), `interp_outlined` (the match
  over the other opcodes), `interp_frames`
  (frame setup, the call opcodes, unwinding and release), the opcode bodies
  (`interp_ops_*`), `call_entry` (JS_Call and friends), generators and async functions.
- **The compiler**: the tokenizer, the emitter, the parser (`parser_*`, `parse_function*`,
  `module_parse`), modules (`modules`, `module_resolve`, `module_link`, `module_load`,
  `module_eval`), the variable resolution pass (`closure_vars`, `resolve_scope_var`,
  `resolve_private_fields`, `eval_variables`, `resolve_variables`), the label resolution
  and peephole pass (`code_match`, `label_helpers`, `resolve_labels*`), `stack_size`,
  `create_function` and `eval`.
- **Serialization**: the binary object format (`bytecode_writer`, `object_writer`,
  `bytecode_reader`, `object_reader`, `object_list`).
- **The builtins**, one group of fragments per class in quickjs.c's order: functions and
  errors, Object, Number and Boolean, String, Math, Array and the iterators, RegExp
  (`regexp_*`, over luce-regex), JSON, Reflect, Proxy, Symbol, Map and Set, Promise,
  URI, Date, Atomics, WeakRef, the intrinsics, ArrayBuffer, the typed arrays and DataView.
- **Unit tests** (`tests_*`), for what can be checked without JavaScript source; the
  JavaScript tests exercise the rest.

Engine idioms:

- JavaScript exceptions: `js_throw(ctx, v) -> never!` and the `js_throw_*_error(ctx,
  f"...") -> never!` helpers store the exception and fail with `error(exception, "")`.
  A function that returned `JS_EXCEPTION` or `-1` fails the same way; its caller writes
  `try`. `goto fail` cleanup becomes `errdefer` (or `defer` when it runs on both paths).
  Where C tests `JS_IsException(v)` and continues differently, use `catch`.
- A C function returning "-1 exception / FALSE / TRUE" is `-> bool!`; "-1 / 0" is `-> !`;
  "NULL with an exception pending" is `-> T*!`.
- `JSValue` locals are `Value`; `ValueUnion` is not zeroable, so an uninitialized C
  `JSValue v;` becomes `var v = js_undefined()` (or `= ---` when every path writes it
  before reading). Arrays of values: `var args: Value[2] = ---`.
- Pointers from values: `v.u.obj` (JS_VALUE_GET_OBJ), `v.u.string`, `v.u.ptr`,
  `js_value_get_int(v)`, `js_value_get_float64(v)`.
- The reference count of a GC object or string is `js_rc(ptr).ref_count`.
- `JSValueConst *argv` stays `argv: Value*` with `argc: i32`, as in C; a call with no
  arguments passes any valid pointer (a local `Value`) with `argc = 0`.
- Builtin tables (`JSCFunctionListEntry` arrays) are `let` arrays of
  `CFunctionListEntry(...)`; the spelling of each C macro is in `api_types.lucb`.
- Class tables and exotic method tables are `let` values of `ClassExoticMethods(...)` etc.
- Port code under `#ifdef CONFIG_*` options that are on by default (check the top of
  quickjs.c); leave out the `DUMP_*` debug blocks.
- The interpreter's structure (two nested loops instead of computed goto, the frequent
  opcodes' fast paths in the loop, one noinline function per other opcode body taking
  the InterpState) is explained in the header of `interpreter.lucb`.

## Tests

- `./test.sh` runs every module's unit tests and then QuickJS's own JavaScript tests
  (`tests/run.py`, through the `ljs` runner built in `build/ljs`). A test run must be
  green before a change is committed; never commit on a pipeline whose exit status is not
  the test's own.
- Every support module has unit tests in its `tests*.lucb` fragments, driven by the
  upstream behaviour: port the C test tables where upstream has them, otherwise write cases
  that pin the C results (compile the C and compare when in doubt).
- test262: `python3 tests/test262.py` clones tc39/test262 at the commit QuickJS pins
  (outside the repository, `../.test262` or `$LUCE_JS_TEST262`, linked from
  `tests/test262`), applies `tests/test262.patch`, builds `build/run-test262` and runs the
  suite with `tests/test262.conf`. The expected result is QuickJS's own:
  `58/83558 errors, 3356 excluded, 6000 skipped`, the 58 being exactly
  `tests/test262_errors.txt`. `--no-build` reuses the runner; `--direct` runs one
  threaded runner as `make test2` does. A test that fails in luce-js and not in QuickJS
  (a line that is not in `tests/test262_errors.txt`) is a port or compiler bug; reduce it,
  fix it, and add the reduction to `tests/js/test_conformance.js`. A test that traps is
  reported as CRASH by the split run.

## Language bugs

When the compiler rejects correct code, crashes, or miscompiles: reduce it to the smallest
program that shows it, keep the reduction in `docs/compiler-issues/`, work around it in the
port with a `# workaround: compiler-issues/NAME` comment, and report it. The compiler is
not changed from this repository. When the compiler is fixed, remove the workaround and
its reduction.

## History

The port was written region by region: the engine started as its shared types, the
generated tables and one stub fragment per region of quickjs.c (every C function with a
generated signature and a `trap("unported: NAME")` body), and each region replaced its
stub with real fragments while the module kept type-checking. No stub is left; the
region-by-region workflow no longer applies. `docs/namemap.txt` is the name table that
workflow generated (`tools/namemap.py`, from a list of quickjs.c's functions); it still
gives the Luce name of every quickjs.c function whose name changes.
