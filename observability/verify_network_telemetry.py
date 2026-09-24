"""Read-only dashboard query checks. Credentials stay in memory.

Requires Grafana port-forward on localhost:13000 and requests.
Prints only panel summaries, never credential values or query response bodies.
"""
import base64
import copy
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
    now = int(time.time() * 1000)
    cutoff = datetime.datetime.fromtimestamp(now / 1000, datetime.timezone.utc).isoformat()
    report = {'checked_at': cutoff, 'panels': []}
    for device, exporter in [('.*', '.*'), ('CE1', '192.168.3.60'), ('DCA-Leaf01', '192.168.3.32'), ('CE2', '192.168.3.61')]:
        for panel in dashboard['panels']:
            if not panel.get('targets'):
                continue
            text = json.dumps(panel['targets'])
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
            item = {'device': device, 'panel': panel['title'], 'http': result.status_code,
                    'rows': rows, 'errors': errors}
            report['panels'].append(item)
            print(json.dumps(item), flush=True)
    return report


if __name__ == '__main__':
    result = run()
    raise SystemExit(any(p['http'] != 200 or p['errors'] for p in result['panels']))
