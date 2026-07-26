from collections.abc import Callable

from network_speed.scheduler import SCHEDULE_MINUTES, register_measurement_jobs


class FakeEvery:
    def __init__(self, module: "FakeScheduleModule"):
        self._module = module

    @property
    def hour(self) -> "FakeEvery":
        return self

    def at(self, minute: str) -> "FakeEvery":
        self._module.registered_minutes.append(minute)
        return self

    def do(self, job_callable: Callable[[], None]) -> None:
        self._module.registered_jobs.append(job_callable)


class FakeScheduleModule:
    def __init__(self):
        self.registered_minutes: list[str] = []
        self.registered_jobs: list[Callable[[], None]] = []

    def every(self) -> FakeEvery:
        return FakeEvery(self)


def test_register_measurement_jobs_registers_all_minutes() -> None:
    schedule_module = FakeScheduleModule()

    register_measurement_jobs(schedule_module=schedule_module, job_callable=lambda: None)

    assert schedule_module.registered_minutes == SCHEDULE_MINUTES
    assert len(schedule_module.registered_jobs) == 6
