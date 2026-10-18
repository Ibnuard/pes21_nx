"""Synthetic table/record invariants; no game assets or disassembly fixtures."""
import builtins
import copy
import json
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage_trophy_ceremony as trophy
from entrance_scene_canary import FDC_PREFIX, inspect_fdc, payload, table_entries
from fixdemo_scene_table import parse_scene_table, serialize_scene_table


@pytest.mark.parametrize("passed", [False, True])
def test_cli_requested_decoder_failure_is_not_a_success(monkeypatch, capsys, passed):
    monkeypatch.setattr(sys, "argv", ["stage_trophy_ceremony.py", "--fl26-root", "donor",
                                    "--mobile-root", "baseline", "--output", "candidate",
                                    "--sample-native-elf", "owned.so"])
    monkeypatch.setattr(trophy, "stage", lambda *args: {
        "status": "asset_only_not_playable", "payloads": [], "barriers": ["runtime pending"]})
    monkeypatch.setattr(trophy, "probe_trophy_motions", lambda *args: {
        "status": "sampled_motion_decode_passed" if passed else "sampled_motion_decode_incomplete",
        "sampled_pose_count": 69 if passed else 0,
        "gap": None if passed else "synthetic unavailable decoder"})
    if passed:
        trophy.main()
    else:
        with pytest.raises(SystemExit) as error:
            trophy.main()
        assert error.value.code == 1
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert rows[0]["status"] == "asset_only_not_playable"
    assert rows[1]["sampled_poses"] == (69 if passed else 0)


def tables():
    variant = {"conditions": [256] + [0] * 9, "files": ["project.fdc"] + [""] * 9,
               "flags": 1, "move_distance": 0., "human_mask": 1}
    row = {"fade": 3, "fade_time": .5, "cut_id": 0x70001, "flags": 0,
           "signed_params": [0] * 4, "human_changes": [], "tail_value": -1}
    terminal = dict(row, cut_id=0)
    native = {"version": 1, "kind": 7, "condition_count": 10, "file_count": 10,
              "cuts": [{"id": 0x70001 + i, "name": f"PROJECT_NATIVE_CUT_{i}",
                        "variants": [copy.deepcopy(variant)]} for i in range(4)],
              "scenes": [{"id": 0x70001 + i, "name": f"PROJECT_NATIVE_SCENE_{i}",
                          "cuts": [dict(row, cut_id=0x70001 + i), terminal.copy()]}
                         for i in range(2)],
              "has_controls": True, "control_condition_count": 2,
              "controls": [{"id": 0x70001, "name": "PROJECT_NATIVE_CONTROL",
                            "variants": [{"conditions": [1, 2], "floats": [.25, 1.5],
                                          "uints": [7]}]}]}
    donor = copy.deepcopy(native)
    donor["cuts"] = [{"id": 0x70001 + i, "name": f"PROJECT_DONOR_CUT_{i}",
                      "variants": []} for i in range(43)]
    donor["scenes"] = [{"id": 0x70001 + i, "name": f"PROJECT_DONOR_SCENE_{i}",
                        "cuts": []} for i in range(7)]
    selected = dict(variant, conditions=[513, 16384, 256] + [0] * 7,
                    files=trophy.DONOR_FILES.copy(), flags=0x7FF, human_mask=3)
    donor["cuts"][-1].update(name=trophy.CUT_NAME, variants=[variant, selected])
    donor["scenes"][-1].update(name=trophy.SCENE_NAME, cuts=[
        dict(row, cut_id=trophy.CUT_ID, human_changes=[[1, 0, 0]],
             signed_params=[6, 0, 180, 0]), terminal.copy()])
    return native, donor


