"""Read-only dashboard query checks. Credentials stay in memory.

Requires Grafana port-forward on localhost:13000 and requests.
Prints only panel summaries, never credential values or query response bodies.
"""
import base64
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time

import requests


def session():
    data = json.loads(subprocess.check_output([
        'kubectl', '-n', 'observability', 'get', 'secret',
        'victoria-metrics-k8s-stack-grafana', '-o', 'json',
    ]))['data']
    client = requests.Session()
    client.auth = tuple(base64.b64decode(data[k]).decode()
                        for k in ('admin-user', 'admin-password'))
    return client


def run():
    client = session()
    base = 'http://127.0.0.1:13000'
    dashboard = client.get(base + '/api/dashboards/uid/network-telemetry', timeout=30)
    dashboard.raise_for_status()
    dashboard = dashboard.json()['dashboard']
    labels = client.get(base + '/api/datasources/proxy/uid/network-snmp/api/v1/query',
                        params={'query': 'snmp_device_uptime_ticks{job="snmp"}'}, timeout=30)
    labels.raise_for_status()
    addresses = [r['metric'] for r in labels.json()['data']['result']]
    now = int(time.time() * 1000)
    cutoff = datetime.datetime.fromtimestamp(now / 1000, datetime.timezone.utc).isoformat()
    report = {'checked_at': cutoff, 'panels': []}
    for device, exporter in [('.*', '.*'), ('CE1', '192.168.3.60'), ('DCA-Leaf01', '192.168.3.32'), ('CE2', '192.168.3.61')]:
        for panel in dashboard['panels']:
            if not panel.get('targets'):
                continue
            text = json.dumps(panel['targets'])
            selected = sorted({r['management_ip'] for r in addresses
                               if device == '.*' or r['device'] == device})
            quoted = ','.join(json.dumps(ip) for ip in selected)
            text = text.replace('${exporter:doublequote}', json.dumps(quoted)[1:-1])
            for token, value in [('${device:regex}', device), ('$device', device),
                                 ('${exporter:regex}', exporter), ('$__rate_interval', '5m'),
                                 ('${__to:date:iso}', cutoff)]:
                text = text.replace(token, value)
            queries = json.loads(text)
            for query in queries:
                query['datasource'] = panel['datasource']
                query['intervalMs'] = 60000
                query['maxDataPoints'] = 1000
            result = client.post(base + '/api/ds/query', json={
                'from': str(now - 86400000), 'to': str(now), 'queries': queries,
            }, timeout=90)
            body = result.json()
            errors = [v.get('error') for v in body.get('results', {}).values() if v.get('error')]
            rows = sum(len(f.get('data', {}).get('values', [[]])[0])
                       for v in body.get('results', {}).values() for f in v.get('frames', [])
                       if f.get('data', {}).get('values'))
            expected_empty = (
                (device == 'CE1' and panel['id'] == 11)
                or (device == 'DCA-Leaf01' and panel['id'] == 5)
                or (device == 'CE2' and panel['id'] >= 7)
            )
            if expected_empty and rows:
                errors.append('Unexpected rows outside the known collection scope')
            if not expected_empty and not rows:
                errors.append('Expected data in the last 24 hours, got no rows')
            item = {'device': device, 'panel': panel['title'], 'http': result.status_code,
                    'rows': rows, 'errors': errors}
            report['panels'].append(item)
            print(json.dumps(item), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = run()
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + '\n')
    raise SystemExit(any(p['http'] != 200 or p['errors'] for p in result['panels']))
