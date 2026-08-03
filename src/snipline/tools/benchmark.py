"""``python -m snipline.tools.benchmark`` -- measure the spans the README claims.

PLAN.md §8 is explicit that a claim like "fast screenshot tool" is worth nothing and a
measured number someone can interrogate is worth something. This harness produces the
latter, on real hardware, and records the monitor configuration it was measured on -- a
latency figure without the display setup behind it is not reproducible.

p95 rather than mean: a screenshot tool that is usually instant and occasionally slow feels
unreliable, and the mean hides exactly that.
"""

from __future__ import annotations

import argparse
import platform
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from snipline.capture.service import CaptureService
from snipline.platform.geometry import MonitorInfo

__all__ = ["Measurement", "describe_layout", "measure", "run"]

DEFAULT_RUNS = 30
WARMUP_RUNS = 3
MS_PER_SECOND = 1000.0
P95 = 0.95

BENCHMARK_REGION = (800, 600)


@dataclass(frozen=True, slots=True)
class Measurement:
    name: str
    samples_ms: list[float]

    @property
    def p50(self) -> float:
        return statistics.median(self.samples_ms)

    @property
    def p95(self) -> float:
        if len(self.samples_ms) < 2:
            return self.samples_ms[0]
        ordered = sorted(self.samples_ms)
        # Nearest-rank, which needs no interpolation and is honest about the sample size.
        index = min(len(ordered) - 1, int(len(ordered) * P95))
        return ordered[index]

    @property
    def mean(self) -> float:
        return statistics.fmean(self.samples_ms)

    def format_row(self) -> str:
        return (
            f"| {self.name} | {self.p50:.1f} | {self.p95:.1f} | "
            f"{min(self.samples_ms):.1f} | {max(self.samples_ms):.1f} |"
        )


def measure(
    name: str,
    action: Callable[[], object],
    runs: int = DEFAULT_RUNS,
    setup: Callable[[], object] | None = None,
    teardown: Callable[[], object] | None = None,
) -> Measurement:
    """Time ``action``, discarding warm-up runs.

    ``setup`` and ``teardown`` run outside the timed section. Some spans need an overlay
    opened or an editor closed around them, and folding that into the measurement would
    report a number no user ever experiences.

    Warm-up matters because the first calls pay for lazily imported modules, the first GDI
    device context, and cold Qt paint engines. Counting them would report a startup cost as
    if it were the steady-state latency of every capture after the first.
    """
    samples: list[float] = []
    for iteration in range(runs + WARMUP_RUNS):
        if setup is not None:
            setup()

        started = time.perf_counter()
        action()
        elapsed = (time.perf_counter() - started) * MS_PER_SECOND

        if teardown is not None:
            teardown()
        if iteration >= WARMUP_RUNS:
            samples.append(elapsed)
    return Measurement(name=name, samples_ms=samples)


def describe_layout(monitors: Sequence[MonitorInfo]) -> str:
    """The display setup a measurement is only meaningful against."""
    parts = [
        f"{m.bounds.width}x{m.bounds.height} @ {round(m.scale * 100)}%"
        + (" (primary)" if m.is_primary else "")
        for m in monitors
    ]
    return "; ".join(parts)


def _build_measurements(service: CaptureService, runs: int) -> list[Measurement]:
    """The three spans named in docs/BENCHMARKS.md, plus the stages they decompose into.

    The stage timings are not decoration: when a span regresses, they say which part did it.
    """
    from snipline.capture_flow import CaptureFlow
    from snipline.config import Settings
    from snipline.editor_session import EditorSession
    from snipline.export.clipboard import frame_to_qimage
    from snipline.platform.geometry import PhysicalRect
    from snipline.region_capture import RegionCapture

    desktop = service.desktop_rect()
    frame = service.grab_desktop()
    settings = Settings()
    flow = CaptureFlow(service=service, settings=settings)

    region = RegionCapture(service=service, flow=flow, deliver=False)
    selection = PhysicalRect(desktop.left, desktop.top, *BENCHMARK_REGION).intersection(
        desktop
    )

    sessions: list[EditorSession] = []

    def open_editor() -> None:
        session = EditorSession(frame=frame.crop(selection), settings=settings, flow=flow)
        session.open()
        sessions.append(session)

    def close_editors() -> None:
        while sessions:
            sessions.pop().window.close()

    clipboard_session = EditorSession(
        frame=frame.crop(selection), settings=settings, flow=flow
    )

    return [
        # Freeze the desktop, build one window per screen, and show them.
        measure("hotkey_to_overlay", region.start, runs, teardown=region.abort),
        # Crop the frozen frame and put an editor on screen ready for input.
        measure("select_to_editor", open_editor, runs, teardown=close_editors),
        # Flatten the scene and place it on the clipboard.
        measure("export_to_clipboard", clipboard_session.copy, runs),
        measure("  - full desktop capture", service.grab_desktop, runs),
        measure("  - frame to QImage", lambda: frame_to_qimage(frame), runs),
    ]


def run(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="snipline-benchmark",
        description="Measure capture and export latency on this machine.",
    )
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="samples per span")
    args = parser.parse_args(argv)

    from PySide6.QtWidgets import QApplication

    from snipline.capture.mss_backend import MssBackend

    app = QApplication.instance() or QApplication([])
    assert app is not None

    service = CaptureService(backend=MssBackend())
    desktop = service.desktop_rect()

    print(f"Machine: {platform.platform()}")
    print(f"Displays: {describe_layout(service.monitors())}")
    print(f"Virtual desktop: {desktop.width}x{desktop.height}")
    print(f"Samples per span: {args.runs} (after {WARMUP_RUNS} warm-up runs)\n")

    print("| Span | p50 (ms) | p95 (ms) | min | max |")
    print("|---|---|---|---|---|")
    for measurement in _build_measurements(service, args.runs):
        print(measurement.format_row())

    service.close()
    return 0


def main() -> int:
    from snipline.platform.dpi import declare_dpi_awareness

    # The same ordering constraint as the app: measuring a DPI-unaware process would time
    # captures of the wrong size.
    declare_dpi_awareness()
    return run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
