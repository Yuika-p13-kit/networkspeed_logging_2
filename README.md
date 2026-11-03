## Network Speed Monitoring System

このリポジトリは、速度計測の単一スクリプトを責務分離して運用互換を維持することを目的とします。

## 使用方法
## 前提条件

1. Python 3.11 以上がインストール済みであること
2. [`uv`](https://docs.astral.sh/uv/) がインストール済みであること
3. PostgreSQL がセットアップ済みであること
4. リポジトリルートに `database_info.txt` が存在すること（形式例: `host=xxx\ndbname=xxx\nuser=xxx\npassword=xxx`）

注意: 機密情報（パスワード等）はリポジトリにコミットしないでください。代替として環境変数を使用すること（例: PGHOST, PGDATABASE, PGUSER, PGPASSWORD）を推奨します。

## セットアップ手順

```bash
# uv で Python 環境を初期化
uv sync
```

テーブル初期化は運用環境の SQL 適用手順に従って実施してください。
CSV バックアップの再投入はアプリ起動時に自動で実行されます。

## 実行方法

```bash
# HTTP で起動
uv run python main.py

# HTTPS で起動（自己署名証明書を利用）
# 1) 証明書生成
bash scripts/generate_local_https_cert.sh

# 2) 環境変数を設定
export NETWORK_SPEED_SSL_CERT="$(pwd)/certs/network-speed-local.crt"
export NETWORK_SPEED_SSL_KEY="$(pwd)/certs/network-speed-local.key"
export NETWORK_SPEED_SSL_PORT="8443"

# 3) 起動
uv run python main.py
```

LAN 内の Raspberry Pi には `https://network-speed-pi.local:8443/` でアクセスします。初回設定後はIPアドレスを接続先に使いません。

### Raspberry Pi のLAN内ホスト名を設定

Pi のコンソールで一度だけ実行し、Avahi/mDNSで `network-speed-pi.local` を広告します。

```bash
sudo hostnamectl set-hostname network-speed-pi
sudo nano /etc/hosts
# `127.0.1.1 raspberrypi` のような旧名の行を `127.0.1.1 network-speed-pi` に変更
# localhost と IPv6 の行は残す
getent hosts "$(hostname)"
sudo -v
sudo apt-get update
sudo apt-get install -y avahi-daemon avahi-utils
sudo systemctl enable --now avahi-daemon
hostnamectl --static
systemctl is-active avahi-daemon
```

Mac と Pi が同じ通常のLANに接続されている状態で、Macから名前解決とSSHを確認します。

```bash
dns-sd -G v4 network-speed-pi.local
ssh threeb@network-speed-pi.local 'hostnamectl --static; systemctl is-active avahi-daemon'
```

`dns-sd` は結果が表示されたら `Control-C` で終了します。名前が解決しない場合はPi上で `avahi-resolve-host-name network-speed-pi.local` を確認し、MacとPiが同じLANにいること、ゲストWi-Fiや無線LANの端末分離が有効でないことを確認してください。別の端末が同名を使っていないかも確認します。mDNSがLANで遮断されている場合は、ルーターのローカルDNSに固定名を登録し、デプロイ時の `DEPLOY_HOST` と証明書生成時の `NETWORK_SPEED_HOSTNAME` に同じDNS名を指定します。

## デプロイ方法

デバイスへ変更を反映するには、リポジトリルートから次のスクリプトを実行します。

```bash
bash scripts/deploy_to_raspberrypi.sh
```

既定では `threeb@network-speed-pi.local:/home/threeb/network_speed` に同期し、`network-speed.service` を再起動します。ルーターDNSを使う場合は `--host` または `DEPLOY_HOST` でその名前を指定できます。`--user`、`--path`、`--service` も必要に応じて上書きできます。

通常デプロイでは `network-speed-health.service` と `network-speed-health.timer` も配置し、5分ごとの独立監視を有効にします。初回デプロイ時に ntfy のトピックがランダム生成され、デプロイ出力に表示されます。そのトピックを ntfy アプリで購読してください。トピックは `/etc/default/network-speed-health` に保存されます。
デプロイ用SSHユーザーは、systemd unit の配置、`/etc/default/network-speed-health` の作成と権限設定、systemd の再読み込み・有効化・再起動を `sudo -n` で実行できる必要があります。

### 計測停止通知（ntfy）

- 通知先は既定サーバー `https://ntfy.sh` です。トピックは初回デプロイ時に Pi 上で生成され、リポジトリには保存されません。
- トピック名を自分で選ぶ場合は、デプロイ後に Pi 上の `/etc/default/network-speed-health` を編集し、`NETWORK_SPEED_NTFY_TOPIC=<topic>` の値を変更してください。次回の監視実行から反映されます。
- トピック名は通知を受け取る ntfy アプリでも必要です。ntfy.sh はトピック名を知る人が購読・投稿できる公開サーバーのため、表示されたトピック名は秘密として扱ってください。
- 初期設定では、`network-speed.service` が active でない、DBから計測状態を読めない、または成功計測が30分以上ない場合に通知します。DBに記録が一度もない場合は、監視開始から30分後に通知します。
- 同一障害の発生時に1回通知し、未復旧なら前回通知から24時間ごとにリマインダーを送ります。障害発生通知は夜間も保留しません。障害開始後の成功計測を確認したら復旧通知を1回送ります。
- ntfy アクセストークンが必要な場合は、Pi 上で `/etc/default/network-speed-health` に `NETWORK_SPEED_NTFY_TOKEN=<token>` を追記してください。ファイルは mode 600 で保護されます。トークンをリポジトリやシェル履歴に保存しないでください。
- 閾値は `NETWORK_SPEED_MEASUREMENT_STALE_MINUTES`、リマインダー間隔は `NETWORK_SPEED_HEALTH_REMINDER_HOURS` で変更できます（systemd unit の Environment を編集して `sudo systemctl daemon-reload`）。

状態確認:

```bash
ssh threeb@network-speed-pi.local 'systemctl status network-speed-health.timer --no-pager'
ssh threeb@network-speed-pi.local 'sudo journalctl -u network-speed-health.service -n 30 --no-pager'
```

この監視は計測サービスとは別プロセスですが、同じ Raspberry Pi 上で実行されます。Pi の電源断やネットワーク断の最中は監視も通知もできないため、その状態も検知するには Pi 外の監視主体が別途必要です。

### Raspberry Pi への HTTPS 最小構成反映手順

以下は自己署名証明書を使うHTTPS設定手順です。証明書には `network-speed-pi.local` が含まれます。SANを更新するため、既存のローカル証明書を明示的に置き換える `--force` を指定します。

```bash
# 1) ローカルで証明書生成
bash scripts/generate_local_https_cert.sh --force

# 2) Pi 側に証明書配置ディレクトリを作成
ssh threeb@network-speed-pi.local 'mkdir -p /home/threeb/network_speed/certs'

# 3) 証明書と秘密鍵を転送
scp certs/network-speed-local.crt threeb@network-speed-pi.local:/home/threeb/network_speed/certs/
scp certs/network-speed-local.key threeb@network-speed-pi.local:/home/threeb/network_speed/certs/
ssh threeb@network-speed-pi.local 'openssl x509 -in /home/threeb/network_speed/certs/network-speed-local.crt -noout -ext subjectAltName'

# 4) コード反映（必要時）
bash scripts/deploy_to_raspberrypi.sh

# 5) service file を反映（必要時）
scp systemd/network-speed.service threeb@network-speed-pi.local:/tmp/network-speed.service
ssh threeb@network-speed-pi.local 'sudo cp /tmp/network-speed.service /etc/systemd/system/network-speed.service && sudo systemctl daemon-reload'

# 6) 再起動と確認
ssh threeb@network-speed-pi.local 'sudo systemctl restart network-speed.service'
ssh threeb@network-speed-pi.local 'sudo systemctl status network-speed.service --no-pager -l | sed -n "1,30p"'
ssh threeb@network-speed-pi.local 'sudo ss -lntp | grep -E ":8000|:8443" || true'

# 7) このMacユーザーのlogin Keychainに証明書をSSL用の信頼ルートとして登録
security add-trusted-cert -r trustRoot -p ssl -k "$HOME/Library/Keychains/login.keychain-db" certs/network-speed-local.crt

# 8) ホスト名検証ありでダッシュボード/APIを確認（Mac標準curlでは --cacert を付けない）
curl -4 --fail --show-error https://network-speed-pi.local:8443/
curl -4 --fail --show-error https://network-speed-pi.local:8443/api/dashboard/latest
```

ルーターDNSを使う場合は、証明書生成時に `NETWORK_SPEED_HOSTNAME=<ルーターDNS名>`、デプロイ時に `DEPLOY_HOST=<ルーターDNS名>` を指定してください。SSH/SCPとHTTPS確認の接続先も同じ名前にします。

補足:

- `network-speed.service` の SSL 環境変数（`NETWORK_SPEED_SSL_CERT` / `NETWORK_SPEED_SSL_KEY` / `NETWORK_SPEED_SSL_PORT`）が欠けると HTTP 起動に戻ります。
- 証明書未配置の状態で再起動すると 8443 で待ち受けません。

## トラブルシューティング

- DB 接続エラー: `database_info.txt` の接続情報を確認
- 計測失敗: ネットワーク接続を確認（自動リトライは最大 5 回実行）
- CSV 退避ファイルが残っている: `uv run python main.py` の起動時再投入ログを確認
- HTTPS ブロック: `https://network-speed-pi.local:8443/` を使用し、証明書SANに名前が含まれていることを確認
- macOS の `curl` が `self signed certificate` を返す: 証明書をlogin Keychainへ上記のとおり信頼登録します。`curl --version` に `SecureTransport` が表示されるMac標準curlでは、`--cacert` ではなくKeychainを使います。
- IPv6で8443へ接続できない: 現在のサービスはIPv4 (`0.0.0.0:8443`) で待ち受けます。確認には `curl -4` を使います。
- `sudo: ホスト network-speed-pi の名前解決ができません`: Pi の `/etc/hosts` で `127.0.1.1` が現在のホスト名 `network-speed-pi` を指すよう修正します（例: `127.0.1.1 network-speed-pi raspberrypi`）。
- 再起動直後に8443へ接続できない: `systemctl status network-speed.service` が `active (running)` になってからHTTPSを確認します。証明書名の不一致が出る場合はPi上の証明書SANを確認し、新しい証明書と鍵を転送してからサービスを再起動します。
- デプロイ先と項目別の同期差分を確認したい: `bash scripts/deploy_to_raspberrypi.sh --dry-run` を実行します。比較のためPiへSSH接続しますが、ファイル転送とサービス再起動は行いません。通常デプロイではPi上の `database_info.txt` と `network_speed_backup.csv` を同期削除の対象外にします。
- 8443 が開かない: Pi 側 `/home/threeb/network_speed/certs` の存在と証明書実ファイル、`/etc/systemd/system/network-speed.service` の SSL 環境変数を確認

## 運用確認

HTTPS、ダッシュボード/API、名前解決の運用確認と障害切り分けは [v2 migration runbook](docs/v2-migration-runbook.md#運用確認https-最小構成) を参照してください。証明書SANとホスト名の検証には `curl -k` を使わないでください。

v2_only 運用のバックフィル・切り戻し手順は `docs/v2-migration-runbook.md` を参照してください。
本番は `network_speed_logs_v2` への `v2_only` 運用へ移行済みです。
運用時の監視と 7 日判定は `python scripts/monitor_dual_write.py --mode v2_only ...` を利用してください。
v1互換導線（`v1_only`）は切り戻し専用として一時的に維持し、`v2_only` の 7日判定で `decision=go` を2サイクル連続で満たした日から14日以内に段階的撤去を開始します。

## 開発環境整備

```bash
# テストを実行
uv run pytest tests/

# CI と同じ依存関係でテストを実行
uv run pytest
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
- `database_info.txt`: `key=value`（例: host, dbname, user, password）。機密情報はコミットしないでください。環境変数（PGHOST, PGDATABASE, PGUSER, PGPASSWORD）の使用を推奨します。
- CSV 退避先: `network_speed_backup.csv`
- 旧実装計測ライブラリ: `speedtest`
- 実行ツールは iMac では `brew install speedtest` で入る `speedtest` を利用し、Raspberry Pi でも同じ `speedtest` CLI を使う（導入方法は環境依存）
