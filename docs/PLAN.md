# Snipline — Build Plan

Origin: the "Screenshot Tool + Annotator" entry under *Desktop Apps (Windows)* in the personal
`Projects to build` list. The original spec was four lines:

> **Scope:** Global hotkey → region-select overlay → draw arrows/text/blur on a canvas → copy or
> save. Multi-monitor aware.
> **Learn:** Overlay windows, canvas drawing, multi-monitor geometry, image export.
> **Measurable:** "capture→annotate→clipboard in < X ms; handles N monitors."

This document expands that into an executable plan.

---

## 1. Goal and non-goals

**Goal.** A Windows screenshot tool that is provably correct on multi-monitor mixed-DPI setups,
with a vector annotation editor, shipping as a signed-ish standalone executable, with a README
that states measured latency numbers.

**The differentiator is DPI correctness, not the drawing tools.** Drawing an arrow is a solved
afternoon. Getting a crop rectangle right when monitor A is 3840×2160 at 150% scaling, monitor B is
1920×1080 at 100%, and B sits to the *left* of A so its coordinates are negative — that is the part
most tools get wrong and the part worth building.

**Non-goals for v1.** Scrolling capture, screen recording, GIF export, OCR, cloud upload, a layered
project file format, and any platform other than Windows. Each is listed in §7 with a reason.

---

## 2. Success criteria

v1 is done when all of the following are true:

1. Benchmark harness reports p95 `hotkey → overlay visible` under 120 ms on the dev machine.
2. A capture spanning two monitors at different scale factors produces an output image whose
   dimensions equal the selected region in **physical** pixels, verified by an automated test
   against synthetic monitor layouts.
3. Undo/redo covers every annotation operation with no image-snapshot memory growth.
4. `pytest` passes headless in CI with zero real screen captures.
5. `pyright` clean in strict mode; `ruff` clean.
6. PyInstaller build produces a working `.exe` on a machine without Python installed.
7. README states the measured numbers, not the target numbers.

---

## 3. Milestones

Each milestone is independently shippable and independently useful. Do not start the next until
the current one is merged and its tests are green.

### M0 — Repo skeleton *(this commit)*

Directory layout, licence, docs, dependency pins, type/lint/test config, CI workflow, the
`CaptureBackend` protocol with its fake implementation, and the coordinate-space primitives. No
capture, no UI.

**Exit:** `pytest` and `pyright` pass on an empty-but-typed codebase.

### M1 — Capture correctness

The foundation everything else inherits bugs from. Build this first and prove it before any UI
exists.

- Declare Per-Monitor-DPI-Aware-V2 at process start via `SetProcessDpiAwarenessContext`.
- Enumerate monitors: bounds, work area, scale factor, primary flag.
- Compute the virtual desktop rect as the union of all monitor bounds. Handle negative origins.
- `MssBackend.grab(rect)` returning a `Frame` carrying its own physical-pixel geometry.
- Save to PNG. Verify pixel dimensions equal the physical region size on every monitor.

**Exit:** a CLI entry point `python -m snipline.tools.grab --all` writes a correct full-virtual-
desktop PNG on a mixed-DPI setup. Automated tests cover the geometry math against synthetic
layouts including negative coordinates and a monitor arrangement with vertical offset.

**Trap:** if DPI awareness is not declared before the first Qt or Win32 call, Windows silently
returns *virtualised* coordinates and the capture is both wrong and blurry. This must be the first
thing `app.py` does, before `QApplication` is constructed.

### M2 — Hotkey and tray

- `RegisterHotKey` against a hidden message window; `WM_HOTKEY` intercepted through a
  `QAbstractNativeEventFilter` and re-emitted as a Qt signal.
- Registration failure (another app owns the combination) surfaces as a visible settings error.
  It must not fail silently — a hotkey that does nothing is the worst possible failure mode.
- `QSystemTrayIcon` with capture / settings / quit.
- Single-instance enforcement via `QLocalServer`; a second launch signals the first to capture and
  then exits.

**Exit:** pressing the hotkey while another app is focused writes a full-desktop PNG and shows a
tray notification.

**Why not `QShortcut`:** Qt shortcuts only fire when the application has keyboard focus. A
screenshot tool is by definition used while something else is focused. Win32 `RegisterHotKey` is
the correct mechanism. The `keyboard` PyPI package is explicitly rejected — it installs a low-level
global keyboard hook, which needs elevation in some configurations and is routinely flagged as a
keylogger by endpoint protection.

### M3 — Selection overlay → clipboard

At the end of this milestone the tool is genuinely useful. Start dogfooding here.

- **Freeze first, then overlay.** Capture the entire virtual desktop into a frame *before* showing
  any overlay window. The overlay then displays that frozen pixmap. This is why open menus,
  tooltips, and hover states are capturable at all — and why the app's own dimming layer never ends
  up inside the screenshot.
- One frameless, translucent, always-on-top overlay window **per screen**. A single window spanning
  the virtual desktop breaks on mixed DPI, because Qt applies one device-pixel-ratio to the whole
  window.
- Rubber-band drag with live dimensions readout, arrow-key nudge for pixel-precise edges, magnifier
  loupe showing pixel coordinates and colour, `Esc` to cancel, click-without-drag to capture the
  window or monitor under the cursor.
- Crop the frozen frame in physical coordinates, push to clipboard.

**Exit:** hotkey → drag → the region is on the clipboard, correct on every monitor.

### M4 — Editor shell, arrow tool, undo

- `QGraphicsScene` / `QGraphicsView` holding the captured pixmap as the background item.
- Tool strategy interface: `mouse_press` / `mouse_move` / `mouse_release`, each producing a
  `QGraphicsItem` wrapped in a `QUndoCommand`.
