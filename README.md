## Network Speed Monitoring System

このリポジトリは、速度計測の単一スクリプトを責務分離して運用互換を維持することを目的とします。

### 現在の実装準備状況
- 詳細要件: `docs/requirements.md`
- 最優先: 復旧フロー（計測リトライ / DB 障害時 CSV 退避・再投入）
- 次段: 読み取り専用 API / ダッシュボード

### 互換要件（抜粋）
- テーブル: `network_speed_measurements`（既存流用）
- 計測失敗時: 最大 5 回リトライ
- スケジュール: 毎時 `:00/:10/:20/:30/:40/:50`
- DB 書き込み失敗時: CSV 退避、起動時再投入後削除
- 単位変換: bps → Mbps（小数点 3 桁）
- `database_info.txt`: `key=value`（`host/database/user/password`）
- CSV 退避先: `network_speed_backup.csv`
- 旧実装計測ライブラリ: `speedtest`

### 次の着手
1. 設定層（`database_info.txt` 互換読み込み）
2. PostgreSQL 永続化層
3. CSV バックアップ層
4. 計測層
5. スケジューラ層
6. `main.py` オーケストレーター化
7. 読み取り専用 API / ダッシュボード
