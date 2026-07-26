from datetime import datetime

import pytest

from network_speed.measurement import (
    MeasurementFailedError,
    bps_to_mbps_rounded,
    measure_with_retry,
)


def test_bps_to_mbps_rounded() -> None:
    assert bps_to_mbps_rounded(12_345_678) == 12.346


def test_measure_with_retry_succeeds_after_retry() -> None:
    attempts = {"count": 0}
    sleep_calls: list[float] = []

    def runner() -> tuple[float, float]:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary failure")
        return 10_000_000.0, 5_500_000.0

    record = measure_with_retry(
        max_attempts=5,
        sleep_seconds=0.25,
        device="Mac",
        runner=runner,
        time_provider=lambda: datetime(2026, 1, 1, 0, 0, 0),
        sleeper=lambda seconds: sleep_calls.append(seconds),
    )

    assert attempts["count"] == 2
    assert sleep_calls == [0.25]
    assert record.download_mbps == 10.0
    assert record.upload_mbps == 5.5
    assert record.device == "Mac"


def test_measure_with_retry_raises_after_max_attempts() -> None:
    def always_fail() -> tuple[float, float]:
        raise RuntimeError("always fail")

    with pytest.raises(MeasurementFailedError):
        measure_with_retry(max_attempts=3, runner=always_fail)


def test_measure_with_retry_rejects_invalid_max_attempts() -> None:
    with pytest.raises(ValueError):
        measure_with_retry(max_attempts=0)
