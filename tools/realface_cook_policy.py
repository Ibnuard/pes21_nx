"""Conservative checks for explicitly audited source-to-cook exceptions."""
import math


def collapsed_triangle(points):
    """True only when all three corners occupy less than 0.00001 cm.

    UE4 can weld matching corners and omit a repeated-index triangle. This
    narrower check does not excuse loss of a thin but extended hair card.
    A release recipe must separately declare its exact expected drop count.
    """
    if (len(points) != 3 or any(len(p) != 3 for p in points)
            or not all(math.isfinite(v) for p in points for v in p)):
        raise ValueError('Expected three finite triangle corners')
    return all(max(p[axis] for p in points) - min(p[axis] for p in points)
               < .00001 for axis in range(3))
