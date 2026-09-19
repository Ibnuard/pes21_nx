"""Export a PES FMDL model to an inspectable glTF 2.0 intermediate.

The repository intentionally does not vendor the third-party FMDL parser or
game assets. Pass a local checkout of ``pes-fmdl-blender/pes-fmdl`` through
``--pes-fmdl-root`` and keep source/output paths under an ignored directory.

This exporter preserves mesh positions, normals, the first UV set, skin
weights, the FMDL bone names/positions, material metadata, and any decoded PNG
textures that can be matched by name. With a mobile skeleton contract, Fox
coordinates are converted through the target UE4 Z-up basis into glTF Y-up and
scaled from metres to centimetres. It does not cook Unreal Engine assets.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
from pathlib import Path
import shutil
import struct
import sys
from typing import Iterable, Sequence


ARRAY_BUFFER = 34962
ELEMENT_ARRAY_BUFFER = 34963
FLOAT = 5126
UNSIGNED_SHORT = 5123
UNSIGNED_INT = 5125

UE_TO_GLTF = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, -1.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]
GLTF_TO_UE = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 0.0, -1.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]


def _xyz(vector) -> tuple[float, float, float]:
    return (float(vector.x), float(vector.y), float(vector.z))


def _xyzw(vector) -> tuple[float, float, float, float]:
    return (float(vector.x), float(vector.y), float(vector.z), float(vector.w))


def _finite(values: Iterable[float]) -> list[float]:
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result):
        raise ValueError("model contains a non-finite numeric value")
    return result


def _bounds(rows: Sequence[Sequence[float]]) -> tuple[list[float], list[float]]:
    if not rows:
        raise ValueError("cannot calculate bounds for an empty accessor")
    width = len(rows[0])
    return (
        [min(float(row[index]) for row in rows) for index in range(width)],
        [max(float(row[index]) for row in rows) for index in range(width)],
    )


def _matrix_multiply(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [sum(left[row][k] * right[k][column] for k in range(4)) for column in range(4)]
        for row in range(4)
    ]


def _trs_matrix(
    rotation: Sequence[float], translation: Sequence[float], scale: Sequence[float]
) -> list[list[float]]:
    x, y, z, w = rotation
    sx, sy, sz = scale
    return [
        [(1 - 2*y*y - 2*z*z) * sx, (2*x*y - 2*z*w) * sy, (2*x*z + 2*y*w) * sz, translation[0]],
        [(2*x*y + 2*z*w) * sx, (1 - 2*x*x - 2*z*z) * sy, (2*y*z - 2*x*w) * sz, translation[1]],
        [(2*x*z - 2*y*w) * sx, (2*y*z + 2*x*w) * sy, (1 - 2*x*x - 2*y*y) * sz, translation[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _inverse_affine(matrix: list[list[float]]) -> list[list[float]]:
    a, b, c = matrix[0][:3]
    d, e, f = matrix[1][:3]
    g, h, i = matrix[2][:3]
    determinant = a*(e*i - f*h) - b*(d*i - f*g) + c*(d*h - e*g)
    if abs(determinant) < 1e-12:
        raise ValueError("skeleton contains a singular bind transform")
    inverse = [
        [(e*i - f*h)/determinant, (c*h - b*i)/determinant, (b*f - c*e)/determinant],
        [(f*g - d*i)/determinant, (a*i - c*g)/determinant, (c*d - a*f)/determinant],
        [(d*h - e*g)/determinant, (b*g - a*h)/determinant, (a*e - b*d)/determinant],
    ]
    translation = [matrix[row][3] for row in range(3)]
    inverse_translation = [
        -sum(inverse[row][column] * translation[column] for column in range(3))
        for row in range(3)
    ]
    return [
        inverse[0] + [inverse_translation[0]],
        inverse[1] + [inverse_translation[1]],
        inverse[2] + [inverse_translation[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _column_major(matrix: list[list[float]]) -> list[float]:
    return [matrix[row][column] for column in range(4) for row in range(4)]


def load_ue4_skeleton_contract(path: Path) -> list[dict]:
    """Read UE4.22 ``FReferenceSkeleton`` data from a UAssetGUI JSON export."""

    document = json.loads(path.read_text(encoding="utf-8-sig"))
    exports = document.get("Exports", [])
    if len(exports) != 1 or not exports[0].get("Extras"):
        raise ValueError("expected one Skeleton export with serialized Extras")
    names = document["NameMap"]
    raw = base64.b64decode(exports[0]["Extras"])
    if len(raw) < 4:
        raise ValueError("truncated Skeleton Extras")
    count = struct.unpack_from("<i", raw, 0)[0]
    if not 0 < count < 1024:
        raise ValueError(f"invalid reference-skeleton bone count: {count}")
    offset = 4
    bones: list[dict] = []
    for index in range(count):
        if offset + 12 > len(raw):
            raise ValueError("truncated reference-skeleton bone info")
        name_index, name_number, parent = struct.unpack_from("<iii", raw, offset)
        offset += 12
        if not 0 <= name_index < len(names) or name_number != 0:
            raise ValueError("unsupported reference-skeleton FName")
        if parent >= index or parent < -1:
            raise ValueError("invalid reference-skeleton parent index")
        bones.append({"name": names[name_index], "parent": parent})
    if offset + 4 > len(raw) or struct.unpack_from("<i", raw, offset)[0] != count:
        raise ValueError("reference-skeleton pose count mismatch")
    offset += 4
    for bone in bones:
        if offset + 40 > len(raw):
            raise ValueError("truncated reference-skeleton bind pose")
        values = _finite(struct.unpack_from("<10f", raw, offset))
        offset += 40
        bone["rotation"] = values[:4]
        bone["translation"] = values[4:7]
        bone["scale"] = values[7:10]
    return bones


def _mobile_bone_name(source_name: str, targets: set[str]) -> str:
    if source_name in targets:
        return source_name
    aliases = {
        "dsk_clavicle_l": "sk_shoulder_l",
        "dsk_clavicle_r": "sk_shoulder_r",
        "dsk_neckback": "sk_neck",
        "dsk_scm": "sk_neck",
    }
    target = aliases.get(source_name)
    if target in targets:
        return target
    if source_name.startswith("skf_") and "sk_head" in targets:
        return "sk_head"
    raise ValueError(f"no mobile skeleton mapping for FMDL bone: {source_name}")


class BufferBuilder:
    def __init__(self) -> None:
        self.data = bytearray()
        self.views: list[dict] = []
        self.accessors: list[dict] = []

    def add_accessor(
        self,
        rows: Sequence[Sequence[float | int]],
        fmt: str,
        component_type: int,
        accessor_type: str,
        *,
        target: int | None = None,
        include_bounds: bool = False,
    ) -> int:
        if not rows:
            raise ValueError("cannot add an empty accessor")
        while len(self.data) % 4:
            self.data.append(0)
        offset = len(self.data)
        flat = [component for row in rows for component in row]
        self.data.extend(struct.pack("<" + fmt * len(flat), *flat))
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(self.data) - offset}
        if target is not None:
            view["target"] = target
        view_index = len(self.views)
        self.views.append(view)
        accessor = {
            "bufferView": view_index,
            "componentType": component_type,
            "count": len(rows),
            "type": accessor_type,
        }
        if include_bounds:
            minimum, maximum = _bounds(rows)
            accessor["min"] = minimum
            accessor["max"] = maximum
        accessor_index = len(self.accessors)
        self.accessors.append(accessor)
        return accessor_index


def _texture_lookup(texture_root: Path | None) -> dict[str, Path]:
    if texture_root is None:
        return {}
    if not texture_root.is_dir():
        raise FileNotFoundError(f"texture root not found: {texture_root}")
    return {
        path.name.casefold(): path
        for path in texture_root.rglob("*.png")
        if path.is_file()
    }


def _material_texture_entries(material) -> list[tuple[str, object]]:
    return list(getattr(material, "textures", []) or [])


def export_model(
    model,
    output: Path,
    *,
    source_name: str,
    texture_root: Path | None = None,
    target_skeleton: list[dict] | None = None,
    position_scale: float = 1.0,
) -> dict:
    """Export an already parsed ``FmdlFile`` object and return the glTF JSON."""

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    binary_path = output.with_suffix(".bin")
    builder = BufferBuilder()

    source_bones = list(model.bones)
    bone_remap: dict[str, str] = {}
    bone_nodes: list[dict] = []
    inverse_bind_rows: list[list[float]] = []
    root_bones: list[int] = []
    if target_skeleton is not None:
        target_by_name = {bone["name"]: index for index, bone in enumerate(target_skeleton)}
        if len(target_by_name) != len(target_skeleton):
            raise ValueError("target skeleton contains duplicate bone names")
        target_names = set(target_by_name)
        bone_indices = {}
        for source_bone in source_bones:
            target_name = _mobile_bone_name(source_bone.name, target_names)
            bone_remap[source_bone.name] = target_name
            bone_indices[id(source_bone)] = target_by_name[target_name]
        children: dict[int, list[int]] = {index: [] for index in range(len(target_skeleton))}
        global_matrices: list[list[list[float]]] = []
        for index, bone in enumerate(target_skeleton):
            parent = int(bone["parent"])
            if parent < 0:
                root_bones.append(index)
            else:
                children[parent].append(index)
            ue_local_matrix = _trs_matrix(
                bone["rotation"], bone["translation"], bone["scale"]
            )
            local_matrix = _matrix_multiply(
                _matrix_multiply(UE_TO_GLTF, ue_local_matrix), GLTF_TO_UE
            )
            global_matrix = (
                local_matrix
                if parent < 0
                else _matrix_multiply(global_matrices[parent], local_matrix)
            )
            global_matrices.append(global_matrix)
            node = {
                "name": bone["name"],
                "matrix": _column_major(local_matrix),
                "extras": {"ue4ReferenceSkeletonIndex": index},
            }
            bone_nodes.append(node)
            inverse_bind_rows.append(_column_major(_inverse_affine(global_matrix)))
        for index, node in enumerate(bone_nodes):
            if children[index]:
                node["children"] = children[index]
        bones = target_skeleton
    else:
        bones = source_bones
        bone_indices = {id(bone): index for index, bone in enumerate(bones)}
        for index, bone in enumerate(bones):
            global_position = _finite(_xyz(bone.globalPosition))
            if bone.parent is not None and id(bone.parent) in bone_indices:
                parent_position = _finite(_xyz(bone.parent.globalPosition))
                translation = [
                    global_position[axis] - parent_position[axis]
                    for axis in range(3)
                ]
            else:
                translation = global_position
                root_bones.append(index)
            node = {
                "name": bone.name or f"bone_{index}",
                "translation": translation,
                "extras": {
                    "fmdlGlobalPosition": global_position,
                    "fmdlLocalPosition": _finite(_xyz(bone.localPosition)),
                },
            }
            children = [
                bone_indices[id(child)]
                for child in bone.children
                if id(child) in bone_indices
            ]
            if children:
                node["children"] = children
            bone_nodes.append(node)
            x, y, z = global_position
            inverse_bind_rows.append(
                [
                    1.0, 0.0, 0.0, 0.0,
                    0.0, 1.0, 0.0, 0.0,
                    0.0, 0.0, 1.0, 0.0,
                    -x, -y, -z, 1.0,
                ]
            )

    inverse_bind_accessor = None
    if bones:
        inverse_bind_accessor = builder.add_accessor(
            inverse_bind_rows, "f", FLOAT, "MAT4"
        )

    lookup = _texture_lookup(texture_root)
    texture_directory = output.parent / f"{output.stem}_textures"
    images: list[dict] = []
    textures: list[dict] = []
    copied_textures: dict[Path, int] = {}

    def texture_index(texture) -> int | None:
        source_filename = Path(texture.filename).with_suffix(".png").name.casefold()
        source = lookup.get(source_filename)
        if source is None:
            return None
        source = source.resolve()
        if source in copied_textures:
            return copied_textures[source]
        texture_directory.mkdir(parents=True, exist_ok=True)
        target = texture_directory / source.name
        shutil.copy2(source, target)
        image_index = len(images)
        images.append({"uri": target.relative_to(output.parent).as_posix()})
        index = len(textures)
        textures.append({"sampler": 0, "source": image_index})
        copied_textures[source] = index
        return index

    gltf_materials: list[dict] = []
    material_indices: dict[object, int] = {}
    for material in model.materialInstances:
        entry = {
            "name": material.name,
            "pbrMetallicRoughness": {
                "baseColorFactor": [1.0, 1.0, 1.0, 1.0],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.8,
            },
            "extras": {
                "fmdlTechnique": material.technique,
                "fmdlShader": material.shader,
                "fmdlTextures": [
                    {
                        "role": role,
                        "filename": texture.filename,
                        "directory": texture.directory,
                    }
                    for role, texture in _material_texture_entries(material)
                ],
                "fmdlParameters": [
                    {"name": name, "value": list(value)}
                    for name, value in (getattr(material, "parameters", []) or [])
                ],
            },
        }
        for role, texture in _material_texture_entries(material):
            index = texture_index(texture)
            if index is None:
                continue
            if role == "Base_Tex_SRGB":
                entry["pbrMetallicRoughness"]["baseColorTexture"] = {"index": index}
                if "alp" in texture.filename.casefold():
                    entry["alphaMode"] = "BLEND"
                    entry["doubleSided"] = True
            elif role == "NormalMap_Tex_NRM":
                entry["normalTexture"] = {"index": index}
        material_indices[id(material)] = len(gltf_materials)
        gltf_materials.append(entry)

    gltf_meshes: list[dict] = []
    mesh_nodes: list[dict] = []
    mesh_summaries: list[dict] = []
    for mesh_index, mesh in enumerate(model.meshes):
        vertices = list(mesh.vertices)
        if not vertices or not mesh.faces:
            continue
        vertex_indices = {id(vertex): index for index, vertex in enumerate(vertices)}
        positions = []
        for vertex in vertices:
            x, y, z = _finite(_xyz(vertex.position))
            # FMDL -> UE is (X,Z,Y); UE Z-up -> glTF Y-up is (X,Z,-Y).
            # Combined, the serialized glTF position is (X,Y,-Z).
            coordinates = (x, y, -z) if target_skeleton is not None else (x, y, z)
            positions.append([component * position_scale for component in coordinates])
        attributes = {
            "POSITION": builder.add_accessor(
                positions, "f", FLOAT, "VEC3", target=ARRAY_BUFFER, include_bounds=True
            )
        }
        if mesh.vertexFields.hasNormal:
            normals = []
            for vertex in vertices:
                x, y, z = _finite(_xyz(vertex.normal))
                normals.append([x, y, -z] if target_skeleton is not None else [x, y, z])
            attributes["NORMAL"] = builder.add_accessor(
                normals, "f", FLOAT, "VEC3", target=ARRAY_BUFFER
            )
        if mesh.vertexFields.hasTangent:
            tangents = []
            for vertex in vertices:
                x, y, z, w = _finite(_xyzw(vertex.tangent))
                tangents.append(
                    [x, y, -z, -w] if target_skeleton is not None else [x, y, z, w]
                )
            attributes["TANGENT"] = builder.add_accessor(
                tangents, "f", FLOAT, "VEC4", target=ARRAY_BUFFER
            )
        if mesh.vertexFields.uvCount:
            uv0 = [_finite((vertex.uv[0].u, vertex.uv[0].v)) for vertex in vertices]
            attributes["TEXCOORD_0"] = builder.add_accessor(
                uv0, "f", FLOAT, "VEC2", target=ARRAY_BUFFER
            )
        if mesh.vertexFields.hasBoneMapping and bones:
            joints: list[list[int]] = []
            weights: list[list[float]] = []
            for vertex in vertices:
                combined: dict[int, float] = {}
                for bone, weight in (vertex.boneMapping or {}).items():
                    joint = bone_indices.get(id(bone))
                    if joint is not None and weight > 0:
                        combined[joint] = combined.get(joint, 0.0) + float(weight)
                weighted = sorted(
                    combined.items(),
                    key=lambda pair: pair[1],
                    reverse=True,
                )[:4]
                total = sum(weight for _, weight in weighted)
                if total <= 0:
                    weighted = [(0, 1.0)]
                    total = 1.0
                joint_row = [joint for joint, _ in weighted]
                weight_row = [weight / total for _, weight in weighted]
                while len(joint_row) < 4:
                    joint_row.append(0)
                    weight_row.append(0.0)
                joints.append(joint_row)
                weights.append(weight_row)
            attributes["JOINTS_0"] = builder.add_accessor(
                joints, "H", UNSIGNED_SHORT, "VEC4", target=ARRAY_BUFFER
            )
            attributes["WEIGHTS_0"] = builder.add_accessor(
                weights, "f", FLOAT, "VEC4", target=ARRAY_BUFFER
            )

        triangles = [
            [vertex_indices[id(vertex)] for vertex in face.vertices]
            for face in mesh.faces
        ]
        if target_skeleton is not None:
            triangles = [[a, c, b] for a, b, c in triangles]
        scalar_indices = [[index] for triangle in triangles for index in triangle]
        index_component = UNSIGNED_SHORT if len(vertices) <= 65535 else UNSIGNED_INT
        index_format = "H" if index_component == UNSIGNED_SHORT else "I"
        indices = builder.add_accessor(
            scalar_indices,
            index_format,
            index_component,
            "SCALAR",
            target=ELEMENT_ARRAY_BUFFER,
            include_bounds=True,
        )
        primitive = {
            "attributes": attributes,
            "indices": indices,
            "mode": 4,
            "material": material_indices[id(mesh.materialInstance)],
        }
        gltf_mesh_index = len(gltf_meshes)
        gltf_meshes.append(
            {
                "name": f"mesh_{mesh_index}_{mesh.materialInstance.name}",
                "primitives": [primitive],
                "extras": {
                    "fmdlAlphaFlags": mesh.alphaFlags,
                    "fmdlShadowFlags": mesh.shadowFlags,
                },
            }
        )
        node = {"name": f"mesh_{mesh_index}", "mesh": gltf_mesh_index}
        if bones and mesh.vertexFields.hasBoneMapping:
            node["skin"] = 0
        mesh_nodes.append(node)
        mesh_summaries.append(
            {
                "sourceMeshIndex": mesh_index,
                "vertices": len(vertices),
                "triangles": len(triangles),
                "material": mesh.materialInstance.name,
            }
        )

    skeleton_root_index = None
    skeleton_nodes: list[dict] = []
    if bones:
        skeleton_root_index = len(bone_nodes)
        skeleton_nodes.append({"name": "FMDL armature", "children": root_bones})
    nodes = bone_nodes + skeleton_nodes + mesh_nodes
    first_mesh_node = len(bone_nodes) + len(skeleton_nodes)
    scene_nodes = (
        ([skeleton_root_index] if skeleton_root_index is not None else [])
        + list(range(first_mesh_node, len(nodes)))
    )
    document = {
        "asset": {
            "version": "2.0",
            "generator": "PES 2021 NX FMDL intermediate exporter",
            "extras": {
                "source": source_name,
                "coordinateSystem": (
                    "glTF Y-up; FMDL -> UE4 Z-up is (X,Y,Z) -> (X,Z,Y)"
                    if target_skeleton is not None
                    else "Fox Engine FMDL native axes preserved"
                ),
                "conversionStage": "intermediate; not an Unreal Engine cooked asset",
                "positionScale": position_scale,
                "boneRemap": bone_remap,
            },
        },
        "scene": 0,
        "scenes": [{"name": Path(source_name).stem, "nodes": scene_nodes}],
        "nodes": nodes,
        "meshes": gltf_meshes,
        "materials": gltf_materials,
        "buffers": [{"uri": binary_path.name, "byteLength": len(builder.data)}],
        "bufferViews": builder.views,
        "accessors": builder.accessors,
        "extras": {"meshSummary": mesh_summaries},
    }
    if bones:
        document["skins"] = [
            {
                "name": "UE4 mobile target skeleton" if target_skeleton else "FMDL skeleton",
                "joints": list(range(len(bones))),
                "inverseBindMatrices": inverse_bind_accessor,
                "skeleton": skeleton_root_index,
            }
        ]
    if images:
        document["samplers"] = [
            {
                "magFilter": 9729,
                "minFilter": 9987,
                "wrapS": 10497,
                "wrapT": 10497,
            }
        ]
        document["images"] = images
        document["textures"] = textures

    binary_path.write_bytes(builder.data)
    output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return document


def load_fmdl(source: Path, parser_root: Path):
    parser_file = parser_root / "FmdlFile.py"
    if not parser_file.is_file():
        raise FileNotFoundError(f"FmdlFile.py not found under: {parser_root}")
    sys.path.insert(0, str(parser_root.resolve()))
    try:
        from FmdlFile import FmdlFile  # type: ignore
    finally:
        sys.path.pop(0)
    model = FmdlFile()
    model.readFile(str(source))
    return model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Input .fmdl file")
    parser.add_argument("--output", required=True, type=Path, help="Output .gltf path")
    parser.add_argument(
        "--pes-fmdl-root",
        required=True,
        type=Path,
        help="Local pes-fmdl-blender/pes-fmdl directory",
    )
    parser.add_argument(
        "--texture-root",
        type=Path,
        help="Optional directory containing decoded .png textures",
    )
    parser.add_argument(
        "--target-skeleton-json",
        type=Path,
        help="Optional UAssetGUI JSON for the UE4.22 mobile Skeleton asset",
    )
    parser.add_argument(
        "--position-scale",
        type=float,
        help="Mesh position multiplier (defaults to 100 with a mobile skeleton)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.suffix.casefold() != ".gltf":
        raise ValueError("--output must end in .gltf")
    model = load_fmdl(args.source, args.pes_fmdl_root)
    target_skeleton = (
        load_ue4_skeleton_contract(args.target_skeleton_json)
        if args.target_skeleton_json
        else None
    )
    position_scale = args.position_scale
    if position_scale is None:
        position_scale = 100.0 if target_skeleton else 1.0
    if not math.isfinite(position_scale) or position_scale <= 0:
        raise ValueError("--position-scale must be a positive finite value")
    document = export_model(
        model,
        args.output,
        source_name=args.source.name,
        texture_root=args.texture_root,
        target_skeleton=target_skeleton,
        position_scale=position_scale,
    )
    summary = document["extras"]["meshSummary"]
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "source_bones": len(model.bones),
                "target_bones": len(target_skeleton or model.bones),
                "meshes": len(summary),
                "vertices": sum(mesh["vertices"] for mesh in summary),
                "triangles": sum(mesh["triangles"] for mesh in summary),
                "textures": len(document.get("images", [])),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
