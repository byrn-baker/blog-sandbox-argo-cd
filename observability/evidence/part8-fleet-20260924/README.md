# Fleet dashboard verification, September 24, 2026

Network Telemetry now shows fleet syslog and SuzieQ state alongside the existing
SNMP and flow panels at `https://grafana.sandbox.lab/d/network-telemetry`.

`panel-checks.json` records 64 successful backend checks: 16 data panels for
All, CE1, DCA-Leaf01 and CE2. Known empty protocol combinations remain empty,
including CE1/CE2 LLDP and NetFlow conversations for the sFlow-only EOS device.
The fleet queries returned 28 device rows and 140 healthy collection statuses.

`browser/browser-checks.json` records four rendered views with no JavaScript
or datasource query errors. Screenshots cover traffic, conversations, flow
detail, state and storage. Visual review caught the default Grafana thresholds
coloring normal retention/coalescer ages red; explicit thresholds now follow
the hourly cleanup cadence and health-alert limits. The affected early storage
screenshots were recaptured after that correction.

Storage panels are fleet-wide even when a single device is selected. Their
metrics arrive through OTLP, while SuzieQ state is queried through its API.
This does not introduce a BGP state-to-metrics bridge or prove that all network
sessions and forwarding paths are healthy.
