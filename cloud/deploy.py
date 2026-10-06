#!/usr/bin/env python3
"""Operator-only deployment. Secrets remain in process memory and encrypted host credentials."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse

HERE = Path(__file__).resolve().parent
VERSION = "1.20.1"
TARGETS = {
    "tapify-prod": ("prod", "tapify-prod-1"),
    "tapify-identity": ("identity", "tapify-identity-1"),
}


PROD_ONLY = re.compile(
    r"^// @@BEGIN_PROD_ONLY@@\n(.*?)^// @@END_PROD_ONLY@@\n", re.S | re.M
)


def render_config(template, role, host, values):
    """Render the public Alloy configuration; secrets are never substituted."""
    # Prod-only blocks (the API scrape) are kept without their markers on the
    # prod host and removed elsewhere, so other hosts have no dead targets.
    config = PROD_ONLY.sub(lambda m: m.group(1) if role == "prod" else "", template)
    for name, value in {"HOST": host, **values}.items():
        config = config.replace("@@" + name + "@@", json.dumps(value))
    if "@@" in config:
        raise ValueError("Unresolved configuration")
    return config


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def run(command, **kwargs):
    result = subprocess.run(
        command,
        stdin=subprocess.DEVNULL if "input" not in kwargs else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=kwargs.pop("timeout", 180),
        **kwargs,
    )
    if result.returncode:
        try:
            detail = json.loads(result.stderr)
            if set(detail) == {"installationFailedAt", "privateDetailsSuppressed"}:
                print(json.dumps(detail), file=sys.stderr)
        except (ValueError, TypeError):
            pass
        raise ValueError("Command failed; private diagnostics suppressed")
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", choices=TARGETS, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    role, host = TARGETS[args.host]
    item = json.loads(
        run(
            [
                "op",
                "item",
                "get",
                "prod-tapify-observability-secrets",
                "--vault",
                "Tapify Prod",
                "--format",
                "json",
            ]
        )
    )
    values = {}
    for name in [
        "METRICS_URL",
        "METRICS_USERNAME",
        "LOGS_URL",
        "LOGS_USERNAME",
        "ACCESS_POLICY_TOKEN",
    ]:
        matches = [f for f in item["fields"] if f["label"] == "GRAFANA_CLOUD_" + name]
        if len(matches) != 1 or not matches[0].get("value"):
            raise ValueError("Missing/ambiguous connection field")
        values[name] = matches[0]["value"].strip()
    for name, path in [
        ("METRICS_URL", "/api/prom/push"),
        ("LOGS_URL", "/loki/api/v1/push"),
    ]:
        url = urllib.parse.urlparse(values[name])
        if (
            url.scheme != "https"
            or not url.hostname.endswith(".grafana.net")
            or url.path != path
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Invalid endpoint")
    if not all(
        values[name].isdigit() for name in ["METRICS_USERNAME", "LOGS_USERNAME"]
    ):
        raise ValueError("Invalid tenant identifier")
    config = render_config(
        (HERE / "config.alloy.template").read_text(),
        role,
        host,
        {k: v for k, v in values.items() if k != "ACCESS_POLICY_TOKEN"},
    )
    target = args.artifacts / (host + ".alloy")
    target.write_text(config)
    run([str(args.artifacts / "alloy-darwin-arm64"), "validate", str(target)])
    if not args.apply:
        print(
            json.dumps(
                {
                    "host": host,
                    "configurationValidated": True,
                    "productionChanged": False,
                }
            )
        )
        return
    binary = args.artifacts / "alloy-linux-amd64"
    expected = digest(binary)
    archive = args.artifacts / ("alloy-" + VERSION + "-linux-amd64.zip")
    archive_digest = digest(archive)
    prefix = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        "-l",
        "root",
        args.host,
    ]
    run(prefix + ["install -d -m 0700 /opt/tapify-observability/incoming"])
    files = [
        archive,
        target,
        HERE / "telemetry.py",
        HERE / "alloy.service",
        HERE / "tapify-observability.service",
        HERE / "install.py",
    ]
    run(
        [
            "scp",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=15",
            *map(str, files),
            "root@" + args.host + ":/opt/tapify-observability/incoming/",
        ],
        timeout=600,
    )
    payload = {
        "host": host,
        "role": role,
        "binary_sha256": expected,
        "archive_sha256": archive_digest,
        "config_file": target.name,
        "token": values["ACCESS_POLICY_TOKEN"],
    }
    result = run(
        prefix + ["python3 /opt/tapify-observability/incoming/install.py"],
        input=json.dumps(payload).encode(),
    )
    # The fixed installer prints only rollout status, never configuration values.
    print(result.decode().strip())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "Cloud collector deployment refused or failed; private details suppressed.",
            file=sys.stderr,
        )
        sys.exit(1)
