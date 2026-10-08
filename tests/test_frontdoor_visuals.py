"""Exercise the production frontdoor renderer with bounded, synthetic state.

These are not native controller/kit or hardware performance tests.
"""
import importlib.util
import json
import re
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def box(draw):
    v = draw['vertices']
    return ((min(v[::4]) + 1) / 2, (1 - max(v[1::4])) / 2,
            (max(v[::4]) + 1) / 2, (1 - min(v[1::4])) / 2)


class FrontdoorVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (shutil.which('cc') or shutil.which('gcc')) or not importlib.util.find_spec('PIL'):
            raise unittest.SkipTest('Host C compiler/Pillow unavailable')
        cls.temp = tempfile.TemporaryDirectory(prefix='pesnx-frontdoor-layout-')
        cls.addClassCleanup(cls.temp.cleanup)
        result = subprocess.run(
            [sys.executable, str(ROOT / 'tools/preview_frontdoor.py'), cls.temp.name, '--geometry-only'],
            cwd=ROOT, capture_output=True, text=True, timeout=90)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.frames = {p.stem: json.loads(p.read_text()) for p in Path(cls.temp.name).glob('*.json')
                      if p.stem != 'provenance'}
        cls.motion = {p.stem: json.loads(p.read_text()) for p in (Path(cls.temp.name) / 'motion').glob('*.json')
                      if not p.stem.startswith('pattern-')}
        cls.pattern = {p.stem: json.loads(p.read_text()) for p in (Path(cls.temp.name) / 'motion').glob('pattern-*.json')}
        cls.source = (ROOT / 'source/frontdoor_overlay.inc').read_text()

    def test_full_flow_fits_native_budgets_and_screen(self):
        # The C driver also checks a vertex-buffer canary and immutable input.
        self.assertEqual(len(self.frames), 62)
        for name, draws in self.frames.items():
            with self.subTest(frame=name):
                self.assertLess(len(draws), 384)
                self.assertLess(sum(len(d['vertices']) // 24 for d in draws), 4096)
                for d in draws:
                    for value in box(d):
                        self.assertGreaterEqual(value, -.001)
                        self.assertLessEqual(value, 1.001)

    def test_flat_art_is_shared_but_not_master_league_fabric(self):
        for name, draws in self.frames.items():
            with self.subTest(frame=name):
                background = [d for d in draws if d['texture'] == 70 and d['kind'] == 2]
                self.assertEqual(len(background), 1)
                self.assertEqual(box(background[0]), (0, 0, 1, 1))
                self.assertFalse(any(d['texture'] == 50 for d in draws))
                for d in draws:
                    if d['texture'] != 76:
                        continue
                    v = d['vertices']
                    u0, v0, u1, v1 = v[2], v[3], v[18], v[19]
                    self.assertEqual(int(v0 * 4), int(v1 * 4))
                    self.assertGreaterEqual(v0 % .25, .0018)
                    self.assertLessEqual(v1 % .25, .2482)
                    b = box(d)
                    self.assertAlmostEqual((b[2] - b[0]) * 1280 / ((b[3] - b[1]) * 720),
                                           (u1 - u0) * 1.5 / (v1 - v0), places=3)

    def test_both_featured_teams_keep_their_side_colour(self):
        for name in ['10-select-team-home', '11-select-team-away', '13-two-player-select']:
            draws = self.frames[name]
            # The opaque side art replaces the generic focused-card fill.
            featured = list({tuple(round(v, 5) for v in box(d)): d for d in draws
                             if d['texture'] == 76
                             and abs(box(d)[3] - box(d)[1] - .260) < .001}.values())
            with self.subTest(frame=name):
                self.assertEqual(len(featured), 2)
                self.assertEqual([int(d['vertices'][3] * 4) for d in featured], [0, 1])
                # Rating bars must remain visible on both coloured cards.
                bars = [d for d in draws if d['kind'] == 0 and d['color'] == [1, 1, 1, 1]
                        and abs(box(d)[3] - box(d)[1] - .009) < .001]
                self.assertEqual(len(bars), 6)
        selector = self.source.split('static void fd_selector(', 1)[1].split('static void fd_hub(', 1)[0]
        self.assertNotIn('BROWSE / CONFIRM', selector)
        self.assertNotIn('WAITING FOR', selector)

    def test_hub_buttons_center_the_complete_icon_text_group(self):
        names = [name for name in self.frames if name.startswith('17-hub-')]
        self.assertEqual(len(names), 9)
        for name in names:
            draws = self.frames[name]
            count = int(name.split('-')[2])
            icons = [d for d in draws if d['kind'] == 2 and d['texture'] == 52 and .78 < box(d)[1] < .89]
            labels = [d for d in draws if d['kind'] == 1 and d['texture'] == 2 and .78 < box(d)[1] < .89]
            with self.subTest(frame=name):
                self.assertEqual(len(icons), count)
                self.assertEqual(len(labels), count)
                width = (.93 - (count - 1) * .012) / count
                for i, (icon, label) in enumerate(zip(icons, labels)):
                    ib, lb = box(icon), box(label)
                    center = .035 + i * (width + .012) + width / 2
                    self.assertAlmostEqual((ib[0] + lb[2]) / 2, center, delta=.004)
                    self.assertLess(ib[2], lb[0])
                    self.assertAlmostEqual((ib[1] + ib[3]) / 2, .834, delta=.001)
                    self.assertLess(lb[1], .834)
                    self.assertGreater(lb[3], .834)
        self.assertIn('fd_cap_top(cy,text_h)', self.source)

    def test_large_controller_helpers_stay_in_footer(self):
        for name, draws in self.frames.items():
            if name in ('01-title', '32-loading', '33-prematch-loading'):
                continue
            with self.subTest(frame=name):
                helpers = [d for d in draws if d['kind'] == 2 and 20 <= d['texture'] <= 37]
                single = name in ('31-credits', '37-half-time-overview', '39-full-time-overview',
                                  '44-results-missing-stats', '45-results-1080p')
                self.assertGreaterEqual(len(helpers), 1 if single else 2)
                self.assertLessEqual(len(helpers), 5)
                for d in helpers:
                    b = box(d)
                    self.assertGreaterEqual(b[1], .9279)
                    self.assertAlmostEqual((b[3] - b[1]) * 720, 38, delta=.1)
                labels = [box(d) for d in draws if d['kind'] == 1 and box(d)[1] > .9279]
                self.assertEqual(len(labels), len(helpers))
                for left, right in zip(labels, labels[1:]):
                    self.assertLess(left[2], right[0] - .025)

    def test_results_share_pause_stats_and_center_all_action_counts(self):
        pause = self.frames['34-pause']
        # The two team strips and stats panel keep exactly the Pause geometry.
        def panels(draws):
            return [tuple(round(v, 5) for v in box(d)) for d in draws
                    if d['texture'] == 76 and abs(box(d)[1] - .104) < .001]
        for name, draws in self.frames.items():
            if int(name[:2]) < 37:
                continue
            with self.subTest(frame=name):
                self.assertEqual(panels(draws), panels(pause))
                labels = [box(d) for d in draws if d['kind'] == 1 and .78 < box(d)[1] < .89]
                count = 3 if name.startswith(('38-', '42-')) else 2 if name.startswith('43-') else 1
                self.assertEqual(len(labels), count)
                start = (1 - count * .296 - (count - 1) * .021) / 2
                for i, label in enumerate(labels):
                    self.assertGreaterEqual(label[0], start + i * .317)
                    self.assertLessEqual(label[2], start + i * .317 + .296)
                for left, right in zip(labels, labels[1:]):
                    self.assertLess(left[2], right[0])
                helper_count = 1 if name.startswith(('37-', '39-', '44-', '45-')) else 4 if count > 1 else 2
                self.assertEqual(sum(d['kind'] == 2 and 20 <= d['texture'] <= 37 for d in draws), helper_count)
        overlay = (ROOT / 'source/overlay.c').read_text()
        route = overlay.split('FrontdoorPage frontdoor_page=FD_NONE;', 1)[1].split('const int native_lab', 1)[0]
        self.assertIn('else if(result_skin)frontdoor_page=FD_RESULT;', route)
        self.assertLess(route.index('result_transition'), route.index('result_skin)frontdoor_page'))
        self.assertLess(route.index('pause_skin)frontdoor_page'), route.index('result_skin)frontdoor_page'))

    def test_kit_container_helpers_describe_directions_not_player_ownership(self):
        self.assertIn('v->kit_editing ? "PREV KIT" : "LEFT"', self.source)
        self.assertIn('v->kit_editing ? "NEXT KIT" : "RIGHT"', self.source)
        self.assertNotIn('v->kit_editing ? "PREV KIT" : "P1"', self.source)
        self.assertNotIn('v->kit_editing ? "NEXT KIT" : "P2"', self.source)

    def test_adjustable_values_have_paired_arrows_without_numeric_pagination(self):
        for name, count in [('20-stadium', 6), ('21-stadium-last-row', 6),
                            ('22-general-settings', 6), ('23-general-settings-scroll', 6),
                            ('30-video-settings', 2), ('29-pause-camera-settings', 4)]:
            arrows = [d for d in self.frames[name] if d['texture'] == 51 and d['kind'] == 2]
            with self.subTest(frame=name):
                self.assertEqual(len(arrows), count * 2)
                for left, right in zip(arrows[::2], arrows[1::2]):
                    lb, rb = box(left), box(right)
                    self.assertAlmostEqual(lb[1], rb[1], places=5)
                    self.assertAlmostEqual(lb[3], rb[3], places=5)
                    self.assertLess(lb[2], rb[0])
        self.assertNotIn('OF %u', self.source)
        self.assertNotIn('%u-%u', self.source)
        self.assertNotIn(' / %u', self.source)

    def test_title_preserves_logo_alpha_and_has_one_start_prompt(self):
        draws = self.frames['01-title']
        logo = [d for d in draws if d['kind'] == 4 and d['texture'] == 56]
        self.assertEqual(len(logo), 1)
        self.assertEqual(logo[0]['color'], [.025, .09, .27, 1])
        self.assertEqual(sum(d['kind'] == 2 and 20 <= d['texture'] <= 37 for d in draws), 1)
        self.assertFalse(any(d['texture'] == 76 and box(d)[1] < .6 for d in draws))

    def test_main_menu_is_four_compact_icon_title_rows_on_the_left(self):
        for name in ['02-main-menu', '03-main-menu-modes', '04-main-menu-settings', '05-main-menu-credits']:
            draws = self.frames[name]
            icons = [d for d in draws if d['texture'] == 52 and d['kind'] == 2]
            labels = [d for d in draws if d['kind'] == 1 and d['texture'] == 2 and box(d)[1] < .9]
            with self.subTest(frame=name):
                self.assertEqual(len(icons), 4)
                self.assertEqual(len(labels), 4)  # No headline or descriptions.
                focus = int(name[:2]) - 2
                y = .337
                for i, (icon, label) in enumerate(zip(icons, labels)):
                    height = .182 if i == focus else .084
                    ib, lb = box(icon), box(label)
                    self.assertLess(lb[2], .457)
                    self.assertAlmostEqual(lb[0], .134, delta=.001)
                    self.assertLess(ib[2], lb[0])
                    self.assertAlmostEqual((ib[1] + ib[3]) / 2, y + height / 2, delta=.001)
                    y += height + .020
                portraits = [d for d in draws if d['kind'] == 2 and 72 <= d['texture'] <= 75]
                self.assertTrue(portraits)
                self.assertGreaterEqual(box(portraits[0])[0], .5599)

    def test_menu_motion_reflows_without_overlap_jump_or_frame_rate_dependency(self):
        # Driver assertions cover retarget continuity, inactive/reentry reset,
        # normalized weights and equal-time poses at different update rates.
        self.assertEqual(len(self.motion), 35)
        def rows(draws):
            return [box(d) for d in draws if d['kind'] == 0 and d['color'] == [1, 1, 1, 1]
                    and abs(box(d)[0] - .050) < .001 and abs(box(d)[2] - .457) < .001]
        for name, draws in self.motion.items():
            cards = rows(draws)
            with self.subTest(frame=name):
                self.assertEqual(len(cards), 4)
                self.assertAlmostEqual(cards[0][1], .337, delta=.001)
                self.assertAlmostEqual(cards[-1][3], .831, delta=.001)
                for prev, nxt in zip(cards, cards[1:]):
                    self.assertAlmostEqual(nxt[1] - prev[3], .020, delta=.001)
                for card in cards:
                    self.assertGreaterEqual(card[3] - card[1], .0839)
                    self.assertLessEqual(card[3] - card[1], .1821)
        self.assertEqual(rows(self.motion['retarget-before']), rows(self.motion['retarget-after']))
        start, end = rows(self.motion['motion-00']), rows(self.motion['motion-08'])
        self.assertGreater(start[0][3] - start[0][1], 2 * (start[1][3] - start[1][1]))
        self.assertGreater(end[1][3] - end[1][1], 2 * (end[0][3] - end[0][1]))

    def test_snapshot_is_read_only_and_legacy_renderer_is_not_drawn_underneath(self):
        snapshot = self.source.split('static void frontdoor_snapshot(', 1)[1].split('static void fd_rect(', 1)[0]
        # These two confirm-state accessors are read-only; "confirm" is the
        # modal's name, not a command to execute it.
        snapshot = re.sub(r'pes_controller_pause_top_menu_confirm_(?:active|focus)\(\)', 'read_only_confirm_state', snapshot)
        self.assertNotRegex(snapshot, r'\b(?:pes_controller|competition_frontend)_\w*(?:set_|move_|input|confirm_|activate|kickoff)\w*\s*\(')
        overlay = (ROOT / 'source/overlay.c').read_text()
        self.assertIn('frontdoor_snapshot(&view,frontdoor_page', overlay)
        self.assertIn('prepare_main_menu_assets(frontdoor_page!=FD_NONE ||', overlay)
        self.assertIn('goto overlay_geometry_ready;', overlay)
        self.assertIn('master_league_draw(&frontdoor_ui);\n    goto overlay_restore;', overlay)

    def test_focused_pattern_loops_inside_its_strip_without_moving_content(self):
        self.assertEqual(len(self.pattern), 61)
        reference = self.pattern['pattern-00']
        different_uvs = set()
        for name, draws in self.pattern.items():
            with self.subTest(frame=name):
                self.assertEqual(len(draws), len(reference))
                for original, current in zip(reference, draws):
                    self.assertEqual(box(original), box(current))
                    if current['texture'] == 76:
                        v = current['vertices']
                        self.assertGreaterEqual(v[3], .7519)
                        self.assertLessEqual(v[19], .9981)
                        self.assertGreaterEqual(v[2], .0012)
                        self.assertLessEqual(v[18], .9988)
                        different_uvs.add(tuple(v[2:4]))
                    else:
                        self.assertEqual(original, current)
        self.assertGreater(len(different_uvs), 30)
        self.assertEqual(reference, self.pattern['pattern-cycle-end'])

    def test_generated_assets_are_exact_public_png_copies_within_decoder_budget(self):
        spec = json.loads((ROOT / 'art/frontdoor/prompts-v2.json').read_text())
        self.assertEqual(spec['mode'], 'built-in image_gen')
        v3 = json.loads((ROOT / 'art/frontdoor/prompts-v3.json').read_text())
        self.assertEqual(v3['mode'], 'built-in image_gen')
        spec['assets'].extend(v3['assets'])
        for asset in spec['assets']:
            data = (ROOT / asset['art']).read_bytes()
            with self.subTest(asset=asset['art']):
                self.assertEqual(data, (ROOT / asset['runtime']).read_bytes())
                self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
                w, h = struct.unpack_from('>II', data, 16)
                self.assertEqual((w, h), (asset['width'], asset['height']))
                self.assertLessEqual(w * h, 2048 * 2048)
                self.assertLessEqual(max(w, h), 4096)


if __name__ == '__main__':
    unittest.main()
