"""PostgreSQL 永続化層。"""

from __future__ import annotations

import logging
from typing import Any

from .models import DatabaseConfig, MeasurementRecord


_VALID_SCHEMA_MIGRATION_MODES = {"v1_only", "dual_write", "v2_only"}
_logger = logging.getLogger(__name__)


class PostgresRepository:
	def __init__(self, config: DatabaseConfig, schema_migration_mode: str = "v2_only"):
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
			self._insert_and_commit(connection, self._insert_v1, record)
			return

		if self._schema_migration_mode == "dual_write":
			self._insert_v1_then_v2(connection, record)
			return

		self._insert_and_commit(connection, self._insert_v2, record)

	def _insert_and_commit(
		self,
		connection: Any,
		insert_func: Any,
		record: MeasurementRecord,
	) -> None:
		with connection.cursor() as cursor:
			insert_func(cursor=cursor, record=record)
		connection.commit()

	def _insert_v1_then_v2(self, connection: Any, record: MeasurementRecord) -> None:
		self._insert_and_commit(connection, self._insert_v1, record)

		try:
			self._insert_and_commit(connection, self._insert_v2, record)
		except Exception:
			connection.rollback()
			_logger.warning(
				"v2 insert failed after successful v1 commit in dual_write mode",
				exc_info=True,
			)

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
			cursor.execute(self._latest_measurement_sql())
			row = cursor.fetchone()

		if row is None:
			return None
		return self._row_to_record(row)

	def fetch_history(self, limit: int) -> list[MeasurementRecord]:
		if limit < 1:
			raise ValueError("limit must be >= 1")

		connection = self._require_connection()
		with connection.cursor() as cursor:
			cursor.execute(self._history_measurement_sql(), (limit,))
			rows = cursor.fetchall()

		return [self._row_to_record(row) for row in rows]

	def _latest_measurement_sql(self) -> str:
		if self._schema_migration_mode == "v2_only":
			return """
			SELECT measured_at, download_mbps, upload_mbps, device, status, error
			FROM network_speed_logs_v2
			ORDER BY measured_at DESC
			LIMIT 1
			"""
		return """
		SELECT timestamp, download_speed_Mbps, upload_speed_Mbps, device
		FROM network_speed_measurements
		ORDER BY timestamp DESC
		LIMIT 1
		"""

	def _history_measurement_sql(self) -> str:
		if self._schema_migration_mode == "v2_only":
			return """
			SELECT measured_at, download_mbps, upload_mbps, device, status, error
			FROM network_speed_logs_v2
			ORDER BY measured_at DESC
			LIMIT %s
			"""
		return """
		SELECT timestamp, download_speed_Mbps, upload_speed_Mbps, device
		FROM network_speed_measurements
		ORDER BY timestamp DESC
		LIMIT %s
		"""

	def _require_connection(self) -> Any:
		if self._connection is None:
			raise RuntimeError("database connection is not established")
		return self._connection

	@staticmethod
	def _row_to_record(row: tuple[Any, ...]) -> MeasurementRecord:
		# support both v1 (4 cols) and v2 (6 cols with status, error)
		if len(row) >= 6:
			timestamp, download_mbps, upload_mbps, device, status, error = row[:6]
		else:
			timestamp, download_mbps, upload_mbps, device = row[:4]
			status = None
			error = None
		return MeasurementRecord(
			timestamp=timestamp,
			download_mbps=float(download_mbps),
			upload_mbps=float(upload_mbps),
			device=str(device),
			status=status,
			error_summary=error,
		)

	def fetch_stats(self, from_, to_) -> dict:
		"""Return aggregated stats between from_ and to_.

		Returns dict with keys: count, avg_download_mbps, max_download_mbps, min_download_mbps,
		avg_upload_mbps, max_upload_mbps, min_upload_mbps
		"""
		if from_ is None or to_ is None:
			raise ValueError("from_ and to_ are required")

		connection = self._require_connection()
		with connection.cursor() as cursor:
			if self._schema_migration_mode == "v2_only":
				cursor.execute(
					"""
					SELECT COUNT(*), AVG(download_mbps), MAX(download_mbps), MIN(download_mbps),
					       AVG(upload_mbps), MAX(upload_mbps), MIN(upload_mbps)
					FROM network_speed_logs_v2
					WHERE measured_at >= %s AND measured_at <= %s
					""",
					(from_, to_),
				)
			else:
				cursor.execute(
					"""
					SELECT COUNT(*), AVG(download_speed_Mbps), MAX(download_speed_Mbps), MIN(download_speed_Mbps),
					       AVG(upload_speed_Mbps), MAX(upload_speed_Mbps), MIN(upload_speed_Mbps)
					FROM network_speed_measurements
					WHERE timestamp >= %s AND timestamp <= %s
					""",
					(from_, to_),
				)
			row = cursor.fetchone()

		count, avg_d, max_d, min_d, avg_u, max_u, min_u = row
		if count == 0:
			return {
				"count": 0,
				"avg_download_mbps": None,
				"max_download_mbps": None,
				"min_download_mbps": None,
				"avg_upload_mbps": None,
				"max_upload_mbps": None,
				"min_upload_mbps": None,
			}

		return {
			"count": int(count),
			"avg_download_mbps": round(float(avg_d), 3) if avg_d is not None else None,
			"max_download_mbps": round(float(max_d), 3) if max_d is not None else None,
			"min_download_mbps": round(float(min_d), 3) if min_d is not None else None,
			"avg_upload_mbps": round(float(avg_u), 3) if avg_u is not None else None,
			"max_upload_mbps": round(float(max_u), 3) if max_u is not None else None,
			"min_upload_mbps": round(float(min_u), 3) if min_u is not None else None,
		}
