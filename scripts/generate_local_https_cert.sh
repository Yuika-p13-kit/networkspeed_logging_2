#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
cert_dir="${NETWORK_SPEED_CERT_DIR:-${repo_root}/certs}"
tls_hostname="${NETWORK_SPEED_HOSTNAME:-network-speed-pi.local}"
hostname_pattern='^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$'
if (( ${#tls_hostname} > 253 )) || [[ ! "${tls_hostname}" =~ ${hostname_pattern} ]]; then
  echo "Invalid DNS hostname for certificate SAN: ${tls_hostname}" >&2
  exit 2
fi

mkdir -p "${cert_dir}"

cert_path="${cert_dir}/network-speed-local.crt"
key_path="${cert_dir}/network-speed-local.key"
force=0

if [[ "${1:-}" == "--force" ]]; then
  force=1
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--force]" >&2
  exit 2
fi

if [[ $force -eq 0 && ( -e "${cert_path}" || -e "${key_path}" ) ]]; then
  echo "Certificate or private key already exists; use --force to replace both: ${cert_dir}" >&2
  exit 0
fi

openssl req -x509 -newkey rsa:2048 -sha256 -days 365 \
  -nodes \
  -keyout "${key_path}" \
  -out "${cert_path}" \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,DNS:${tls_hostname},IP:127.0.0.1"

echo "Generated self-signed certificate: ${cert_path}"
echo "Private key: ${key_path}"
