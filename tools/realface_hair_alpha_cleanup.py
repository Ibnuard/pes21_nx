"""Conservative alpha proof for pruning nonrendering source hair triangles.

The mask shader's cutoff is 0.3333. A triangle can be removed only when every
texel in its periodic UV bounding rectangle, including bilinear neighbours,
is below 0.333 in both source and runtime-sized textures. This deliberately
rejects some invisible triangles instead of deleting a possibly visible one.
"""
import numpy as np


def alpha_bound(uv, alpha):
    uv = np.asarray(uv, dtype=float)
    alpha = np.asarray(alpha)
    if (uv.shape != (3, 2) or not np.isfinite(uv).all() or alpha.ndim != 2 or
            not alpha.size or not np.isfinite(alpha).all() or
            alpha.min() < 0 or alpha.max() > 1):
        raise ValueError('Invalid normalized alpha/triangle UV input')
    height, width = alpha.shape
    low = np.floor(uv.min(axis=0) * [width, height] - .5).astype(int) - 1
    high = np.ceil(uv.max(axis=0) * [width, height] - .5).astype(int) + 1
    # Avoid allocating an unbounded rectangle for tiling source UVs.
    xx = (np.arange(width) if high[0] - low[0] >= width else
          np.arange(low[0], high[0] + 1) % width)
    yy = (np.arange(height) if high[1] - low[1] >= height else
          np.arange(low[1], high[1] + 1) % height)
    return float(alpha[np.ix_(yy, xx)].max())


def invisible_bindings(triangles, uv, weights, alphas):
    """Return only offending triangles with a complete transparency proof."""
    triangles = np.asarray(triangles, dtype=int)
    uv = np.asarray(uv, dtype=float)
    if triangles.ndim != 2 or triangles.shape[1] != 3 or uv.shape != (len(triangles), 3, 2):
        raise ValueError('Source triangle/UV counts differ')
    if not alphas or not len(weights) or triangles.min(initial=0) < 0 or triangles.max(initial=0) >= len(weights):
        raise ValueError('Source weights/alpha are missing or out of range')
    allowed = {'sk_head', 'sk_neck', 'sk_chest'}
    bad = np.asarray([bool(set(w) - allowed) for w in weights])
    if any(not w for w in weights):
        raise ValueError('Missing source skin weights')
    offending = np.flatnonzero(bad[triangles].any(axis=1))
    removed = []; held = []; maximum = 0.
    for i in offending:
        bound = max(alpha_bound(uv[i], alpha) for alpha in alphas)
        maximum = max(maximum, bound)
        (removed if bound < .333 else held).append(int(i))
    return np.asarray(removed, dtype=int), dict(
        offending_triangles=len(offending), transparent_triangles=len(removed),
        potentially_visible_triangles=len(held), maximum_offending_alpha=maximum,
        source_and_runtime_alpha_checked=True, bilinear_wrap_checked=True,
        cutoff=.333, visible_source_geometry_changed=False)
