import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import realface_native_hair_validate as validation


def setup(monkeypatch):
    owner=dict(base_id=1,native_player_id=9,fingerprint='identity',name='Authored player')
    row=dict(owner,status='candidate_visual_hold',composite_geometry_pass=True,
             recipe_source_sha256={'authored.py':'code'},cache_key='one',folder='candidate')
    canonical=dict(owner,status='prepared')
    documents={Path('owners'):[owner],Path('canonical/prepare-report.json'):[canonical],
               Path('trial/trial-report.json'):[row]}
    monkeypatch.setattr(validation,'read',lambda p:documents[Path(p)])
    monkeypatch.setattr(validation,'CODE',('authored.py',))
    monkeypatch.setattr(validation,'sha',lambda p:'code')
    monkeypatch.setattr(validation,'valid_cache',lambda *args:True)
    return dict(source_profiles='owners',work_dir='canonical'),row,canonical,documents


def test_only_current_identity_matched_candidate_enters_cook(monkeypatch):
    cfg,row,canonical,docs=setup(monkeypatch)
    result=validation.candidates(cfg,['trial'])
    assert len(result)==1 and result[0]['status']=='prepared'
    assert row['status']=='candidate_visual_hold'
    row['status']='held_composite_geometry'
    assert validation.candidates(cfg,['trial'])==[]


def test_accepted_heads_stale_recipe_and_identity_changes_stay_out(monkeypatch):
    cfg,row,canonical,docs=setup(monkeypatch)
    canonical['reuse_cooked']=True
    with pytest.raises(ValueError,match='accepted inherited'):validation.candidates(cfg,['trial'])
    canonical.pop('reuse_cooked');row['fingerprint']='different'
    with pytest.raises(ValueError,match='identity differs'):validation.candidates(cfg,['trial'])
    row['fingerprint']='identity';row['recipe_source_sha256']={}
    with pytest.raises(ValueError,match='older geometry'):validation.candidates(cfg,['trial'])


def test_changed_bytes_and_conflicting_recipes_never_share_a_cook(monkeypatch):
    cfg,row,canonical,docs=setup(monkeypatch)
    monkeypatch.setattr(validation,'valid_cache',lambda *args:False)
    with pytest.raises(ValueError,match='bytes or geometry'):validation.candidates(cfg,['trial'])
    monkeypatch.setattr(validation,'valid_cache',lambda *args:True)
    docs[Path('other/trial-report.json')]=[dict(row,cache_key='different')]
    with pytest.raises(ValueError,match='one native hair candidate'):validation.candidates(cfg,['trial','other'])
