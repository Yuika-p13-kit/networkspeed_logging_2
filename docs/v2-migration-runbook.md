# v2 Migration Runbook

## 前提条件

- 実行ディレクトリはリポジトリルートとします。
- `NETWORK_SPEED_DB_*` 環境変数、または `database_info.txt`（ルート）、または `old_src/database_info.txt` で DB 接続情報を解決します。
- `network_speed_measurements`（v1）と `network_speed_logs_v2`（v2）が参照可能であること。

## Step 1: dual_write 検証

1. 1 件書き込みと v1/v2 反映を確認します（既定では検証データを削除します）。

```bash
python scripts/verify_dual_write.py
```

2. 検証データを残して目視確認したい場合:

```bash
python scripts/verify_dual_write.py --no-cleanup
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

1. dual_write を有効化した設定で systemd を反映します。

```bash
sudo systemctl daemon-reload
sudo systemctl restart network-speed.service
sudo systemctl status network-speed.service
```

2. 監視スクリプトで v1/v2 の件数差と最新時刻差を点検します。

```bash
python scripts/monitor_dual_write.py
python scripts/monitor_dual_write.py --max-count-gap 5 --max-lag-seconds 300
python scripts/monitor_dual_write.py --json
```

3. 1週間後の移行可否は、次のコマンド1回で判定できます（decision=go なら移行可）。

```bash
# dual_write 判定例
python scripts/monitor_dual_write.py --mode dual_write --observation-days 7 --interval-minutes 10 --min-sample-coverage 0.99 --max-count-gap 5 --max-lag-seconds 300 --json
```

4. 閾値超過時は次の順で対応します。

- `scripts/backfill_v1_to_v2.py` を再実行して差分を解消する。
- 差分が解消しない場合は `NETWORK_SPEED_SCHEMA_MIGRATION_MODE=v1_only` に切り戻し、原因調査後に再度 dual_write を有効化する。

## Step 4: カットオーバー

1. 監視結果が連続して閾値内であることを確認したうえで、systemd の設定を `v2_only` に切り替えます。

```bash
sudo systemctl daemon-reload
sudo systemctl restart network-speed.service
sudo systemctl status network-speed.service
```

2. 切り替え後は、読み取りと監視を継続し、v2 のみで更新されていることを確認します。

```bash
python scripts/monitor_dual_write.py --mode v2_only --max-lag-seconds 300
python scripts/monitor_dual_write.py --mode v2_only --json
```

3. 1週間後の移行可否は、次のコマンド1回で判定できます（decision=go なら移行可）。

```bash
# v2_only 判定例
python scripts/monitor_dual_write.py --mode v2_only --observation-days 7 --interval-minutes 10 --min-sample-coverage 0.99 --max-lag-seconds 900 --json
```

> **注意**: `v2_only` 移行後は v1 への書き込みが止まるため、`--mode v2_only` を明示して判定軸を切り替えてください。

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

1. 実行環境の設定を v1 のみに戻します。

```bash
export NETWORK_SPEED_SCHEMA_MIGRATION_MODE=v1_only
```

2. 監視プロセスを再起動し、書き込み先が v1 のみになったことを確認します。

## カットオーバー判定条件

- dual_write 検証で v1/v2 の両方に 1 件ずつ反映される。
- バックフィル dry-run の件数が想定どおりである。
- バックフィル本実行後、再度 dry-run が 0 件または許容範囲の差分である。
- 最新時刻比較で v1 と v2（success）の遅延が許容範囲内である。
- 切り戻し手順が検証済みである。
