"""設定読み込み層。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from .models import AppConfig, DatabaseConfig


_VALID_SCHEMA_MIGRATION_MODES = {"v1_only", "dual_write", "v2_only"}


def parse_database_info_file(file_path: str) -> dict[str, str]:
	path = Path(file_path)
	if not path.exists():
		raise FileNotFoundError(f"database info file not found: {file_path}")

	result: dict[str, str] = {}
	for line in path.read_text(encoding="utf-8").splitlines():
		stripped = line.strip()
		if not stripped or stripped.startswith("#"):
			continue
		if "=" not in stripped:
			raise ValueError(f"invalid database_info line: {stripped}")
		key, value = stripped.split("=", 1)
		key = key.strip()
		value = value.strip()
		if not key:
			raise ValueError(f"empty key in database_info line: {stripped}")
		result[key] = value
	return result


def build_database_config(
	env: Mapping[str, str],
	file_values: Mapping[str, str],
) -> DatabaseConfig:
	host = env.get("NETWORK_SPEED_DB_HOST") or file_values.get("host")
	database = env.get("NETWORK_SPEED_DB_NAME") or file_values.get("database")
	user = env.get("NETWORK_SPEED_DB_USER") or file_values.get("user")
	password = env.get("NETWORK_SPEED_DB_PASSWORD") or file_values.get("password")

	missing: list[str] = []
	if not host:
		missing.append("host")
	if not database:
		missing.append("database")
	if not user:
		missing.append("user")
	if not password:
		missing.append("password")
	if missing:
		raise ValueError(f"database config missing required keys: {', '.join(missing)}")

	port_raw = env.get("NETWORK_SPEED_DB_PORT") or file_values.get("port") or "5432"
	port = int(port_raw)

	return DatabaseConfig(
		host=host,
		database=database,
		user=user,
		password=password,
		port=port,
	)


def parse_schema_migration_mode(raw_mode: str) -> str:
	if raw_mode not in _VALID_SCHEMA_MIGRATION_MODES:
		raise ValueError(
			"invalid schema_migration_mode: "
			f"{raw_mode}. expected one of {', '.join(sorted(_VALID_SCHEMA_MIGRATION_MODES))}"
		)
	return raw_mode


def load_app_config(base_dir: Path | str = ".") -> AppConfig:
	base_path = Path(base_dir)
	database_info_path = base_path / "database_info.txt"

	file_values: dict[str, str] = {}
	if database_info_path.exists():
		file_values = parse_database_info_file(str(database_info_path))

	env = os.environ
	db = build_database_config(env=env, file_values=file_values)

	backup_csv_path = env.get("NETWORK_SPEED_BACKUP_CSV", "network_speed_backup.csv")
	device = env.get("NETWORK_SPEED_DEVICE", "Mac")
	history_limit_default = int(env.get("NETWORK_SPEED_HISTORY_LIMIT_DEFAULT", "100"))
	retry_max_attempts = int(env.get("NETWORK_SPEED_RETRY_MAX_ATTEMPTS", "5"))
	web_host = env.get("NETWORK_SPEED_WEB_HOST", "0.0.0.0")
	web_port = int(env.get("NETWORK_SPEED_WEB_PORT", "8000"))
	schema_migration_mode = parse_schema_migration_mode(
		env.get("NETWORK_SPEED_SCHEMA_MIGRATION_MODE", "v1_only")
	)

	return AppConfig(
		db=db,
		backup_csv_path=backup_csv_path,
		device=device,
		history_limit_default=history_limit_default,
		retry_max_attempts=retry_max_attempts,
		web_host=web_host,
		web_port=web_port,
		schema_migration_mode=schema_migration_mode,
	)
