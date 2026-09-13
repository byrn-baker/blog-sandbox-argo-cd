# Rollout verification

The recorded audit follows deployment of commit `2f289a4`. All six Argo CD
Applications were Synced and Healthy. Grafana contained exactly 38 dashboards:
28 in K3s, 7 in Observability, 2 in Storage and 1 in Network, with none in General.
The JSON records the audit time, individual queries, fresh samples and pod status.

All three masters supplied etcd, scheduler and controller-manager metrics.
The three local agents had empty remote-write queues. All six Longhorn managers
and all five selected Argo CD components were scraped successfully. All nine
K3s nodes were Ready, all three volumes were healthy with three RW replicas,
and all 28 network devices still supplied SNMP interface metrics. No failed
scrape targets, active coverage alerts or recent rule execution errors appeared
in the recorded checks.

All 26 queries in the three new overview dashboards returned data. Browser checks
loaded and scrolled every panel without query errors or No data results. The
screenshots show the deployed dashboards, including readable PVC and node names.
New metric families only have history from this deployment onward.

Validation before publication included the pinned Helm chart render, vmagent's
configuration dry-run, Kubernetes server-side dry-runs, and the SNMP generator's
16 tests. Later server-side validation used Argo's field manager to avoid an
ownership conflict with fields it had already applied. The latest rendered
Grafana Deployment was also admitted in a server-side dry-run, including its
native sidecar and startup probe on this K3s version.

The rollout exposed two provisioning problems: disabling chart dashboard sources
did not remove their old ConfigMaps, and per-object HTTP reload retries stalled
the dashboard sidecar. The bounded migration hook removed the 44 obsolete
ConfigMaps. The final sidecar loads the current files before Grafana startup and
continues watching them; Grafana's file provider detects updates every 30 seconds.
Grafana recovered and the browser checks passed. SQLite lock errors occurred
during provisioning, so this is not evidence that every database or storage
performance issue has been fixed.

These checks establish working metrics and dashboards during the audit. They do
not validate external alert notification delivery, install a log/trap pipeline,
prove cold-boot persistence of the QEMU/GRO changes, or replace a sustained
network and storage load test.
