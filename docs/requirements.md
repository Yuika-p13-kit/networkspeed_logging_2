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

## 12. ダッシュボード要件定義（確定版）

### 12.1 目的
- 保存済み計測結果をブラウザで可視化し、運用者が回線状態と異常兆候を素早く把握できるようにする。
- 復旧フロー（計測リトライ、CSV 退避・再投入）を最優先し、表示/API は読み取り専用として実装する。

### 12.2 対象ユーザー
- 日常運用担当者（計測結果の確認、障害一次切り分け）。
- 保守担当者（期間比較、復旧後の取り込み確認）。

### 12.3 ユースケース（優先順）
1. 直近の最新計測値を確認する（速やかな障害判別）。
2. 指定期間の履歴を取得して傾向を確認する（ダンプ／比較）。
3. 簡易統計（平均・最大・最小・件数）で期間傾向を把握する。
4. リカバリ状況（CSV 未投入データ）を可視化する。
5. 過去1時間や直近ウィンドウの移動平均を確認して短期的な変化を把握する（例: 1h平均、6点移動平均）。
6. 曜日別／時間帯別の傾向を確認して、平日/休日や日中/夜間の差を観察する（時間帯ヒートマップや集計表示）。
7. シーズン単位（季節・長期キャンペーン等）での比較・統計が必要な場合に備え、シーズン別集計を容易にするための設計を行う（将来的な拡張）。

### 12.4 機能要件（確定）
- 最新値表示: `/api/dashboard/latest` から表示。表示項目: timestamp (ISO8601 UTC), download_speed_mbps (numeric, 3dp), upload_speed_mbps, device, status, error_summary (optional)
- 履歴一覧: `/api/dashboard/history` で取得。並び: 新しい順。表示カラム: timestamp, download_speed_mbps, upload_speed_mbps, device, status
- 期間フィルタ: `from` / `to`（ISO8601 UTC）で絞り込み可能。`from` <= `to` を必須チェック。
- ページネーション: `limit` (default 100, max 1000) と `offset` をサポート。
- 簡易統計: `/api/dashboard/stats` が count, avg_download_mbps, max_download_mbps, min_download_mbps, avg_upload_mbps, max_upload_mbps, min_upload_mbps を返す。
- エラーステータス表示: `status` により色分けやアイコン表示を行う（運用側の説明参照）。

### 12.5 API 仕様（詳細）
共通ルール:
- 全て GET。認証は現段階では非対象（運用で限定公開することを推奨）。
- 時刻の扱い: DB は UTC で保存する。API 入力は UTC の ISO8601（例: 2026-08-09T00:00:00Z）。表示は UTC を基本とし、UI 側でローカル表示に変換可能。
- 上限・保護: `from`/`to` の期間は最大 30 日（ポリシーで変更可）。`limit` の最大は 1000（既定 100）。不正なパラメータは 400 を返す。

エンドポイント:
1) GET /api/dashboard/latest
- Query: none
- Response (200):
  {
    "timestamp": "2026-08-09T12:00:00Z",
    "download_speed_mbps": 120.123,
    "upload_speed_mbps": 20.456,
    "device": "Mac",
    "status": "success",
    "error_summary": null
  }
- Errors: 500 on server error (ログ出力)

2) GET /api/dashboard/history?from=...&to=...&limit=...&offset=...
- Query:
  - from (ISO8601, optional)
  - to (ISO8601, optional)
  - limit (int, optional, default=100, max=1000)
  - offset (int, optional, default=0)
- Response (200):
  {
    "total": 1234,
    "limit": 100,
    "offset": 0,
    "records": [ { /* same shape as latest */ } ]
  }

3) GET /api/dashboard/stats?from=...&to=...
- Query: from, to (required together)
- Response (200):
  {
    "count": 120,
    "avg_download_mbps": 95.123,
    "max_download_mbps": 200.000,
    "min_download_mbps": 10.000,
    "avg_upload_mbps": 15.456,
    "max_upload_mbps": 40.000,
    "min_upload_mbps": 1.234
  }

互換性:
- 既存 `/api/latest` と `/api/history` は引き続き維持する（当面はラッパー実装）。将来廃止予定は docs に記載。

### 12.5.1 status / error_summary（明確化）
- status 値集合: `success`, `measurement_failed`, `db_write_failed`, `recovery_pending`, `unknown`。
- 判定ロジック（優先順）:
  1) DB 側に `status` 列が存在し値が入っている場合はそれを返す（v2 優先）。
  2) 1 が無い場合は measurement 値で判定: download と upload が数値 → `success`、どちらか欠損 → `measurement_failed`。
  3) CSV 退避ファイルに未投入レコードがあり該当データが再投入されていない場合は `recovery_pending` を優先表示（API は運用状態として返す）。
  4) 判定不能なら `unknown`。
- error_summary: 文字列（短文、例: "DB timeout during insert"). 存在しない場合は null またはフィールド省略。

### 12.6 非機能要件（追記）
- 性能目標: 小規模運用（10k レコード程度）に対して最新値 API は 95p 500ms、履歴/統計は 95p 2s を目安とする。大規模対応はキャッシュ/集計テーブルで別タスク。
- ロギング: API は INFO レベルでリクエスト要約、ERROR で例外詳細（但し機密情報はログ出力しない）。
- セキュリティ: 出力は必ずエスケープ。公開前にアクセス制限を設けること。

### 12.7 制約（再掲）
- DB スキーマは変更しない。
- 復旧フロー優先。表示/API は読み取り専用で実装。

### 12.8 受け入れ基準（追記）
- ドキュメント: API スキーマ（例含む）が docs/requirements.md に記載され、Critic のレビューが完了していること。
- API: `/api/dashboard/latest` が既存 `/api/latest` と同等のデータを返すこと（互換テスト）。
- テスト: pytest で読み取りエンドポイントの単体テスト・統合テストが追加され、ローカルで成功すること。
- UI: シンプルな HTML ダッシュボードで最新値・履歴取得が動作すること（手動確認で可）。

### 12.9 未決事項（残す）
- グラフ種類、配色、モバイル優先度は別タスクで決定。
- 認証方針は運用チームで決定（ドキュメントに注意喚起を追加）。
- データ保持期間・大規模運用は別途検討。

※ 本セクションは実装着手前の最終仕様候補。実装中に小さな修正が出る可能性があるため、Critic による最終承認を必須とする。
