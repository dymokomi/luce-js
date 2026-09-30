# luce-base compiler requests

The changes the luce-js (QuickJS) and luce-browser (Ladybird) ports need from luce-base, in
priority order, each with an inline reproduction so it can be worked on from any machine.
Evidence and profiles for the performance items are in `docs/PERFORMANCE.md` ("What only the
compiler can close"). The gate for any backend change: luce-js `./test.sh` passes and
`python3 tests/test262.py` prints `Result: 58/83558 errors` with 0 crashes.

Status as of 2026-09-30 (Luce 0.8.25). Numbers are stable, so fixed items leave gaps. Bugs are reported to the LUCE_BASE_ONLY_MACHINE session. Items 2–12 are ordered by priority; 13 onwards were found by the
luce-browser ports (correctness first) and are not yet ranked against them. Fixed items move to the bottom list with the fixing commit.

## Open

### 2. Fallible results are returned through memory (backend, remaining part)

Luce 0.8.12 copies a fallible result inline instead of calling memcpy. Returning a small
`T!` in registers, with the failure flag in a register, is the remaining part (an ABI
change). `Value!` is 48 bytes today.

### 3. Windows x64 still spills parameters at entry (backend, remaining part)

Luce 0.8.12 uses parameters from their registers on arm64 and System V, forms frame
addresses at their use, and saves only the callee-saved registers it uses. The Windows x64
calling convention still stores parameters at entry.

### 7. Small values and optional results are copied through stack temporaries between calls (backend)

`Value` (16 bytes) and `T?` results/arguments go through a stack slot and a copy instead of
registers. Lower priority than 2–4; measure after those. The tiny-skia port measured passing
32-byte values between functions 3–6× slower than 16-byte ones; its pipelines are 5–30× slower
than tiny-skia (tests/raster/bench.lucb in luce-browser-render).

Within a function, Luce 0.8.25 (luce-base 0.32.0, 77924d8) keeps a small struct whose address
stays in the frame in registers, a field each (the `split` pass), including the arguments
and results of the calls it expands; what remains of item 7 is the calling convention,
item 2's ABI change.

## Fixed

Luce 0.8.13 (luce-base 6af76f1; the commits below were gated on arm64 macOS against luce-js
(test262 58/83558, 0 crashes), luce-regex (both backends) and every luce-browser package before
the release; the repositories here still pin 0.8.12 until they adopt it):
- 63b2798: item 27. print/trap f-strings stream with no limit, and a `fmt`/Writer f-string keeps
  1024 bytes ending in "...".
- d9c6dc7: items 12 (asm callee-saved registers saved), 13 (float methods through a pointer),
  14 (`sizeof(T)` per instance), 15 (C backend `&local_array`), 17 (`indexed()` loops don't
  allocate), 21 (`check -W` exits 1 on warnings), 22 (range facts indexed: 2000 checks
  27 s → 0.9 s), 23 (`check --target`; branches ruled out by a target constant don't warn);
  build.sh fetches luce-std at its own pin.
- eca8ab7: items 5 (integer constant lets fold), 9 (warnings name the fragment and line),
  10 (test builds compile only what tests reach), 16 (C backend `-ffp-contract=off`),
  18 (generic function values), 19, 20, 24, 25 (`const T[N]*`), 26 (`mul_add` on f32/f64
  and their vectors); C-backend test bodies get format buffers (the luce-regex regression);
  a global initialised with `~` compiles in the C backend.

Still open: 2, 3, 7 (ABI work).

Luce 0.8.25 (luce-base 0.32.0 and 0.32.1):
- item 6: the format buffers of f-strings passed as `fmt` or printed are pooled per
  function and given back when their statement ends, so disjoint statements share one:
  `fstr3`'s frame 3424 → 1328 bytes.
- item 7, within a function: small structs live in registers (see item 7 above).
- item 11: measured at 0.56 s for the 24000-element array (3.5 s before); linear.
- small methods of other modules (a Vector3's `cross`, `math.max`, a `length` calling the
  C library) are expanded at --opt 2 and 3.

- Luce 0.8.12 (luce-base ca67a3e):
  - Dense `match` is a jump table; a u8 match subject stays in a register; `(i32)`/`(i64)`
    float casts are one instruction (perf-match).
  - Fallible results copied inline (ljs memcpy calls 7193 → 901); parameters used from their
    registers (arm64, System V); frame addresses formed at their use; `inline` honoured up
    to 1024 instructions, traps not counted (perf-calls). ljs fib 15.11G → 12.21G
    instructions; microbench geometric mean 4.75 → 2.86 × qjs.
  - Integer-backed enum checks are linear (800 cases 6.9 s → 0.02 s); `fmt` accepts
    `u8[128]*` (check-fixes).
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
