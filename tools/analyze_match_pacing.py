"""Compare saved Switch timings, with optional sampled GPU stream spans.

Example: --case native=baseline.log --case face=face.log --output comparison.json
Use the same diagnostic NRO, lineup, camera, stadium, weather and sequence.
The tool never installs assets or infers a triangle sweet spot from static counts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

FIELDS = ('stadium', 'day', 'weather', 'season', 'quality', 'home', 'away', 'camera', 'zone', 'viewport')


def read_case(path, allow_partial=False):
    data = Path(path).read_bytes()
    rows = []
    face_loads = []
    render_control = None
    sessions = []
    compile_failures, link_failures, quality_policies = [], [], []
    for line in data.decode('utf-8-sig', errors='replace').splitlines():
        session = re.fullmatch(r'FootballNX scene v(\d+) session', line)
        if session:
            sessions.append(int(session[1]))
        if line.startswith('GL compile failed:'):
            compile_failures.append(line.partition(':')[2].strip())
        if line.startswith('GL link failed:'):
            link_failures.append(line.partition(':')[2].strip())
        if line.startswith('model quality:'):
            quality_policies.append(line.partition(':')[2].strip())
        if line.startswith('render control:'):
            mode=re.search(r'state_cache=(enabled|bypassed)\b',line)
            if mode: render_control=mode[1]
        if line.startswith('realface-load:'):
            values=dict(re.findall(r'(\w+)=(\d+)',line))
            face_loads.append({k:int(v) for k,v in values.items()})
        if not line.startswith(('near-camera:', 'frame pacing:')):
            continue
        # The explanatory suffix repeats "zone=camera target". Only parse
        # the measurement prefix; otherwise every genuine zone is overwritten
        # by the prose word "camera" and unlike regions are merged together.
        values = dict(re.findall(r'(\w+)=([^\s]+)', line.partition(' (')[0]))
        row = {k: int(v) if v.isdecimal() else v for k, v in values.items()}
        row['kind'] = 'zone' if line.startswith('near-camera:') else 'whole_play'
        row['over20'] = row.get('over20', row.get('over20ms'))
        row['over30'] = row.get('over30', row.get('over30ms'))
        for field in ('frames', 'avg_us', 'worst_us', 'over20', 'over30'):
            if not isinstance(row.get(field), int) or row[field] < 0:
                raise ValueError('Missing or invalid timing field: ' + field)
        if not row['frames'] or row['over30'] > row['over20'] or row['over20'] > row['frames']:
            raise ValueError('Invalid frame or threshold counts')
        if row['avg_us'] <= 0 or row['worst_us'] < row['avg_us']:
            raise ValueError('Invalid presentation interval')
        if 'blend_requests' in row or 'blend_skipped' in row:
            if (any(type(row.get(k)) is not int or row[k]<0 for k in ('blend_requests','blend_skipped')) or
                    row['blend_skipped']>row['blend_requests']):
                raise ValueError('Invalid blend savings counts')
        if 'gpu_samples' in row:
            if (row.get('gpu_supported') not in (0,1) or
                    any(not isinstance(row.get(k),int) or row[k]<0 for k in
                        ('gpu_samples','gpu_avg_us','gpu_worst_us')) or
                    (row['gpu_samples'] and (not row['gpu_supported'] or
                                            row['gpu_worst_us']<row['gpu_avg_us']))):
                raise ValueError('Invalid sampled GPU timing')
        rows.append(row)
    if not rows and not allow_partial:
        raise ValueError('No presentation measurements in ' + str(path))
    # Zone and whole-play reports overlap; never count both as distinct frames.
    preferred = [r for r in rows if r['kind'] == 'zone'] or rows
    groups = {}
    for row in preferred:
        key = tuple(str(row.get(k, 'unknown')) for k in FIELDS)
        if row['kind'] == 'whole_play':
            # Older journals lack day and camera. Keep DAY/NIGHT apart anyway.
            key = tuple(str(row.get('time', 'unknown')) if k == 'day' else v
                        for k, v in zip(FIELDS, key))
        groups.setdefault(key, []).append(row)
    summaries = []
    for key, group in groups.items():
        count = sum(r['frames'] for r in group)
        interval = sum(r['frames'] * r['avg_us'] for r in group) / count
        summary = dict(context=dict(zip(FIELDS, key)), frames=count, windows=len(group),
                       mean_interval_us=round(interval, 2),
                       presentation_rate_hz=round(1_000_000 / interval, 2),
                       over20_percent=round(100 * sum(r['over20'] for r in group) / count, 3),
                       over30_percent=round(100 * sum(r['over30'] for r in group) / count, 3),
                       worst_us=max(r['worst_us'] for r in group), sufficient_frames=count >= 600)
        for field in ('swap_us', 'render_span_us', 'draws_x10', 'submitted_elements',
                      'draw_cpu_us', 'upload_cpu_us', 'upload_bytes', 'mapped_bytes'):
            summary[field] = (round(sum(r[field] * r['frames'] for r in group) / count, 2)
                              if all(field in r for r in group) else None)
        gpu=[r for r in group if r.get('gpu_supported')==1 and r.get('gpu_samples',0)>0]
        samples=sum(r['gpu_samples'] for r in gpu)
        summary['gpu_samples']=samples
        summary['gpu_mean_stream_us']=(round(sum(r['gpu_avg_us']*r['gpu_samples'] for r in gpu)/samples,2)
                                       if samples else None)
        summary['gpu_worst_stream_us']=max((r['gpu_worst_us'] for r in gpu),default=None)
        summary['gpu_supported']=any(r.get('gpu_supported')==1 for r in group)
        # Outcomes are absolute counts across the window, not per-frame means.
        for field in ('map_calls','map_failures','unmap_calls','unmap_failures',
                      'gl_error_checks','gl_errors','blend_requests','blend_skipped'):
            summary[field]=(sum(r[field] for r in group) if all(field in r for r in group) else None)
        summary['first_gl_error']=next((r['first_gl_error'] for r in group if r.get('first_gl_error')),None)
        # Quantiles cannot be averaged. Report the worst per-window upper bound,
        # explicitly not an exact global percentile of the combined samples.
        for percent in (50, 95, 99):
            field = f'p{percent}_upper_us'
            summary['max_window_' + field] = (max(r[field] for r in group)
                                            if all(field in r for r in group) else None)
        summaries.append(summary)
    return dict(log=str(Path(path).resolve()), log_sha256=hashlib.sha256(data).hexdigest(),
                measurement_kind=preferred[0]['kind'] if preferred else 'unavailable', groups=summaries,
                timings_available=bool(preferred),
                raw_windows=preferred, ignored_overlapping_whole_play=len(rows)-len(preferred),
                face_loads=face_loads, state_cache=render_control,
                startup=dict(session_versions=sessions,
                             compile_failures=compile_failures,
                             link_failures=link_failures,
                             model_quality_policies=quality_policies,
                             shader_cache_hit_rate=None,
                             visibility_verified=False),
                unresolved_face_loads=[r for r in face_loads if r.get('face_resolved')==0],
                unresolved_hair_loads=[r for r in face_loads if r.get('hair_component') and r.get('hair_resolved')==0])


def compare(cases, allow_partial=False):
    if len(cases) != len(set(cases)):
        raise ValueError('Duplicate case names')
    loaded = {name: read_case(path,allow_partial=allow_partial) for name, path in cases.items()}
    grouped = {}
    for name, case in loaded.items():
        for group in case['groups']:
            key = tuple(group['context'][k] for k in FIELDS)
            grouped.setdefault(key, {})[name] = group
    comparisons = []
    for key, rows in grouped.items():
        if len(rows) < 2:
            continue
        complete = 'unknown' not in key and all(r['sufficient_frames'] for r in rows.values())
        comparisons.append(dict(context=dict(zip(FIELDS, key)), cases=rows,
                                comparable_context_and_sample_size=complete))
    return dict(cases=loaded, comparisons=comparisons,
                triangle_budget_recommendation=None,
                limitations=[
                    'GPU fields require supported, available, nondisjoint timestamp pairs; missing samples stay unknown.',
                    'GPU stream spans include idle gaps between submitted commands; they are not a pure GPU busy counter.',
                    'Other durations are presentation intervals and CPU driver calls.',
                    'Face load snapshots do not prove later visibility, material binding or animation correctness.',
                    'Zone is camera target, not ball position; V2 camera ID 134, native Stadium ID 6.',
                    'Verify identical NRO, lineup, active PAKs and play sequence separately.',
                    'Startup failure records do not measure disk-cache hits; an empty list does not prove visible or synchronized resources.',
                    'A 600-frame bucket is a minimum sample, not proof of repeatability or causation.',
                    'No polygon budget is chosen without controlled asset variants and visual review.',
                ])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', action='append', required=True, metavar='NAME=LOG')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--allow-partial',action='store_true',
                   help='Keep load-only cases explicitly unavailable; never invent timings')
    args = p.parse_args()
    cases = {}
    for value in args.case:
        name, separator, path = value.partition('=')
        if not separator or not name or not path or name in cases:
            p.error('Each case requires a unique NAME=LOG')
        cases[name] = Path(path)
    report = compare(cases,allow_partial=args.allow_partial)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(args.output), cases=len(cases), comparisons=len(report['comparisons']))))


if __name__ == '__main__':
    main()
