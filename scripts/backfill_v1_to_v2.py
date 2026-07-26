#!/usr/bin/env python3
"""v1 テーブルから v2 テーブルへ再実行可能にバックフィルする。"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from network_speed.config import build_database_config, parse_database_info_file


def _resolve_file_values() -> tuple[dict[str, str], str]:
    root_info = PROJECT_ROOT / "database_info.txt"
    old_info = PROJECT_ROOT / "old_src" / "database_info.txt"

    if root_info.exists():
        return parse_database_info_file(str(root_info)), str(root_info)
    if old_info.exists():
        return parse_database_info_file(str(old_info)), str(old_info)
    return {}, "(none)"


def _parse_since(raw: str | None) -> datetime | None:
    if raw is None:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError as exc:
        raise ValueError("--since は 'YYYY-MM-DD HH:MM:SS' 形式で指定してください") from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="v1 から v2 へのバックフィル")
    parser.add_argument("--dry-run", action="store_true", help="投入せず件数のみ表示")
    parser.add_argument("--since", type=str, default=None, help="下限時刻 (YYYY-MM-DD HH:MM:SS)")
    return parser.parse_args()


def _where_clause(since_dt: datetime | None) -> str:
    return "WHERE m.timestamp >= %s" if since_dt else ""


def _count_sql(since_dt: datetime | None) -> str:
    where = _where_clause(since_dt)
    return f"""
        SELECT count(*)
        FROM network_speed_measurements AS m
        {where}
        AND NOT EXISTS (
            SELECT 1
            FROM network_speed_logs_v2 AS v
            WHERE v.measured_at = m.timestamp
              AND v.device = m.device
              AND v.download_mbps = m.download_speed_mbps
              AND v.upload_mbps = m.upload_speed_mbps
        )
    """ if where else """
        SELECT count(*)
        FROM network_speed_measurements AS m
        WHERE NOT EXISTS (
            SELECT 1
            FROM network_speed_logs_v2 AS v
            WHERE v.measured_at = m.timestamp
              AND v.device = m.device
              AND v.download_mbps = m.download_speed_mbps
              AND v.upload_mbps = m.upload_speed_mbps
        )
    """


def _insert_sql(since_dt: datetime | None) -> str:
    where = _where_clause(since_dt)
    return f"""
        INSERT INTO network_speed_logs_v2
            (measured_at, download_mbps, upload_mbps, ping_ms, device, status, error)
        SELECT
            m.timestamp,
            m.download_speed_mbps,
            m.upload_speed_mbps,
            NULL,
            m.device,
            'success',
            NULL
        FROM network_speed_measurements AS m
        {where}
        AND NOT EXISTS (
            SELECT 1
            FROM network_speed_logs_v2 AS v
            WHERE v.measured_at = m.timestamp
              AND v.device = m.device
              AND v.download_mbps = m.download_speed_mbps
              AND v.upload_mbps = m.upload_speed_mbps
        )
    """ if where else """
        INSERT INTO network_speed_logs_v2
            (measured_at, download_mbps, upload_mbps, ping_ms, device, status, error)
        SELECT
            m.timestamp,
            m.download_speed_mbps,
            m.upload_speed_mbps,
            NULL,
            m.device,
            'success',
            NULL
        FROM network_speed_measurements AS m
        WHERE NOT EXISTS (
            SELECT 1
            FROM network_speed_logs_v2 AS v
            WHERE v.measured_at = m.timestamp
              AND v.device = m.device
              AND v.download_mbps = m.download_speed_mbps
              AND v.upload_mbps = m.upload_speed_mbps
        )
    """


def _build_params(since_dt: datetime | None) -> tuple[object, ...]:
    if since_dt:
        return (since_dt,)
    return ()


def main(args: argparse.Namespace) -> int:
    file_values, file_source = _resolve_file_values()

    try:
        db_config = build_database_config(env=os.environ, file_values=file_values)
        params = _build_params(args.since_dt)
    except Exception as exc:
        print(f"error: config parse failed: {exc}")
        return 1

    try:
        connection = psycopg2.connect(
            host=db_config.host,
            dbname=db_config.database,
            user=db_config.user,
            password=db_config.password,
            port=db_config.port,
        )

        with connection:
            with connection.cursor() as cursor:
                cursor.execute(_count_sql(args.since_dt), params)
                target_count = int(cursor.fetchone()[0])

                if args.dry_run:
                    print("backfill_v1_to_v2: dry-run")
                    print(f"source_file={file_source}")
                    print(f"since={args.since if args.since else '(none)'}")
                    print(f"target_count={target_count}")
                    return 0

                cursor.execute(_insert_sql(args.since_dt), params)
                inserted = cursor.rowcount

        connection.close()
    except Exception as exc:
        print(f"error: backfill failed: {exc}")
        return 1

    print("backfill_v1_to_v2: ok")
    print(f"source_file={file_source}")
    print(f"since={args.since if args.since else '(none)'}")
    print(f"target_count={target_count} inserted_count={inserted}")
    return 0


if __name__ == "__main__":
    args = _parse_args()
    try:
        args.since_dt = _parse_since(args.since)
    except ValueError as exc:
        print(f"error: {exc}")
        raise SystemExit(2)
    raise SystemExit(main(args))
