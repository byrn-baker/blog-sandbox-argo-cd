# Application ordering and validation

The root Application loads the manifests in this directory. Longhorn precedes
VictoriaMetrics through their sync-wave annotations. SNMP history follows at
wave 4 (`snmp-metrics`), then its Collector at wave 5 (`otel-snmp`). Flow/syslog,
MetalLB, VictoriaLogs and SuzieQ remain separate future work.

The child-Application health script in ../bootstrap/argocd-values.yaml was
installed through the existing Argo CD Helm bootstrap on 2026-09-12 and checked
in the live argocd-cm. It reports Progressing until a child has health information and
requires both Healthy and Synced for successful health. Degraded child health
is preserved so a failed prerequisite remains visible.

Bootstrap values are outside the root Application's apps path. Committing a
change to that values file alone does not update the running Argo CD installation.
Use the existing pinned argo-cd 10.8.0 chart and lab mirror for the reviewed
bootstrap upgrade. Confirm argocd-cm contains the health script afterward.

The isolated test root validated the following behavior on 2026-09-12:

1. A first child referenced an absent source path. It reported Healthy but
   Unknown sync status, which the customization correctly treated as Progressing.
2. The root waited on that first child; the second child did not exist.
3. Adding the prerequisite source allowed the first child to sync, then the
   second child appeared and synced. All three Applications became Healthy.
4. The test Applications, namespace and source manifests were removed.

This is initial root synchronization ordering. Existing child Applications may
reconcile independently through auto-sync; waves do not serialize their later
updates. Workloads still need their own readiness, retries and dependency checks.
Do not introduce a failure into the live Longhorn Application to test this.

The SNMP canary checked one IOS-XE and one EOS device before full collection.
The Collector obtains credentials from the externally managed
`network-snmp-credentials` Secret. Generation and rotation are documented in
../../blog-sandbox/telemetry/README.md. Generated values and dashboard data must
be changed through that generator.

The separate 547-day SNMP store leaves the existing cluster store's retention
unchanged. Both receive the same SNMP samples over OTLP, allowing existing
alerts and queries while independently budgeting history storage. This is
SNMP-only delivery, not completion of the broader telemetry plan.

## Grafana access from the management network

Open [Network SNMP](http://192.168.3.66:30300/d/network-snmp) and use the
existing Grafana login. The Grafana Service is declared as NodePort 30300 in
../values/victoria-metrics-values.yaml and deployed through Argo CD. No extra
VM or port-forward is required. The client must have a route to 192.168.3.0/24.

On 2026-09-12, checks from the automation host on that subnet passed through
192.168.3.63, 192.168.3.66 and 192.168.3.69: health returned HTTP 200 with the
database healthy, login returned HTTP 200, and the authenticated dashboard API
returned Network SNMP with 16 panels. Unauthenticated dashboard API requests
returned HTTP 401. Access from the user's own computer was not verified.

NodePort also exposes this port on other reachable node addresses; this is
not a management-interface-only binding. The existing Grafana Service port
remains 80 and the container listens on 3000. External traffic uses port 30300.
