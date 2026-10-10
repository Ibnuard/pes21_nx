"""Convert an owned Anfield FL stadium shell into a local glTF intermediate.

Uses optional local pes-file-tools and pes-fmdl-blender parsers, not vendored
game data. Does not import PC lighting, gameplay, crowds, or the pitch surface.
Output must remain local/ignored. Run stadium_shell_fbx.py in Blender next.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from io import BytesIO

from export_pes_fmdl_gltf import load_fmdl, export_model

PARTS = ("back1", "back2", "front1", "front2", "left1", "left2", "right1", "right2")


def convert(stadium: Path, output: Path, fmdl_parser: Path, pes_tools: Path,
            with_audience_areas=False):
    from PIL import Image
    sys.path.insert(0, str(pes_tools.resolve()))
    from pes_file_tools import fpk, ftex
    source = stadium / "Asset/model/bg/st004/#Win/st004.fpk"
    textures = stadium / "Asset/model/bg/st004/sourceimages/tga/#windx11"
    pack = fpk.FpkFile()
    pack.readFile(str(source))
    output.mkdir(parents=True, exist_ok=True)
    models = output / "source"
    decoded = output / "textures"
    models.mkdir(exist_ok=True)
    decoded.mkdir(exist_ok=True)
    filenames = {p.name.lower(): p for p in textures.iterdir() if p.suffix.lower() == ".ftex"}
    report = {"source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "coordinate_basis": "Fox metres, Y-up; Blender exports centimetres, UE X=Fox X, Y=Fox Z, Z=Fox Y",
              "parts": [], "textures": {}, "missing_textures": []}
    for part in PARTS:
        matches = [(name, data) for name, data in pack.entries.items()
                   if Path(name).name.lower() == part + ".fmdl"]
        if len(matches) != 1:
            raise ValueError("Expected one shell part: " + part)
        path = models / (part + ".fmdl")
        path.write_bytes(matches[0][1])
        model = load_fmdl(path, fmdl_parser)
        for mat in model.materialInstances:
            for role, tex in mat.textures:
                if not role.startswith("Base_"):
                    continue
                stem = Path(tex.filename).stem
                png = decoded / (stem + ".png")
                # Cache only this run's decoded metadata. Reusing an old PNG
                # without its alpha report would turn masked fences opaque on
                # a repeated conversion or after changing the source texture.
                if stem in report["textures"]:
                    continue
                original = filenames.get((stem + ".ftex").lower())
                if original is None:
                    report["missing_textures"].append(tex.filename)
                    continue
                dds = ftex.ftexToDdsBuffer(original.read_bytes())
                img = Image.open(BytesIO(dds)).convert("RGBA")
                img.save(png)
                report["textures"][stem] = dict(width=img.width, height=img.height,
                    alpha_range=img.getchannel("A").getextrema(),
                    sha256=hashlib.sha256(original.read_bytes()).hexdigest())
        document = export_model(model, output / (part + ".gltf"),
            source_name=path.name, texture_root=decoded, position_scale=1.0)
        summary = document["extras"]["meshSummary"]
        report["parts"].append(dict(name=part, meshes=len(summary),
            triangles=sum(x["triangles"] for x in summary),
            vertices=sum(x["vertices"] for x in summary)))
    report["missing_textures"] = sorted(set(report["missing_textures"]))
    report["triangles"] = sum(p["triangles"] for p in report["parts"])
    if report["triangles"] > 180_000:
        raise ValueError("Shell exceeds first-prototype triangle budget")
    if with_audience_areas:
        from stadium_crowd import read_areas
        audience_pack = fpk.FpkFile()
        audience_pack.readFile(str(stadium / 'Asset/model/bg/st004/audi/#Win/audiarea_st004.fpk'))
        areas = [b for n, b in audience_pack.entries.items() if Path(n).name == 'audiarea.bin']
        if len(areas) != 1:
            raise ValueError('Expected one audience area member')
        count = len(read_areas(areas[0]))
        area_path = output/'audiarea.bin'
        area_path.write_bytes(areas[0])
        report['audience_areas'] = {'file': str(area_path), 'quads': count}
    (output / "conversion.local.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("stadium", "output", "fmdl-parser", "pes-tools"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument('--with-audience-areas', action='store_true')
    args = parser.parse_args()
    result = convert(args.stadium, args.output, args.fmdl_parser, args.pes_tools,
                     args.with_audience_areas)
    print(json.dumps({k: v for k, v in result.items() if k != "textures"}, indent=2))
