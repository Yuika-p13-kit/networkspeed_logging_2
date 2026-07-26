"""CSV バックアップ層。"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .models import MeasurementRecord


class MeasurementWriter(Protocol):
	def insert_measurement(self, record: MeasurementRecord) -> None:
		...


class CsvBackupStore:
	def __init__(self, csv_path: Path | str):
		self.csv_path = Path(csv_path)

	def append(self, record: MeasurementRecord) -> None:
		self.csv_path.parent.mkdir(parents=True, exist_ok=True)
		with self.csv_path.open("a", newline="", encoding="utf-8") as file:
			writer = csv.writer(file)
			writer.writerow(
				[
					record.timestamp.isoformat(),
					f"{record.download_mbps:.3f}",
					f"{record.upload_mbps:.3f}",
					record.device,
				]
			)

	def load_all(self) -> list[MeasurementRecord]:
		if not self.csv_path.exists():
			return []

		results: list[MeasurementRecord] = []
		with self.csv_path.open("r", newline="", encoding="utf-8") as file:
			reader = csv.reader(file)
			for row in reader:
				if not row:
					continue
				if len(row) != 4:
					raise ValueError(f"invalid backup row: {row}")
				timestamp_raw, download_raw, upload_raw, device = row
				results.append(
					MeasurementRecord(
						timestamp=datetime.fromisoformat(timestamp_raw),
						download_mbps=float(download_raw),
						upload_mbps=float(upload_raw),
						device=device,
					)
				)
		return results

	def delete_file(self) -> None:
		self.csv_path.unlink(missing_ok=True)

	def replay_to_repository(self, repository: MeasurementWriter) -> int:
		records = self.load_all()
		replayed = 0
		for record in records:
			repository.insert_measurement(record)
			replayed += 1
		if records:
			self.delete_file()
		return replayed
