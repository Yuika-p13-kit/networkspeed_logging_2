from pathlib import Path

import pytest

from network_speed.config import (
    build_database_config,
    load_app_config,
    parse_database_info_file,
)


def test_parse_database_info_file_valid(tmp_path: Path) -> None:
    file_path = tmp_path / "database_info.txt"
    file_path.write_text(
        "host=localhost\n"
        "database=network\n"
        "user=test_user\n"
        "password=test_pass\n",
        encoding="utf-8",
    )

    values = parse_database_info_file(str(file_path))

    assert values["host"] == "localhost"
    assert values["database"] == "network"
    assert values["user"] == "test_user"
    assert values["password"] == "test_pass"


def test_parse_database_info_file_invalid_line(tmp_path: Path) -> None:
    file_path = tmp_path / "database_info.txt"
    file_path.write_text("invalid_line\n", encoding="utf-8")

    with pytest.raises(ValueError):
        parse_database_info_file(str(file_path))


def test_build_database_config_prefers_environment() -> None:
    env = {
        "NETWORK_SPEED_DB_HOST": "env-host",
        "NETWORK_SPEED_DB_NAME": "env-db",
        "NETWORK_SPEED_DB_USER": "env-user",
        "NETWORK_SPEED_DB_PASSWORD": "env-pass",
        "NETWORK_SPEED_DB_PORT": "15432",
    }
    file_values = {
        "host": "file-host",
        "database": "file-db",
        "user": "file-user",
        "password": "file-pass",
        "port": "5432",
    }

    config = build_database_config(env=env, file_values=file_values)

    assert config.host == "env-host"
    assert config.database == "env-db"
    assert config.user == "env-user"
    assert config.password == "env-pass"
    assert config.port == 15432


def test_build_database_config_raises_when_required_missing() -> None:
    with pytest.raises(ValueError):
        build_database_config(env={}, file_values={})


def test_load_app_config_without_file_uses_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETWORK_SPEED_DB_HOST", "localhost")
    monkeypatch.setenv("NETWORK_SPEED_DB_NAME", "netdb")
    monkeypatch.setenv("NETWORK_SPEED_DB_USER", "tester")
    monkeypatch.setenv("NETWORK_SPEED_DB_PASSWORD", "secret")
    monkeypatch.setenv("NETWORK_SPEED_RETRY_MAX_ATTEMPTS", "5")

    app_config = load_app_config(base_dir=tmp_path)

    assert app_config.db.host == "localhost"
    assert app_config.db.database == "netdb"
    assert app_config.device == "Mac"
    assert app_config.retry_max_attempts == 5
