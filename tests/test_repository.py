from datetime import datetime

import pytest

from network_speed.models import DatabaseConfig, MeasurementRecord
from network_speed.repository import PostgresRepository


class FakeCursor:
    def __init__(self, fetchone_result=None, fetchall_result=None):
        self.fetchone_result = fetchone_result
        self.fetchall_result = fetchall_result or []
        self.executed: list[tuple[str, tuple | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self.executed.append((sql, params))

    def fetchone(self):
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor
        self.commit_count = 0
        self.close_count = 0

    def cursor(self) -> FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.commit_count += 1

    def close(self) -> None:
        self.close_count += 1


def _repo() -> PostgresRepository:
    config = DatabaseConfig(
        host="localhost",
        database="netdb",
        user="tester",
        password="secret",
        port=5432,
    )
    return PostgresRepository(config)


def test_insert_measurement_commits() -> None:
    repo = _repo()
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    repo._connection = connection

    record = MeasurementRecord(
        timestamp=datetime(2026, 1, 1, 0, 0, 0),
        download_mbps=123.456,
        upload_mbps=78.9,
        device="Mac",
    )

    repo.insert_measurement(record)

    assert connection.commit_count == 1
    assert len(cursor.executed) == 1
    sql, params = cursor.executed[0]
    assert "INSERT INTO network_speed_measurements" in sql
    assert params == (
        record.timestamp,
        record.download_mbps,
        record.upload_mbps,
        record.device,
    )


def test_fetch_latest_returns_none_when_empty() -> None:
    repo = _repo()
    cursor = FakeCursor(fetchone_result=None)
    repo._connection = FakeConnection(cursor)

    record = repo.fetch_latest()

    assert record is None


def test_fetch_latest_returns_measurement_record() -> None:
    repo = _repo()
    timestamp = datetime(2026, 1, 1, 0, 10, 0)
    cursor = FakeCursor(fetchone_result=(timestamp, 10.123, 5.678, "Mac"))
    repo._connection = FakeConnection(cursor)

    record = repo.fetch_latest()

    assert record is not None
    assert record.timestamp == timestamp
    assert record.download_mbps == pytest.approx(10.123)
    assert record.upload_mbps == pytest.approx(5.678)
    assert record.device == "Mac"


def test_fetch_history_limit_and_order() -> None:
    repo = _repo()
    rows = [
        (datetime(2026, 1, 1, 0, 20, 0), 20.0, 10.0, "Mac"),
        (datetime(2026, 1, 1, 0, 10, 0), 10.0, 5.0, "Mac"),
    ]
    cursor = FakeCursor(fetchall_result=rows)
    repo._connection = FakeConnection(cursor)

    records = repo.fetch_history(limit=2)

    assert len(records) == 2
    assert records[0].download_mbps == pytest.approx(20.0)
    assert records[1].download_mbps == pytest.approx(10.0)
    sql, params = cursor.executed[0]
    assert "LIMIT %s" in sql
    assert params == (2,)


def test_fetch_history_rejects_invalid_limit() -> None:
    repo = _repo()

    with pytest.raises(ValueError):
        repo.fetch_history(limit=0)


def test_require_connection_guard() -> None:
    repo = _repo()
    record = MeasurementRecord(
        timestamp=datetime(2026, 1, 1, 0, 0, 0),
        download_mbps=1.0,
        upload_mbps=1.0,
        device="Mac",
    )

    with pytest.raises(RuntimeError):
        repo.insert_measurement(record)
