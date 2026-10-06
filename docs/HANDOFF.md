# Handoff: luce-js and the luce-browser port

Start here when picking this work up on a new machine. The state below is as of 2026-10-06.
luce-js is the JavaScript engine of the Luce web browser. The browser is a faithful port of
Ladybird's LibWeb in the `luce-browser-*` packages, and `luced-browser` is the application.

## 1. What to check out

Every repository lives side by side in one directory. Packages refer to each other by
`../<name>` paths in `package.prisma`, and there are no commit pins: CI and local builds use
main of every dependency (luce-base `docs/CI.md`). To set up a workspace for one repository:

```sh
mkdir luce_dev && cd luce_dev
git clone https://github.com/dymokomi/luce-base
git clone https://github.com/dymokomi/luce-browser-engine     # or luce-js, luced-browser, ...
python3 luce-base/tools/checkout_main.py luce-browser-engine  # clones every path dependency at main
(cd luce-base && ./build.sh)
export PATH=$PWD/luce-base/build:$PATH
(cd luce-browser-engine && ./test.sh)
```

`checkout_main.py` clones what is missing and uses existing siblings as they are, so `git pull`
those yourself. A dependency in `package.prisma` carries no version; at release time it means
the newest release, recorded in `luc.lock`.

Reference sources ("donors") are for local comparison only and never go into these repositories:
- QuickJS, for luce-js: https://github.com/bellard/quickjs at `04be246` (VERSION 2026-06-04);
  `make qjs` gives the C engine that `tests/bench.py` compares against.
- test262: `tests/test262.py` fetches its own checkout at `5c8206929d` and applies QuickJS's patch.
- Ladybird (and the Skia, FreeType, skcms, libwebp, libpng and libjpeg-turbo it builds), for the
  browser: a reference build in `.donors/ladybird-pin`; see `luce-browser-tools/DONORS.md`.
  The C/C++ oracles that pin tests to them live in `luce-browser-tools/oracles/`.

## 2. Repositories

