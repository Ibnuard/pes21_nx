#!/usr/bin/env python3
"""Isolated Blender export and FBX roundtrip check for prepared rigid props.

blender --background --python tools/cinematic_props_fbx.py --
  --input local-debug/<new-preparation>/preparation.local.json
  --output local-debug/<new-preparation>/fbx

No UE editor/cook, PAK packaging, scene activation, or active runtime writes.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
from itertools import product
import json
import math
from pathlib import Path, PurePosixPath
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
POSITION_TOLERANCE_M = 2e-6
UV_TOLERANCE = 2e-6
PROP_PATHS = {
    "cup_int_hi": "common/demo/prop/cup_int_hi/cup_int_hi",
    "platform_cmn": "common/demo/fixdemoobj/winners_platform_common/winners_platform_common",
}


def child_file(root: Path, relative: str) -> Path:
    if (not relative or "\\" in relative or ":" in relative or
            any(p in ("", ".", "..") for p in relative.split("/")) or
            PurePosixPath(relative).is_absolute()):
        raise ValueError("unsafe preparation member")
    path = (root / relative).resolve(strict=True)
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError("preparation member escaped root")
    return path


def rigid_gltf(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("skins") or doc.get("animations") or any("skin" in node for node in doc["nodes"]):
        raise ValueError("rigid prop must not carry skins or animations")
    for mesh in doc["meshes"]:
        for primitive in mesh["primitives"]:
            if primitive.get("mode", 4) != 4 or primitive.get("targets"):
                raise ValueError("rigid prop requires triangles without morph targets")
            attributes = primitive["attributes"]
            if any(name.startswith(("JOINTS_", "WEIGHTS_")) for name in attributes):
                raise ValueError("rigid prop must not carry skin attributes")
    return doc


def validate_preparation(source: Path) -> dict:
    profile = json.loads(source.read_text(encoding="utf-8"))
    if profile.get("schema") != "PESNX_CINEMATIC_PROPS_V1" or profile.get("cooked") is not False:
        raise ValueError("unsupported preparation manifest")
    if [row["key"] for row in profile["props"]] != list(PROP_PATHS):
        raise ValueError("only the two audited props may be exported")
    expected_files = set()
    for prop in profile["props"]:
        key, prefix = prop["key"], PROP_PATHS[prop["key"]]
        if (prop["gltf"] != f"{key}/{key}.gltf" or
                prop["descriptor_model_path"] != prefix + ".fpk" or
                prop["runtime_model_path"] != "cpk_dat/" + prefix + ".xml" or
                prop["target_class"] != "StaticMesh" or
                prop["target_object_path"] != f"/Game/Assets/FootballNX/FixDemo/{key}/{key}.{key}"):
            raise ValueError("prop path escaped the exact allowlist")
        gltf = child_file(source.parent, prop["gltf"])
        doc = rigid_gltf(gltf)
        expected_files.add(prop["gltf"])
        for resource in (*doc["buffers"], *doc.get("images", [])):
            path = child_file(gltf.parent, resource["uri"])
            expected_files.add(path.relative_to(source.parent).as_posix())
    hashed_files = set()
    for item in profile["outputs"]:
        if item["file"] in hashed_files:
            raise ValueError("duplicate prepared input hash")
        hashed_files.add(item["file"])
        raw = child_file(source.parent, item["file"]).read_bytes()
        if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("prepared input changed: " + item["file"])
    if expected_files != hashed_files:
        raise ValueError("prepared resource hash coverage differs")
    return profile


def accessor_rows(doc: dict, binary: bytes, index: int):
    """Read only the tightly packed, finite accessors emitted by preparation."""
    accessor = doc["accessors"][index]
    view = doc["bufferViews"][accessor["bufferView"]]
    if accessor.get("sparse") or accessor.get("normalized") or view["buffer"] != 0:
        raise ValueError("unsupported accessor storage")
    width = {"VEC2": 2, "VEC3": 3, "SCALAR": 1}[accessor["type"]]
    code = {5126: "f", 5123: "H", 5125: "I"}[accessor["componentType"]]
    layout = "<" + code * width
    stride = struct.calcsize(layout)
    count = accessor["count"]
    offset, length = view.get("byteOffset", 0), view["byteLength"]
    relative = accessor.get("byteOffset", 0)
    if (view.get("byteStride", stride) != stride or count <= 0 or count > 150000 or
            min(offset, length, relative) < 0 or relative + count * stride > length or
            offset + length > len(binary)):
        raise ValueError("accessor exceeds its bounded buffer view")
    rows = [struct.unpack_from(layout, binary, offset + relative + i * stride)
            for i in range(count)]
    if not all(math.isfinite(v) for row in rows for v in row):
        raise ValueError("non-finite accessor")
    return rows


def source_primitives(path: Path, doc: dict):
    if len(doc["buffers"]) != 1:
        raise ValueError("one prepared binary buffer expected")
    binary = child_file(path.parent, doc["buffers"][0]["uri"]).read_bytes()
    if len(binary) != doc["buffers"][0]["byteLength"]:
        raise ValueError("prepared buffer length changed")
    for node in doc["nodes"]:
        if any(key in node for key in ("matrix", "translation", "rotation", "scale")):
            raise ValueError("prepared rigid geometry must not carry node transforms")
    for mesh in doc["meshes"]:
        for primitive in mesh["primitives"]:
            attributes = primitive["attributes"]
            pos = accessor_rows(doc, binary, attributes["POSITION"])
            normals = accessor_rows(doc, binary, attributes["NORMAL"])
            names = sorted(name for name in attributes if name.startswith("TEXCOORD_"))
            if names != [f"TEXCOORD_{i}" for i in range(len(names))] or not 1 <= len(names) <= 4:
                raise ValueError("non-contiguous prepared UV channels")
            uvs = [accessor_rows(doc, binary, attributes[name]) for name in names]
            indices = [row[0] for row in accessor_rows(doc, binary, primitive["indices"])]
            if (any(len(rows) != len(pos) for rows in (normals, *uvs)) or
                    len(indices) % 3 or any(not isinstance(i, int) or not 0 <= i < len(pos) for i in indices)):
                raise ValueError("prepared vertex/index correspondence changed")
            yield pos, normals, uvs, indices


def winding_votes(path: Path, doc: dict) -> dict:
    """Check measured Fox clockwise triangles before reversing Blender faces."""

    votes = {"aligned": 0, "opposed": 0, "degenerate": 0}
    for pos, normals, _, indices in source_primitives(path, doc):
        for i in range(0, len(indices), 3):
            a, b, c = indices[i:i + 3]
            u = [pos[b][j] - pos[a][j] for j in range(3)]
            v = [pos[c][j] - pos[a][j] for j in range(3)]
            cross = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                     u[0] * v[1] - u[1] * v[0]]
            dot = sum(cross[j] * sum(normals[k][j] for k in (a, b, c)) for j in range(3))
            votes["aligned" if dot > 1e-10 else "opposed" if dot < -1e-10 else "degenerate"] += 1
    if not votes["opposed"] or votes["aligned"]:
        raise ValueError("source winding changed; do not silently flip geometry")
    return votes


def source_triangles(path: Path, doc: dict):
    """Expected Blender corners: reverse Fox winding, Y-up to Z-up, V flip."""
    triangles = []
    for positions, _, channels, indices in source_primitives(path, doc):
        corners = []
        for index, (x, y, z) in enumerate(positions):
            row = [x, -z, y]
            for channel in channels:
                u, v = channel[index]
                row.extend((u, 1. - v))
            corners.append(tuple(row))
        for i in range(0, len(indices), 3):
            a, b, c = indices[i:i + 3]
            triangles.append((corners[a], corners[c], corners[b]))
    return triangles


def mesh_triangles(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    points = [obj.matrix_world @ v.co for v in mesh.vertices]
    triangles = []
    for triangle in mesh.loop_triangles:
        corners = []
        for loop in triangle.loops:
            row = list(points[mesh.loops[loop].vertex_index])
            for uv in mesh.uv_layers:
                row.extend(uv.data[loop].uv)
            corners.append(tuple(float(v) for v in row))
        triangles.append(tuple(corners))
    return triangles


def match_triangles(expected, actual, position_tolerance_m=POSITION_TOLERANCE_M,
                    uv_tolerance=UV_TOLERANCE):
    """Match oriented triangles with bounded float drift, retaining seam UVs.

    Cyclic corner order and triangle order may change in FBX. A reflected
    triangle, reassigned UV corner, changed topology, or dropped duplicate may
    not. A centroid grid keeps this linear for the audited bounded meshes.
    """
    if not expected or len(expected) != len(actual):
        raise ValueError("triangle count changed")
    if not all(math.isfinite(v) and v > 0 for v in (position_tolerance_m, uv_tolerance)):
        raise ValueError("invalid geometry/UV tolerance")
    width = len(expected[0][0])
    if width < 5 or width > 11 or width % 2 != 1:
        raise ValueError("unexpected triangle corner width")
    for triangle in (*expected, *actual):
        if len(triangle) != 3 or any(len(row) != width or
                                  not all(math.isfinite(v) for v in row) for row in triangle):
            raise ValueError("invalid triangle corner data")

    def cell(triangle):
        return tuple(math.floor(sum(row[i] for row in triangle) / 3 / position_tolerance_m)
                     for i in range(3))

    pending = defaultdict(dict)
    for index, triangle in enumerate(actual):
        pending[cell(triangle)][index] = triangle
    offsets = tuple(product((-1, 0, 1), repeat=3))
    position_error = uv_error = 0.
    matches = []
    for source in expected:
        location = cell(source)
        found = None
        for offset in offsets:
            key = tuple(location[i] + offset[i] for i in range(3))
            for index, candidate in pending.get(key, {}).items():
                for rotation in range(3):
                    delta = [[abs(a - b) for a, b in zip(source[i], candidate[(i + rotation) % 3])]
                             for i in range(3)]
                    xyz_error = max(value for row in delta for value in row[:3])
                    tex_error = max(value for row in delta for value in row[3:])
                    if xyz_error <= position_tolerance_m and tex_error <= uv_tolerance:
                        found = (key, index, rotation, xyz_error, tex_error)
                        break
                if found:
                    break
            if found:
                break
        if found is None:
            raise ValueError("triangle geometry, winding or UV corner correspondence changed")
        key, index, rotation, xyz_error, tex_error = found
        del pending[key][index]
        matches.append((index, rotation))
        position_error = max(position_error, xyz_error)
        uv_error = max(uv_error, tex_error)
    return ({"triangles_matched": len(expected), "uv_channels": (width - 3) // 2,
             "max_position_delta_m": position_error, "max_uv_delta": uv_error,
             "position_tolerance_m": position_tolerance_m, "uv_tolerance": uv_tolerance,
             "winding_and_uv_corners_verified": True}, matches)


def compare_triangles(expected, actual) -> dict:
    return match_triangles(expected, actual)[0]


def snapshot(obj, triangles=None):
    mesh = obj.data
    mesh.calc_loop_triangles()
    points = [obj.matrix_world @ v.co for v in mesh.vertices]
    bounds = [[min(p[i] for p in points) for i in range(3)],
              [max(p[i] for p in points) for i in range(3)]]
    # Diagnostic signature only: acceptance uses tolerance-bounded triangles.
    triangles = mesh_triangles(obj) if triangles is None else triangles
    corners = [[round(value, 6) or 0. for value in row]
               for triangle in triangles for row in triangle]
    corners.sort()
    return {"bounds_m": bounds, "triangles": len(mesh.loop_triangles),
            "uv_channels": len(mesh.uv_layers),
            "corner_signature": hashlib.sha256(json.dumps(corners).encode()).hexdigest(),
            "has_skin": bool(obj.vertex_groups) or any(m.type == "ARMATURE" for m in obj.modifiers)}


def reverse_faces_preserving_normals(obj):
    import bmesh
    mesh = obj.data
    coordinates = [tuple(v.co) for v in mesh.vertices]
    # Keep normals as corner data alongside UVs. Blender's encoded split
    # normals can differ across faces sharing a vertex; averaging loses seams.
    normal_values = [tuple(value.vector) for value in mesh.corner_normals]
    attribute = mesh.attributes.new(name="_pesnx_source_normal", type="FLOAT_VECTOR", domain="CORNER")
    attribute_name = attribute.name
    for row, value in zip(attribute.data, normal_values):
        row.vector = value
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
    finally:
        bm.free()
    if [tuple(v.co) for v in mesh.vertices] != coordinates:
        raise ValueError("face reversal reordered vertices")
    attribute = mesh.attributes[attribute_name]
    mesh.normals_split_custom_set([tuple(row.vector) for row in attribute.data])
    mesh.attributes.remove(attribute)
    mesh.update()


def normal_winding_votes(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    points = [obj.matrix_world @ v.co for v in mesh.vertices]
    normal_transform = obj.matrix_world.to_3x3().inverted().transposed()
    normals = [normal_transform @ n.vector for n in mesh.corner_normals]
    votes = {"aligned": 0, "opposed": 0, "degenerate": 0}
    for tri in mesh.loop_triangles:
        a, b, c = [points[v] for v in tri.vertices]
        dot = (b - a).cross(c - a).dot(sum((normals[i] for i in tri.loops), normals[0] * 0))
        votes["aligned" if dot > 1e-10 else "opposed" if dot < -1e-10 else "degenerate"] += 1
    if votes["opposed"] or not votes["aligned"]:
        raise ValueError("exported prop shading normals oppose triangle winding")
    return votes


def fbx_contract_from_tree(root, version, expected_bounds) -> dict:
    """Check serialized axes/units and the simple rigid FBX model transform."""
    def child(node, name):
        found = [entry for entry in node.elems if entry.id == name]
        if len(found) != 1:
            raise ValueError("missing/ambiguous FBX element: " + name.decode())
        return found[0]

    def properties(node):
        return {entry.props[0].decode(): list(entry.props[4:])
                for entry in child(node, b"Properties70").elems if entry.id == b"P"}

    if version != 7400:
        raise ValueError("expected FBX 7.4 for the UE4.22 importer")
    values = properties(child(root, b"GlobalSettings"))
    expected_axes = {"UpAxis": 2, "UpAxisSign": 1, "FrontAxis": 1,
                     "FrontAxisSign": 1, "CoordAxis": 0, "CoordAxisSign": -1}
    axes = {name: values[name][0] for name in expected_axes}
    if axes != expected_axes or values["UnitScaleFactor"] != [1.]:
        raise ValueError("FBX unit or axis convention changed")
    objects = child(root, b"Objects").elems
    geometries = [entry for entry in objects if entry.id == b"Geometry"]
    models = [entry for entry in objects if entry.id == b"Model"]
    if (len(geometries) != 1 or len(models) != 1 or
            geometries[0].props[2] != b"Mesh" or models[0].props[2] != b"Mesh" or
            any(entry.id in (b"Deformer", b"AnimationStack", b"AnimationCurve") for entry in objects)):
        raise ValueError("FBX must contain exactly one rigid mesh without animation/skin")
    values = properties(models[0])
    for name, default in (("PreRotation", [0., 0., 0.]), ("PostRotation", [0., 0., 0.]),
                          ("RotationOffset", [0., 0., 0.]), ("RotationPivot", [0., 0., 0.]),
                          ("ScalingOffset", [0., 0., 0.]), ("ScalingPivot", [0., 0., 0.]),
                          ("GeometricTranslation", [0., 0., 0.]),
                          ("GeometricRotation", [0., 0., 0.]),
                          ("GeometricScaling", [1., 1., 1.])):
        actual = values.get(name, default)
        if (len(actual) != len(default) or not all(math.isfinite(v) for v in actual) or
                any(abs(a - b) > 1e-7 for a, b in zip(actual, default))):
            raise ValueError("unexpected rigid FBX model transform: " + name)
    translation = values.get("Lcl Translation", [0., 0., 0.])
    scale = values.get("Lcl Scaling", [1., 1., 1.])
    rotation = values.get("Lcl Rotation", [0., 0., 0.])
    if (len(translation) != 3 or len(scale) != 3 or len(rotation) != 3 or
            not all(math.isfinite(v) for v in (*translation, *scale, *rotation)) or
            any(v <= 0 for v in scale)):
        raise ValueError("invalid FBX model scale/translation")
    # Blender's default +Y forward -> requested -Y forward conversion is
    # serialized as a half turn around Z. Accept only that measured transform.
    if (abs(rotation[0]) > 1e-4 or abs(rotation[1]) > 1e-4 or
            abs(abs(rotation[2]) - 180.) > 1e-4):
        raise ValueError("unexpected rigid FBX model rotation")
    vertices = child(geometries[0], b"Vertices").props[0]
    if not vertices or len(vertices) % 3 or not all(math.isfinite(v) for v in vertices):
        raise ValueError("invalid FBX vertices")
    cosine, sine = math.cos(math.radians(rotation[2])), math.sin(math.radians(rotation[2]))
    points = []
    for i in range(0, len(vertices), 3):
        x, y, z = (vertices[i + j] * scale[j] for j in range(3))
        points.append((cosine * x - sine * y + translation[0],
                       sine * x + cosine * y + translation[1], z + translation[2]))
    bounds = [[min(p[i] for p in points) for i in range(3)],
              [max(p[i] for p in points) for i in range(3)]]
    # The declared FBX CoordAxisSign=-1 reflects its world X for this UE
    # contract. Combined with the half turn, this is Blender (X,-Y,Z).
    # An actual UE import/cooked-buffer check remains a separate gate.
    target_bounds = [[-bounds[1][0], bounds[0][1], bounds[0][2]],
                     [-bounds[0][0], bounds[1][1], bounds[1][2]]]
    if any(abs(a - b) > POSITION_TOLERANCE_M * 100
           for a, b in zip(sum(target_bounds, []), sum(expected_bounds, []))):
        raise ValueError("serialized FBX centimetre bounds differ from source contract")
    return {"version": version, "unit_scale_factor_cm": 1., "axes": axes,
            "model_scale": scale, "model_translation_cm": translation,
            "model_rotation_degrees": rotation,
            "fbx_bounds_cm": bounds, "expected_ue_bounds_cm": target_bounds,
            "serialized_cm_bounds_verified": True, "ue_import_verified": False}


def fbx_contract(path: Path, expected_bounds):
    from io_scene_fbx.parse_fbx import parse
    root, version = parse(str(path))
    return fbx_contract_from_tree(root, version, expected_bounds)


def main():
    import bpy
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    source, output = args.input.resolve(strict=True), args.output.resolve()
    allowed = (ROOT / "local-debug").resolve()
    if allowed not in source.parents or allowed not in output.parents:
        raise ValueError("input/output must remain strictly inside ignored local-debug")
    if output.exists():
        raise FileExistsError("FBX output exists; use a new directory")
    profile = validate_preparation(source)
    output.mkdir(parents=True)
    report = {"schema": "PESNX_CINEMATIC_PROP_FBX_V1", "preparation": str(source),
              "blender_version": bpy.app.version_string, "cooked": False,
              "runtime_installed": False, "hardware_tested": False, "props": []}
    for prop in profile["props"]:
        gltf = child_file(source.parent, prop["gltf"])
        doc = rigid_gltf(gltf)
        winding = winding_votes(gltf, doc)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 1.
        bpy.ops.import_scene.gltf(filepath=str(gltf), import_pack_images=False)
        objects = list(bpy.context.scene.objects)
        if len(objects) != 1 or objects[0].type != "MESH":
            raise ValueError("one rigid mesh object expected per prop")
        obj = objects[0]
        obj.name = prop["key"]
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        # glTF imports its Y-up conversion as an object rotation. Bake it so
        # the FBX has one simple mesh transform and explicit cm scale.
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        reverse_faces_preserving_normals(obj)
        before_triangles = mesh_triangles(obj)
        source_check = compare_triangles(source_triangles(gltf, doc), before_triangles)
        before = snapshot(obj, before_triangles)
        before["normal_winding_votes"] = normal_winding_votes(obj)
        expected_height = prop["geometry"]["height_m"]
        if (before["has_skin"] or before["triangles"] != prop["geometry"]["triangles"] or
                before["uv_channels"] != prop["geometry"]["uv_sets"][0] or
                not math.isclose(before["bounds_m"][1][2] - before["bounds_m"][0][2],
                                 expected_height, abs_tol=1e-6)):
            raise ValueError("Blender import changed rigid geometry, UV channels or scale")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        fbx = output / (prop["key"] + ".fbx")
        result = bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={"MESH"},
                                         global_scale=1., apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
                                         axis_forward="-Y", axis_up="Z", use_mesh_modifiers=True,
                                         bake_anim=False, path_mode="ABSOLUTE", embed_textures=False,
                                         add_leaf_bones=False)
        if "FINISHED" not in result or not fbx.is_file():
            raise ValueError("FBX export failed")
        serialized = fbx_contract(fbx, prop["geometry"]["expected_ue_bounds_cm"])
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 1.
        bpy.ops.import_scene.fbx(filepath=str(fbx), use_anim=False)
        objects = list(bpy.context.scene.objects)
        if len(objects) != 1 or objects[0].type != "MESH":
            raise ValueError("FBX roundtrip produced an unexpected skeleton/object")
        after_triangles = mesh_triangles(objects[0])
        after = snapshot(objects[0], after_triangles)
        after["normal_winding_votes"] = normal_winding_votes(objects[0])
        roundtrip_check = compare_triangles(before_triangles, after_triangles)
        if (after["has_skin"] or after["triangles"] != before["triangles"] or
                after["uv_channels"] != before["uv_channels"] or
                any(abs(a - b) > 1e-5 for a, b in zip(sum(before["bounds_m"], []), sum(after["bounds_m"], [])))):
            raise ValueError("FBX roundtrip changed geometry/UV correspondence: " + json.dumps({"before": before, "after": after}))
        report["props"].append({"key": prop["key"], "fbx": str(fbx),
                                "sha256": hashlib.sha256(fbx.read_bytes()).hexdigest(),
                                "target_object_path": prop["target_object_path"],
                                "source_winding_votes": winding, "faces_reversed": True,
                                "before": before, "after": after,
                                "source_to_blender": source_check,
                                "roundtrip_corner_check": roundtrip_check,
                                "fbx_contract": serialized,
                                "expected_ue_bounds_cm": prop["geometry"]["expected_ue_bounds_cm"],
                                "roundtrip_verified": True})
    (output / "fbx.local.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PESNX_CINEMATIC_PROP_FBX_OK", str(output))


if __name__ == "__main__":
    main()
