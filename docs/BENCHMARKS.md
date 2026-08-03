# Benchmarks

> **Status:** measured on `C1` only. The harness ships as `python -m snipline.tools.benchmark`.
> `C2`-`C5` are unmeasured because the development machine has one display; those rows stay
> empty rather than being filled with a number from a different configuration.

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

Measured with `python -m snipline.tools.benchmark --runs 40`, machine otherwise idle.

### `C1` -- single 1920x1080 @ 125%

Windows 10 (build 26200), Python 3.11, PySide6 6.11.1, 40 samples per span after 3 warm-up runs.

| Span | p50 (ms) | p95 (ms) | min | max | Target p95 |
|---|---|---|---|---|---|
| `hotkey_to_overlay` | 34.8 | 43.9 | 27.5 | 179.7 | < 120 ms |
| `select_to_editor` | 14.7 | 23.3 | 10.9 | 23.6 | < 80 ms |
| `export_to_clipboard` | 3.1 | 7.0 | 1.9 | 113.0 | < 60 ms |
| - full desktop capture | 20.8 | 26.4 | 17.7 | 26.6 | -- |
| - frame to QImage | 2.1 | 2.5 | 1.5 | 2.7 | -- |

All three spans are inside target on this configuration.

### Reading these numbers honestly

- **One display at 125%.** This is `C1`, the easiest configuration. It says nothing about the
  mixed-DPI cases the project exists to get right, and it must not be quoted as if it did.
- **The `max` column is worse than the p95 on two spans.** Those outliers -- 179.7 ms and
  113.0 ms -- are single samples out of 40, consistent with a scheduler preemption or a GC
  pause rather than a systematic cost. They are reported rather than trimmed because a
  benchmark that quietly discards its worst samples is measuring the wrong thing.
- **Idle machine only.** The loaded measurement described under *Method* above has not been
  taken yet.
- **Full desktop capture dominates `hotkey_to_overlay`**, at roughly 21 of its 35 ms. That is
  GDI `BitBlt` reading 1920x1080, and it is where to look first if this span regresses.

### Unmeasured configurations

| Config | Status |
|---|---|
| `C2` dual 1920x1080 @ 100% | not measured -- no second display available |
| `C3` 3840x2160 @ 150% + 1920x1080 @ 100% | not measured |
| `C4` C3 with negative-origin secondary | not measured |
| `C5` three monitors @ 100/125/150% | not measured |

The geometry for all five layouts is covered by unit tests against synthetic monitor data; what
is missing here is *timing* on real multi-monitor hardware, not correctness coverage.