def test_append_preserves_ids_controls_native_endings_and_inputs():
    native, donor = tables()
    before = copy.deepcopy((native, donor))
    result = trophy.build_trophy_table(native, donor)
    assert (native, donor) == before
    assert result["cuts"][:4] == native["cuts"]
    assert result["scenes"][:2] == native["scenes"]
    assert result["controls"] == native["controls"]
    assert result["has_controls"] and result["control_condition_count"] == 2
    assert all(not row["variants"] for row in result["cuts"][4:42])
    assert all(not row["cuts"] for row in result["scenes"][2:6])
    assert result["cuts"][-1]["id"] == 0x7002B
    assert result["scenes"][-1]["id"] == 0x70007
    variant = result["cuts"][-1]["variants"][0]
    assert variant["flags"] == 0x7FF and variant["human_mask"] == 3
    assert variant["files"] == trophy.DONOR_FILES[:3] + [""] + trophy.DONOR_FILES[4:]
    assert variant["conditions"] == [256] + [0] * 9
    assert result["scenes"][-1]["cuts"][0]["human_changes"] == [[1, 0, 0]]
    assert result["scenes"][-1]["cuts"][0]["signed_params"] == [6, 0, 180, 0]
    assert parse_scene_table(serialize_scene_table(result), 7) == result


@pytest.mark.parametrize("change", [
    lambda n, d: n.update(kind=1),
    lambda n, d: n.update(condition_count=9),
    lambda n, d: n["cuts"][0].update(id=0x70002),
    lambda n, d: n.update(cuts=copy.deepcopy(d["cuts"])),
    lambda n, d: n.update(scenes=copy.deepcopy(d["scenes"])),
    lambda n, d: d["scenes"][-1].update(name="OTHER"),
    lambda n, d: d["cuts"][-1]["variants"][1].update(flags=0x87FF),
    lambda n, d: d["cuts"][-1]["variants"][1].update(human_mask=1),
    lambda n, d: d["cuts"][-1]["variants"][1]["files"].__setitem__(0, "end_trophy_01_cupintclub.fdc"),
    lambda n, d: d["scenes"][-1]["cuts"][0].update(human_changes=[[0, 0, 0]]),
    lambda n, d: d["scenes"][-1]["cuts"][0].update(tail_value=0),
    lambda n, d: d["scenes"][-1]["cuts"][-1].update(cut_id=trophy.CUT_ID),
])
def test_changed_layout_or_existing_target_id_fails_closed(change):
    native, donor = tables()
    change(native, donor)
    with pytest.raises(ValueError):
        trophy.build_trophy_table(native, donor)


def raw_table(items, named):
    data = bytearray(4 + 12 * len(items))
    struct.pack_into("<I", data, 0, len(items))
    for i, (key, raw) in enumerate(items):
        offset = len(data)
        data.extend(raw)
        metadata = len(data)
        data.extend(key.encode() + b"\0" if named else bytes([key, 0]))
        struct.pack_into("<III", data, 4 + 12 * i, offset, len(raw), metadata)
    return bytes(data)


def actor(size, word, refs=()):
    prefix = struct.pack("<I", word) + b"\0" * 16
    paths = b"".join(("cpk_dat/" + ref).encode() + b"\0" for ref in refs)
    assert len(prefix) + len(paths) <= size
    return (prefix + paths).ljust(size, b"\0")


def teammate_items():
    records, resources = [], []
    for i, stem in enumerate(trophy.TEAMMATE_STEMS):
        motion = trophy.MOTION_PREFIX + "dml_end_trophy01_" + stem
        records.append((4, actor(364, 0x10001 + i, (motion + ".gani", motion + ".seq"))))
        resources.extend([
            ("cpk_dat/" + motion + ".gani", b"\0" * 4),
            ("cpk_dat/" + motion + ".seq", struct.pack("<4I", 1, 0, i, 0)),
            ("cpk_dat/" + motion + "_eyes_target.gani", b"\0" * 4),
        ])
    for i in range(4):
        refs = (trophy.MOB_MODELS[1 if i in (0, 3) else 0], trophy.MOB_RESOURCES[1],
                trophy.MOB_RESOURCES[0 if i in (0, 3) else 2])
        records.append((5, actor(444, 0x10002 + i, refs)))
    resources.extend(("cpk_dat/" + name, b"\0" * 4) for name in trophy.MOB_RESOURCES)
    return records, resources


def teammate_fdc(records=None, resources=None):
    default_records, default_resources = teammate_items()
    return raw_table([
        ("cpk_dat/" + FDC_PREFIX + "end/cut_data/" + trophy.CORE_FILES[2],
         raw_table(default_records if records is None else records, False)),
        *(default_resources if resources is None else resources),
    ], True)


