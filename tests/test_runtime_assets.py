"""Exercise the production C archive reader with the Python packer's output."""
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from pack_runtime_assets import collect, pack, verify


class RuntimeAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which('gcc')
        if not cc:
            raise unittest.SkipTest('host C compiler unavailable')
        cls.temp = tempfile.TemporaryDirectory(prefix='pesnx-assets-test-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name)
        cls.exe = cls.folder / 'read.exe'
        source = cls.folder / 'read.c'
        source.write_text('''#include "runtime_assets.h"
int main(int argc,char **argv){
 if(argc!=5)return 2;
 size_t n=777,cap=(size_t)strtoull(argv[3],NULL,10);
 void *p=atoi(argv[4])?nx_asset_read(argv[2],cap,&n):
   nx_asset_read_archive(argv[1],argv[2],cap,&n);
 if(!p)return n?4:3;
 int ok=fwrite(p,1,n,stdout)==n;
 free(p);return ok?0:5;
}''')
        subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-I',
                        str(ROOT / 'source'), str(source), '-o', str(cls.exe)], check=True)

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(dir=self.folder)
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.payloads = {'CupLogos/a.png': b'cup-logo\x00\xff',
                         'LeagueLogos/z.png': b'league-logo' * 17,
                         'Commentary/indonesia.nxcp': b'delta-audio' * 100,
                         'Animations/referee.nxra': b'synthetic-motion' * 100}
        for name, data in self.payloads.items():
            p = self.root / name
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(data)
        self.archive = self.root / 'FootballNX.assets'
        pack(self.root, self.archive)

    def read(self, name, cap=2000000, loose=False):
        return subprocess.run([str(self.exe), str(self.archive), name, str(cap),
                               str(int(loose))], cwd=self.root, capture_output=True)

    def test_deterministic_archive_and_binary_search(self):
        baseline = self.archive.read_bytes()
        report = pack(self.root, self.archive)
        self.assertEqual(baseline, self.archive.read_bytes())
        self.assertEqual(len(report['entries']), 4)
        for name, data in self.payloads.items():
            for spelling in (name, name.lower(), name.upper()):
                with self.subTest(name=spelling):
                    result = self.read(spelling)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, data)
        self.assertEqual(self.read('CupLogos/missing.png').returncode, 3)
        self.assertEqual(self.read('CupLogos/a.png', 2).returncode, 3)

    def test_loose_override_and_archive_only_install(self):
        path = self.root / 'CupLogos/a.png'
        path.write_bytes(b'override')
        self.assertEqual(self.read('CupLogos/a.png', loose=True).stdout, b'override')
        path.write_bytes(b'')
        self.assertEqual(self.read('CupLogos/a.png', loose=True).returncode, 3)
        for name in self.payloads:
            (self.root / name).unlink()
        for name, data in self.payloads.items():
            self.assertEqual(self.read(name, loose=True).stdout, data)

    def test_rejects_traversal_and_bad_archive_metadata(self):
        for name in ('../file', '/CupLogos/a.png', 'CupLogos/../a.png',
                     'CupLogos//a.png', 'C:\\file', 'CupLogos/a.png/', 'x' * 128):
            self.assertEqual(self.read(name).returncode, 3, name)
        good = self.archive.read_bytes()
        # First sorted entry is animation. Mutate each bounded field.
        cases = []
        for offset, value, fmt in ((0, 0, '<Q'), (8, 0, '<I'), (8, 4097, '<I'),
                (12, 159, '<I'), (16, len(good)+1, '<Q'), (24, 0, '<Q'),
                (32+128, 1, '<Q'), (32+128, 2**63, '<Q'),
                (32+136, 2**63, '<Q'), (32+136, 0, '<Q'),
                (32+144, 0, '<Q'), (32+152, 1, '<I')):
            data = bytearray(good)
            struct.pack_into(fmt, data, offset, value)
            cases.append(data)
        cases.extend((good[:31], good[:-1], good + b'garbage'))
        for index, data in enumerate(cases):
            with self.subTest(corruption=index):
                self.archive.write_bytes(data)
                self.assertEqual(self.read('Animations/referee.nxra').returncode, 3)
                with self.assertRaises(ValueError):
                    verify(self.archive)

    def test_packer_preserves_inputs_and_refuses_reader_limit(self):
        expected = collect(self.root)
        verify(self.archive, expected)
        for name, data in self.payloads.items():
            self.assertEqual((self.root / name).read_bytes(), data)
        (self.root / 'Commentary/huge.nxcp').write_bytes(bytes(1048577))
        before = self.archive.read_bytes()
        with self.assertRaises(ValueError):
            pack(self.root, self.archive)
        self.assertEqual(before, self.archive.read_bytes())
