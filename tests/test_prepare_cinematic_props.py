"""Synthetic geometry/contract tests; no game payloads are required."""
from pathlib import Path
from types import SimpleNamespace as NS
import math
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_cinematic_props as props


def vector(x=0., y=0., z=0.):
    return NS(x=x, y=y, z=z)


class Bone:
    def __init__(self):
        self.name = "sk_prop"
        self.parent = None
        self.children = []
        self.globalPosition = vector()
        self.localPosition = vector()


def model(prop=props.PROPS[0]):
    root = Bone() if prop.root_bone else None
    vertices = [NS(position=vector(-.2, 0, -.1)),
                NS(position=vector(.2, 0, .1)),
                NS(position=vector(0, prop.height_m, 0))]
    for vertex in vertices:
        vertex.boneMapping = {root: 1.} if root else None
        vertex.uv = [NS(u=0., v=1.), NS(u=.25, v=.75)]
    return NS(bones=[root] if root else [],
              meshes=[NS(vertices=vertices, faces=[NS(vertices=vertices)],
                         vertexFields=NS(uvCount=2))])


def test_exact_descriptor_runtime_and_cooked_namespaces():
    cup, platform = props.PROPS
    assert cup.model_path == "common/demo/prop/cup_int_hi/cup_int_hi.fpk"
    assert platform.model_path == "common/demo/fixdemoobj/winners_platform_common/winners_platform_common.fpk"
    assert cup.object_path == "/Game/Assets/FootballNX/FixDemo/cup_int_hi/cup_int_hi.cup_int_hi"
    assert platform.object_path == "/Game/Assets/FootballNX/FixDemo/platform_cmn/platform_cmn.platform_cmn"
    assert "/#Win/" in cup.archive_path
    assert "/#Win/" not in cup.model_path


@pytest.mark.parametrize("prop", props.PROPS)
def test_metres_to_centimetres_and_vertical_axis(prop):
    result = props.mesh_audit(model(prop), prop)
    assert result["height_m"] == pytest.approx(prop.height_m)
    assert result["expected_ue_bounds_cm"][1][2] == pytest.approx(prop.height_m * 100)
    assert result["expected_ue_bounds_cm"][0] == pytest.approx([-20., -10., 0.])
    assert result["triangles"] == 1
    assert result["uv_sets"] == [2]


def test_single_identity_root_requires_every_vertex_to_be_rigid():
    obj = model()
    obj.meshes[0].vertices[0].boneMapping[obj.bones[0]] = .5
    with pytest.raises(ValueError, match="fully weighted"):
        props.mesh_audit(obj, props.PROPS[0])


def test_rejects_missing_weights_instead_of_silently_attaching_root():
    obj = model()
    obj.meshes[0].vertices[1].boneMapping = {}
    with pytest.raises(ValueError, match="fully weighted"):
        props.mesh_audit(obj, props.PROPS[0])


@pytest.mark.parametrize("failure", ["name", "hierarchy", "root_translation", "scale", "nan"])
def test_rejects_changed_geometry_contract(failure):
    obj = model()
    if failure == "name":
        obj.bones[0].name = "player"
    elif failure == "hierarchy":
        obj.bones[0].children = [Bone()]
    elif failure == "root_translation":
        obj.bones[0].globalPosition.y = .2
    elif failure == "scale":
        obj.meshes[0].vertices[-1].position.y *= 100
    else:
        obj.meshes[0].vertices[0].position.x = math.nan
    with pytest.raises(ValueError):
        props.mesh_audit(obj, props.PROPS[0])


def test_texture_paths_are_exact_and_scoped_to_one_prop():
    texture = NS(directory="/Assets/pes16/demo/prop/cup_int_hi/sourceimages/tga/", filename="cup_bsm.tga")
    assert props.texture_member(props.PROPS[0], texture) == "common/demo/prop/cup_int_hi/sourceimages/tga/#windx11/cup_bsm.ftex"
    texture.directory = "/Assets/pes16/demo/prop/another_cup/sourceimages/tga/"
    with pytest.raises(ValueError, match="namespace"):
        props.texture_member(props.PROPS[0], texture)


@pytest.mark.parametrize("name", ["../texture.tga", "a/b.tga", "a\\b.tga", "texture.png"])
def test_texture_name_does_not_escape_directory(name):
    texture = NS(directory="/Assets/pes16/demo/prop/cup_int_hi/sourceimages/tga", filename=name)
    with pytest.raises(ValueError, match="filename"):
        props.texture_member(props.PROPS[0], texture)


def test_secondary_uvs_survive_shared_exporter():
    document = {"meshes": [{"primitives": [{"attributes": {"TEXCOORD_0": 0}}]}],
                "bufferViews": [], "accessors": [], "buffers": [{}]}
    binary = bytearray(b"abc")
    props.append_extra_uvs(document, binary, model())
    view = document["bufferViews"][0]
    assert view["byteOffset"] == 4
    assert view["byteLength"] == 24
    assert len(binary) == document["buffers"][0]["byteLength"] == 28
    assert struct.unpack_from("<2f", binary, 4) == (.25, .75)
    assert document["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_1"] == 0


def test_rejects_non_finite_secondary_uv():
    obj = model()
    obj.meshes[0].vertices[0].uv[1].u = math.inf
    document = {"meshes": [{"primitives": [{"attributes": {}}]}],
                "bufferViews": [], "accessors": [], "buffers": [{}]}
    with pytest.raises(ValueError, match="secondary UV"):
        props.append_extra_uvs(document, bytearray(), obj)


def test_output_never_overwrites_or_leaves_ignored_root(tmp_path, monkeypatch):
    monkeypatch.setattr(props, "ROOT", tmp_path)
    local = tmp_path / "local-debug"
    local.mkdir()
    assert props.new_local_output(local / "new") == local / "new"
    with pytest.raises(ValueError, match="strictly inside"):
        props.new_local_output(local)
    with pytest.raises(ValueError, match="strictly inside"):
        props.new_local_output(tmp_path / "dist/new")
    (local / "existing").mkdir()
    with pytest.raises(FileExistsError):
        props.new_local_output(local / "existing")


class Archive:
    def __init__(self, items):
        self.items = items

    def read(self, name):
        return self.items[name]


def cup_skeleton():
    data = bytearray(60)
    struct.pack_into("<II", data, 0, 1, 1)
    struct.pack_into("<IIi", data, 8, 0, 40, -1)
    data[52:] = b"sk_prop\0"
    return bytes(data)


def test_native_skeleton_identity_fails_closed():
    values = {props.CHARACTER_PREFIX + "cup_anim_skel.ask": cup_skeleton(),
              props.CHARACTER_PREFIX + "cup_skel.frig": b"synthetic-rig"}
    rows = props.verify_cup_skeleton(Archive(values), Archive(dict(values)))
    assert len(rows) == 2 and all(row["mobile_identical"] for row in rows)
    changed = dict(values)
    changed[props.CHARACTER_PREFIX + "cup_skel.frig"] += b"changed"
    with pytest.raises(ValueError, match="differs"):
        props.verify_cup_skeleton(Archive(values), Archive(changed))


def test_texture_decoder_rejects_oversize_before_external_decode():
    raw = bytearray(64)
    raw[:4] = b"FTEX"
    struct.pack_into("<3H", raw, 10, 8192, 8192, 1)
    with pytest.raises(ValueError, match="bounded"):
        props.decode_texture(bytes(raw), None)
