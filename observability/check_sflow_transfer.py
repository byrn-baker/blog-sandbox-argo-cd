"""Verify the named transfer through Grafana's query API and browser.

Usage: python check_sflow_transfer.py TRANSFER_REPORT EVIDENCE_DIRECTORY
Requires local Grafana port-forward, requests and Playwright.
"""
import datetime
import json
import os
from pathlib import Path
import sys
import urllib.parse

from playwright.sync_api import sync_playwright
from verify_network_telemetry import session


def main():
    transfer=json.loads(Path(sys.argv[1]).read_text())
    dest=Path(sys.argv[2]); dest.mkdir(parents=True,exist_ok=True)
    start=int(datetime.datetime.fromisoformat(transfer['started_at']).timestamp()*1000)-5000
    end=int(datetime.datetime.fromisoformat(transfer['ended_at']).timestamp()*1000)+60000
    port=str(transfer['destination_port'])
    client=session(); base='http://127.0.0.1:13000'
    dash=client.get(base+'/api/dashboards/uid/network-telemetry',timeout=30)
    dash.raise_for_status()
    panel=next(p for p in dash.json()['dashboard']['panels'] if p['id']==18)
    query=dict(panel['targets'][0])
    # All EOS exporter addresses resolved by the dashboard's SNMP inventory.
    labels=client.get(base+'/api/datasources/proxy/uid/network-snmp/api/v1/query',
                     params={'query':'snmp_device_uptime_ticks{job="snmp"}'},timeout=30)
    labels.raise_for_status()
    ips=sorted({r['metric']['management_ip'] for r in labels.json()['data']['result']})
    query['expr']=query['expr'].replace('${exporter:doublequote}',','.join(json.dumps(ip) for ip in ips))
    query['expr']=query['expr'].replace('${flow_port:doublequote}',json.dumps('^'+port+'$'))
    query.update(datasource=panel['datasource'],intervalMs=60000,maxDataPoints=1000)
    result=client.post(base+'/api/ds/query',json={'from':str(start),'to':str(end),'queries':[query]},timeout=90)
    result.raise_for_status(); body=result.json()
    assert not any(v.get('error') for v in body['results'].values()),'Grafana query error'
    encoded=json.dumps(body)
    for expected in [transfer['source_device'],transfer['destination_device'],transfer['source_address'],
                     transfer['destination_address'],port,'nautobot.exporter.label']:
        assert expected in encoded,expected
    (dest/'grafana-transfer-query.json').write_text(json.dumps(body,indent=2)+'\n')
    url='/d/network-telemetry?'+urllib.parse.urlencode({'from':start,'to':end,'refresh':'',
                                                     'var-device':'$__all','var-flow_port':'^'+port+'$'})
    errors=[]
    named_responses=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH'))
        page=browser.new_page(viewport={'width':1900,'height':1100})
        page.on('pageerror',lambda e:errors.append(str(e)))
        def response(r):
            if '/api/ds/query' in r.url:
                try:
                    data=r.json()
                    encoded=json.dumps(data)
                    if transfer['source_device'] in encoded and transfer['destination_device'] in encoded:
                        named_responses.append(True)
                    if r.status>=400 or any(v.get('error') for v in data.get('results',{}).values()):
                        errors.extend(v['error'] for v in data.get('results',{}).values() if v.get('error'))
                        print(json.dumps({'failed_query_expressions':[q.get('expr') for q in r.request.post_data_json.get('queries',[])]}),flush=True)
                except Exception: errors.append('Could not inspect datasource response')
        page.on('response',response)
        page.goto(base+'/login')
        page.locator('input[name="user"]').fill(client.auth[0])
        page.locator('input[name="password"]').fill(client.auth[1])
        page.get_by_role('button',name='Log in',exact=True).click()
        page.wait_for_url(lambda u:'/login' not in u,timeout=60000)
        page.goto(base+url)
        page.get_by_text(panel['title'],exact=True).evaluate("el=>el.scrollIntoView({block:'start'})")
        # Grafana's canvas table cells are not DOM text locators. Check the
        # browser's actual query response, then inspect the saved rendering.
        page.wait_for_timeout(15000)
        page.screenshot(path=str(dest/'named-sflow-transfer.png'))
        print(json.dumps({'browser_query_errors':errors,'named_responses':len(named_responses)}),flush=True)
        assert not errors,errors
        assert named_responses,'Browser did not receive the named transfer'
        browser.close()
    report={'passed':True,'query_errors':errors,'dashboard_url':'https://grafana.sandbox.lab'+url,
            'source':transfer['source_device'],'destination':transfer['destination_device'],'port':port}
    (dest/'browser-transfer.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__': main()
