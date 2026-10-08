"""Geometry from the production League renderer driven through real frontend input."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]


def bounds(draw):
    v=draw['vertices']
    return min(v[::4]),min(v[1::4]),max(v[::4]),max(v[1::4])


class LeagueVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('cc') or not importlib.util.find_spec('PIL'):
            raise unittest.SkipTest('Host C compiler/Pillow unavailable')
        cls.temp=tempfile.TemporaryDirectory(prefix='pesnx-league-layout-')
        cls.addClassCleanup(cls.temp.cleanup)
        subprocess.run([sys.executable,str(ROOT/'tools/preview_league.py'),cls.temp.name,'--geometry-only'],
                       cwd=ROOT,check=True,timeout=60,capture_output=True)
        cls.frames={p.stem:json.loads(p.read_text()) for p in Path(cls.temp.name).glob('*.json')
                    if p.stem!='provenance'}

    def test_flow_stays_within_native_vertex_and_draw_budgets(self):
        self.assertEqual(len(self.frames),59)
        for name,draws in self.frames.items():
            with self.subTest(page=name):
                self.assertLess(len(draws),384)
                self.assertLess(sum(len(d['vertices'])//24 for d in draws),4096)
                for draw in draws:
                    for value in bounds(draw):self.assertLessEqual(abs(value),1.002)

    def test_controller_hints_live_in_footer_with_no_overlap(self):
        for name,draws in self.frames.items():
            helpers=[d for d in draws if d['kind']==2 and 20<=d['texture']<=37]
            with self.subTest(page=name):
                self.assertGreaterEqual(len(helpers),2)
                self.assertLessEqual(len(helpers),5)
                for draw in helpers:
                    self.assertLessEqual(bounds(draw)[3],1-2*.925)
                labels=sorted((bounds(d) for d in draws if d['kind']==1 and bounds(d)[3]<1-2*.925))
                self.assertEqual(len(labels),len(helpers))
                for left,right in zip(labels,labels[1:]):self.assertLess(left[2],right[0]-.025)
        for name in ['17-match-centre','33-knockout-bracket','49-first-leg-result']:
            self.assertEqual(sum(d['kind']==2 and 20<=d['texture']<=37 for d in self.frames[name]),5)

    def test_participant_cards_keep_four_row_geometry_on_partial_pages(self):
        for name,count in [('08-participants',8),('44-three-participants',3),
                           ('58-nineteen-participants',8),('59-participants-last-page',3)]:
            cards=[bounds(d) for d in self.frames[name]
                   if d['kind']==0 and d['color']==[.93,.96,.99,1]]
            crests=[bounds(d) for d in self.frames[name] if d['kind']==2 and d['texture']==3]
            with self.subTest(page=name):
                self.assertEqual(len(cards),count)
                self.assertEqual(len(crests),count)
                # Partial pages are the same two-column grid, without the
                # old stadium/news illustration filling the unused column.
                self.assertFalse(any(d['kind']==2 and d['texture']==60
                                     for d in self.frames[name]))
                for i,(card,crest) in enumerate(zip(cards,crests)):
                    self.assertAlmostEqual((card[0]+1)/2,.06+(i//4)*.452,delta=.001)
                    self.assertAlmostEqual((card[2]-card[0])/2,.425,delta=.001)
                    self.assertAlmostEqual((card[3]-card[1])/2,.120,delta=.001)
                    self.assertAlmostEqual((1-card[3])/2,.298+(i%4)*.139,delta=.001)
                    self.assertAlmostEqual((crest[3]-crest[1])/2,.084,delta=.001)

    def test_no_floating_text_in_gaps_and_header_preserves_aspect(self):
        for name,draws in self.frames.items():
            with self.subTest(page=name):
                headers=[d for d in draws if d['texture']==63 and d['kind']==2]
                self.assertEqual(len(headers),1)
                v=headers[0]['vertices']
                self.assertAlmostEqual((v[16]-v[0])*1280/((v[1]-v[17])*720),
                                       (v[18]-v[2])*3/(v[19]-v[3]),places=3)
                for draw in draws:
                    if draw['kind']!=1:continue
                    _,bottom,_,top=bounds(draw)
                    top,bottom=(1-top)/2,(1-bottom)/2
                    for a,b in [(.166,.187),(.906,.921)]:
                        self.assertFalse(top<b and bottom>a,(name,top,bottom))

    def test_champion_atlas_and_bracket_status_are_separate_from_team_rows(self):
        for name in ['35-knockout-champions','36-final-champion-atlas','38-standings-champions']:
            crests=[d for d in self.frames[name] if d['kind']==2 and d['texture']==3]
            self.assertTrue(any((bounds(d)[3]-bounds(d)[1])*.5>=.15 for d in crests),name)
        for name in ['33-knockout-bracket','34-final-upcoming','49-first-leg-result','50-aggregate-result']:
            draws=self.frames[name]
            cards=[d for d in draws if d['kind']==0 and d['color']==[.93,.96,.99,1]]
            self.assertTrue(cards,name)
            for card in cards:
                x,_,right,top=bounds(card)
                row=[bounds(d) for d in draws if d['kind']==1 and abs(bounds(d)[3]-(top-.045))<.004
                     and bounds(d)[0]>=x+.13 and bounds(d)[2]<=right+.02]
                self.assertEqual(len(row),2,(name,row))
                self.assertLess(row[0][2],row[1][0])
                self.assertAlmostEqual(row[0][3],row[1][3],delta=.003)

    def test_six_team_pages_keep_owner_badges_and_rank_indicators(self):
        for name,rows in [('15-standings',6),('16-standings-page2',6),
                          ('51-table-eight-players-page1',6),
                          ('52-table-eight-players-page2',6),('53-table-last-page',2)]:
            draws=self.frames[name]
            crests=[d for d in draws if d['kind']==2 and d['texture']==3]
            badges=[d for d in draws if d['kind']==0 and d['color']==[.03,.42,.70,1]]
            with self.subTest(page=name):
                self.assertEqual(len(crests),rows)
                self.assertLessEqual(len(badges),rows)
                if name=='15-standings':self.assertEqual(len(badges),2)
                for d in crests:self.assertAlmostEqual((bounds(d)[3]-bounds(d)[1])*.5,.069,delta=.001)
                # Six uniform rows, also on the partially filled last page.
                tops=sorted(bounds(d)[3] for d in crests)
                for a,b in zip(tops,tops[1:]):self.assertAlmostEqual(b-a,.160,delta=.001)
        arrows=[d for name in ['29-table-after-match','54-table-movement-page2'] for d in self.frames[name] if d['kind']==0 and
                len(set(zip(d['vertices'][::4],d['vertices'][1::4])))==3]
        self.assertTrue(any(d['color'][:3]==[.03,.48,.76] for d in arrows))
        self.assertTrue(any(d['color'][:3]==[.86,.14,.23] for d in arrows))
        for d in arrows:
            v=d['vertices'];self.assertLessEqual(bounds(d)[2],2*.110-1)
            self.assertEqual(v[9]>v[1],d['color'][0]<.1)


if __name__=='__main__':unittest.main()
