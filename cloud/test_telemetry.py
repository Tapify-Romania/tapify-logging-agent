import json
import unittest
from telemetry import (
    count_errors,
    event,
    parse_ops,
    task_snapshot,
    task_journal_snapshot,
)


class TelemetryTests(unittest.TestCase):
    def test_garbage_collected_oneshot_uses_trusted_journal_history(self):
        unit = "tapify-auth-job@ops-status.service"
        success = {
            "_PID": "1",
            "UNIT": unit,
            "MESSAGE_ID": "39f53479d3a045ac8e11786248231fbf",
            "JOB_RESULT": "done",
            "__REALTIME_TIMESTAMP": "1000000",
        }
        failure = {
            "_PID": "1",
            "UNIT": unit,
            "JOB_RESULT": "failed",
            "__REALTIME_TIMESTAMP": "2000000",
        }
        result = task_journal_snapshot(
            [json.dumps(success), json.dumps(failure)], unit, True
        )
        self.assertEqual(
            result, {"expected": 1, "last_run": 2, "last_success": 1, "ok": 0}
        )
        success["_PID"] = "555"
        self.assertIsNone(task_journal_snapshot([json.dumps(success)], unit, True))

    def test_failure_preserves_previous_success_and_records_failure(self):
        result = task_snapshot(
            {
                "Result": "exit-code",
                "ExecMainStatus": "3",
                "ExecMainExitTimestampMonotonic": "9000000",
            },
            True,
            100,
            10,
            80,
        )
        self.assertEqual(
            result, {"expected": 1, "last_run": 99, "last_success": 80, "ok": 0}
        )

    def test_success_uses_real_exit_time_not_poll_time(self):
        result = task_snapshot(
            {
                "Result": "success",
                "ExecMainStatus": "0",
                "ExecMainExitTimestampMonotonic": "7000000",
            },
            False,
            100,
            10,
        )
        self.assertEqual(result["last_success"], 97)
        self.assertEqual(result["expected"], 0)

    def test_never_run_job_is_not_reported_successful(self):
        result = task_snapshot(
            {"Result": "success", "ExecMainStatus": "0"}, True, 100, 10
        )
        self.assertEqual(result["ok"], 0)
        self.assertEqual(result["last_success"], 0)

    def test_ops_parser_exports_only_numeric_aggregate_allowlist(self):
        body = {"appMode": "production", "private": "SECRET-CANARY"}
        for key in [
            "oidcLifecycle",
            "securityMail",
            "providerRevocations",
            "passwordResetCleanup",
        ]:
            body[key] = {"pending": 2, "failed": 0, "recipient": "SECRET-CANARY"}
        parsed = parse_ops(
            [
                json.dumps(
                    {"MESSAGE": json.dumps(body), "__REALTIME_TIMESTAMP": "1000000"}
                )
            ]
        )
        self.assertEqual(parsed[0], 1)
        self.assertNotIn("SECRET-CANARY", repr(parsed))
        body["oidcLifecycle"]["pending"] = "SECRET-CANARY"
        self.assertIsNone(
            parse_ops(
                [
                    json.dumps(
                        {"MESSAGE": json.dumps(body), "__REALTIME_TIMESTAMP": "1000000"}
                    )
                ]
            )
        )

    def test_raw_error_body_is_never_in_exported_event(self):
        count = count_errors(
            'ERROR password=SECRET-CANARY\n{"level":"error","statusCode":401,"cookie":"SECRET-CANARY"}'
        )
        self.assertEqual(count, 1)
        record = event("tapify-prod-1", "api", "error_summary", count=count)
        self.assertNotIn("SECRET-CANARY", json.dumps(record))
        with self.assertRaises(ValueError):
            event("tapify-prod-1", "SECRET-CANARY", "error_summary")


if __name__ == "__main__":
    unittest.main()
