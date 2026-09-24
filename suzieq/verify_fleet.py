"""Read-only API checks against the generated inventory and live Nautobot names."""
import argparse
import base64
import datetime
import json
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request

import yaml

sys.path.insert(0, '/home/ubuntu/blog-sandbox/telemetry')
import canary_control as control
import generate_suzieq as generator


def check():
    manifest = yaml.safe_load((Path(__file__).parent / 'generated-values.yaml').read_text())
    addresses = {host['url'].removeprefix('ssh://') for source in manifest['inventory']['sources'] for host in source['hosts']}
    devices = generator.fleet(control.api('graphql/', {'query': (generator.ROOT / 'queries/network_fleet.gql').read_text()}))
    expected = {d['name'] for d in devices if d['address'] in addresses}
    assert len(expected) == len(addresses), 'Generated inventory does not match Nautobot'
    secret = json.loads(subprocess.check_output(['kubectl','-n','observability','get','secret','suzieq-credentials','-o','json']))
    key = base64.b64decode(secret['data']['API_KEY']).decode()
    result = {'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'expected_devices':sorted(expected), 'tables':{}}
    for table in ['device','bgp','interface','lldp','route','sqPoller']:
        url = 'http://127.0.0.1:18000/api/v2/' + table + '/show?' + urllib.parse.urlencode({'namespace':'sp-demo-lab'})
        request = urllib.request.Request(url,headers={'access_token':key})
        with urllib.request.urlopen(request,timeout=60) as response:
            rows = json.load(response)
        assert isinstance(rows,list), table
        counts = {name:sum(r['hostname'] == name for r in rows) for name in sorted(expected)}
        assert {r['hostname'] for r in rows} <= expected, table + ' has unexpected hosts'
        result['tables'][table] = {'rows':len(rows), 'by_device':counts}
        if table in ['device','interface','route']:
            assert all(counts.values()), (table,counts)
        if table == 'sqPoller':
            required = {'device','bgp','interfaces','lldp','routes'}
            bad = [{'hostname':r['hostname'],'service':r['service'],'status':r.get('statusStr'),
                    'timestamp':r.get('timestamp')} for r in rows if r.get('statusStr') != 'OK']
            result['poller_errors'] = bad
            assert not bad, bad
            for host in expected:
                assert {r['service'] for r in rows if r['hostname'] == host} == required, host
            result['poller_timestamps'] = {host:max(r['timestamp'] for r in rows if r['hostname']==host)
                                           for host in sorted(expected)}
    print(json.dumps(result),flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report',type=Path)
    args = parser.parse_args()
    result = check()
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2)+'\n')
