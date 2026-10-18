"""Synthetic FBX preparation checks, runnable without Blender/game payloads."""
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import cinematic_props_fbx as fbx


def triangle(offset=0.):
    return ((offset + .100004999, 0., 0., .1, .2, .7, .8),
            (offset + 1., 0., 0., .3, .4, .9, 1.),
            (offset, 1., 0., .5, .6, 1.1, 1.2))


def test_oriented_matching_accepts_only_small_drift_and_cyclic_order():
    first, second = triangle(), triangle(2.)
    drifted = tuple(tuple(v + 2e-8 if i < 3 else v for i, v in enumerate(row)) for row in first)
    # This harmless drift crosses the old rounded-hash boundary.
    assert round(first[0][0], 5) != round(drifted[0][0], 5)
    result = fbx.compare_triangles([first, second], [second[1:] + second[:1], drifted[2:] + drifted[:2]])
    assert result["triangles_matched"] == 2
    assert result["uv_channels"] == 2
    assert result["max_position_delta_m"] == pytest.approx(2e-8)
    assert result["max_uv_delta"] == 0
    assert result["winding_and_uv_corners_verified"] is True


@pytest.mark.parametrize("change", ["winding", "uv0", "uv1", "position", "duplicate", "nan"])
def test_oriented_matching_rejects_corruption(change):
    expected = [triangle(), triangle(2.)]
    actual = [[list(row) for row in tri] for tri in expected]
    if change == "winding":
        actual[0].reverse()
    elif change in ("uv0", "uv1"):
        index = 3 if change == "uv0" else 5
        actual[0][0][index], actual[0][1][index] = actual[0][1][index], actual[0][0][index]
    elif change == "position":
        actual[0][0][0] += fbx.POSITION_TOLERANCE_M * 2
    elif change == "duplicate":
        actual[1] = actual[0]
    else:
        actual[0][0][0] = math.nan
    with pytest.raises(ValueError):
        fbx.compare_triangles(expected, actual)


def test_oriented_matching_preserves_duplicate_triangle_count():
    tri = triangle()
    assert fbx.compare_triangles([tri, tri], [tri, tri])["triangles_matched"] == 2
    with pytest.raises(ValueError, match="count"):
        fbx.compare_triangles([tri, tri], [tri])


def gltf_fixture(folder: Path, key="synthetic"):
    folder.mkdir(parents=True, exist_ok=True)
    doc = {"nodes": [{"mesh": 0}], "meshes": [], "buffers": [], "bufferViews": [], "accessors": []}
    binary = bytearray()

    def add(rows, shape, code="f", component=5126):
        binary.extend(bytes(-len(binary) % 4))
        start = len(binary)
        for row in rows:
            binary.extend(struct.pack("<" + code * len(row), *row))
        index = len(doc["accessors"])
        doc["bufferViews"].append({"buffer": 0, "byteOffset": start, "byteLength": len(binary) - start})
        doc["accessors"].append({"bufferView": index, "type": shape, "componentType": component, "count": len(rows)})
        return index

    attributes = {
        "POSITION": add([(0., 0., 0.), (2., 0., 0.), (0., 1., 0.)], "VEC3"),
        "NORMAL": add([(0., 0., 1.)] * 3, "VEC3"),
        "TEXCOORD_0": add([(.1, .2), (.3, .4), (.5, .6)], "VEC2"),
        "TEXCOORD_1": add([(.7, .8), (.9, 1.), (1.1, 1.2)], "VEC2"),
    }
    indices = add([(0,), (2,), (1,)], "SCALAR", "H", 5123)
    doc["meshes"] = [{"primitives": [{"attributes": attributes, "indices": indices, "mode": 4}]}]
    doc["buffers"] = [{"uri": key + ".bin", "byteLength": len(binary)}]
    (folder / (key + ".bin")).write_bytes(binary)
    path = folder / (key + ".gltf")
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path, doc, binary


