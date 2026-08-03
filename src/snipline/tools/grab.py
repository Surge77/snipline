"""``python -m snipline.tools.grab`` -- capture without any UI.

This is M1's exit criterion and stays useful afterwards as the fastest way to prove the
capture path on a real mixed-DPI desktop: no overlay, no hotkey, no tray, nothing between
the monitor geometry and the written PNG. When a capture is wrong, running this first says
whether the bug is in M1 or in everything built on top of it.

The service is injected so the whole CLI is exercised in CI against FakeBackend.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from snipline.capture.service import CaptureService
from snipline.config import ExportFormat
from snipline.export.encode import DEFAULT_QUALITY, save_frame
from snipline.platform.geometry import PhysicalRect

__all__ = ["build_parser", "main", "parse_region", "run"]

ServiceFactory = Callable[[], CaptureService]

REGION_FIELDS = 4


def parse_region(text: str) -> PhysicalRect:
    """Parse ``left,top,width,height`` in absolute virtual-desktop physical pixels.

    Left and top may be negative -- monitors above or left of the primary live there --
    while width and height may not, which ``PhysicalRect`` enforces.
    """
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != REGION_FIELDS:
        raise ValueError(f"expected left,top,width,height; got {text!r}")
    try:
        left, top, width, height = (int(part) for part in parts)
    except ValueError as error:
        raise ValueError(f"region values must be integers: {text!r}") from error
    return PhysicalRect(left, top, width, height)


def fuse_negative_region(argv: list[str]) -> list[str]:
    """Rewrite ``--region -1920,0,8,8`` into ``--region=-1920,0,8,8``.

    argparse treats any token starting with ``-`` as an option, and its negative-number
    escape hatch only recognises bare numbers, not ``-1920,0,8,8``. Without this the one
    case this project exists to get right -- a region on a monitor left of the primary --
    is unusable from the CLI.
    """
    fused: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        has_dashed_value = (
            token == "--region"
            and index + 1 < len(argv)
            and argv[index + 1].startswith("-")
        )
        if has_dashed_value:
            fused.append(f"--region={argv[index + 1]}")
            index += 2
        else:
            fused.append(token)
            index += 1
    return fused


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="snipline-grab",
        description="Capture the desktop, one monitor, or a region, to an image file.",
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument(
        "--all",
        action="store_true",
        help="capture the whole virtual desktop (the default)",
    )
    target.add_argument("--monitor", type=int, metavar="INDEX", help="capture one monitor")
    target.add_argument(
        "--region",
        type=parse_region,
        metavar="L,T,W,H",
        help="capture a rect in absolute physical pixels; L and T may be negative",
    )
    target.add_argument(
        "--list",
        action="store_true",
        help="print the monitor layout and exit without capturing",
    )
    parser.add_argument("-o", "--output", type=Path, help="destination file")
    parser.add_argument(
        "--format",
        type=ExportFormat,
        choices=list(ExportFormat),
        default=ExportFormat.PNG,
        metavar="{" + ",".join(f.value for f in ExportFormat) + "}",
        help="image format (default: png)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=DEFAULT_QUALITY,
        help=f"quality for lossy formats (default: {DEFAULT_QUALITY})",
    )
    return parser


def _default_output(export_format: ExportFormat) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path(f"snipline-{stamp}.{export_format.value}")


def _print_layout(service: CaptureService) -> None:
    for monitor in service.monitors():
        marker = " (primary)" if monitor.is_primary else ""
        bounds = monitor.bounds
        print(
            f"[{monitor.index}] {bounds.width}x{bounds.height} "
            f"at ({bounds.left}, {bounds.top}) "
            f"{round(monitor.scale * 100)}%{marker}"
        )
    print(f"virtual desktop: {service.desktop_rect()}")


def _default_backend() -> CaptureService:
    from snipline.capture.mss_backend import MssBackend

    return CaptureService(backend=MssBackend())


def run(argv: list[str], service_factory: ServiceFactory = _default_backend) -> int:
    args = build_parser().parse_args(fuse_negative_region(argv))
    service = service_factory()

    try:
        if args.list:
            _print_layout(service)
            return 0

        if args.monitor is not None:
            frame = service.grab_monitor(args.monitor)
        elif args.region is not None:
            frame = service.grab_region(args.region)
        else:
            frame = service.grab_desktop()

        destination = args.output or _default_output(args.format)
        written = save_frame(
            frame,
            destination,
            export_format=args.format,
            quality=args.quality,
        )
    except (ValueError, IndexError, RuntimeError, OSError) as error:
        # A wrong monitor index or an off-desktop selection is user error, not a crash.
        print(f"snipline-grab: {error}", file=sys.stderr)
        return 1
    finally:
        service.close()

    print(f"{written} ({frame.width}x{frame.height} physical pixels)")
    return 0


def main() -> int:
    # Must happen before any monitor query, or Windows reports virtualised coordinates and
    # every capture below is silently wrong on high-DPI monitors.
    from snipline.platform.dpi import declare_dpi_awareness

    declare_dpi_awareness()
    return run(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
