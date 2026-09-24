# Network Telemetry dashboard verification

Checked on 2026-09-24. Dashboard UID: `network-telemetry`.

The final API run in `grafana-panel-checks.json` queried 12 data panels for
All, CE1, DCA-Leaf01 and CE2 over the preceding 24 hours. All 48 checks returned
HTTP 200 without query errors and met the expected nonempty/empty scope checks.

| Observation | All | CE1 | DCA-Leaf01 | CE2 |
| --- | ---: | ---: | ---: | ---: |
| Flow exporters | 28 | 1 | 1 | 1 |
| SuzieQ device rows | 2 | 1 | 1 | 0 |
| BGP rows | 18 | 8 | 10 | 0 |
| Interface rows | 33 | 10 | 23 | 0 |
| LLDP rows | 2 | 0 | 2 | 0 |
| Route rows | 182 | 76 | 106 | 0 |
| Poller rows | 10 | 5 | 5 | 0 |

`browser/browser-checks.json` records zero JavaScript and data-query errors
for all four selections. Screenshots show the merged flow conversation table,
raw records, scope-limited state, and poller timestamps. A final DCA-Leaf01 flow
screenshot checks the explicit log timestamp display added after the four-scope
browser run. Backend frame counts in the API report are not rendered table row
counts: each NetFlow conversation produces separate byte and packet frames,
which the dashboard merges into one row.

The management HTTPS endpoint passed certificate-verified `/api/health` with
`database: ok` and Grafana 13.1.1. All 13 Argo Applications were Healthy/Synced.
The SuzieQ datasource API reports its header value as a populated secure field
and does not return plaintext secureJsonData. Credentials were used in memory;
they are not part of these artifacts.

## Corrections made during verification

- Pod DNS could not resolve grafana.com. Signed, checksum-verified plugin
  archives are now installed from the existing lab mirror.
- Provisioning hit SQLite locks because Grafana 13.1.1's adapter did not apply
  the configured WAL mode. A declared init container backed up the database
  and enabled WAL before Grafana started. The running pod has WAL files and
  reached readiness. Plugin loading still took several minutes on the final
  startup; this work did not diagnose the underlying storage/network latency.
- Grafana's regex formatting of exporter addresses was rejected by LogsQL.
  The dashboard now uses exact address lists resolved from SNMP labels.
- Flow stats initially rendered as individual selectable frames. Explicit
  merge and column ordering now put exporters and byte/packet counts into
  readable tables. Ports retain their integer display rather than SI suffixes.
- A whole-range raw-flow sort timed out during a 24-hour query. Raw detail is
  now a bounded preview of 500 matching records, explicitly not guaranteed to
  be the newest. Aggregate panels still query the selected range.

## Limits

SuzieQ and syslog still cover only CE1 and DCA-Leaf01. This work did not expand
device configuration, test a historical state transition, implement SuzieQ
retention, or resolve the deferred vEOS forwarding issue. sFlow record counts
are not packet counts. Router observations can count the same traffic at
multiple devices and must not be summed as a unique network traffic total.
