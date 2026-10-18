"""Synthetic cooked-buffer validation; optional tools/game fixtures not needed."""
import json
import math
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import validate_cinematic_props_cooked as cooked
from test_cinematic_props_fbx import gltf_fixture


def geometry(tmp_path):
    path, _, _ = gltf_fixture(tmp_path)
    source, normals = cooked.source_geometry(path)
    return source, normals, [[0., 0., 0.], [200., 0., 100.]]


def test_cooked_corner_match_reports_half_uv_and_normal_quantization(tmp_path):
    source, normals, bounds = geometry(tmp_path)
    actual = [tuple(tuple(v + (2e-8 if i < 3 else .0004) for i, v in enumerate(row)) for row in tri)
              for tri in source]
    angle = math.radians(1.)
    quantized = [((math.sin(angle), 0., math.cos(angle)),) * 3]
    report = cooked.compare_cooked(source, normals, actual, quantized, bounds)
    assert report["triangles_matched"] == 1 and report["uv_channels"] == 2
    assert report["max_uv_delta"] == pytest.approx(.0004)
    assert report["max_normal_angle_degrees"] == pytest.approx(1.)
    assert report["normal_winding_votes"] == {"aligned": 1, "opposed": 0, "degenerate": 0}
    assert report["cooked_geometry_verified"] is True


@pytest.mark.parametrize("change", ["axis", "uv_reflect", "winding", "normals", "bounds", "uv_precision"])
def test_cooked_match_does_not_fit_transform_or_hide_damage(tmp_path, change):
    source, normals, bounds = geometry(tmp_path)
    actual = [[list(row) for row in tri] for tri in source]
    actual_normals = normals
    if change == "axis":
        for row in actual[0]:
            row[0], row[2] = row[2], row[0]
    elif change == "uv_reflect":
        for row in actual[0]:
            row[4] = 1. - row[4]
    elif change == "winding":
        actual[0].reverse()
    elif change == "normals":
        actual_normals = [((1., 0., 0.),) * 3]
    elif change == "bounds":
        bounds[1][0] *= 100
    else:
        actual[0][0][5] += .0006
    with pytest.raises(ValueError):
        cooked.compare_cooked(source, normals, actual, actual_normals, bounds)


def test_cooked_reader_accepts_interleaved_signed_normalized_values():
    doc = {"accessors": [{"bufferView": 0, "type": "VEC3", "componentType": 5120, "count": 2,
                           "normalized": True}],
           "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 8, "byteStride": 4}]}
    blob = struct.pack("<8b", -128, 0, 127, 99, 127, 0, -127, 99)
    assert cooked.cooked_accessor(doc, [blob], 0) == [(-1., 0., 1.), (1., 0., -1.)]
    doc["bufferViews"][0]["byteLength"] = 6
    with pytest.raises(ValueError, match="buffer view"):
        cooked.cooked_accessor(doc, [blob], 0)


def test_cooked_material_uv_and_untransformed_mesh_contract(tmp_path):
    path, doc, _ = gltf_fixture(tmp_path)
    doc["materials"] = [{"name": "M_gold_ggx_LR"}]
    doc["meshes"][0]["primitives"][0]["material"] = 0
    path.write_text(json.dumps(doc), encoding="utf-8")
    triangles, normals = cooked.cooked_geometry(path, "M_gold_ggx_LR", 2)
    assert len(triangles) == len(normals) == 1
    with pytest.raises(ValueError, match="material"):
        cooked.cooked_geometry(path, "M_plastic_a", 2)
    with pytest.raises(ValueError, match="UV channel"):
        cooked.cooked_geometry(path, "M_gold_ggx_LR", 1)
    doc["nodes"][0]["scale"] = [100., 100., 100.]
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="untransformed"):
        cooked.cooked_geometry(path, "M_gold_ggx_LR", 2)


@pytest.mark.parametrize("normal", [(0., 0., 0.), (0., 0., math.nan), (10., 0., 0.)])
def test_normals_are_bounded_finite_directions(normal):
    with pytest.raises(ValueError):
        cooked.unit(normal)
