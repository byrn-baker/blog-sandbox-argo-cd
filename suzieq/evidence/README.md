# SuzieQ canary, September 23, 2026

The root Application deployed SuzieQ 0.25.0 from image digest
`sha256:51e9615a9245e118b5f5f2b13043913a59f1f52e42cf1265c29ad12b1bd5ab4e`.
The generated inventory selected CE1 and DCA-Leaf01 as the IOS-XE and EOS
canaries. The inventory contains environment-variable references only; the
externally managed `suzieq-credentials` Secret resolves the existing Nautobot
SSH credential authorities and owns the REST API key.

The initial pod exposed two runtime requirements that inventory syntax checking
does not test. The image writes default logs under `/tmp`, and its REST process
requires a writable data directory during startup. Commit `efcd9c8` added an
ephemeral writable `/tmp` and a shared writable Parquet PVC mount while keeping
the image root filesystems read-only. The failed pod was deleted after the new
StatefulSet revision was applied; its Longhorn PVC was retained.

The corrected pod reached 2/2 Ready with zero restarts. The REST API returned:

| Table | Rows | Canaries represented |
|---|---:|---|
| device | 2 | CE1, DCA-Leaf01 |
| bgp | 18 | CE1, DCA-Leaf01 |
| interface | 33 | CE1, DCA-Leaf01 |
| lldp | 2 | DCA-Leaf01 |
| route | 182 | CE1, DCA-Leaf01 |

The `sqPoller` table reported `OK` for all five requested services on both
devices. CE1's successful LLDP poll returned no neighbor rows; this is an empty
result, not an authentication or parser failure. EOS and IOS-XE were detected
automatically over SSH.

The 5 GiB Longhorn volume was healthy with three replicas. The root and SuzieQ
Applications finished Healthy and Synced at commit `64bcde0`. A narrow Argo
ignore rule excludes only the server-populated status nested inside the
StatefulSet PVC template.

Fleet expansion remains gated. Open-source SuzieQ 0.25.0 does not implement
data expiry, so a finite PVC is a capacity bound rather than a retention policy.
Measure canary growth and test a supported backup/cleanup procedure before
generating the 28-device inventory. Grafana Infinity and the OTLP state bridge
are not part of this canary.
