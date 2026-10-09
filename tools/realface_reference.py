"""Read a local UE Viewer glTF rest mesh as native PES21 centimetres.

This deliberately accepts only the single, untransformed mesh export used by
the reference workflow. It is not a general glTF importer. No game data ships
with this reader. The basis was checked against the original position buffer.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import struct


def load_reference(path: Path) -> dict:
    path = Path(path).resolve()
    doc = json.loads(path.read_text(encoding="utf-8"))
    if len(doc.get("meshes", [])) != 1 or len(doc.get("skins", [])) != 1:
        raise ValueError("Expected one skinned reference mesh")
    mesh_nodes = [n for n in doc["nodes"] if "mesh" in n]
    if len(mesh_nodes) != 1 or mesh_nodes[0]["mesh"] != 0 or mesh_nodes[0].get("skin") != 0:
        raise ValueError("Ambiguous reference mesh node")
    if any(k in mesh_nodes[0] for k in ("matrix", "translation", "rotation", "scale")):
        raise ValueError("Reference mesh must be exported in its rest frame")
    buffers = []
    for spec in doc["buffers"]:
        target = (path.parent / spec["uri"]).resolve()
        if not target.is_relative_to(path.parent):
            raise ValueError("Reference buffer must be beside the glTF")
        raw = target.read_bytes()
        if len(raw) != spec["byteLength"]:
            raise ValueError("Reference buffer size mismatch")
        buffers.append(raw)

    def accessor(index):
        a = doc["accessors"][index]
        if "sparse" in a:
            raise ValueError("Sparse reference accessors are unsupported")
        view = doc["bufferViews"][a["bufferView"]]
        raw = buffers[view["buffer"]]
        formats = {5121: ("B", 255), 5123: ("H", 65535), 5125: ("I", 4294967295), 5126: ("f", 1)}
        fmt, denominator = formats[a["componentType"]]
        count = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[a["type"]]
        fmt = "<" + fmt * count
        size = struct.calcsize(fmt)
        stride = view.get("byteStride", size)
        offset = a.get("byteOffset", 0)
        start = view.get("byteOffset", 0) + offset
        if (a["count"] < 1 or stride < size or offset < 0 or
                offset + (a["count"] - 1) * stride + size > view["byteLength"] or
                view.get("byteOffset", 0) + view["byteLength"] > len(raw)):
            raise ValueError("Reference accessor exceeds its buffer view")
        values = [struct.unpack_from(fmt, raw, start + i * stride) for i in range(a["count"])]
        if a.get("normalized"):
            values = [tuple(x / denominator for x in row) for row in values]
        if not all(math.isfinite(v) for row in values for v in row):
            raise ValueError("Non-finite reference data")
        return values

    names = [doc["nodes"][i]["name"] for i in doc["skins"][0]["joints"]]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate reference joints")
    vertices, normals, uv, weights, faces = [], [], [], [], []
    for prim in doc["meshes"][0]["primitives"]:
        if prim.get("mode", 4) != 4:
            raise ValueError("Expected reference triangles")
        attrs = prim["attributes"]
        xyz = accessor(attrs["POSITION"])
        ns = accessor(attrs["NORMAL"])
        st = accessor(attrs["TEXCOORD_0"])
        js = accessor(attrs["JOINTS_0"])
        ws = accessor(attrs["WEIGHTS_0"])
        if not len(xyz) == len(ns) == len(st) == len(js) == len(ws):
            raise ValueError("Reference attribute counts differ")
        base = len(vertices)
        # UE Viewer's glTF is metres in X/Z/Y order. This reflection also
        # requires reversed triangle winding, but no reflection of the UVs.
        vertices.extend((x * 100, z * 100, y * 100) for x, y, z in xyz)
        normals.extend((x, z, y) for x, y, z in ns)
        uv.extend(st)
        for joints, values in zip(js, ws):
            if any(w < 0 for w in values) or abs(sum(values) - 1) > .01:
                raise ValueError("Invalid reference skin weights")
            combined = {}
            for joint, value in zip(joints, values):
                if value:
                    name = names[joint]
                    combined[name] = combined.get(name, 0) + value
            total = sum(combined.values())
            weights.append({n: w / total for n, w in combined.items()})
        indices = [v[0] for v in accessor(prim["indices"])]
        if len(indices) % 3 or any(i < 0 or i >= len(xyz) for i in indices):
            raise ValueError("Invalid reference triangle indices")
        faces.extend(tuple(base + i for i in reversed(indices[j:j+3])) for j in range(0, len(indices), 3))
    return dict(vertices=vertices, normals=normals, uv=uv, weights=weights,
                faces=faces, bone_names=names)


def barycentric(point, triangle):
    """Barycentric coordinates at an already projected triangle point."""
    a, b, c = triangle
    sub = lambda x, y: [u - v for u, v in zip(x, y)]
    dot = lambda x, y: sum(u * v for u, v in zip(x, y))
    v0, v1, v2 = sub(b, a), sub(c, a), sub(point, a)
    d00, d01, d11 = dot(v0, v0), dot(v0, v1), dot(v1, v1)
    denominator = d00 * d11 - d01 * d01
    if abs(denominator) < 1e-12:
        raise ValueError("Degenerate reference triangle")
    v = (d11 * dot(v2, v0) - d01 * dot(v2, v1)) / denominator
    w = (d00 * dot(v2, v1) - d01 * dot(v2, v0)) / denominator
    values = [max(0., min(1., q)) for q in (1 - v - w, v, w)]
    total = sum(values)
    return [x / total for x in values]


def mix_weights(original, target, amount):
    if not math.isfinite(amount) or not 0 <= amount <= 1:
        raise ValueError("Weight blend must be 0..1")
    for weights in (original, target):
        if not weights or any(not math.isfinite(w) or w < 0 for w in weights.values()) or abs(sum(weights.values())-1) > .01:
            raise ValueError("Input skin weights must be finite, nonnegative and normalized")
    merged = {n: original.get(n, 0) * (1-amount) + target.get(n, 0) * amount
              for n in original.keys() | target.keys()}
    kept = sorted(((n, w) for n, w in merged.items() if w > 1e-8),
                  key=lambda x: (-x[1], x[0]))[:4]
    total = sum(w for n, w in kept)
    if not total or not math.isfinite(total):
        raise ValueError("No valid skin influence")
    return {n: w/total for n, w in kept}


def socket_target_x(accepted_pupil_x, accepted_opening, target_opening):
    """Transfer relative pupil centring between asymmetric eyelid openings.

    Openings contain min/max/mean X sampled in a thin band at pupil height.
    Front-view X has opposite signs for the two eyes; preserve the accepted
    eye's outward bias relative to its opening, not its world-space gaze.
    """
    if not all(math.isfinite(v) for v in (accepted_pupil_x, *accepted_opening, *target_opening)):
        raise ValueError("Non-finite eye landmarks")
    amin, amax, acenter = accepted_opening
    tmin, tmax, tcenter = target_opening
    if not amin < accepted_pupil_x < amax or not amin < acenter < amax or not tmin < tcenter < tmax:
        raise ValueError("Pupil/opening landmarks are invalid")
    if acenter * tcenter >= 0:
        raise ValueError("Expected opposite eye openings across native X=0")
    fraction = (accepted_pupil_x - acenter) / (amax - amin)
    target = tcenter - fraction * (tmax - tmin)
    if not tmin < target < tmax:
        raise ValueError("Target pupil lies outside its opening")
    return target


def socket_target_z(accepted_pupil_z, accepted_opening, target_opening):
    """Transfer pupil height relative to each eye's own eyelid opening."""
    if not all(math.isfinite(v) for v in (accepted_pupil_z, *accepted_opening, *target_opening)):
        raise ValueError("Non-finite eye landmarks")
    amin, amax, acenter = accepted_opening
    tmin, tmax, tcenter = target_opening
    if not amin < accepted_pupil_z < amax or not amin < acenter < amax or not tmin < tcenter < tmax:
        raise ValueError("Pupil/opening landmarks are invalid")
    target = tcenter + (accepted_pupil_z-acenter) * (tmax-tmin)/(amax-amin)
    if not tmin < target < tmax:
        raise ValueError("Target pupil lies outside its opening")
    return target
