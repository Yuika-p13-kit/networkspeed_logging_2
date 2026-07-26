from datetime import datetime
import sys
from types import SimpleNamespace

import pytest

import main
from network_speed.measurement import MeasurementFailedError
from network_speed.models import MeasurementRecord


class FakeRepo:
    def __init__(self, fail_on_insert: bool = False):
        self.fail_on_insert = fail_on_insert
        self.connected = False
        self.inserted_records: list[MeasurementRecord] = []

    def connect(self) -> None:
        self.connected = True

    def insert_measurement(self, record: MeasurementRecord) -> None:
        if self.fail_on_insert:
            raise RuntimeError("db error")
        self.inserted_records.append(record)


class FakeBackup:
    def __init__(self, fail_on_replay: bool = False):
        self.fail_on_replay = fail_on_replay
        self.appended_records: list[MeasurementRecord] = []
        self.replay_called = 0
        self.csv_path = "network_speed_backup.csv"

    def append(self, record: MeasurementRecord) -> None:
        self.appended_records.append(record)

    def replay_to_repository(self, repository: FakeRepo) -> int:
        self.replay_called += 1
        if self.fail_on_replay:
            raise RuntimeError("replay error")
        return 0


def _record() -> MeasurementRecord:
    return MeasurementRecord(
        timestamp=datetime(2026, 1, 1, 0, 0, 0),
        download_mbps=123.456,
        upload_mbps=78.9,
        device="Mac",
    )


def _config() -> SimpleNamespace:
    return SimpleNamespace(retry_max_attempts=5, device="Mac", db="db", backup_csv_path="network_speed_backup.csv")


def test_run_measurement_cycle_db_success_no_csv_append(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = FakeRepo()
    backup = FakeBackup()
    config = _config()

    monkeypatch.setattr(main, "measure_with_retry", lambda **kwargs: _record())

    main.run_measurement_cycle(repo=repo, backup=backup, config=config)

    assert len(repo.inserted_records) == 1
    assert backup.appended_records == []


def test_run_measurement_cycle_db_failure_appends_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = FakeRepo(fail_on_insert=True)
    backup = FakeBackup()
    config = _config()

    monkeypatch.setattr(main, "measure_with_retry", lambda **kwargs: _record())

    main.run_measurement_cycle(repo=repo, backup=backup, config=config)

    assert len(backup.appended_records) == 1


def test_run_measurement_cycle_measure_failure_does_not_append_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = FakeRepo()
    backup = FakeBackup()
    config = _config()

    def _raise_measurement_failure(**kwargs):
        raise MeasurementFailedError("failed")

    monkeypatch.setattr(main, "measure_with_retry", _raise_measurement_failure)

    main.run_measurement_cycle(repo=repo, backup=backup, config=config)

    assert repo.inserted_records == []
    assert backup.appended_records == []


def test_bootstrap_calls_replay_and_continues_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_repo = FakeRepo()
    fake_backup = FakeBackup(fail_on_replay=True)
    cfg = _config()
    calls = {"register": 0, "loop": 0}

    monkeypatch.setattr(main, "load_app_config", lambda base_dir='.': cfg)
    monkeypatch.setattr(main, "PostgresRepository", lambda db_config: fake_repo)
    monkeypatch.setattr(main, "CsvBackupStore", lambda csv_path: fake_backup)

    def _fake_register(schedule_module, job_callable):
        calls["register"] += 1

    def _fake_loop(schedule_module, interval_seconds=1.0, sleeper=None):
        calls["loop"] += 1

    monkeypatch.setattr(main, "register_measurement_jobs", _fake_register)
    monkeypatch.setattr(main, "run_scheduler_loop", _fake_loop)
    monkeypatch.setitem(sys.modules, "schedule", object())

    main.bootstrap_and_run(base_dir='.')

    assert fake_repo.connected is True
    assert fake_backup.replay_called == 1
    assert calls["register"] == 1
    assert calls["loop"] == 1
