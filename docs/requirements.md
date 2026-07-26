# Network Speed Monitoring System 要件定義（詳細化）

## 1. 目的
- 既存の単一スクリプト運用を責務分離し、運用停止しにくい構成へ移行する。
- 10 分間隔計測・PostgreSQL 保存・読み取り専用ダッシュボード/API を提供する。
- 最優先は復旧性（計測リトライ、DB 障害時 CSV 退避と再投入）と既存互換維持。

## 2. スコープ
### 2.1 対象
- 計測、永続化、CSV バックアップ、スケジューラ、読み取り API/ダッシュボード。
- `main.py` はオーケストレーションのみ。

### 2.2 非対象
- DB スキーマ変更（明示依頼がない限り実施しない）。
- 書き込み系 API。
- 高度な認証・認可。

## 3. 互換要件（必須）
- テーブルは `network_speed_measurements` を利用。
  - `timestamp`
  - `download_speed_Mbps`
  - `upload_speed_Mbps`
  - `device`
- 速度は bps → Mbps 変換し、小数点 3 桁で丸めて保存。
- 計測失敗時は最大 5 回リトライ。
- スケジュールは毎時 `:00/:10/:20/:30/:40/:50`。
- DB 書き込み失敗時は CSV 退避。
- 起動時に CSV を再投入し、成功したら CSV を削除。
- `database_info.txt` の互換パスを維持。
- `device` 既定値は `Mac` を維持。
- CSV 退避ファイル名は `network_speed_backup.csv` を維持。
- 計測ライブラリは `speedtest`（speedtest-cli 系）を維持。
- 実行ツールは iMac では `brew install speedtest` で入る `speedtest` を使い、Raspberry Pi でも同じ `speedtest` CLI を使う（導入方法は環境ごとに異なる）。

## 4. 機能要件
### 4.1 設定層
- 単一の設定読み込み窓口を作る。
- 優先順位（暫定）:
  1) 環境変数
  2) `database_info.txt`
  3) コード既定値
- `database_info.txt` の存在時は DB 接続情報を解釈し、不足項目は環境変数/既定値で補完。
- `database_info.txt` は `key=value` 形式とし、最低限 `host` `database` `user` `password` を扱う。

### 4.2 永続化層（PostgreSQL）
- 書き込み: 1 件の計測結果を `network_speed_measurements` へ挿入。
- 読み取り: 
  - 最新 1 件
  - 履歴 N 件（既定 100 件）
- DB 例外は上位に通知し、CSV 退避判定に利用できること。

### 4.3 CSV バックアップ層
- 書き込み失敗時、計測結果 1 件を CSV へ追記。
- CSV はヘッダーなし追記形式とし、`timestamp,download_speed,upload_speed,device` の順で保存。
- アプリ起動時、CSV が存在すれば先頭から順に DB 再投入。
- 再投入完了時に CSV を削除。
- 再投入途中で失敗した場合は CSV を保持（削除しない）。

### 4.4 計測層
- speedtest 実行による download/upload bps の取得。
- 実装ライブラリは `speedtest` を使用する。
- 失敗時リトライ（最大 5 回、指数バックオフは任意）。
- 成功時に Mbps（3 桁丸め）へ変換し返却。

### 4.5 スケジューラ層
- 毎時 6 回固定（00,10,20,30,40,50 分）で計測ジョブを起動。
- 1 回の失敗でプロセス全体停止しない。

### 4.6 表示/API 層（読み取り専用）
- API:
  - `GET /api/latest` 最新 1 件
  - `GET /api/history?limit=100` 履歴
- ダッシュボード:
  - 最新値（download/upload/timestamp/device）
  - 履歴一覧（新しい順）
- すべて読み取り専用。

## 5. 非機能要件
- ログは INFO/ERROR を最低限出力し、障害原因を判別可能にする。
- メモリ上に未送信データを溜め込まず、退避は CSV を正とする。
- Python 3.11 以上で動作。

## 6. 障害復旧フロー（受け入れ基準）
1. 計測失敗時:
   - 1 回目失敗で停止しない。
   - 最大 5 回以内に成功すれば通常保存へ進む。
2. DB 書き込み失敗時:
   - 同計測データを CSV へ退避。
   - 監視ループは継続。
3. 起動時復旧:
   - CSV データを DB へ再投入。
   - 全件成功時のみ CSV 削除。

## 7. 実装準備（推奨構成）
- `src/network_speed/config.py` 設定読み込み
- `src/network_speed/repository.py` PostgreSQL read/write
- `src/network_speed/backup.py` CSV 退避/再投入
- `src/network_speed/measurement.py` speedtest + リトライ + Mbps 変換
- `src/network_speed/scheduler.py` 10 分スケジューリング
- `src/network_speed/web.py` API/ダッシュボード
- `main.py` 依存注入と起動順制御

## 8. 実装順（確定）
1. 設定層
2. 永続化層
3. CSV バックアップ層
4. 計測層
5. スケジューラ層
6. `main.py` オーケストレーター化
7. API/ダッシュボード
8. 運用確認

## 9. 未確定事項（実装前にユーザー確認が望ましい）
- ダッシュボード実装方式（サーバーサイド HTML か SPA か）。
- API/ダッシュボード実行ポート。

## 10. 未確定事項に対する暫定方針（確認が取れるまで）
- Web は最小依存で FastAPI + サーバーサイド HTML を採用。
- ポートは `8000`。

## 11. old_src 反映メモ
- `old_src/test.py` で `database_info.txt` が `key=value` 読み込みであることを確認。
- `old_src/test.py` で CSV 名が `network_speed_backup.csv` であることを確認。
- `old_src/SpeedTest_chatgpt.py` で `speedtest` 利用を確認。
