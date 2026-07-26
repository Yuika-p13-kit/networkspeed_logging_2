from datetime import datetime
from pathlib import Path

import pytest

from network_speed.backup import CsvBackupStore
from network_speed.models import MeasurementRecord


class FakeRepository:
    def __init__(self, fail_at: int | None = None):
        self.records: list[MeasurementRecord] = []
        self.fail_at = fail_at

    def insert_measurement(self, record: MeasurementRecord) -> None:
        current_index = len(self.records)
        if self.fail_at is not None and current_index == self.fail_at:
            raise RuntimeError("db error")
        self.records.append(record)


def _record(index: int = 0) -> MeasurementRecord:
    return MeasurementRecord(
        timestamp=datetime(2026, 1, 1, 0, 0, index),
        download_mbps=123.456 + index,
        upload_mbps=78.9 + index,
        device="Mac",
    )


def test_append_and_load_roundtrip(tmp_path: Path) -> None:
    csv_path = tmp_path / "network_speed_backup.csv"
    store = CsvBackupStore(csv_path)
    store.append(_record(1))
    store.append(_record(2))

    loaded = store.load_all()

    assert len(loaded) == 2
    assert loaded[0].download_mbps == pytest.approx(124.456)
    assert loaded[1].upload_mbps == pytest.approx(80.9)


def test_replay_to_repository_success_deletes_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "network_speed_backup.csv"
    store = CsvBackupStore(csv_path)
    store.append(_record(1))
    store.append(_record(2))
    repo = FakeRepository()

    replayed = store.replay_to_repository(repo)

    assert replayed == 2
    assert len(repo.records) == 2
    assert not csv_path.exists()


def test_replay_to_repository_failure_keeps_file(tmp_path: Path) -> None:
    csv_path = tmp_path / "network_speed_backup.csv"
    store = CsvBackupStore(csv_path)
    store.append(_record(1))
    store.append(_record(2))
    repo = FakeRepository(fail_at=1)

    with pytest.raises(RuntimeError):
        store.replay_to_repository(repo)

    assert csv_path.exists()
