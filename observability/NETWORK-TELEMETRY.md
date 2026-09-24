# Network Telemetry dashboard

Open `https://grafana.sandbox.lab/d/network-telemetry` in the Network folder.
The dashboard combines existing SNMP metrics, VictoriaLogs flow/syslog records,
and SuzieQ REST tables. The device selector obtains names from SNMP and resolves
their management addresses for exporter filtering. Missing data stays missing.

## Data and time

- SNMP charts and raw logs use Grafana's selected time range.
- Raw flow detail is a bounded preview of up to 500 matching records, not
  necessarily the newest. Narrow the device and time selection for investigation.
- NetFlow byte/packet sums describe exported observations. The same traffic can
  be observed by several routers; All is not a unique network traffic total.
- sFlow detail displays sampled fields and sampling rate. Record counts are
  not packets, sessions, or utilization estimates.
- SuzieQ state tables request the last known state at the selected range end.
  Row timestamps can be old because unchanged state is not rewritten each poll.
- The live sqPoller table deliberately ignores historical range selection. It
  shows collection status and timestamp independently of state-change age.
- SuzieQ and syslog cover all 28 network devices. Empty BGP or LLDP tables can
  be valid for a device; check collection status before diagnosing missing data.
- Raw logs retain 14 days. SuzieQ coalesced history retains 14 days plus a
  pre-cutoff baseline for unchanged state, with a 24-hour recovery quarantine.
  See `../suzieq/README.md` for the expiry and recovery limits.
- Storage usage, active/quarantined bytes, retention age and coalescer age are
  fleet-wide panels, independent of the device selector. These operational
  gauges arrive through OTLP. SuzieQ state still comes directly from its API;
  it is not converted into Prometheus state metrics.

## Provisioning and credentials

The root-managed VictoriaMetrics Application provisions plugins and datasources
from `values/victoria-metrics-values.yaml`. VictoriaLogs 0.32.0 and Infinity 4.0.0
are pinned Grafana plugins. The existing cluster-observability Application
provisions the dashboard ConfigMap from `observability/kustomization.yaml`.

Plugin archives are served by the existing lab mirror under `grafana-plugins/`.
External DNS resolution failed from the Grafana pod during the first rollout.
The mirrored archives match the Grafana catalog SHA-256 values:

```text
8204d097b17f53b1c3a71761047734b7980bd983710c6cfcef8d938abe5eeef0  victoriametrics-logs-datasource-0.32.0.zip
0aa338db608f4bff2fd5c135930621ecbd6a0a72f8d8e9bc68bb58636972efc9  yesoreyeram-infinity-datasource-4.0.0.zip
```

Grafana reads API_KEY from the existing suzieq-credentials Secret through an
environment reference. Provisioning stores it as secureJsonData; it never goes
in dashboard JSON or URL parameters. Infinity restricts destinations to the
internal SuzieQ service and uses its backend parser. Rotating the Secret also
requires a declared Grafana pod rollout to reread the environment value.

## Grafana startup

Grafana 13.1.1's SQLite adapter converts `_journal_mode=WAL` to
`_pragma=_journal_mode(WAL)`, leaving the database in rollback-journal mode.
The rollout encountered repeated SQLITE_BUSY errors during provisioning.
The declared `sqlite-wal` init container sets `PRAGMA journal_mode=WAL` before
Grafana starts, and saves a SQLite backup to `grafana.db.before-wal` first.
It does not overwrite that backup on later starts. Recreate deployment keeps
the startup step separate from the Grafana writer. Recheck the workaround when
upgrading Grafana. The relevant upstream implementation is
[the 13.1.1 SQLite adapter](https://github.com/grafana/grafana/blob/v13.1.1/pkg/util/sqlite/sqlite_nocgo.go).

## Verification

Render the pinned chart and run `kubectl kustomize observability` before pushing.
After Argo reconciliation, forward Grafana locally:

```sh
kubectl -n observability port-forward svc/victoria-metrics-k8s-stack-grafana 13000:80
python3 observability/verify_network_telemetry.py
```

The verifier uses the existing admin Secret in memory, queries the provisioned
dashboard through Grafana for All, CE1, DCA-Leaf01 and CE2, and prints only result
counts and errors. Browser verification is available in
`check_telemetry_browser.py` with Playwright and a locally installed Chromium.
Set `CHROMIUM_PATH` if Chromium is not installed in Playwright's default location.
The browser check records JavaScript and Grafana query errors as well as screenshots.
The API check accepts `--report path.json` for sanitized evidence and asserts
the known empty protocol scopes. It resolves exporter addresses from live SNMP
labels, matching the dashboard's exact-address selection.
An empty scope-limited table is expected; inspect poller status before treating
it as collection failure.
