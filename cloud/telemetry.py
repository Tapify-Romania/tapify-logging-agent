#!/usr/bin/env python3
"""Bounded host/service/job telemetry. Original log messages never leave this process."""

import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request

ROOT = Path("/var/lib/tapify-observability")
METRICS = Path("/var/lib/tapify-observability-metrics")
LOGS = Path("/var/log/tapify-observability/events.log")
TASKS = {
    "lifecycle": 60,
    "security-mail": 60,
    "provider-revocations": 60,
    "password-resets": 300,
    "ops-status": 60,
}
PROPERTIES = [
    "LoadState",
    "ActiveState",
    "Result",
    "ExecMainStatus",
    "ExecMainExitTimestampMonotonic",
    "NRestarts",
]
STATS = {"pending", "overduePending", "activeLeased", "reclaimableLeased", "failed"}
OUTBOXES = {
    "oidcLifecycle": "lifecycle",
    "securityMail": "security-mail",
    "providerRevocations": "provider-revocations",
    "passwordResetCleanup": "password-resets",
}
HEALTH = {
    "api": "http://127.0.0.1:3300/health",
    "dashboard": "http://127.0.0.1:3100/ro/login",
    "menu": "http://127.0.0.1:3200/api/health",
    "identity": "http://127.0.0.1:3120/sign-in",
}


def run(command, timeout=10):
    return subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env={
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            "LC_ALL": "C",
        },
    )


def service_state(unit):
    result = run(["systemctl", "show", unit, "--property=" + ",".join(PROPERTIES)])
    if result.returncode:
        return {}
    return dict(
        line.split("=", 1)
        for line in result.stdout.decode().splitlines()
        if "=" in line
    )


def task_snapshot(properties, expected, now, monotonic, previous_success=0):
    exit_mono = int(properties.get("ExecMainExitTimestampMonotonic", "0") or "0")
    exit_time = max(0, now - monotonic + exit_mono / 1_000_000) if exit_mono else 0
    ok = (
        properties.get("Result") == "success"
        and properties.get("ExecMainStatus") == "0"
    )
    if exit_time and ok:
        previous_success = max(previous_success, exit_time)
    return {
        "expected": int(expected),
        "last_run": exit_time,
        "last_success": previous_success,
        "ok": int(ok and bool(exit_time)),
    }


def task_journal_snapshot(lines, unit, expected, previous_success=0):
    """One-shot instances can be garbage-collected; retain trusted manager results."""
    latest = None
    for line in lines:
        try:
            entry = json.loads(line)
            if entry.get("_PID") != "1" or entry.get("UNIT") != unit:
                continue
            if (
                entry.get("MESSAGE_ID") == "39f53479d3a045ac8e11786248231fbf"
                and entry.get("JOB_RESULT") == "done"
            ):
                ok = True
            elif entry.get("JOB_RESULT") in {
                "failed",
                "timeout",
                "canceled",
                "dependency",
            } or entry.get("RESULT") in {
                "exit-code",
                "signal",
                "timeout",
                "core-dump",
                "resources",
                "start-limit-hit",
            }:
                ok = False
            else:
                continue
            stamp = int(entry["__REALTIME_TIMESTAMP"]) / 1_000_000
            if ok:
                previous_success = max(previous_success, stamp)
            if latest is None or stamp > latest[0]:
                latest = (stamp, ok)
        except (ValueError, TypeError, KeyError):
            continue
    if latest is None:
        return None
    return {
        "expected": int(expected),
        "last_run": latest[0],
        "last_success": previous_success,
        "ok": int(latest[1]),
    }


def parse_ops(lines):
    """Accept only production aggregate counts; discard every other field/body."""
    latest = None
    for line in lines:
        try:
            entry = json.loads(line)
            body = json.loads(entry["MESSAGE"])
            if body.get("appMode") != "production":
                continue
            counts = {}
            for source, task in OUTBOXES.items():
                for stat, value in body[source].items():
                    if stat in STATS:
                        if type(value) is not int or value < 0 or value > 2**31 - 1:
                            raise ValueError("Invalid count")
                        counts[(task, stat)] = value
            if not all(
                (task, "pending") in counts and (task, "failed") in counts
                for task in OUTBOXES.values()
            ):
                continue
            candidate = (int(entry["__REALTIME_TIMESTAMP"]) / 1_000_000, counts)
            if latest is None or candidate[0] > latest[0]:
                latest = candidate
        except (ValueError, TypeError, KeyError):
            continue
    return latest


