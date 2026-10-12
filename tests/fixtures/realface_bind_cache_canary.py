"""Blender-only regression: cached bind matrices equal the original arithmetic."""
import json
from pathlib import Path
import random
import sys
from types import SimpleNamespace

from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from blender_fit_realface import runtime_matrix, weighted_bind_matrix

rng = random.Random(29)


def rig():
    return {name: Matrix.Translation(Vector([rng.uniform(-10, 10) for _ in range(3)])) @
            Matrix.Rotation(rng.uniform(-.8, .8), 4, 'XYZ'[i % 3])
            for i, name in enumerate(('head', 'neck', 'chest'))}


native, cooked = rig(), rig()
obj = SimpleNamespace(matrix_world=Matrix.Translation(Vector((.3, -.2, .7))))
checks = 0
for revision in range(3):
    for i in range(200):
        raw = [rng.uniform(.01, 1) for _ in native]
        weights = {name: value / sum(raw) for name, value in zip(native, raw)}
        old_bind = Matrix([[sum((native[n] @ cooked[n].inverted())[r][c] * w for n, w in weights.items())
                            for c in range(4)] for r in range(4)])
        old = old_bind @ Matrix.Diagonal((1., -1., 1., 1.)) @ obj.matrix_world
        for reused in range(3):
            actual = runtime_matrix(obj, weights, native, cooked)
            assert max(abs(actual[r][c] - old[r][c]) for r in range(4) for c in range(4)) < 1e-6
            bind = weighted_bind_matrix(weights, native, cooked)
            assert max(abs(bind[r][c] - old_bind[r][c]) for r in range(4) for c in range(4)) < 1e-6
            checks += 2
    # New references must replace cached rig transforms, even with identical
    # names and weight tuples. Callers never mutate a rest rig in place.
    native, cooked = rig(), rig()
print(json.dumps(dict(bind_matrix_comparisons=checks, max_allowed_component_error=1e-6)))
