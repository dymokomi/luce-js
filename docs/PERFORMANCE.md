# Performance of luce-js

luce-js runs the same bytecode as C QuickJS with the same algorithms, so its speed against
`qjs` measures two things: what the port adds on top of the C (checked arithmetic, fallible
results, bounds checks, calls where C inlines) and what the luce-base compiler makes of the
code. This document gives the benchmarks, how to run and profile them, the current numbers,
the techniques the port uses on its hot paths, and the gaps that only the compiler can
close, with the evidence for each.

## Benchmarks

- `tests/bench/*.js`: seven small programs, one per hot path of the interpreter:
  `fib` (recursive calls), `loop_sum` (a counted loop over locals), `array_ops` (push and
  indexed reads and writes), `closure_calls` (calls of closures reading and writing a
  captured variable), `property_access` (get_field/put_field on objects of one shape),
  `method_calls` (method calls through the prototype with `this` field access) and
  `string_concat` (building strings with `+=`).
- `tests/bench/microbench.js`: upstream's `tests/microbench.js` (MIT, unchanged): about 70
  microbenchmarks, each timed as nanoseconds per operation.

## How to run

```sh
# the seven programs: best wall time of --runs runs with each engine, and the ratio
QJS=/path/to/qjs tests/bench.py [--runs 5] [--save after.json] [--compare before.json] [name ...]
# microbench.js (about four minutes): ns per operation with each engine, ratio, geometric mean
QJS=/path/to/qjs tests/bench.py --micro [--save F] [--compare F] [name-prefix ...]
```

`tests/bench.py` builds `build/ljs-release` (`luce-base build tests/ljs.lucb --release`)
unless `--no-build` is given. `qjs` is upstream's, built with its Makefile.

Wall times move by 5-10% with the machine's load. For a comparison of two builds, the
instruction and cycle counts of `/usr/bin/time -l` (macOS) are steadier than the time:

```sh
/usr/bin/time -l build/ljs-release tests/bench/fib.js 2>&1 | grep -E "instructions|cycles"
```

Profiling (macOS): build with symbols and line tables, then sample the process:

```sh
luce-base build tests/ljs.lucb -o build/ljs-prof --release --debug
build/ljs-prof tests/bench/fib.js & sample $! 3            # functions, by call tree
xcrun xctrace record --template 'Time Profiler' --output t.trace --launch -- build/ljs-prof x.js
xcrun xctrace export --input t.trace --xpath '/trace-toc/run[@number="1"]/data/table[@schema="time-profile"]'
```

The xctrace export gives the address of every sample; `atos -o build/ljs-prof -l
0x100000000 ADDR...` maps them to source lines, and `objdump -d --no-show-raw-insn
--disassemble-symbols=_lb_14luce_js_engine_16js_call_internal build/ljs-release` shows the
code. The numbers below were taken this way (arm64, macOS, Apple M-series).

## Current numbers

Measured with Luce 0.8.12 (luce-base ca67a3e: jump-table matches, fallible results copied
inline, parameters used from their registers, frame addresses formed at their use, `inline`
honoured, one-instruction float casts). `before` is the same port built with Luce 0.8.11
(luce-base 8eb0c28) in the microbenchmark table; qjs and `ljs now` are from one run. Times move by 5-10% with the
machine's load.

The seven programs, best of 5 runs (seconds; `42675e4` is the port before the first
performance round, `0.8.11` the port after it, built with Luce 0.8.11, from an earlier run):

| benchmark | qjs | ljs 42675e4 | ljs 0.8.11 | ljs now | ljs/qjs now | speed-up over 0.8.11 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fib | 0.221 | 0.948 | 0.734 | 0.476 | 2.2 | 1.54 |
| loop_sum | 0.324 | 0.689 | 0.737 | 0.357 | 1.1 | 2.06 |
| array_ops | 0.171 | 0.862 | 0.573 | 0.347 | 2.0 | 1.65 |
| closure_calls | 0.094 | 0.500 | 0.344 | 0.218 | 2.3 | 1.58 |
| property_access | 0.137 | 0.829 | 0.293 | 0.185 | 1.3 | 1.58 |
| method_calls | 0.136 | 1.047 | 0.470 | 0.316 | 2.3 | 1.49 |
| string_concat | 0.211 | 1.181 | 1.211 | 0.738 | 3.5 | 1.64 |

