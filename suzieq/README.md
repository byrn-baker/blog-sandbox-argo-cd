# SuzieQ network state

This local chart runs the pinned SuzieQ 0.25.0 poller and REST API in one pod,
sharing a Longhorn-backed Parquet volume. `generated-values.yaml` is produced
from Nautobot by `blog-sandbox/telemetry/generate_suzieq.py`. It contains no
credential values. The externally managed `suzieq-credentials` Secret resolves
the existing Cisco and Arista SSH Secrets Groups and supplies the REST API key.

The inventory is generated from Nautobot for staged expansion to 28 network
devices. The poller is read-only and runs one worker at a 60-second cadence,
collecting device facts, BGP, interfaces, LLDP and routes. Inventory checksums
trigger a declared rollout when the device list changes.

## History, recovery and growth

Open-source SuzieQ does not implement data expiry. The lab retention sidecar
implements a 14-day window for coalesced history, with one additional baseline
block per table/schema/namespace before the cutoff. Keeping that full block,
including every shard, preserves unchanged state with older row timestamps.
The native hourly coalescer carries unchanged records into subsequent blocks.
Raw, not-yet-coalesced state is never removed by this policy.

Expired blocks move to `/data/.retention-quarantine` for 24 hours before being
purged. They no longer appear in queries but can be recovered during that grace
period by moving the exact file back to its relative `coalesced/` path. Restore
only into an absent target, never overwrite a newer block. This protects against
a mistaken expiry decision, not loss of the PVC. Maintain a separate volume
backup for disaster recovery. A pre-fleet copy of the table directories was
exported to the automation host outside Git. Writers were not quiesced, so that
copy is not a transactional snapshot. Recurring off-volume backups remain
separate operational work.

The cleaner accepts only the pinned hourly coalescer layout. Unknown formats
stop cleanup. Internal sqCoalescer statistics use their Parquet timestamps for
expiry; they are events, not state snapshots. Revalidate the cleaner before
upgrading SuzieQ or changing coalescer periods. Old baseline state can remain
longer than 14 days, intentionally. Queries before the supported window are not
a complete historical record.

`test_retention.py` checks baseline/shard preservation, dry-run behavior, recovery
grace, unknown-layout rejection, and raw-data preservation. Run
`test_retention_live.py` against the canary before expansion: it copies data to an
isolated temporary directory, accelerates expiry on that copy, compares latest
and retained-history queries for all six tables, then verifies byte-identical
restoration. It does not delete production history.

The 5 GiB PVC remains in place. The initial two-device dataset used about 2.2 MiB
of Parquet data over 7.7 hours. Linear extrapolation to 28 devices and 14 days is
about 1.3 GiB, but route scale and change frequency differ by device. This is a
starting estimate, not a measured fleet retention guarantee.

Every minute the sidecar exports active/quarantine bytes, file count, filesystem
capacity/free space, retention status and coalescer age as OTLP protobuf metrics.
The network store retains these with the other long-term network metrics; the
cluster store supplies alert evaluation. Rules warn on less than 30 percent free
space, a seven-day growth projection above 80 percent capacity, stale retention,
and stalled coalescing. Delivery retries three times and logs discarded batches.
