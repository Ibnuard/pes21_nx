"""Independently export/audit two isolated cooked props with owned UModel.

No game assets ship with this tool. Exports/reports remain in local-debug.
No import, cook, PAK write, runtime installation or scene activation occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess

from cinematic_props_fbx import (ROOT, PROP_PATHS, child_file, match_triangles,
                                  rigid_gltf, source_primitives, validate_preparation)

POSITION_LIMIT_M = 2e-6
HALF_UV_LIMIT = 5e-4
NORMAL_LIMIT_DEGREES = 3.
MATERIALS = {"cup_int_hi": "M_gold_ggx_LR", "platform_cmn": "M_plastic_a"}


def unit(vector):
    length = math.sqrt(sum(v * v for v in vector))
    if not math.isfinite(length) or not .8 <= length <= 1.2:
        raise ValueError("invalid source/cooked shading normal")
    return tuple(v / length for v in vector)


def source_geometry(path):
    """UModel static glTF = (UE X,Z,Y) metres = original Fox (X,Y,Z)."""
    triangles, shading = [], []
    for positions, normals, channels, indices in source_primitives(path, rigid_gltf(path)):
        corners = [tuple(position) + tuple(v for channel in channels for v in channel[index])
                   for index, position in enumerate(positions)]
        for i in range(0, len(indices), 3):
            a, b, c = indices[i:i + 3]
            # UModel's glTF front faces use CCW. Our audited Fox source is CW.
            order = (a, c, b)
            triangles.append(tuple(corners[index] for index in order))
            shading.append(tuple(unit(normals[index]) for index in order))
    return triangles, shading


def cooked_accessor(doc, blobs, index):
    accessor = doc["accessors"][index]
    if accessor.get("sparse"):
        raise ValueError("sparse cooked accessor unsupported")
    view = doc["bufferViews"][accessor["bufferView"]]
    raw = blobs[view["buffer"]]
    code, denominator = {5120: ("b", 127), 5121: ("B", 255), 5122: ("h", 32767),
                         5123: ("H", 65535), 5125: ("I", 4294967295), 5126: ("f", 1)}[accessor["componentType"]]
    width = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[accessor["type"]]
    layout = "<" + code * width
    size = struct.calcsize(layout)
    stride = view.get("byteStride", size)
    count, relative, offset = accessor["count"], accessor.get("byteOffset", 0), view.get("byteOffset", 0)
    if (not 0 < count <= 150000 or stride < size or min(relative, offset, view["byteLength"]) < 0 or
            relative + (count - 1) * stride + size > view["byteLength"] or
            offset + view["byteLength"] > len(raw)):
        raise ValueError("cooked accessor exceeds its buffer view")
    rows = [struct.unpack_from(layout, raw, offset + relative + i * stride) for i in range(count)]
    if accessor.get("normalized"):
        if code == "f":
            raise ValueError("float cooked accessor cannot be normalized")
        rows = [tuple(max(-1., v / denominator) for v in row) for row in rows]
    if not all(math.isfinite(v) for row in rows for v in row):
        raise ValueError("non-finite cooked accessor")
    return rows


def cooked_geometry(path, material, uv_channels):
    doc = rigid_gltf(path)
    if (len(doc["meshes"]) != 1 or len(doc["nodes"]) != 1 or doc["nodes"][0].get("mesh") != 0 or
            any(key in doc["nodes"][0] for key in ("matrix", "translation", "rotation", "scale"))):
        raise ValueError("one untransformed cooked static mesh expected")
    blobs = []
    for buffer in doc["buffers"]:
        raw = child_file(path.parent, buffer["uri"]).read_bytes()
        if len(raw) != buffer["byteLength"]:
            raise ValueError("cooked buffer size changed")
        blobs.append(raw)
    primitives = doc["meshes"][0]["primitives"]
    if len(primitives) != 1 or [row["name"] for row in doc["materials"]] != [material]:
        raise ValueError("cooked material/section contract changed")
    triangles, shading = [], []
    for primitive in primitives:
        if primitive["material"] != 0:
            raise ValueError("cooked material index changed")
        attributes = primitive["attributes"]
        if sorted(n for n in attributes if n.startswith("TEXCOORD_")) != [f"TEXCOORD_{i}" for i in range(uv_channels)]:
            raise ValueError("cooked UV channel count changed")
        positions = cooked_accessor(doc, blobs, attributes["POSITION"])
        normals = cooked_accessor(doc, blobs, attributes["NORMAL"])
        channels = [cooked_accessor(doc, blobs, attributes[f"TEXCOORD_{i}"]) for i in range(uv_channels)]
        if any(len(rows) != len(positions) for rows in (normals, *channels)):
            raise ValueError("cooked attribute counts differ")
        corners = [tuple(position) + tuple(v for channel in channels for v in channel[index])
                   for index, position in enumerate(positions)]
        indices = [row[0] for row in cooked_accessor(doc, blobs, primitive["indices"])]
        if len(indices) % 3 or any(not isinstance(i, int) or not 0 <= i < len(positions) for i in indices):
            raise ValueError("invalid cooked triangle indices")
        for i in range(0, len(indices), 3):
            order = indices[i:i + 3]
            triangles.append(tuple(corners[index] for index in order))
            shading.append(tuple(unit(normals[index]) for index in order))
    return triangles, shading


def normal_votes(triangles, normals):
    votes = {"aligned": 0, "opposed": 0, "degenerate": 0}
    for corners, shading in zip(triangles, normals):
        a, b, c = (row[:3] for row in corners)
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        cross = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        dot = sum(cross[i] * sum(row[i] for row in shading) for i in range(3))
        votes["aligned" if dot > 1e-10 else "opposed" if dot < -1e-10 else "degenerate"] += 1
    if votes["opposed"] or not votes["aligned"]:
        raise ValueError("cooked normals oppose the front-face winding")
    return votes


def compare_cooked(source, source_normals, cooked, cooked_normals, expected_bounds):
    check, matches = match_triangles(source, cooked, POSITION_LIMIT_M, HALF_UV_LIMIT)
    maximum_angle = 0.
    uv_errors = [0.] * check["uv_channels"]
    for source_index, (cooked_index, rotation) in enumerate(matches):
        for corner in range(3):
            source_row = source[source_index][corner]
            cooked_row = cooked[cooked_index][(corner + rotation) % 3]
            for channel in range(len(uv_errors)):
                uv_errors[channel] = max(uv_errors[channel], *(abs(source_row[i] - cooked_row[i])
                                         for i in (3 + 2 * channel, 4 + 2 * channel)))
            a = source_normals[source_index][corner]
            b = cooked_normals[cooked_index][(corner + rotation) % 3]
            cosine = min(1., max(-1., sum(x * y for x, y in zip(a, b))))
            maximum_angle = max(maximum_angle, math.degrees(math.acos(cosine)))
    if maximum_angle > NORMAL_LIMIT_DEGREES:
        raise ValueError("cooked normal angular error exceeds the packed-normal tolerance")
    points = [row[:3] for tri in cooked for row in tri]
    bounds = [[min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]]
    ue_bounds = [[row[0] * 100, row[2] * 100, row[1] * 100] for row in bounds]
    if any(abs(a - b) > POSITION_LIMIT_M * 100 for a, b in zip(sum(ue_bounds, []), sum(expected_bounds, []))):
        raise ValueError("cooked axis/centimetre bounds changed")
    check.update({"max_uv_delta_by_channel": uv_errors,
                  "max_normal_angle_degrees": maximum_angle, "normal_angle_limit_degrees": NORMAL_LIMIT_DEGREES,
                  "normal_winding_votes": normal_votes(cooked, cooked_normals),
                  "umodel_bounds_m": bounds, "measured_ue_bounds_cm": ue_bounds,
                  "axis_contract": "UModel static glTF (UE X,Z,Y) metres equals source Fox (X,Y,Z)",
                  "uv_contract": "UModel glTF UVs equal source Fox UVs; no rotation/reflection fitted",
                  "cooked_geometry_verified": True})
    return check


def audit(preparation, cooked_root, umodel, output):
    preparation, cooked_root, umodel, output = (Path(p).resolve() for p in (preparation, cooked_root, umodel, output))
    allowed = (ROOT / "local-debug").resolve()
    if any(allowed not in p.parents for p in (preparation, cooked_root, output)):
        raise ValueError("inputs/outputs must remain strictly inside ignored local-debug")
    if output.exists():
        raise FileExistsError("use a new cooked audit directory")
    if not umodel.is_file():
        raise FileNotFoundError(umodel)
    profile = validate_preparation(preparation)
    content = cooked_root / "PesMobile/Content"
    assets = content / "Assets/FootballNX/FixDemo"
    for key in PROP_PATHS:
        for name in (key, MATERIALS[key], "T_" + MATERIALS[key][2:]):
            for suffix in (".uasset", ".uexp"):
                if not (assets / key / (name + suffix)).is_file():
                    raise FileNotFoundError("cook incomplete: " + name + suffix)
    output.mkdir(parents=True)
    report = {"schema": "PESNX_CINEMATIC_COOKED_AUDIT_V1", "preparation": str(preparation),
              "preparation_sha256": hashlib.sha256(preparation.read_bytes()).hexdigest(),
              "cooked_root": str(cooked_root), "umodel_sha256": hashlib.sha256(umodel.read_bytes()).hexdigest(),
              "props": [], "runtime_installed": False, "hardware_tested": False,
              "material_scalar_values_independently_verified": False,
              "limitations": ["Static cooked buffers validated; native parenting, animation and teardown remain runtime gates.",
                              "UModel material identity and texture format checks do not validate scalar parameters or compiled shader appearance; its material decoder may omit Metallic.",
                              "Materials use base colour and scalar PBR approximations; Fox packed normal/specular maps remain unused."]}
    for prop in profile["props"]:
        key = prop["key"]
        destination = output / key
        destination.mkdir()
        result = subprocess.run([str(umodel), "-export", "-gltf", "-png", "-game=ue4.22",
                                 "-path=" + str(content), "-out=" + str(destination), key],
                                capture_output=True, timeout=120)
        log = result.stdout + result.stderr
        (output / (key + ".log")).write_bytes(log)
        if result.returncode or b"ERROR:" in log:
            raise ValueError("UModel export failed: " + key)
        paths = list(destination.rglob(key + ".gltf"))
        if len(paths) != 1:
            raise ValueError("missing/ambiguous UModel static glTF: " + key)
        source, source_normals = source_geometry(child_file(preparation.parent, prop["gltf"]))
        actual, actual_normals = cooked_geometry(paths[0], MATERIALS[key], prop["geometry"]["uv_sets"][0])
        check = compare_cooked(source, source_normals, actual, actual_normals, prop["geometry"]["expected_ue_bounds_cm"])
        formats = {value.decode() for p in (assets / key).glob("T_*.uexp")
                   for value in re.findall(rb"PF_[A-Z0-9_]+", p.read_bytes())}
        if formats != {"PF_ETC1"}:
            raise ValueError("cooked base texture format changed: " + repr(formats))
        check.update({"key": key, "material": MATERIALS[key], "texture_formats": sorted(formats),
                      "exported_gltf": str(paths[0]), "cooked_files": [
                          {"file": p.relative_to(cooked_root).as_posix(), "bytes": p.stat().st_size,
                           "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                          for p in sorted((assets / key).iterdir()) if p.is_file()]})
        report["props"].append(check)
    report["status"] = "verified"
    (output / "cooked-audit.local.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PESNX_CINEMATIC_COOKED_AUDIT_OK", str(output), flush=True)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("preparation", "cooked-root", "umodel", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    audit(args.preparation, args.cooked_root, args.umodel, args.output)
