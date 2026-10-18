"""Read-only geometry audit of locally owned mobile realface PAKs.

Requires local repak and UE Viewer executables. Only numerical mesh metadata
is retained: no vertices, textures, game code or extracted payloads. PAKs are
temporarily hard-linked (not copied) into isolated search roots so native and
patched packages cannot accidentally override one another. Keep output local.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import struct
import subprocess
import tempfile


PART = re.compile(r"(?:^|/)RealFace/(\d+)_(face|hair)\.uasset$")
METRICS_SCHEMA = 2


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def parse_dump(text):
    """Parse UE Viewer's cooked LOD summary, checking every index range."""
    result = {}
    for block in re.split(r"(?=ClassName:)", text):
        match = re.match(r"ClassName: SkeletalMesh4 ObjectName: (\d+_(?:face|hair))\s", block)
        if not match:
            continue
        name = match[1]
        count = re.search(r"^    LodCount = (\d+)$", block, re.M)
        bones = re.search(r"^    BoneCount = (\d+)$", block, re.M)
        if not count or not bones:
            raise ValueError(f"Incomplete cooked mesh: {name}")
        lods = []
        for lod in re.split(r"(?=^        Lods\[\d+\] =)", block, flags=re.M)[1:]:
            index = int(re.match(r"        Lods\[(\d+)\]", lod)[1])
            vertices = re.search(r"^            NumVerts = (\d+)$", lod, re.M)
            indices = re.search(r"^            IndexCount = (\d+)$", lod, re.M)
            sections = re.search(r"^            Sections\[(\d+)\] =", lod, re.M)
            faces = re.findall(r"Sections\[(\d+)\] = \{ Material=.*?, FirstIndex=(\d+), NumFaces=(\d+) \}", lod)
            if not vertices or not indices or not sections or index != len(lods):
                raise ValueError(f"Incomplete/nonsequential LOD: {name}/{index}")
            cursor = 0
            for expected, (section, first, number) in enumerate(faces):
                if int(section) != expected or int(first) != cursor:
                    raise ValueError(f"Noncontiguous section indices: {name}/{index}")
                cursor += 3 * int(number)
            # UE Viewer build 1590's text dump reports its 16-bit index array
            # length. A 32-bit mesh can report zero here; independently export
            # and check glTF accessors below before accepting that exception.
            needs_gltf = int(indices[1]) == 0 and cursor > 0 and int(vertices[1]) > 65535
            if len(faces) != int(sections[1]) or (cursor != int(indices[1]) and not needs_gltf):
                raise ValueError(f"Section/index count mismatch: {name}/{index}")
            lods.append(dict(lod=index, triangles=cursor // 3, vertices=int(vertices[1]),
                             sections=len(faces), section_triangles=[int(f[2]) for f in faces],
                             index_validation="gltf_required" if needs_gltf else "dump_count"))
        if len(lods) != int(count[1]) or not lods:
            raise ValueError(f"LOD count mismatch: {name}")
        if name in result:
            raise ValueError(f"Duplicate mesh: {name}")
        result[name] = dict(lods=lods, bones=int(bones[1]))
    return result


def validate_gltf_indices(document, lod):
    primitives = [p for mesh in document["meshes"] for p in mesh["primitives"]]
    if len(primitives) != lod["sections"]:
        raise ValueError("glTF section count differs from cooked dump")
    for primitive, triangles in zip(primitives, lod["section_triangles"]):
        accessor = document["accessors"][primitive["indices"]]
        if (primitive.get("mode", 4) != 4 or accessor["type"] != "SCALAR"
                or accessor["componentType"] not in (5123, 5125)
                or accessor["count"] != triangles * 3):
            raise ValueError("glTF indices differ from cooked sections")
        view = document["bufferViews"][accessor["bufferView"]]
        width = 2 if accessor["componentType"] == 5123 else 4
        if accessor.get("byteOffset", 0) + accessor["count"] * width > view["byteLength"]:
            raise ValueError("glTF index buffer is truncated")
    lod["index_validation"] = "gltf_accessor_count"


