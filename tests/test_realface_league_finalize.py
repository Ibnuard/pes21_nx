"""Hold recovery cannot remove visible hair or increase the permitted ceiling."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from realface_empty_slot_policy import verified_empty_slot
from realface_league_finalize import empty_recipe, recovery_allocation
import realface_budget_experiment as trial


def source():
    return dict(positions=[(0,4,174),(.05,4,174),(0,4.05,174)], triangles=[[0,1,2]],
                alpha_max=0, materials=['rf_hair_empty'], bindings=[{'sk_head':1.0}]*3)


def test_verified_existing_placeholder_keeps_geometry_and_binding():
    proof=verified_empty_slot(**source())
    assert not proof['geometry_replaced'] and not proof['visible_source_removed'] and not proof['binding_changed']


@pytest.mark.parametrize('changes',[
    {'materials':['rf_hair']}, {'alpha_max':.01}, {'triangles':[[0,1,2],[0,1,2]]},
    {'positions':[(0,4,174),(1,4,174),(0,5,174)]},
    {'positions':[(0,40,174),(.05,40,174),(0,40.05,174)]},
    {'bindings':[{'sk_neck':1.0}]*3}, {'positions':[(0,4,174),(.05,4,174),(0,float('nan'),174)]}])
def test_empty_slot_policy_rejects_visible_unproven_or_moved_surface(changes):
    with pytest.raises(ValueError):
        verified_empty_slot(**dict(source(),**changes))


@pytest.mark.parametrize('cap',[5000,7000])
@pytest.mark.parametrize('skin',[3000,2800,2600])
def test_recovery_only_redistributes_the_existing_complete_head_allowance(cap,skin):
    override=recovery_allocation(cap,skin,True)
    config=dict(experimental_head_cap=cap,experimental_allocations={'1':override})
    budget=trial.effective_allocation(config,1)
    assert budget['face_skin']+budget['eye']+budget['hair']+20==cap
    assert budget['hair_face_lock'] and budget['hair_error_cm']==.45
    assert budget['skin_error_cm']==trial.allocation(cap)['skin_error_cm']


def test_empty_recipe_is_separately_fingerprinted_and_restored_on_error():
    old_allocation,old_code=trial.effective_allocation,trial.recipe_code
    with pytest.raises(RuntimeError):
        with empty_recipe():
            budget=trial.effective_allocation({'experimental_head_cap':5000},1)
            assert budget['verified_empty_hair_slot']
            code=trial.recipe_code(budget)
            assert 'realface_empty_slot_policy.py' in code and 'blender_realface_empty_budget_worker.py' in code
            raise RuntimeError('synthetic interruption')
    assert trial.effective_allocation is old_allocation and trial.recipe_code is old_code


@pytest.mark.parametrize('result_status',['validated','held_import'])
def test_cook_resumes_failed_records_and_never_clears_them_for_preview(tmp_path,monkeypatch,result_status):
    import realface_league_finalize as finish
    import realface_batch_release as factory
    row=dict(base_id=1,status='prepared',cache_key='p')
    old=dict(base_id=1,status='held_import',reason='old compiler failed')
    verified={1:old};calls=[]
    monkeypatch.setattr(factory,'cook',lambda config:calls.append(config['work_dir']))
    monkeypatch.setattr(factory,'verify',lambda config,workers:[dict(row,status=result_status)])
    monkeypatch.setattr(finish,'validate_head',lambda row:None)
    if result_status=='validated':
        finish.cook_missing(dict(work_dir=str(tmp_path)),{1:row},verified)
    else:
        with pytest.raises(RuntimeError,match='lack independent cook validation'):
            finish.cook_missing(dict(work_dir=str(tmp_path)),{1:row},verified)
    assert len(calls)==1 and verified[1]['status']==result_status


@pytest.mark.parametrize('triangles,accepted', [(7000, True), (7001, False)])
def test_recovery_honours_inclusive_human_ceiling(tmp_path, monkeypatch, triangles, accepted):
    import realface_league_finalize as finish
    from types import SimpleNamespace
    profile = tmp_path / 'source.json'
    profile.write_text('{}')
    owner = dict(base_id=1, native_player_id=1, fingerprint='current', name='Test', profile=str(profile))
    old = dict(owner, status='held_geometry', cache_key='old',
               reason='Experimental complete head cap exceeded: 7100')
    rows = {1: old}
    monkeypatch.setattr(finish, 'PreparationProcess', lambda *a: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(finish, 'status', lambda *a, **kw: None)
    monkeypatch.setattr(finish, 'validate_head', lambda *a: None)
    monkeypatch.setattr(trial, 'prepare_one', lambda *a: dict(
        owner, status='prepared', triangles=triangles, cache_key='new', folder='scoped'))
    finish.recover(dict(work_dir=str(tmp_path), blender='unused'), rows, {}, {1: owner})
    assert (rows[1]['status'] == 'prepared') is accepted
