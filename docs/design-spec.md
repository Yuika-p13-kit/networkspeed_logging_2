# Network Speed Monitoring System 設計仕様書（関数レベル）

## 1. 目的
本書は、`docs/requirements.md` の要件を実装へ落とし込むための関数レベル設計を定義する。

## 2. 対象範囲
- 設定層: `src/network_speed/config.py`
- 永続化層: `src/network_speed/repository.py`
- CSV バックアップ層: `src/network_speed/backup.py`
- 計測層: `src/network_speed/measurement.py`
- スケジューラ層: `src/network_speed/scheduler.py`
- Web/API 層: `src/network_speed/web.py`
- オーケストレーター: `main.py`

## 3. 共通データモデル

### 3.1 測定結果（ドメイン）
- 名称: `MeasurementRecord`
- フィールド:
  - `timestamp: datetime`
  - `download_mbps: float`
  - `upload_mbps: float`
  - `device: str`（既定値 `Mac`）

### 3.2 DB 接続情報
- 名称: `DatabaseConfig`
- フィールド:
  - `host: str`
  - `database: str`
  - `user: str`
  - `password: str`
  - `port: int = 5432`

### 3.3 アプリ設定
- 名称: `AppConfig`
- フィールド（最小）:
  - `db: DatabaseConfig`
  - `backup_csv_path: str = "network_speed_backup.csv"`
  - `device: str = "Mac"`
  - `history_limit_default: int = 100`
  - `retry_max_attempts: int = 5`
  - `web_host: str = "0.0.0.0"`
  - `web_port: int = 8000`

## 4. 設定層設計（config.py）

### 4.1 関数一覧
1. `parse_database_info_file(file_path: str) -> dict[str, str]`
   - 役割: `database_info.txt`（`key=value`）を読み取り辞書化
   - 入力: ファイルパス
   - 出力: キー文字列辞書
   - 例外: 不正行は `ValueError`、ファイルなしは `FileNotFoundError`

2. `build_database_config(env: Mapping[str, str], file_values: Mapping[str, str]) -> DatabaseConfig`
   - 役割: 環境変数優先で DB 設定を構築
   - 優先順位: 環境変数 > `database_info.txt` > 既定値
   - 例外: 必須項目欠損は `ValueError`

3. `load_app_config(base_dir: Path | str = ".") -> AppConfig`
   - 役割: 全設定の集約ロード
   - 入力: 実行基準ディレクトリ
   - 出力: `AppConfig`

### 4.2 環境変数マップ
- `NETWORK_SPEED_DB_HOST`
- `NETWORK_SPEED_DB_NAME`
- `NETWORK_SPEED_DB_USER`
- `NETWORK_SPEED_DB_PASSWORD`
- `NETWORK_SPEED_DB_PORT`
- `NETWORK_SPEED_DEVICE`
- `NETWORK_SPEED_BACKUP_CSV`
- `NETWORK_SPEED_WEB_HOST`
- `NETWORK_SPEED_WEB_PORT`

## 5. 永続化層設計（repository.py）

### 5.1 クラス
`PostgresRepository`
- コンストラクタ:
  - `__init__(self, config: DatabaseConfig)`

### 5.2 関数一覧
1. `connect(self) -> None`
   - 役割: DB 接続確立
   - 例外: 接続失敗時は元例外を再送出

2. `close(self) -> None`
   - 役割: DB 接続切断（冪等）

3. `insert_measurement(self, record: MeasurementRecord) -> None`
   - 役割: `network_speed_measurements` へ 1 件挿入
   - SQL: パラメータバインド必須（SQL インジェクション防止）

4. `fetch_latest(self) -> MeasurementRecord | None`
   - 役割: 最新 1 件取得

5. `fetch_history(self, limit: int) -> list[MeasurementRecord]`
   - 役割: 新しい順に `limit` 件取得

### 5.3 テーブル互換
- 対象テーブル: `network_speed_measurements`
- 利用カラム:
  - `timestamp`
  - `download_speed_Mbps`
  - `upload_speed_Mbps`
  - `device`

## 6. CSV バックアップ層設計（backup.py）

### 6.1 クラス
`CsvBackupStore`
- コンストラクタ:
  - `__init__(self, csv_path: Path | str)`

### 6.2 関数一覧
1. `append(self, record: MeasurementRecord) -> None`
   - 役割: CSV へヘッダーなし追記
   - 保存順: `timestamp,download_speed,upload_speed,device`

