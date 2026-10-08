"""Build an isolated A/B control that undoes only two old day shadow colours.

This is a diagnostic package, not a confirmed Night/High lighting fix. Retain
the user's full custom pitch; never replace it with the obsolete 11-file PAK.
All proprietary inputs and generated packages must remain local and ignored.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

from tune_day_pitch_material import patch_color

MATERIALS = Path("PesMobile/Content/Assets/bg_lighting_AM1/Materials")
OLD_SHADOW = (0.03125, 0.023696, 0.0, 1.0)


def green_shadow():
    weights = (0.2126, 0.7152, 0.0722)
    ratio = (0.60, 1.0, 0.29)
    # Use the exact float32 source used by the original colour-edit recipe.
    old = struct.unpack("<4f", struct.pack("<4f", *OLD_SHADOW))
    level = sum(a * b for a, b in zip(old, weights)) / sum(a * b for a, b in zip(ratio, weights))
    return tuple(v * level for v in ratio) + (1.0,)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(pak, native, output, repak):
    before = sha(pak)
    output.mkdir(parents=True, exist_ok=False)
    original, stage = output / "original", output / "stage"
    subprocess.run([str(repak), "unpack", str(pak), "-o", str(original)], check=True)
    inputs = {p.relative_to(original): sha(p) for p in original.rglob("*") if p.is_file()}
    if len(inputs) != 31:
        raise ValueError("Expected the complete 31-member accepted custom pitch PAK")
    shutil.copytree(original, stage)
    edits = []
    for name in ("MI_Pitch_L", "MI_Pitch_R"):
        relative = MATERIALS / (name + ".uexp")
        path = stage / relative
        restored, offset = patch_color(path.read_bytes(), green_shadow(), OLD_SHADOW)
        if restored != (native / relative).read_bytes():
            raise ValueError(f"{name}: inverse colour edit does not match the owned original")
        if (stage / relative.with_suffix(".uasset")).read_bytes() != (native / relative.with_suffix(".uasset")).read_bytes():
            raise ValueError(f"{name}: unsupported material header")
        path.write_bytes(restored)
        edits.append({"member": relative.as_posix(), "offset": offset,
                      "green_rgba": green_shadow(), "restored_rgba": OLD_SHADOW})
    changed = {p for p, value in inputs.items() if sha(stage / p) != value}
    if changed != {MATERIALS / (name + ".uexp") for name in ("MI_Pitch_L", "MI_Pitch_R")}:
        raise ValueError("Unexpected edits outside the two day material colours")
    target = output / "PesMobile-Android_ETC1_P.pak"
    subprocess.run([str(repak), "pack", "--version", "V8A", "--compression", "Zlib", str(stage), str(target)], check=True)
    verify = output / "verify"
    subprocess.run([str(repak), "unpack", str(target), "-o", str(verify)], check=True)
    roundtrip = {p.relative_to(verify): sha(p) for p in verify.rglob("*") if p.is_file()}
    if roundtrip != {p: sha(stage / p) for p in inputs} or sha(pak) != before:
        raise ValueError("PAK roundtrip failed or original input changed")
    report = {"purpose": "Diagnostic A/B; NOT a confirmed Night/High fix",
              "input_sha256": before, "output_sha256": sha(target),
              "members": len(inputs), "unchanged_members": len(inputs) - len(edits),
              "edits": edits, "input_unchanged": True, "roundtrip_verified": True}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pak", "native", "output", "repak"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    build(*(getattr(args, name).resolve() for name in ("pak", "native", "output", "repak")))
