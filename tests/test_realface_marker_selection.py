import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from realface_league_seam_recovery import marker_candidates
from realface_pipeline import sha


def prepared(tmp_path):
    source=tmp_path/'lite_skin-meshopt.json'
    source.write_text(json.dumps(dict(positions=[0,0,0,.005,0,0,0,.005,0],indices=[0,1,2]*24)))
    (tmp_path/'complete.json').write_text(json.dumps(dict(cache_key='prepared',outputs={source.name:sha(source)})))
    return dict(folder=str(tmp_path),cache_key='prepared',budgets={})


def test_no_repeat_after_verified_marker_policy(tmp_path):
    row=prepared(tmp_path)
    assert marker_candidates({10:row})=={10}
    row['budgets']['skin_marker_cleanup']=True
    assert marker_candidates({10:row})==set()
    assert marker_candidates({})==set()


def test_changed_geometry_cannot_enter_preselection(tmp_path):
    row=prepared(tmp_path)
    (tmp_path/'lite_skin-meshopt.json').write_text('{}')
    with pytest.raises(ValueError,match='immutable'):
        marker_candidates({10:row})
