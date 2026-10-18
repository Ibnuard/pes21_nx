import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_hair_alpha_cleanup import alpha_bound, invisible_bindings
from realface_native_hair_recover import eligible
import realface_native_hair_recover as recovery
from realface_native_hair_precompute import next_job
from realface_batch_inventory import read, write


def test_uv_wrap_and_bilinear_neighbours_cannot_hide_visible_texel():
    alpha = np.zeros((16, 16)); alpha[8, 15] = 1.
    uv = np.asarray([[0., .5], [.01, .5], [.01, .51]])
    assert alpha_bound(uv, alpha) == 1.
    alpha[8, 15] = 0.
    assert alpha_bound(uv, alpha) == 0.


def test_visible_or_resize_affected_bindings_remain_held():
    tri = [[0, 1, 2], [3, 4, 5]]
    uv = np.asarray([[[.2, .2], [.21, .2], [.2, .21]], [[.7, .7], [.71, .7], [.7, .71]]])
    weights = [{'sk_shoulder_l': .1, 'sk_head': .9}] * 6
    full = np.zeros((64, 64)); runtime = np.zeros((16, 16)); runtime[11, 11] = 1.
    removed, proof = invisible_bindings(tri, uv, weights, [full, runtime])
    assert list(removed) == [0]
    assert proof['potentially_visible_triangles'] == 1
    assert not proof['visible_source_geometry_changed']


def test_valid_head_triangles_are_never_selected_for_cleanup():
    removed, proof = invisible_bindings([[0, 1, 2]], np.zeros((1, 3, 2)),
        [{'sk_head': 1.}] * 3, [np.zeros((8, 8))])
    assert not len(removed) and proof['offending_triangles'] == 0


def test_cutoff_boundary_and_tiled_uv_are_conservative():
    alpha = np.zeros((8, 8)); alpha[3, 3] = 85 / 255
    uv = np.asarray([[0., 0.], [1000000., 0.], [0., 1000000.]])
    assert alpha_bound(uv, alpha) > .333
    with pytest.raises(ValueError, match='normalized'):
        alpha_bound(uv * np.nan, alpha)


def test_recovery_never_replaces_inherited_or_successful_heads():
    failed = dict(status='held_conversion', reason='ValueError: Source card binding is outside the audited head/neck chain')
    assert eligible(failed, {})
    assert not eligible(failed, dict(reuse_cooked=True))
    assert not eligible(dict(failed, status='candidate_visual_hold'), {})
    assert not eligible(dict(failed, reason='Other failure'), {})


def test_recovery_combines_only_passes_and_invalidates_replaced_cook_keys(monkeypatch, tmp_path):
    root = tmp_path / 'repo'; work = root / 'local-debug' / 'league'; canonical = root / 'canonical'
    monkeypatch.setattr(recovery, 'HERE', root / 'tools')
    faces = [dict(base_id=1, status='prepared'), dict(base_id=2, status='prepared', reuse_cooked=True),
             dict(base_id=3, status='prepared')]
    reason = 'Source card binding is outside the audited head/neck chain'
    rows = [dict(base_id=1, status='held_conversion', cache_key='old', reason=reason),
            dict(base_id=3, status='candidate_visual_hold', cache_key='unchanged', triangles=1900)]
    owners = [dict(base_id=i, name=str(i), profile='original') for i in (1, 2, 3)]
    write(work / 'coverage.json', dict(counts={'held_conversion': 1},
          players=[dict(base_id=i, name=str(i), team_ids=[8]) for i in (1, 2, 3)], teams=[dict(team_id=8)]))
    write(work / 'chosen-faces.json', faces); write(canonical / 'prepare-report.json', faces)
    write(work / 'trial-report.json', rows); write(work / 'owners.json', owners)
    write(work / 'verify-report.json', [dict(base_id=1, cache_key='old', status='held_geometry'),
          dict(base_id=3, cache_key='unchanged', status='validated')])
    monkeypatch.setattr(recovery, 'clean_source', lambda cfg, owner, *a: (dict(owner, profile='cleaned'), None))
    monkeypatch.setattr(recovery, 'convert', lambda *a: dict(base_id=1, status='candidate_visual_hold',
        cache_key='new', triangles=2000))
    cfg, out = recovery.recover(dict(work_dir=str(canonical), source_profiles=str(work / 'owners.json')), work)
    assert out != work and read(work / 'trial-report.json') == rows
    combined = {r['base_id']: r for r in read(out / 'trial-report.json')}
    assert combined[1]['cache_key'] == 'new' and combined[3]['cache_key'] == 'unchanged'
    assert [r['base_id'] for r in read(out / 'verify-report.json')] == [3]
    assert read(out / 'coverage.json')['counts']['accepted_v37_retained'] == 1
    assert read(cfg['source_profiles'])[0]['profile'] == 'cleaned'


def test_shape_recovery_does_not_offer_duplicate_effective_or_unbounded_allocations():
    assert recovery.shape_variants(1900) == []
    assert recovery.shape_variants(1800) == [(420, 2)]
    assert recovery.shape_variants(1728) == [(420, 2), (150, 3)]
    assert recovery.shape_variants(1400) == [(420, 2), (150, 3), (500, 3)]


def test_precompute_prioritizes_failed_bindings_and_never_replaces_accepted_heads():
    rows = [dict(base_id=1, status='held_composite_geometry', cache_key='shape'),
            dict(base_id=2, status='held_conversion', cache_key='binding',
                 reason='Source card binding is outside the audited head/neck chain'),
            dict(base_id=3, status='held_composite_geometry', cache_key='accepted')]
    faces = {1: {}, 2: {}, 3: dict(reuse_cooked=True)}
    assert next_job(rows, faces, {})['base_id'] == 2
    done = {2: dict(original_key='binding')}
    assert next_job(rows, faces, done)['base_id'] == 1
    done[1] = dict(original_key='shape')
    assert next_job(rows, faces, done) is None
    rows[0]['cache_key'] = 'changed'
    assert next_job(rows, faces, done)['base_id'] == 1