def count_errors(text):
    count = 0
    for line in text.splitlines():
        line = re.sub(r"\x1b\[[0-9;]*m", "", line)
        if re.search(r'"statusCode"\s*:\s*4\d\d', line):
            continue
        if re.search(r'\b(ERROR|FATAL)\b|"level"\s*:\s*"(error|fatal)"', line):
            count += 1
    return count


def event(host, service, kind, count=0, up=None):
    if host not in {"tapify-prod-1", "tapify-identity-1"}:
        raise ValueError("Unknown host")
    if service not in {"api", "dashboard", "menu", "identity", "collector", *TASKS}:
        raise ValueError("Unknown service")
    if kind not in {
        "heartbeat",
        "state_change",
        "error_summary",
        "snapshot_failure",
        "job_failure",
    }:
        raise ValueError("Unknown event")
    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host": host,
        "service": service,
        "event": kind,
        "count": int(count),
        "up": up,
        "message": {
            "heartbeat": "Monitoring snapshot completed",
            "state_change": "Service state changed",
            "error_summary": "Error-level entries observed; inspect original logs on the host",
            "snapshot_failure": "Monitoring snapshot failed; inspect the host",
            "job_failure": "Identity job failed; inspect the host",
        }[kind],
    }


def write_event(record):
    # Bounded, operator-owned files; never record source messages, URLs or identifiers.
    if LOGS.exists() and LOGS.stat().st_size > 2_000_000:
        previous = LOGS.with_suffix(".log.1")
        os.replace(LOGS, previous)
    fd = os.open(LOGS, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o640)
    with os.fdopen(fd, "a") as output:
        output.write(json.dumps(record) + "\n")


def metric(name, value, **labels):
    encoded = ",".join(
        key + "=" + json.dumps(str(val)) for key, val in sorted(labels.items())
    )
    return name + ("{" + encoded + "}" if encoded else "") + " " + str(value) + "\n"


