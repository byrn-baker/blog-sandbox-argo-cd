# Part 8 flow and syslog canary

This chart runs one Collector on dcb-k3s-w1 and advertises 192.168.3.241 through
MetalLB on that worker's eth0. It is deliberately pinned for the two-device
experiment; worker failure interrupts this endpoint. The separate VictoriaLogs
Application provides 14-day configured storage on Longhorn.

Sources and device configurations live in the sibling blog-sandbox repository.
See `telemetry/evidence/part8-canary/README.md` there for results and limits.
The only enabled network exporters are CE1 and DCA-Leaf01.

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
