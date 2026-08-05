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
```

テーブル初期化は運用環境の SQL 適用手順に従って実施してください。
CSV バックアップの再投入はアプリ起動時に自動で実行されます。

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
- CSV 退避ファイルが残っている: `uv run python main.py` の起動時再投入ログを確認

v2_only 運用のバックフィル・切り戻し手順は `docs/v2-migration-runbook.md` を参照してください。
本番は `network_speed_logs_v2` への `v2_only` 運用へ移行済みです。
運用時の監視と 7 日判定は `python scripts/monitor_dual_write.py --mode v2_only ...` を利用してください。
v1互換導線（`v1_only`）は切り戻し専用として一時的に維持し、`v2_only` の 7日判定で `decision=go` を2サイクル連続で満たした日から14日以内に段階的撤去を開始します。

## 開発環境整備

```bash
# テストを実行
uv run pytest tests/

# コード品質チェック
uv run black src/ && uv run flake8 src/
```

### 現在の実装状況
- 詳細要件: `docs/requirements.md`
- 設計仕様（関数レベル）: `docs/design-spec.md`
- テスト設計: `docs/test-design.md`
- 稼働中: `network_speed_logs_v2` への 10 分間隔書き込み
- 維持中: 復旧フロー（計測リトライ / DB 障害時 CSV 退避・再投入）
- 次段: 読み取り専用 API / ダッシュボード

### 運用要件（抜粋）
- 保存先テーブル: `network_speed_logs_v2`
- 計測失敗時: 最大 5 回リトライ
- スケジュール: 毎時 `:00/:10/:20/:30/:40/:50`
- DB 書き込み失敗時: CSV 退避、起動時再投入後削除
- 単位変換: bps → Mbps（小数点 3 桁）
- `database_info.txt`: `key=value`（`host/database/user/password`）
- CSV 退避先: `network_speed_backup.csv`
- 旧実装計測ライブラリ: `speedtest`
- 実行ツールは iMac では `brew install speedtest` で入る `speedtest` を利用し、Raspberry Pi でも同じ `speedtest` CLI を使う（導入方法は環境依存）