def atomic_write(path, text, mode):
    temporary = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "w") as output:
        output.write(text)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def collect(config, state):
    now = time.time()
    role, host = config["role"], config["host"]
    expected_host = {"prod": "tapify-prod-1", "identity": "tapify-identity-1"}[role]
    if host != expected_host:
        raise ValueError("Host mismatch")
    text = metric("tapify_observability_snapshot_timestamp_seconds", now)
    services = ["api", "dashboard", "menu"] if role == "prod" else ["identity"]
    until = datetime.datetime.now(datetime.timezone.utc).isoformat()
    since = state.get("logs_since", until)
    for service in services:
        if role == "prod":
            result = run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    '{"up":{{.State.Running}},"restarts":{{.RestartCount}}}',
                    "tapify-" + service,
                ]
            )
            data = (
                json.loads(result.stdout)
                if result.returncode == 0
                else {"up": False, "restarts": 0}
            )
            logs = run(
                [
                    "docker",
                    "logs",
                    "--since",
                    since,
                    "--until",
                    until,
                    "--tail",
                    "500",
                    "tapify-" + service,
                ]
            )
            errors = (
                count_errors((logs.stdout + logs.stderr).decode(errors="replace"))
                if logs.returncode == 0
                else 0
            )
        else:
            data = service_state("tapify-auth.service")
            data = {
                "up": data.get("ActiveState") == "active",
                "restarts": int(data.get("NRestarts", "0")),
            }
            logs = run(
                [
                    "journalctl",
                    "-u",
                    "tapify-auth.service",
                    "--since",
                    since,
                    "--until",
                    until,
                    "-n",
                    "500",
                    "--no-pager",
                    "-o",
                    "cat",
                ]
            )
            errors = (
                count_errors(logs.stdout.decode(errors="replace"))
                if logs.returncode == 0
                else 0
            )
        up = int(data["up"])
        try:
            with urllib.request.urlopen(HEALTH[service], timeout=5) as response:
                up = int(up and response.status == 200)
        except Exception:
            up = 0
        text += metric("tapify_service_up", up, service=service)
        text += metric(
            "tapify_service_restarts_total", data["restarts"], service=service
        )
        count = state.setdefault("errors", {}).get(service, 0) + errors
        state["errors"][service] = count
        text += metric("tapify_service_log_errors_total", count, service=service)
        if state.setdefault("services", {}).get(service) != up:
            write_event(event(host, service, "state_change", up=up))
        state["services"][service] = up
        if errors:
            write_event(event(host, service, "error_summary", count=errors))
    state["logs_since"] = until
    if role == "identity":
        # This is the existing read-only aggregate-status job, never a delivery/cleanup job.
        if now - state.get("ops_invoked_at", 0) >= 60:
            run(
                ["systemctl", "start", "tapify-auth-job@ops-status.service"], timeout=30
            )
            state["ops_invoked_at"] = now
        for task in TASKS:
            text += metric("tapify_identity_job_period_seconds", TASKS[task], task=task)
            properties = service_state("tapify-auth-job@" + task + ".service")
            enabled = (
                run(
                    ["systemctl", "is-enabled", "tapify-auth-job@" + task + ".timer"]
                ).returncode
                == 0
            )
            previous = state.setdefault("tasks", {}).get(task, {})
            snapshot = task_snapshot(
                properties,
                enabled or task == "ops-status",
                now,
                time.monotonic(),
                previous.get("last_success", 0),
            )
            if not snapshot["last_run"]:
                unit = "tapify-auth-job@" + task + ".service"
                history = run(
                    ["journalctl", "-u", unit, "-n", "40", "--no-pager", "-o", "json"]
                )
                snapshot = (
                    task_journal_snapshot(
                        history.stdout.decode(errors="replace").splitlines(),
                        unit,
                        enabled or task == "ops-status",
                        previous.get("last_success", 0),
                    )
                    or snapshot
                )
            state["tasks"][task] = snapshot
            for key, value in snapshot.items():
                text += metric("tapify_identity_job_" + key, value, task=task)
            if (
                snapshot["last_run"]
                and not snapshot["ok"]
                and snapshot["last_run"] != previous.get("last_run")
            ):
                write_event(event(host, task, "job_failure"))
        journal = run(
            [
                "journalctl",
                "-u",
                "tapify-auth-job@ops-status.service",
                "-n",
                "60",
                "--no-pager",
                "-o",
                "json",
            ]
        )
        parsed = parse_ops(journal.stdout.decode(errors="replace").splitlines())
        text += metric("tapify_identity_ops_snapshot_valid", int(parsed is not None))
        text += metric(
            "tapify_identity_ops_snapshot_timestamp_seconds", parsed[0] if parsed else 0
        )
        if parsed:
            for (task, stat), value in parsed[1].items():
                text += metric("tapify_identity_outbox_" + stat, value, task=task)
    text += metric("tapify_observability_snapshot_ok", 1)
    if now - state.get("heartbeat_at", 0) >= 60:
        write_event(event(host, "collector", "heartbeat"))
        state["heartbeat_at"] = now
    return text


def main():
    if os.geteuid() != 0:
        raise ValueError("Root required")
    config = json.loads(Path("/etc/tapify-observability/host.json").read_text())
    path = ROOT / "state.json"
    state = json.loads(path.read_text()) if path.exists() else {}
    while True:
        try:
            text = collect(config, state)
            atomic_write(METRICS / "tapify.prom", text, 0o644)
            atomic_write(path, json.dumps(state), 0o600)
        except Exception:
            atomic_write(
                METRICS / "tapify.prom",
                metric("tapify_observability_snapshot_ok", 0)
                + metric(
                    "tapify_observability_snapshot_timestamp_seconds", time.time()
                ),
                0o644,
            )
            write_event(event(config["host"], "collector", "snapshot_failure"))
        time.sleep(30)


if __name__ == "__main__":
    main()
