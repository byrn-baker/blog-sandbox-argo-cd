# Part 7 verification and screenshots

These are browser captures of the deployed Grafana dashboards reached through
`https://grafana.sandbox.lab`. They are not mockups. The article uses the current
Cisco interface, folder, K3s and SERVERS-VRF views; the Arista, storage and Argo
views provide supporting screenshots.

| File | View or evidence |
| --- | --- |
| part7-snmp-cisco.png | CE1 / GigabitEthernet2; the freshness counter remains fleet-wide |
| part7-snmp-arista.png | DCA-Leaf01 / Ethernet1 |
| part7-dashboard-folders.png | K3s, Network, Observability and Storage folders |
| part7-k3s-stability.png | One-hour cluster view; availability does not imply zero restarts or low latency |
| part7-longhorn.png | Three healthy, attached volumes and three RW replicas per volume |
| part7-argocd.png | Application and component history; historical states can differ from current status |
| part7-routing-vrf.png | SERVERS selection with three Established peers; IS-IS/BFD remain unfiltered |
| browser-verification.json | Browser query errors, empty-panel counts and filter selections |
| live-state.json | Current app/node/storage state, folder counts, collection and query checks |
| bgp-counter-query-check.json | Comparison of unchanged raw counters with two increase calculations |

The audit found ten Healthy/Synced Argo Applications, nine Ready nodes, 39
dashboards in the four folders, and fresh SNMP data from 28 devices. Both stores
contained 136 labeled BGP peers: 133 default-context and three SERVERS peers.
The three overview dashboards passed 26 query checks; the routing dashboard
passed 45 across All, default and SERVERS selections.

The screenshot review caught a BGP transition calculation issue. The newly
observed VRF counters were constant at 3, 6 and 3, but `increase` reported those
values as recent increases. The corrected graph uses `increase_prometheus`,
which returned zero for these unchanged series. The [MetricsQL documentation](https://docs.victoriametrics.com/metricsql/#increase_prometheus)
describes this function. Existing raw samples are unchanged; no past events
were removed or rewritten.

The routing screenshot was recaptured after the corrected expression appeared
in Grafana. Newly labeled BGP series begin at the rollout, so the graph does
not recreate earlier VRF history. DNS queries through pfSense returned the
management ingress VIP. Separate authenticated API checks verified certificate
trust, hostname validation and protected API access for Grafana and Argo CD.

This audit did not test a cold boot, datacenter failure, maximum throughput or
external alert delivery. Screenshot time axes show the observed window; they
are not a claim of uninterrupted stability outside it.
