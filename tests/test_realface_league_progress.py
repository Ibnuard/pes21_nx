from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_league_progress import summarize


def fixture():
    owner=dict(base_id=12,native_player_id=44,fingerprint='owner-a',name='Player',team_ids=[7],status='candidate_pending_device')
    prep=dict(owner,status='prepared',cache_key='new',budgets={},triangles=1998,recipe_source_sha256={'code':'current'})
    return owner,prep


def test_stale_cook_cannot_cover_a_new_preparation():
    owner,prep=fixture();old=dict(prep,status='validated',cache_key='old')
    report=summarize([owner],{12},[('recovery',[prep],[old])],lambda _: {'code':'current'})
    row=report['players'][0]
    assert row['stage']=='cook_pending' and row['historical_cook_pass']
    assert row['visual_review']=='pending'


def test_current_cooked_pass_is_not_visual_acceptance():
    owner,prep=fixture();verified=dict(prep,status='validated')
    report=summarize([owner],{12},[('current',[prep],[verified])],lambda _: {'code':'current'})
    assert report['counts']=={'cooked_needs_visual_review':1}
    assert report['players'][0]['visual_review']=='pending'
    stale=summarize([owner],{12},[('old',[prep],[verified])],lambda _: {'code':'changed'})
    assert stale['counts']=={'recipe_changed':1}


def test_failed_recovery_does_not_erase_historical_pass_or_claim_current_coverage():
    owner,prep=fixture();old=dict(prep,cache_key='old',status='validated')
    held=dict(prep,status='held_cook_validation',reason='normal mismatch')
    report=summarize([owner],{12},[('old',[dict(prep,cache_key='old')],[old]),
        ('recovery',[prep],[held])],lambda _: {'code':'current'})
    assert report['historical_cook_passes']==1
    assert report['current_cook_passes']==0
    assert report['players'][0]['historical_cook_pass']
    assert report['players'][0]['stage']=='held_cook_validation'


def test_stale_overlay_cannot_replace_current_mesh_and_matching_cook():
    owner,prep=fixture();old=dict(prep,cache_key='old',recipe_source_sha256={'code':'old'})
    report=summarize([owner],{12},[('current',[prep],[dict(prep,status='validated')]),
        ('stale-recovery',[old],[dict(old,status='validated')])],lambda _: {'code':'current'})
    assert report['counts']=={'cooked_needs_visual_review':1}
    assert report['players'][0]['cache_key']=='new'


def test_overlay_preserves_identity_and_rejects_duplicates_and_over_budget():
    owner,prep=fixture()
    with pytest.raises(ValueError,match='identity'):
        summarize([owner],{12},[('wrong',[dict(prep,fingerprint='another-owner')],[])])
    with pytest.raises(ValueError,match='Duplicate'):
        summarize([owner],{12},[('duplicate',[prep,prep],[])])
    with pytest.raises(ValueError,match='triangle'):
        summarize([owner],{12},[('large',[dict(prep,triangles=2001)],[])],lambda _: {'code':'current'})


def test_missing_source_and_accepted_release_remain_distinct():
    owner,prep=fixture();missing=dict(owner,base_id=13,status='missing_source')
    inherited=dict(prep,reuse_cooked={'cooked_cache_key':'pinned'},inherited_release_sha256='accepted')
    report=summarize([owner,missing],{12},[('accepted',[inherited],[])])
    assert report['counts']=={'accepted_v37':1,'source_unresolved':1}


def test_failed_optional_trial_does_not_displace_an_earlier_cooked_candidate():
    from realface_league_progress import passing_trial
    owner,prep=fixture();current=lambda _: {'code':'current'}
    trial=dict(prep,status='held_geometry',cache_key='failed',reason='Missing hair coverage')
    selected,outcomes=passing_trial('trial',[trial],[],{12:owner},current)
    report=summarize([owner],{12},[('good',[prep],[dict(prep,status='validated')]),
        ('trial',selected,[])],current)
    assert report['players'][0]['cache_key']=='new'
    assert outcomes[0]['reason']=='Missing hair coverage' and not outcomes[0]['selected']
    selected,outcomes=passing_trial('passed',[prep],[dict(prep,status='validated')],{12:owner},current)
    assert selected==[prep] and outcomes[0]['selected']
    assert outcomes[0]['visual_review']=='pending'
    with pytest.raises(ValueError,match='identity'):
        passing_trial('wrong',[dict(trial,fingerprint='wrong')],[],{12:owner},current)