- `QUndoStack` wired to Ctrl+Z / Ctrl+Y.
- Arrow tool as the reference implementation of the interface.

**The scene-graph decision.** The alternative is painting directly into a `QImage`. Rejected:
undo would require snapshotting the whole image per operation (memory grows with edit count on a
4K capture), and an arrow becomes uneditable the moment it is drawn. With a scene graph, undo is a
stack of small commands, annotations stay selectable and restylable, and flattening happens exactly
once at export.

### M5 — Remaining tools

Rectangle, ellipse, freehand, text, numbered step badges, pixelate, solid fill, cosmetic blur.
Colour and stroke-width picker. Each tool is one file under `editor/tools/` and requires zero edits
to the editor itself — if a new tool forces an editor change, the interface is wrong.

**Redaction items are special.** A redaction item samples the background pixmap beneath its own
rect and renders the processed patch, so dragging it re-processes the newly covered area rather
than smearing stale pixels.

### M6 — Export, settings, packaging, benchmark

- `Sink` protocol: `ClipboardSink`, `FileSink`. Flatten via `QGraphicsScene.render()` at **device**
  resolution — rendering at view resolution silently downscales the export on a high-DPI monitor.
- Settings persisted through `QSettings`: hotkey, default sink, format, quality, save directory.
- Windows clipboard note: the standard `CF_DIB` clipboard format discards the alpha channel. A
  capture with transparency copied to the clipboard will composite against black or white depending
  on the receiving application. File export preserves alpha; the clipboard path must either
  composite deliberately against a known background or write `PNG` as a registered clipboard format.
- PyInstaller `--onedir` build. `--onefile` is rejected: it unpacks to a temp directory on every
  launch, adding seconds of startup for a tool whose entire value proposition is sub-second
  response.
- Benchmark harness writes p50/p95 for the three spans in §2 into `docs/BENCHMARKS.md`.

**Exit:** the README's number table is filled in with measured values.

---

## 4. Work breakdown by milestone

| M | Deliverable | Est. | Risk |
|---|---|---|---|
| M0 | skeleton, protocols, config, CI | 0.5 d | low |
| M1 | DPI awareness, monitor enumeration, capture | 2 d | **high** — the whole project rests here |
| M2 | hotkey, tray, single instance | 1 d | medium — `RegisterHotKey` conflicts |
| M3 | overlay, selection, clipboard | 2.5 d | medium — per-screen overlay coordination |
| M4 | editor, scene, undo, arrow | 2 d | low |
| M5 | remaining tools, redaction | 2.5 d | low |
| M6 | export, settings, packaging, benchmark | 2 d | medium — PyInstaller + Qt plugin bundling |

Roughly two focused weeks. M1 is the milestone to slow down on; every downstream bug that looks
like an editor bug will actually be an M1 coordinate bug.

---

## 5. Testing strategy

**Unit, headless, in CI.** Geometry and DPI conversion, region clamping to monitor bounds, virtual
desktop union math, undo stack behaviour, flatten output determinism (hash a rendered scene),
tool state machines, export encoder selection. Runs with `QT_QPA_PLATFORM=offscreen` and
`FakeBackend`. This is where the coverage requirement is met.

**Explicitly not unit-testable.** `RegisterHotKey`, the real system clipboard, actual multi-monitor
enumeration, tray icon behaviour. These are OS-boundary calls with no meaningful seam; they are
covered by a manual checklist in `docs/MANUAL_TESTS.md` and exercised by dogfooding from M3 onward.
Do not write mock-heavy tests that assert `ctypes` was called with certain arguments — those tests
only ever break during refactors and never catch a real bug.

**Fixtures.** Synthetic monitor layouts as data: side-by-side same DPI, side-by-side mixed DPI,
negative-origin secondary, vertically offset, three-monitor mixed. Every geometry function is
tested against all five.

---

## 6. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| DPI awareness set too late | every capture wrong and blurry | make it the first statement in `app.py`; assert it in a startup check |
| Mixing logical and physical coordinates | subtly wrong crops, only on some monitors | separate types (`LogicalRect` / `PhysicalRect`), convert only at explicit boundaries |
| Overlay steals focus from the app being captured | can't capture menus | freeze-then-overlay makes this irrelevant |
| Hotkey already registered by another app | tool appears dead | surface the failure in the UI, offer to rebind |
| PyInstaller misses Qt platform plugins | exe fails on clean machines | test the build in a VM without Python, as part of M6 |
| Antivirus flags the exe | unusable distribution | avoid global keyboard hooks; `RegisterHotKey` only |

---

## 7. Deferred, with reasons

- **Scrolling capture** — needs stitching with template matching; a project in itself.
- **Screen recording / GIF** — different pipeline (encoder, frame pacing), doubles scope.
- **OCR** — Tesseract is a heavy dependency for a v1 nice-to-have.
- **Windows Graphics Capture (WinRT)** — more correct for HDR and protected windows than GDI
  `BitBlt`, but a large complexity jump. Revisit if HDR capture proves visibly wrong.
- **Layered project format** — deliberately excluded on privacy grounds; see the redaction section
  of the README.
- **macOS / Linux** — the `platform/` package is the seam that would make this possible. Having a
  seam is not a commitment to using it.

---

## 8. Definition of done for the portfolio claim

The README states measured p50/p95 latency for three spans and the monitor configuration those
numbers were measured on. A claim like "fast screenshot tool" is worth nothing; "hotkey to overlay
in 94 ms p95 across three monitors at 100/125/150% scaling" is a claim someone can interrogate.
