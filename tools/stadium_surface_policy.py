"""Keep the owned Fox mesh's surface flags when merging stadium materials."""
import copy


def surface_policy(flags, shader, technique):
    # Source FMDL flags: 0x20 two-sided, 0x80 alpha test. Forward glass,
    # constant-alpha and decals also use 0x10. A solid forward shader does not.
    forward_alpha = bool(flags & 0x10) and 'solid' not in (shader+' '+technique).lower()
    return dict(masked=bool(flags & 0x80) or forward_alpha,
                two_sided=bool(flags & 0x20))


def apply_surface_policies(document, model):
    original = document['materials']
    materials, lookup = [], {}
    for mesh, node in zip(model.meshes, document['meshes']):
        policy = surface_policy(mesh.alphaFlags, mesh.materialInstance.shader, mesh.materialInstance.technique)
        for primitive in node['primitives']:
            old = primitive['material']
            key = (old, policy['masked'], policy['two_sided'])
            if key not in lookup:
                material = copy.deepcopy(original[old])
                material['name'] += '_'+('cut' if policy['masked'] else 'solid')+'_'+('two' if policy['two_sided'] else 'one')
                material['alphaMode'] = 'MASK' if policy['masked'] else 'OPAQUE'
                material['alphaCutoff'] = .4
                material['doubleSided'] = policy['two_sided']
                material['extras']['nxMasked'] = policy['masked']
                material['extras']['nxTwoSided'] = policy['two_sided']
                lookup[key] = len(materials)
                materials.append(material)
            primitive['material'] = lookup[key]
    document['materials'] = materials
