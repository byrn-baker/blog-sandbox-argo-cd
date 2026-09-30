# Part 8 flow and syslog canary

This chart runs one Collector on dcb-k3s-w1 and advertises 192.168.3.241 through
MetalLB on that worker's eth0. It remains pinned to that worker;
worker failure interrupts this endpoint. The separate VictoriaLogs
Application provides 14-day configured storage on Longhorn.

Sources and device configurations live in the sibling blog-sandbox repository.
See `telemetry/evidence/part8-canary/README.md` there for results and limits.
All 13 IOS-XE routers export NetFlow and all 15 EOS switches export sFlow.
Syslog also covers all 28 devices. The chart name retains its canary history.

## Nautobot ownership enrichment

`generated-enrichment.yaml` comes from the sibling repository's
`telemetry/generate_flow_enrichment.py` and `queries/flow_enrichment.gql`.
It uses device/interface address assignments, including the ten servers, to
add source, destination and exporter ownership labels before storage. It does
not replace original flow fields or infer an inner endpoint from a tunnel IP.
The named interface is the address assignment, not the observation's ingress port.

Exact assigned addresses resolve; shared addresses list every owner. Namespace
collisions remain ambiguous because these decoded records lack VRF context.
Unknown IPs stay unknown, with their original addresses preserved. No external
IP intelligence service or per-record Nautobot API request is involved.

Regenerate when IP ownership changes, review the diff, validate with the pinned
Collector, then deploy through Argo:

```sh
cd /home/ubuntu/blog-sandbox
python3 telemetry/generate_flow_enrichment.py \
  --output ../blog-sandbox-argo-cd/telemetry-canary/generated-enrichment.yaml \
  --snapshot /path/to/reviewed-nautobot-snapshot.json
python3 -m unittest discover -s telemetry -p test_flow_enrichment.py
python3 telemetry/test_flow_enrichment_live.py
```

The generator uses the operator host's existing Nautobot credential helper,
but generated output contains no credentials. Failed/empty queries preserve
the previous files. The inventory content hash and generation time accompany
new flow records. Older logs are not backfilled. This is a reviewed snapshot,
not an automatically refreshed or historical inventory service. A snapshot
can become stale without stopping collection; refresh is part of inventory
change handling. Both shared and ambiguous cases are tested before rollout.

The enrichment checksum causes a declared Collector rollout on update. Its
restart has the same UDP and NetFlow-template-cache gaps described below.

Change `values.yaml` configRevision whenever changing the embedded Collector
configuration, so Argo rolls the Deployment. Validate with the pinned binary
before pushing. This canary uses bounded memory queues and can lose records
during restarts, backend outages or UDP loss. A restart also loses NetFlow v9
templates until exporters refresh them. No high-availability claim is made.

The PostSync hook must observe new test records from both networks. After each
sync starts the hook, run `telemetry/canary_probe.py` from blog-sandbox locally
with `--bind 192.168.3.21 --label management --vip 192.168.3.241`, and on a lab
VM with its bond0 IP and `--label lab`. The hook is bounded to ten minutes and
fails rather than treating an assigned VIP as proof of delivery.

The syslog receiver retains the original vendor message and decodes PRI;
`net.peer.ip` identifies the UDP sender. Message timestamps are ingestion time.
NetFlow/sFlow records expose the pinned receiver's normalized projection, not
all original wire fields. In particular, this canary does not yet expose VNI.
