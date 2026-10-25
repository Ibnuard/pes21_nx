#!/usr/bin/env python3
"""Prepare two owned FL26 cinematic props for an isolated UE4.22 cook.

Only cup_int_hi and winners_platform_common are accepted. This tool emits
rigid glTF/PNG cook inputs and a manifest, never a PAK or runtime replacement.
The optional external PES parsers and all game-derived output stay ignored.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import importlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import struct
import sys

from entrance_scene_canary import Cpk, CHARACTER_PREFIX, asset_name, digest
from export_pes_fmdl_gltf import export_model
from convert_ef_referee import read_skeleton

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "PESNX_CINEMATIC_PROPS_V1"


@dataclass(frozen=True)
class Prop:
    key: str
    directory: str
    source_stem: str
    height_m: float
    root_bone: str | None

    @property
    def model_path(self):
        return self.directory + "/" + self.source_stem + ".fpk"

    @property
    def archive_path(self):
        return self.directory + "/#Win/" + self.source_stem + ".fpk"

    @property
    def object_path(self):
        return f"/Game/Assets/FootballNX/FixDemo/{self.key}/{self.key}.{self.key}"


PROPS = (
    Prop("cup_int_hi", "common/demo/prop/cup_int_hi", "cup_int_hi", .6015, "sk_prop"),
    Prop("platform_cmn", "common/demo/fixdemoobj/winners_platform_common",
         "winners_platform_common", .591361, None),
)


def new_local_output(path: Path) -> Path:
    result = path.resolve()
    if (ROOT / "local-debug").resolve() not in result.parents:
        raise ValueError("output must be strictly inside ignored local-debug")
    if result.exists():
        raise FileExistsError("output already exists; choose a new isolated directory")
    return result


def xyz(value):
    result = tuple(float(getattr(value, axis)) for axis in ("x", "y", "z"))
    if not all(math.isfinite(v) for v in result):
        raise ValueError("non-finite geometry")
    return result


def ue_point(point):
    """Fox metres/Y-up -> the project's UE centimetres/Z-up contract."""
    x, y, z = point
    return [100 * x, 100 * z, 100 * y]


def mesh_audit(model, prop: Prop) -> dict:
    """Flatten only a proven identity single-root rigid mesh, never a person."""
    bones = list(model.bones)
    expected = [] if prop.root_bone is None else [prop.root_bone]
    if [bone.name for bone in bones] != expected:
        raise ValueError("unexpected prop skeleton; this is not a skeletal retargeter")
    if bones:
        bone = bones[0]
        if (bone.parent is not None or bone.children or
                any(abs(v) > 1e-7 for v in xyz(bone.globalPosition) + xyz(bone.localPosition))):
            raise ValueError("prop root must have an identity origin and no hierarchy")
    if not 1 <= len(model.meshes) <= 8:
        raise ValueError("unexpected prop mesh count")
    points = []
    vertices = triangles = 0
    for mesh in model.meshes:
        if not 1 <= mesh.vertexFields.uvCount <= 4:
            raise ValueError("prop requires 1..4 UV sets")
        vertices += len(mesh.vertices)
        triangles += len(mesh.faces)
        for vertex in mesh.vertices:
            points.append(xyz(vertex.position))
            mapping = vertex.boneMapping or {}
            if bones:
                if (len(mapping) != 1 or next(iter(mapping)) is not bones[0] or
                        not math.isclose(float(next(iter(mapping.values()))), 1., abs_tol=1e-6)):
                    raise ValueError("prop vertex is not fully weighted to its sole root")
            elif mapping:
                raise ValueError("static prop unexpectedly contains bone weights")
    if not (0 < vertices <= 50000 and 0 < triangles <= 50000):
        raise ValueError("prop exceeds the bounded geometry budget")
    bounds = [[min(p[i] for p in points) for i in range(3)],
              [max(p[i] for p in points) for i in range(3)]]
    height = bounds[1][1] - bounds[0][1]
    if not math.isclose(height, prop.height_m, abs_tol=.001):
        raise ValueError("prop height does not match the audited metre-scale source")
    if abs(bounds[0][1]) > .001 or max(abs(v) for row in bounds for v in row) > 10:
        raise ValueError("unexpected prop origin or dimensions")
    return {"bones": expected, "identity_root": bool(bones),
            "rigid_weights_verified": True, "vertices": vertices, "triangles": triangles,
            "source_bounds_m": bounds, "height_m": height,
            "expected_ue_bounds_cm": [ue_point(bounds[0]), ue_point(bounds[1])],
            "uv_sets": [mesh.vertexFields.uvCount for mesh in model.meshes]}


