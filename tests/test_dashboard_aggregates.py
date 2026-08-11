from datetime import datetime, timezone
from fastapi.testclient import TestClient

from src.network_speed.web import create_app


class DummyRepo:
    def fetch_aggregates(self, from_, to_, group_by=None, window=None, limit=100, offset=0):
        return {
            "group_by": group_by,
            "window": window,
            "rows": [
                {"group": "2026-08-11T07:00:00Z", "count": 6, "download_avg": 95.123, "upload_avg": 12.345},
                {"group": "2026-08-11T08:00:00Z", "count": 6, "download_avg": 100.0, "upload_avg": 15.0},
            ],
        }


def test_aggregates_requires_from_to():
    repo = DummyRepo()
    app = create_app(repo)
    client = TestClient(app)

    r = client.get("/api/dashboard/aggregates")
    assert r.status_code == 400


def test_aggregates_with_mock_repo():
    repo = DummyRepo()
    app = create_app(repo)
    client = TestClient(app)

    from_ts = datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    to_ts = datetime(2026, 8, 11, 23, 59, tzinfo=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    r = client.get(f"/api/dashboard/aggregates?from={from_ts}&to={to_ts}&group_by=hour")
    assert r.status_code == 200
    body = r.json()
    assert body["group_by"] == "hour"
    assert isinstance(body["rows"], list)
    assert len(body["rows"]) == 2
    first = body["rows"][0]
    assert first["download_avg"] == 95.123
    assert first["count"] == 6
