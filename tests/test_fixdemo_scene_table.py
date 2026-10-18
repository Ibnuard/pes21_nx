"""Synthetic (non-proprietary) FixDemo typed-stream schema regressions."""

import copy
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from fixdemo_scene_table import (  # noqa: E402
    TableError, parse_scene_table, select_scene, serialize_scene_table,
)


def table_fixture(kind=1):
    def cut_row(cut_id, end=False):
        return {"fade": 3, "fade_time": 0.5, "cut_id": 0 if end else cut_id,
                "flags": 0, "signed_params": [1, -1, 60, -30],
                "human_changes": [] if end else [[0, 1, 2]], "tail_value": -1}

    cut_id = kind << 16 | 1
    return {"version": 1, "kind": kind, "condition_count": 2, "file_count": 2,
            "cuts": [{"name": "PROJECT_TEST_CUT", "id": cut_id, "variants": [
                {"conditions": [256, 0], "files": ["project_test_cam.fdc", ""],
                 "flags": 0, "move_distance": 0.0, "human_mask": 1}]}],
            "scenes": [{"name": "PROJECT_TEST_SCENE", "id": cut_id,
                        "cuts": [cut_row(cut_id), cut_row(0, True)]}],
            "has_controls": False, "control_condition_count": 0, "controls": []}


@pytest.mark.parametrize("kind", [1, 7, 8, 9])
def test_roundtrip_supported_banks(kind):
    original = table_fixture(kind)
    raw = serialize_scene_table(original)
    decoded = parse_scene_table(raw, kind)
    assert decoded == original
    assert serialize_scene_table(decoded) == raw


def test_control_stream_roundtrip():
    original = table_fixture()
    original.update(has_controls=True, control_condition_count=2,
                    controls=[{"name": "PROJECT_CTRL", "id": 0x10001,
                               "variants": [{"conditions": [256, 0],
                                             "floats": [0.25, 1.0], "uints": [22]}]}])
    assert parse_scene_table(serialize_scene_table(original), 1) == original


def test_select_scene_remaps_only_dependencies_and_keeps_conditions():
    original = table_fixture()
    second_cut = copy.deepcopy(original["cuts"][0])
    second_cut.update(name="PROJECT_SECOND_CUT", id=0x10002)
    second_cut["variants"][0]["conditions"] = [300, 42]
    original["cuts"].append(second_cut)
    second_scene = copy.deepcopy(original["scenes"][0])
    second_scene.update(name="PROJECT_SECOND_SCENE", id=0x10002)
    second_scene["cuts"][0]["cut_id"] = 0x10002
    original["scenes"].append(second_scene)
    snapshot = copy.deepcopy(original)
    selected = select_scene(original, 0x10002)
    assert len(selected["cuts"]) == len(selected["scenes"]) == 1
    assert selected["cuts"][0]["name"] == "PROJECT_SECOND_CUT"
    assert selected["cuts"][0]["variants"][0]["conditions"] == [300, 42]
    assert selected["scenes"][0]["id"] == 0x10001
    assert selected["scenes"][0]["cuts"][0]["cut_id"] == 0x10001
    assert selected["scenes"][0]["cuts"][1]["cut_id"] == 0
    assert original == snapshot
    assert parse_scene_table(serialize_scene_table(selected), 1) == selected


def test_select_scene_refuses_unresolved_cross_bank_cut():
    original = table_fixture()
    original["scenes"][0]["cuts"][0]["cut_id"] = 0x70001
    with pytest.raises(TableError, match="cross-kind"):
        select_scene(original, 0x10001)
    with pytest.raises(TableError, match="does not exist"):
        select_scene(table_fixture(), 0x10009)


