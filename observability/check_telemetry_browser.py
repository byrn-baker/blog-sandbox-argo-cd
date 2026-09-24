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
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.goto('http://127.0.0.1:13000/login')
        page.locator('input[name="user"]').fill(client.auth[0])
        page.locator('input[name="password"]').fill(client.auth[1])
        page.get_by_role('button', name='Log in', exact=True).click()
        page.wait_for_url(lambda url: '/login' not in url, timeout=60000)
        for device in ['All', 'CE1', 'DCA-Leaf01', 'CE2']:
            value = '$__all' if device == 'All' else device
            page.goto('http://127.0.0.1:13000/d/network-telemetry?from=now-24h&to=now&var-device=' + value)
            page.get_by_text('How to read this dashboard', exact=True).wait_for(timeout=60000)
            page.wait_for_timeout(12000)
            page.screenshot(path=str(dest / (device + '-traffic.png')))
            page.get_by_text('Flow record detail', exact=True).evaluate(
                "el => el.scrollIntoView({block: 'start'})")
            page.wait_for_timeout(8000)
            page.screenshot(path=str(dest / (device + '-flows.png')))
            page.get_by_text('Installed routes', exact=True).evaluate(
                "el => el.scrollIntoView({block: 'start'})")
            page.wait_for_timeout(8000)
            page.screenshot(path=str(dest / (device + '-state.png')))
            print(json.dumps({'device': device, 'page_errors': errors,
                              'has_dashboard': 'Network Telemetry' in page.title()}), flush=True)
        browser.close()


if __name__ == '__main__':
    run()
