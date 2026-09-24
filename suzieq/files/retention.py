"""Bound coalesced history, preserving a cutoff baseline and all raw data.

Expired blocks move to a one-day recovery quarantine before removal. Only the
pinned hourly coalescer filename/layout is eligible. Unknown files fail closed.
"""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import time
import urllib.request

BLOCK = re.compile(r'^sqc-h1-\d+-(\d+)-(\d+)\.parquet$')
RAW = re.compile(r'^[0-9a-f]{32}-\d+\.parquet$')
TABLES = {'device', 'bgp', 'interfaces', 'lldp', 'routes', 'sqPoller', 'sqCoalescer'}


def candidates(root, cutoff):
    groups = defaultdict(list)
    internal_expired = []
    base = root / 'coalesced'
    for path in base.rglob('*.parquet'):
        relative = path.relative_to(base)
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root.parent):
            raise ValueError('Symlink in coalesced data')
        match = BLOCK.fullmatch(path.name)
        if (len(relative.parts) == 4 and relative.parts[0] == 'sqCoalescer'
                and relative.parts[1].startswith('sqvers=')
                and relative.parts[2].startswith('namespace=') and RAW.fullmatch(path.name)):
            # Internal coalescer statistics are event records, not state snapshots.
            import pyarrow.parquet as pq
            metadata = pq.read_metadata(path)
            column = metadata.schema.names.index('timestamp')
            newest = max(metadata.row_group(i).column(column).statistics.max
                         for i in range(metadata.num_row_groups))
            if newest / 1000 < cutoff:
                internal_expired.append(path)
            continue
        if (not match or len(relative.parts) != 4 or relative.parts[0] not in TABLES
                or not relative.parts[1].startswith('sqvers=')
                or not relative.parts[2].startswith('namespace=')):
            raise ValueError('Unrecognized coalescer layout; cleanup stopped')
        start, end = map(int, match.groups())
        if end - start != 3600:
            raise ValueError('Unexpected coalescer interval')
        groups[path.parent].append((start, end, path))
    expired = []
    for blocks in groups.values():
        old = [b for b in blocks if b[1] <= cutoff]
        if not old:
            continue
        # Retain the full final block before the cutoff, including every shard.
        baseline = max(b[1] for b in old)
        expired.extend(p for _, end, p in old if end < baseline)
    return sorted(expired + internal_expired)


def maintain(root, days=14, grace_hours=24, apply=False, now=None):
    root = Path(root).resolve(strict=True)
    if root == Path('/') or not (root / 'coalesced').is_dir():
        raise ValueError('Expected a SuzieQ data directory with coalesced data')
    if days < 1 or grace_hours < 24:
        raise ValueError('Retention and recovery grace must each be at least one day')
    now = int(time.time() if now is None else now)
    expired = candidates(root, now - days * 86400)
    quarantine = root / '.retention-quarantine'
    if quarantine.is_symlink():
        raise ValueError('Quarantine must not be a symlink')
    moved = removed = 0
    if apply:
        for src in expired:
            dest = quarantine / str(now) / src.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                raise ValueError('Quarantine collision')
            src.rename(dest)
            moved += 1
        if quarantine.exists():
            for batch in quarantine.iterdir():
                if batch.is_symlink() or not batch.name.isdigit() or not batch.is_dir():
                    raise ValueError('Unexpected quarantine entry')
                if now - int(batch.name) < grace_hours * 3600:
                    continue
                # Validate all exact file targets before deleting this batch.
                files = candidates_for_purge(batch)
                for path in files:
                    path.unlink()
                    removed += 1
                for directory in sorted(batch.rglob('*'), key=lambda p: len(p.parts), reverse=True):
                    if directory.is_dir():
                        directory.rmdir()
                batch.rmdir()
    return {'eligible': len(expired), 'quarantined': moved, 'purged': removed,
            'apply': apply, 'cutoff': now - days * 86400}


def candidates_for_purge(batch):
    files = []
    for path in batch.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in quarantine')
        if path.is_file():
            rel = path.relative_to(batch)
            if (len(rel.parts) != 5 or rel.parts[0] != 'coalesced'
                    or rel.parts[1] not in TABLES or not rel.parts[2].startswith('sqvers=')
                    or not rel.parts[3].startswith('namespace=')
                    or not (BLOCK.fullmatch(path.name)
                            or (rel.parts[1] == 'sqCoalescer' and RAW.fullmatch(path.name)))):
                raise ValueError('Unknown quarantine file')
            files.append(path)
    return files


def measurements(root):
    active = quarantine = count = 0
    for path in root.rglob('*.parquet'):
        if path.is_symlink():
            continue
        try:
            size = path.stat().st_size
        except FileNotFoundError:  # Coalescer can replace raw blocks during scan.
            continue
        if '.retention-quarantine' in path.relative_to(root).parts:
            quarantine += size
        else:
            active += size
            count += 1
    disk = os.statvfs(root)
    poll_blocks = [int(m.group(2)) for p in (root / 'coalesced/sqPoller').rglob('*.parquet')
                   if (m := BLOCK.fullmatch(p.name))]
    return {'suzieq_storage_active_bytes':active, 'suzieq_storage_quarantine_bytes':quarantine,
            'suzieq_storage_files':count, 'suzieq_storage_available_bytes':disk.f_bavail * disk.f_frsize,
            'suzieq_storage_capacity_bytes':disk.f_blocks * disk.f_frsize,
            'suzieq_coalescer_latest_block_end_seconds':max(poll_blocks, default=0)}


def publish(values, endpoint):
    point_time = str(time.time_ns())
    body = {'resourceMetrics':[{'resource':{'attributes':[
        {'key':'service.name','value':{'stringValue':'suzieq-retention'}}]},
        'scopeMetrics':[{'scope':{'name':'lab.suzieq.storage'}, 'metrics':[
            {'name':name, 'gauge':{'dataPoints':[{'timeUnixNano':point_time,'asDouble':value}]}}
            for name, value in values.items()]}]}]}
    request = urllib.request.Request(endpoint, data=json.dumps(body).encode(),
                                     headers={'Content-Type':'application/json'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                response.read()
            return
        except Exception:
            if attempt == 2:
                print(json.dumps({'event':'storage_metrics_batch_discarded','attempts':3}),flush=True)
            else:
                time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/data')
    parser.add_argument('--days', type=int, default=14)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--endpoint', default='http://snmp-metrics.observability.svc:8428/opentelemetry/v1/metrics')
    args = parser.parse_args()
    root = Path(args.root)
    last_run = last_success = failures = 0
    while True:
        if time.time() - last_run >= 3600:
            last_run = time.time()
            try:
                result = maintain(root, days=args.days, apply=args.apply)
                last_success = time.time()
                print(json.dumps({'event':'retention_check',**result}),flush=True)
            except Exception as exc:
                failures += 1
                print(json.dumps({'event':'retention_failed','error_type':type(exc).__name__}),flush=True)
        values = measurements(root)
        values.update(suzieq_retention_last_success_timestamp_seconds=last_success,
                      suzieq_retention_failures=failures, suzieq_retention_enabled=int(args.apply))
        publish(values, args.endpoint)
        if args.once:
            break
        time.sleep(60)


if __name__ == '__main__':
    main()
