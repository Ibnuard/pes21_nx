"""Offline front-face UV/depth checks against the unreduced source surface.

Surface distance alone misses a sparse triangle stretching the dark mouth
texture into the cheek. This audit samples the visible source and candidate
at identical cameras, measuring the UV sampled at each covered pixel.
"""
import numpy as np


def unique_triangle_offsets(indices):
    """Keep the first nondegenerate face, including its original winding.

    Callers must gather attributes from these same corners: discarded reverse
    duplicates cannot participate in normal averaging for the retained face.
    """
    if len(indices) % 3:
        raise ValueError('Incomplete triangle index buffer')
    seen = set()
    for start in range(0, len(indices), 3):
        face = indices[start:start+3]
        key = tuple(sorted(face))
        if len(set(face)) == 3 and key not in seen:
            seen.add(key)
            yield start


def collapsed_skin_marker(points, weights):
    """Ignore sub-micrometre bind-roundoff only with identical skinning.

    A visible sliver or coincident corners with different animation weights
    are not covered by this policy. Coordinates are native centimetres.
    """
    if not weights[0] or any(value != weights[0] for value in weights[1:]):
        return False
    p=np.asarray(points,dtype=float)
    return bool(np.isfinite(p).all() and
                max(float(np.sum((p[a]-p[b])**2)) for a,b in ((0,1),(1,2),(2,0))) <= 1e-10)
from realface_mobile_geometry import raster


def feature_locks(positions, triangles, uv, locks, texture):
    """Preserve the neck seam and visible mouth crease, not every neck vertex."""
    positions = np.asarray(positions).reshape(-1, 3)
    triangles = np.asarray(triangles).reshape(-1, 3)
    uv = np.asarray(uv).reshape(-1, 2)
    result = np.asarray(locks, dtype=np.uint8).copy()
    _, alias = np.unique(np.round(positions, 5), axis=0, return_inverse=True)
    faces = alias[triangles]
    edges = np.sort(np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]])), axis=1)
    edges, counts = np.unique(edges, axis=0, return_counts=True)
    boundary = np.unique(edges[counts == 1])
    neck = positions[:, 2] < 155
    before = int(result[neck].sum())
    result[neck] = np.isin(alias[neck], boundary)
    # Only visible source vertices may define the mouth crease. Hidden inner
    # mouth walls and black unused texels must not consume the face budget.
    frame = raster(positions, triangles, uv[triangles], np.ones((1, 1)),
                   np.array([[1, 0, 0], [0, 0, 1], [0, 1, 0]]), ((-9.5, 155), (9.5, 182)), size=192)
    visible = np.zeros(len(positions), bool)
    visible[np.unique(triangles[np.unique(frame['front'][frame['front'] >= 0])])] = True
    nose = positions[(np.abs(positions[:, 0])<1.5) & (positions[:, 2]>160) & (positions[:, 2]<176)]
    if not len(nose): raise ValueError('No native-space nose anchor')
    nose_z = nose[np.argmax(nose[:, 1]), 2]
    mouth = (visible & (np.abs(positions[:, 0])<4.8) &
             (positions[:, 2]>nose_z-6.5) & (positions[:, 2]<nose_z-1.5))
    if not mouth.any(): raise ValueError('No visible mouth surface for feature protection')
    x = np.clip((uv[:, 0]*texture.shape[1]).astype(int), 0, texture.shape[1]-1)
    y = np.clip((uv[:, 1]*texture.shape[0]).astype(int), 0, texture.shape[0]-1)
    luma = texture[y, x, :3] @ np.array([.2126, .7152, .0722])
    candidates = np.flatnonzero(mouth & (luma < np.median(luma[mouth])*.65))
    # Dense PC models can have thousands of tiny crease samples. Bound the
    # added anchors and spread them spatially rather than locking every one.
    if len(candidates)>128:
        selected = [int(candidates[np.argmin(luma[candidates])])]
        distance = np.full(len(candidates), np.inf)
        for _ in range(127):
            distance = np.minimum(distance, np.linalg.norm(positions[candidates]-positions[selected[-1]], axis=1))
            selected.append(int(candidates[np.argmax(distance)]))
        candidates = np.array(selected)
    result[candidates] = 1
    return result.tolist(), dict(neck_vertices_locked_before=before,
                                 neck_boundary_vertices_locked=int(result[neck].sum()),
                                 mouth_crease_anchors=len(candidates), maximum_mouth_anchors=128)


