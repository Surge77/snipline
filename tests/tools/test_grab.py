"""The M1 exit criterion, as a test.

``python -m snipline.tools.grab --all`` must write a PNG whose pixel dimensions equal the
virtual desktop in physical pixels, on layouts including negative origins and mixed DPI.
The real backend is swapped for FakeBackend here; what is under test is the wiring and the
geometry, not GDI.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from snipline.capture.fake_backend import FakeBackend
from snipline.capture.service import CaptureService
from snipline.platform.geometry import MonitorInfo, PhysicalRect
from snipline.tools.grab import parse_region, run

MIXED_DPI_WITH_NEGATIVE_ORIGIN = [
    MonitorInfo(0, PhysicalRect(0, 0, 3840, 2160), PhysicalRect(0, 0, 3840, 2160), 1.5, True),
    MonitorInfo(
        1, PhysicalRect(-1920, 0, 1920, 1080), PhysicalRect(-1920, 0, 1920, 1080), 1.0, False
    ),
]


@pytest.fixture
def service_factory(backend: FakeBackend):  # type: ignore[no-untyped-def]
    def factory(monitors: list[MonitorInfo] = MIXED_DPI_WITH_NEGATIVE_ORIGIN):
        return lambda: CaptureService(backend=backend, monitors_provider=lambda: monitors)

    return factory


def test_grab_all_writes_the_whole_virtual_desktop(
    tmp_path: Path, service_factory  # type: ignore[no-untyped-def]
) -> None:
    destination = tmp_path / "desktop.png"

    exit_code = run(["--all", "-o", str(destination)], service_factory())

    assert exit_code == 0
    with Image.open(destination) as written:
        # 3840 wide primary plus a 1920 wide monitor at a negative origin.
        assert written.size == (5760, 2160)


def test_grab_monitor_writes_that_monitors_physical_size(
    tmp_path: Path, service_factory  # type: ignore[no-untyped-def]
) -> None:
    destination = tmp_path / "monitor.png"

    run(["--monitor", "0", "-o", str(destination)], service_factory())

    with Image.open(destination) as written:
        assert written.size == (3840, 2160)  # physical, not the 2560x1440 logical size


def test_grab_region_writes_exactly_the_requested_rect(
    tmp_path: Path, service_factory  # type: ignore[no-untyped-def]
) -> None:
    destination = tmp_path / "region.png"

    run(["--region", "-1900,10,300,200", "-o", str(destination)], service_factory())

    with Image.open(destination) as written:
        assert written.size == (300, 200)


def test_list_reports_every_monitor_without_capturing(
    capsys: pytest.CaptureFixture[str],
    backend: FakeBackend,
    service_factory,  # type: ignore[no-untyped-def]
) -> None:
    exit_code = run(["--list"], service_factory())

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "3840x2160" in output
    assert "150%" in output
    assert backend.grab_calls == []


def test_defaults_to_the_full_desktop_when_no_target_is_given(
    tmp_path: Path, service_factory  # type: ignore[no-untyped-def]
) -> None:
    destination = tmp_path / "default.png"

    run(["-o", str(destination)], service_factory())

    with Image.open(destination) as written:
        assert written.size == (5760, 2160)


def test_generates_a_timestamped_filename_when_no_output_is_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service_factory  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.chdir(tmp_path)

    run(["--all"], service_factory())

    written = list(tmp_path.glob("snipline-*.png"))
    assert len(written) == 1


def test_reports_a_failure_without_a_traceback(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    service_factory,  # type: ignore[no-untyped-def]
) -> None:
    exit_code = run(
        ["--region", "9000,9000,10,10", "-o", str(tmp_path / "off.png")], service_factory()
    )

    assert exit_code == 1
    assert "outside the virtual desktop" in capsys.readouterr().err


def test_rejects_an_unknown_monitor_index(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    service_factory,  # type: ignore[no-untyped-def]
) -> None:
    exit_code = run(["--monitor", "7", "-o", str(tmp_path / "x.png")], service_factory())

    assert exit_code == 1
    assert "no monitor" in capsys.readouterr().err


def test_region_on_a_monitor_left_of_primary_survives_argparse(
    tmp_path: Path, service_factory  # type: ignore[no-untyped-def]
) -> None:
    # argparse would otherwise read "-1900,..." as an unknown option and abort. This is the
    # negative-origin case the whole project is about, so it gets its own test.
    destination = tmp_path / "negative.png"

    exit_code = run(["--region", "-1900,10,64,48", "-o", str(destination)], service_factory())

    assert exit_code == 0
    with Image.open(destination) as written:
        assert written.size == (64, 48)


def test_equals_form_of_region_also_works(
    tmp_path: Path, service_factory  # type: ignore[no-untyped-def]
) -> None:
    destination = tmp_path / "eq.png"

    run(["--region=-1900,10,64,48", "-o", str(destination)], service_factory())

    with Image.open(destination) as written:
        assert written.size == (64, 48)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0,0,100,50", PhysicalRect(0, 0, 100, 50)),
        ("-1920,-200,640,480", PhysicalRect(-1920, -200, 640, 480)),
        (" 10 , 20 , 30 , 40 ", PhysicalRect(10, 20, 30, 40)),
    ],
)
def test_parse_region_accepts_negative_and_spaced_values(
    text: str, expected: PhysicalRect
) -> None:
    assert parse_region(text) == expected


@pytest.mark.parametrize("text", ["1,2,3", "a,b,c,d", "1,2,3,4,5", "", "1,2,-3,4"])
def test_parse_region_rejects_malformed_input(text: str) -> None:
    with pytest.raises(ValueError):
        parse_region(text)
