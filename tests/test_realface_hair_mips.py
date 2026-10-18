from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_hair_mips import protect_payloads


def test_only_discarded_tiny_alpha_changes_and_rerun_is_idempotent():
    base=bytes((1,2,3,200))*16
    small=bytes((4,5,6,60,7,8,9,0,10,11,12,30,13,14,15,0))
    last=bytes((16,17,18,40))
    source=[base,small,last]
    result,proof=protect_payloads(source,[(4,4),(2,2),(1,1)])
    assert result[0]==base and [r['index'] for r in proof['changed_mips']]==[1,2]
    for old,new in zip(source,result):
        assert len(old)==len(new)
        assert all(old[i]==new[i] for i in range(len(old)) if i%4!=3 or old[i]==0)
    assert max(result[1][3::4])==86 and result[2][3]==86
    assert protect_payloads(result,[(4,4),(2,2),(1,1)])[0]==result
    assert protect_payloads(result,[(4,4),(2,2),(1,1)])[1]['changed_mips']==[]


def test_empty_placeholder_stays_empty_and_large_or_unknown_loss_is_held():
    empty=[bytes((1,2,3,0))*16,bytes((1,2,3,0))]
    assert protect_payloads(empty,[(4,4),(1,1)])[0]==empty
    visible=bytes((1,2,3,255))*64
    with pytest.raises(ValueError,match='bounded'):
        protect_payloads([visible,bytes((1,2,3,30))*16],[(8,8),(4,4)])
    with pytest.raises(ValueError,match='bounded'):
        protect_payloads([visible,bytes(4)],[(8,8),(1,1)])