def texture_member(prop: Prop, texture) -> str:
    directory = texture.directory.replace("\\", "/").rstrip("/")
    expected = "/Assets/pes16/" + prop.directory.removeprefix("common/") + "/sourceimages/tga"
    if directory != expected:
        raise ValueError("texture outside the explicit prop namespace")
    filename = texture.filename
    if (PurePosixPath(filename).name != filename or "\\" in filename or
            not filename.endswith(".tga")):
        raise ValueError("unsupported texture filename")
    return asset_name(prop.directory + "/sourceimages/tga/#windx11/" +
                      filename.removesuffix(".tga") + ".ftex")


def append_extra_uvs(document: dict, binary: bytearray, model) -> None:
    """The shared exporter keeps UV0; preserve any additional prop UVs too."""
    exported = [mesh for mesh in model.meshes if mesh.vertices and mesh.faces]
    if len(exported) != len(document["meshes"]):
        raise ValueError("exported mesh correspondence changed")
    for target, source in zip(document["meshes"], exported):
        attributes = target["primitives"][0]["attributes"]
        for channel in range(1, source.vertexFields.uvCount):
            rows = [(float(v.uv[channel].u), float(v.uv[channel].v)) for v in source.vertices]
            if not all(math.isfinite(value) for row in rows for value in row):
                raise ValueError("non-finite secondary UV")
            binary.extend(bytes((-len(binary)) % 4))
            offset = len(binary)
            binary.extend(b"".join(struct.pack("<2f", *row) for row in rows))
            view = len(document["bufferViews"])
            document["bufferViews"].append({"buffer": 0, "byteOffset": offset,
                                          "byteLength": len(rows) * 8, "target": 34962})
            accessor = len(document["accessors"])
            document["accessors"].append({"bufferView": view, "componentType": 5126,
                                         "count": len(rows), "type": "VEC2"})
            attributes[f"TEXCOORD_{channel}"] = accessor
    document["buffers"][0]["byteLength"] = len(binary)


def parse_fmdl(data: bytes, parser):
    container = parser.FmdlContainer()
    container.readStream(io.BytesIO(data))
    cls = parser.FmdlFile
    strings, extensions = cls.parseStrings(container)
    boxes = cls.parseBoundingBoxes(container)
    model = cls()
    model.bones = cls.parseBones(container, strings, boxes)
    model.materialInstances = cls.parseMaterialInstances(container, strings)
    model.meshes = cls.parseMeshes(container, model.bones, model.materialInstances, extensions)
    return model


def verify_cup_skeleton(source, mobile):
    result = []
    for filename in ("cup_anim_skel.ask", "cup_skel.frig"):
        name = CHARACTER_PREFIX + filename
        donor, target = source.read(name), mobile.read(name)
        if donor != target:
            raise ValueError("Mobile/donor cup skeleton or rig differs")
        if filename.endswith(".ask"):
            if read_skeleton(donor) != [{"name": "sk_prop", "parent": -1, "pos": (0., 0., 0.)}]:
                raise ValueError("cup animation skeleton is not the audited single root")
        result.append({"name": name, "bytes": len(donor), "sha256": digest(donor),
                       "mobile_identical": True})
    return result


def decode_texture(raw, ftex):
    from PIL import Image
    if len(raw) < 64 or raw[:4] != b"FTEX":
        raise ValueError("unsupported FTEX header")
    width, height, depth = struct.unpack_from("<3H", raw, 10)
    if not (0 < width <= 4096 and 0 < height <= 4096 and depth == 1):
        raise ValueError("texture exceeds bounded 2D dimensions")
    image = Image.open(io.BytesIO(ftex.ftexToDdsBuffer(raw)))
    if image.size != (width, height):
        raise ValueError("decoded texture dimensions differ")
    return image.convert("RGBA")


