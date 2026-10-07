# luce-base compiler requests

The changes the luce-js (QuickJS) and luce-browser (Ladybird) ports need from luce-base, in
priority order, each with an inline reproduction so it can be worked on from any machine.
Evidence and profiles for the performance items are in `docs/PERFORMANCE.md` ("What only the
compiler can close"). The gate for any backend change: luce-js `luc test` passes; its
`tests/test262_suite` holds `python3 tests/test262.py` to `Result: 58/83558 errors` with 0 crashes.

Status as of 2026-10-01 (Luce 0.8.30). Numbers are stable, so fixed items leave gaps. Bugs are reported to the LUCE_BASE_ONLY_MACHINE session. Every request is fixed; new ones go under Open with an inline reproduction.

## Open

None.

## Fixed

Luce 0.8.30 (luce-base 0.32.6), gated against luce-js (`./test.sh`, and test262 58/83558 with
0 crashes at QuickJS's 1 MB stack):
- item 2: a fallible result of up to four words comes back in registers (x0-x3 on arm64,
  rax/rdx/rcx/r8 on x86-64) with its failure flag, and the Error in the thread's
  `core.failure`; a failure passed up is not copied again. js_parse_primary_expr's frame
  1536 -> 224 bytes, js_parse_expr_binary 304 -> 128; the parser takes 300 nested function
  expressions at 1 MB (about 110 before, QuickJS 256) and recursion reaches about 1150
  levels. js_default_stack_size is QuickJS's 1 MB again.
- item 3: Windows x64 receives its first four scalar parameters straight from their
  registers and saves only the nonvolatile registers a function names.
- item 7: small aggregates of integer words (up to 16 bytes; 8 on Windows) are passed and
  returned in registers between calls, as within a function since 0.8.25.
- frames pack their slots by life (first fit), and a statement's format buffers live below
  the frame only while the statement runs (compiler-issues/frame-slots-not-shared, removed).

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
