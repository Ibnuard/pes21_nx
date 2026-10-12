"""Offline shell limits: retain the native playable pitch and omit distant city."""
import math
import copy


def interpolate_vertex(a, b, fraction):
    """Clip authored stadium vertices without dropping UVs or normals."""
    out = copy.copy(a)
    for field, components in (('position', 'xyz'), ('normal', 'xyzw'),
                              ('tangent', 'xyzw'), ('color', 'rgba')):
        left, right = getattr(a, field, None), getattr(b, field, None)
        if left is None or right is None:
            continue
        value = copy.copy(left)
        for component in components:
            if hasattr(left, component):
                x, y = getattr(left, component), getattr(right, component)
                setattr(value, component, x + (y-x)*fraction)
        setattr(out, field, value)
    out.uv = []
    for left, right in zip(getattr(a, 'uv', []), getattr(b, 'uv', [])):
        uv = copy.copy(left)
        uv.u = left.u + (right.u-left.u)*fraction
        uv.v = left.v + (right.v-left.v)*fraction
        out.uv.append(uv)
    if getattr(a, 'boneMapping', None) or getattr(b, 'boneMapping', None):
        left, right = a.boneMapping or {}, b.boneMapping or {}
        out.boneMapping = {k: left.get(k, 0)*(1-fraction)+right.get(k, 0)*fraction for k in set(left)|set(right)}
    return out


def subtract_pitch(face, half_x=53.5, half_z=35.):
    """Return the outside pieces, preserving apron triangles across the pitch."""
    remaining = list(face.vertices)
    polygons = []
    for axis, sign, bound in (('x', 1, half_x), ('x', -1, half_x),
                              ('z', 1, half_z), ('z', -1, half_z)):
        if not remaining:
            break
        inside, outside = [], []
        for previous, current in zip(remaining[-1:]+remaining[:-1], remaining):
            before = sign*getattr(previous.position, axis)-bound
            after = sign*getattr(current.position, axis)-bound
            if (before <= 0) != (after <= 0):
                hit = interpolate_vertex(previous, current, before/(before-after))
                inside.append(hit); outside.append(hit)
            (inside if after <= 0 else outside).append(current)
        if len(outside) >= 3:
            polygons.append(outside)
        remaining = inside
    result = []
    for polygon in polygons:
        for i in range(1, len(polygon)-1):
            triangle = copy.copy(face)
            triangle.vertices = [polygon[0], polygon[i], polygon[i+1]]
            result.append(triangle)
    return result


def overlaps_pitch(points, half_x=53.5, half_z=35.):
    """Separating-axis triangle/rectangle test, including crossing large faces."""
    axes = [(1., 0.), (0., 1.)]
    for i in range(3):
        a,b = points[i],points[(i+1)%3]
        axes.append((-(b[2]-a[2]), b[0]-a[0]))
    for x,z in axes:
        projections=[p[0]*x+p[2]*z for p in points]
        radius=half_x*abs(x)+half_z*abs(z)
        if min(projections)>radius or max(projections)<-radius:
            return False
    return True


def trim_shell(model):
    removed={'native_pitch_overlap':0,'apron_fragments_retained':0,'distant_exterior':0,'degenerate':0}
    kept=[]
    for mesh in model.meshes:
        faces=[]
        for face in mesh.faces:
            points=[tuple(getattr(v.position,k) for k in 'xyz') for v in face.vertices]
            if len(points)!=3 or any(not math.isfinite(v) for p in points for v in p):
                raise ValueError('Nonfinite or non-triangle stadium geometry')
            if any(abs(p[0])>180 or abs(p[2])>150 or not -15<=p[1]<=100 for p in points):
                removed['distant_exterior']+=1;continue
            if max(p[1] for p in points)<2.6 and overlaps_pitch(points):
                fragments = subtract_pitch(face)
                faces.extend(fragments)
                removed['native_pitch_overlap']+=1
                removed['apron_fragments_retained']+=len(fragments)
                continue
            a,b,c=points
            u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
            cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            if sum(x*x for x in cross)<1e-16:
                removed['degenerate']+=1;continue
            faces.append(face)
        if faces:
            used={id(v):v for face in faces for v in face.vertices}
            mesh.vertices=list(used.values())
            mesh.faces=faces;kept.append(mesh)
    model.meshes=kept
    used_materials={id(m.materialInstance) for m in kept}
    model.materialInstances=[m for m in model.materialInstances if id(m) in used_materials]
    return removed