def test_only_trailing_mobs_and_their_resources_removed_without_reindexing():
    source = teammate_fdc()
    result, report = trophy.strip_trailing_suit_mobs(source)
    before = table_entries(source, named=True)
    after = table_entries(result, named=True)
    assert len(after) == 31
    assert [row.name for row in after] == [row.name for row in before[:31]]
    assert [payload(result, row) for row in after[1:]] == [payload(source, row) for row in before[1:31]]
    old_inner, new_inner = payload(source, before[0]), payload(result, after[0])
    old_records, new_records = table_entries(old_inner, named=False), table_entries(new_inner, named=False)
    assert len(new_records) == 10
    assert [payload(new_inner, row) for row in new_records] == [payload(old_inner, row) for row in old_records[:10]]
    assert inspect_fdc(result)["actor_id_words"]["4"] == list(range(1, 11))
    assert report["removed_record_ordinals"] == [10, 11, 12, 13]
    assert report["removed_resource_ordinals"] == [31, 32, 33]
    assert report["retained_record_and_resource_payloads_identical"]
    assert not report["native_sequence_execution_verified"]
    assert b"mob_low_su" not in result and b"dml_mobH" not in result


@pytest.mark.parametrize("case", ["record-order", "actor-id", "actor-bank", "object-id",
                                  "object-model", "extra-record", "resource-order",
                                  "embedded-mob", "retained-reference", "truncated"])
def test_unknown_indices_or_dependencies_are_never_filtered(case):
    records, resources = teammate_items()
    if case == "record-order": records[9], records[10] = records[10], records[9]
    elif case in ("actor-id", "actor-bank", "object-id"):
        i = 10 if case == "object-id" else 0
        word = 0x20001 if case == "actor-bank" else 0x10063
        records[i] = (records[i][0], struct.pack("<I", word) + records[i][1][4:])
    elif case == "object-model": records[10] = (5, records[10][1].replace(b"mob_low_su01b", b"mob_low_su09b"))
    elif case == "extra-record": records.append(records[-1])
    elif case == "resource-order": resources[29], resources[30] = resources[30], resources[29]
    elif case == "embedded-mob": resources[-1] = (resources[-1][0], b"unexpected")
    elif case == "retained-reference": resources[1] = (resources[1][0], (trophy.MOB_RESOURCES[0] + "\0").encode())
    raw = teammate_fdc(records, resources)
    if case == "truncated": raw = raw[:-1]
    with pytest.raises(ValueError):
        trophy.strip_trailing_suit_mobs(raw)


class SyntheticCpk:
    def __init__(self, members):
        self.members = members
        self.index = dict.fromkeys(members)
        self.path = Path("synthetic-owned.cpk")

    def read(self, name):
        return self.members[name]


def asset_sources():
    files = {trophy.CORE_FILES[2]: teammate_fdc()}
    captain_motion = trophy.MOTION_PREFIX + "dml_end_trophy01_cup_int.gani"
    skeleton = trophy.CHARACTER_PREFIX + "cup_anim_skel.ask"
    cup_motion = trophy.MOTION_PREFIX + "dml_end_trophy01_cup_int_cup_int_hi.gani"
    cup_records = [(2, actor(92, 0x1303E8)), (4, actor(364, 0x10000, (captain_motion,))),
                   (5, actor(444, 0x1006E, (trophy.PROP_MODELS[0], skeleton, cup_motion)))]
    files[trophy.CORE_FILES[0]] = raw_table([
        (FDC_PREFIX + "end/cut_data/" + trophy.CORE_FILES[0], raw_table(cup_records, False)),
        (captain_motion, b"\0" * 4), (cup_motion, b"\0" * 4), (skeleton, b"\0" * 4)], True)
    files[trophy.CORE_FILES[3]] = raw_table([
        (FDC_PREFIX + "end/cut_data/" + trophy.CORE_FILES[3],
         raw_table([(5, actor(444, 0x10190, (trophy.PROP_MODELS[1],)))], False))], True)
    files[trophy.CORE_FILES[1]] = raw_table([
        (FDC_PREFIX + "end/cut_data/" + trophy.CORE_FILES[1],
         raw_table([(0, bytes(64))], False))], True)
    members = {FDC_PREFIX + "end/cut_data/" + name: raw for name, raw in files.items()}
    gani = struct.pack("<8I", 0x0BFCA2D2, 32, 32, 0, 0, 1, 0, 0)
    for raw in files.values():
        for row in inspect_fdc(raw)["resources"]:
            if row["name"].endswith(".gani"):
                members[row["name"]] = gani
    for name in trophy.PROP_MODELS:
        parent, basename = name.rsplit("/", 1)
        members[parent + "/#Win/" + basename] = b"synthetic-model-not-mobile"
    members[skeleton] = b"synthetic-shared-skeleton"
    mobile = SyntheticCpk({skeleton: members[skeleton]})
    return SyntheticCpk(members), [mobile]