def audit_pak(pak, repak, umodel, work, label, chunk_size=64):
    listing = subprocess.run([str(repak), "list", str(pak)], check=True,
                             capture_output=True, text=True, encoding="utf-8").stdout
    names = sorted({f"{m[1]}_{m[2]}" for line in listing.splitlines()
                    if (m := PART.search(line.replace("\\", "/")))})
    if not names:
        raise ValueError(f"No RealFace face/hair packages in {pak}")
    meshes = {}
    # TemporaryDirectory removes only its own link. Original PAK stays intact.
    with tempfile.TemporaryDirectory(prefix=label + "-pak-", dir=work) as temporary:
        os.link(pak, Path(temporary) / pak.name)
        for start in range(0, len(names), chunk_size):
            batch = names[start:start + chunk_size]
            args = [str(umodel), "-dump", "-all", "-notex", "-noanim", "-nostat",
                    "-game=ue4.22", "-path=" + temporary]
            args += ["-pkg=" + name for name in batch[1:]] + [batch[0]]
            run = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=180)
            if run.returncode or "ERROR:" in run.stdout or "ERROR:" in run.stderr:
                raise RuntimeError(f"UE Viewer failed: {label}/{batch[0]}: " + (run.stdout + run.stderr)[-1500:])
            parsed = parse_dump(run.stdout)
            if set(parsed) != set(batch):
                raise ValueError(f"Missing/unexpected meshes in {label}/{batch[0]}")
            for name, mesh in parsed.items():
                if any(lod["index_validation"] == "gltf_required" for lod in mesh["lods"]):
                    with tempfile.TemporaryDirectory(prefix="indices-", dir=work) as exported:
                        subprocess.run([str(umodel), "-export", "-gltf", "-lods", "-notex", "-game=ue4.22",
                                        "-path=" + temporary, "-out=" + exported, name], check=True,
                                       capture_output=True, timeout=180)
                        for lod in mesh["lods"]:
                            if lod["index_validation"] != "gltf_required":
                                continue
                            suffix = "" if lod["lod"] == 0 else "_Lod" + str(lod["lod"])
                            files = list(Path(exported).rglob(name + suffix + ".gltf"))
                            if len(files) != 1:
                                raise ValueError(f"Missing glTF index proof: {name}/{lod['lod']}")
                            validate_gltf_indices(json.loads(files[0].read_text(encoding="utf-8")), lod)
            meshes.update(parsed)
            print(f"{label}: {len(meshes)}/{len(names)} meshes", flush=True)
    return dict(pak_sha256=sha256(pak), pak_bytes=pak.stat().st_size,
                mesh_count=len(meshes), meshes=meshes)


def percentile(values, fraction):
    values = sorted(values)
    offset = (len(values) - 1) * fraction
    lo, hi = math.floor(offset), math.ceil(offset)
    return values[lo] + (values[hi] - values[lo]) * (offset - lo)


def distribution(values):
    if not values:
        raise ValueError("Empty distribution")
    return dict(count=len(values), min=min(values), median=statistics.median(values),
                mean=round(statistics.mean(values), 2), p90=round(percentile(values, .9), 2),
                p95=round(percentile(values, .95), 2), max=max(values))


def player_rows(meshes, require_pairs=True):
    ids = sorted({int(name.split("_")[0]) for name in meshes})
    rows = []
    for native in ids:
        if not require_pairs and any(f"{native}_{part}" not in meshes for part in ("face", "hair")):
            continue
        row = dict(native_player_id=native)
        for part in ("face", "hair"):
            mesh = meshes.get(f"{native}_{part}")
            if mesh is None:
                raise ValueError(f"Missing mesh pair: {native}/{part}")
            row[part + "_lods"] = len(mesh["lods"])
            for field in ("triangles", "vertices", "sections"):
                row[part + "_" + field] = mesh["lods"][0][field]
        for field in ("triangles", "vertices", "sections"):
            row["total_" + field] = row["face_" + field] + row["hair_" + field]
        rows.append(row)
    return rows


