# SuzieQ network state

This local chart runs the pinned SuzieQ 0.25.0 poller and REST API in one pod,
sharing a Longhorn-backed Parquet volume. `generated-values.yaml` is produced
from Nautobot by `blog-sandbox/telemetry/generate_suzieq.py`. It contains no
credential values. The externally managed `suzieq-credentials` Secret resolves
the existing Cisco and Arista SSH Secrets Groups and supplies the REST API key.

The initial generated inventory is a two-platform canary. Expand it to all 28
network devices only after two successful poll cycles show BGP, interfaces,
LLDP and routes for both platforms. The poller is read-only and runs one worker
at a 60-second cadence.

Open-source SuzieQ does not implement data expiry. The 5 GiB PVC is a canary
capacity bound, not a retention mechanism. Measure growth and test a supported
backup/cleanup procedure before fleet expansion. Do not claim T009 or T033
complete until that gate is resolved.
