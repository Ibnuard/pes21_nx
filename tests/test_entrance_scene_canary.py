"""Synthetic only: no PES/FL26 bytes or ignored fixtures are needed."""
from __future__ import annotations

from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from entrance_scene_canary import (asset_name, dependency_audit, gani_header,
                                   inspect_fdc, output_directory, table_entries,
                                   variant_report)


def table(items, *, named):
    header_size = 4 + 12 * len(items)
    body = bytearray()
    metadata = bytearray()
    rows = []
    payload_size = sum(len(raw) for _, raw in items)
    for value, raw in items:
        rows.append((header_size + len(body), len(raw),
                     header_size + payload_size + len(metadata)))
        body += raw
        metadata += (value.encode("ascii") + b"\0" if named else struct.pack("<H", value))
    return (struct.pack("<I", len(items)) +
            b"".join(struct.pack("<III", *row) for row in rows) + body + metadata)


def fixture_fdc():
    inner = table([
        (0, bytes(64)),
        (6, b"ent/canm/test_camera.canm\0" + bytes(10)),
        (2, b"cpk_dat/common/demo/motion/test.gani\0"),
    ], named=False)
    return table([
        ("cpk_dat/common/demo/fixdemo/ent/cut_data/test.fdc", inner),
        ("ent/canm/test_camera.canm", b"camera-test-data"),
        ("cpk_dat/common/demo/motion/test.gani", bytes(4)),
    ], named=True)


def test_named_and_typed_tables_and_placeholder_dependencies():
    report = inspect_fdc(fixture_fdc())
    assert report["self_name"] == "common/demo/fixdemo/ent/cut_data/test.fdc"
    assert report["record_types"] == {0: 1, 2: 1, 6: 1}
    assert report["record_sizes"]["0"] == [64]
    assert report["resources"][0]["placeholder"] is False
    assert report["resources"][1]["placeholder"] is True
    assert report["path_references"] == ["common/demo/motion/test.gani", "ent/canm/test_camera.canm"]


@pytest.mark.parametrize("data", [b"", b"\x01", bytes(4), struct.pack("<I", 0xFFFFFFFF)])
def test_rejects_truncated_and_excessive_table(data):
    with pytest.raises(ValueError):
        table_entries(data, named=True)


@pytest.mark.parametrize("field,value", [(4, 0), (8, 0), (8, 0xFFFFFFFF), (12, 0)])
def test_rejects_out_of_bounds_payload_and_metadata(field, value):
    data = bytearray(fixture_fdc())
    struct.pack_into("<I", data, field, value)
    with pytest.raises(ValueError):
        inspect_fdc(bytes(data))


def test_rejects_overlapping_ranges():
    data = bytearray(fixture_fdc())
    first_offset = struct.unpack_from("<I", data, 4)[0]
    struct.pack_into("<I", data, 16, first_offset)
    with pytest.raises(ValueError, match="overlapping"):
        inspect_fdc(bytes(data))


def test_rejects_unterminated_names_and_non_scene_first_resource():
    with pytest.raises(ValueError, match="unterminated"):
        table_entries(fixture_fdc()[:-1], named=True)
    not_fdc = table([("common/not-a-scene.bin", bytes(16))], named=True)
    with pytest.raises(ValueError, match="first FDC resource"):
        inspect_fdc(not_fdc)


@pytest.mark.parametrize("value", ["../escape", "/absolute", "D:/file", "common//a", "common/./a", "common/../../a"])
def test_path_traversal_is_never_an_asset(value):
    with pytest.raises(ValueError, match="unsafe asset path"):
        asset_name(value)


def make_gani():
    return struct.pack("<8I", 0x0BFCA2D2, 32, 48, 0, 0, 1, 0, 0x83480000) + bytes(16)


def test_gani_envelope_accepts_measured_layout_not_guessed_bones():
    header = gani_header(make_gani())
    assert header["version"] == 1
    assert header["bytes"] == 48
    for offset in (0, 4, 8, 12, 16, 20, 24):
        invalid = bytearray(make_gani())
        invalid[offset] ^= 1
        with pytest.raises(ValueError, match="unsupported"):
            gani_header(bytes(invalid))


