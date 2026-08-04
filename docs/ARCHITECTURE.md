# Snipline — Architecture

## Layering

Dependencies point one direction only. Nothing in a lower layer imports from a higher one.

```
                  app shell
        (tray, single instance, settings)
                      │
                 controllers
          (capture flow orchestration)
                      │
   ┌────────┬─────────┼─────────┬──────────┐
 hotkey  capture   overlay    editor     export
service  service (selection)  (scene)   (sinks)
   └────────┴─────────┼─────────┴──────────┘
                      │
                 platform/win32
        (ctypes, DPI, monitor geometry, clipboard)
```

The rule that makes this testable: **UI code never calls Win32 directly.** Every OS interaction
goes through `platform/`. That confines the untestable surface to a handful of thin shims and lets
everything above run headless.

## The capture flow

```
WM_HOTKEY
  → CaptureService.grab_virtual_desktop()   # one frozen frame, all monitors
  → OverlayWindow.show(frozen_frame)        # per screen, dim + rubber band
  → user drags → PhysicalRect
  → EditorWindow.open(frame.crop(region))
  → user annotates                          # QGraphicsScene items + QUndoStack
  → ExportService.flatten() → ClipboardSink | FileSink
```

### Freeze first, then overlay

The desktop is captured *before* any overlay window appears. The overlay renders that frozen
pixmap, so what the user drags over is a still image, not the live screen.

This is not an optimisation, it is the only design that works:

- The app's own dimming layer cannot appear in the output, because the output was captured first.
- Open menus, tooltips, drag states, and hover effects stay capturable — they would dismiss the
  moment an overlay took focus.
- Selection is instant, because no pixels are being read during the drag.

## Coordinate spaces

Two spaces exist and must never be mixed. Every multi-monitor screenshot bug is a mixed-space bug.

| Space | Unit | Used for |
|---|---|---|
| **Logical** | Qt points, DPI-scaled | widget geometry, mouse events, layout |
| **Physical** | device pixels | capture, crop, export dimensions |

Conversion happens only at explicit boundaries, using the owning screen's
`QScreen.devicePixelRatio()`. Which screen owns a point matters: on a mixed-DPI setup, the ratio
differs per monitor, so a rect spanning two monitors has no single conversion factor and must be
converted per-monitor.

The types in `platform/geometry.py` are distinct on purpose. A function that accepts a
`PhysicalRect` cannot silently be handed a `LogicalRect`.

### Windows specifics

- The virtual desktop origin is **not** `(0, 0)`. A monitor positioned left of or above the primary
  has negative coordinates. The virtual desktop rect is the union of all monitor bounds, and its
  top-left may be negative.
- Per-Monitor-DPI-Aware-V2 must be declared via `SetProcessDpiAwarenessContext` **before** any Qt
  or Win32 call. Declared late, Windows returns virtualised coordinates and every capture is both
  wrong and blurry.
- Monitor arrangements change at runtime (docking, hot-plug, resolution change). Monitor state is
  re-enumerated on each capture rather than cached at startup.

## Components

### `platform/`

The only package permitted to import `ctypes` or touch Win32.

- `dpi.py` — awareness declaration, per-monitor scale factors, logical↔physical conversion.
- `monitors.py` — enumeration, bounds, work areas, virtual desktop union.
- `hotkey.py` — `RegisterHotKey` / `UnregisterHotKey` against a hidden message window, plus the
  `QAbstractNativeEventFilter` that turns `WM_HOTKEY` into a Qt signal.
- `clipboard_win.py` — clipboard formats, including the alpha-channel caveat.
- `geometry.py` — `LogicalRect`, `PhysicalRect`, `MonitorInfo`. Pure data, no OS calls, fully
  tested.

### `capture/`

`CaptureBackend` is a `Protocol` with a single method:

```python
def grab(self, rect: PhysicalRect) -> Frame: ...
```

`MssBackend` is the real implementation. `FakeBackend` returns a deterministic synthetic gradient
and is what every test uses. **This protocol is the test seam** — no test ever grabs the real
screen, exactly as no test should ever make a real network call.

`Frame` carries the pixel buffer together with the physical rect it came from, so a crop can be
computed without the caller re-deriving the origin.

A note on the buffer: `mss` returns raw BGRA. Converting through
`PIL → bytes → QImage` costs two extra full-frame copies. Wrap it once with
`QImage(buf, w, h, QImage.Format_ARGB32)` and keep a reference to the buffer alive, or Qt will read
freed memory when Python garbage-collects it.

### `overlay/`

One frameless, translucent, always-on-top window **per screen**. A single window spanning the
virtual desktop is wrong on mixed DPI because Qt applies one device-pixel-ratio per window.

