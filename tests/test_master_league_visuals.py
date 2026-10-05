"""Actual C layout vertices, not snapshots of a separately authored mockup."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


class MasterLeagueVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('gcc') or not importlib.util.find_spec('PIL'):
            raise unittest.SkipTest('Host C compiler/Pillow unavailable')
        cls.temp=tempfile.TemporaryDirectory(prefix='pesnx-career-layout-')
        cls.addClassCleanup(cls.temp.cleanup)
        subprocess.run([sys.executable,str(ROOT/'tools/preview_master_league.py'),cls.temp.name],
                       cwd=ROOT,check=True,timeout=60,capture_output=True)
        cls.frames={p.stem:json.loads(p.read_text()) for p in Path(cls.temp.name).glob('*.json')}

    def test_every_page_fits_native_vertex_budget(self):
        self.assertEqual(len(self.frames),8)
        for name,draws in self.frames.items():
            with self.subTest(page=name):
                self.assertLess(len(draws),224)
                self.assertLess(sum(len(d['vertices'])//24 for d in draws),4096)
                for d in draws:
                    vertices=d['vertices']
                    for offset in range(0,len(vertices),4):
                        self.assertLessEqual(abs(vertices[offset]),1.002)
                        self.assertLessEqual(abs(vertices[offset+1]),1.002)

    def test_atlas_regions_have_gutters_and_preserve_aspect(self):
        for name,draws in self.frames.items():
            for d in draws:
                if d['kind']!=2 or d['texture']!=6:continue
                v=d['vertices'];u0,t0,u1,t1=v[2],v[3],v[18],v[19]
                with self.subTest(page=name,uv=(u0,t0,u1,t1)):
                    self.assertGreater(d['radius'],0)
                    self.assertEqual(int(u0*2),int(u1*2))
                    self.assertEqual(int(t0*2),int(t1*2))
                    self.assertGreaterEqual(u0%0.5,.0019)
                    self.assertGreaterEqual(t0%0.5,.0019)
                    self.assertLessEqual(u1%0.5,.4981)
                    self.assertLessEqual(t1%0.5,.4981)
                    screen_aspect=(v[16]-v[0])*1280/((v[1]-v[17])*720)
                    sample_aspect=(u1-u0)*2/(t1-t0)
                    self.assertAlmostEqual(screen_aspect,sample_aspect,places=2)

    def test_distinct_text_lines_do_not_overlap(self):
        for name,draws in self.frames.items():
            boxes=[]
            for d in draws:
                if d['kind']!=1 or not d['vertices']:continue
                v=d['vertices'];xs=[(x+1)*640 for x in v[0::4]];ys=[(1-y)*360 for y in v[1::4]]
                boxes.append((min(xs),min(ys),max(xs),max(ys)))
            for i,a in enumerate(boxes):
                for b in boxes[i+1:]:
                    overlap_x=min(a[2],b[2])-max(a[0],b[0])
                    overlap_y=min(a[3],b[3])-max(a[1],b[1])
                    with self.subTest(page=name,first=a,second=b):
                        self.assertFalse(overlap_x>1.5 and overlap_y>1.5)


if __name__=='__main__':unittest.main()
