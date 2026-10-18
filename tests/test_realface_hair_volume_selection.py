import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_league_hair_volume import select


def test_failed_hair_retry_preserves_existing_successes_and_empty_selection():
    owners={i:dict(base_id=i,native_player_id=i,fingerprint=str(i)) for i in (1,2)}
    held=[dict(owners[i],status='held_geometry') for i in (1,2)]
    prepared={1:dict(owners[1],status='prepared')}
    assert select(owners,prepared,held=held)=={2}
    assert select(owners,prepared,held=[])==set()
    assert select(owners,prepared,players=[1])=={1}


def test_trial_cannot_replace_accepted_or_unverified_identity():
    owner=dict(base_id=1,native_player_id=9,fingerprint='verified')
    with pytest.raises(ValueError,match='inherited'):
        select({1:owner},{1:dict(owner,reuse_cooked=True)},players=[1])
    with pytest.raises(ValueError,match='verified'):
        select({1:owner},{},players=[2])
    with pytest.raises(ValueError,match='identity differs'):
        select({1:owner},{},held=[dict(owner,fingerprint='changed',status='held_geometry')])
