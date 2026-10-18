import copy
import sys
from pathlib import Path

import pytest
import json

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_league_mobile import allocations
from realface_league_mobile_release import validate_rows


def test_hair_budget_accounts_for_eyes_retained_above_the_requested_target():
    from blender_realface_league_worker import remaining_hair_budget
    budget=dict(face_skin=1600,eye=128,hair=260,head_cap=2000)
    # Eye enclosure can retain extra triangles. Spend only the true remainder.
    effective=remaining_hair_budget(budget,1812)
    assert effective['hair']==188
    assert budget['hair']==260
    assert remaining_hair_budget(budget,1700)['hair']==260
    with pytest.raises(ValueError,match='Face exceeds complete head cap'):
        remaining_hair_budget(budget,2000)


def test_every_fallback_keeps_face_priority_and_complete_head_ceiling():
    for budget in allocations():
        assert budget['face_skin']+budget['eye']+budget['hair'] <= 2000
        assert budget['head_cap']==2000
        assert budget['face_skin']>budget['hair']
        assert budget['skin_feature_policy']
    assert allocations()[0]['hair_mode']=='shell'


def test_unverified_missing_or_reused_owner_cannot_enter_league_package():
    source={1:dict(base_id=1,native_player_id=2,fingerprint='a')}
    row=dict(source[1],status='validated',budgets={},recipe_source_sha256={'test':'current'})
    current=lambda budget:{'test':'current'}
    validate_rows([row],source,{},current)
    for key,value in [('fingerprint','wrong'),('status','held_geometry'),('recipe_source_sha256',{'test':'old'})]:
        changed=dict(row,**{key:value})
        with pytest.raises(ValueError): validate_rows([changed],source,{},current)
    with pytest.raises(ValueError): validate_rows([],source,{},current)
    with pytest.raises(ValueError): validate_rows([row,row],source,{},current)


def test_historical_reuse_requires_exact_accepted_cache_and_release():
    row=dict(base_id=1,native_player_id=2,fingerprint='a',status='validated',cache_key='prepared',
             cooked_cache_key='cooked',inherited_release_sha256='accepted')
    validate_rows([row],{1:row},{1:row},lambda budget:pytest.fail('Do not relabel historical code'))
    changed=dict(row,cooked_cache_key='other')
    with pytest.raises(ValueError):validate_rows([changed],{1:row},{1:row},lambda budget:{})


def test_rejected_visuals_block_package_before_assets_are_staged(tmp_path,monkeypatch):
    import realface_league_mobile_release as release
    (tmp_path/'verify-report.json').write_text('[]')
    (tmp_path/'QUALITY-HOLD.json').write_text(json.dumps({'approved':False,
        'reason':'User rejected the simplified hairstyle'}))
    monkeypatch.setattr(release,'sources',lambda config:pytest.fail('Must stop before collecting assets'))
    with pytest.raises(ValueError,match='visual regression unresolved'):
        release.package({'work_dir':str(tmp_path)})
    assert not (tmp_path/'releases').exists()


def test_strict_import_adapter_flushes_bounded_groups_before_cook(tmp_path,monkeypatch):
    import realface_league_cook as adapter
    from realface_mobile import PROFILE_POLICY
    player=tmp_path/'player';player.mkdir()
    (player/'simplification.json').write_text(json.dumps({'total_triangles':1988}))
    (player/'ue-profile.json').write_text(json.dumps(PROFILE_POLICY))
    (tmp_path/'prepare-report.json').write_text(json.dumps([{'status':'prepared','folder':str(player)}]))
    events=[]
    def imported(conf,project,batch,profiles,index):events.append(('import',len(profiles),index))
    def commanded(args,log):events.append(('cook',))
    def cooked(config):
        for index,count in enumerate([32,32,32,32,5]):
            adapter.factory.import_chunk(config,'project','batch',list(range(count)),index)
        adapter.factory.command(['editor','-run=cook'],'log')
        return 'done'
    monkeypatch.setattr(adapter.factory,'import_chunk',imported)
    monkeypatch.setattr(adapter.factory,'command',commanded)
    monkeypatch.setattr(adapter.factory,'cook',cooked)
    assert adapter.cook({'work_dir':str(tmp_path)})=='done'
    assert events==[('import',128,0),('import',5,4),('cook',)]
    assert adapter.factory.import_chunk is imported
    (player/'simplification.json').write_text(json.dumps({'total_triangles':2001}))
    with pytest.raises(ValueError):adapter.cook({'work_dir':str(tmp_path)})


def test_old_completion_marker_cannot_finish_a_new_follow_queue(tmp_path):
    from realface_league_cook_queue import preparation_finished
    assert not preparation_finished(tmp_path)
    (tmp_path/'prepare-complete.json').write_text(json.dumps({'run_id':'old'}))
    (tmp_path/'prepare-running.json').write_text(json.dumps({'run_id':'new'}))
    assert not preparation_finished(tmp_path)
    (tmp_path/'prepare-complete.json').write_text(json.dumps({'run_id':'new'}))
    assert preparation_finished(tmp_path)
