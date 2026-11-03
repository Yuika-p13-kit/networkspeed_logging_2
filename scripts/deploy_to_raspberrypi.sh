#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

remote_user="${DEPLOY_USER:-threeb}"
remote_host="${DEPLOY_HOST:-network-speed-pi.local}"
remote_path="${DEPLOY_PATH:-/home/threeb/network_speed}"
service_name="${DEPLOY_SERVICE:-network-speed.service}"
ssh_target="${remote_user}@${remote_host}"

usage() {
  cat <<'EOF'
Usage: scripts/deploy_to_raspberrypi.sh [--host HOST] [--user USER] [--path PATH] [--service NAME] [--dry-run]

Environment variables:
  DEPLOY_HOST       Remote host name (default: network-speed-pi.local)
  DEPLOY_USER       SSH user (default: threeb)
  DEPLOY_PATH       Remote project path (default: /home/threeb/network_speed)
  DEPLOY_SERVICE    systemd service name (default: network-speed.service)
EOF
}

dry_run=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      remote_host="$2"
      ssh_target="${remote_user}@${remote_host}"
      shift 2
      ;;
    --user)
      remote_user="$2"
      ssh_target="${remote_user}@${remote_host}"
      shift 2
      ;;
    --path)
      remote_path="$2"
      shift 2
      ;;
    --service)
      service_name="$2"
      shift 2
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

rsync_args=(
  -az
  --delete
  --exclude '.git/'
  --exclude '.venv/'
  --exclude 'database_info.txt'
  --exclude 'network_speed_backup.csv'
  --exclude '__pycache__/'
  --exclude '.pytest_cache/'
  --exclude '.mypy_cache/'
  --exclude '.ruff_cache/'
)

if [[ $dry_run -eq 1 ]]; then
  rsync_args+=(--dry-run --itemize-changes)
fi

echo "Deploying ${repo_root} -> ${ssh_target}:${remote_path}"
rsync "${rsync_args[@]}" "${repo_root}/" "${ssh_target}:${remote_path}/"

if [[ $dry_run -eq 1 ]]; then
  echo "Dry-run complete; skipped service restart."
  exit 0
fi

ssh "${ssh_target}" "set -euo pipefail
cd '${remote_path}'
sudo -n systemctl restart '${service_name}'
sudo -n systemctl status '${service_name}' --no-pager -l
"