def test_reduced_dependency_closure_keeps_two_explicit_renderer_barriers():
    source, mobile = asset_sources()
    additions, reports, reduction = trophy.collect_payloads(source, mobile)
    assert not any("mob" in name or name.endswith(".fpk") for name in additions)
    assert not any(trophy.FX_FILE in name for name in additions)
    barriers = [row["name"] for report in reports for row in report["dependencies"]
                if row["resolution"] == "donor_platform_only"]
    assert set(barriers) == set(trophy.PROP_MODELS)
    assert reduction["removed_object_ids"] == [2, 3, 4, 5]


@pytest.mark.parametrize("case", ["missing-motion", "shared-drift", "ambiguous-mobile", "ambiguous-model"])
def test_dependency_mismatches_fail_closed(case):
    source, mobile = asset_sources()
    skeleton = trophy.CHARACTER_PREFIX + "cup_anim_skel.ask"
    if case == "missing-motion":
        del source.members[trophy.MOTION_PREFIX + "dml_end_trophy01_hug01.gani"]
    elif case == "shared-drift": mobile[0].members[skeleton] = b"different"
    elif case == "ambiguous-mobile": mobile.append(mobile[0])
    else:
        name = trophy.PROP_MODELS[0]
        parent, basename = name.rsplit("/", 1)
        source.members[parent + "/#Other/" + basename] = b"other"
    source.index = dict.fromkeys(source.members)
    with pytest.raises(ValueError):
        trophy.collect_payloads(source, mobile)


def test_failed_preflight_emits_only_a_barrier_report(tmp_path, monkeypatch):
    output = tmp_path / "detached"
    monkeypatch.setattr(trophy, "output_directory", lambda path: path)
    def unavailable(_):
        raise ValueError("optional owned baseline unavailable")
    monkeypatch.setattr(trophy, "verify", unavailable)
    report = trophy.stage(tmp_path / "donor", tmp_path / "mobile", output)
    assert report["status"] == "blocked_asset_validation"
    assert not report["scene_enabled"] and not report["runtime_verified"]
    assert not (output / "update").exists()
    assert set(path.name for path in output.iterdir()) == {"trophy-report.json", "NOT-PLAYABLE.txt"}
    assert json.loads((output / "trophy-report.json").read_text()) == report


def test_public_or_existing_output_is_refused(tmp_path):
    with pytest.raises(ValueError, match="local-debug"):
        trophy.stage(tmp_path, tmp_path, tmp_path / "public-output")


def test_optional_decoder_dependency_gap_is_recorded(tmp_path, monkeypatch):
    output = tmp_path / "samples"
    monkeypatch.setattr(trophy, "output_directory", lambda path: path)
    original_import = builtins.__import__
    def missing_decoder(name, *args, **kwargs):
        if name == "native_animation_bake":
            raise ModuleNotFoundError("optional isolated decoder unavailable")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", missing_decoder)
    report = trophy.probe_trophy_motions(tmp_path, tmp_path, tmp_path / "owned.so", output)
    assert report["status"] == "sampled_motion_decode_incomplete"
    assert "ModuleNotFoundError" in report["gap"]
    assert not report["hardware_tested"] and not report["full_clip_decode"]
    assert json.loads((output / "motion-samples.json").read_text()) == report