def test_source_corner_mapping_reverses_winding_converts_axes_and_flips_both_uvs(tmp_path):
    path, doc, _ = gltf_fixture(tmp_path)
    assert fbx.winding_votes(path, doc) == {"opposed": 1, "aligned": 0, "degenerate": 0}
    corners = fbx.source_triangles(path, doc)[0]
    assert corners[0] == pytest.approx((0., 0., 0., .1, .8, .7, .2))
    assert corners[1] == pytest.approx((2., 0., 0., .3, .6, .9, 0.))
    assert corners[2] == pytest.approx((0., 0., 1., .5, .4, 1.1, -.2))


@pytest.mark.parametrize("change", ["skin", "joints", "weights", "morph", "lines"])
def test_rigid_input_rejects_deformation_and_nontriangles(tmp_path, change):
    path, doc, _ = gltf_fixture(tmp_path)
    primitive = doc["meshes"][0]["primitives"][0]
    if change == "skin":
        doc["nodes"][0]["skin"] = 0
    elif change in ("joints", "weights"):
        primitive["attributes"][change.upper() + "_0"] = 0
    elif change == "morph":
        primitive["targets"] = [{"POSITION": 0}]
    else:
        primitive["mode"] = 1
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError):
        fbx.rigid_gltf(path)


@pytest.mark.parametrize("change", ["truncated", "out_of_bounds", "nan", "sparse", "interleaved"])
def test_accessor_rejects_unsupported_or_invalid_buffer(tmp_path, change):
    _, doc, binary = gltf_fixture(tmp_path)
    if change == "truncated":
        binary = binary[:8]
    elif change == "out_of_bounds":
        doc["accessors"][0]["byteOffset"] = 100
    elif change == "nan":
        struct.pack_into("<f", binary, 0, math.nan)
    elif change == "sparse":
        doc["accessors"][0]["sparse"] = {"count": 1}
    else:
        doc["bufferViews"][0]["byteStride"] = 16
    with pytest.raises(ValueError):
        fbx.accessor_rows(doc, binary, 0)


def preparation_fixture(folder):
    profile = {"schema": "PESNX_CINEMATIC_PROPS_V1", "cooked": False, "props": [], "outputs": []}
    for key, prefix in fbx.PROP_PATHS.items():
        gltf_fixture(folder / key, key)
        profile["props"].append({"key": key, "gltf": f"{key}/{key}.gltf", "target_class": "StaticMesh",
                                 "descriptor_model_path": prefix + ".fpk", "runtime_model_path": prefix + ".xml",
                                 "target_object_path": f"/Game/Assets/FootballNX/FixDemo/{key}/{key}.{key}"})
    for file in sorted(folder.rglob("*")):
        if file.is_file():
            raw = file.read_bytes()
            profile["outputs"].append({"file": file.relative_to(folder).as_posix(), "bytes": len(raw),
                                       "sha256": hashlib.sha256(raw).hexdigest()})
    manifest = folder / "preparation.local.json"
    manifest.write_text(json.dumps(profile), encoding="utf-8")
    return manifest, profile


def test_preparation_requires_complete_hash_coverage(tmp_path):
    path, profile = preparation_fixture(tmp_path)
    assert fbx.validate_preparation(path) == profile
    profile["outputs"].pop()
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(ValueError, match="coverage"):
        fbx.validate_preparation(path)


@pytest.mark.parametrize("change", ["target_object_path", "runtime_model_path", "descriptor_model_path", "hash"])
def test_preparation_rejects_changed_contract(tmp_path, change):
    path, profile = preparation_fixture(tmp_path)
    if change == "hash":
        profile["outputs"][0]["sha256"] = "0" * 64
    else:
        profile["props"][0][change] += "_other"
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(ValueError):
        fbx.validate_preparation(path)


def element(name, props=(), elems=()):
    return NS(id=name, props=list(props), elems=list(elems))


def properties(values):
    return element(b"Properties70", elems=[element(b"P", [name.encode(), b"", b"", b"", *value])
                                           for name, value in values.items()])


def fbx_tree():
    globals_ = {"UpAxis": [2], "UpAxisSign": [1], "FrontAxis": [1], "FrontAxisSign": [1],
                "CoordAxis": [0], "CoordAxisSign": [-1], "UnitScaleFactor": [1.]}
    model = element(b"Model", [1, b"synthetic", b"Mesh"], [properties({"Lcl Rotation": [0., 0., 180.000005],
                                                                          "Lcl Scaling": [100.] * 3})])
    geometry = element(b"Geometry", [2, b"synthetic", b"Mesh"],
                       [element(b"Vertices", [[.1, -.2, 0., 2., 0., 0., .1, .3, .6]])])
    root = element(b"", elems=[element(b"GlobalSettings", elems=[properties(globals_)]),
                               element(b"Objects", elems=[model, geometry])])
    return root, [[10., -30., 0.], [200., 20., 60.]]


