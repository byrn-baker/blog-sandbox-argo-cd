# Application ordering and validation

The root Application loads the manifests in this directory. Longhorn precedes
VictoriaMetrics through their sync-wave annotations. Future telemetry Application
names and waves are defined in the sibling blog-sandbox feature plan; they are
not deployed applications yet.

The child-Application health script in ../bootstrap/argocd-values.yaml must be
installed through the existing Argo CD Helm bootstrap before relying on root
sync waves. It reports Progressing until a child has health information and
requires both Healthy and Synced for successful health. Degraded child health
is preserved so a failed prerequisite remains visible.

Bootstrap values are outside the root Application's apps path. Committing a
change to that values file alone does not update the running Argo CD installation.
Use the existing pinned argo-cd 10.8.0 chart and lab mirror for the reviewed
bootstrap upgrade. Confirm argocd-cm contains the health script afterward.

Before adding production dependencies, validate in an isolated test root:

1. Create two disposable child Applications in successive waves, with the first
   deliberately unable to become Healthy.
2. Sync the test root and confirm the later child is not created until the first
   is Healthy and Synced.
3. Repair the first child and verify the later wave proceeds.
4. Remove the disposable test resources and record the observed statuses.

This is initial root synchronization ordering. Existing child Applications may
reconcile independently through auto-sync; waves do not serialize their later
updates. Workloads still need their own readiness, retries and dependency checks.
Do not introduce a failure into the live Longhorn Application to test this.

The 2026-09-09 local validation rendered the pinned chart and verified the script
in the resulting ConfigMap. Lua execution and the live wave test remain pending.
The running cluster also has control-plane and storage blockers documented in
../../blog-sandbox/specs/blog-obs-stack/specs/001-otel-network-telemetry/evidence/2026-09-09-baseline/README.md.
