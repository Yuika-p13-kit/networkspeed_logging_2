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

### 2.3 運用モード適用範囲（章の読み分け）
- 章 3〜11 は「移行期互換モード（`v1` / `dual_write` を含む）」の要件として扱う。
- 章 12 は「`v2_only` モードで提供するダッシュボード/API 要件」として扱う。
- 実装判断ルール:
  1) 運用モードが `v2_only` の場合は章 12 を正式要件として実装し、章 3/4 の v1 前提は互換維持範囲として扱う。
  2) 運用モードが `v1` または `dual_write` の場合は章 3〜11 を優先し、章 12 は矛盾しない範囲で適用する。
- 本件（issue #2）で追加・修正する表示/API 要件は `v2_only` を主軸とし、章 3〜11 は既存運用を壊さないための互換維持要件として解釈する。

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

## 12. ダッシュボード要件定義（初版）

### 12.1 目的
- 保存済み計測結果をブラウザで可視化し、運用者が回線状態と異常兆候を素早く把握できるようにする。
- 復旧性の担保（計測リトライ、CSV 退避・再投入）を優先し、表示/API はその上に読み取り専用で提供する。

### 12.2 対象ユーザー
- 日常運用担当者（計測結果の確認、障害一次切り分け）。
- 保守担当者（期間比較、復旧後の取り込み確認）。

### 12.3 ユースケース
- 直近の最新計測値を 1 画面で確認する。
- 任意期間の履歴を抽出し、回線低下や欠測を確認する。
- 簡易統計で期間内の傾向（平均・最大・最小）を把握する。
- 失敗・復旧関連ステータスを確認し、運用判断に使う。

### 12.4 機能要件
- 一覧表示: 新しい順で履歴を表示できること（timestamp, download, upload, device, status を表示）。
- 期間フィルタ: 開始日時・終了日時で絞り込みできること。
- 最新値表示: 直近 1 件の download/upload/timestamp/device/status を常時表示できること。
- 簡易統計: フィルタ結果に対して件数、平均、最大、最小を表示できること（download/upload）。
- エラーステータス表示: 計測失敗または DB 書き込み失敗・復旧処理中を識別できる表示を提供すること。

### 12.5 API 要件（読み取り専用）
- 前提: すべて GET のみ、更新系 API は提供しない。
- 想定エンドポイント:
  - `GET /api/dashboard/latest`
  - `GET /api/dashboard/history?from=...&to=...&limit=...`
  - `GET /api/dashboard/stats?from=...&to=...`
- 既存 API との関係:
  - 正式 API: `/api/dashboard/*` を正式運用経路とする。
  - 互換 API（deprecate 予定）: `GET /api/latest` と `GET /api/history` は互換維持のため残す。
  - 見直し時期: 互換 API は 2026-12-31 までに廃止可否を再判定し、以降の保持有無を issue で明文化する。
- レスポンス項目:
  - latest/history 共通: timestamp, download_speed_mbps, upload_speed_mbps, device, status
  - stats: count, avg_download_mbps, max_download_mbps, min_download_mbps, avg_upload_mbps, max_upload_mbps, min_upload_mbps
  - エラー表示補助: error_summary（存在する場合のみ）

### 12.5.1 `status` / `error_summary` の生成ルール（DB スキーマ変更なし）
- `status` の値集合は `success` / `measurement_failed` / `db_write_failed` / `recovery_pending` / `unknown` とする。
- `status` 判定優先順:
  1) 取得元に `status` 列があり値が入っている場合はその値を返す（v2 列優先）。
  2) 1) が使えない場合は暫定判定とし、download/upload が両方数値なら `success`、いずれか欠損なら `measurement_failed`。
  3) 退避 CSV が存在し未再投入データがある場合は `recovery_pending` を優先表示する（最新表示/API 応答時点の運用状態として扱う）。
  4) 上記で判定不能な場合は `unknown`。
- `error_summary` 判定:
  - 取得元にエラー要約情報（例: `error` 列）がある場合のみ返す。
  - エラー要約情報が無い場合、`/api/dashboard/*` では `null` を返すか項目を省略する。
  - 互換 API（`/api/latest` / `/api/history`）では `error_summary` を省略可とする。

### 12.6 非機能要件
- 可用性: 計測処理と独立して表示/API が参照可能であり、表示機能障害が計測停止要因にならないこと。
- 応答性能目標: 母集団 10,000 件の保存データで、同一条件の連続 30 リクエスト計測時に、最新値 API は 95 パーセンタイル 500ms 以内、履歴/統計 API は 95 パーセンタイル 2 秒以内（履歴は `limit=1000` 条件）。
- 運用性: 障害切り分けに必要なアクセスログ・アプリログを最小限出力すること。
- セキュリティ最低限: 外部公開しない前提でも入力パラメータ検証を行い、不正な期間・limit を拒否すること。

### 12.7 制約
- `v2_only` 前提で要件を定義し、v1 互換整理方針と矛盾しないこと。
- 実装順は「復旧フロー優先（計測/CSV/再投入の担保）」を維持し、表示/API は後段とすること。
- DB スキーマは変更しないこと（既存テーブル利用を前提に要件化）。
- 既存仕様（10 分間隔、最大 5 回リトライ、CSV 退避復旧）を壊さないこと。

### 12.8 受け入れ基準
- 入力条件: 期間指定なしで `GET /api/dashboard/latest` と `GET /api/dashboard/history` を実行した場合、期待結果: HTTP 200 で latest 1 件と既定件数内の履歴（新しい順）が返る。失敗時挙動: パラメータ不備以外で 5xx を返した場合は障害ログを出力し、計測ジョブ側の継続性を維持する。
- 入力条件: `from` / `to` / `limit` を指定して `GET /api/dashboard/history` と `GET /api/dashboard/stats` を実行した場合、期待結果: 履歴件数・統計値が同条件の DB 集計結果と一致する。失敗時挙動: `from > to` または上限超過 `limit` は HTTP 400 で拒否する。
- 入力条件: status 列ありデータと status 列なし相当データの双方を参照した場合、期待結果: status は 12.5.1 の優先順で判定される。失敗時挙動: 判定不能時は `unknown` を返す。
- 入力条件: error 要約情報が無いデータを参照した場合、期待結果: `error_summary` は `null` または省略になる。失敗時挙動: 項目欠如を理由に API 全体をエラー終了しない。
- 入力条件: 表示/API プロセス障害を発生させた場合、期待結果: 次回計測（10 分間隔）と失敗時 CSV 退避・再投入フローが継続する。
- 入力条件: 本要件対応後にマイグレーション差分を確認した場合、期待結果: DB スキーマ変更を伴う差分が存在しない。

### 12.9 未決事項
- UI 詳細（グラフ種類、配色、モバイル表示優先度）。
- 認証要否（ローカル限定運用のままか、将来認証導入するか）。
- 表示/API のデータ保存期間と最大取得件数ポリシー。
- status/error_summary の最終マッピング規則（既存データとの差分吸収方法）。
