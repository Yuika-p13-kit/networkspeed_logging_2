# ntfy Health Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Notify a user through ntfy when Raspberry Pi measurements stop succeeding, send one reminder per 24 hours while the incident remains, and send one recovery notification.

**Architecture:** A separate systemd timer invokes a health-check script every five minutes, so monitoring continues when the web/measurement process exits. The script checks the v2 database's latest successful measurement, evaluates persisted incident state, and publishes through ntfy.sh; a local timer cannot report a Pi power/network outage while the Pi itself is offline.

**Tech Stack:** Python 3.11 standard library HTTP client, existing psycopg2 database driver and config parser, systemd service/timer, JSON state under `/var/lib`.

**Spec:** GitHub Issue #14, including the 30-minute stale threshold proposal, immediate incident notification, daily reminders, recovery notification, and external-monitor limitation.

## Global Constraints

- Default ntfy server is `https://ntfy.sh`.
- Topic is generated on first deployment and kept in `/etc/default/network-speed-health`; optional access token stays out of the repository.
- Do not allow notification errors to stop the existing measurement service.
- Health monitoring must run outside `network-speed.service` and persist incident/reminder state across restarts.
- A local monitor cannot notify while the Pi is powered off or disconnected from the network.

## Review Focus

- Missing or malformed topic configuration must not break measurements; monitor should log configuration and exit safely.
- ntfy HTTP errors/timeouts must not mark a notification as delivered or crash the measurement service.
- Empty database, DB connection errors, and naive/aware timestamps must be handled without false recovery.
- A service restart during an incident must preserve the 24-hour reminder schedule and avoid a duplicate start notification.
- The deployment script must preserve the local topic/token file and avoid exposing the token in output.

---

### Task 1: Health state and ntfy publisher

**Files:**
- Create: `src/network_speed/health_monitor.py`
- Create: `scripts/monitor_measurement_health.py`

**Interfaces:**
- `health_monitor.py` owns ntfy publishing, timestamp/incident evaluation, and atomic JSON state persistence.
- `monitor_measurement_health.py` loads repository DB configuration, checks systemd service state and latest successful v2 timestamp, then applies the state transition.

- [x] Implement the state transitions for outage start, 24-hour reminder, and recovery; treat publish failure as undelivered and preserve retryability.
- [x] Implement ntfy.sh POST with optional Bearer token and finite request timeout.
- [x] Query the latest successful v2 timestamp, catch DB/systemd failures as monitor input, and make missing topic a safe disabled state.

### Task 2: Independent systemd monitor and deployment

**Files:**
- Create: `systemd/network-speed-health.service`
- Create: `systemd/network-speed-health.timer`
- Modify: `scripts/deploy_to_raspberrypi.sh`

- [x] Add a five-minute systemd timer and oneshot service with persistent state directory and a separate environment file.
- [x] Install/enable the monitor units during normal deployment and generate one random topic if none is configured.
- [x] Print the topic needed for the user's ntfy subscription without printing any access token.
- [x] Keep `--dry-run` read-only and keep the existing database/backup artifacts excluded from rsync deletion.

### Task 3: Operator documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/v2-migration-runbook.md`

- [x] Document topic subscription, optional token setup, stale threshold, daily reminder cadence, and recovery behavior.
- [x] Document timer/journal inspection and clarify that Pi power/network loss requires an observer outside the Pi.

### Task 4: Branch review and PR

- [x] Inspect the complete diff for secrets, accidental unrelated files, and requirement coverage; the independent reviewer findings were addressed.
- [x] Run non-test syntax/format checks: Python bytecode compilation, `bash -n`, and `git diff --check` passed. Automated tests were not added or run.
- [x] Commit the feature in `8f72a20` and `b2d4369`.
- [ ] Open a PR linked to Issue #14.

**Review record:** An independent review found four Important issues; the follow-up commit addresses recovery delivery retry state, current-vs-cached DB timestamps, deployment path/service overrides, and journal error extraction. The author then re-read the changed paths; no new issue was found. PR creation remains.
