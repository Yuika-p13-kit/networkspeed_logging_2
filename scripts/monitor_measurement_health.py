#!/usr/bin/env python3
"""Check measurement freshness and send ntfy incident/reminder/recovery alerts."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
	sys.path.insert(0, str(SRC_DIR))

import psycopg2

from network_speed.config import load_app_config
from network_speed.health_monitor import load_state, publish_ntfy, save_state


_logger = logging.getLogger("measurement_health")
DEFAULT_STALE_AFTER_MINUTES = 30
DEFAULT_REMINDER_INTERVAL_HOURS = 24


def _positive_int(name: str, default: int) -> int:
	raw_value = os.getenv(name, str(default))
	try:
		value = int(raw_value)
	except ValueError as exc:
		raise ValueError(f"{name} must be a positive integer") from exc
	if value <= 0:
		raise ValueError(f"{name} must be a positive integer")
	return value


def _latest_successful_measurement(config: Any) -> datetime | None:
	connection = psycopg2.connect(
		host=config.db.host,
		dbname=config.db.database,
		user=config.db.user,
		password=config.db.password,
		port=config.db.port,
		connect_timeout=8,
	)
	try:
		with connection:
			with connection.cursor() as cursor:
				cursor.execute("SET LOCAL statement_timeout = '5s'")
				cursor.execute(
					"""
					SELECT max(measured_at)
					FROM network_speed_logs_v2
					WHERE status = 'success'
					"""
				)
				return cursor.fetchone()[0]
	finally:
		connection.close()


def _service_is_active(service_name: str) -> bool:
	result = subprocess.run(
		["systemctl", "is-active", "--quiet", service_name],
		check=False,
		timeout=5,
	)
	return result.returncode == 0


def _recent_error_summary(service_name: str) -> str | None:
	try:
		result = subprocess.run(
			[
				"journalctl",
				"-u",
				service_name,
				"-n",
				"100",
				"--since",
				"24 hours ago",
				"--no-pager",
				"-o",
				"cat",
			],
			capture_output=True,
			text=True,
			check=False,
			timeout=5,
		)
		if result.returncode != 0:
			return None
		error_lines = [
			line.strip()
			for line in result.stdout.splitlines()
			if line.strip()
			and any(
				marker in line.lower()
				for marker in ("[error]", "failed", "traceback", "失敗", "例外", "エラー")
			)
		]
		summary = " | ".join(error_lines[-3:])
		return summary[-800:] if summary else None
	except (OSError, subprocess.TimeoutExpired):
		return None


def _epoch(value: datetime) -> float:
	if value.tzinfo is None:
		return value.timestamp()
	return value.astimezone(timezone.utc).timestamp()


def _format_local_epoch(value: float | None) -> str:
	if value is None:
		return "なし"
	return datetime.fromtimestamp(value).astimezone().isoformat(timespec="seconds")


def _message(reason: str, last_success_epoch: float | None, error_summary: str | None) -> str:
	parts = [
		"network-speed の計測が停止または長時間成功していません。",
		f"状態: {reason}",
		f"最終成功計測: {_format_local_epoch(last_success_epoch)}",
	]
	if error_summary:
		parts.append(f"直近のエラー: {error_summary}")
	return "\n".join(parts)


def _publish(topic: str, title: str, message: str, token: str | None) -> bool:
	try:
		publish_ntfy(topic=topic, title=title, message=message, token=token)
		return True
	except Exception:
		_logger.exception("ntfy notification could not be delivered")
		return False


def run_health_check() -> int:
	logging.basicConfig(
		level=logging.INFO,
		format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
	)
	topic = os.getenv("NETWORK_SPEED_NTFY_TOPIC", "").strip()
	if not topic:
		_logger.info("ntfy topic is not configured; health alerts are disabled")
		return 0

	now_epoch = datetime.now().astimezone().timestamp()
	state_path = os.getenv(
		"NETWORK_SPEED_HEALTH_STATE_PATH",
		"/var/lib/network-speed-health/state.json",
	)
	state = load_state(state_path, now_epoch)
	stale_after = _positive_int(
		"NETWORK_SPEED_MEASUREMENT_STALE_MINUTES", DEFAULT_STALE_AFTER_MINUTES
	) * 60
	reminder_interval = _positive_int(
		"NETWORK_SPEED_HEALTH_REMINDER_HOURS", DEFAULT_REMINDER_INTERVAL_HOURS
	) * 60 * 60
	service_name = os.getenv("NETWORK_SPEED_SERVICE_NAME", "network-speed.service")
	token = os.getenv("NETWORK_SPEED_NTFY_TOKEN") or None

	last_success_epoch: float | None = None
	current_success_epoch: float | None = None
	database_query_succeeded = False
	reason: str | None = None
	error_summary: str | None = None
	try:
		config = load_app_config(PROJECT_ROOT)
		latest_success = _latest_successful_measurement(config)
		database_query_succeeded = True
		if latest_success is not None:
			current_success_epoch = _epoch(latest_success)
	except Exception:
		_logger.exception("latest successful measurement could not be read")
		reason = "DBから計測状態を確認できません"
	last_success_epoch = current_success_epoch
	if last_success_epoch is None:
		cached_success = state.get("last_success_at")
		if cached_success is not None:
			last_success_epoch = float(cached_success)

	try:
		service_active = _service_is_active(service_name)
	except (OSError, subprocess.TimeoutExpired):
		_logger.exception("measurement service state could not be read")
		service_active = False

	if reason is None and not service_active:
		reason = f"{service_name} が active ではありません"
	if reason is None:
		if current_success_epoch is None and state.get("last_success_at") is not None:
			reason = "DBに以前の成功計測記録が見つかりません"
		elif current_success_epoch is None:
			age_seconds = now_epoch - float(state["monitor_started_at"])
			if age_seconds >= stale_after:
				reason = "成功した計測記録がまだありません"
		elif now_epoch - current_success_epoch >= stale_after:
			reason = f"最終成功計測から{int((now_epoch - current_success_epoch) // 60)}分経過しています"

	if current_success_epoch is not None:
		state["last_success_at"] = current_success_epoch

	incident_started_at = state.get("incident_started_at")
	if (
		incident_started_at is not None
		and reason is None
		and service_active
		and database_query_succeeded
		and current_success_epoch is not None
		and current_success_epoch > float(incident_started_at)
	):
		state["recovery_pending"] = {
			"recovered_at": now_epoch,
			"last_success_at": current_success_epoch,
		}
		state["incident_started_at"] = None
		state["last_notification_at"] = None
		state["incident_reason"] = None

	if reason is not None:
		error_summary = _recent_error_summary(service_name)
		if state.get("incident_started_at") is None:
			state["incident_started_at"] = now_epoch
			state["last_notification_at"] = None
		state["incident_reason"] = reason
		last_notification_at = state.get("last_notification_at")
		should_notify = (
			last_notification_at is None
			or now_epoch - float(last_notification_at) >= reminder_interval
		)
		if should_notify:
			title = "Network speed measurement stopped" if last_notification_at is None else "Network speed still unavailable"
			message = _message(reason, last_success_epoch, error_summary)
			pending_recovery = state.get("recovery_pending")
			if pending_recovery and last_notification_at is None:
				message = (
					"前回の障害は計測再開を確認しましたが、復旧通知が未配信です。\n"
					+ message
				)
			if _publish(topic, title, message, token):
				state["last_notification_at"] = now_epoch
				state["recovery_pending"] = None
	elif state.get("incident_started_at") is None and state.get("recovery_pending"):
		pending_recovery = state["recovery_pending"]
		message = (
			"network-speed の計測が再開しました。\n"
			f"復旧確認時刻: {_format_local_epoch(float(pending_recovery['recovered_at']))}\n"
			f"最終成功計測: {_format_local_epoch(float(pending_recovery['last_success_at']))}"
		)
		if _publish(topic, "Network speed measurement recovered", message, token):
			state["recovery_pending"] = None

	try:
		save_state(state_path, state)
	except OSError:
		_logger.exception("health monitor state could not be saved")
		return 1
	return 0


if __name__ == "__main__":
	raise SystemExit(run_health_check())
