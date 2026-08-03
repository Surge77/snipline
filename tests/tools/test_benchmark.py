"""Benchmark statistics.

The harness itself runs against real hardware, so what is tested here is the arithmetic it
reports -- a benchmark that computes p95 wrongly produces a confidently false claim in the
README, which is worse than no number at all.
"""

from __future__ import annotations

from snipline.platform.geometry import MonitorInfo, PhysicalRect
from snipline.tools.benchmark import WARMUP_RUNS, Measurement, describe_layout, measure


def test_p50_is_the_median() -> None:
    assert Measurement("x", [10.0, 20.0, 30.0]).p50 == 20.0


def test_p95_reports_the_slow_tail_not_the_average() -> None:
    # A tool that is usually instant and occasionally slow feels unreliable, and the mean
    # hides exactly that. 19 fast samples and one slow one must not read as fast.
    samples = [10.0] * 19 + [500.0]

    measurement = Measurement("x", samples)

    assert measurement.p95 == 500.0
    assert measurement.mean < 40.0


def test_p95_of_a_single_sample_is_that_sample() -> None:
    assert Measurement("x", [42.0]).p95 == 42.0


def test_measure_discards_warm_up_runs() -> None:
    # The first calls pay for lazy imports and cold caches; counting them would report a
    # startup cost as the steady-state latency.
    calls: list[int] = []

    result = measure("x", lambda: calls.append(1), runs=5)

    assert len(calls) == 5 + WARMUP_RUNS
    assert len(result.samples_ms) == 5


def test_measured_samples_are_positive() -> None:
    result = measure("x", lambda: sum(range(1000)), runs=3)

    assert all(sample >= 0 for sample in result.samples_ms)


def test_the_row_is_valid_markdown_with_all_four_statistics() -> None:
    row = Measurement("Capture", [10.0, 20.0, 30.0]).format_row()

    assert row.startswith("| Capture |")
    assert row.count("|") == 6


def test_the_layout_description_records_size_and_scaling() -> None:
    # A latency number without the display setup behind it is not reproducible.
    monitors = [
        MonitorInfo(
            0, PhysicalRect(0, 0, 3840, 2160), PhysicalRect(0, 0, 3840, 2160), 1.5, True
        ),
        MonitorInfo(
            1, PhysicalRect(-1920, 0, 1920, 1080), PhysicalRect(-1920, 0, 1920, 1080), 1.0, False
        ),
    ]

    described = describe_layout(monitors)

    assert "3840x2160 @ 150% (primary)" in described
    assert "1920x1080 @ 100%" in described