microbench.js, ns per operation. Geometric mean of ljs/qjs over the 71 microbenchmarks:
**6.0 at 42675e4, 4.75 with Luce 0.8.11, 2.86 with Luce 0.8.12**. A selection (the rest are
between 1.1 and 8 times qjs; run `tests/bench.py --micro` for all):

| microbenchmark | qjs | ljs before | ljs now | ljs/qjs now | speed-up |
| --- | ---: | ---: | ---: | ---: | ---: |
| empty_loop | 5.56 | 13.35 | 7.09 | 1.3 | 1.88 |
| date_now | 21.20 | 71.48 | 54.32 | 2.6 | 1.32 |
| prop_read | 6.47 | 13.38 | 7.16 | 1.1 | 1.87 |
| prop_update | 7.65 | 15.73 | 8.65 | 1.1 | 1.82 |
| array_length_read | 6.47 | 14.44 | 7.40 | 1.1 | 1.95 |
| array_push | 19.18 | 108.08 | 60.12 | 3.1 | 1.80 |
| func_call | 12.90 | 50.75 | 32.70 | 2.5 | 1.55 |
| func_closure_call | 13.15 | 52.20 | 32.30 | 2.5 | 1.62 |
| float_arith | 13.20 | 29.28 | 16.02 | 1.2 | 1.83 |
| map_set_int | 58.78 | 322.80 | 214.00 | 3.6 | 1.51 |
| math_min | 16.00 | 69.42 | 36.39 | 2.3 | 1.91 |
| regexp_ascii | 94.40 | 667.00 | 416.00 | 4.4 | 1.60 |
| regexp_replace | 385.30 | 1561.50 | 966.00 | 2.5 | 1.62 |
| string_length | 7.03 | 25.97 | 18.15 | 2.6 | 1.43 |
| int_toString | 25.57 | 175.00 | 109.67 | 4.3 | 1.60 |
| prop_create | 25.54 | 167.00 | 89.45 | 3.5 | 1.87 |
| string_build3 | 26.65 | 177.60 | 96.72 | 3.6 | 1.84 |
| array_for_of | 12.31 | 161.80 | 99.38 | 8.1 | 1.63 |
| global_destruct | 19.56 | 235.50 | 145.00 | 7.4 | 1.62 |
| bigint64_arith | 23.70 | 243.00 | 146.85 | 6.2 | 1.65 |

Property, array and global access and int/float arithmetic are now within 1.1-1.4× of qjs.
The largest remaining ratios (array_for_of, destructuring, arguments, bigint, Map, regexp
execution) are listed under "Remaining port-side gaps" and the open compiler items below.

## What the port does on its hot paths

The interpreter's structure (the dispatch loop's fast paths, the outlined opcode bodies on
an `InterpState`, the frame budget) is described in the header of `interpreter.lucb`. The
techniques, each checked against the generated code:

- **The frequent opcodes run in the dispatch loop**, as C's loop runs them: the stack,
  locals, arguments and closure variables, the jumps, int arithmetic and comparisons,
  number arithmetic and comparisons with a float operand (add, sub, mul, the comparisons;
  add_loc on two floats), mod on two non-negative ints, `push_this` of an object, the
  named-property opcodes (`get_field`, `get_field2`, `get_length`, `put_field`) with
  find_own_property's hash-chain walk written out, the elements of fast arrays
  (`get_array_el`, `get_array_el2`, `get_array_el3`, `put_array_el`) and the calls. A case
  a fast path does not take has changed nothing and falls through to the opcode's full
  body, so the slow path is C's code unchanged (`tests/js/test_fast_paths.js` checks both
  sides of each).
- **No values, helpers or fallible calls in the loop's arms**: values are written as tag
  and payload where they lie and reference counts tested in place, so an arm adds no frame
  slot. js_call_internal's frame is the stack one level of JavaScript recursion takes
  (1.3 KB): recursion goes 3000 levels deep in the default 4 MB stack.
- **Calls**: a C function's class hook is called by js_call_internal before any frame is
  set up, as JS_CallInternal does, and js_call_c_function_frame dispatches on the calling
  shape itself. interp_enter takes the call from the InterpState js_call_internal filled
  (parameters spill to the stack at every entry) and walks the frame with pointers;
  interp_call_done and interp_leave release values in place.
- **Hot helpers stay inlinable**: the native inliner expands a function of up to 32
  instructions. A trap (`else trap`, a checked `+`, a bounds-checked index) adds a call and
  about five instructions, so the hot helpers read as C reads: `var_ref_at` reads the
  closure variables without the nullable checks, the reference-count helpers address the
  count by integer arithmetic, find_own_property uses wrapping arithmetic.
