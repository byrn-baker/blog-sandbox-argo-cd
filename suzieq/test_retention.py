import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('retention', Path(__file__).parent / 'files/retention.py')
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


class RetentionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.folder = self.root / 'coalesced/device/sqvers=4.0/namespace=lab'
        self.folder.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def block(self, start, shard=0):
        p = self.folder / f'sqc-h1-{shard}-{start}-{start + 3600}.parquet'
        p.write_bytes(b'fixture')
        return p

    def test_baseline_all_shards_and_recent_history_survive(self):
        old = self.block(0)
        baseline = [self.block(3600, 0), self.block(3600, 1)]
        recent = self.block(7200)
        self.assertEqual(retention.candidates(self.root, 7200), [old])
        report = retention.maintain(self.root, days=1, apply=True, now=93600)
        self.assertEqual(report['quarantined'], 1)
        self.assertTrue(all(p.exists() for p in baseline + [recent]))
        self.assertFalse(old.exists())
        saved = self.root / '.retention-quarantine/93600' / old.relative_to(self.root)
        self.assertEqual(saved.read_bytes(), b'fixture')
        saved.rename(old)  # Recovery requires no rewrite of Parquet contents.
        self.assertTrue(old.exists())

    def test_unchanged_old_state_is_kept(self):
        p = self.block(0)
        self.assertEqual(retention.candidates(self.root, 999999), [])
        self.assertTrue(p.exists())

    def test_dry_run_does_not_move_files(self):
        p = self.block(0)
        self.block(3600)
        report = retention.maintain(self.root, days=1, now=93600)
        self.assertEqual(report['eligible'], 1)
        self.assertTrue(p.exists())

    def test_purge_only_after_recovery_grace(self):
        self.block(0)
        self.block(3600)
        retention.maintain(self.root, days=1, apply=True, now=93600)
        self.assertEqual(retention.maintain(self.root, days=1, apply=True, now=93601)['purged'], 0)
        self.assertEqual(retention.maintain(self.root, days=1, apply=True, now=180001)['purged'], 1)

    def test_unrecognized_layout_fails_closed(self):
        self.block(0)
        self.block(3600)
        (self.folder / 'unexpected.parquet').write_bytes(b'fixture')
        with self.assertRaises(ValueError):
            retention.maintain(self.root, days=1, apply=True, now=93600)
        self.assertFalse((self.root / '.retention-quarantine').exists())

    def test_raw_data_is_untouched(self):
        raw = self.root / 'device/raw.parquet'
        raw.parent.mkdir()
        raw.write_bytes(b'raw')
        self.block(0)
        self.block(3600)
        retention.maintain(self.root, days=1, apply=True, now=93600)
        self.assertEqual(raw.read_bytes(), b'raw')


if __name__ == '__main__':
    unittest.main()
