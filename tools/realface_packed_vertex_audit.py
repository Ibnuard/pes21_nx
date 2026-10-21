"""Read-only audit of the constrained UE4.22 cooked core vertex streams.

Matches the position/static/skin-weight serialization used by local Android
fixtures. No asset writer is provided. Exact equality covers packed position,
both tangent-basis vectors/sign, every UV channel and all stored skin weights.
Additional color, section/bone-map, morph or cloth semantics are NOT parsed.
Zero equal core records rules out full-record duplicates; positive matches are
only candidates and never authorize merging. Index and bone-list boundaries
are cross-checked to avoid accepting an isolated byte-pattern coincidence.
"""
from collections import Counter
import math
import struct


def _u32(data, offset):
    if offset < 0 or offset + 4 > len(data):
        raise ValueError('Truncated packed stream')
    return struct.unpack_from('<I', data, offset)[0]


def _take(data, offset, size):
    if size < 0 or offset < 0 or offset + size > len(data):
        raise ValueError('Packed stream range exceeds payload')
    return data[offset:offset + size]


def _bulk(data, offset, stride, count):
    if (_u32(data, offset), _u32(data, offset + 4)) != (stride, count):
        raise ValueError('Packed bulk stride/count differs')
    start = offset + 8
    return _take(data, start, stride * count), start + stride * count, start


def _bones(data, offset, end):
    rows = []
    for _ in range(2):
        count = _u32(data, offset); offset += 4
        if not 1 <= count <= 256:
            raise ValueError('Unsupported bone-list count')
        raw = _take(data, offset, count * 2); offset += count * 2
        values = struct.unpack('<' + str(count) + 'H', raw)
        if len(set(values)) != count:
            raise ValueError('Repeated bone-list index')
        rows.append(values)
    if offset != end or not set(rows[0]) <= set(rows[1]):
        raise ValueError('Index/bone-list/position boundary differs')
    return rows


def _indices(data, before, vertices, triangles):
    found = []
    for size, code in ((2, 'H'), (4, 'I')):
        signature = bytes([size]) + struct.pack('<II', size, triangles * 3)
        offset = -1
        while True:
            offset = data.find(signature, offset + 1, before)
            if offset < 0:
                break
            start = offset + len(signature); end = start + size * triangles * 3
            if end > before:
                continue
            try:
                bones = _bones(data, end, before)
                values = struct.unpack('<' + str(triangles * 3) + code,
                                       _take(data, start, end - start))
                if max(values) >= vertices:
                    continue
            except (ValueError, struct.error):
                continue
            found.append(dict(header_offset=offset, data_offset=start,
                              index_size=size, indices=len(values),
                              referenced_vertices=len(set(values)),
                              unused_vertices=vertices-len(set(values)),
                              active_bone_indices=list(bones[0]),
                              required_bone_indices=list(bones[1])))
    if len(found) != 1:
        raise ValueError('Expected one bounded primary index buffer')
    return found[0]


def _candidate(data, offset, vertices, triangles):
    position, cursor, p_start = _bulk(data, offset + 8, 12, vertices)
    if not all(math.isfinite(v[0]) for v in struct.iter_unpack('<f', position)):
        raise ValueError('Non-finite packed position')
    if _take(data, cursor, 2) != b'\x01\x00':
        raise ValueError('Unsupported static stream strip flags')
    cursor += 2
    uv_channels, count, full_uv, high_tangent = struct.unpack(
        '<4I', _take(data, cursor, 16)); cursor += 16
    if count != vertices or not 1 <= uv_channels <= 4 or full_uv > 1 or high_tangent > 1:
        raise ValueError('Unsupported static stream metadata')
    tangent_stride = 16 if high_tangent else 8
    tangent, cursor, t_start = _bulk(data, cursor, tangent_stride, vertices)
    uv_element = 8 if full_uv else 4
    uv, cursor, uv_start = _bulk(data, cursor, uv_element, vertices * uv_channels)
    if not all(math.isfinite(v[0]) for v in struct.iter_unpack('<f' if full_uv else '<e', uv)):
        raise ValueError('Non-finite packed UV')
    if _take(data, cursor, 2) != b'\x01\x00':
        raise ValueError('Unsupported weight stream strip flags')
    cursor += 2
    extra, count = struct.unpack('<2I', _take(data, cursor, 8)); cursor += 8
    if count != vertices or extra > 1:
        raise ValueError('Unsupported packed weight metadata')
    weight_stride = 16 if extra else 8
    weights, cursor, w_start = _bulk(data, cursor, weight_stride, vertices)
    influences = weight_stride // 2
    if any(sum(weights[i*weight_stride+influences:(i+1)*weight_stride]) != 255
           for i in range(vertices)):
        raise ValueError('Packed skin weights do not sum to255')
    uv_stride = uv_element * uv_channels
    records = [position[i*12:(i+1)*12] + tangent[i*tangent_stride:(i+1)*tangent_stride]
               + uv[i*uv_stride:(i+1)*uv_stride] + weights[i*weight_stride:(i+1)*weight_stride]
               for i in range(vertices)]
    groups = Counter(records)
    return dict(vertices=vertices, triangles=triangles, position_header_offset=offset,
                core_stream_end=cursor, uv_channels=uv_channels,
                full_precision_uvs=bool(full_uv), high_precision_tangent_basis=bool(high_tangent),
                extra_bone_influences=bool(extra),
                spans=dict(position=dict(offset=p_start, stride=12),
                           tangent_basis=dict(offset=t_start, stride=tangent_stride),
                           uv=dict(offset=uv_start, stride=uv_stride),
                           bone_indices_weights=dict(offset=w_start, stride=weight_stride)),
                index_buffer=_indices(data, offset, vertices, triangles),
                unique_core_records=len(groups),
                duplicate_core_vertices=vertices-len(groups),
                duplicate_core_group_sizes=sorted(v for v in groups.values() if v > 1),
                position_only_duplicate_vertices=vertices-len({position[i*12:(i+1)*12] for i in range(vertices)}),
                no_exact_full_record_merge_possible=len(groups)==vertices,
                additional_vertex_semantics_verified=False,
                merge_authorized=False, data_changed=False)


def audit_core_streams(data, vertices, triangles):
    if (isinstance(vertices, bool) or isinstance(triangles, bool) or
            not isinstance(vertices, int) or not isinstance(triangles, int) or
            not 1 <= vertices <= 65535 or not 1 <= triangles <= 1000000):
        raise ValueError('Unsupported expected vertex/triangle count')
    signature = struct.pack('<4I', 12, vertices, 12, vertices)
    offset = -1; found = []
    while True:
        offset = data.find(signature, offset + 1)
        if offset < 0:
            break
        try:
            found.append(_candidate(data, offset, vertices, triangles))
        except (ValueError, struct.error):
            continue
    if len(found) != 1:
        raise ValueError('Expected one unambiguous complete core-stream chain')
    return found[0]
