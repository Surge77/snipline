"""Test configuration.

The offscreen platform is set here rather than in pytest.ini because it must be in the
environment before PySide6 is first imported, and doing it in pytest.ini would require the
pytest-env plugin as an extra dependency.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from snipline.capture.fake_backend import FakeBackend
from snipline.platform.geometry import MonitorInfo, PhysicalRect


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


def _monitor(
    index: int,
    left: int,
    top: int,
    width: int,
    height: int,
    scale: float,
    primary: bool = False,
) -> MonitorInfo:
    bounds = PhysicalRect(left, top, width, height)
    return MonitorInfo(
        index=index,
        bounds=bounds,
        work_area=bounds,
        scale=scale,
        is_primary=primary,
    )


# The five layouts from docs/BENCHMARKS.md, as data. Every geometry function is expected to
# behave against all of them -- especially C4, where the secondary monitor sits at negative
# coordinates, which is the most common source of whole-monitor-offset crop bugs.

LAYOUT_C1 = [_monitor(0, 0, 0, 1920, 1080, 1.0, primary=True)]

LAYOUT_C2 = [
    _monitor(0, 0, 0, 1920, 1080, 1.0, primary=True),
    _monitor(1, 1920, 0, 1920, 1080, 1.0),
]

LAYOUT_C3 = [
    _monitor(0, 0, 0, 3840, 2160, 1.5, primary=True),
    _monitor(1, 3840, 0, 1920, 1080, 1.0),
]

LAYOUT_C4 = [
    _monitor(0, 0, 0, 3840, 2160, 1.5, primary=True),
    _monitor(1, -1920, 0, 1920, 1080, 1.0),
]

LAYOUT_C5 = [
    _monitor(0, 0, 0, 1920, 1080, 1.0, primary=True),
    _monitor(1, 1920, -200, 2560, 1440, 1.25),
    _monitor(2, -3840, 0, 3840, 2160, 1.5),
]

ALL_LAYOUTS = {
    "C1": LAYOUT_C1,
    "C2": LAYOUT_C2,
    "C3": LAYOUT_C3,
    "C4": LAYOUT_C4,
    "C5": LAYOUT_C5,
}


@pytest.fixture(params=sorted(ALL_LAYOUTS), ids=sorted(ALL_LAYOUTS))
def layout(request: pytest.FixtureRequest) -> list[MonitorInfo]:
    """Parametrised over every monitor layout, so geometry tests cover all five."""
    return ALL_LAYOUTS[request.param]
