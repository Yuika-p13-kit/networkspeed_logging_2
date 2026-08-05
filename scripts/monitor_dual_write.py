#!/usr/bin/env python3
"""dual_write 運用時の v1/v2 整合監視スクリプト。"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timedelta
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
    parser.add_argument(
        "--mode",
        choices=("auto", "dual_write", "v2_only"),
        default="auto",
        help="判定モード（auto は NETWORK_SPEED_SCHEMA_MIGRATION_MODE を参照）",
    )
    parser.add_argument(
        "--observation-days",
        type=int,
        default=7,
        help="観測期間（日）",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=10,
        help="期待サンプル算出に使う実行間隔（分）",
    )
    parser.add_argument(
        "--min-sample-coverage",
        type=float,
        default=0.99,
        help="最小サンプル被覆率（actual/expected）",
    )
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


def _resolve_mode(arg_mode: str) -> str:
    if arg_mode != "auto":
        return arg_mode

    env_mode = os.getenv("NETWORK_SPEED_SCHEMA_MIGRATION_MODE", "").strip().lower()
    if env_mode == "v2_only":
        return "v2_only"
    return "dual_write"


def _collect_metrics(db_config: Any, observation_days: int, interval_minutes: int) -> dict[str, Any]:
    observed_at = datetime.now()
    cutoff = observed_at - timedelta(days=observation_days)

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

                cursor.execute(
                    """
                    SELECT count(*)
                    FROM network_speed_logs_v2
                    WHERE status = 'success' AND measured_at >= %s
                    """,
                    (cutoff,),
                )
                v2_success_count_in_window = int(cursor.fetchone()[0])
    finally:
        connection.close()

    count_gap = abs(v1_count - v2_success_count)
    lag_seconds = _compute_lag_seconds(v1_latest, v2_success_latest)
    expected_samples = math.floor(observation_days * 24 * 60 / interval_minutes)
    sample_coverage = (
        1.0 if expected_samples == 0 else float(v2_success_count_in_window) / float(expected_samples)
    )

    return {
        "observed_at": observed_at.isoformat(sep=" "),
        "observation_days": observation_days,
        "interval_minutes": interval_minutes,
        "window_start": cutoff.isoformat(sep=" "),
        "v1_count": v1_count,
        "v2_success_count": v2_success_count,
        "v2_success_count_in_window": v2_success_count_in_window,
        "expected_samples": expected_samples,
        "sample_coverage": sample_coverage,
        "v1_latest": v1_latest.isoformat(sep=" ") if v1_latest else None,
        "v2_success_latest": v2_success_latest.isoformat(sep=" ") if v2_success_latest else None,
        "count_gap": count_gap,
        "lag_seconds": lag_seconds,
    }


def _evaluate_checks(mode: str, metrics: dict[str, Any], args: argparse.Namespace) -> tuple[str, str, dict[str, Any]]:
    checks: dict[str, Any] = {}

    sample_coverage = float(metrics["sample_coverage"])
    sample_coverage_pass = sample_coverage >= args.min_sample_coverage
    checks["sample_coverage"] = {
        "pass": sample_coverage_pass,
        "value": sample_coverage,
        "threshold": args.min_sample_coverage,
    }

    if mode == "dual_write":
        count_gap = int(metrics["count_gap"])
        lag_seconds = metrics["lag_seconds"]

        count_gap_pass = count_gap <= args.max_count_gap
        lag_seconds_pass = lag_seconds is not None and lag_seconds <= args.max_lag_seconds

        checks["count_gap"] = {
            "pass": count_gap_pass,
            "value": count_gap,
            "threshold": args.max_count_gap,
        }
        checks["lag_seconds"] = {
            "pass": lag_seconds_pass,
            "value": lag_seconds,
            "threshold": args.max_lag_seconds,
        }

        decision = "go" if (sample_coverage_pass and count_gap_pass and lag_seconds_pass) else "no-go"
    else:
        observed_at = datetime.fromisoformat(metrics["observed_at"])
        v2_latest_str = metrics["v2_success_latest"]
        freshness_seconds: int | None = None
        if v2_latest_str is not None:
            freshness_seconds = int(abs((observed_at - datetime.fromisoformat(v2_latest_str)).total_seconds()))

        v2_freshness_pass = freshness_seconds is not None and freshness_seconds <= args.max_lag_seconds
        checks["v2_freshness"] = {
            "pass": v2_freshness_pass,
            "value": freshness_seconds,
            "threshold": args.max_lag_seconds,
        }

        decision = "go" if (sample_coverage_pass and v2_freshness_pass) else "no-go"

    status = "ok" if decision == "go" else "alert"
    return status, decision, checks


def main() -> int:
    args = _parse_args()
    if args.max_count_gap < 0:
        print("error: --max-count-gap は 0 以上で指定してください")
        return 1
    if args.max_lag_seconds < 0:
        print("error: --max-lag-seconds は 0 以上で指定してください")
        return 1
    if args.observation_days < 0:
        print("error: --observation-days は 0 以上で指定してください")
        return 1
    if args.interval_minutes <= 0:
        print("error: --interval-minutes は 1 以上で指定してください")
        return 1
    if args.min_sample_coverage < 0 or args.min_sample_coverage > 1:
        print("error: --min-sample-coverage は 0 以上 1 以下で指定してください")
        return 1

    file_values, file_source = _resolve_file_values()
    mode = _resolve_mode(args.mode)

    try:
        db_config = build_database_config(env=os.environ, file_values=file_values)
        metrics = _collect_metrics(
            db_config,
            observation_days=args.observation_days,
            interval_minutes=args.interval_minutes,
        )
        status, decision, checks = _evaluate_checks(mode, metrics, args)
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False))
        else:
            print(f"error: monitor failed: {exc}")
        return 1

    if args.json:
        payload = {
            "status": status,
            "mode": mode,
            "decision": decision,
            "source_file": file_source,
            "thresholds": {
                "max_count_gap": args.max_count_gap,
                "max_lag_seconds": args.max_lag_seconds,
                "observation_days": args.observation_days,
                "interval_minutes": args.interval_minutes,
                "min_sample_coverage": args.min_sample_coverage,
            },
            "metrics": metrics,
            "checks": checks,
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"monitor_dual_write: status={status} mode={mode} decision={decision}")
        print("checks:")
        for name, detail in checks.items():
            result = "pass" if detail["pass"] else "fail"
            print(
                f"  - {name}: {result} "
                f"value={detail['value']} threshold={detail['threshold']}"
            )
        print("metrics:")
        print(
            f"  v1_count={metrics['v1_count']} "
            f"v2_success_count={metrics['v2_success_count']} "
            f"count_gap={metrics['count_gap']}"
        )
        print(
            f"  v1_latest={metrics['v1_latest']} "
            f"v2_success_latest={metrics['v2_success_latest']} "
            f"lag_seconds={metrics['lag_seconds']}"
        )
        print(
            f"  sample_coverage={metrics['sample_coverage']} "
            f"actual_samples={metrics['v2_success_count_in_window']} "
            f"expected_samples={metrics['expected_samples']}"
        )
        print(
            f"thresholds max_count_gap={args.max_count_gap} "
            f"max_lag_seconds={args.max_lag_seconds} "
            f"observation_days={args.observation_days} "
            f"interval_minutes={args.interval_minutes} "
            f"min_sample_coverage={args.min_sample_coverage}"
        )
        print(f"source_file={file_source}")

    return 0 if decision == "go" else 2


if __name__ == "__main__":
    raise SystemExit(main())
