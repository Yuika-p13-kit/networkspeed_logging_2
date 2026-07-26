## Network Speed Monitoring System

このリポジトリは、速度計測の単一スクリプトを責務分離して運用互換を維持することを目的とします。

## 使用方法
## 前提条件

1. Python 3.8 以上がインストール済みであること
2. [`uv`](https://docs.astral.sh/uv/) がインストール済みであること
3. PostgreSQL がセットアップ済みであること
4. リポジトリルートに `database_info.txt` が存在すること（形式: `host=xxx\npassword=xxx\nuser=xxx\npassword=xxx`）

## セットアップ手順

```bash
# uv で Python 環境を初期化
uv sync

# PostgreSQL データベースとテーブルを初期化
uv run python scripts/init_db.py

# 既存の CSV バックアップがあれば復旧
uv run python scripts/restore_backup.py
```

## 実行方法

```bash
# スケジューラーを起動（バックグラウンド推奨）
uv run python main.py

# または cron/systemd で定期実行を設定
# 例: 毎時 :00/:10/:20/:30/:40/:50 に実行
```

## トラブルシューティング

- DB 接続エラー: `database_info.txt` の接続情報を確認
- 計測失敗: ネットワーク接続を確認（自動リトライは最大 5 回実行）
- CSV 退避ファイルが残っている: 手動で `uv run python scripts/restore_backup.py` を実行

## 開発環境整備

```bash
# テストを実行
uv run pytest tests/

# コード品質チェック
uv run black src/ && uv run flake8 src/
```

### 現在の実装準備状況
- 詳細要件: `docs/requirements.md`
- 設計仕様（関数レベル）: `docs/design-spec.md`
- テスト設計: `docs/test-design.md`
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
- 実行ツールは iMac では `brew install speedtest` で入る `speedtest` を利用し、Raspberry Pi でも同じ `speedtest` CLI を使う（導入方法は環境依存）

### 次の着手
1. 設定層（`database_info.txt` 互換読み込み）
2. PostgreSQL 永続化層
3. CSV バックアップ層
4. 計測層
5. スケジューラ層
6. `main.py` オーケストレーター化
7. 読み取り専用 API / ダッシュボード