The windows coordinate through a shared selection model so a drag that starts on one monitor and
ends on another produces one rect, not two.

Contains: rubber band, dimensions readout, magnifier loupe with pixel coordinates and colour under
cursor, keyboard nudge, `Esc` cancellation, click-without-drag to select the window or monitor
under the cursor.

### `ui/`

Design tokens, the brand mark, the tool glyphs, and the style sheet. Separate from `editor/` and
`overlay/` because both need it and neither owns it; nothing in here knows what a capture is.

`theme.py` imports no Qt, so the tokens are assertable without a `QApplication` and the style sheet
is built from them rather than repeating their values. Every icon the running application shows is
drawn with `QPainter` from one vector definition — see D13 for why, and for why the executable's own
`.ico` is not an exception to it.

### `editor/`

`QGraphicsScene` with the captured pixmap as the background item and one `QGraphicsItem` per
annotation.

Tools are strategy objects implementing `mouse_press` / `mouse_move` / `mouse_release`. Each
produces an item wrapped in a `QUndoCommand` pushed onto a `QUndoStack`. Adding a tool means adding
one file under `editor/tools/` and registering it — if a new tool requires editing the editor, the
interface is wrong and should be fixed rather than worked around.

**Why a scene graph rather than painting into a `QImage`:**

| | Raster | Scene graph |
|---|---|---|
| Undo | snapshot the whole image per step; memory grows with edit count | small commands on a stack |
| Editing a drawn arrow | impossible | select, move, restyle |
| Export | already flat | one `scene.render()` at the end |
| Complexity | lower | moderate |

The moderate complexity buys undo and re-editability, both of which are load-bearing features
rather than nice-to-haves.

**Redaction items** sample the background pixmap beneath their own rect and render the processed
patch. This means moving a redaction re-processes the newly covered region instead of dragging
stale pixels around — a bug present in several shipping tools.

### `export/`

`Sink` protocol with `ClipboardSink` and `FileSink`. Flattening renders the scene at **device**
resolution; rendering at view resolution silently downscales the output on a high-DPI monitor,
which is the kind of bug that only shows up in someone else's bug report.

## Security posture

- **Redaction:** pixelate and solid fill only. Blur is cosmetic and labelled as such. Blurred text
  is often recoverable by rendering candidate strings under the same blur and comparing.
- **No layered project format in v1.** A layered file retains the original pixels beneath a
  redaction; sharing it leaks exactly what the user tried to hide. Export is always flattened.
- **No global keyboard hooks.** `RegisterHotKey` registers one specific combination with the OS and
  receives nothing else. A low-level hook (`SetWindowsHookEx`, or the `keyboard` PyPI package) sees
  every keystroke system-wide — unnecessary privilege for this feature, and a genuine reason for
  endpoint protection to quarantine the binary.
- **No network access in v1.** There is no upload path, no telemetry, and no update check. Adding
  any of these later is a change to the tool's trust model and belongs in its own decision record.

## Module layout

```
src/snipline/
  app.py                  QApplication, wiring, hotkey registration
  config.py               settings dataclass
  settings_store.py       QSettings persistence for it
  tray.py                 tray icon and menu, as signals
  single_instance.py      named-mutex lock, hands off to the running copy
  capture_flow.py         hotkey -> capture -> deliver
  region_capture.py       hotkey -> overlay -> cropped frame
  editor_session.py       frame -> editor window -> export
  platform/
    dpi.py  geometry.py  hotkey.py  keys.py  monitors.py
  capture/
    backend.py  mss_backend.py  fake_backend.py  frame.py  service.py
  overlay/
    controller.py         one window per screen, one shared model
    window.py             painting and events
    chrome.py             handles, size readout, hint
    magnifier.py          the loupe
    selection.py          the state machine; no Qt
    mapping.py            logical <-> physical, and Qt screen matching
  editor/
    window.py  scene.py  commands.py  toolbar.py  style.py
    tools/  base.py  registry.py  select.py  arrow.py  shapes.py
            freehand.py  text.py  step.py  redaction.py
  export/
    sink.py  clipboard.py  encode.py  qt_image.py
  ui/
    theme.py              design tokens; imports no Qt
    mark.py  icons.py  qss.py
  tools/
    grab.py  benchmark.py  make_icons.py
tests/                    mirrors src/, FakeBackend throughout
assets/                   build-time only; see D13
```

Hard limit of 300 lines per file. `overlay/window.py` and `editor/window.py` are the two that
approach it — split by responsibility (`chrome.py` and `magnifier.py` came out of the former) rather
than letting either grow.