def visible_attributes(positions, triangles, uv, basis, bounds, size=96):
    frame = raster(positions, triangles, uv[triangles], np.ones((1, 1)), basis, bounds, size=size)
    rows, columns = np.where(frame['mask'])
    faces = triangles[frame['front'][rows, columns]]
    projected = positions @ basis.T
    lo, hi = np.asarray(bounds)
    xy = lo + (np.stack((columns, rows), axis=1)+.5)/size*(hi-lo)
    a, b, c = (projected[faces[:, i], :2] for i in range(3))
    denom = (b[:, 1]-c[:, 1])*(a[:, 0]-c[:, 0])+(c[:, 0]-b[:, 0])*(a[:, 1]-c[:, 1])
    w0 = ((b[:, 1]-c[:, 1])*(xy[:, 0]-c[:, 0])+(c[:, 0]-b[:, 0])*(xy[:, 1]-c[:, 1]))/denom
    w1 = ((c[:, 1]-a[:, 1])*(xy[:, 0]-c[:, 0])+(a[:, 0]-c[:, 0])*(xy[:, 1]-c[:, 1]))/denom
    weights = np.stack((w0, w1, 1-w0-w1), axis=1)
    result = dict(frame)
    for name, values in (('uv', uv), ('position', positions)):
        field = np.full((size, size, values.shape[1]), np.nan)
        field[rows, columns] = (weights[:, :, None]*values[faces]).sum(axis=1)
        result[name] = field
    return result


def audit(request, reduced, size=96):
    p = np.array(request['positions']).reshape(-1, 3)
    uv = np.array(request['uv']).reshape(-1, 2)
    before = np.array(request['indices']).reshape(-1, 3)
    after = np.array(reduced).reshape(-1, 3)
    nose = p[(np.abs(p[:, 0])<1.5) & (p[:, 2]>160) & (p[:, 2]<176)]
    if not len(nose):
        raise ValueError('Cannot locate the frontal face in native rest coordinates')
    nose_z = nose[np.argmax(nose[:, 1]), 2]
    reports = []
    for yaw in (0, -25, 25):
        angle = np.radians(yaw)
        basis = np.array([[np.cos(angle), -np.sin(angle), 0], [0, 0, 1], [np.sin(angle), np.cos(angle), 0]])
        bounds = ((-9.5, 155), (9.5, 182))
        left = visible_attributes(p, before, uv, basis, bounds, size)
        right = visible_attributes(p, after, uv, basis, bounds, size)
        mask = left['mask'] & right['mask']
        # Pixel error at the actual 92x124 skin tile, not the full source PNG.
        delta = np.linalg.norm((left['uv']-right['uv'])*[92, 124], axis=2)
        mouth = ((np.abs(left['position'][:, :, 0])<4.8) &
                 (left['position'][:, :, 2]>nose_z-6.5) &
                 (left['position'][:, :, 2]<nose_z-1.5))
        regions = {}
        for name, region in (('face', np.ones(mask.shape, bool)), ('mouth', mouth)):
            valid = mask & region
            if not valid.any(): raise ValueError('No comparable surface pixels')
            regions[name] = dict(pixels=int(valid.sum()), uv_p95_texels=float(np.percentile(delta[valid], 95)),
                                 uv_max_texels=float(np.max(delta[valid])),
                                 depth_p95_cm=float(np.percentile(np.abs(left['depth'][valid]-right['depth'][valid]), 95)))
        reports.append(dict(yaw=yaw, regions=regions))
    return dict(views=reports, sample_resolution=size,
                mouth_uv_p95_max=max(r['regions']['mouth']['uv_p95_texels'] for r in reports),
                face_uv_p95_max=max(r['regions']['face']['uv_p95_texels'] for r in reports))


def needs_refinement(proof):
    """Screen the worst projections; this is not a substitute for visual QA."""
    return proof['mouth_uv_p95_max'] > 1.3 or proof['face_uv_p95_max'] > 1.35


def audit_cached_player(row):
    """Audit an immutable prepared cache, including identity and input hashes."""
    from pathlib import Path
    from realface_batch_inventory import read
    from realface_pipeline import sha
    folder = Path(row['folder'])
    source, reduced = folder/'lite_skin-meshopt.json', folder/'lite_skin-meshopt-result.json'
    stamp = read(folder/'complete.json')
    if stamp.get('cache_key') != row['cache_key']:
        raise ValueError('Prepared identity cache key changed')
    hashes = {p.name: sha(p) for p in (source, reduced)}
    if any(stamp['outputs'].get(name) != digest for name, digest in hashes.items()):
        raise ValueError('Prepared reduction inputs changed')
    proof = audit(read(source), read(reduced)['indices'])
    return dict(**{k: row[k] for k in ('base_id', 'native_player_id', 'fingerprint', 'name')},
                status='audited', priority=needs_refinement(proof), input_sha256=hashes, **proof)


def main():
    import argparse
    from concurrent.futures import ProcessPoolExecutor
    from pathlib import Path
    from realface_batch_inventory import read, write
    from realface_pipeline import sha
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verified-report', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--workers', type=int, default=2, choices=range(1, 5))
    args = parser.parse_args()
    rows = read(args.verified_report)
    if any(r['status'] not in ('validated', 'validated_cached') for r in rows):
        raise ValueError('Input must be an independently verified batch')
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        result = list(pool.map(audit_cached_player, rows))
    write(args.output, dict(players=result, priority_count=sum(r['priority'] for r in result),
                           verified_report_sha256=sha(args.verified_report),
                           audit_source_sha256=sha(Path(__file__)), hardware_tested=False))


if __name__ == '__main__':
    main()
