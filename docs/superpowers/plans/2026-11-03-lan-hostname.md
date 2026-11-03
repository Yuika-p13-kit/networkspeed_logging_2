# LAN Host Name Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Raspberry Pi SSH, HTTPS, and deployment use a stable LAN name even when its DHCP address changes.

**Architecture:** Advertise `network-speed-pi.local` from the Pi through Avahi/mDNS. Use that name as the deployment default and in local HTTPS certificate SANs and operator documentation. If mDNS cannot cross the home LAN, document router local DNS as the fallback.

**Tech Stack:** Raspberry Pi OS/Linux (`hostnamectl`, Avahi), macOS Bonjour tools, Bash/SSH/rsync, OpenSSL, Markdown.

**Spec:** `docs/superpowers/specs/2026-11-03-lan-hostname-design.md`

## Global Constraints

- Access is limited to the home LAN; remote access is out of scope.
- Normal connection paths must not depend on a hard-coded IP.
- Preserve unrelated working-tree changes.
- Verify DNS name resolution, SSH, HTTPS dashboard/API, and deployment after the Pi address changes.

## Review Focus

- Avahi absent or disabled on the Pi: verify the chosen name is advertised after service setup.
- Multicast blocked or isolated by Wi-Fi/AP settings: document evidence and router-DNS fallback.
- A duplicate `.local` host name: detect it and choose a unique hostname before relying on it.
- Certificate still contains only an IP SAN: verify the DNS name is present and HTTPS accepts that name.
- Old IP literals remain in active procedures: search README, runbook, deploy script, and certificate generator for stale defaults.

---

### Task 1: Configure and verify the Pi's mDNS name

**Files:**
- Modify: `README.md` (Pi setup and Mac-side diagnosis)
- Modify: `docs/v2-migration-runbook.md` (deployment verification and router-DNS fallback)

**Interfaces:**
- Produces: Pi hostname `network-speed-pi`, advertised as `network-speed-pi.local`.

- [ ] **Step 1: Inspect the Pi over SSH before changing it**

Run from the Mac on the home LAN: `ssh threeb@192.168.1.30 'hostnamectl --static; systemctl is-enabled avahi-daemon; systemctl is-active avahi-daemon; command -v avahi-daemon'`.
Expected: capture current hostname and whether Avahi is present/enabled; do not assume the Pi is reachable from the Codex sandbox.

- [ ] **Step 2: Configure the Pi if needed**

Set hostname to `network-speed-pi`; install `avahi-daemon` using the Pi's OS package manager if absent; enable and start the daemon. Preserve any existing SSH user and project path.

- [ ] **Step 3: Verify from macOS**

Run `dns-sd -G v4 network-speed-pi.local` and `ssh threeb@network-speed-pi.local 'hostname -f; systemctl is-active avahi-daemon'`.
Expected: the name resolves to the Pi's current LAN address and SSH reports the selected hostname with Avahi active.

- [ ] **Step 4: Document setup and mDNS failure diagnosis**

Document Pi commands, Mac checks, duplicate-name checks, and the condition for switching to router local DNS. Do not claim mDNS works until these checks succeed.

### Task 2: Use the stable name for deployment and HTTPS

**Files:**
- Modify: `scripts/deploy_to_raspberrypi.sh`
- Modify: `scripts/generate_local_https_cert.sh`
- Modify: `README.md`
- Modify: `docs/v2-migration-runbook.md`
- Test: `tests/test_hostname_configuration.py`

**Interfaces:**
- Consumes: Pi hostname `network-speed-pi.local` from Task 1.
- Produces: default deployment target `threeb@network-speed-pi.local`; local certificate SAN includes `DNS:network-speed-pi.local` and loopback names/IPs.

- [ ] **Step 1: Update deployment target defaults**

Change `DEPLOY_HOST` default and help text to `network-speed-pi.local`; retain `--host` and `DEPLOY_HOST` overrides for router DNS or alternate setups. `--dry-run` may use rsync's SSH transport to compare remote files, must itemize proposed changes, and must exit before the separate SSH command that restarts the service.

- [ ] **Step 2: Update certificate SAN and safe regeneration**

Replace the fixed Pi IP SAN with `DNS:network-speed-pi.local`, retaining `DNS:localhost` and `IP:127.0.0.1`. Add `NETWORK_SPEED_HOSTNAME` for router-DNS fallback, validate it as a DNS host name, `NETWORK_SPEED_CERT_DIR` for isolated verification, and `--force` for intentional certificate/key replacement; without `--force`, preserve existing files. Keep generated private keys out of Git.

- [ ] **Step 3: Update documented SSH/SCP/HTTPS commands**

Replace active Pi IP literals in README and runbook with the chosen name. State that the certificate must be regenerated and copied to the Pi before HTTPS host-name verification; preserve explicit local `127.0.0.1` checks where they run on the Pi itself.

- [ ] **Step 4: Check for stale active references**

Run `rg -n '192\.168\.1\.(27|30)|raspberrypi\.local' README.md docs/v2-migration-runbook.md scripts`.
Expected: no old address/name remains as the normal deployment or access path; historical notes may remain only when labeled as historical.

- [ ] **Step 5: Run the focused configuration tests**

Run: `.venv/bin/pytest -q tests/test_hostname_configuration.py`
Expected: deployment defaults to the stable hostname; `--dry-run` skips the service restart command; generated certificate includes the DNS SAN and loopback SANs; existing certificate is preserved unless `--force` is supplied.

### Task 3: Verify after a DHCP address change

**Files:**
- Modify: `README.md` (acceptance/evidence record)
- Modify: `docs/v2-migration-runbook.md` (final operational checks)

**Interfaces:**
- Consumes: `network-speed-pi.local`, the deployed service, and a certificate containing that DNS SAN.

- [ ] **Step 1: Verify hostname-based HTTPS**

Run `curl --cacert certs/network-speed-local.crt --fail --show-error https://network-speed-pi.local:8443/` and `curl --cacert certs/network-speed-local.crt --fail --show-error https://network-speed-pi.local:8443/api/dashboard/latest` from the Mac.
Expected: successful TLS hostname validation, dashboard response, and JSON API response.

- [ ] **Step 2: Verify deployment path**

Run `bash scripts/deploy_to_raspberrypi.sh --dry-run`, review the printed destination, then run the deployment after confirming certificate and service prerequisites.
Expected: rsync/SSH target is `threeb@network-speed-pi.local`, and the service remains active after deployment.

- [ ] **Step 3: Verify persistence across address change**

After a DHCP lease change or Pi reconnect, repeat DNS resolution, SSH, HTTPS, and API checks.
Expected: all checks pass using the name, independent of the Pi's numeric address.

- [ ] **Step 4: Record evidence and fallback outcome**

Record the date and observed hostname-based results. If mDNS fails due to the LAN, configure a router local-DNS name and substitute it in deploy/certificate/docs before marking the issue complete.
