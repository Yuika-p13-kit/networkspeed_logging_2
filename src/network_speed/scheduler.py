"""スケジューラ層。"""

from __future__ import annotations

import time
from typing import Any, Callable


SCHEDULE_MINUTES = [":00", ":10", ":20", ":30", ":40", ":50"]


def register_measurement_jobs(schedule_module: Any, job_callable: Callable[[], None]) -> None:
	for minute in SCHEDULE_MINUTES:
		schedule_module.every().hour.at(minute).do(job_callable)


def run_scheduler_loop(
	schedule_module: Any,
	interval_seconds: float = 1.0,
	sleeper: Callable[[float], None] = time.sleep,
) -> None:
	while True:
		schedule_module.run_pending()
		sleeper(interval_seconds)
