# Testing luce-js on Windows

The host (`src/luce_js/host/`, quickjs-libc.c) and the test programs (`ljs`,
`run-test262`) follow quickjs-libc.c's `#if defined(_WIN32)` branches on
`x86_64-windows`. They were only cross-compiled and linked with MinGW-w64 on macOS;
these steps run them on Windows. Report every command's output where it differs
from the expected output below.

## 1. Checkouts

Use PowerShell in an MSYS2 UCRT64 setup where `luce-base.exe` has been built
(`../luce-base/docs/WINDOWS.md`: `python tools/build_windows.py`) and `gcc`, `git` and
`python` are on PATH. All repositories are siblings in one directory, and Git must not
convert line endings (the tests compare bytes and the errors file is read in binary):

```powershell
git config --global core.autocrlf false
cd C:\luce_dev          # the directory holding luce-base
git clone https://github.com/dymokomi/luce-std.git
git clone https://github.com/dymokomi/luce-regex.git
git clone -b work/windows https://github.com/dymokomi/luce-js.git
git -C luce-base checkout 8eb0c283b885fdc4ece93aead27ae1b530bbfc50   # or newer
git -C luce-std checkout 1ccc1e5cbbe599902ac534856496ec9c546d9909
git -C luce-regex checkout 292c1592945c9cde9b25a9d616f2a62911cb815d
git -C luce-js log --oneline -2
```

The last command must show `Add WINDOWS_TEST.md ...` above
`04888c1 Host and test programs on Windows: quickjs-libc.c's _WIN32 branches`. For an
existing checkout: `git -C luce-js fetch origin work/windows` then
`git -C luce-js checkout -B work/windows origin/work/windows`.

Put the compiler on PATH for the Python scripts:

```powershell
$env:PATH = "C:\luce_dev\luce-base\build;" + $env:PATH
luce-base --version
cd C:\luce_dev\luce-js
```

## 2. Build

```powershell
luce-base build tests/ljs.lucb -o build/ljs.exe
luce-base build tests/run_test262 -o build/run-test262.exe --release
.\build\ljs.exe -m -e "import * as os from 'os'; print(os.platform, typeof os.exec, os.O_BINARY, os.SIGABRT)"
```

Expected: both builds succeed without errors, and the last command prints
`win32 undefined 32768 22`.

## 3. Unit tests of each module

```powershell
luce-base test src/luce_js/cutils
luce-base test src/luce_js/dtoa
luce-base test src/luce_js/engine
luce-base test src/luce_js/host
```

Expected: every line `ok`, and for the host `13 passed`. Two host tests (os.exec and
signal/read handlers) return at once on Windows, where those functions do not exist;
`the os table has this target's functions and constants` and `mkdir, open, utimes,
stat, realpath, readdir and remove work together` exercise the Windows paths.

## 4. QuickJS's JavaScript tests

```powershell
python tests/run.py --no-build
```

Expected: 15 files (test_std.js and test_rw_handler.js are not run on Windows, as in
upstream's Makefile), ending with

```
15 files: 15 passed, 0 failed, 0 known failures, 0 unexpected passes
```

## 5. A test262 subset

Fetch and patch test262 once (git clone, `git apply`, and a junction at `tests\test262`):

```powershell
python tests/test262.py --fetch-only
python tests/test262.py --no-build --direct -- -c test262.conf -a -d test262/test/built-ins/Atomics
python tests/test262.py --no-build --direct -- -c test262.conf -a -d test262/test/built-ins/Array
python tests/test262.py --no-build --direct -- -c test262.conf -a -d test262/test/built-ins/RegExp
python tests/test262.py --no-build --direct -- -c test262.conf -a -d test262/test/language/module-code
python tests/test262.py --no-build --direct -- -c test262.conf -a -d test262/test/built-ins/Date
$env:TZ = "PST8PDT"
python tests/test262.py --no-build --direct -- -c test262.conf -a -d test262/test/built-ins/Date
Remove-Item Env:TZ
```

On macOS the last lines are:

| directory | result |
| --- | --- |
| built-ins/Atomics | `Result: 0/562 errors, 101 skipped` |
| built-ins/Array | `Result: 0/5929 errors, 95 skipped` |
| built-ins/RegExp | `Result: 0/3756 errors` |
| language/module-code | `Result: 4/577 errors, 17 skipped` |
| built-ins/Date | `Result: 0/1172 errors, 8 skipped` |

Windows prints one progress line per test instead of dots (run-test262 does not
check the tty there). Like upstream, it does not set `TZ=America/Los_Angeles` on
Windows, so the Date tests that assume California time may fail outside that zone;
the second Date run sets the CRT's `PST8PDT` instead. Send the error lines of any
run whose result differs.

## 6. Optional: the whole suite

```powershell
python tests/test262.py --no-build
```

On macOS: `Result: 58/83558 errors` with 0 crashes (split across processes). Report
the result line, the crashes, and the lines marked new or changed.
