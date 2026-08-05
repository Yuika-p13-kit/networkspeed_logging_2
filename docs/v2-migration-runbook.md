# v2 Migration Runbook

## 前提条件

- 実行ディレクトリはリポジトリルートとします。
- `NETWORK_SPEED_DB_*` 環境変数、または `database_info.txt`（ルート）、または `old_src/database_info.txt` で DB 接続情報を解決します。
- `network_speed_logs_v2`（v2）での通常運用を前提とし、`network_speed_measurements`（v1）は切り戻し時のみ参照します。

## v1互換の保持方針（撤去期限つき）

- v1互換（`v1_only` と v1テーブル参照）を残す理由は、障害時に即時切り戻して計測停止を避けるためです。
- 撤去期限は「`v2_only` の 7日判定で `decision=go` を2サイクル連続で満たした日から14日以内」とします。
- 期限到達後は、別PRで v1/dual_write のコードと手順を段階的に削除します（テーブルDROPはこのrunbookの対象外）。

## Step 1: v2_only 運用前提の確認

1. `v2_only` 前提の 7 日判定を確認します。

```bash
python scripts/monitor_dual_write.py --mode v2_only --observation-days 7 --interval-minutes 10 --min-sample-coverage 0.99 --max-lag-seconds 900 --json
```

2. 短時間の監視確認を行う場合:

```bash
python scripts/monitor_dual_write.py --mode v2_only --max-lag-seconds 300
python scripts/monitor_dual_write.py --mode v2_only --json
```

## Step 2: バックフィル

1. まず dry-run で対象件数のみ確認します。

```bash
python scripts/backfill_v1_to_v2.py --dry-run
```

2. 期間を絞る場合（下限時刻指定）:

```bash
python scripts/backfill_v1_to_v2.py --dry-run --since "2026-07-01 00:00:00"
```

3. 本実行:

```bash
python scripts/backfill_v1_to_v2.py
```

4. 期間指定で本実行:

```bash
python scripts/backfill_v1_to_v2.py --since "2026-07-01 00:00:00"
```

## Step 3: 監視フェーズ

1. `v2_only` の設定で systemd を反映します。

```bash
sudo systemctl daemon-reload
sudo systemctl restart network-speed.service
sudo systemctl status network-speed.service
```

2. 監視スクリプトで `v2_only` の稼働状況と最新時刻差を点検します。

```bash
python scripts/monitor_dual_write.py --mode v2_only
python scripts/monitor_dual_write.py --mode v2_only --max-lag-seconds 300
python scripts/monitor_dual_write.py --mode v2_only --json
```

3. 1週間後の `v2_only` 継続判定は、次のコマンド1回で確認できます（decision=go なら継続可）。

```bash
# v2_only 判定例
python scripts/monitor_dual_write.py --mode v2_only --observation-days 7 --interval-minutes 10 --min-sample-coverage 0.99 --max-lag-seconds 900 --json
```

4. 閾値超過時は次の順で対応します。

- `scripts/backfill_v1_to_v2.py` を再実行して差分を解消する。
- 差分が解消しない場合は `NETWORK_SPEED_SCHEMA_MIGRATION_MODE=v1_only` に切り戻し、原因調査後に `v2_only` へ戻す。

## Step 4: カットオーバー

1. 監視結果が連続して閾値内であることを確認したうえで、systemd の設定が `v2_only` 前提であることを維持します。

```bash
sudo systemctl daemon-reload
sudo systemctl restart network-speed.service
sudo systemctl status network-speed.service
```

2. 運用中は、読み取りと監視を継続し、v2 のみで更新されていることを確認します。

```bash
python scripts/monitor_dual_write.py --mode v2_only --max-lag-seconds 300
python scripts/monitor_dual_write.py --mode v2_only --json
```

3. 1週間後の `v2_only` 継続判定は、次のコマンド1回で確認できます（decision=go なら継続可）。

```bash
# v2_only 判定例
python scripts/monitor_dual_write.py --mode v2_only --observation-days 7 --interval-minutes 10 --min-sample-coverage 0.99 --max-lag-seconds 900 --json
```

> **注意**: 通常運用は `v2_only` が前提です。`v1_only` は切り戻し時の例外手順としてのみ使ってください。

> **撤去目安**: `v2_only` の 7日判定が2サイクル連続で `decision=go` になったら、14日以内に v1互換導線の削除PRを起票してください。

4. 問題が出た場合は、Step 3 の切り戻し手順で `v1_only` に戻します。

## 整合性確認 SQL

```sql
-- v1 件数
SELECT count(*) AS v1_count
FROM network_speed_measurements;

-- v2 成功データ件数
SELECT count(*) AS v2_success_count
FROM network_speed_logs_v2
WHERE status = 'success';

-- 最新時刻比較
SELECT
  (SELECT max(timestamp) FROM network_speed_measurements) AS v1_latest,
  (SELECT max(measured_at) FROM network_speed_logs_v2 WHERE status = 'success') AS v2_latest;
```

## 切り戻し手順

1. 実行環境の設定を `v1_only` に戻します。

```bash
export NETWORK_SPEED_SCHEMA_MIGRATION_MODE=v1_only
```

2. 監視プロセスを再起動し、書き込み先が v1 のみになったことを確認します。

## カットオーバー判定条件

- `v2_only` 判定で継続可となる。
- バックフィル dry-run の件数が想定どおりである。
- バックフィル本実行後、再度 dry-run が 0 件または許容範囲の差分である。
- 最新時刻比較で v2 の遅延が許容範囲内である。
- 切り戻し手順で `v1_only` に戻せることが確認済みである。
