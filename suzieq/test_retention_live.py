"""Test retention on an isolated copy of canary Parquet data inside its image."""
from pathlib import Path
import subprocess

code = (Path(__file__).parent / 'files/retention.py').read_text()
test = r'''
import json, shutil, tempfile, time, types
from pathlib import Path
import pandas as pd
from suzieq.sqobjects import get_sqobject

module = types.ModuleType('retention_test_module')
exec(SOURCE, module.__dict__)
with tempfile.TemporaryDirectory(prefix='suzieq-retention-test-') as temp:
    root = Path(temp) / 'data'
    shutil.copytree('/data', root, ignore=shutil.ignore_patterns('lost+found', '.retention-quarantine'))
    config = Path(temp) / 'config.yml'
    config.write_text('data-directory: ' + str(root) + '\ntemp-directory: ' + temp + '\n')
    tables = ['device','bgp','interfaces','lldp','routes','sqPoller']
    cutoff = int(time.time()) - 3 * 3600
    end = pd.Timestamp.now(tz='UTC').isoformat()
    start = pd.Timestamp(cutoff, unit='s', tz='UTC').isoformat()
    def read(table, history=False):
        cls = get_sqobject(table)
        obj = cls(config_file=str(config), view='all' if history else 'latest',
                  start_time=start if history else '', end_time=end if history else '')
        frame = obj.get(namespace=['sp-demo-lab'], columns=['*'])
        assert 'error' not in frame.columns, frame.to_string()
        # Order-independent comparison, retaining every field and duplicate row.
        return sorted(json.dumps(r, sort_keys=True) for r in json.loads(frame.to_json(orient='records')))
    before = {(t,h):read(t,h) for t in tables for h in [False,True]}
    full_before = {p.relative_to(root):p.read_bytes() for p in root.rglob('*.parquet')}
    # Accelerate expiry on the COPY only, with a cutoff three hours ago.
    report = module.maintain(root, days=1, apply=True, now=cutoff + 86400)
    assert report['quarantined'] > 0, report
    after = {(t,h):read(t,h) for t in tables for h in [False,True]}
    assert before == after, 'Latest state or retained historical query changed'
    for batch in (root / '.retention-quarantine').iterdir():
        for saved in module.candidates_for_purge(batch):
            target = root / saved.relative_to(batch)
            target.parent.mkdir(parents=True,exist_ok=True)
            assert not target.exists()
            saved.rename(target)
    restored = {p.relative_to(root):p.read_bytes() for p in root.rglob('*.parquet')}
    assert full_before == restored, 'Recovery did not restore identical Parquet files'
    print(json.dumps({'isolated_copy':True, 'queries_compared':len(before),
                      'latest_rows':{t:len(before[t,False]) for t in tables},
                      'quarantined_files':report['quarantined'],
                      'state_and_history_preserved':True, 'byte_identical_restore':True}))
'''.replace('SOURCE', repr(code))
result = subprocess.run(['kubectl','-n','observability','exec','-i','suzieq-0','-c','poller','--','python','-'],
                        input=test, text=True, timeout=180)
raise SystemExit(result.returncode)
