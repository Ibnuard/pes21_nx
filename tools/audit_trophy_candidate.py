#!/usr/bin/env python3
"""Recheck a detached trophy candidate without installing or activating it.

Retained geometry measurements are bound to current cooked/package bytes.
This is an offline asset audit, never a claim of scene or hardware readiness.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile

from cinematic_props_fbx import child_file, validate_preparation
from cook_cinematic_props import NAMESPACE, material_shader_versions, unrealpak_confirmed
from entrance_scene_canary import Cpk
from prepare_loose_cpk import digest, read_manifest, verify
import stage_trophy_ceremony as trophy
from validate_cinematic_props_cooked import MATERIALS

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("cup_int_hi", "platform_cmn")
# Versioned handoff gaps, not inferred successes from a marker/report flag.
RUNTIME_GAPS = (
    "Serialized mesh-completion observer with exact owner/load-key/scene identity, bounded timeout and hidden failure.",
    "Invocation-scoped final-result capture: actual END phase, mapped current teams, goals/shootout scores and monotonic match token.",
    "Native scene/prop integration with single ownership, failure fallback, Skip/destructor cleanup and FPS restoration.",
    "One validated dt220/manifest pair preserving the installed entrance; independent entrance/trophy updates cannot be overlaid.",
    "Switch playback: winner/captain, cup parenting, podium placement, natural completion, Skip and subsequent matches.",
)


def read(path: Path, schema: str) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or result.get("schema") != schema:
        raise ValueError("unsupported report schema: " + str(path))
    return result


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def measured_file(path: Path, record: dict) -> None:
    require(type(record.get("bytes")) is int and record["bytes"] > 0,
            "invalid recorded byte count")
    require(path.stat().st_size == record["bytes"] and digest(path) == record.get("sha256"),
            "artifact changed: " + str(path))


def finite_limit(value, maximum: float) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= maximum


def check_geometry(check: dict, source: dict) -> None:
    triangles = source["geometry"]["triangles"]
    require(type(triangles) is int and triangles > 0, "invalid source triangle count")
    require(check.get("cooked_geometry_verified") is True and
            check.get("winding_and_uv_corners_verified") is True and
            check.get("triangles_matched") == triangles and
            check.get("uv_channels") == source["geometry"]["uv_sets"][0],
            "missing geometry/UV correspondence")
    require(check.get("normal_winding_votes") ==
            {"aligned": triangles, "opposed": 0, "degenerate": 0},
            "invalid oriented normals")
    for name, maximum in (("max_position_delta_m", 2e-6), ("max_uv_delta", .0005),
                          ("max_normal_angle_degrees", 3.0)):
        require(finite_limit(check.get(name), maximum), "geometry tolerance failed: " + name)
    require(check.get("material") == MATERIALS[source["key"]] and
            check.get("texture_formats") == ["PF_ETC1"], "material/texture contract changed")


def check_package(package_report: Path, cooked_audit: Path, repak: Path,
                  unrealpak: Path, temporary: Path) -> dict:
    package = read(package_report, "PESNX_CINEMATIC_PROP_PACKAGE_V1")
    cooked = read(cooked_audit, "PESNX_CINEMATIC_COOKED_AUDIT_V1")
    require(package.get("stage") == "asset-only-not-playable" and
            cooked.get("status") == "verified", "asset stages are incomplete")
    preparation_path = Path(cooked["preparation"])
    preparation = validate_preparation(preparation_path)
    require(digest(preparation_path) == cooked["preparation_sha256"] ==
            package["preparation_sha256"], "preparation provenance mismatch")
    require(tuple(p["key"] for p in cooked["props"]) == KEYS and
            tuple(p["key"] for p in preparation["props"]) == KEYS,
            "expected exactly the cup and podium")
    root = Path(cooked["cooked_root"])
    files = {}
    metrics = []
    for prop, source in zip(cooked["props"], preparation["props"]):
        check_geometry(prop, source)
        key = prop["key"]
        material = MATERIALS[key]
        required = {f"{key}/{stem}{suffix}" for stem in (key, material, "T_" + material[2:])
                    for suffix in (".uasset", ".uexp")}
        optional = {f"{key}/T_{material[2:]}.ubulk"}
        observed = set()
        for row in prop["cooked_files"]:
            path = child_file(root, row["file"])
            relative = path.relative_to((root / NAMESPACE).resolve()).as_posix()
            require(relative in required | optional and row["file"] not in files,
                    "unexpected/duplicate cooked member")
            measured_file(path, row)
            files[row["file"]] = row
            observed.add(relative)
        require(required <= observed <= required | optional, "incomplete cooked member set")
        require(material_shader_versions(root / NAMESPACE / key / (material + ".uexp")) ==
                {"100", "310 es"}, "missing ES2/ES3.1 shaders")
        metrics.append({"key": key, "triangles": prop["triangles_matched"],
                        "uv_channels": prop["uv_channels"]})
    require(set(package["members"]) == set(files) and len(package["members"]) == len(files),
            "package/cooked-audit member set mismatch")
    pak = Path(package["package"])
    measured_file(pak, package)
    listing = subprocess.check_output([str(repak), "list", str(pak)], text=True,
                                      timeout=60).splitlines()
    require(sorted(listing) == sorted(files), "actual PAK member set mismatch")
    # Validate names against the exact cooked namespace BEFORE allowing unpack.
    result = subprocess.run([str(unrealpak), str(pak), "-Test"], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=90)
    require(unrealpak_confirmed(result.stdout, len(files)), "UnrealPak integrity check failed")
    restored = temporary / "unpacked"
    subprocess.run([str(repak), "unpack", "-q", "-o", str(restored), str(pak)],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    require(sorted(p.relative_to(restored).as_posix() for p in restored.rglob("*") if p.is_file()) ==
            sorted(files), "unpacked member set mismatch")
    for name, row in files.items():
        measured_file(child_file(restored, name), row)
    return {"pak_sha256": digest(pak), "members": len(files), "props": metrics,
            "unrealpak_integrity_rechecked": True, "unpacked_payload_hashes_match": True,
            "geometry_evidence": "retained measurements bound to current cooked and unpacked bytes",
            "material_appearance_hardware_verified": False}


def check_trophy(report_path: Path) -> dict:
    report = read(report_path, "PESNX_TROPHY_ASSETS_V1")
    require(report.get("status") == "asset_only_not_playable" and
            report.get("scene_enabled") is False and report.get("runtime_verified") is False,
            "expected detached, inactive trophy assets")
    require((report["scene_id"], report["cut_id"], report["donor_variant_index"]) ==
            (trophy.SCENE_ID, trophy.CUT_ID, trophy.VARIANT_INDEX), "unreviewed trophy selection")
    baseline = Path(report["baseline_root"])
    manifest = verify(baseline)
    require(manifest["version"] == 2 and manifest["build_id"] == trophy.BASELINE_BUILD and
            digest(baseline / "LooseCpk/manifest.txt") == report["baseline_manifest_sha256"],
            "baseline manifest differs")
    base = baseline / "LooseCpk/dt220_mobile_all.cpk"
    require(digest(base) == trophy.BASELINE_DT220_SHA256 == report["baseline_dt220_sha256"],
            "baseline dt220 differs")
    update = report_path.parent / "update"
    candidate = update / "LooseCpk/dt220_mobile_all.cpk"
    validation = report["validation"]
    require(digest(candidate) == validation["candidate_sha256"] and
            candidate.stat().st_size == validation["size"], "candidate CPK changed")
    expected = copy.deepcopy(manifest)
    row = next(r for r in expected["files"] if r["name"] == base.name)
    row.update(size=candidate.stat().st_size, sha256=digest(candidate))
    require(read_manifest(update) == expected, "candidate/manifest pair or unrelated entry differs")
    old, new = Cpk(base), Cpk(candidate)
    payloads = {}
    for item in report["payloads"]:
        name = item["name"]
        require(name not in payloads, "duplicate trophy payload")
        raw = new.read(name)
        require(len(raw) == item["bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"],
                "trophy member changed: " + name)
        payloads[name] = raw
    require(set(payloads) & set(old.index) == {trophy.TABLE}, "unrelated native replacement")
    require(set(new.index) == set(old.index) | set(payloads), "unexpected/missing CPK member")
    require(list(new.index) == list(old.index) + sorted(set(payloads) - set(old.index)),
            "CPK row order changed")
    unchanged = 0
    for name in old.index:
        require(new.index[name]["ID"] == old.index[name]["ID"], "CPK ID changed")
        if name != trophy.TABLE:
            require(new.read(name) == old.read(name), "unrelated CPK member changed: " + name)
            unchanged += 1
    # Rebuild the intended table/closure from the SAME owned donor and compare
    # current bytes, rather than trusting a self-consistent edited report alone.
    donor = Cpk(Path(report["donor_archive"]))
    from fixdemo_scene_table import parse_scene_table, serialize_scene_table
    expected_table = trophy.build_trophy_table(parse_scene_table(old.read(trophy.TABLE), 7),
                                              parse_scene_table(donor.read(trophy.TABLE), 7))
    planned, _, _ = trophy.collect_payloads(donor, [old, Cpk(baseline / "LooseCpk/dt230_mobile_all.cpk")])
    planned[trophy.TABLE] = serialize_scene_table(expected_table)
    require(payloads == planned, "trophy payloads differ from the authored donor plan")
    require(new.read(trophy.ENTRANCE_TABLE) == old.read(trophy.ENTRANCE_TABLE), "entrance changed")
    return {"dt220_sha256": digest(candidate), "unrelated_members_identical": unchanged,
            "payloads": len(payloads), "native_entrance_preserved": True,
            "full_baseline_verified": True, "scene_enabled": False}


def run_audit(trophy_report: Path, package_report: Path, cooked_audit: Path,
              repak: Path, unrealpak: Path, output: Path) -> dict:
    output = output.resolve()
    require((ROOT / "local-debug").resolve() in output.parents,
            "output must be a new directory inside ignored local-debug")
    require(not output.exists(), "output already exists")
    output.mkdir(parents=True)
    result = {"schema": "PESNX_TROPHY_READINESS_V1", "checks": {},
              "asset_validation_passed": False, "ready_for_switch_trophy_test": False,
              "production_ready": False, "runtime_modified": False,
              "runtime_gaps": list(RUNTIME_GAPS)}
    with tempfile.TemporaryDirectory(prefix="verify-", dir=output) as temp:
        for name, function in (
                ("trophy_assets", lambda: check_trophy(trophy_report)),
                ("cooked_props", lambda: check_package(package_report, cooked_audit, repak, unrealpak, Path(temp)))):
            try:
                result["checks"][name] = {"status": "passed", **function()}
            except (OSError, ValueError, KeyError, TypeError, RuntimeError,
                    subprocess.SubprocessError) as exc:
                result["checks"][name] = {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}
    result["asset_validation_passed"] = all(row["status"] == "passed" for row in result["checks"].values())
    result["status"] = "assets_verified_runtime_pending" if result["asset_validation_passed"] else "asset_validation_failed"
    (output / "readiness-report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def exit_status(result: dict, require_playable: bool) -> int:
    if not result["asset_validation_passed"]:
        return 1
    return 2 if require_playable and not result["ready_for_switch_trophy_test"] else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("trophy-report", "package-report", "cooked-audit", "repak", "unrealpak", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--require-playable", action="store_true",
                        help="exit 2 when assets pass but playable integration is still missing")
    args = parser.parse_args()
    result = run_audit(args.trophy_report, args.package_report, args.cooked_audit,
                       args.repak, args.unrealpak, args.output)
    print(json.dumps(result, indent=2))
    raise SystemExit(exit_status(result, args.require_playable))


if __name__ == "__main__":
    main()
