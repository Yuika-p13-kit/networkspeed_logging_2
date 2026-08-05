"""PostgreSQL 永続化層。"""

from __future__ import annotations

import logging
from typing import Any

from .models import DatabaseConfig, MeasurementRecord


_VALID_SCHEMA_MIGRATION_MODES = {"v1_only", "dual_write", "v2_only"}
_logger = logging.getLogger(__name__)


class PostgresRepository:
	def __init__(self, config: DatabaseConfig, schema_migration_mode: str = "v1_only"):
		if schema_migration_mode not in _VALID_SCHEMA_MIGRATION_MODES:
			raise ValueError(
				"invalid schema_migration_mode: "
				f"{schema_migration_mode}. expected one of {', '.join(sorted(_VALID_SCHEMA_MIGRATION_MODES))}"
			)
		self._config = config
		self._schema_migration_mode = schema_migration_mode
		self._connection: Any | None = None

	def connect(self) -> None:
		if self._connection is not None:
			return

		try:
			import psycopg2
		except ImportError as exc:
			raise RuntimeError("psycopg2 is required to use PostgresRepository") from exc

		self._connection = psycopg2.connect(
			host=self._config.host,
			dbname=self._config.database,
			user=self._config.user,
			password=self._config.password,
			port=self._config.port,
		)

	def close(self) -> None:
		if self._connection is None:
			return
		self._connection.close()
		self._connection = None

	def insert_measurement(self, record: MeasurementRecord) -> None:
		connection = self._require_connection()

		if self._schema_migration_mode == "v1_only":
			with connection.cursor() as cursor:
				self._insert_v1(cursor=cursor, record=record)
			connection.commit()
			return

		if self._schema_migration_mode == "dual_write":
			with connection.cursor() as cursor:
				self._insert_v1(cursor=cursor, record=record)
			connection.commit()

			try:
				with connection.cursor() as cursor:
					self._insert_v2(cursor=cursor, record=record)
				connection.commit()
			except Exception:
				connection.rollback()
				_logger.warning(
					"v2 insert failed after successful v1 commit in dual_write mode",
					exc_info=True,
				)
			return

		with connection.cursor() as cursor:
			self._insert_v2(cursor=cursor, record=record)
		connection.commit()

	@staticmethod
	def _insert_v1(cursor: Any, record: MeasurementRecord) -> None:
		cursor.execute(
			"""
			INSERT INTO network_speed_measurements
				(timestamp, download_speed_Mbps, upload_speed_Mbps, device)
			VALUES (%s, %s, %s, %s)
			""",
			(
				record.timestamp,
				record.download_mbps,
				record.upload_mbps,
				record.device,
			),
		)

	@staticmethod
	def _insert_v2(cursor: Any, record: MeasurementRecord) -> None:
		cursor.execute(
			"""
			INSERT INTO network_speed_logs_v2
				(measured_at, download_mbps, upload_mbps, ping_ms, device, status, error)
			VALUES (%s, %s, %s, %s, %s, %s, %s)
			""",
			(
				record.timestamp,
				record.download_mbps,
				record.upload_mbps,
				None,
				record.device,
				"success",
				None,
			),
		)

	def fetch_latest(self) -> MeasurementRecord | None:
		connection = self._require_connection()
		with connection.cursor() as cursor:
			if self._schema_migration_mode == "v2_only":
				cursor.execute(
					"""
					SELECT measured_at, download_mbps, upload_mbps, device
					FROM network_speed_logs_v2
					ORDER BY measured_at DESC
					LIMIT 1
					"""
				)
			else:
				cursor.execute(
					"""
					SELECT timestamp, download_speed_Mbps, upload_speed_Mbps, device
					FROM network_speed_measurements
					ORDER BY timestamp DESC
					LIMIT 1
					"""
				)
			row = cursor.fetchone()

		if row is None:
			return None
		return self._row_to_record(row)

	def fetch_history(self, limit: int) -> list[MeasurementRecord]:
		if limit < 1:
			raise ValueError("limit must be >= 1")

		connection = self._require_connection()
		with connection.cursor() as cursor:
			if self._schema_migration_mode == "v2_only":
				cursor.execute(
					"""
					SELECT measured_at, download_mbps, upload_mbps, device
					FROM network_speed_logs_v2
					ORDER BY measured_at DESC
					LIMIT %s
					""",
					(limit,),
				)
			else:
				cursor.execute(
					"""
					SELECT timestamp, download_speed_Mbps, upload_speed_Mbps, device
					FROM network_speed_measurements
					ORDER BY timestamp DESC
					LIMIT %s
					""",
					(limit,),
				)
			rows = cursor.fetchall()

		return [self._row_to_record(row) for row in rows]

	def _require_connection(self) -> Any:
		if self._connection is None:
			raise RuntimeError("database connection is not established")
		return self._connection

	@staticmethod
	def _row_to_record(row: tuple[Any, Any, Any, Any]) -> MeasurementRecord:
		timestamp, download_mbps, upload_mbps, device = row
		return MeasurementRecord(
			timestamp=timestamp,
			download_mbps=float(download_mbps),
			upload_mbps=float(upload_mbps),
			device=str(device),
		)
