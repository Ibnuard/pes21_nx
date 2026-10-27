"""Keep the owned Fox mesh's surface flags when merging stadium materials."""
import copy
import re


def protected_surface(name, reviewed=()):
    """Preserve whole stair surfaces and explicitly reviewed venue surfaces.

    Some venues name their lower-tier risers/walkways as concrete or floor.
    They need the same fixed-border treatment, but a global concrete match
    would also protect unrelated facade detail in every existing recipe.
    """
    return name in reviewed or bool(re.search(
        r'stair|stir|_star[0-9_]|_conc[0-9_]|_cncr324_|walkway|flatramp', name))


def preserved_source_faces(positions, indices, rules):
    """Select reviewed original panels before disconnected stair clustering.

    Positions use Blender's (Fox X, -Fox Z, Fox height) metre basis. Exact
    expected counts and the outer conversion fingerprints bind each rule.
    No new vertices, filled holes, texture changes or displaced faces result.
    """
    import numpy as np
    p=np.asarray(positions,dtype=float).reshape(-1,3)
    ids=np.asarray(indices).reshape(-1,3)
    if (not np.isfinite(p).all() or not np.issubdtype(ids.dtype,np.integer) or
            not len(ids) or ids.min()<0 or ids.max()>=len(p)):
        raise ValueError('Malformed preserved source surface')
    t=p[ids];selected=np.zeros(len(ids),dtype=bool)
    for rule in rules:
        expected=rule['expected_source_triangles']
        if type(expected) is not int or not 1<=expected<=2048:
            raise ValueError('Unbounded source panel count')
        if rule['kind']=='wide_panel':
            edge=rule['minimum_edge_m'];area=rule['minimum_area_m2']
            if not 10<=edge<=150 or not 1<=area<=100:
                raise ValueError('Unreviewed source panel dimensions')
            longest=np.linalg.norm(t-np.roll(t,1,axis=1),axis=2).max(1)
            size=np.linalg.norm(np.cross(t[:,1]-t[:,0],t[:,2]-t[:,0]),axis=1)*.5
            match=(longest>=edge)&(size>=area)
        elif rule['kind']=='upper_stair_band':
            lo=rule['minimum_height_m'];hi=rule['maximum_height_m']
            zlo=rule['minimum_source_z_m'];zhi=rule['maximum_source_z_m']
            if (not all(np.isfinite(x) for x in (lo,hi,zlo,zhi)) or
                    not 8<=lo<hi<=40 or hi-lo>3 or
                    not 40<=zlo<zhi<=120 or zhi-zlo>10):
                raise ValueError('Unreviewed upper stair band')
            match=((t[:,:,2].min(1)>=lo)&(t[:,:,2].max(1)<=hi)&
                   (-t[:,:,1].max(1)>=zlo)&(-t[:,:,1].min(1)<=zhi))
        elif rule['kind']=='central_stair_access':
            width=rule['maximum_abs_source_x_m']
            lo=rule['minimum_height_m'];hi=rule['maximum_height_m']
            zlo=rule['minimum_abs_source_z_m'];zhi=rule['maximum_abs_source_z_m']
            if (not all(np.isfinite(x) for x in (width,lo,hi,zlo,zhi)) or
                    not .5<=width<=4 or not -.1<=lo<=0 or not 2<=hi<=8 or
                    not 35<=zlo<zhi<=65 or zhi-zlo>15):
                raise ValueError('Unreviewed central stair access bounds')
            # Preserve the actual narrow treads and risers at both sideline
            # entrances. Spatial clustering can erase these even when the
            # whole material has a fixed-border fallback. Keep source faces,
            # rather than drawing a replacement plane across either access.
            match=((abs(t[:,:,0]).max(1)<=width)&
                   (t[:,:,2].min(1)>=lo)&(t[:,:,2].max(1)<=hi)&
                   (abs(t[:,:,1]).min(1)>=zlo)&(abs(t[:,:,1]).max(1)<=zhi))
        else:
            raise ValueError('Unknown preserved source surface rule')
        if int(match.sum())!=expected:
            raise ValueError('Reviewed source panel count changed')
        selected|=match
    return np.flatnonzero(selected).tolist()


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
