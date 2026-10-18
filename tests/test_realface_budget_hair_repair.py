from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_budget_hair_repair import facial_hair_count,merge_rows


def test_native_region_excludes_scalp_and_rear_long_hair():
    assert facial_hair_count(dict(positions=[0,7,165,1,7,165,0,7,166,
        0,7,177,1,7,177,0,7,178,0,-7,165,1,-7,165,0,-7,166],
        indices=list(range(9))))==1


def test_held_repair_does_not_resurrect_bad_old_head_or_change_identity():
    old=dict(base_id=1,native_player_id=10,fingerprint='a',cache_key='x',status='prepared')
    proof=dict(old,status='validated',cooked_folder='c',cooked_cache_key='k')
    assert merge_rows([old],[],[proof])[0]['reuse_cooked']['cooked_cache_key']=='k'
    held=dict(old,status='held_geometry',cache_key='y')
    assert merge_rows([old],[held],[proof])[0]['status']=='held_geometry'
    with pytest.raises(ValueError,match='identity'):
        merge_rows([old],[dict(held,fingerprint='b')],[proof])
    with pytest.raises(ValueError,match='outside'):
        merge_rows([old],[dict(held,base_id=2)],[proof])
