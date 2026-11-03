"""Measurement health alert state and ntfy publisher."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


_logger = logging.getLogger(__name__)
_TOPIC_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_topic(topic: str) -> str:
	if not _TOPIC_PATTERN.fullmatch(topic):
		raise ValueError("ntfy topic must be 1-64 letters, digits, underscores, or hyphens")
	return topic


def publish_ntfy(
	topic: str,
	title: str,
	message: str,
	token: str | None = None,
	timeout_seconds: float = 10.0,
) -> None:
	"""Publish a plain-text message to the default ntfy server."""
	valid_topic = validate_topic(topic)
	request = Request(
		f"https://ntfy.sh/{quote(valid_topic, safe='')}",
		data=message.encode("utf-8"),
		method="POST",
		headers={
			"Content-Type": "text/plain; charset=utf-8",
			"Title": title,
		},
	)
	if token:
		request.add_header("Authorization", f"Bearer {token}")

	try:
		with urlopen(request, timeout=timeout_seconds) as response:
			if response.status < 200 or response.status >= 300:
				raise RuntimeError(f"ntfy returned HTTP {response.status}")
	except (HTTPError, URLError, TimeoutError, OSError) as exc:
		raise RuntimeError("ntfy publish failed") from exc


def load_state(path: str | Path, now_epoch: float) -> dict[str, Any]:
	state_path = Path(path)
	try:
		state = json.loads(state_path.read_text(encoding="utf-8"))
	except FileNotFoundError:
		state = {}
	except (OSError, json.JSONDecodeError) as exc:
		_logger.warning("health monitor state could not be read; starting fresh: %s", exc)
		state = {}

	if not isinstance(state, dict):
		state = {}
	state.setdefault("monitor_started_at", now_epoch)
	state.setdefault("incident_started_at", None)
	state.setdefault("last_notification_at", None)
	state.setdefault("incident_reason", None)
	return state


def save_state(path: str | Path, state: dict[str, Any]) -> None:
	state_path = Path(path)
	state_path.parent.mkdir(parents=True, exist_ok=True)
	fd, temporary_name = tempfile.mkstemp(prefix=f".{state_path.name}.", dir=state_path.parent)
	try:
		with os.fdopen(fd, "w", encoding="utf-8") as stream:
			json.dump(state, stream, ensure_ascii=False, sort_keys=True)
			stream.write("\n")
			stream.flush()
			os.fsync(stream.fileno())
		os.chmod(temporary_name, 0o600)
		os.replace(temporary_name, state_path)
	except Exception:
		try:
			os.unlink(temporary_name)
		except FileNotFoundError:
			pass
		raise
