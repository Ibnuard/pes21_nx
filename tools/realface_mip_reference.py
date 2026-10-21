"""Read-only masked-mip reference, never a texture patch or acceptance gate.

Array coverage is not hairstyle coverage: UV reuse, occlusion and the projected
pixel footprint matter. These orthographic mask proxies omit shading, gaze,
animation, anisotropic filtering and device-specific sampler behavior. A lower
average error does not approve a regression in an individual view. No package,
model, renderer or runtime is changed by this module.
"""
import numpy as np

CUTOFF = 85


def match_destination_coverage(alpha, target, maximum_scale=4.):
    """Find a bounded scale by measuring the actual destination, including ties.

    No minimum nonempty count is imposed. Discrete mip coverage can be
    unrepresentable; the returned residual must not be hidden by a forced pixel.
    """
    alpha = np.asarray(alpha)
    if alpha.dtype != np.uint8 or alpha.ndim != 2 or not alpha.size:
        raise ValueError('Expected nonempty uint8 alpha plane')
    if not 0 <= target <= 1 or maximum_scale < 1:
        raise ValueError('Invalid reference coverage/scale')
    positive = np.unique(alpha[alpha > 0]).astype(float)
    events = np.concatenate([(CUTOFF - .5 + side*1e-7)/positive
                             for side in (-1,1)])
    scales = sorted(set([.25,1.,maximum_scale] +
                        [float(s) for s in events if .25 <= s <= maximum_scale]))
    best = None
    for scale in scales:
        result = np.floor(alpha.astype(float) * scale + .5).clip(0, 255).astype(np.uint8)
        coverage = float(np.mean(result >= CUTOFF))
        score = (abs(coverage - target), abs(np.log(scale)))
        if best is None or score < best[0]:
            best = score, result, scale, coverage
    _, result, scale, coverage = best
    assert np.array_equal(result[alpha == 0], alpha[alpha == 0])
    return result, dict(scale=scale, target=target, measured=coverage,
                        absolute_error=abs(coverage-target),
                        minimum_nonempty_pixel_forced=False)


def alpha_reference_chain(alphas):
    if not alphas:
        raise ValueError('Missing alpha chain')
    target = float(np.mean(alphas[0] >= CUTOFF))
    result = [alphas[0].copy()]
    proof = [dict(index=0, unchanged=True, target=target, measured=target)]
    for i, alpha in enumerate(alphas[1:], 1):
        candidate, finding = match_destination_coverage(alpha, target)
        result.append(candidate)
        proof.append(dict(index=i, **finding))
    return result, proof


def bilinear(alpha, uv):
    """Periodic texture addressing with half-texel centers, linear alpha."""
    h, w = alpha.shape
    q = np.asarray(uv) * [w, h] - .5
    floor = np.floor(q).astype(np.int64)
    fraction = q - floor
    x, y = floor[..., 0], floor[..., 1]
    fx, fy = fraction[..., 0], fraction[..., 1]
    return (alpha[y % h, x % w] * (1-fx) * (1-fy)
            + alpha[y % h, (x+1) % w] * fx * (1-fy)
            + alpha[(y+1) % h, x % w] * (1-fx) * fy
            + alpha[(y+1) % h, (x+1) % w] * fx * fy)


def lod_for_triangle(points, uv, shape):
    """Orthographic affine derivatives; diagnostic, not the mobile GPU."""
    screen_edges = np.stack([points[1]-points[0], points[2]-points[0]])
    if abs(np.linalg.det(screen_edges)) < 1e-10:
        return 0.
    duv = np.stack([uv[1]-uv[0], uv[2]-uv[0]])
    derivatives = np.linalg.solve(screen_edges, duv)
    h, w = shape
    rho = max(np.linalg.norm(derivatives[0] * [w, h]),
              np.linalg.norm(derivatives[1] * [w, h]), 1.)
    return float(np.log2(rho))


def sample_chain(alphas, uv, lod):
    lod = np.clip(lod, 0, len(alphas)-1)
    low = int(np.floor(lod)); high = min(low+1, len(alphas)-1)
    f = lod-low
    return bilinear(alphas[low], uv)*(1-f) + bilinear(alphas[high], uv)*f


def masked_raster(p, triangles, uv, alphas, basis, bounds, size, skin_depth,
                  explicit_base=False):
    projected = p @ basis.T
    lo, hi = map(np.asarray, bounds)
    screen = (projected[:, :2]-lo)/(hi-lo)*size
    depth = np.full((size,size), -np.inf)
    mask = np.zeros((size,size), bool)
    fragments = 0
    for index, face in enumerate(triangles):
        points = screen[face]
        low = np.maximum(np.floor(points.min(axis=0)).astype(int), 0)
        high = np.minimum(np.ceil(points.max(axis=0)).astype(int), size-1)
        if np.any(high < low):
            continue
        a,b,c = points
        den = (b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den) < 1e-10:
            continue
        x,y = np.meshgrid(np.arange(low[0],high[0]+1)+.5,
                          np.arange(low[1],high[1]+1)+.5)
        w0 = ((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den
        w1 = ((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den
        w2 = 1-w0-w1
        bary = np.stack([w0,w1,w2], axis=-1)
        inside = (w0 >= -1e-7) & (w1 >= -1e-7) & (w2 >= -1e-7)
        mapped = bary @ uv[index]
        lod = 0. if explicit_base else lod_for_triangle(points, uv[index], alphas[0].shape)
        solid = inside & (sample_chain(alphas, mapped, lod) >= CUTOFF)
        fragments += int(solid.sum())
        sl = slice(low[1],high[1]+1), slice(low[0],high[0]+1)
        z = bary @ projected[face, 2]
        live = solid & (z > depth[sl]) & (z > skin_depth[sl]+.005)
        depth[sl][live] = z[live]
        mask[sl][live] = True
    return mask, fragments


def reference_error(mask, reference_fraction):
    expected = float(reference_fraction.sum())
    actual = int(mask.sum())
    hard_reference = reference_fraction >= .5
    union = int(np.count_nonzero(mask | hard_reference))
    return dict(expected_visible_pixels=expected, actual_visible_pixels=actual,
                normalized_absolute_error=float(np.abs(mask.astype(float)-reference_fraction).sum()/max(expected,1.)),
                coverage_ratio=actual/max(expected,1.),
                binary_half_coverage_iou=float(np.count_nonzero(mask & hard_reference)/union) if union else 1.)
