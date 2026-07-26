#!/usr/bin/env python3
"""dual_write の疎通確認を 1 レコードで行うスクリプト。"""

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
from network_speed.models import MeasurementRecord
from network_speed.repository import PostgresRepository


def _resolve_file_values() -> tuple[dict[str, str], str]:
    root_info = PROJECT_ROOT / "database_info.txt"
    old_info = PROJECT_ROOT / "old_src" / "database_info.txt"

    if root_info.exists():
        return parse_database_info_file(str(root_info)), str(root_info)
    if old_info.exists():
        return parse_database_info_file(str(old_info)), str(old_info)
    return {}, "(none)"


def _generate_device() -> str:
    # v1 は varchar(8) のため 8 文字固定で生成
    return f"V{int(datetime.now().timestamp() * 1000) % 10_000_000:07d}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="dual_write 検証")
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="検証用データを削除せず残す",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    file_values, file_source = _resolve_file_values()

    try:
        db_config = build_database_config(env=os.environ, file_values=file_values)
    except Exception as exc:
        print(f"error: database config resolve failed: {exc}")
        return 1

    record = MeasurementRecord(
        timestamp=datetime.now(),
        download_mbps=111.111,
        upload_mbps=22.222,
        device=_generate_device(),
    )

    repo = PostgresRepository(db_config, schema_migration_mode="dual_write")

    v1_count = 0
    v2_count = 0
    cleanup_done = False

    try:
        repo.connect()
        repo.insert_measurement(record)
        repo.close()

        connection = psycopg2.connect(
            host=db_config.host,
            dbname=db_config.database,
            user=db_config.user,
            password=db_config.password,
            port=db_config.port,
        )
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM network_speed_measurements WHERE device = %s",
                    (record.device,),
                )
                v1_count = int(cursor.fetchone()[0])

                cursor.execute(
                    "SELECT count(*) FROM network_speed_logs_v2 WHERE device = %s AND status = 'success'",
                    (record.device,),
                )
                v2_count = int(cursor.fetchone()[0])

                if not args.no_cleanup:
                    cursor.execute(
                        "DELETE FROM network_speed_measurements WHERE device = %s",
                        (record.device,),
                    )
                    cursor.execute(
                        "DELETE FROM network_speed_logs_v2 WHERE device = %s",
                        (record.device,),
                    )
                    cleanup_done = True
        connection.close()
    except Exception as exc:
        try:
            repo.close()
        except Exception:
            pass
        print(f"error: verify failed: {exc}")
        return 1

    print("verify_dual_write: ok")
    print(f"source_file={file_source}")
    print(f"device={record.device} v1_count={v1_count} v2_count={v2_count}")
    print(f"cleanup={'done' if cleanup_done else 'skipped'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
