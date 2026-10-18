from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import package_realface_runtime_probe as M


def test_retiring_entrance_does_not_whitelist_another_changed_scene(tmp_path,monkeypatch):
    base=tmp_path/'native';other=tmp_path/'canary';other.write_bytes(b'local synthetic canary')
    native={M.TABLE:b'native table','common/demo/fixdemo/end/table_end.bin':b'unchanged ending'}
    current={**native,M.TABLE:b'entrance canary',
             'common/demo/anime/FoxAnim/FixDemo/Animations/dml_ent_test.gani':b'new motion'}
    class Fake:
        def __init__(self,path):self.index=native if path==base else current
        def read(self,name):return self.index[name]
    monkeypatch.setattr(M,'Cpk',Fake)
    monkeypatch.setattr(M,'parse_scene_table',lambda data,kind:dict(scenes=[dict(name='NX_WALKOUT_CANARY_V1')]))
    assert M.entrance_only_canary(base,other)==M.sha(other)
    current['common/demo/fixdemo/end/table_end.bin']=b'other agent trophy work'
    with pytest.raises(ValueError,match='unrelated native member'):M.entrance_only_canary(base,other)
    current['common/demo/fixdemo/end/table_end.bin']=native['common/demo/fixdemo/end/table_end.bin']
    current['common/demo/fixdemo/end/cup.fdc']=b'new trophy'
    with pytest.raises(ValueError,match='unrelated resource'):M.entrance_only_canary(base,other)
    del current['common/demo/fixdemo/end/cup.fdc'];del current['common/demo/fixdemo/end/table_end.bin']
    with pytest.raises(ValueError,match='omitted'):M.entrance_only_canary(base,other)
