import base64
import json
import struct
from types import SimpleNamespace

from tools.export_pes_fmdl_gltf import export_model, load_ue4_skeleton_contract


class Bag:
    pass


def vector3(x, y, z):
    return SimpleNamespace(x=x, y=y, z=z)


def vector4(x, y, z, w=1.0):
    return SimpleNamespace(x=x, y=y, z=z, w=w)


def test_exports_skinned_triangle_with_normalized_weights(tmp_path):
    root = Bag()
    root.name = "sk_root"
    root.parent = None
    root.children = []
    root.localPosition = vector4(0, 0, 0, 0)
    root.globalPosition = vector4(0, 1, 0)
    child = Bag()
    child.name = "sk_head"
    child.parent = root
    child.children = []
    child.localPosition = vector4(0, 0, 0, 0)
    child.globalPosition = vector4(0, 2, 0)
    root.children = [child]
    material = SimpleNamespace(
        name="face",
        technique="skin",
        shader="skin_shader",
        textures=[],
        parameters=[],
    )

    def vertex(x, y, weights):
        return SimpleNamespace(
            position=vector3(x, y, 0),
            normal=vector3(0, 0, 1),
            uv=[SimpleNamespace(u=x, v=y)],
            boneMapping=weights,
        )

    vertices = [
        vertex(0, 0, {root: 2, child: 2}),
        vertex(1, 0, {child: 1}),
        vertex(0, 1, {root: 1}),
    ]
    face = SimpleNamespace(vertices=vertices)
    mesh = SimpleNamespace(
        vertices=vertices,
        faces=[face],
        materialInstance=material,
        vertexFields=SimpleNamespace(
            hasNormal=True, hasTangent=False, hasBoneMapping=True, uvCount=1
        ),
        alphaFlags=0,
        shadowFlags=0,
    )
    model = SimpleNamespace(
        bones=[root, child],
        materialInstances=[material],
        meshes=[mesh],
    )

    target = tmp_path / "face.gltf"
    document = export_model(model, target, source_name="face.fmdl")

    assert target.is_file()
    assert target.with_suffix(".bin").is_file()
    assert document["nodes"][0]["children"] == [1]
    assert document["nodes"][1]["translation"] == [0.0, 1.0, 0.0]
    assert document["skins"][0]["joints"] == [0, 1]
    assert document["extras"]["meshSummary"] == [
        {
            "sourceMeshIndex": 0,
            "vertices": 3,
            "triangles": 1,
            "material": "face",
        }
    ]
    primitive = document["meshes"][0]["primitives"][0]
    assert set(primitive["attributes"]) == {
        "POSITION",
        "NORMAL",
        "TEXCOORD_0",
        "JOINTS_0",
        "WEIGHTS_0",
    }
    assert document["accessors"][primitive["indices"]]["count"] == 3


def test_copies_matching_decoded_texture(tmp_path):
    texture_root = tmp_path / "decoded"
    texture_root.mkdir()
    (texture_root / "face_bsm_alp.png").write_bytes(b"png")
    texture = SimpleNamespace(
        filename="face_bsm_alp.dds",
        directory="/sourceimages/",
    )
    material = SimpleNamespace(
        name="face",
        technique="skin",
        shader="skin_shader",
        textures=[("Base_Tex_SRGB", texture)],
        parameters=[],
    )
    vertices = [
        SimpleNamespace(position=vector3(0, 0, 0), uv=[], boneMapping=None),
        SimpleNamespace(position=vector3(1, 0, 0), uv=[], boneMapping=None),
        SimpleNamespace(position=vector3(0, 1, 0), uv=[], boneMapping=None),
    ]
    mesh = SimpleNamespace(
        vertices=vertices,
        faces=[SimpleNamespace(vertices=vertices)],
        materialInstance=material,
        vertexFields=SimpleNamespace(
            hasNormal=False, hasTangent=False, hasBoneMapping=False, uvCount=0
        ),
        alphaFlags=0,
        shadowFlags=0,
    )
    model = SimpleNamespace(bones=[], materialInstances=[material], meshes=[mesh])

    target = tmp_path / "output" / "face.gltf"
    document = export_model(
        model,
        target,
        source_name="face.fmdl",
        texture_root=texture_root,
    )

    assert document["images"] == [{"uri": "face_textures/face_bsm_alp.png"}]
    assert (target.parent / document["images"][0]["uri"]).read_bytes() == b"png"
    assert document["materials"][0]["alphaMode"] == "BLEND"