class FakeCpk:
    def __init__(self, files):
        self.index = files
        self.path = Path("synthetic.cpk")

    def read(self, name):
        return self.index[name]


def test_zero_gani_placeholder_must_resolve_from_an_archive():
    cut = inspect_fdc(fixture_fdc())
    name = "common/demo/motion/test.gani"
    source = FakeCpk({name: make_gani()})
    rows = dependency_audit(cut, source, [])
    motion = next(row for row in rows if row["name"] == name)
    assert motion["resolution"] == "donor_only"
    assert motion["bytes"] == 48
    assert motion["gani_envelope"]["version"] == 1
    assert next(row for row in rows if row["name"].endswith(".canm"))["resolution"] == "embedded"
    assert dependency_audit(cut, FakeCpk({}), [])[0]["resolution"] == "missing"
    assert dependency_audit(cut, source, [source])[0]["resolution"] == "mobile"
    assert dependency_audit(cut, source, [source])[0]["donor_identical"] is True
    changed = FakeCpk({name: make_gani()[:-1] + b"1"})
    assert dependency_audit(cut, source, [changed])[0]["donor_identical"] is False
    assert dependency_audit(cut, source, [source, source])[0]["resolution"] == "ambiguous_mobile"


def test_unrecognized_donor_animation_stays_a_format_error():
    cut = inspect_fdc(fixture_fdc())
    source = FakeCpk({"common/demo/motion/test.gani": b"wrong"})
    assert "format_error" in dependency_audit(cut, source, [])[0]


def test_platform_only_model_is_not_accepted_as_a_mobile_dependency():
    cut = {"resources": [], "self_name": "common/demo/fixdemo/end/cut_data/test.fdc",
           "path_references": ["common/demo/prop/project/project.fpk"]}
    source = FakeCpk({"common/demo/prop/project/#Win/project.fpk": b"synthetic-model"})
    result = dependency_audit(cut, source, [FakeCpk({})])[0]
    assert result["resolution"] == "donor_platform_only"
    assert result["platform_candidates"][0]["name"].endswith("/#Win/project.fpk")
    assert "gani_envelope" not in result


def test_output_never_targets_active_runtime_or_existing_results(tmp_path):
    with pytest.raises(ValueError, match="local-debug"):
        output_directory(tmp_path / "dist" / "pes21_nx")
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="local-debug"):
        output_directory(root / "local-debug")
    # Point the guard at a synthetic existing directory without touching any
    # real runtime or old diagnostic output.
    import entrance_scene_canary
    from unittest.mock import patch
    debug = tmp_path / "local-debug" / "existing"
    debug.mkdir(parents=True)
    with patch.object(entrance_scene_canary, "ROOT", tmp_path):
        with pytest.raises(FileExistsError):
            output_directory(debug)


def test_variant_subset_requires_explicit_real_members_and_records_omissions():
    from fixdemo_scene_table import serialize_scene_table
    original = {"version": 1, "kind": 1, "condition_count": 1, "file_count": 2,
                "cuts": [{"name": "TEST", "id": 0x10001, "variants": [
                    {"conditions": [256], "files": ["test.fdc", "optional.fdc"],
                     "flags": 0, "move_distance": 0.0, "human_mask": 1}]}],
                "scenes": [], "has_controls": False, "controls": []}
    source = FakeCpk({
        "common/demo/fixdemo/ent/table_ent.bin": serialize_scene_table(original),
        "common/demo/fixdemo/ent/cut_data/test.fdc": fixture_fdc(),
        "common/demo/motion/test.gani": make_gani(),
    })
    selected = variant_report(source, [], "TEST", 0, selected_files=["test.fdc"])
    assert selected["omitted_files"] == ["optional.fdc"]
    assert selected["dependency_counts"] == {"donor_only": 1, "embedded": 1}
    assert selected["runtime_verified"] is False
    for chosen in ([], ["unknown.fdc"], ["test.fdc", "test.fdc"]):
        with pytest.raises(ValueError, match="nonempty unique"):
            variant_report(source, [], "TEST", 0, selected_files=chosen)
    with pytest.raises(ValueError, match="unknown entrance"):
        variant_report(source, [], "TEST", 1)
