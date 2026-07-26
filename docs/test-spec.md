# Network Speed Monitoring System テスト仕様書（pytest 実装向け）

## 1. 目的
- `docs/test-design.md` のテスト設計を、pytest でそのまま実装可能な粒度に具体化する。

## 2. スコープ
- 本フェーズ実装対象: `config.py` / `backup.py` / `measurement.py`
- 未実装層（repository / scheduler / web / orchestrator）はテストケース ID の定義のみ維持。

## 3. 実行条件
- コマンド: `pytest -q`
- Python: 3.11+
- テストは外部ネットワーク・実 DB に依存しない（モック/フェイクを使用）。

## 4. TC-ID と pytest マッピング

### 4.1 設定層
- TC-CFG-001 → `tests/test_config.py::test_parse_database_info_file_valid`
- TC-CFG-002 → `tests/test_config.py::test_load_app_config_without_file_uses_env`
- TC-CFG-003 → `tests/test_config.py::test_build_database_config_raises_when_required_missing`

### 4.2 CSV バックアップ層
- TC-BK-001 → `tests/test_backup.py::test_append_and_load_roundtrip`
- TC-BK-002 → `tests/test_backup.py::test_replay_to_repository_success_deletes_file`
- TC-BK-003 → `tests/test_backup.py::test_replay_to_repository_failure_keeps_file`

### 4.3 計測層
- TC-MEAS-001 → `tests/test_measurement.py::test_bps_to_mbps_rounded`
- TC-MEAS-002 → `tests/test_measurement.py::test_measure_with_retry_succeeds_after_retry`
- TC-MEAS-003 → `tests/test_measurement.py::test_measure_with_retry_raises_after_max_attempts`

## 5. モック方針
- 計測層: `runner` / `sleeper` / `time_provider` を依存注入してテスト。
- バックアップ層: `insert_measurement` を持つフェイクリポジトリを利用。
- 設定層: `tmp_path` と `monkeypatch` でファイル/環境変数を制御。

## 6. 合否判定
- すべての上記テストが成功で合格。
- 失敗時は TC-ID 単位で原因を切り分け、設計仕様書との不一致を優先確認。
