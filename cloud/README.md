# Grafana Cloud collectors

The cloud path uses native Grafana Alloy (pinned release and verified archive
checksum) with its embedded Unix exporter. It is separate from the legacy
Promtail/NetBird setup script. Production and Identity hosts need no central
Grafana/Loki VM or public exporter port.

Deploy the two systemd units with `/etc/alloy/config.alloy` rendered from the
template using the host name and four public ingestion connection values.
The collector token is a host-bound encrypted systemd credential named
`grafana_token`, stored at `/etc/credstore.encrypted/tapify-alloy-token.cred`.
It is read as an Alloy secret, never inserted in the public configuration.
The collector HTTP interface binds to loopback port 12345.

`telemetry.py` reads only the named Tapify container/service states and bounded
recent logs. It exports counters and fixed, sanitized log summaries. Original
messages, request bodies, customer identifiers and credentials are never written
to the export stream. This initial log stream deliberately provides operational
summaries; inspect originals locally for detail, or use separately scrubbed
Sentry exceptions. Metrics/log retention is bounded locally.

On Identity the helper refreshes the existing **read-only** `ops-status` job
every minute. It never runs a delivery/cleanup job or enables its timer.
Job `expected` metrics are derived from timer enablement; ops-status is expected
because this helper runs it. Last-success timestamps use the actual systemd
execution timestamp and remain unchanged on failures. Since systemd can discard
completed one-shot instance state, trusted PID-1 journal completion/failure
records provide a fallback. Application-provided messages cannot forge success.
Queues are exported only
as validated numeric aggregate counts. A stale/missing operational snapshot must
be alerted on alongside queue backlog and worker failures.

Host configuration is `/etc/tapify-observability/host.json` with `role` (`prod`
or `identity`) and `host` (`tapify-prod-1` or `tapify-identity-1`). Metrics are in
`/var/lib/tapify-observability-metrics/tapify.prom`; sanitized events are in
`/var/log/tapify-observability/events.log`. Helper state is private under
`/var/lib/tapify-observability`.

Run focused checks with `python3 -m unittest discover -s cloud -p 'test_*.py'`.
Validate rendered Alloy configurations with the pinned binary before activation.
`deploy.py --host <tapify-prod|tapify-identity> --artifacts <approved-directory>`
validates a public configuration; `--apply` transfers the verified compressed
Linux release and installs the fixed native services. Keep the official
`SHA256SUMS` verification evidence for the artifact. Binary hashes are streamed
to bound memory usage. No production token is written to the local filesystem.
Deployment, remote credentials, notification tests and timer enablement require
authorization for those operations. Retain previous configurations for rollback.
