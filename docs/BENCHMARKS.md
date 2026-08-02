# Benchmarks

> **Status:** no measurements yet. The harness lands in M6. This file defines what gets measured
> and how, so the numbers mean something when they arrive.

## Why this file exists

The project rule is that a README which cannot state a number is not worth writing. "Fast
screenshot tool" is unfalsifiable. "Hotkey to overlay in 94 ms p95 across three monitors at
100/125/150% scaling" is a claim someone can interrogate, reproduce, and disagree with.

## Spans measured

| Span | From | To | Target p95 |
|---|---|---|---|
| `hotkey_to_overlay` | `WM_HOTKEY` received | first overlay window painted | < 120 ms |
| `select_to_editor` | mouse release on selection | editor window ready for input | < 80 ms |
| `export_to_clipboard` | export invoked | clipboard contains the image | < 60 ms |

`hotkey_to_overlay` is the only one users consciously feel. The other two are measured to catch
regressions, not because anyone notices 40 ms in an editor.

## Method

- `time.perf_counter_ns()` at each boundary; spans recorded into an in-memory ring buffer.
- 100 iterations per configuration, discarding the first 10 as warm-up (Qt lazily initialises
  paint engines and font caches on first paint).
- Report p50 and p95, not mean. The mean hides the stutter that makes a tool feel bad.
- Run with the machine otherwise idle, then again with a browser and an IDE open — a screenshot
  tool is always used *while* something else is running, so the loaded number is the honest one.

## Configurations to report

Every published number states the monitor configuration it was measured on. A single-1080p number
is not comparable to a mixed-DPI number and should not be presented as if it were.

| ID | Layout |
|---|---|
| `C1` | single 1920×1080 @ 100% |
| `C2` | dual 1920×1080 @ 100%, side by side |
| `C3` | 3840×2160 @ 150% + 1920×1080 @ 100% |
| `C4` | C3 with the secondary positioned left of primary (negative coordinates) |
| `C5` | three monitors @ 100/125/150% |

`C3`–`C5` are where correctness bugs live. `C4` exists specifically because negative-origin layouts
are the most common source of off-by-a-whole-monitor crop bugs.

## Correctness assertions

Latency is worthless if the output is wrong. Each benchmark run also asserts:

- Output image dimensions equal the selected region in **physical** pixels, on every monitor.
- A capture spanning two monitors at different scale factors contains no seam, duplication, or gap.
- Round-tripping a known test pattern through capture → export produces pixel-identical output.

## Results

_Pending M6._

| Config | hotkey→overlay p50 | p95 | select→editor p95 | export→clipboard p95 |
|---|---|---|---|---|
| C1 | — | — | — | — |
| C2 | — | — | — | — |
| C3 | — | — | — | — |
| C4 | — | — | — | — |
| C5 | — | — | — | — |

Hardware and OS build used for the measurements will be stated here alongside the table. Numbers
without a machine description are not reproducible and should be treated as decoration.
