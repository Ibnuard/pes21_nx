import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('pacing', Path(__file__).resolve().parents[1] / 'tools/analyze_match_pacing.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class PacingAnalysisTests(unittest.TestCase):
    def test_cold_and_warm_startup_records_do_not_invent_cache_or_visibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            cold, warm = Path(tmp)/'cold.log', Path(tmp)/'warm.log'
            cold.write_text('FootballNX scene v48 session\n'
                            'render stability v47: private overlay vertex state\n'
                            'model quality: HIGH=standard/high (player/stadium)\n'
                            'GL compile failed: allocation failed\n'
                            'GL link failed: incomplete program\n')
            warm.write_text('FootballNX scene v48 session\n'
                            'model quality: diagnostic control: native player classes\n'
                            'frame pacing: time=DAY frames=600 avg_us=16667 '
                            'worst_us=18000 over20ms=0 over30ms=0\n')
            result = M.compare({'cold':cold, 'warm':warm}, allow_partial=True)
            first, second = result['cases']['cold'], result['cases']['warm']
            self.assertFalse(first['timings_available'])
            self.assertEqual(first['startup']['session_versions'], [48])
            self.assertEqual(first['startup']['compile_failures'], ['allocation failed'])
            self.assertEqual(first['startup']['link_failures'], ['incomplete program'])
            self.assertEqual(second['startup']['compile_failures'], [])
            self.assertEqual(second['startup']['model_quality_policies'],
                             ['diagnostic control: native player classes'])
            self.assertIsNone(second['startup']['shader_cache_hit_rate'])
            self.assertFalse(second['startup']['visibility_verified'])
            self.assertEqual(result['comparisons'], [])

    def test_legacy_log_keeps_missing_startup_evidence_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp)/'old.log'
            log.write_text('frame pacing: time=DAY frames=600 avg_us=17000 '
                           'worst_us=19000 over20ms=0 over30ms=0\n')
            startup = M.read_case(log)['startup']
            self.assertEqual(startup['session_versions'], [])
            self.assertEqual(startup['model_quality_policies'], [])
            self.assertIsNone(startup['shader_cache_hit_rate'])
            self.assertFalse(startup['visibility_verified'])

    def test_load_only_log_is_unknown_and_cannot_approve_timing_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'loads.log'
            log.write_text('render control: state_cache=bypassed (diagnostic boot setting)\n'
                           'realface-load: v43 native_id=34493 face_resolved=1 face_mesh=1 face_lods=1\n')
            with self.assertRaisesRegex(ValueError,'No presentation'):M.read_case(log)
            result=M.compare({'bypassed':log},allow_partial=True)
            case=result['cases']['bypassed']
            self.assertFalse(case['timings_available'])
            self.assertEqual(case['measurement_kind'],'unavailable')
            self.assertEqual(case['face_loads'][0]['native_id'],34493)
            self.assertEqual(case['state_cache'],'bypassed')
            self.assertEqual(case['groups'],[])
            self.assertEqual(result['comparisons'],[])

    def test_render_control_and_absolute_buffer_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'outcomes.log'
            log.write_text('render control: state_cache=bypassed (diagnostic boot setting)\n'+
                'near-camera: zone=near_middle frames=600 avg_us=17000 worst_us=25000 over20=1 over30=0 '
                'map_calls=20 map_failures=2 unmap_calls=18 unmap_failures=1 gl_error_checks=3 gl_errors=1 first_gl_error=1282\n'+
                'near-camera: zone=near_middle frames=1200 avg_us=17000 worst_us=25000 over20=1 over30=0 '
                'map_calls=30 map_failures=0 unmap_calls=30 unmap_failures=0 gl_error_checks=2 gl_errors=0 first_gl_error=0\n')
            result=M.read_case(log);group=result['groups'][0]
            self.assertEqual(result['state_cache'],'bypassed')
            self.assertEqual((group['map_calls'],group['map_failures'],group['unmap_failures']),(50,2,1))
            self.assertEqual((group['gl_error_checks'],group['gl_errors'],group['first_gl_error']),(5,1,1282))

    def test_explanatory_suffix_cannot_overwrite_measured_zone(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'regions.log'
            log.write_text('near-camera: camera=5 zone=near_middle frames=600 avg_us=18000 worst_us=20000 over20=0 over30=0 '
                           '(CPU calls; not GPU time; zone=camera target; quantiles=bucket upper bounds)\n'
                           'near-camera: camera=5 zone=centre_middle frames=600 avg_us=16000 worst_us=19000 over20=0 over30=0 '
                           '(CPU calls; not GPU time; zone=camera target; quantiles=bucket upper bounds)\n')
            groups=M.read_case(log)['groups']
            self.assertEqual([g['context']['zone'] for g in groups],['near_middle','centre_middle'])
            self.assertEqual([g['mean_interval_us'] for g in groups],[18000,16000])

    def test_blend_savings_are_absolute_counts_and_old_logs_are_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'blend.log'
            line='near-camera: camera=6 zone=near_middle frames=600 avg_us=17000 worst_us=20000 over20=0 over30=0 '
            log.write_text(line+'blend_requests=900 blend_skipped=600\n'+
                           line+'blend_requests=700 blend_skipped=200\n')
            group=M.read_case(log)['groups'][0]
            self.assertEqual((group['blend_requests'],group['blend_skipped']),(1600,800))
            log.write_text(line+'\n')
            self.assertIsNone(M.read_case(log)['groups'][0]['blend_requests'])
            log.write_text(line+'blend_requests=1 blend_skipped=2\n')
            with self.assertRaisesRegex(ValueError,'blend savings'):M.read_case(log)

    def test_gpu_uses_its_own_sample_count_and_failed_loads_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'gpu.log'
            line='near-camera: camera=6 zone=near_middle frames={} avg_us=17000 worst_us=25000 over20=1 over30=0 '
            log.write_text((line.format(600)+'gpu_supported=1 gpu_samples=2 gpu_avg_us=12000 gpu_worst_us=15000\n')+
                           (line.format(1200)+'gpu_supported=1 gpu_samples=6 gpu_avg_us=16000 gpu_worst_us=18000\n')+
                           'realface-load: v42 native_id=34493 face_resolved=0 hair_component=1 hair_resolved=1\n')
            report=M.read_case(log);group=report['groups'][0]
            self.assertEqual(group['gpu_samples'],8)
            self.assertEqual(group['gpu_mean_stream_us'],15000)
            self.assertEqual(group['gpu_worst_stream_us'],18000)
            self.assertEqual(report['unresolved_face_loads'][0]['native_id'],34493)
            self.assertEqual(report['unresolved_hair_loads'],[])
            log.write_text(line.format(600)+'gpu_supported=0 gpu_samples=0 gpu_avg_us=0 gpu_worst_us=0\n')
            self.assertIsNone(M.read_case(log)['groups'][0]['gpu_mean_stream_us'])
            log.write_text(line.format(600)+'gpu_supported=0 gpu_samples=1 gpu_avg_us=100 gpu_worst_us=200\n')
            with self.assertRaisesRegex(ValueError,'GPU'):M.read_case(log)

    def test_overlapping_reports_weighting_and_unknown_percentiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'test.log'
            log.write_text('frame pacing: v33 time=DAY frames=200 avg_us=20000 worst_us=30000 over20ms=5 over30ms=0\n'
                           'near-camera: v32 camera=134 zone=near_middle frames=100 avg_us=16000 worst_us=25000 over20=5 over30=0\n'
                           'near-camera: v32 camera=134 zone=near_middle frames=300 avg_us=18000 worst_us=35000 over20=60 over30=3\n')
            result = M.read_case(log)
            self.assertEqual(result['ignored_overlapping_whole_play'], 1)
            group = result['groups'][0]
            self.assertEqual(group['frames'], 400)
            self.assertEqual(group['mean_interval_us'], 17500)
            self.assertEqual(group['over20_percent'], 16.25)
            self.assertIsNone(group['max_window_p95_upper_us'])
            self.assertFalse(group['sufficient_frames'])

    def test_mismatched_camera_and_invalid_counts_cannot_approve_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a.log', Path(tmp) / 'b.log'
            line = 'near-camera: camera={} frames=600 avg_us=16667 worst_us=18000 over20=0 over30=0\n'
            a.write_text(line.format(6)); b.write_text(line.format(134))
            self.assertEqual(M.compare({'native': a, 'face': b})['comparisons'], [])
            b.write_text(line.format(6))
            result = M.compare({'native': a, 'face': b})
            self.assertFalse(result['comparisons'][0]['comparable_context_and_sample_size'])
            self.assertIsNone(result['triangle_budget_recommendation'])
            b.write_text('frame pacing: frames=10 avg_us=16000 worst_us=18000 over20ms=11 over30ms=0')
            with self.assertRaises(ValueError): M.read_case(b)

    def test_quantile_bounds_never_averaged_and_day_night_kept_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / 'test.log'
            log.write_text('frame pacing: time=DAY frames=100 avg_us=17000 worst_us=30000 over20ms=1 over30ms=0 p95_upper_us=18000\n'
                           'frame pacing: time=DAY frames=200 avg_us=17000 worst_us=30000 over20ms=2 over30ms=0 p95_upper_us=25000\n'
                           'frame pacing: time=NIGHT frames=100 avg_us=16000 worst_us=17000 over20ms=0 over30ms=0\n')
            rows = M.read_case(log)['groups']
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['max_window_p95_upper_us'], 25000)
            self.assertEqual(rows[0]['frames'], 300)
            self.assertEqual(rows[1]['frames'], 100)


if __name__ == '__main__': unittest.main()
