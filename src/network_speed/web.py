"""読み取り専用 API / ダッシュボード層。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, List

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from .models import MeasurementRecord


class DashboardRecord(BaseModel):
    timestamp: datetime
    download_speed_mbps: float
    upload_speed_mbps: float
    device: str
    status: str = "success"
    error_summary: Optional[str] = None


class HistoryResponse(BaseModel):
    total: int
    limit: int
    offset: int
    records: List[DashboardRecord]


class StatsResponse(BaseModel):
    count: int
    avg_download_mbps: Optional[float]
    max_download_mbps: Optional[float]
    min_download_mbps: Optional[float]
    avg_upload_mbps: Optional[float]
    max_upload_mbps: Optional[float]
    min_upload_mbps: Optional[float]


def _record_to_dashboard(record: MeasurementRecord, status: str = "success", error_summary: Optional[str] = None) -> DashboardRecord:
    return DashboardRecord(
        timestamp=record.timestamp,
        download_speed_mbps=round(float(record.download_mbps), 3),
        upload_speed_mbps=round(float(record.upload_mbps), 3),
        device=record.device,
        status=status,
        error_summary=error_summary,
    )


def create_app(repo: Any):
    """Create FastAPI app for dashboard.

    repo is expected to provide at least fetch_latest() and fetch_history(...)
    For tests a lightweight mock object may be provided with the needed methods.
    """

    app = FastAPI()

    # helper to get latest
    @app.get("/api/dashboard/latest", response_model=DashboardRecord)
    def dashboard_latest():
        try:
            latest = repo.fetch_latest()
        except Exception as exc:
            raise HTTPException(status_code=500, detail="internal error") from exc

        if latest is None:
            raise HTTPException(status_code=404, detail="no records")

        # if repo exposes status/error fields use them; otherwise derive
        status = getattr(latest, "status", None)
        error_summary = getattr(latest, "error_summary", None)
        if status is None:
            # derive: success if both numbers
            try:
                _ = float(latest.download_mbps)
                _ = float(latest.upload_mbps)
                status = "success"
            except Exception:
                status = "measurement_failed"

        return _record_to_dashboard(latest, status=status, error_summary=error_summary)

    # wrapper for old /api/latest
    @app.get("/api/latest", response_model=DashboardRecord)
    def legacy_latest():
        return dashboard_latest()

    # history endpoint
    @app.get("/api/dashboard/history", response_model=HistoryResponse)
    def dashboard_history(
        from_: Optional[datetime] = Query(None, alias="from"),
        to_: Optional[datetime] = Query(None, alias="to"),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        if (from_ is not None) and (to_ is not None) and (from_ > to_):
            raise HTTPException(status_code=400, detail="from must be <= to")

        # prefer repo.fetch_history that accepts filtering/pagination
        try:
            if hasattr(repo, "fetch_history_with_filters"):
                total, records = repo.fetch_history_with_filters(from_=from_, to_=to_, limit=limit, offset=offset)
            elif hasattr(repo, "fetch_history"):
                # try calling with extended signature
                try:
                    total, records = repo.fetch_history(from_=from_, to_=to_, limit=limit, offset=offset)  # type: ignore
                except TypeError:
                    # fallback: call fetch_history(limit+offset) and slice
                    fetched = repo.fetch_history(limit + offset)
                    records = fetched[offset: offset + limit]
                    total = len(fetched)
            else:
                raise RuntimeError("repository does not implement fetch_history")
        except Exception as exc:
            raise HTTPException(status_code=500, detail="internal error") from exc

        dash_records = [_record_to_dashboard(r) for r in records]
        return HistoryResponse(total=total, limit=limit, offset=offset, records=dash_records)

    # legacy wrapper
    @app.get("/api/history", response_model=HistoryResponse)
    def legacy_history(
        from_: Optional[datetime] = Query(None, alias="from"),
        to_: Optional[datetime] = Query(None, alias="to"),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ):
        return dashboard_history(from_=from_, to_=to_, limit=limit, offset=offset)

    @app.get("/api/dashboard/stats", response_model=StatsResponse)
    def dashboard_stats(
        from_: Optional[datetime] = Query(None, alias="from"),
        to_: Optional[datetime] = Query(None, alias="to"),
    ):
        if from_ is None or to_ is None:
            raise HTTPException(status_code=400, detail="from and to are required")
        if from_ > to_:
            raise HTTPException(status_code=400, detail="from must be <= to")

        try:
            if hasattr(repo, "fetch_stats"):
                stats = repo.fetch_stats(from_=from_, to_=to_)
            else:
                # fallback: get a large slice and compute
                if hasattr(repo, "fetch_history_with_filters"):
                    total, records = repo.fetch_history_with_filters(from_=from_, to_=to_, limit=1000000, offset=0)
                elif hasattr(repo, "fetch_history"):
                    try:
                        total, records = repo.fetch_history(from_=from_, to_=to_, limit=1000000, offset=0)  # type: ignore
                    except TypeError:
                        records = repo.fetch_history(1000000)
                        total = len(records)
                else:
                    raise RuntimeError("repository does not implement history/stat retrieval")

                # compute stats
                count = len(records)
                if count == 0:
                    stats = {
                        "count": 0,
                        "avg_download_mbps": None,
                        "max_download_mbps": None,
                        "min_download_mbps": None,
                        "avg_upload_mbps": None,
                        "max_upload_mbps": None,
                        "min_upload_mbps": None,
                    }
                else:
                    downloads = [float(r.download_mbps) for r in records]
                    uploads = [float(r.upload_mbps) for r in records]
                    stats = {
                        "count": count,
                        "avg_download_mbps": sum(downloads) / count,
                        "max_download_mbps": max(downloads),
                        "min_download_mbps": min(downloads),
                        "avg_upload_mbps": sum(uploads) / count,
                        "max_upload_mbps": max(uploads),
                        "min_upload_mbps": min(uploads),
                    }
        except Exception as exc:
            raise HTTPException(status_code=500, detail="internal error") from exc

        return StatsResponse(**stats)

    return app
