"""Render the dashboard using an existing local Grafana port-forward.

Run with Playwright installed. Screenshot destination is a command-line path.
Credentials stay in memory and are never written to evidence.
"""
import json
import os
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

from verify_network_telemetry import session


def run():
    client = session()
    dest = Path(sys.argv[1])
    dest.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=
            os.environ.get('CHROMIUM_PATH'))
        page = browser.new_page(viewport={'width': 1600, 'height': 1100})
        errors = []
        query_errors = []
        reports = []
        page.on('pageerror', lambda err: errors.append(str(err)))
        def check_response(response):
            if '/api/ds/query' not in response.url:
                return
            try:
                body = response.json()
                for result in body.get('results', {}).values():
                    if result.get('error'):
                        query_errors.append(result['error'])
                if response.status >= 400 and not body.get('results'):
                    query_errors.append('Query HTTP ' + str(response.status))
            except Exception as exc:
                query_errors.append(type(exc).__name__ + ' reading query response')
        page.on('response', check_response)
        page.goto('http://127.0.0.1:13000/login')
        page.locator('input[name="user"]').fill(client.auth[0])
        page.locator('input[name="password"]').fill(client.auth[1])
        page.get_by_role('button', name='Log in', exact=True).click()
        page.wait_for_url(lambda url: '/login' not in url, timeout=60000)
        for device in ['All', 'CE1', 'DCA-Leaf01', 'CE2']:
            errors.clear()
            query_errors.clear()
            value = '$__all' if device == 'All' else device
            page.goto('http://127.0.0.1:13000/d/network-telemetry?from=now-24h&to=now&refresh=&var-device=' + value)
            page.get_by_text('How to read this dashboard', exact=True).wait_for(timeout=60000)
            page.wait_for_timeout(12000)
            page.wait_for_load_state('networkidle', timeout=90000)
            page.screenshot(path=str(dest / (device + '-traffic.png')))
            page.get_by_text('NetFlow conversations: observed bytes and packets', exact=True).evaluate(
                "el => el.scrollIntoView({block: 'start'})")
            page.wait_for_timeout(2000)
            page.wait_for_load_state('networkidle', timeout=90000)
            page.screenshot(path=str(dest / (device + '-conversations.png')))
            page.get_by_text('Flow record detail', exact=True).evaluate(
                "el => el.scrollIntoView({block: 'start'})")
            page.wait_for_timeout(8000)
            page.wait_for_load_state('networkidle', timeout=90000)
            page.screenshot(path=str(dest / (device + '-flows.png')))
            page.get_by_text('Installed routes', exact=True).evaluate(
                "el => el.scrollIntoView({block: 'start'})")
            page.wait_for_timeout(8000)
            page.wait_for_load_state('networkidle', timeout=90000)
            page.screenshot(path=str(dest / (device + '-state.png')))
            page.get_by_text('SuzieQ volume used (fleet)', exact=True).evaluate(
                "el => el.scrollIntoView({block: 'start'})")
            page.wait_for_timeout(3000)
            page.wait_for_load_state('networkidle', timeout=90000)
            page.screenshot(path=str(dest / (device + '-storage.png')))
            report = {'device': device, 'page_errors': list(errors),
                      'query_errors': list(query_errors),
                      'has_dashboard': 'Network Telemetry' in page.title()}
            reports.append(report)
            print(json.dumps(report), flush=True)
        browser.close()
        (dest / 'browser-checks.json').write_text(json.dumps(reports, indent=2) + '\n')
        if any(r['page_errors'] or r['query_errors'] or not r['has_dashboard'] for r in reports):
            raise SystemExit(1)


if __name__ == '__main__':
    run()