def test_serialized_fbx_metres_to_cm_axis_contract_is_not_an_ue_import_claim():
    tree, expected = fbx_tree()
    result = fbx.fbx_contract_from_tree(tree, 7400, expected)
    assert result["serialized_cm_bounds_verified"] is True
    assert result["ue_import_verified"] is False
    assert result["unit_scale_factor_cm"] == 1
    assert result["model_scale"] == [100.] * 3
    for a, b in zip(result["expected_ue_bounds_cm"], expected):
        assert a == pytest.approx(b, abs=2e-4)


@pytest.mark.parametrize("change", ["unit", "axis", "rotation", "scale", "skin", "version"])
def test_serialized_fbx_rejects_contract_drift(change):
    tree, expected = fbx_tree()
    global_props = tree.elems[0].elems[0].elems
    model_props = tree.elems[1].elems[0].elems[0].elems
    version = 7400
    if change in ("unit", "axis"):
        key = b"UnitScaleFactor" if change == "unit" else b"CoordAxisSign"
        next(row for row in global_props if row.props[0] == key).props[-1] = 100 if change == "unit" else 1
    elif change == "rotation":
        model_props[0].props[-1] = 0
    elif change == "scale":
        model_props[1].props[-3:] = [1.] * 3
    elif change == "skin":
        tree.elems[1].elems.append(element(b"Deformer"))
    else:
        version = 7500
    with pytest.raises(ValueError):
        fbx.fbx_contract_from_tree(tree, version, expected)


@pytest.mark.parametrize("path", ["../outside.bin", "/absolute.bin", "a\\b.bin", "C:/a.bin", "a//b.bin"])
def test_resource_paths_cannot_escape_preparation(tmp_path, path):
    with pytest.raises(ValueError, match="unsafe"):
        fbx.child_file(tmp_path, path)


@pytest.mark.skipif(not os.environ.get("PESNX_TEST_BLENDER"), reason="optional Blender executable: set PESNX_TEST_BLENDER")
def test_blender_preserves_split_normals_and_two_uv_seams_when_reversing_faces():
    # Two joined faces with distinct custom normals reproduce the failure of
    # treating split normals as one normal per vertex. No game input is used.
    script = """
import sys
sys.path.insert(0, %r)
import bpy
import cinematic_props_fbx as f
bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new('split-normal-test')
mesh.from_pydata([(0,0,0),(1,0,0),(0,1,0),(0,0,1)], [], [(0,2,1),(0,1,3)])
obj = bpy.data.objects.new('split-normal-test', mesh)
bpy.context.collection.objects.link(obj)
for channel in range(2):
    uv = mesh.uv_layers.new(name='UV' + str(channel))
    for i, row in enumerate(uv.data):
        row.uv = (i * .1, channel + i * .07)
mesh.normals_split_custom_set([(0,0,1)] * 3 + [(0,1,0)] * 3)
mesh.update()
before = f.mesh_triangles(obj)
expected = [(t[0], t[2], t[1]) for t in before]
f.reverse_faces_preserving_normals(obj)
assert f.compare_triangles(expected, f.mesh_triangles(obj))['max_uv_delta'] == 0
assert f.normal_winding_votes(obj) == {'aligned': 2, 'opposed': 0, 'degenerate': 0}
assert not mesh.attributes.get('_pesnx_source_normal')
print('SYNTHETIC_SPLIT_NORMALS_OK')
""" % str(Path(fbx.__file__).parent)
    result = subprocess.run([os.environ["PESNX_TEST_BLENDER"], "--background", "--factory-startup",
                             "--disable-autoexec", "--offline-mode", "--threads", "2",
                             "--python-exit-code", "1", "--python-expr", script],
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SYNTHETIC_SPLIT_NORMALS_OK" in result.stdout
