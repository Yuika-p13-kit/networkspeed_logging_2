from __future__ import annotations

import logging
from pathlib import Path

from network_speed.backup import CsvBackupStore
from network_speed.config import load_app_config
from network_speed.measurement import MeasurementFailedError, measure_with_retry
from network_speed.models import AppConfig
from network_speed.repository import PostgresRepository
from network_speed.scheduler import register_measurement_jobs, run_scheduler_loop


logger = logging.getLogger(__name__)


def run_measurement_cycle(
    repo: PostgresRepository,
    backup: CsvBackupStore,
    config: AppConfig,
) -> None:
    try:
        record = measure_with_retry(
            max_attempts=config.retry_max_attempts,
            device=config.device,
        )
    except MeasurementFailedError as exc:
        logger.error("計測に失敗しました: %s", exc)
        return
    except Exception as exc:  # 防御的: 予期しない計測例外でも運用継続
        logger.error("計測処理で予期しないエラー: %s", exc)
        return

    try:
        repo.insert_measurement(record)
        logger.info(
            "DB保存成功: timestamp=%s download=%.3f upload=%.3f device=%s",
            record.timestamp.isoformat(),
            record.download_mbps,
            record.upload_mbps,
            record.device,
        )
    except Exception as exc:
        logger.error("DB保存失敗。CSVへ退避します: %s", exc)
        try:
            backup.append(record)
            logger.info("CSV退避成功: %s", backup.csv_path)
        except Exception as backup_exc:
            logger.error("CSV退避にも失敗しました: %s", backup_exc)


def bootstrap_and_run(base_dir: str | Path = ".") -> None:
    import schedule

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_app_config(base_dir=base_dir)
    repo = PostgresRepository(config.db)
    backup = CsvBackupStore(config.backup_csv_path)

    logger.info("アプリ起動: base_dir=%s", Path(base_dir))
    repo.connect()
    logger.info("DB接続完了")

    try:
        replayed_count = backup.replay_to_repository(repo)
        logger.info("CSV再投入完了: %d件", replayed_count)
    except Exception as exc:
        logger.error("CSV再投入でエラー（継続します）: %s", exc)

    def scheduled_job() -> None:
        run_measurement_cycle(repo=repo, backup=backup, config=config)

    register_measurement_jobs(schedule_module=schedule, job_callable=scheduled_job)
    logger.info("スケジュール登録完了: 毎時 :00/:10/:20/:30/:40/:50")
    run_scheduler_loop(schedule_module=schedule)


def main() -> None:
    bootstrap_and_run()


if __name__ == "__main__":
    main()
