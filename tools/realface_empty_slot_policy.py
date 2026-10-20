"""An explicit transparent native placeholder is not missing visible hair."""
import math


def verified_empty_slot(positions, triangles, alpha_max, materials, bindings):
    if materials != ['rf_hair_empty'] or alpha_max != 0:
        raise ValueError('Empty-slot recovery requires declared empty material and zero alpha')
    if len(positions) != 3 or len(triangles) != 1 or sorted(triangles[0]) != [0, 1, 2]:
        raise ValueError('Only the existing three-vertex placeholder is supported')
    if len(bindings) != 3 or any(b != {'sk_head': 1.0} for b in bindings):
        raise ValueError('Empty slot must retain its exact native head binding')
    if any(len(p) != 3 or any(not math.isfinite(v) for v in p) for p in positions):
        raise ValueError('Nonfinite empty-slot geometry')
    spans = [max(p[i] for p in positions)-min(p[i] for p in positions) for i in range(3)]
    if max(spans) > .051 or any(abs(p[0]) > 2 or abs(p[1]) > 8 or not 160 < p[2] < 185 for p in positions):
        raise ValueError('Placeholder must remain tiny and inside the native head')
    return dict(policy='existing_transparent_native_head_slot_v1', triangles=1,
                source_extent_cm=spans, alpha_max=0, visible_source_removed=False,
                geometry_replaced=False, binding_changed=False)
