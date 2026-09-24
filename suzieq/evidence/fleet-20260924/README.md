# SuzieQ fleet rollout, September 24, 2026

The poller inventory now covers all 28 Nautobot network devices: 13 IOS-XE
routers and 15 EOS switches. The original two-device deployment expanded to a
five-device pilot, then the full fleet through the Argo CD root Application.
Existing device credentials were reused, not changed. Polling is read-only.

`pilot-first.json` and `pilot-second.json` record the pilot checks. Full-fleet
checks at 04:02:04 and 04:03:36 UTC returned 28 device rows, 329 BGP rows,
370 interface rows, 36 LLDP rows and 2,274 route rows. All 140 service-status
rows were OK in both checks. The inventory, device names and addresses were
reconciled against live Nautobot, not a separate static device list.

BGP and LLDP can legitimately have no rows on some devices. Every device had
device, interface and route rows, and status entries for all five configured
services. The period is 60 seconds. Unchanged state and poller statistics are
not necessarily rewritten every cycle, so timestamps are not evidence of a
fresh write on every successful poll. These checks establish collection, not
that every BGP session or forwarding path is healthy.

## Retention and storage

The sidecar retains 14 days of coalesced history plus a complete baseline block
before the cutoff. Expired blocks spend 24 hours in quarantine before removal.
Raw files are excluded. Six local tests passed. `retention-copy-test.json`
records an isolated test against copied live data: 12 files were quarantined,
latest and retained-history results for six tables were unchanged, and all
files were restored byte-for-byte. Production history was not shortened for
this test.

`storage-metrics.json` confirms nine gauges arrived in both the network-history
and cluster-health stores. `alert-rules.json` confirms all four rules were
loaded, healthy and inactive. The five-GiB PVC remains in place; short initial
observations do not establish a measured 14-day fleet storage budget. Monitor
growth before changing scope or retention. The recovery and backup limits are
documented in `../../README.md`.

The Grafana integration uses SuzieQ's REST API for state. Storage-health gauges
use OTLP; this rollout does not implement the planned BGP state-to-metrics
bridge, credential-rotation tests or controlled forwarding-failure tests.
