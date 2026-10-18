"""Synthetic policy tests: no game motions or scene bytes are distributed."""
import copy
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from stage_entrance_walkout import (CORE_FILES, MOTION_PREFIX, build_walkout_table,
                                   validate_walkout_actors, validate_motion_path)
from fixdemo_scene_table import parse_scene_table, serialize_scene_table


def fixture():
    row = {"fade": 3, "fade_time": .5, "cut_id": 65537, "flags": 0,
           "signed_params": [0, 0, 0, 0], "human_changes": [], "tail_value": -1}
    terminal = copy.deepcopy(row)
    terminal["cut_id"] = 0
    native = {"version": 1, "kind": 1, "condition_count": 10, "file_count": 10,
              "cuts": [{"name": "TEST_NATIVE", "id": 65537, "variants": [
                  {"conditions": [256]+[0]*9, "files": ["test.fdc"]+[""]*9,
                   "flags": 0, "move_distance": 0., "human_mask": 1}]}],
              "scenes": [{"name": "TEST_NATIVE", "id": 65537, "cuts": [row,terminal]}],
              "has_controls": False, "control_condition_count": 0, "controls": []}
    donor = copy.deepcopy(native)
    donor["cuts"][0].update(name="ENT_012_CMN", id=65556)
    variant = donor["cuts"][0]["variants"][0]
    variant.update(files=list(CORE_FILES)+["extra_mob.fdc","extra_audi.fdc"]+[""]*5,
                   conditions=[7681,2816,256]+[0]*7, flags=0x1ffffff, human_mask=3)
    donor["scenes"][0]["name"] = "ENT_ANTH0_CMN"
    donor["scenes"][0]["cuts"][0].update(cut_id=65556,
        human_changes=[[3,1,0],[1,0,0],[4,12,0],[2,11,0]])
    return native, donor


def test_minimal_walkout_keeps_terminal_and_does_not_modify_input():
    native, donor = fixture()
    snapshot = copy.deepcopy((native,donor))
    result = build_walkout_table(native,donor)
    assert (native,donor) == snapshot
    assert result["scenes"][0]["id"] == 65537
    assert result["scenes"][0]["cuts"][-1] == native["scenes"][0]["cuts"][-1]
    assert result["scenes"][0]["cuts"][0]["human_changes"] == [[3,1,0],[1,0,0],[4,12,0],[2,11,0]]
    variant = result["cuts"][0]["variants"][0]
    assert variant["conditions"] == [256]+[0]*9
    assert variant["files"] == list(CORE_FILES)+[""]*7
    assert variant["human_mask"] == 3 and variant["flags"] == 0x1ffffff
    assert parse_scene_table(serialize_scene_table(result), 1) == result


@pytest.mark.parametrize("change", [
    lambda n,d: n.update(kind=7),
    lambda n,d: d.update(kind=7),
    lambda n,d: n.update(has_controls=True),
    lambda n,d: n["scenes"][0]["cuts"][-1].update(cut_id=1),
    lambda n,d: n["cuts"][0]["variants"][0].update(conditions=[257]+[0]*9),
    lambda n,d: d["cuts"][0]["variants"][0].update(human_mask=1),
    lambda n,d: d["cuts"][0]["variants"][0].update(flags=0),
    lambda n,d: d["cuts"][0]["variants"][0].update(files=["other.fdc"]*10),
    lambda n,d: d["scenes"][0]["cuts"][0].update(tail_value=7),
    lambda n,d: d["scenes"][0]["cuts"][0].update(human_changes=[]),
])
def test_unsupported_descriptors_are_refused(change):
    native, donor = fixture()
    change(native,donor)
    with pytest.raises(ValueError):
        build_walkout_table(native,donor)


def table(items, named):
    header = 4+12*len(items)
    data = bytearray(header)
    struct.pack_into("<I",data,0,len(items))
    for i,(kind,raw) in enumerate(items):
        offset = len(data)
        data.extend(raw)
        meta = len(data)
        data.extend(kind.encode()+b"\0" if named else bytes([kind,0]))
        struct.pack_into("<III",data,4+12*i,offset,len(raw),meta)
    return bytes(data)


def actor_fixture(ids=range(25), controllers=(23,24), bank=1, extra=False):
    records = [(4,struct.pack("<I",(bank<<16)|i)+bytes(360)) for i in ids]
    records += [(2,struct.pack("<I",i)+bytes(88)) for i in controllers]
    if extra: records.append((5,bytes(10)))
    return table([("common/demo/fixdemo/ent/cut_data/project_test.fdc",table(records,False))],True)


def test_all_native_requested_actors_are_required():
    validate_walkout_actors(actor_fixture())
    for invalid in (actor_fixture(ids=range(24)),actor_fixture(ids=[0]*25),
                    actor_fixture(controllers=(22,23)),actor_fixture(bank=2),
                    actor_fixture(extra=True)):
        with pytest.raises(ValueError):
            validate_walkout_actors(invalid)


def test_only_reviewed_entrance_motion_namespace_is_accepted():
    for stem in ("dml_ent_entering06_home01", "dml_ent_row01_judge02_lm_eyes_target"):
        path = MOTION_PREFIX + stem + ".gani"
        assert validate_motion_path(path) == path
    for path in ("common/demo/fixdemo/ent/test.gani", MOTION_PREFIX + "dml_end_test.gani",
                 MOTION_PREFIX + "dml_ent_test.seq", MOTION_PREFIX + "dml_ent_test/other.gani",
                 MOTION_PREFIX + "../dml_ent_test.gani"):
        with pytest.raises(ValueError):
            validate_motion_path(path)
