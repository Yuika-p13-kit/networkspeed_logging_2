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

## 運用確認（HTTPS 最小構成）

Pi の初回ホスト名/mDNS設定は README の「Raspberry Pi のLAN内ホスト名を設定」を参照してください。ここでは、設定済みの名前 `network-speed-pi.local` からサービスを運用確認します。

1. Mac から同じLAN上で名前解決とSSHを確認します。

```bash
dns-sd -G v4 network-speed-pi.local
ssh threeb@network-speed-pi.local 'hostnamectl --static; systemctl is-active avahi-daemon'
```

`dns-sd` は名前とIPv4アドレスが表示されたら `Control-C` で終了します。解決しない場合は同一LAN接続、ゲストWi-Fi/端末分離、重複ホスト名、Pi上の `avahi-daemon` の順に確認します。LANがmDNSマルチキャストを遮断する場合は、ルーターのローカルDNSへ一意の名前を登録し、証明書生成で `NETWORK_SPEED_HOSTNAME=<DNS名>`、デプロイで `DEPLOY_HOST=<DNS名>` を指定します。SSH/SCP/HTTPSの接続先も同じ名前にします。

2. service の SSL 環境変数を確認します。

```bash
sudo systemctl show -p Environment network-speed.service
```

期待値の例:

- `NETWORK_SPEED_SSL_CERT=/home/threeb/network_speed/certs/network-speed-local.crt`
- `NETWORK_SPEED_SSL_KEY=/home/threeb/network_speed/certs/network-speed-local.key`
- `NETWORK_SPEED_SSL_PORT=8443`

3. Pi 自身で8443の待ち受けと応答を確認します。

```bash
sudo ss -lntp | grep -E ":8000|:8443" || true
curl -k -sS -D - https://127.0.0.1:8443/ -o /dev/null | sed -n "1,15p"
curl -k -sS -D - https://127.0.0.1:8443/api/dashboard/latest | sed -n "1,20p"
```

4. Mac のlogin Keychainに自己署名証明書をSSL用の信頼ルートとして登録し、選定したホスト名でHTTPSとAPIを確認します。Mac標準curlはSecureTransportを使うため、`--cacert` ではなくKeychainで信頼させます。IPv6はサービスが待ち受けないため、検証では `-4` を指定します。`curl -k` は証明書とホスト名の検証を無効化するため、この確認には使いません。

```bash
security add-trusted-cert -r trustRoot -p ssl -k "$HOME/Library/Keychains/login.keychain-db" certs/network-speed-local.crt
curl -4 --fail --show-error https://network-speed-pi.local:8443/
curl -4 --fail --show-error https://network-speed-pi.local:8443/api/dashboard/latest
```

5. 判定基準:

- 起動ログが `Web サーバー起動: https://0.0.0.0:8443`
- `https://127.0.0.1:8443/` が `HTTP/1.1 200 OK`
- `/api/dashboard/latest` が 200 + JSON

6. 失敗時の確認順:

- `/home/threeb/network_speed/certs` の存在と証明書ファイル配置
- `systemd` unit の SSL 環境変数
- `sudo systemctl daemon-reload && sudo systemctl restart network-speed.service`

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
- HTTPS 運用時は `8443` の LISTEN と `curl -k` での 200 応答が確認済みである。
