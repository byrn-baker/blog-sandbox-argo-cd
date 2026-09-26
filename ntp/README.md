# Lab NTP

The `ntp` Argo CD Application is discovered by `root-app` from
`apps/16-ntp.yaml`. Kustomize generates the Chrony ConfigMap and changes its
name when configuration changes, which triggers a Deployment rollout.

| Client path | NTP address | MetalLB interface |
| --- | --- | --- |
| Management | `192.168.3.242:123/UDP` | `eth0` |
| Lab fabric | `10.100.0.241:123/UDP` | `bond0` |

These are two addresses for the same single replica, not independent time
sources. Both Services preserve client source addresses with
`externalTrafficPolicy: Local`. MetalLB announces each address from the worker
hosting the ready pod. The Services forward UDP 123 to container port 1123.
No HTTP ingress or DNS record is required.

`../blog-sandbox/service_endpoints.yml` (relative to the repository root)
declares the same addresses. The Git-sourced Nautobot job `NTP VIP Reservations`
in `jobs/ntp_reservation/` reserves them in Global IPAM without assigning them to
device interfaces. Keep these addresses outside DHCP allocation ranges.

Chrony uses the existing gateway at `192.168.3.1` as its upstream. This gateway
was verified to serve synchronized NTP before deployment. It is currently the
only upstream, so this service does not add independent time-source redundancy.
PVE and K3s hosts should retain independent time synchronization to avoid a
dependency on this cluster service.

The container image is pinned by digest and contains Chrony 4.6.1. Its default
startup script is bypassed so `chrony.conf` owns all settings. Chrony runs as
UID 100 with all capabilities dropped, a read-only root filesystem, and no
service-account token. `-x` prevents host clock adjustments; `-U` permits the
non-root startup. Writable runtime and drift data are ephemeral.

Only `192.168.3.0/24` and `10.0.0.0/8` clients are allowed. Remote Chrony command
access is disabled. Readiness requires synchronization; liveness checks that
the daemon responds locally. There is no local-stratum fallback that would
claim synchronization without an upstream. The single replica has a service
gap during restarts and cluster outages.

Inspect the service:

```sh
kubectl -n argocd get applications root-app ntp
kubectl -n ntp get pods,services -o wide
kubectl -n ntp exec deployment/chrony -- /usr/bin/chronyc tracking
kubectl -n ntp exec deployment/chrony -- /usr/bin/chronyc -n sources -v
kubectl -n ntp exec deployment/chrony -- /usr/bin/chronyc -n clients
python3 ntp/query_ntp.py 192.168.3.242
```

`query_ntp.py` only queries NTP. It does not set the client clock. Run it from a
lab host against `10.100.0.241` to check the fabric path. It verifies the server
mode, request correlation, synchronization flag, stratum, and timestamp fields.
Reported offset is relative to the querying host, not proof of absolute accuracy.

Network-device NTP settings must be introduced through Git-managed Nautobot
contexts and templates, validated, then rendered with Golden Config. Fresh
backups, compliance, and Config Plans precede a separately approved router and
switch deployment.

## Deployment verification, 2026-09-26

Argo CD deployed the service from commit `66efa67`. The `ntp` and `root-app`
Applications reached Healthy/Synced, as did all other existing Applications.
The pod started on `dcc-k3s-w6`, became ready after selecting `192.168.3.1`,
and reported stratum 4 with Normal leap status. Its logs confirmed that system
clock control was disabled.

Validated NTP replies were received over these paths at approximately 18:52 UTC:

| Client | Endpoint | Stratum | Sample round-trip delay |
| --- | --- | --- | --- |
| Automation host, `192.168.3.21` | `192.168.3.242` | 4 | 0.382 ms |
| DCA, `10.100.0.10` | `10.100.0.241` | 4 | 181.213 ms |
| DCB, `10.100.0.20` | `10.100.0.241` | 4 | 196.202 ms |
| DCC, `10.100.0.30` | `10.100.0.241` | 4 | 4.243 ms |

These are individual samples, not an accuracy benchmark. The longer fabric
paths can limit NTP accuracy, particularly when latency is asymmetric.
Chrony's live access checks allowed both configured client networks and denied
`203.0.113.1`. No routers, switches, PVE hosts, or K3s host time settings were
changed. Device synchronization, pod failover, and upstream failure recovery
were not tested.

The source repository reservation commit is `611839c`. Nautobot source sync,
reservation dry-run, and reservation execution all completed with SUCCESS.
The reservation execution JobResult is `713770f2-5b5a-4ce4-9b4e-1efee6b69e91`.

References: [container source](https://github.com/cturra/docker-ntp),
[Chrony options](https://chrony-project.org/doc/4.6/chronyd.html), and
[MetalLB Services](https://metallb.io/usage/).
