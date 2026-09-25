# luce-base compiler requests

The changes the luce-js (QuickJS) and luce-browser (Ladybird) ports need from luce-base, in
priority order, each with an inline reproduction so it can be worked on from any machine.
Evidence and profiles for the performance items are in `docs/PERFORMANCE.md` ("What only the
compiler can close"). The gate for any backend change: luce-js `./test.sh` passes and
`python3 tests/test262.py` prints `Result: 58/83558 errors` with 0 crashes.

Status as of 2026-09-25. Fixed items move to the bottom list with the fixing commit.

## Open

### 1. Checking an integer-backed enum is cubic in its number of cases (front end)

`luce-base check` of an `enum ... as u16` with explicit values: 200 cases 0.10 s, 400 0.79 s,
800 6.3 s, 1600 51 s (×8 per doubling). A plain enum or an 800-field struct checks in 0.02 s.
Ladybird's generated CSS enums have 850 (Keyword) and 409 (PropertyID) cases, so the browser's
css module takes ~9 s to check and every module importing it pays that again (9 of the
engine's 12 s).

```luce
pub enum Big as u16:
    case_0 = 0
    case_1 = 1
    # ... generate case_N = N up to case_799 = 799
```

Expected: linear (or n log n) time, like a plain enum.

### 2. Fallible results are returned through memory with a call to memcpy (backend)

Every `T!` return builds the result record in the frame and copies it to the caller with
`bl memcpy` (48 bytes for `Value!`, 32 for `!`/`bool!`), on the success path too.
`_platform_memmove` is 8.6% of all luce-js microbench samples and 13–16% of string code.

```luce
let exc: ErrorCode = ErrorCode.package(1)
struct V:
    var a: u64
    var b: i64
noinline func f1(x: i64) -> V!:
    if x == 3:
        error(exc, "bad")
    return V(a = 1, b = x)
noinline func f2(x: i64) -> !:
    if x == 3:
        error(exc, "bad")
```

Actual (arm64, `--release`): f1 ends `mov x2, #0x30; bl memcpy`, f2 `mov x2, #0x20; bl memcpy`.
Expected: the value in registers with the failure flag in a register, or at least an inline
copy of the few words.

### 3. Parameters are always spilled; large functions hoist and spill addresses (backend)

Every function stores its register parameters at entry and reloads them at first use. Large
functions compute the address of each local/field/global they use at entry and keep it in a
stack slot (`add x9, x19, #0x80; str x9, [sp, #0x38]`), reloading it at each use; the prologue
saves all ten callee-saved registers. luce-js's js_call_internal does 74 stores before its
first opcode; an empty JS call costs 983 instructions against 242 in C QuickJS.
Expected: parameters used from their registers, addresses formed at the use
(`[x19, #0x80]`), only the callee-saved registers that are used saved.

### 4. The inliner stops at 32 instructions and ignores `inline` (backend)

A function is expanded only when its optimised body is at most 32 instructions, `inline` or
not; each `trap` path adds about 5 instructions toward that limit; a function whose only call
is on a cold path is never a leaf. Expected: honour `inline` (up to a generous limit), and
count cold trap/call paths less.

### 5. Constant-expression top-level `let`s are not folded (backend)

```luce
let a: i32 = 3 << 4
let b: i32 = 48
noinline func fa(x: i32) -> i32:
    return x & a
noinline func fb(x: i32) -> i32:
    return x & b
```

Actual: `fa` loads `a` from memory (`adrp; add; ldrsw`), `fb` uses an immediate; in large
functions the address is also hoisted and spilled. Expected: both use `#0x30`.
(luce-js works around it by writing its flag constants as literals.)

### 6. Stack slots are not shared between call sites of f-string arguments (backend)

Frame-home sharing (9852cbf, fixed in 8eb0c28) helped plain locals, but each f-string argument
still reserves its own ~1.1 KB buffer, so frames grow with the number of call sites:

```luce
noinline func sink(n: i32, message: fmt) -> i32!:
    var buf: u8[64] = ---
    let t = try format(buf, message)
    return (i32)t.length + n
func fwd(message: fmt) -> i32!:
    return try sink(1, message)
func fstr3(x: i32) -> i32!:
    if x > 5:
        return try fwd(f"value {x}")
    if x > 6:
        return try fwd(f"value2 {x}")
    if x > 7:
        return try fwd(f"value3 {x}")
    return x
```

Actual: `fstr3` has a 3552-byte frame (400 bytes with plain string literals). The engine's
parser frames are 0.5–5 KB, so luce-js raises QuickJS's default JS stack from 1 MB to 4 MB.
Expected: one buffer per disjoint path, or share them like other slots.

### 7. Small values and optional results are copied through stack temporaries (backend)

`Value` (16 bytes) and `T?` results/arguments go through a stack slot and a copy instead of
registers. Lower priority than 2–4; measure after those.

### 8. `luce-base fmt` refuses `u8[128]*` (formatter)

```luce
func convert_unsigned_to_string(value: u64, buffer: u8[128]*) -> usize:
    return 0
```

`check` accepts it; `fmt` exits 1 with "the layout reads back as a different tree".
`(u8[128])*` formats fine. Expected: `fmt` prints a spelling that reads back as the same type.

### 9. Diagnostics in directory modules use concatenated line numbers (tooling)

`luce-base check -W` on a directory module reports warnings as `module:9889:1` (the line in the
fragments' concatenation) instead of `fragment.lucb:LINE:COL`, so every warning has to be mapped
by counting ORDER. Expected: the fragment file and its own line, as for errors.

### 10. `luce-base test` compiles every function of the module under test (tooling)

A test build keeps every function of the tested module, so a function whose body calls a
platform-only extern (e.g. `malloc_usable_size` on Linux, `_msize` on Windows) fails to link
on the other platforms unless its body is wrapped in `if platform.X:`. `build` prunes what is
unreachable. Expected: prune unreferenced non-test functions in test builds too, or document
the rule.

### 11. The interpreter's start-up is quadratic in the length of a global array literal (interpreter)

`luce-base test` (interpreted) of a module with one `let big: u16[24000] = [...]` takes 3.5 s
(6000 elements 0.38 s, 12000 1.1 s, ×3 per doubling); `check` takes 0.05 s and
`test --native` 0.2 s. LibTextCodec's encoding indexes (~85k entries) make every interpreted
test run of that module take 35 s before the first test.

```luce
let big: u16[24000] = [0, 7, 14, 21, 28]   # ...continue to 24000 elements
test "first":
    assert(big[1] == 7)
```

Expected: linear, like the native build. (luce-browser runs that module's tests `--native`.)

## Done on a branch, waiting for merge and release

- **Dense `match` → jump table; u8 match subject kept in a register; `(i32)`/`(i64)` float
  casts as one instruction** (fcvtzs / cvttsd2si with fix-ups): luce-base branch
  `perf-match` a84393d. ljs instruction counts −10…−45% per benchmark. Narrow and unsigned
  saturating float casts still call the helper.

## Fixed

- 0450da6: nullable pointer conversions; `sp[-1]`; `p += n`; storing `&local` through a
  pointer read from a parameter's field; optional fallible function-pointer adapter.
- 25914a4: `(const (T*)*)p` cast; bare `return` in a parenthesised catch handler; extern
  function addresses in constant tables; C-backend conditional constants and bool casts;
  inner `break` taken as leaving the outer loop; one diagnostic after a type error; fmt keeps
  commented array rows. Spec decisions: `&self` in mutating methods, `b"…"` is `const u8[]`,
  an untyped range is `i64`.
- a3f279e: C backend writes negative enum cases as signed literals.
- aee68f1: dense `match` binary search (superseded by the jump table above).
- 9852cbf / 8eb0c28: frame-home sharing, with the call-argument escape fix.
- 1645e01: small leaf functions inlined after optimisation.
