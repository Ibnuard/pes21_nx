"""Exact offline floor ownership using Shapely 2.1 (no runtime dependency).

Union the owned native floor BEFORE subtraction. Subtracting hundreds of
individual floor triangles produces unnecessary internal seams and fragments.
The union retains uncovered corners and holes, unlike a rectangle/convex hull.
"""
import json
from pathlib import Path
import sys


def height_band(points, minimum, maximum):
    """XY footprint of only the part of a sloping triangle near floor height."""
    polygon = [tuple(p) for p in points]
    for height, sign in ((minimum, 1), (maximum, -1)):
        clipped = []
        for a, b in zip(polygon, polygon[1:]+polygon[:1]):
            inside_a = sign*(a[2]-height) >= 0
            inside_b = sign*(b[2]-height) >= 0
            if inside_a:
                clipped.append(a)
            if inside_a != inside_b:
                t = (height-a[2])/(b[2]-a[2])
                clipped.append(tuple(a[i]+t*(b[i]-a[i]) for i in range(3)))
        polygon = clipped
    return [p[:2] for p in polygon]


def repair_polygons(native, faces):
    from shapely import Polygon, union_all, constrained_delaunay_triangles
    floor = union_all([Polygon(t) for t in native], grid_size=0.00001)
    floor = floor.simplify(0.00002, preserve_topology=True)
    if not floor.is_valid or floor.area < 7000 or floor.area > 12000:
        raise ValueError('Invalid native stadium floor footprint')
    output = {}
    for index, entry in faces.items():
        points = entry['points'] if isinstance(entry, dict) else entry
        subject = Polygon(points)
        ownership = floor
        if isinstance(entry, dict):
            if len(entry['clip']) < 3:
                continue
            ownership = floor.intersection(Polygon(entry['clip']))
        if subject.area < 1e-8 or subject.intersection(ownership).area < 1e-8:
            continue
        outside = subject.difference(ownership, grid_size=0.00001)
        pieces = []
        for triangle in constrained_delaunay_triangles(outside).geoms:
            if triangle.area > 1e-8:
                pieces.append(list(triangle.exterior.coords)[:3])
        if abs(sum(Polygon(t).area for t in pieces)-outside.area) > 1e-5:
            raise ValueError('Triangulation changed the retained floor area')
        output[index] = pieces
    return output


if __name__ == '__main__':
    request = json.loads(Path(sys.argv[1]).read_text())
    Path(sys.argv[2]).write_text(json.dumps(repair_polygons(request['native'], request['faces'])))
