"""Read owned FL seating areas and author a bounded static 2D crowd mesh.

No game payload is bundled. Version 1 audiarea files describe seating quads,
including the gaps between sections; the atlas is supplied separately.
Coordinates remain Fox metres (Y up) until the Blender export stage.
"""
import math
import struct


def read_areas(data):
    if len(data) < 56 or struct.unpack_from('<2I', data) != (1, 1):
        raise ValueError('unsupported audience area header')
    offsets = [x for x in struct.unpack_from('<12I', data, 8) if x]
    if not offsets or offsets != sorted(set(offsets)) or offsets[0] != 56:
        raise ValueError('invalid audience section table')
    result = []
    for i, offset in enumerate(offsets):
        if offset + 36 > len(data):
            raise ValueError('truncated audience section')
        kind, bounds_offset, *header = struct.unpack_from('<2I6fI', data, offset)
        count = header[-1]
        end = offsets[i+1] if i+1 < len(offsets) else len(data)
        if bounds_offset != offset + 8 or not 0 < count <= 2048 or offset+36+count*96 != end:
            raise ValueError('invalid audience section size')
        bounds = header[:6]
        if not all(math.isfinite(x) for x in bounds):
            raise ValueError('nonfinite audience bounds')
        for j in range(count):
            at = offset+36+j*96
            points = list(struct.iter_unpack('<3f', data[at+16:at+64]))
            if any(not all(math.isfinite(v) and bounds[a]-.01 <= v <= bounds[a+3]+.01
                           for a, v in enumerate(p)) for p in points):
                raise ValueError('audience point outside section bounds')
            result.append({'section': kind, 'corners': points})
    return result


def crowd_rows(areas, row_spacing=.82, height=1.55, max_rows=6000):
    if not .5 <= row_spacing <= 2 or not 1 <= height <= 2:
        raise ValueError('invalid crowd density/height')
    vertices, faces, uvs = [], [], []
    for area_index, area in enumerate(areas):
        a, b, c, d = area['corners']
        if a[1]+d[1] > b[1]+c[1]:
            a, b, c, d = b, a, d, c
        depth = (math.hypot(b[0]-a[0], b[2]-a[2]) +
                 math.hypot(c[0]-d[0], c[2]-d[2]))*.5
        rows = max(1, int(depth/row_spacing))
        for row in range(rows):
            # Insets keep the sprite's feet inside the authored seating area.
            t = (row+.5)/rows
            left = tuple(a[k]+(b[k]-a[k])*t for k in range(3))
            right = tuple(d[k]+(c[k]-d[k])*t for k in range(3))
            width = math.hypot(right[0]-left[0], right[2]-left[2])
            if width < .5:
                continue
            if len(faces) >= max_rows:
                raise ValueError('crowd exceeds row budget')
            # The 8:1 native seated atlas repeats as a strip, not one object
            # per person. Stable phase offsets reduce obvious vertical repeats.
            phase = ((area_index*17+row*7)%29)/29
            u0, u1 = phase, phase+width/(8*height)
            start = len(vertices)
            vertices.extend([left, right, (right[0], right[1]+height, right[2]),
                             (left[0], left[1]+height, left[2])])
            faces.append((start, start+1, start+2, start+3))
            uvs.extend([(u0, 0), (u1, 0), (u1, 1), (u0, 1)])
    return vertices, faces, uvs
