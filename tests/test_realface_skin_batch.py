import copy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import realface_skin_batch as batch


PALETTE = {i: [240-i*25, 210-i*25, 190-i*25] for i in range(1,7)}


def test_consistent_neck_selects_review_only_and_large_mismatch():
    result = batch.classify([PALETTE[5]]*3, PALETTE, 1)
    assert result['status']=='review_candidate'
    assert result['nearest_skin']==5
    assert not result['automatic_patch']


def test_nearest_default_and_split_swatches_never_silently_patch():
    assert batch.classify([PALETTE[3]]*3, PALETTE, 3)['status']=='already_nearest'
    assert batch.classify([PALETTE[3]]*3, PALETTE, 7)['status']=='held_measurement'
    result=batch.classify([PALETTE[1], PALETTE[6], PALETTE[6]], PALETTE, 1)
    assert result['status']=='held_measurement'


def test_duplicate_native_owner_and_missing_palette_rejected():
    with pytest.raises(ValueError, match='Duplicate identity'):
        batch.unique([dict(native_player_id=1),dict(native_player_id=1)],'native_player_id')
    with pytest.raises(ValueError, match='six native palettes'):
        batch.classify([PALETTE[1]]*3, {1:PALETTE[1]}, 1)


def test_null_base_ids_are_not_asset_owners_but_native_collision_still_fails():
    state=dict(identities={str(i):dict(base_id=base,native_player_id=i,status='active')
                           for i,base in ((1,None),(2,None),(3,123))})
    assert set(batch.canonical_owners(state))=={123}
    state['identities']['2']['native_player_id']=3
    with pytest.raises(ValueError,match='Duplicate identity'):
        batch.canonical_owners(state)


@pytest.mark.parametrize('field,value',[('base_id',2),('native_player_id',2),('fingerprint','reused-slot')])
def test_profile_must_match_validated_head_and_canonical_owner(tmp_path,field,value):
    row=dict(base_id=1,native_player_id=10,fingerprint='owner',status='validated',folder=str(tmp_path))
    owner={**row,'status':'active'}
    profile={k:row[k] for k in ('base_id','native_player_id','fingerprint')}
    (tmp_path/'ue-profile.json').write_text(json.dumps(profile))
    assert batch.checked_profile(row,owner)[1]==profile
    changed=copy.deepcopy(profile);changed[field]=value
    (tmp_path/'ue-profile.json').write_text(json.dumps(changed))
    with pytest.raises(ValueError,match='identity disagree'):
        batch.checked_profile(row,owner)
