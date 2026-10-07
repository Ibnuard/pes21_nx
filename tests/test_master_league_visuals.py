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
        self.assertTrue({'landing','settings','club-selector','nationality-selector',
            'calendar','squad-list','contract-term','career-settings','ranking-focus'} <= self.frames.keys())
        for name,draws in self.frames.items():
            with self.subTest(page=name):
                self.assertLess(len(draws),384)
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

    def test_popup_and_standings_prioritize_readability(self):
        draws=self.frames['offer-terms']
        popup=[d for d in draws if d.get('layer')==2 and d['kind']==0
               and d['color']==[1,1,1,1]][0]
        v=popup['vertices']
        self.assertAlmostEqual((v[16]-v[0])*640,768,delta=1)
        self.assertAlmostEqual((v[16]+v[0])*.5,0,delta=.002)
        arrows=[d for d in draws if d.get('layer')==2 and d['texture']==7]
        self.assertEqual(len(arrows),6)
        for i in range(0,6,2):
            left,right=arrows[i]['vertices'],arrows[i+1]['vertices']
            self.assertAlmostEqual(left[1],right[1],places=4)
            self.assertAlmostEqual(left[17],right[17],places=4)
            self.assertAlmostEqual((left[1]-left[17])*360,24.48,delta=.1)
            self.assertAlmostEqual((left[0]+right[16])*.5,0,delta=.002)
        badges=[d for d in self.frames['league-table'] if d['kind']==2 and d['texture']==2]
        self.assertEqual(len(badges),9) # header crest + eight table rows
        for d in badges[1:]:
            self.assertGreaterEqual((d['vertices'][1]-d['vertices'][17])*360,36)

    def test_quick_save_toast_dismisses_without_navigation(self):
        self.assertTrue(any(d.get('layer')==1 for d in self.frames['quick-save']))
        self.assertFalse(any(d.get('layer')==1 for d in self.frames['quick-save-dismissed']))
        before=[d for d in self.frames['quick-save'] if d.get('layer')!=1]
        after=[d for d in self.frames['quick-save-dismissed'] if d.get('layer')!=1]
        self.assertEqual(before,after)

    def test_empty_icon_crop_opacity_and_foreground_toast(self):
        icons=[d for d in self.frames['scorers-empty'] if d['texture']==7]
        self.assertEqual(len(icons),1)
        icon=icons[0]
        self.assertGreaterEqual(icon['vertices'][2],.55)
        self.assertAlmostEqual(icon['color'][3],.58,places=2)
        draws=self.frames['quick-save']
        helpers=[i for i,d in enumerate(draws) if 10<=d['texture']<=17]
        toasts=[i for i,d in enumerate(draws) if d['layer']==1]
        self.assertGreater(min(toasts),max(helpers))
        overlay=(ROOT/'source/overlay.c').read_text()
        self.assertGreater(overlay.index('master_league_draw_layer(&master_league_ui,1)'),
                           overlay.index('// Draw all helper glyphs'))

    def test_primary_tiles_balance_and_calendar_playback(self):
        def cards(name):
            return [d for d in self.frames[name] if d['kind']==0 and
                    abs(d['color'][0]-.93)<.005 and abs(d['color'][1]-.96)<.005]
        # Market tiles fill the panel; not the old 62px list rows.
        for d in cards('market'):
            self.assertGreater((d['vertices'][1]-d['vertices'][17])*360,80)
        # Two profile cards share equal free space above/below the group.
        profile=[d for d in self.frames['manager'] if d in cards('manager') or
                 (d['kind']==2 and d['texture']==6 and
                  abs((d['vertices'][1]-d['vertices'][17])*.5-.215)<.001)]
        self.assertEqual(len(profile),2)
        top=(1-profile[0]['vertices'][1])*360
        bottom=(1-profile[-1]['vertices'][17])*360
        self.assertAlmostEqual(top-.280*720,.835*720-bottom,delta=1)
        self.assertNotEqual(self.frames['advance-start'],self.frames['advance-moving'])
        self.assertTrue(any(d['layer']==1 for d in self.frames['advance-arrived']))

    def test_short_action_groups_and_save_slots_are_proportional(self):
        def tiles(name):
            return [d for d in self.frames[name] if d.get('layer',0)==0 and
                    ((d['kind']==0 and abs(d['color'][0]-.93)<.005 and abs(d['color'][1]-.96)<.005)
                    or (d['kind']==2 and d['texture']==6 and d['vertices'][1]<.5
                        and (d['vertices'][16]-d['vertices'][0])*640>800))]
        for name in ('squad','next-match','my-teams','save-slots'):
            group=tiles(name)
            with self.subTest(page=name):
                self.assertEqual(len(group),3 if name=='save-slots' else 2)
                heights=[(d['vertices'][1]-d['vertices'][17])*360 for d in group]
                self.assertLess(max(heights)-min(heights),1)
                self.assertGreater(min(heights),110)
                top=(1-group[0]['vertices'][1])*360
                bottom=(1-group[-1]['vertices'][17])*360
                self.assertAlmostEqual(top-.280*720,.835*720-bottom,delta=1)

    def test_confirmation_modals_cover_helpers_and_keep_background(self):
        for name in ('overwrite-modal','play-modal','simulate-modal','release-modal'):
            draws=self.frames[name]
            modal=[i for i,d in enumerate(draws) if d['layer']==3]
            helpers=[i for i,d in enumerate(draws) if 10<=d['texture']<=17]
            with self.subTest(page=name):
                self.assertGreater(min(modal),max(helpers))
                panel=[draws[i] for i in modal if draws[i]['kind']==0 and draws[i]['color']==[1,1,1,1]][0]
                v=panel['vertices']
                self.assertAlmostEqual((v[16]-v[0])*640,704,delta=1)
                self.assertAlmostEqual((v[16]+v[0])*.5,0,delta=.002)
                self.assertFalse(any(d['layer']==1 for d in draws))
                self.assertTrue(any(d['layer']==0 and d['kind']==2 and d['texture']==6 for d in draws))

    def test_scorer_and_story_identity_use_badge_atlas(self):
        for name,minimum in (('scorers-with-badges',2),('club-feed',3),('feed-results',4),('feed-transfers',3)):
            badges=[d for d in self.frames[name] if d['kind']==2 and d['texture']==2]
            with self.subTest(page=name):self.assertGreaterEqual(len(badges),minimum)
        # Terminal replies contain status imagery and no fake disabled actions.
        terminal=self.frames['rejected-offer']
        self.assertTrue(any(d['layer']==2 and d['texture']==7 for d in terminal))
        self.assertFalse(any(d['layer']==2 and d['kind']==0 and
            abs(d['color'][0]-.89)<.005 and abs(d['color'][1]-.91)<.005 for d in terminal))

    def test_calendar_tiles_fill_five_and_six_week_months(self):
        for name,weeks in (('calendar',5),('calendar-august',6)):
            cells=[d for d in self.frames[name] if d['kind']==0 and
                   abs(d['color'][0]-.93)<.005 and abs(d['color'][1]-.96)<.005]
            self.assertEqual(len(cells),31)
            height=(cells[0]['vertices'][1]-cells[0]['vertices'][17])*360
            self.assertAlmostEqual(height,(.490-(weeks-1)*.008)/weeks*720,delta=.2)
            bottom=(1-cells[-1]['vertices'][17])*360
            self.assertAlmostEqual(bottom,.817*720,delta=.2)

    def test_unread_indicators_are_visible_in_market_and_hub(self):
        for name in ('market-unread','hub-unread','transfer-response'):
            dots=[d for d in self.frames[name] if d['kind']==0 and
                  abs(d['color'][0]-.91)<.001 and abs(d['color'][1]-.08)<.001]
            self.assertTrue(dots,name)
            for d in dots:
                self.assertAlmostEqual((d['vertices'][16]-d['vertices'][0])*640,12,delta=.2)
                self.assertAlmostEqual((d['vertices'][1]-d['vertices'][17])*360,12,delta=.2)

    def test_distinct_text_lines_do_not_overlap(self):
        for name,draws in self.frames.items():
            boxes=[]
            for d in draws:
                if d['kind']!=1 or not d['vertices']:continue
                v=d['vertices'];xs=[(x+1)*640 for x in v[0::4]];ys=[(1-y)*360 for y in v[1::4]]
                boxes.append((min(xs),min(ys),max(xs),max(ys),d.get('layer',0)))
            for i,a in enumerate(boxes):
                for b in boxes[i+1:]:
                    if a[4]!=b[4]:continue # deliberate timed toast overlay
                    overlap_x=min(a[2],b[2])-max(a[0],b[0])
                    overlap_y=min(a[3],b[3])-max(a[1],b[1])
                    with self.subTest(page=name,first=a,second=b):
                        self.assertFalse(overlap_x>1.5 and overlap_y>1.5)

    def test_offer_crests_and_fee_positions_survive_reading(self):
        positions=[]
        for name in ('club-offers-top','club-offers-read'):
            draws=self.frames[name]
            self.assertGreaterEqual(sum(d['kind']==2 and d['texture']==2 for d in draws),3)
            fees=[d for d in draws if d['kind']==1 and d['layer']==0 and d['vertices'] and
                  min(d['vertices'][0::4])>0 and .29<(1-d['vertices'][1])*.5<.8]
            self.assertEqual(len(fees),2)
            xs=[max(d['vertices'][0::4]) for d in fees]
            self.assertAlmostEqual(xs[0],xs[1],delta=.0001)
            self.assertGreater((xs[0]+1)*640,1060) # right edge, not a left-aligned value column
            positions.append(xs)
            dots=[d for d in draws if d['kind']==0 and abs(d['color'][0]-.91)<.001 and abs(d['color'][1]-.08)<.001]
            for dot in dots:
                dot_top=(1-dot['vertices'][1])*360
                self.assertLess(min(abs(dot_top-y*720) for y in (.307,.448)),1)
        self.assertEqual(positions[0],positions[1])
        offers=self.frames['national-offer']
        self.assertGreaterEqual(sum(d['kind']==2 and d['texture']==2 for d in offers),2)
        self.assertTrue(any(d['layer']==2 and d['texture']==2 for d in self.frames['national-offer-modal']))
        self.assertFalse(any(d['layer']==2 and d['kind']==0 and abs(d['color'][0]-.89)<.005 and
                             abs(d['color'][1]-.91)<.005 for d in self.frames['national-declined-modal']))

    def test_v7_lists_start_at_top_and_world_sprites_are_isolated(self):
        for name,y in (('club-offers-top',.297),('feed-results',.421),('feed-transfers',.421)):
            rows=[d for d in self.frames[name] if d['layer']==0 and
                  ((d['kind']==0 and abs(d['color'][0]-.93)<.005 and abs(d['color'][1]-.96)<.005) or
                   (name=='club-offers-top' and d['kind']==2 and d['texture']==6 and
                    .28<(1-d['vertices'][1])*.5<.8))]
            if rows:
                self.assertAlmostEqual((1-rows[0]['vertices'][1])*.5,y,delta=.001)
        self.assertTrue(any(d['layer']==1 for d in self.frames['window-closed-toast']))
        for name in ('cup-competitions','national-office','feed-results'):
            icons=[d for d in self.frames[name] if d['texture']==8]
            self.assertTrue(icons,name)
            for d in icons:
                v=d['vertices']
                self.assertEqual(int(v[2]*2),int(v[18]*2))
                self.assertEqual(int(v[3]*2),int(v[19]*2))
                self.assertAlmostEqual((v[16]-v[0])*640,(v[1]-v[17])*360,delta=.2)
        self.assertTrue(any(d['texture']==2 for d in self.frames['national-regional-cup']))


if __name__=='__main__':unittest.main()
