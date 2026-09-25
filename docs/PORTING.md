# Porting QuickJS to luce-base

luce-js is a port of Fabrice Bellard's QuickJS (upstream `bellard/quickjs`, version
2026-06-04, commit `04be246`) to luce-base. It is a **faithful port**: the same data
structures, the same algorithms, the same bytecode, the same atoms, the same order of
functions, and the same comments where they still apply. It is not a redesign. When in
doubt, do what the C does, spelled the way luce-base spells it.

The language reference is `../luce-base/docs/language/base.md`; the standard library
reference is `../luce-base/docs/LIBRARY.md`. Read §5–§12 of the language before porting.

## Layout

| C source | Luce module | Directory |
| --- | --- | --- |
| `cutils.c`, `cutils.h`, `list.h` | `luce_js.cutils` | `src/luce_js/cutils/` |
| `dtoa.c`, `dtoa.h` | `luce_js.dtoa` | `src/luce_js/dtoa/` |
| `libunicode.c`, `libunicode-table.h` | `luce_js.unicode` | `src/luce_js/unicode/` |
| `libregexp.c`, `libregexp-opcode.h` | `luce_js.regexp` | `src/luce_js/regexp/` |
| `quickjs.c`, `quickjs.h`, `quickjs-atom.h`, `quickjs-opcode.h` | `luce_js.engine` | `src/luce_js/engine/` |

Every module is a directory whose `ORDER` file lists its fragments (language §16.1). The
fragments of one module share one scope, exactly like the one C file they came from, so a
`static` C function is a private Luce function visible to every fragment of its module.
Another module's declarations are reached with `import luce_js.cutils as cutils` in the
module's first fragment (imports in `module.lucb` apply to every fragment) and must be `pub`.

- Keep each fragment focused and under about 600 lines. Split along the C source's own
  sections, in the C source's order.
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

- Fragments over 150 lines use `# mark: Name ====...` section comments.
- Keep QuickJS's explanatory comments (as `#` comments), and give every `pub` declaration
  a `##` doc line.
- Tests live in a `tests.lucb` fragment at the end of the module's `ORDER` (tests may use
  private declarations). Run a module's tests with `luce-base test src/luce_js/<module>`.

## Names

- Functions: snake_case of the C name. A `JS_` prefix is dropped; a `js_` prefix is kept;
  leading underscores are dropped and `_raw` is appended. camelCase boundaries become
  underscores; `UInt`, `BigInt`, `JSON`, `RegExp`, `UTF8` read as one word each.
  - `JS_NewObject` → `new_object`, `JS_GetPropertyUint32` → `get_property_uint32`,
    `__JS_AtomToValue` → `atom_to_value_raw`, `js_array_lastIndexOf` →
    `js_array_last_index_of`, `js_bigint_asUintN` → `js_bigint_as_uint_n`,
    `JS_AddIntrinsicRegExp` → `add_intrinsic_reg_exp`, `dbuf_put_u32` → `dbuf_put_u32`.
  - The complete table of every function whose name changes is `docs/namemap.txt`
    (`CName luce_name`). Use it; do not invent names.
  - Two collisions are resolved by hand: the static `delete_property` becomes
    `delete_property_internal`; `js_bigint_toString` (the builtin method) becomes
    `js_bigint_to_string_method`.
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
- The support libraries (`cutils`, `dtoa`, `unicode`, `regexp`) keep QuickJS's C contracts:
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

## Tests

- Every support module has unit tests in its `tests.lucb`, driven by the upstream
  behaviour: port the C test tables where upstream has them, otherwise write cases that pin
  the C results (compile the C and compare when in doubt).
- The engine is tested by running upstream's `tests/*.js` and, later, test262.
- A test run must be green before a change is committed. Never commit on a pipeline whose
  exit status is not the test's own.

## Language bugs

When the compiler rejects correct code, crashes, or miscompiles: reduce it to the smallest
program that shows it, keep the reduction in `docs/compiler-issues/`, work around it in the
port with a `# workaround: compiler-issues/NAME` comment, and report it. The compiler is
not changed from this repository.
