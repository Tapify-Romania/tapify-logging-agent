#!/usr/bin/env python3
"""Fixed native collector installation, invoked over SSH with a private stdin payload."""

import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import zipfile

STAGE = "input"
INCOMING = Path("/opt/tapify-observability/incoming")


def run(command, **kwargs):
    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL if "input" not in kwargs else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=90,
        **kwargs,
    )
    if result.returncode:
        raise ValueError("Installation command failed")
    return result.stdout


def main():
    global STAGE
    if os.geteuid() != 0:
        raise ValueError("Root required")
    payload = json.load(sys.stdin)
    if (payload["role"], payload["host"]) not in [
        ("prod", "tapify-prod-1"),
        ("identity", "tapify-identity-1"),
    ]:
        raise ValueError("Unexpected target")
    if payload["config_file"] != payload["host"] + ".alloy":
        raise ValueError("Unexpected configuration")
    if not payload["token"] or any(c in payload["token"] for c in "\r\n\0"):
        raise ValueError("Invalid token")
    binary = INCOMING / "alloy-linux-amd64"
    archive = INCOMING / "alloy-1.20.1-linux-amd64.zip"

    def digest(path):
        checksum = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                checksum.update(block)
        return checksum.hexdigest()

    STAGE = "archive-verification"
    if digest(archive) != payload["archive_sha256"]:
        raise ValueError("Transferred archive checksum mismatch")
    with zipfile.ZipFile(archive) as compressed:
        with (
            compressed.open("alloy-linux-amd64") as source,
            binary.open("xb") as target,
        ):
            shutil.copyfileobj(source, target, length=1024 * 1024)
    if digest(binary) != payload["binary_sha256"]:
        raise ValueError("Transferred binary checksum mismatch")
    STAGE = "existing-installation-check"
    if (
        Path("/etc/systemd/system/alloy.service").exists()
        or Path("/etc/credstore.encrypted/tapify-alloy-token.cred").exists()
    ):
        raise ValueError("Existing installation needs reviewed update")
    STAGE = "service-user-and-directories"
    try:
        account = pwd.getpwnam("alloy")
    except KeyError:
        run(
            [
                "useradd",
                "--system",
                "--home-dir",
                "/var/lib/alloy",
                "--shell",
                "/usr/sbin/nologin",
                "alloy",
            ]
        )
        account = pwd.getpwnam("alloy")
    for name in [
        "/etc/alloy",
        "/etc/tapify-observability",
        "/usr/local/lib/tapify-observability",
        "/var/lib/tapify-observability-metrics",
        "/var/lib/tapify-observability",
    ]:
        Path(name).mkdir(mode=0o755, parents=True, exist_ok=True)
    os.chmod("/var/lib/tapify-observability", 0o700)
    logdir = Path("/var/log/tapify-observability")
    logdir.mkdir(mode=0o2750, exist_ok=True)
    os.chown(logdir, 0, account.pw_gid)
    os.chmod(logdir, 0o2750)
    config = Path("/etc/tapify-observability/host.json")
    config.write_text(json.dumps({"role": payload["role"], "host": payload["host"]}))
    os.chmod(config, 0o644)
    for source, target, mode in [
        (binary, Path("/usr/local/bin/alloy"), 0o755),
        (INCOMING / payload["config_file"], Path("/etc/alloy/config.alloy"), 0o644),
        (
            INCOMING / "telemetry.py",
            Path("/usr/local/lib/tapify-observability/telemetry.py"),
            0o755,
        ),
    ]:
        shutil.copyfile(source, target)
        os.chmod(target, mode)
    STAGE = "encrypted-credential"
    credential = "/etc/credstore.encrypted/tapify-alloy-token.cred"
    run(
        [
            "systemd-creds",
            "encrypt",
            "--with-key=host",
            "--name=grafana_token",
            "-",
            credential,
        ],
        input=payload["token"].encode(),
    )
    os.chmod(credential, 0o600)
    STAGE = "native-configuration-validation"
    run(
        [
            "systemd-run",
            "--quiet",
            "--wait",
            "--pipe",
            "--collect",
            "--unit=tapify-alloy-config-validation",
            "--uid=alloy",
            "--property=LoadCredentialEncrypted=grafana_token:" + credential,
            "/usr/local/bin/alloy",
            "validate",
            "/etc/alloy/config.alloy",
        ]
    )
    for name in ["alloy.service", "tapify-observability.service"]:
        target = Path("/etc/systemd/system") / name
        shutil.copyfile(INCOMING / name, target)
        os.chmod(target, 0o644)
    STAGE = "unit-validation"
    run(
        [
            "systemd-analyze",
            "verify",
            "/etc/systemd/system/alloy.service",
            "/etc/systemd/system/tapify-observability.service",
        ]
    )
    STAGE = "activation"
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "--now", "tapify-observability.service"])
    run(["systemctl", "enable", "--now", "alloy.service"])
    print(
        json.dumps(
            {
                "host": payload["host"],
                "collectorInstalled": True,
                "version": "1.20.1",
                "credentialEncrypted": True,
                "deliveryTimersChanged": False,
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            json.dumps(
                {"installationFailedAt": STAGE, "privateDetailsSuppressed": True}
            ),
            file=sys.stderr,
        )
        sys.exit(1)