def summarize(rows):
    return dict(players=len(rows),
                metrics={part + "_" + field: distribution([r[part + "_" + field] for r in rows])
                         for part in ("face", "hair", "total") for field in ("triangles", "vertices", "sections")},
                face_lod_counts=dict(Counter(r["face_lods"] for r in rows)),
                hair_lod_counts=dict(Counter(r["hair_lods"] for r in rows)))


def compare(native, patch, verification):
    if patch["pak_sha256"] != verification["pak_sha256"]:
        raise ValueError("PAK does not match the release verification manifest")
    native_rows = player_rows(native["meshes"], require_pairs=False)
    patch_rows = player_rows(patch["meshes"])
    covered = [r for r in verification["players"] if r["status"] in ("preserved_verified", "candidate_pending_device")]
    owners = {int(r["native_player_id"]): r for r in covered}
    if len(owners) != len(covered) or len({r["base_id"] for r in covered}) != len(covered):
        raise ValueError("Duplicate covered identity")
    if {r["native_player_id"] for r in patch_rows} != set(owners):
        raise ValueError("Packaged mesh IDs do not match verified covered identities")
    baseline = {r["native_player_id"]: r for r in native_rows}
    for row in patch_rows:
        owner = owners[row["native_player_id"]]
        row.update({k: owner[k] for k in ("base_id", "name", "team_ids")})
        old = baseline.get(row["native_player_id"])
        row["native_slot_triangles"] = old["total_triangles"] if old else None
        # Storage-slot comparison only, never evidence of old/new player identity.
        row["native_slot_ratio"] = round(row["total_triangles"] / old["total_triangles"], 3) if old and old["total_triangles"] else None
    patch_rows.sort(key=lambda r: r["total_triangles"], reverse=True)
    teams = []
    for team in verification["teams"]:
        members = [r for r in patch_rows if team["team_id"] in r["team_ids"]]
        if members:
            teams.append(dict(team, covered=len(members),
                              median_head_triangles=statistics.median(r["total_triangles"] for r in members),
                              largest_head_triangles=max(r["total_triangles"] for r in members),
                              eleven_heaviest_heads=sum(r["total_triangles"] for r in members[:11])))
    native_summary = summarize(native_rows)
    native_summary["combined_scope"] = "Complete face/hair pairs only; absent native hair is not assumed zero cost"
    native_summary["all_parts"] = {part: dict(
        triangles=distribution([m["lods"][0]["triangles"] for name, m in native["meshes"].items() if name.endswith("_" + part)]),
        vertices=distribution([m["lods"][0]["vertices"] for name, m in native["meshes"].items() if name.endswith("_" + part)]),
        lod_counts=dict(Counter(len(m["lods"]) for name, m in native["meshes"].items() if name.endswith("_" + part))))
        for part in ("face", "hair")}
    return dict(scope="LOD0 face (including eyes) plus hair/scalp; body, boots and render passes excluded",
                hardware_profiled=False, sources={"native": {k: v for k, v in native.items() if k != "meshes"},
                                                  "patch": {k: v for k, v in patch.items() if k != "meshes"}},
                native=native_summary, patch=summarize(patch_rows),
                triangles_above_native_max=sum(r["total_triangles"] > max(n["total_triangles"] for n in native_rows) for r in patch_rows),
                players=patch_rows, teams=teams)


