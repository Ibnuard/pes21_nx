"""Synthetic package corruption/readiness regressions; no game fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_trophy_candidate as audit


def geometry(key="cup_int_hi"):
    source = {"key": key, "geometry": {"triangles": 2, "uv_sets": [1]}}
    measured = {"key": key, "triangles_matched": 2, "uv_channels": 1,
                "cooked_geometry_verified": True, "winding_and_uv_corners_verified": True,
                "normal_winding_votes": {"aligned": 2, "opposed": 0, "degenerate": 0},
                "max_position_delta_m": 0., "max_uv_delta": 0., "max_normal_angle_degrees": 0.,
                "material": audit.MATERIALS[key], "texture_formats": ["PF_ETC1"]}
    return source, measured


@pytest.mark.parametrize("field,value", [
    ("triangles_matched", 1), ("uv_channels", 2), ("cooked_geometry_verified", False),
    ("winding_and_uv_corners_verified", False), ("max_position_delta_m", 2.01e-6),
    ("max_uv_delta", .00051), ("max_normal_angle_degrees", 3.01),
    ("max_position_delta_m", float("nan")), ("max_uv_delta", float("inf")),
    ("max_normal_angle_degrees", -1), ("max_position_delta_m", True),
    ("normal_winding_votes", {"aligned": 1, "opposed": 1, "degenerate": 0}),
    ("texture_formats", ["PF_DXT1"]), ("material", "Other"),
])
def test_geometry_evidence_rejects_missing_or_out_of_range_measurement(field, value):
    source, measured = geometry()
    audit.check_geometry(measured, source)
    measured[field] = value
    with pytest.raises(ValueError):
        audit.check_geometry(measured, source)


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def recorded(path):
    return {"bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


@pytest.fixture
def package_case(tmp_path, monkeypatch):
    root = tmp_path / "cooked"
    source = {"props": []}
    cooked = {"schema": "PESNX_CINEMATIC_COOKED_AUDIT_V1", "status": "verified",
              "cooked_root": str(root), "props": []}
    for key in audit.KEYS:
        prop, check = geometry(key)
        source["props"].append(prop)
        check["cooked_files"] = []
        material = audit.MATERIALS[key]
        for stem in (key, material, "T_" + material[2:]):
            for suffix in (".uasset", ".uexp"):
                name = (audit.NAMESPACE / key / (stem + suffix)).as_posix()
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(("synthetic " + name).encode())
                check["cooked_files"].append({"file": name, **recorded(path)})
        cooked["props"].append(check)
    preparation = write_json(tmp_path / "preparation.json", source)
    cooked.update(preparation=str(preparation), preparation_sha256=audit.digest(preparation))
    pak = tmp_path / "test.pak"
    pak.write_bytes(b"synthetic package; fake decoder is explicitly injected below")
    package = {"schema": "PESNX_CINEMATIC_PROP_PACKAGE_V1", "stage": "asset-only-not-playable",
               "package": str(pak), **recorded(pak), "preparation_sha256": audit.digest(preparation),
               "members": [r["file"] for p in cooked["props"] for r in p["cooked_files"]]}
    package_path = write_json(tmp_path / "package.json", package)
    cooked_path = write_json(tmp_path / "cooked.json", cooked)
    calls = []
    monkeypatch.setattr(audit, "validate_preparation", lambda p: copy.deepcopy(source))
    monkeypatch.setattr(audit, "material_shader_versions", lambda p: {"100", "310 es"})
    monkeypatch.setattr(audit.subprocess, "check_output", lambda *a, **kw: "\n".join(package["members"]))

    def run(argv, **kwargs):
        calls.append(argv)
        if argv[1] == "unpack":
            shutil.copytree(root, Path(argv[argv.index("-o") + 1]))
        return audit.subprocess.CompletedProcess(argv, 0, f'Pak file "test.pak" healthy, {len(package["members"])} files checked.')

    monkeypatch.setattr(audit.subprocess, "run", run)
    temp = tmp_path / "temp"
    temp.mkdir()
    return package_path, cooked_path, root, package, cooked, calls, temp


def check(case):
    package_path, cooked_path, *_, temp = case
    return audit.check_package(package_path, cooked_path, Path("repak"), Path("UnrealPak"), temp)


def test_current_bytes_and_unpacked_payloads_match_retained_measurements(package_case):
    result = check(package_case)
    assert result["members"] == 12
    assert result["unpacked_payload_hashes_match"]
    assert not result["material_appearance_hardware_verified"]


def test_cooked_asset_change_rejected_before_unpack(package_case):
    _, _, root, package, _, calls, _ = package_case
    (root / package["members"][0]).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="artifact changed"):
        check(package_case)
    assert not calls


@pytest.mark.parametrize("change", ["duplicate", "extra", "missing", "path_escape", "unrelated"])
def test_report_cannot_bless_unexpected_or_incomplete_package(package_case, change):
    package_path, cooked_path, _, package, cooked, calls, _ = package_case
    if change == "duplicate":
        package["members"].append(package["members"][0])
    elif change == "extra":
        package["members"].append("PesMobile/Content/Unrelated.uasset")
    elif change == "missing":
        cooked["props"][0]["cooked_files"].pop()
    elif change == "path_escape":
        cooked["props"][0]["cooked_files"][0]["file"] = "../outside.uasset"
    else:
        cooked["props"][0]["key"] = "other_cup"
    write_json(package_path, package)
    write_json(cooked_path, cooked)
    with pytest.raises(ValueError):
        check(package_case)
    assert not calls


def test_actual_member_set_is_checked_before_extraction(package_case, monkeypatch):
    calls = package_case[5]
    monkeypatch.setattr(audit.subprocess, "check_output", lambda *a, **kw: "../../escape.bin\n")
    with pytest.raises(ValueError, match="actual PAK member set"):
        check(package_case)
    assert not calls


def test_unpack_corruption_is_not_reported_as_pass(package_case, monkeypatch):
    original = audit.subprocess.run

    def corrupt(argv, **kwargs):
        result = original(argv, **kwargs)
        if argv[1] == "unpack":
            root = Path(argv[argv.index("-o") + 1])
            (root / package_case[3]["members"][0]).write_bytes(b"bad decoded bytes")
        return result

    monkeypatch.setattr(audit.subprocess, "run", corrupt)
    with pytest.raises(ValueError, match="artifact changed"):
        check(package_case)


@pytest.mark.parametrize("failed", [None, "trophy_assets", "cooked_props"])
def test_checks_are_independent_and_assets_never_imply_playable(tmp_path, monkeypatch, failed):
    monkeypatch.setattr(audit, "ROOT", tmp_path)

    def fake_check(name):
        if name == failed:
            raise ValueError("synthetic missing input")
        return {"checked": True, "ready_for_switch_trophy_test": True}

    monkeypatch.setattr(audit, "check_trophy", lambda *a: fake_check("trophy_assets"))
    monkeypatch.setattr(audit, "check_package", lambda *a: fake_check("cooked_props"))
    output = tmp_path / "local-debug/audit"
    result = audit.run_audit(*(Path("unused") for _ in range(5)), output)
    assert len(result["checks"]) == 2
    assert result["asset_validation_passed"] is (failed is None)
    assert result["ready_for_switch_trophy_test"] is False
    assert result["production_ready"] is False and result["runtime_modified"] is False
    assert audit.exit_status(result, False) == (1 if failed else 0)
    assert audit.exit_status(result, True) == (1 if failed else 2)
    assert list(output.iterdir()) == [output / "readiness-report.json"]
    with pytest.raises(ValueError, match="already exists"):
        audit.run_audit(*(Path("unused") for _ in range(5)), output)


def test_output_cannot_write_into_active_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    output = tmp_path / "dist/pes21_nx"
    with pytest.raises(ValueError, match="ignored local-debug"):
        audit.run_audit(*(Path("unused") for _ in range(5)), output)
    assert not output.exists()