- **A workaround for a compiler gap** (below): the engine's flag constants are written as
  literals.
- **A regular expression literal compiles once**: its program is kept by the function
  (FunctionBytecode.regexp_cache) and shared by the RegExp objects it makes, as QuickJS's
  objects share the bytecode string compiled with the function (regexp_bridge.lucb). Before,
  every evaluation of a literal compiled the pattern: 3.4 us per `/re/.exec(s)` in a loop,
  now 1.0 us.

Tried and left out, because the generated code or the time did not improve: an `Op` enum
backed by u32 (to keep the dispatch subject in a register; the binary search dominates),
reaching the InterpState through a pointer local (the same code), a string-concatenation
arm in the loop (the frame grew by 208 bytes for no measurable gain), and computing the
small-block size in js_malloc_raw inline.

A note on measuring: an edit anywhere in js_call_internal moves the code of the dispatch
loop, and the time of a loop benchmark moves with it by up to 5% (cycles, with the same
instruction count). Compare instruction counts before concluding.

## What only the compiler can close

Measured on `build/ljs-release` (luce-base 8eb0c28, arm64 macOS). The instruction counts
come from `/usr/bin/time -l`: per fib call, ljs runs 1420 instructions and qjs 358; ljs
retires them at 6.2 instructions per cycle and qjs at 5.5. The gap is the number of
instructions, not stalls, and the items below are where those instructions come from.

**Status with Luce 0.8.12:** items 1, 2 and 6 are fixed (the float-cast workaround is
removed); 3 is fixed as an inline copy (results in registers remain an ABI change); 4 is
fixed on arm64 and System V (Windows x64 still spills parameters); 5 is fixed (`inline`
honoured up to 1024 instructions, traps not counted). 7 and 8 remain open. The analyses
below are kept as they were measured on 8eb0c28; the live list is docs/COMPILER-REQUESTS.md.

### 1. `match` is a binary search, not a jump table

The dispatch loop's `match op:` over the `Op` enum (about 120 arms, the rest in `_`)
lowers to a tree of compare-and-branch. Walking the generated tree for 13 hot opcodes,
one dispatch executes 31-38 instructions with 6-8 conditional branches before the arm's
first instruction. C's computed goto is 3 (`ldrb`, `ldr` from the table, `br`).

- Share: the `match op:` line (interpreter.lucb, the dispatch) takes 63% of
  js_call_internal's samples over the whole of microbench.js, 22% of all samples; 47% of
  js_call_internal's samples (29% of all) in fib.
- Per operation: an empty loop iteration (6 opcodes) is 353 instructions in ljs, 88 in qjs;
  `x = x + 1` (4 opcodes) is 121 against 39.
- Reduction:

  ```luce
  enum Op as u8:
      a = 0
      b = 1
      c = 2
      d = 3
  noinline func run(code: const u8*, n: i64) -> i64:
      var pc = code
      var acc: i64 = 0
      var i: i64 = 0
      while i < n:
          let op = (Op)*pc
          pc += 1
          match op:
              .a:
                  acc += 1
              .b:
                  acc += 2
              .c:
                  acc -= 1
              .d:
                  pc = code
              _:
                  acc += 5
          i += 1
      return acc
  ```

  Expected: a bounds test and an indirect branch through a table of arm addresses (dense
  cases; the Op values are 0..243). Actual: `mov x10, #2; cmp w12, w10; b.hs ...;
  mov x10, #0; cmp w12, w10; b.eq ...` down the tree.
- Expected gain: the largest single item. Dispatch is about 35 of the 55-60 instructions of
  a simple opcode; a jump table would bring the loop benchmarks (loop_sum 2.4x, empty_loop
  2.6x) close to C and every other benchmark down by a quarter or more.

### 2. A u8 match subject goes through memory twice

In the same reduction, `let op = (Op)*pc` is stored to its stack slot, reloaded, stored to
a second slot for the match and reloaded again before the first compare (`strb; ldrb;
strb; ldrb`, with the slot addresses themselves reloaded from spill slots: 8 instructions
and two store-to-load forwards on the path to every branch of the dispatch). With an
`i32`/`i64`-backed enum the compares read the register (the two stores remain, dead).

- Expected: the loaded byte stays in a register (`ldrb w12, [x14]; cmp w12, ...`).

### 3. Fallible results are returned through memory with a call to memcpy