def test_reads_ue4_reference_skeleton_contract(tmp_path):
    raw = bytearray(struct.pack("<i", 2))
    raw.extend(struct.pack("<iii", 0, 0, -1))
    raw.extend(struct.pack("<iii", 1, 0, 0))
    raw.extend(struct.pack("<i", 2))
    raw.extend(struct.pack("<10f", 0, 0, 0, 1, 0, 0, 0, 1, 1, 1))
    raw.extend(struct.pack("<10f", 0, 0, 0, 1, 1, 2, 3, 1, 1, 1))
    source = tmp_path / "skeleton.json"
    source.write_text(
        json.dumps(
            {
                "NameMap": ["root_main", "sk_head"],
                "Exports": [{"Extras": base64.b64encode(raw).decode("ascii")}],
            }
        ),
        encoding="utf-8",
    )

    bones = load_ue4_skeleton_contract(source)

    assert [bone["name"] for bone in bones] == ["root_main", "sk_head"]
    assert bones[1]["parent"] == 0
    assert bones[1]["translation"] == [1.0, 2.0, 3.0]


def test_retargets_facial_weights_to_mobile_head_and_scales_mesh(tmp_path):
    head = Bag()
    head.name = "sk_head"
    jaw = Bag()
    jaw.name = "skf_jaw"
    material = SimpleNamespace(
        name="face", technique="skin", shader="skin", textures=[], parameters=[]
    )
    vertices = [
        SimpleNamespace(
            position=vector3(0, 0, 0),
            normal=vector3(0, 0, 1),
            uv=[],
            boneMapping={head: 0.25, jaw: 0.75},
        ),
        SimpleNamespace(
            position=vector3(1, 0, 0),
            normal=vector3(0, 0, 1),
            uv=[],
            boneMapping={jaw: 1.0},
        ),
        SimpleNamespace(
            position=vector3(0, 1, 0),
            normal=vector3(0, 0, 1),
            uv=[],
            boneMapping={head: 1.0},
        ),
    ]
    mesh = SimpleNamespace(
        vertices=vertices,
        faces=[SimpleNamespace(vertices=vertices)],
        materialInstance=material,
        vertexFields=SimpleNamespace(
            hasNormal=True, hasTangent=False, hasBoneMapping=True, uvCount=0
        ),
        alphaFlags=0,
        shadowFlags=0,
    )
    model = SimpleNamespace(
        bones=[head, jaw], materialInstances=[material], meshes=[mesh]
    )
    target_skeleton = [
        {
            "name": "root_main",
            "parent": -1,
            "rotation": [0, 0, 0, 1],
            "translation": [0, 0, 0],
            "scale": [1, 1, 1],
        },
        {
            "name": "sk_head",
            "parent": 0,
            "rotation": [0, 0, 0, 1],
            "translation": [0, 2, 0],
            "scale": [1, 1, 1],
        },
    ]

    document = export_model(
        model,
        tmp_path / "retargeted.gltf",
        source_name="face.fmdl",
        target_skeleton=target_skeleton,
        position_scale=100,
    )

    assert document["asset"]["extras"]["boneRemap"] == {
        "sk_head": "sk_head",
        "skf_jaw": "sk_head",
    }
    assert document["skins"][0]["joints"] == [0, 1]
    position = document["meshes"][0]["primitives"][0]["attributes"]["POSITION"]
    assert document["accessors"][position]["max"] == [100.0, 100.0, -0.0]