def audit_runtime_lod(path):
    """Inspect actual owned actor dispatch, retaining symbols/hashes only."""
    from elftools.elf.elffile import ELFFile
    classes = ("_ZTV16APlayerActorHigh", "_ZTV15APlayerActorLow", "_ZTV18APlayerActorLowest")
    target = "_ZN12APlayerActor12LoadRealFaceEPKc"
    force = "_ZN21USkinnedMeshComponent12SetForcedLODEi"
    with Path(path).open("rb") as stream:
        elf = ELFFile(stream)
        if elf["e_machine"] != "EM_AARCH64" or not elf.little_endian:
            raise ValueError("Expected the compatible little-endian AArch64 library")
        table = elf.get_section_by_name(".dynsym")
        strings = elf.get_section(table["sh_link"]).data()
        indexed, selected = [], {}
        for offset, info, other, section, address, size in struct.iter_unpack("<IBBHQQ", table.data()):
            name = strings[offset:strings.find(b"\0", offset)].decode("utf-8")
            indexed.append((name, address, size))
            if name in classes + (target, force) and address:
                selected[name] = (address, size)
        if len(selected) != 5:
            raise ValueError("Required native actor/LOD symbols unavailable")
        routes = {}
        for section in elf.iter_sections():
            if section.name.startswith(".rela"):
                for offset, info, addend in struct.iter_unpack("<QQq", section.data()):
                    if (info & 0xffffffff) != 257 or indexed[info >> 32][0] != target or addend:
                        continue
                    for name in classes:
                        start, size = selected[name]
                        if start <= offset < start + size:
                            if name in routes:
                                raise ValueError("Ambiguous face-loader vtable slot")
                            routes[name] = dict(loader=target, virtual_byte_offset=offset - start - 16)
        if set(routes) != set(classes) or len({v["virtual_byte_offset"] for v in routes.values()}) != 1:
            raise ValueError("Actor face loader dispatch differs from audited contract")
        address, size = selected[force]
        stream.seek(next(elf.address_offsets(address)))
        digest = hashlib.sha256(stream.read(size)).hexdigest()
    return dict(library_sha256=sha256(path), actor_face_loaders=routes,
                force_lod_symbol=force, force_lod_address=address, force_lod_bytes=size,
                force_lod_sha256=digest, runtime_modified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("native-pak", "patch-pak", "verification", "repak", "umodel", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--mobile-library", type=Path, help="Optional owned ELF dispatch audit (pyelftools required)")
    args = parser.parse_args()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, pak in (("native", args.native_pak), ("patch", args.patch_pak)):
        pak = pak.resolve()
        saved = work / (label + "-mesh-metrics.json")
        digest = sha256(pak)
        tool_hashes = {"umodel": sha256(args.umodel), "repak": sha256(args.repak)}
        cached = json.loads(saved.read_text(encoding="utf-8")) if saved.exists() else None
        if (cached and cached.get("metrics_schema") == METRICS_SCHEMA
                and cached["pak_sha256"] == digest and cached.get("tool_sha256") == tool_hashes):
            results[label] = cached
        else:
            result = audit_pak(pak, args.repak.resolve(), args.umodel.resolve(), work, label)
            if result["pak_sha256"] != digest:
                raise ValueError("PAK changed during audit")
            result["tool_sha256"] = tool_hashes
            result["metrics_schema"] = METRICS_SCHEMA
            saved.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            results[label] = result
    verification = json.loads(args.verification.read_text(encoding="utf-8"))
    report = compare(results["native"], results["patch"], verification)
    report["verification_sha256"] = sha256(args.verification)
    report["auditor_sha256"] = sha256(__file__)
    if args.mobile_library:
        report["runtime_lod"] = audit_runtime_lod(args.mobile_library)
    (work / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (work / "players.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(report["players"][0]))
        writer.writeheader()
        writer.writerows(dict(r, team_ids=";".join(map(str, r["team_ids"]))) for r in report["players"])
    print(json.dumps({k: report[k] for k in ("native", "patch", "triangles_above_native_max")}, indent=2))


if __name__ == "__main__":
    main()