Every function returning `T!` builds its result record in its frame and copies it to the
caller's buffer with a call to memcpy: 48 bytes for `Value!`, 32 bytes for `!` and
`bool!`, on the success path too; the caller then copies the value out again.

- Share: `_platform_memmove` is 8.6% of all samples over microbench.js (plus 0.9% in the
  `memcpy` stub), 13-16% in string_concat, 14% in array_for_of, 12% in array_pop. The
  callers are the whole engine: js_array_cmp_slots, js_call_internal, js_concat_string1,
  js_call_c_function, js_get_property_internal, js_malloc, js_get_property_value,
  js_to_number_hint_free, ... (every `Value!` and `i32!` return).
- Reduction:

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

  Actual: f1's success path ends `mov x2, #0x30; bl memcpy`, f2's `mov x2, #0x20; bl
  memcpy`. Expected: the value in `x0`/`x1` with the failure flag in a register (or at
  least an inline copy of the few words into the `x8` buffer).
- Expected gain: 8-16% on builtin-heavy code, more once item 1 is fixed.

### 4. Every entry spills the parameters, and large functions spill hoisted addresses

Each function stores its register parameters to the stack at entry and reloads them at
their first use (find_own_property: three stores and three loads before its first
comparison). Large functions also compute the address of every local, field and global
they use at entry and keep each in a stack slot (`add x9, x19, #0x80; str x9, [sp, #0x38]`
for `&st.opcode`, several times over), then reload the address at each use; the
prologue saves all ten callee-saved registers.

- js_call_internal, which every JavaScript call enters: about 400 instructions from the
  entry to the first dispatch (static count of the path, including interp_enter's call),
  with 74 stores before the first opcode. An empty JavaScript function call (`f()` in a
  loop) costs 983 instructions in ljs and 242 in qjs.
- Share: js_call_internal outside the dispatch line, interp_enter, interp_leave and
  interp_call_done are 40% of the samples of the call loop above.
- Expected: parameters used from their registers; addresses formed at the use
  (`[x19, #0x80]` addressing); only the callee-saved registers the function uses saved.

### 5. The inliner stops at 32 instructions, `inline` included

A function is expanded only when its optimised body is at most 32 instructions, whether
or not it is declared `inline`. get_field_inline (GET_FIELD_INLINE, `inline` in the
source) and the shape lookups are called out of line; each trap (`else trap`, checked
arithmetic, a bounds check) adds about five instructions and makes a small helper too
large. The port keeps its hot helpers under the limit by hand (see above).

- Expected: `inline` honoured (C's `force_inline`), or a larger limit for single-call-site
  and hot helpers; traps kept out of line so that they do not count against the budget.

### 6. Float-to-integer casts are calls (fixed in Luce 0.8.12)

`(i32)d`, `(i64)d` and `i32(d)` lower to a call of std/core's `f_to_s` (about 60
instructions with its frame) where arm64 has `fcvtzs` (which already saturates and maps NaN
to 0). JS_NewFloat64 runs it for every number result: 1.9% of a loop of Math.abs calls.
Luce 0.8.12 emits `fcvtzs` / `cvttsd2si`, and the port's `f64_to_i32_small` workaround is gone.

### 7. Constants initialised by an expression are not folded (worked around)

`let a: i32 = 3 << 4` becomes a global initialised at startup and loaded at every use
(`adrp; add; ldr`), and large functions hoist and spill its address; `let b: i32 = 48` is
an immediate. js_call_internal's prologue spilled the addresses of prop_tmask,
prop_writable and prop_length. Reduction and workaround:
`docs/compiler-issues/constant-let-not-folded.lucb`.

### 8. Small values are copied through temporaries

A 16-byte `Value` built by a helper (`js_undefined()`, `js_new_int32(...)`) or assigned
from a field goes through two or three stack temporaries (`stp xzr, xzr, [x19]; ldp ...;
stp ...` chains), and optional results (`usize?`) are returned through the stack
(small_block_total_size, on every js_malloc). The port writes values as tag and payload in
its hot paths for this reason.

## Remaining port-side gaps

Beyond the compiler items, the largest ratios in microbench.js are:

- `regexp_ascii`/`regexp_utf16` (about 7x now, 39x before the literal sharing): the match
  itself is luce-regex's engine (a separate package), about 5x slower per exec than
  libregexp.
- `array_for_of`, the destructuring benchmarks, `array_pop`, the BigInt and number
  formatting benchmarks (8-14x): long chains of small fallible calls (iterator next, length
  and element reads, ToString), where items 3, 4 and 5 compound; their C code is ported as
  it is.
