from datetime import datetime, timezone

from fastapi.testclient import TestClient

from network_speed.models import MeasurementRecord
from network_speed.web import create_app


class DummyRepoLatest:
    def __init__(self, record=None):
        self._record = record

    def fetch_latest(self):
        return self._record


class DummyRepoHistory:
    def __init__(self, records):
        self._records = records

    def fetch_history_with_filters(self, from_, to_, limit, offset):
        # ignore from_/to_ for simplicity in tests
        total = len(self._records)
        records = self._records[offset: offset + limit]
        return total, records


class DummyRepoStats:
    def __init__(self, stats):
        self._stats = stats

    def fetch_stats(self, from_, to_):
        return self._stats


def make_record(ts, d, u, device="Mac"):
    return MeasurementRecord(timestamp=ts, download_mbps=d, upload_mbps=u, device=device)


def test_latest_returns_expected_shape():
    ts = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    rec = make_record(ts, 120.1234, 20.4567, device="Mac")
    repo = DummyRepoLatest(record=rec)
    app = create_app(repo)
    client = TestClient(app)

    r = client.get("/api/dashboard/latest")
    assert r.status_code == 200
    data = r.json()
    assert data["timestamp"] == "2026-08-09T12:00:00+00:00"
    assert abs(data["download_speed_mbps"] - 120.123) < 0.001
    assert abs(data["upload_speed_mbps"] - 20.457) < 0.001
    assert data["device"] == "Mac"
    assert data["status"] == "success"


def test_history_enforces_limit_and_returns_total():
    base = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)
    records = [make_record(base, i * 10.0 + 1.0, i * 1.0 + 0.5) for i in range(5)]
    repo = DummyRepoHistory(records=records)
    app = create_app(repo)
    client = TestClient(app)

    r = client.get("/api/dashboard/history?limit=2&offset=1")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert len(data["records"]) == 2


def test_from_greater_than_to_returns_400():
    # use a repo that won't be called
    repo = DummyRepoHistory(records=[])
    app = create_app(repo)
    client = TestClient(app)

    r = client.get("/api/dashboard/history?from=2026-08-10T00:00:00Z&to=2026-08-09T00:00:00Z")
    assert r.status_code == 400


def test_stats_endpoint_returns_values():
    stats = {
        "count": 3,
        "avg_download_mbps": 50.0,
        "max_download_mbps": 100.0,
        "min_download_mbps": 10.0,
        "avg_upload_mbps": 5.0,
        "max_upload_mbps": 10.0,
        "min_upload_mbps": 1.0,
    }
    repo = DummyRepoStats(stats=stats)
    app = create_app(repo)
    client = TestClient(app)

    r = client.get("/api/dashboard/stats?from=2026-08-01T00:00:00Z&to=2026-08-09T00:00:00Z")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 3
    assert data["avg_download_mbps"] == 50.0
