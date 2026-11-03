from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_deploy_defaults_to_stable_local_hostname(tmp_path: Path) -> None:
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    capture_dir = tmp_path / "calls"
    capture_dir.mkdir()
    for command in ("rsync", "ssh"):
        shim = shim_dir / command
        shim.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$*\" >> '{capture_dir / (command + '.log')}'\n",
            encoding="utf-8",
        )
        shim.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}:{env['PATH']}"
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy_to_raspberrypi.sh"), "--dry-run"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    expected_target = "threeb@network-speed-pi.local:/home/threeb/network_speed"
    assert expected_target in result.stdout
    rsync_args = (capture_dir / "rsync.log").read_text(encoding="utf-8")
    assert expected_target in rsync_args
    assert "--dry-run" in rsync_args
    assert "--itemize-changes" in rsync_args
    assert "--exclude network_speed_backup.csv" in rsync_args
    assert not (capture_dir / "ssh.log").exists()


def test_certificate_generator_uses_dns_name_and_preserves_existing_files(tmp_path: Path) -> None:
    cert_dir = tmp_path / "certs"
    env = os.environ.copy()
    env["NETWORK_SPEED_CERT_DIR"] = str(cert_dir)

    subprocess.run(
        ["bash", str(ROOT / "scripts/generate_local_https_cert.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    cert_path = cert_dir / "network-speed-local.crt"
    key_path = cert_dir / "network-speed-local.key"
    san = subprocess.run(
        ["openssl", "x509", "-in", str(cert_path), "-noout", "-ext", "subjectAltName"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    fingerprint = subprocess.run(
        ["openssl", "x509", "-in", str(cert_path), "-noout", "-fingerprint"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert "DNS:network-speed-pi.local" in san
    assert "DNS:localhost" in san
    assert "IP Address:127.0.0.1" in san

    subprocess.run(
        ["bash", str(ROOT / "scripts/generate_local_https_cert.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert key_path.exists()
    assert subprocess.run(
        ["openssl", "x509", "-in", str(cert_path), "-noout", "-fingerprint"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout == fingerprint

    subprocess.run(
        ["bash", str(ROOT / "scripts/generate_local_https_cert.sh"), "--force"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert subprocess.run(
        ["openssl", "x509", "-in", str(cert_path), "-noout", "-fingerprint"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout != fingerprint


def test_certificate_generator_accepts_router_local_dns_hostname(tmp_path: Path) -> None:
    cert_dir = tmp_path / "router-certs"
    env = os.environ.copy()
    env["NETWORK_SPEED_CERT_DIR"] = str(cert_dir)
    env["NETWORK_SPEED_HOSTNAME"] = "network-speed-pi.home"

    subprocess.run(
        ["bash", str(ROOT / "scripts/generate_local_https_cert.sh")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    san = subprocess.run(
        [
            "openssl",
            "x509",
            "-in",
            str(cert_dir / "network-speed-local.crt"),
            "-noout",
            "-ext",
            "subjectAltName",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert "DNS:network-speed-pi.home" in san
    assert "DNS:network-speed-pi.local" not in san
