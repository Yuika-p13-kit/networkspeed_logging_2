#!/usr/bin/env python3
"""dual_write 運用時の v1/v2 整合監視スクリプト。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="dual_write 監視")
    parser.add_argument("--max-count-gap", type=int, default=0, help="許容する件数差")
    parser.add_argument(
        "--max-lag-seconds",
        type=int,
        default=120,
        help="許容する最新時刻差（秒）",
    )
    parser.add_argument("--json", action="store_true", help="JSON で出力")
    return parser.parse_args()


def _compute_lag_seconds(v1_latest: datetime | None, v2_latest: datetime | None) -> int | None:
    if v1_latest is None or v2_latest is None:
        return None
    return int(abs((v1_latest - v2_latest).total_seconds()))


def _collect_metrics(db_config: Any) -> dict[str, Any]:
    connection = psycopg2.connect(
        host=db_config.host,
        dbname=db_config.database,
        user=db_config.user,
        password=db_config.password,
        port=db_config.port,
    )

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM network_speed_measurements")
                v1_count = int(cursor.fetchone()[0])

                cursor.execute(
                    "SELECT count(*) FROM network_speed_logs_v2 WHERE status = 'success'"
                )
                v2_success_count = int(cursor.fetchone()[0])

                cursor.execute("SELECT max(timestamp) FROM network_speed_measurements")
                v1_latest = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT max(measured_at) FROM network_speed_logs_v2 WHERE status = 'success'"
                )
                v2_success_latest = cursor.fetchone()[0]
    finally:
        connection.close()

    count_gap = abs(v1_count - v2_success_count)
    lag_seconds = _compute_lag_seconds(v1_latest, v2_success_latest)

    return {
        "v1_count": v1_count,
        "v2_success_count": v2_success_count,
        "v1_latest": v1_latest.isoformat(sep=" ") if v1_latest else None,
        "v2_success_latest": v2_success_latest.isoformat(sep=" ") if v2_success_latest else None,
        "count_gap": count_gap,
        "lag_seconds": lag_seconds,
    }


def main() -> int:
    args = _parse_args()
    if args.max_count_gap < 0:
        print("error: --max-count-gap は 0 以上で指定してください")
        return 1
    if args.max_lag_seconds < 0:
        print("error: --max-lag-seconds は 0 以上で指定してください")
        return 1

    file_values, file_source = _resolve_file_values()

    try:
        db_config = build_database_config(env=os.environ, file_values=file_values)
        metrics = _collect_metrics(db_config)
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: monitor failed: {exc}")
        return 1

    count_gap = int(metrics["count_gap"])
    lag_seconds = metrics["lag_seconds"]
    lag_over = lag_seconds is not None and lag_seconds > args.max_lag_seconds
    count_over = count_gap > args.max_count_gap
    ok = not lag_over and not count_over

    if args.json:
        payload = {
            "status": "ok" if ok else "alert",
            "source_file": file_source,
            "thresholds": {
                "max_count_gap": args.max_count_gap,
                "max_lag_seconds": args.max_lag_seconds,
            },
            "metrics": metrics,
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        status = "ok" if ok else "alert"
        print(
            f"monitor_dual_write: {status} "
            f"v1_count={metrics['v1_count']} "
            f"v2_success_count={metrics['v2_success_count']} "
            f"count_gap={metrics['count_gap']} "
            f"lag_seconds={metrics['lag_seconds']}"
        )
        print(
            f"v1_latest={metrics['v1_latest']} "
            f"v2_success_latest={metrics['v2_success_latest']}"
        )
        print(
            f"thresholds max_count_gap={args.max_count_gap} "
            f"max_lag_seconds={args.max_lag_seconds}"
        )
        print(f"source_file={file_source}")

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
