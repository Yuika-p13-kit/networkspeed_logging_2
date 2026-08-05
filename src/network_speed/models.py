from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    database: str
    user: str
    password: str
    port: int = 5432


@dataclass(frozen=True)
class AppConfig:
    db: DatabaseConfig
    backup_csv_path: str = "network_speed_backup.csv"
    device: str = "Mac"
    history_limit_default: int = 100
    retry_max_attempts: int = 5
    web_host: str = "0.0.0.0"
    web_port: int = 8000
    schema_migration_mode: str = "v1_only"


@dataclass(frozen=True)
class MeasurementRecord:
    timestamp: datetime
    download_mbps: float
    upload_mbps: float
    device: str = "Mac"
