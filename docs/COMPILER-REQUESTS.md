# luce-base compiler requests

The changes the luce-js (QuickJS) and luce-browser (Ladybird) ports need from luce-base, in
priority order, each with an inline reproduction so it can be worked on from any machine.
Evidence and profiles for the performance items are in `docs/PERFORMANCE.md` ("What only the
compiler can close"). The gate for any backend change: luce-js `./test.sh` passes and
`python3 tests/test262.py` prints `Result: 58/83558 errors` with 0 crashes.

Status as of 2026-09-25. Items 1–12 are ordered by priority; 13 onwards were found by the
luce-browser ports (correctness first) and are not yet ranked against them. Fixed items move to the bottom list with the fixing commit.

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
registers. Lower priority than 2–4; measure after those. The tiny-skia port measured passing
32-byte values between functions 3–6× slower than 16-byte ones; its pipelines are 5–30× slower
than tiny-skia (tests/raster/bench.lucb in luce-browser-render).

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

### 12. `asm` clobbering a callee-saved register does not save it (backend)

An `asm` block declaring a callee-saved register destroyed (`out("x19") _`, or rbx/r12–r15 on
x86-64) does not make the function save and restore it, so the caller's value is lost.
Found by luce-browser's LibGC port (register-spill test of the conservative scan).

```luce
noinline func write_x19(marker: usize):
    asm arm64 (in("x9") marker, out("x19") _):
        mov x19, x9
    asm x86_64 (in("rax") marker, out("rbx") _):
        mov %rax, %rbx

test "a destroyed callee-saved register is preserved for the caller":
    var total: usize = 0
    for i in 0..<10:
        write_x19(0xdead)
        total += (usize)i
    assert(total == 45)
```

Actual: `test` stops with a signal; as a program, total == 57014 (0xdead + 9) — the prologue
saves only x29/x30. Expected: callee-saved registers named in `out(...)` are saved and restored.

### 13. Float methods through a pointer emit an invalid `mov s16, w14` (backend, arm64)

`key.bits()` (or any float method, including the compiler-supplied `Comparable.compare` in a generic body at f32/f64) on a float reached through a pointer emits a GPR→FP `mov`, which the assembler rejects: `gen.s: error: invalid operand for instruction mov s16, w14` (`mov d16, x14` for f64). Found by luce-browser r01 (AK). Workaround: load into a local first.

```luce
func h(key: const f32*) -> u32:
    return key.bits()

test "bits through a pointer":
    var x: f32 = 1.5
    assert(h(&x) == 0x3fc00000)

# The same happens for any method of a float called through a pointer, e.g. the compiler-supplied
# Comparable.compare in a generic body instantiated at f64 (`lhs.compare(*rhs)` with
# `lhs: const T*`): gen.s: `mov d16, x14`.
```

Expected: `fmov`, and the test passes.

### 14. `sizeof(T)` in a generic `if` condition is folded as 0 (front end)

In a generic function a constant condition over `sizeof(T)` is folded at declaration-check time, so every instantiation takes the same branch: pick(u32) = 1, pick(u64) = 1. Binding `let size = sizeof(T)` first works.

```luce
func pick[T](value: const T*) -> usize:
    if sizeof(T) % 8 == 0:
        return 1
    else:
        return 2

func pick_workaround[T](value: const T*) -> usize:
    let size = sizeof(T)
    if size % 8 == 0:
        return 1
    return 2

test "sizeof(T) in a generic if condition":
    let a = 1u32
    let b = 1u64
    print(f"pick u32 = {pick(&a)} (expected 2), pick u64 = {pick(&b)} (expected 1)")
    print(f"workaround u32 = {pick_workaround(&a)} (expected 2), u64 = {pick_workaround(&b)} (expected 1)")
```

Expected: pick(u32) = 2, pick(u64) = 1.

### 15. C backend: `&local_array` decays to the first element (C backend)

`luce-base build --backend=c` of `fill(&value)` with `var value: i32[2]` fails: `incompatible pointer types passing 'int32_t[2]' to parameter of type 'lb_a_i32_0a2 *'`. `&struct.array_field` is fine. Found by the tiny-skia port.

```luce
func fill(r: i32[2]*):
    (*r)[1] = 5

pub func main(arguments: str[]) -> i32:
    var value: i32[2] = [0, 0]
    fill(&value)
    print(f"{value[1]}")
    return 0
```

Expected: prints 5 in both backends.

### 16. C backend contracts `a * b + c` into an FMA (C backend)

The generated C is compiled with clang's default `-ffp-contract=on`, breaking the spec's "IEEE 754 with no contraction" (§7.2); the native backend prints 0, the C backend 864026624. The tiny-skia port must be bit-exact and so needs the native backend.

```luce
func muladd(a: f32, b: f32, c: f32) -> f32:
    return a * b + c

pub func main(arguments: str[]) -> i32:
    # (1 + 2^-12)^2 = 1 + 2^-11 + 2^-24: the last term is lost when a*b rounds to f32 first;
    # fused, it survives.
    let a: f32 = 1.000244140625
    let r = muladd(a, a, -1.00048828125)
    print(f"{r.bits()}")
    return 0
```

Expected: compile the generated C with `-ffp-contract=off`; prints 0 in both.

### 17. `for (i, x) in span.indexed()` leaks 48 bytes per loop (backend/runtime)

Each `.indexed()` loop allocates a 48-byte block through memory.heap that is never freed, whether the loop ends or is left by `return` (`leaks --atExit`: 5 leaks for 240 bytes). An index loop leaks nothing. Found by the tiny-skia port.

```luce
func count_large(values: const f32[]) -> usize:
    var n: usize = 0
    for (i, v) in values.indexed():
        if v > 5.0:
            n += i
    return n

pub func main(arguments: str[]) -> i32:
    var total: usize = 0
    for i in 0..<5:
        total += count_large([0.0, 2.0])
    print(f"{total}")
    return 0
```

Expected: no allocation, or it is freed.

### 18. A generic function cannot be used as a function value (front end)

Neither the expected type nor `negate[i64]` selects an instance: "expected `func(void*?, const i64*) -> bool`, got `func(void*?, const T*) -> bool`"; `negate[i64]` parses as indexing. Workaround: a static method of a generic struct (`Matcher[T].matches`).

```luce
func negate[T](context: void*?, value: const T*) -> bool:
    return context == none

func outer[T](value: T) -> bool:
    let callback: func(void*?, const T*) -> bool = negate
    return callback(none, &value)

test "generic function value at a concrete type":
    let callback: func(void*?, const i64*) -> bool = negate
    var v: i64 = 3
    assert(callback(none, &v))

test "generic function value inside a generic function":
    assert(outer[i64](3))
```

Expected: both tests pass, as for non-generic functions (§5.6).

### 19. One rejected `else` under `try` poisons every later `f() else ...` in the module (front end)

After the (correct) error for an `else` fallback under a surrounding `try`, every later `fallible() else ...` in the module gets the same error, so in directory modules the one real error is buried among spurious ones in later fragments.

```luce
let code: ErrorCode = ErrorCode.package(1)

func make(v: i32) -> i32!:
    if v < 0: error(code, "neg")
    return v

func throw_with(v: i32) -> never!:
    error(code, "thrown")

pub func first(v: i32) -> !:
    if v > 10:
        try throw_with(make(v) else trap("MUST"))

pub func second(v: i32) -> i32:
    return make(v) else trap("MUST")
```

Expected: one error, at the `else` under `try`.

### 20. A comment after `catch failure:` inside parentheses does not parse (parser)

`discard(fail() catch failure: # comment` → "expected the end of the line"; the same comment on its own line parses.

```luce
pub let failing: ErrorCode = ErrorCode.package(1)

func fail() -> i64!:
    error(failing, "no")

test "comment after catch in parentheses":
    var failed = false
    discard(fail() catch failure: # comment on the catch line
        failed = true
        recover 0)
    assert(failed)
```

Expected: a trailing comment does not change where the suite starts.

### 21. `luce-base check -W` exits 0 when it prints warnings (tooling)

A warning-free gate has to parse the output: `check -W` prints the warnings but still exits 0,
so `luce-base check -W mod && git commit` commits with warnings. luce-browser's test.sh works
around it by failing on any output. Expected: a non-zero exit when `-W` printed a warning (or a
`-Werror` flag).

## Done on a branch, waiting for merge and release (x86_64 runs on LINUX/WINDOWS pending)

- **Dense `match` → jump table; u8 match subject kept in a register; `(i32)`/`(i64)` float
  casts as one instruction** (fcvtzs / cvttsd2si with fix-ups): luce-base branch
  `perf-match` a84393d. ljs instruction counts −10…−45% per benchmark. Narrow and unsigned
  saturating float casts still call the helper.

- **Enum case check linear** (800 cases 6.9 s → 0.02 s) and **`fmt` accepts `u8[128]*`**
  (items 1 and 8 above): branch `check-fixes` d568164.
- **Fallible results copied inline instead of memcpy** (ljs memcpy calls 7193 → 901; item 2,
  partly: returning them in registers is an ABI change still to do), **parameters moved
  straight from their registers** (System V and arm64; not yet Windows x64), **frame addresses
  formed at their use** with base+offset folding (item 3), **`inline` honoured up to 1024
  instructions, traps not counted** (item 4): branch `perf-calls` fa4fc10 (includes
  perf-match). ljs: fib 15.11G → 12.21G instructions, empty-call loop 3.59G → 2.89G,
  string_concat 16.13G → 11.61G.

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
