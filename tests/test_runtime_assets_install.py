"""Migration preserves overrides and supplies an independently readable backup."""
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from pack_runtime_assets import pack, verify
from install_runtime_assets import install


class RuntimeAssetInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'runtime'
        self.root.mkdir()
        (self.root / 'CupLogos').mkdir()
        (self.root / 'CupLogos/a.png').write_bytes(b'logo')
        (self.root / 'Commentary').mkdir()
        (self.root / 'Commentary/indonesia.nxcp').write_bytes(b'accepted sound')
        self.archive = self.base / 'new.assets'
        pack(self.root, self.archive)
        self.backup = self.base / 'backup'

    def test_archive_only_install_preserves_sound_and_backup(self):
        (self.root / 'save.dat').write_bytes(b'save untouched')
        result = install(self.root, self.archive, self.backup)
        self.assertEqual(result['retired_files'], 2)
        self.assertFalse((self.root / 'CupLogos').exists())
        self.assertFalse((self.root / 'Commentary').exists())
        self.assertEqual((self.root / 'save.dat').read_bytes(), b'save untouched')
        self.assertEqual(verify(self.root / 'FootballNX.assets'), verify(self.archive))
        with zipfile.ZipFile(result['backup']) as backup:
            self.assertEqual(backup.read('Commentary/indonesia.nxcp'), b'accepted sound')
            self.assertEqual(backup.read('CupLogos/a.png'), b'logo')

    def test_custom_loose_asset_blocks_before_replacing_anything(self):
        old = self.root / 'FootballNX.assets'
        old.write_bytes(b'older archive')
        (self.root / 'CupLogos/a.png').write_bytes(b'my override')
        with self.assertRaisesRegex(ValueError, 'repack'):
            install(self.root, self.archive, self.backup)
        self.assertEqual(old.read_bytes(), b'older archive')
        self.assertEqual((self.root / 'CupLogos/a.png').read_bytes(), b'my override')
        self.assertFalse(self.backup.exists())

    def test_check_is_read_only_and_backup_cannot_stay_in_runtime(self):
        report = install(self.root, self.archive, self.backup, True)
        self.assertTrue(report['check_only'])
        self.assertTrue((self.root / 'CupLogos/a.png').is_file())
        self.assertFalse(self.backup.exists())
        with self.assertRaisesRegex(ValueError, 'outside'):
            install(self.root, self.archive, self.root / 'backup')
