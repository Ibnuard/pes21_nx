"""Find isolated subpixel skin-marker clusters, never ordinary facial details.

Coordinates are native centimetres. Every triangle must already meet the
microscopic exclusion used by the unchanged surface auditor. A whole cluster
must also fit inside 0.6 mm and have identical nonempty animation weights.
Visibility equivalence is a separate required check in the Blender adapter.
"""
import numpy as np


def marker_triangles(positions, triangles, weights):
    points = np.asarray(positions, dtype=float).reshape(-1, 3)
    faces = np.asarray(triangles, dtype=int).reshape(-1, 3)
    if len(weights) != len(points) or not np.isfinite(points).all():
        raise ValueError('Invalid marker geometry or skin weights')
    # Position aliases connect UV seams for classification only. No exported
    # position, UV or weight is welded or moved by this routine.
    _, aliases = np.unique(np.round(points, 4), axis=0, return_inverse=True)
    parents = list(range(int(aliases.max(initial=-1))+1))
    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index
    for face in aliases[faces]:
        a,b,c = map(root, face)
        parents[b] = a
        parents[c] = a
    groups = {}
    for index, face in enumerate(faces):
        groups.setdefault(root(aliases[face[0]]), []).append(index)
    remove, reports = [], []
    for indices in groups.values():
        selected = faces[indices]
        vertices = np.unique(selected)
        p = points[vertices]
        if np.linalg.norm(p.max(axis=0)-p.min(axis=0)) > .06:
            continue
        first = weights[int(vertices[0])]
        if not first or any(weights[int(i)] != first for i in vertices):
            continue
        q = points[selected]
        edge = q-np.roll(q, 1, axis=1)
        area = np.linalg.norm(np.cross(q[:,1]-q[:,0], q[:,2]-q[:,0]), axis=1)
        if not (np.linalg.norm(edge,axis=2).max(initial=0) < .03 and np.all(area <= 2e-4)):
            continue
        remove.extend(indices)
        reports.append(dict(triangles=len(indices), vertices=len(vertices),
                            extent_cm=float(np.linalg.norm(p.max(axis=0)-p.min(axis=0)))))
    return sorted(remove), reports
