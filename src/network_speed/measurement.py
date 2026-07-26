"""速度計測層。"""

from __future__ import annotations

import json
import socket
import subprocess
import time
from datetime import datetime, timezone
from typing import Callable

from .models import MeasurementRecord


SERVER_ID = "XXXX"


class MeasurementFailedError(Exception):
	pass


def run_speedtest() -> dict:
	result = {
		"timestamp": datetime.now(timezone.utc).isoformat(),
		"download": 0.0,
		"upload": 0.0,
		"ping": 0.0,
		"device": socket.gethostname(),
		"server_id": SERVER_ID,
		"error": None,
	}

	command = ["speedtest", "--format=json", "--server-id", SERVER_ID]
	try:
		completed = subprocess.run(
			command,
			capture_output=True,
			text=True,
			timeout=60,
			check=False,
		)
	except Exception as exc:
		result["error"] = f"failed to execute speedtest: {exc}"
		return result

	if completed.returncode != 0:
		error_detail = completed.stderr.strip() or completed.stdout.strip()
		if not error_detail:
			error_detail = f"exit code {completed.returncode}"
		result["error"] = f"speedtest command failed: {error_detail}"
		return result

	try:
		payload = json.loads(completed.stdout)
	except json.JSONDecodeError as exc:
		result["error"] = f"failed to parse speedtest json: {exc}"
		return result

	try:
		download_bandwidth = float(payload["download"]["bandwidth"])
		upload_bandwidth = float(payload["upload"]["bandwidth"])
		ping_latency = float(payload["ping"]["latency"])
	except (KeyError, TypeError, ValueError) as exc:
		result["error"] = f"missing or invalid fields in speedtest json: {exc}"
		return result

	result["download"] = round(download_bandwidth * 8 / 1_000_000, 3)
	result["upload"] = round(upload_bandwidth * 8 / 1_000_000, 3)
	result["ping"] = round(ping_latency, 3)

	timestamp = payload.get("timestamp")
	if isinstance(timestamp, str) and timestamp:
		result["timestamp"] = timestamp

	server = payload.get("server")
	if isinstance(server, dict) and server.get("id") is not None:
		result["server_id"] = str(server["id"])

	return result


def run_speedtest_once() -> tuple[float, float]:
	result = run_speedtest()
	if result["error"] is not None:
		raise RuntimeError(str(result["error"]))

	download_bps = float(result["download"]) * 1_000_000
	upload_bps = float(result["upload"]) * 1_000_000
	return download_bps, upload_bps


def bps_to_mbps_rounded(value_bps: float) -> float:
	return round(value_bps / 1_000_000, 3)


def measure_with_retry(
	max_attempts: int = 5,
	sleep_seconds: float = 0.0,
	device: str = "Mac",
	runner: Callable[[], tuple[float, float]] = run_speedtest_once,
	time_provider: Callable[[], datetime] = datetime.now,
	sleeper: Callable[[float], None] = time.sleep,
) -> MeasurementRecord:
	if max_attempts < 1:
		raise ValueError("max_attempts must be >= 1")

	last_error: Exception | None = None
	for attempt in range(1, max_attempts + 1):
		try:
			download_bps, upload_bps = runner()
			return MeasurementRecord(
				timestamp=time_provider(),
				download_mbps=bps_to_mbps_rounded(download_bps),
				upload_mbps=bps_to_mbps_rounded(upload_bps),
				device=device,
			)
		except Exception as exc:
			last_error = exc
			if attempt < max_attempts and sleep_seconds > 0:
				sleeper(sleep_seconds)

	raise MeasurementFailedError(f"measurement failed after {max_attempts} attempts") from last_error
