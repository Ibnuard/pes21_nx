"""Read-only audit of an owned pitch PAK and its native perimeter dependencies.

All decoded payloads and reports belong in ignored local-debug output. Nothing
is repacked, recoloured or installed. The supplied PAK is never modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np

from build_low_pitch_phase_patch import name_entries
from cooked_texture import Texture

CONTENT = Path("PesMobile/Content/Assets/bg_lighting_AM1")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(pak, native, output, repak):
    output.mkdir(parents=True, exist_ok=False)
    stage = output / "patch"
    before = digest(pak)
    subprocess.run([str(repak), "unpack", str(pak), "-o", str(stage)], check=True)
    files = sorted(p for p in stage.rglob("*") if p.is_file())
    report = {"pak": str(pak), "sha256": before, "bytes": pak.stat().st_size,
              "members": {p.relative_to(stage).as_posix(): digest(p) for p in files},
              "perimeter_materials": [], "textures": []}
    textures = set()
    for name in ("M_PitchSide", "M_field_ed"):
        relative = CONTENT / "Materials" / (name + ".uasset")
        overridden = (stage / relative).exists()
        material = (stage if overridden else native) / relative
        dependencies = [n for n, _, _ in name_entries(material.read_bytes())
                        if n.startswith("/Game/") and "/Textures/" in n]
        report["perimeter_materials"].append(
            {"name": name, "overridden": overridden, "textures": dependencies})
        textures.update(dependencies)
    for dependency in sorted(textures):
        relative = Path("PesMobile/Content") / (dependency.removeprefix("/Game/") + ".uexp")
        overridden = (stage / relative).exists()
        path = (stage if overridden else native) / relative
        texture = Texture(path)
        decoded = texture.decode()
        decoded.save(output / (path.stem + ".png"))
        rgb = np.asarray(decoded)[:, :, :3].astype(np.int16)
        green = (rgb[:, :, 1] > 180) & (rgb[:, :, 1] > rgb[:, :, 0] * 1.5) & (rgb[:, :, 1] > rgb[:, :, 2] * 1.5)
        report["textures"].append({"name": path.stem, "overridden": overridden,
            "format": texture.format, "size": [texture.width, texture.height],
            "rgb_min": rgb.min(axis=(0, 1)).tolist(),
            "rgb_max": rgb.max(axis=(0, 1)).tolist(),
            "bright_green_fraction": float(green.mean())})
    if digest(pak) != before:
        raise ValueError("Input PAK changed during read-only audit")
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "members"}, indent=2))
    print(f"Audited {len(files)} patch members; original PAK unchanged")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pak", "native", "output", "repak"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    audit(*(getattr(args, name).resolve() for name in ("pak", "native", "output", "repak")))
