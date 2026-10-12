"""Conservative checks for explicitly audited source-to-cook exceptions."""
import math


def audited_triangle_drop(source, cooked, exact_collapses):
    """Accept unchanged topology or removal of every audited collapsed face.

    Coincident positions need not be welded when their UVs/weights differ.
    Retaining such triangles is valid; partial unexplained removal is not.
    """
    if min(source, cooked, exact_collapses) < 0 or exact_collapses > source:
        raise ValueError('Invalid triangle audit counts')
    if source == cooked:
        return 0
    if exact_collapses and source - cooked == exact_collapses:
        return exact_collapses
    raise ValueError('Cooked triangle count changed beyond audited collapses')


def collapsed_triangle(points):
    """Accept a point collapse or two exactly identical triangle corners.

    UE4 can weld matching corners and omit a repeated-index triangle. This
    Exact repeated corners form a zero-area line even when the third corner
    is distant. Near-coincident extended cards still do not qualify.
    A release recipe must separately declare its exact expected drop count.
    """
    if (len(points) != 3 or any(len(p) != 3 for p in points)
            or not all(math.isfinite(v) for p in points for v in p)):
        raise ValueError('Expected three finite triangle corners')
    return (any(all(points[a][axis] == points[b][axis] for axis in range(3))
                for a,b in ((0,1),(1,2),(0,2))) or
            all(max(p[axis] for p in points) - min(p[axis] for p in points)
                < .00001 for axis in range(3)))