| Repository | What |
| --- | --- |
| luce-js | QuickJS 2026-06-04 in luce-base; test262 matches C QuickJS's failures exactly |
| luce-regex | the RegExp engine (QuickJS libregexp/libunicode) luce-js and the browser use |
| luce-browser-foundation | `ak`, `gc`, `web_unicode`, `text_codec`, `web_url`, `web_infra` (AK, LibGC, LibUnicode, LibTextCodec, LibURL) |
| luce-browser-css | `css_syntax` (tokenizer, token streams), `css_data` (generated from Ladybird's JSON) |
| luce-browser-html | `html_syntax` (HTML tokenizer, entities) |
| luce-browser-render | `gfx`, `web_fonts`, `raster` (Skia m144 rules, pixel-exact), `display_list` (+ CPU player, filters, 3D, color management) |
| luce-browser-engine | `web` (LibWeb: DOM, HTML, CSS, layout, painting, fetch, animations, media without playback), `webview` (embedding, after LibWebView/WebContent), `webview_api` (the Luce-facing facade), `tests/web_test` (Ladybird's test runner) |
| luced-browser | the browser application: Luce on luce-ui, luced-2d's look, tabs, address field, history |
| luce-browser-tools | oracles, briefs, compiler-issue reductions; local tooling, not a package |

The engine also uses our own format and system libraries rather than Ladybird's: luce-fonts
(OpenType, shaping, WOFF/WOFF2), luce-color (ICC through an skcms port), luce-png (APNG),
luce-jpeg, luce-webp, luce-gif, luce-bmp, luce-ico, luce-xml, luce-compress (gzip, Brotli),
luce-std `net`, luce-tls and luce-crypto. Improvements go into those libraries.

Each browser package has `docs/regions/*.md` (what each region ported, its deviations) and
`docs/namemap.tsv` (every C++ name to its Luce name). The engine's design is
`luce-browser-engine/docs/DESIGN.md`.

## 3. Where it stands

- **Phase 1 (static rendering) and phase 2 (loading) are done.** web_test runs Ladybird's
  tests: Layout 921/922, Ref 780/820, Crash 51/52, Screenshot 65/67 (the other 2 need an HTTP
  server). It is built with `--profile diagnostic` (unwritten storage poisoned with 0xAA).
- Loading is non-blocking (Core::Notifier on the event loop, HTTP/1.1 and TLS 1.3 as state
  machines, connection reuse). Images cover PNG/APNG, JPEG, WebP, GIF, BMP, ICO and SVG, all
  color-managed. Web Animations and CSS animations/transitions run.
- luced-browser renders real sites with scripting disabled. Background tabs are hidden
  (no rendering); closed tabs are torn down completely.
- **Phase 3 (JavaScript) is next:** connecting luce-js to the engine (bindings, the DOM from
  JS, events, timers). Stubs keep their P3 signatures and trap `unported (P3): ...`.
- Remaining known gaps: TLS 1.2-only servers (luce-tls speaks 1.3), no HTTP/2, cache or cookie
  storage, JPEG XL and AVIF, a nested `spin_until` deadlock Ladybird shares (react.dev).

## 4. Rules the owner set

- Repositories hold only Luce code, test data and the harness CI runs. C/C++ donor code and
  comparison drivers stay local.
- Tests pass before any commit; commit only on green, and never chain `git commit` after a
  piped command. CI runs on every push (macOS and Linux; luce-std and luce-js also Windows).
- **Fixes land on main** once their own tests and their dependents' tests pass. There is no
  version bump, publish or tag per fix: releases (`luc publish`, the Luce toolchain) happen in
  occasional batches. Don't add commit pins.
- Use and improve our own libraries; don't port a donor's equivalent (see §2).
- Code bar: faithful to the donor, files of at most about 600 lines with header boxes,
  `# mark:` sections and `##` docs on pub declarations; `luce-base check -W` prints nothing and
  `luce-base fmt --check` passes.
- No backward compatibility; there are no users yet. Spell it Color/color.
- At most one or two agents at a time, each in its own worktree; merge into main and work there.

## 5. How the work is done

**luce-js.** Conventions are in `docs/PORTING.md`, speed in `docs/PERFORMANCE.md`. The gate:
`./test.sh` and `python3 tests/test262.py`, which must print `Result: 58/83558 errors` with
0 crashes, exactly C QuickJS's failures.

**The browser.** Work goes in regions: one agent per region in its own worktree on a branch,
briefed from `luce-browser-tools/briefs/region-brief-template.md`. The agent ports faithfully,
pins tests to the donor with local oracles (sources in `luce-browser-tools/oracles/`, binaries
git-ignored), writes `docs/regions/<region>.md`, and commits on its branch. The coordinator
gates each branch in a fresh workspace built as in §1, merges into main, pushes, and watches CI.

Pitfalls learned:
- Tests that wait for frames must not assume the engine paints after a change it already
  painted. Wait for the named page's load, then force a frame with a screenshot, as Ladybird's
  test-web does (`test_webview_sync_rendering`).
- `luce-base test` runs every imported module's tests in one process, so process-wide state
  (FontDatabase's provider, caches that outlive a VM) must be per-VM or VM-independent
  (DESIGN §3.3 rule 7).
- Timing-dependent crashes show up under load: run the suite at `-j 64` or beside `yes`
  processes (kill them by PID only, never `pkill`).
- Linux-only failures come from libm last-bit differences in float oracles: allow 64 ulps off
  macOS as the existing tests do.

## 6. People and sessions

Other Claude sessions on the owner's machines take messages by name:
- **LUCE_LANG** owns the language and toolchain: luce-base, luce, luce-std, luc, luce-ui and
  luce-window, and the cross-repository migrations. Send compiler bugs there with a minimal
  inline repro; `docs/COMPILER-REQUESTS.md` keeps the written list.
- **LUCED_BROWSER** owns luce-js, the `luce-browser-*` packages, luced-browser and the format
  libraries the browser added (luce-webp, luce-xml, luce-gif, luce-bmp, luce-ico).
- **LINUX** (Ubuntu x86-64) and **WINDOWS** run tests on their platforms. Send them exact steps
  and pushed commits, and ask them not to commit or publish.

The owner decides on releases and anything outside these repositories.
