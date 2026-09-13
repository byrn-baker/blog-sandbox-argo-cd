# Routing polling validation

The rollout used CE1, DCA-Leaf01 and SP1 as canaries before expanding the
role-based receivers to the fleet. The existing 28-device interface collection
remained enabled. The pinned Collector binary accepted the generated configuration,
Helm rendered it successfully, and the Kubernetes API accepted dry runs of the
new dashboard and routing rules. The generator's 23 tests passed.

Two post-rollout snapshots, over two minutes apart, found the same result in both
VictoriaMetrics stores: 133 BGP state, uptime and transition-counter rows;
28 IS-IS adjacencies; 56 Cisco BFD application rows; and 28 fresh device uptime
samples. All reported states were Established or Up. All 28 IS-IS local interface
names matched CLI output. BFD local discriminators matched the 28 CLI sessions.

`routing-cli-comparison.json` records the per-device comparison. The SNMP BGP
peers are a subset of the 136 peers found with Cisco IPv4/VPNv4 and EOS
all-VRF/EVPN summaries. Three SERVERS-VRF peers on the Leaf03 devices are absent
from the polled tables. BFD application IDs 9 and 15 report the same local
sessions separately. The BFD interface column is excluded because its values
do not match IF-MIB; the dashboard makes no BFD interface-name claim.

`routing-polling-audit.json` contains the repeated snapshots. The 15 dashboard
queries all returned data. Browser checks found no query errors or empty panels.
Remote AS numbers retain their full value rather than magnitude abbreviations.
`network-routing.png` captures the corrected rendering.

`routing-pipeline-health.json` records zero current Collector failed, refused or
errored metric points, zero queued export requests, and 47 healthy, inactive
routing rules. Grafana contains Network 2, K3s 28, Storage 2 and Observability 7
dashboards. No external alert delivery or trap/syslog reception was tested.

## Repeating the checks

In Grafana Explore, run each query against both `network-snmp` and
`VictoriaMetrics` datasource UIDs:

```promql
count(snmp_bgp_peer_state{job="snmp"})
count(snmp_bgp_peer_uptime_seconds{job="snmp"})
count(snmp_bgp_peer_established_transitions_total{job="snmp"})
count(snmp_isis_adjacency_state{job="snmp"})
count(snmp_bfd_session_state{job="snmp",local_discriminator!=""})
count(count by(device,local_discriminator)(snmp_bfd_session_state{job="snmp",local_discriminator!=""}))
count(time() - timestamp(snmp_device_uptime_ticks{job="snmp"}) < 180)
```

Expected counts are 133, 133, 133, 28, 56, 28 and 28 respectively. Query state
values separately; a correct count alone does not establish healthy neighbors.
Use the dashboard's IS-IS query to check its dynamic interface join. Compare
against `show isis neighbors` and `show interfaces`. For BFD use the LD column in
`show bfd neighbors`, retaining application identity in the SNMP comparison.
Review `routing-rules.yaml` whenever neighbor intent changes. These snapshots
verify collection across repeated polls, not stability through a reboot or an
extended high-throughput test.