def prepare(source_cpk: Path, mobile_cpk: Path, pes_tools: Path,
            fmdl_parser: Path, output: Path) -> dict:
    output = new_local_output(output)
    for required in (pes_tools / "pes_file_tools/fpk.py", fmdl_parser / "FmdlFile.py"):
        if not required.is_file():
            raise FileNotFoundError(required)
    sys.path[:0] = [str(pes_tools.resolve()), str(fmdl_parser.resolve())]
    try:
        fpk = importlib.import_module("pes_file_tools.fpk")
        ftex = importlib.import_module("pes_file_tools.ftex")
        parser = importlib.import_module("FmdlFile")
    finally:
        del sys.path[:2]
    source, mobile = Cpk(source_cpk), Cpk(mobile_cpk)
    skeletons = verify_cup_skeleton(source, mobile)
    # Validate both geometry contracts before creating an output directory.
    parsed = []
    for prop in PROPS:
        packed = source.read(prop.archive_path)
        pack = fpk.FpkFile()
        pack.read(packed)
        expected = ("/Assets/pes16/" + prop.directory.removeprefix("common/") +
                    "/scenes/" + prop.source_stem + ".fmdl")
        if expected not in pack.entries:
            raise ValueError("expected audited FMDL member missing")
        raw = pack.entries[expected]
        model = parse_fmdl(raw, parser)
        geometry = mesh_audit(model, prop)
        parsed.append((prop, packed, raw, model, geometry))
    output.mkdir(parents=True)
    report = {"schema": SCHEMA, "stage": "mesh-and-texture-inputs-only",
              "source_archive": str(source.path), "source_archive_bytes": source.size,
              "mobile_archive": str(mobile.path), "shared_cup_skeleton": skeletons,
              "axis_contract": {"source": "Fox metres, Y-up", "gltf": "source axes/metres preserved",
                                "blender": "(X,-Z,Y), metres", "ue": "(X,Z,Y)*100, centimetres"},
              "cooked": False, "runtime_installed": False, "hardware_tested": False,
              "props": [], "limitations": [
                  "Cooked UE4.22 assets and the opt-in prop renderer adapter are separate steps.",
                  "Material preview uses base colour plus explicit scalar PBR approximations.",
                  "Normal/specular/metalness source maps are preserved, but packed channels are not guessed.",
                  "Cup actor parenting/animation remains native and must be checked on hardware."]}
    for prop, packed, raw, model, geometry in parsed:
        work = output / prop.key
        textures = work / "textures"
        textures.mkdir(parents=True)
        material_rows, texture_rows, image_indices = [], [], {}
        for material in model.materialInstances:
            row = {"name": material.name, "shader": material.shader, "technique": material.technique,
                   "inputs": [], "preview_metallic": 1.0 if prop.root_bone else 0.,
                   "preview_roughness": .35 if prop.root_bone else .8}
            for role, texture in material.textures:
                name = texture_member(prop, texture)
                if name not in image_indices:
                    content = source.read(name)
                    image = decode_texture(content, ftex)
                    filename = PurePosixPath(name).stem + ".png"
                    image.save(textures / filename)
                    image_indices[name] = len(texture_rows)
                    texture_rows.append({"name": name, "file": "textures/" + filename,
                                         "source_sha256": digest(content), "width": image.width,
                                         "height": image.height, "alpha_range": image.getchannel("A").getextrema()})
                row["inputs"].append({"role": role, "texture": image_indices[name],
                                      "srgb": role == "Base_Tex_SRGB",
                                      "preview_bound": role == "Base_Tex_SRGB"})
            material_rows.append(row)
        rigid = copy.copy(model)
        rigid.bones = []  # Only after mesh_audit proved an identity rigid root.
        gltf = work / (prop.key + ".gltf")
        document = export_model(rigid, gltf, source_name=prop.source_stem + ".fmdl", position_scale=1.)
        binary = bytearray(gltf.with_suffix(".bin").read_bytes())
        append_extra_uvs(document, binary, rigid)
        document["samplers"] = [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}]
        document["images"] = [{"uri": row["file"]} for row in texture_rows]
        document["textures"] = [{"source": index, "sampler": 0} for index in range(len(texture_rows))]
        for target, row in zip(document["materials"], material_rows):
            pbr = target["pbrMetallicRoughness"]
            pbr.update(metallicFactor=row["preview_metallic"], roughnessFactor=row["preview_roughness"])
            for item in row["inputs"]:
                if item["preview_bound"]:
                    pbr["baseColorTexture"] = {"index": item["texture"]}
        document["extras"]["rigidRootAudit"] = geometry
        gltf.with_suffix(".bin").write_bytes(binary)
        gltf.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        report["props"].append({"key": prop.key, "descriptor_model_path": prop.model_path,
                                "runtime_model_path": "cpk_dat/" + prop.model_path.removesuffix(".fpk") + ".xml",
                                "donor_archive_path": prop.archive_path,
                                "fpk_sha256": digest(packed), "fmdl_sha256": digest(raw),
                                "target_class": "StaticMesh", "target_object_path": prop.object_path,
                                "gltf": gltf.relative_to(output).as_posix(), "geometry": geometry,
                                "materials": material_rows, "textures": texture_rows})
    report["outputs"] = [{"file": p.relative_to(output).as_posix(), "bytes": p.stat().st_size,
                           "sha256": digest(p.read_bytes())} for p in sorted(output.rglob("*")) if p.is_file()]
    (output / "preparation.local.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-cpk", "mobile-cpk", "pes-tools", "fmdl-parser", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    report = prepare(args.source_cpk, args.mobile_cpk, args.pes_tools, args.fmdl_parser, args.output)
    print(json.dumps({"schema": report["schema"], "props": [p["key"] for p in report["props"]],
                      "output": str(args.output.resolve()), "cooked": False}, indent=2))


if __name__ == "__main__":
    main()
