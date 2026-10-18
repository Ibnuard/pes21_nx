"""Synthetic metadata checks; no copyrighted mesh fixture is required."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_realface_performance import compare, parse_dump, player_rows, validate_gltf_indices


def dump(name="42_face", lods=((30, 60),)):
    blocks = []
    for index, (triangles, vertices) in enumerate(lods):
        blocks.append(f"""        Lods[{index}] =
        {{
            Sections[1] =
            {{
                Sections[0] = {{ Material=None, FirstIndex=0, NumFaces={triangles} }}
            }}
            NumVerts = {vertices}
            IndexCount = {triangles * 3}
            NumTexCoords = 1
        }}""")
    return f"""ClassName: SkeletalMesh4 ObjectName: {name}
    LODInfo[{len(lods)}] = {{ }}
    Lods[{len(lods)}] =
    {{
{chr(10).join(blocks)}
    }}
    LodCount = {len(lods)}
    BoneCount = 29
"""


def test_all_lods_are_separate_and_head_cost_uses_lod_zero():
    meshes = parse_dump(dump(lods=((30, 60), (10, 20))) + dump("42_hair", ((20, 40), (5, 10))))
    assert [x["triangles"] for x in meshes["42_face"]["lods"]] == [30, 10]
    row, = player_rows(meshes)
    assert (row["face_lods"], row["hair_lods"], row["total_triangles"]) == (2, 2, 50)


@pytest.mark.parametrize("old,new", [("IndexCount = 90", "IndexCount = 89"),
                                    ("FirstIndex=0", "FirstIndex=3"),
                                    ("LodCount = 1", "LodCount = 2"),
                                    ("Sections[1] =", "Sections[2] =")])
def test_corrupt_or_partial_counts_are_rejected(old, new):
    with pytest.raises(ValueError):
        parse_dump(dump().replace(old, new))


def test_32bit_dump_requires_independent_accessor_proof():
    mesh = parse_dump(dump(lods=((70000, 100000),)).replace("IndexCount = 210000", "IndexCount = 0"))["42_face"]
    lod = mesh["lods"][0]
    assert lod["index_validation"] == "gltf_required"
    doc = dict(meshes=[dict(primitives=[dict(indices=0)])],
               accessors=[dict(type="SCALAR", componentType=5125, count=210000, bufferView=0)],
               bufferViews=[dict(byteLength=840000)])
    broken = copy.deepcopy(doc)
    broken["bufferViews"][0]["byteLength"] -= 4
    with pytest.raises(ValueError, match="truncated"):
        validate_gltf_indices(broken, lod)
    validate_gltf_indices(doc, lod)
    assert lod["index_validation"] == "gltf_accessor_count"
    with pytest.raises(ValueError):
        parse_dump(dump().replace("IndexCount = 90", "IndexCount = 0"))


def test_native_missing_hair_is_not_counted_as_free_hair():
    meshes = parse_dump(dump() + dump("43_face") + dump("43_hair"))
    with pytest.raises(ValueError, match="Missing mesh pair"):
        player_rows(meshes)
    rows = player_rows(meshes, require_pairs=False)
    assert [r["native_player_id"] for r in rows] == [43]


def test_release_identity_and_hash_must_match():
    native = dict(meshes=parse_dump(dump() + dump("42_hair")), pak_sha256="native")
    patch = dict(meshes=parse_dump(dump(lods=((100, 150),)) + dump("42_hair")), pak_sha256="patch")
    proof = dict(pak_sha256="patch", players=[dict(native_player_id=42, base_id=900,
                 name="Synthetic Player", team_ids=[7], status="candidate_pending_device")],
                 teams=[dict(team_id=7, name="Synthetic Team")])
    report = compare(native, patch, proof)
    assert report["players"][0]["base_id"] == 900
    assert report["players"][0]["total_triangles"] == 130
    assert report["triangles_above_native_max"] == 1
    unmatched_native = dict(native, meshes=parse_dump(dump("43_face") + dump("43_hair")))
    unmatched = compare(unmatched_native, patch, proof)
    assert unmatched["players"][0]["native_slot_triangles"] is None
    assert unmatched["patch"]["metrics"]["total_triangles"]["max"] == 130
    proof["pak_sha256"] = "wrong"
    with pytest.raises(ValueError, match="PAK does not match"):
        compare(native, patch, proof)
    proof["pak_sha256"] = "patch"
    proof["players"][0]["native_player_id"] = 43
    with pytest.raises(ValueError, match="mesh IDs"):
        compare(native, patch, proof)