2. `load_all(self) -> list[MeasurementRecord]`
   - 役割: CSV 全件を読み込み

3. `delete_file(self) -> None`
   - 役割: CSV ファイル削除（存在しない場合は無視）

4. `replay_to_repository(self, repository: PostgresRepository) -> int`
   - 役割: CSV 全件を DB 再投入
   - 戻り値: 成功件数
   - 失敗時仕様: 途中で例外なら CSV は削除しない

## 7. 計測層設計（measurement.py）

### 7.1 関数一覧
1. `run_speedtest_once() -> tuple[float, float]`
   - 役割: speedtest 実行で bps を返す
   - 戻り値: `(download_bps, upload_bps)`

2. `bps_to_mbps_rounded(value_bps: float) -> float`
   - 役割: bps → Mbps 変換し小数点 3 桁へ丸め
   - 定義: `round(value_bps / 1_000_000, 3)`

3. `measure_with_retry(max_attempts: int = 5, sleep_seconds: float = 0.0) -> MeasurementRecord`
   - 役割: 最大 5 回リトライで測定
   - 成功: `MeasurementRecord` を返却
   - 失敗: `MeasurementFailedError` を送出

### 7.2 例外
- `MeasurementFailedError(Exception)`
  - 全リトライ失敗時に利用

## 8. スケジューラ層設計（scheduler.py）

### 8.1 定数
- `SCHEDULE_MINUTES = [":00", ":10", ":20", ":30", ":40", ":50"]`

### 8.2 関数一覧
1. `register_measurement_jobs(schedule_module, job_callable) -> None`
   - 役割: 毎時 6 回のジョブ登録

2. `run_scheduler_loop(schedule_module, interval_seconds: float = 1.0) -> None`
   - 役割: `run_pending()` を繰り返し実行
   - 例外方針: ジョブ例外で全体停止しないよう上位で処理

## 9. Web/API 層設計（web.py）

### 9.1 ファクトリ
1. `create_app(repository: PostgresRepository, default_limit: int = 100)`
   - 役割: Web アプリ生成

### 9.2 エンドポイント
1. `GET /api/latest`
   - 返却: 最新 1 件（なければ `null` または 204）

2. `GET /api/history?limit=100`
   - 返却: 履歴配列（新しい順）

3. `GET /`
   - 返却: ダッシュボード HTML（最新 + 履歴）

## 10. オーケストレーター設計（main.py）

### 10.1 関数一覧
1. `run_measurement_cycle(repo: PostgresRepository, backup: CsvBackupStore, config: AppConfig) -> None`
   - 処理:
     1) `measure_with_retry`
     2) DB insert
     3) 失敗時 CSV append

2. `bootstrap_and_run() -> None`
   - 処理:
     1) 設定ロード
     2) DB 接続
     3) CSV 再投入（起動時）
     4) スケジュール登録
     5) ループ開始

## 11. 主要シーケンス

### 11.1 通常測定
1. スケジューラが `run_measurement_cycle` を呼ぶ
2. 計測層が速度取得（最大5回）
3. 永続化層が DB 保存
4. 成功ログ出力

### 11.2 DB 障害時
1. 計測成功
2. DB 保存失敗
3. バックアップ層が CSV 追記
4. 監視ループ継続

### 11.3 起動時復旧
1. `bootstrap_and_run` 開始
2. CSV 存在確認
3. 全件再投入
4. 全件成功時のみ CSV 削除

## 12. エラーハンドリング方針
- 設定不備（起動不能）: 起動時に明示エラーで停止
- 計測失敗（運用継続）: 当該サイクルのみ失敗扱い
- DB 保存失敗（運用継続）: CSV 退避へフォールバック
- 再投入失敗（運用継続）: CSV 保持で次回へ持越し

## 13. ログ方針
- INFO: 起動、測定成功、DB 保存成功、CSV 再投入成功件数
- WARNING: 一時的な再試行
- ERROR: 計測全失敗、DB 保存失敗、CSV 再投入失敗

## 14. 依存ライブラリ（予定）
- `psycopg2-binary`
- `schedule`
- `speedtest-cli`
- `fastapi`
- `jinja2`
- `uvicorn`

## 15. トレーサビリティ
- 要件 `retry <= 5` → `measure_with_retry`
- 要件 `10分間隔` → `register_measurement_jobs`
- 要件 `DB失敗時CSV` → `run_measurement_cycle` + `CsvBackupStore.append`
- 要件 `起動時再投入` → `bootstrap_and_run` + `CsvBackupStore.replay_to_repository`