@pytest.mark.parametrize("kind", [7, 8, 9])
def test_non_entrance_selection_preserves_semantic_native_ids(kind):
    original = table_fixture(kind)
    base = kind << 16
    for index in (2, 3):
        cut = copy.deepcopy(original["cuts"][0])
        cut.update(name=f"PROJECT_CUT_{index}", id=base | index)
        original["cuts"].append(cut)
        scene = copy.deepcopy(original["scenes"][0])
        scene.update(name=f"PROJECT_SCENE_{index}", id=base | index)
        scene["cuts"][0]["cut_id"] = base | index
        original["scenes"].append(scene)
    result = select_scene(original, base | 3, name="PROJECT_SELECTED")
    assert result["scenes"][2]["id"] == base | 3
    assert result["scenes"][2]["name"] == "PROJECT_SELECTED"
    assert result["scenes"][2]["cuts"][0]["cut_id"] == base | 3
    assert result["cuts"][2] == original["cuts"][2]
    assert all(not row["cuts"] for row in result["scenes"][:2])
    assert all(not row["variants"] for row in result["cuts"][:2])
    assert parse_scene_table(serialize_scene_table(result), kind) == result


@pytest.mark.parametrize("mutation,match", [
    (lambda h: h.__setitem__(11, 0xFFFFFFFF), "bounds"),
    (lambda h: h.__setitem__(10, h[11]), "overlapping"),
    (lambda h: h.__setitem__(2, 0), "one scene-table block"),
])
def test_reject_bad_header(mutation, match):
    raw = bytearray(serialize_scene_table(table_fixture()))
    header = list(struct.unpack_from("<14I", raw))
    mutation(header)
    struct.pack_into("<14I", raw, 0, *header)
    with pytest.raises(TableError, match=match):
        parse_scene_table(raw, 1)


def test_reject_bad_strings_indices_and_block_count():
    raw = serialize_scene_table(table_fixture())
    header = struct.unpack_from("<14I", raw)
    bad = bytearray(raw)
    struct.pack_into("<I", bad, header[9], 999999)
    with pytest.raises(TableError, match="block read count"):
        parse_scene_table(bad, 1)
    bad = bytearray(raw)
    struct.pack_into("<I", bad, header[8], 0xFFFFFFFF)
    with pytest.raises(TableError, match="string"):
        parse_scene_table(bad, 1)
    bad = bytearray(raw)
    # Version, cut count, then the first cut's variant-array start.
    struct.pack_into("<H", bad, header[11] + 4, 999)
    with pytest.raises(TableError, match="index exceeds"):
        parse_scene_table(bad, 1)


@pytest.mark.parametrize("size", [0, 8, 55])
def test_reject_truncated_header(size):
    with pytest.raises(TableError, match="size"):
        parse_scene_table(bytes(size), 1)


@pytest.mark.parametrize("kind", [0, 2, 3, 6, 10, -1, 256])
def test_reject_unimplemented_kinds(kind):
    with pytest.raises(TableError, match="supported"):
        parse_scene_table(serialize_scene_table(table_fixture()), kind)


@pytest.mark.parametrize("case", ["condition", "file", "changes", "nan", "signed", "id"])
def test_writer_rejects_mobile_abi_overflow(case):
    table = table_fixture()
    variant = table["cuts"][0]["variants"][0]
    if case == "condition":
        table["condition_count"] = 11
        variant["conditions"] = [0] * 11
    elif case == "file":
        table["file_count"] = 11
        variant["files"] = [""] * 11
    elif case == "changes":
        table["scenes"][0]["cuts"][0]["human_changes"] = [[0, 0, 0]] * 11
    elif case == "nan":
        variant["move_distance"] = float("nan")
    elif case == "signed":
        table["scenes"][0]["cuts"][0]["signed_params"][0] = 128
    else:
        table["cuts"][0]["id"] = 0x10002
    with pytest.raises(TableError):
        serialize_scene_table(table)


def test_terminal_scene_kept_and_no_descriptor_activation():
    table = table_fixture(7)
    result = parse_scene_table(serialize_scene_table(select_scene(table, 0x70001)), 7)
    assert result["scenes"][0]["cuts"][-1]["cut_id"] == 0
    # A decoder has no runtime side effects and never calls a native factory.
    assert "enabled" not in result
