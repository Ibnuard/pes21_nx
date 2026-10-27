"""Select explicitly reviewed backing from an owned shell glTF.

The input is a local intermediate export, not committed geometry. Upright
panels require an exact height band or a hash-bound face/bounds receipt.
Reviewed roof surfaces retain their exact source positions. An explicit
underground-floor receipt restores only the source outline outside the
protected field rectangle. Unreviewed geometry remains excluded.
"""
import hashlib
import json
from pathlib import Path


def signal_foundation_quads(recipe):
    """Project-authored underground completion of two measured apron gaps.

    This is deliberately distinct from unchanged source-face restoration.
    The floor is below the camera exclusion and outside its horizontal box;
    it never fills the protected playing surface or moves an original face.
    """
    import numpy as np
    from stadium_geometry import overlaps_pitch
    expected=[dict(minimum_x_m=-30.,maximum_x_m=-14.,minimum_z_m=40.01,maximum_z_m=44.5),
              dict(minimum_x_m=14.,maximum_x_m=30.,minimum_z_m=40.01,maximum_z_m=44.5)]
    if (recipe.get('key')!='SignalIdunaPark' or recipe.get('kind')!='authored_apron_foundation' or
            recipe.get('plane_m')!=-.6 or recipe.get('quads')!=expected):
        raise ValueError('Unreviewed Signal Iduna foundation bounds')
    result=[]
    for q in expected:
        x0,x1=q['minimum_x_m'],q['maximum_x_m'];z0,z1=q['minimum_z_m'],q['maximum_z_m']
        points=[[x0,-.6,z0],[x0,-.6,z1],[x1,-.6,z1],[x1,-.6,z0]]
        uv=[(0.,0.),(0.,1.),(1.,1.),(1.,0.)]
        for ids in ((0,1,2),(0,2,3)):
            tri=np.array([points[i] for i in ids])
            if overlaps_pitch(tri,58.,40.):
                raise ValueError('Foundation overlaps the protected camera/pitch box')
            result.append(dict(positions=tri.tolist(),normal=[0.,1.,0.],
                               uv=[uv[i] for i in ids],source_triangle=None,
                               winding_flipped=False))
    return result,dict(kind='project_authored_underground_foundation',triangles=4,
        plane_m=-.6,protected_half_x_m=58.,protected_half_z_m=40.,
        camera_box_bottom_clearance_m=.1,quads=expected,
        policy_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def clip_floor_triangles(positions, indices, *, plane_m, expected_source_triangles,
                        protected_half_x_m=58., protected_half_z_m=40.):
    """Clip only an owned planar underground floor, preserving its outline.

    Runs in the host Python with optional Shapely, before the Blender stage.
    The protected rectangle becomes a real hole, not an overlapping overlay.
    """
    import numpy as np
    from shapely import polygons, union_all, box, constrained_delaunay_triangles
    p=np.asarray(positions,dtype=float);ids=np.asarray(indices)
    if (not np.isfinite(p).all() or not -15 <= plane_m < -.25 or
            not 53.5 <= protected_half_x_m <= 65 or not 35 <= protected_half_z_m <= 45):
        raise ValueError('Unreviewed underground backing plane')
    tri=p[ids]
    selected=np.all(abs(tri[:,:,1]-plane_m)<.002,axis=1)
    if int(selected.sum())!=expected_source_triangles:
        raise ValueError('Owned floor selection changed')
    footprint=union_all(polygons(tri[selected][:,:,[0,2]]),grid_size=.00001)
    protected=box(-protected_half_x_m,-protected_half_z_m,protected_half_x_m,protected_half_z_m)
    region=footprint.difference(protected)
    rows=[]
    for triangle in constrained_delaunay_triangles(region).geoms:
        points=np.array([[x,plane_m,z] for x,z in list(triangle.exterior.coords)[:3]])
        n=np.cross(points[1]-points[0],points[2]-points[0])
        if np.linalg.norm(n)<1e-8:continue
        if n[1]<0:points=points[[0,2,1]]
        rows.append(dict(positions=points.tolist(),normal=[0.,1.,0.],uv=[(.5,.5)]*3,
                         source_triangle=None,winding_flipped=False))
    if not 1<=len(rows)<=148 or region.intersection(protected).area>1e-8:
        raise ValueError('Unbounded or overlapping clipped backing')
    return rows,dict(source_triangles=int(selected.sum()),clipped_triangles=len(rows),plane_m=plane_m,
                     source_area_m2=float(footprint.area),retained_area_m2=float(region.area),
                     protected_half_x_m=protected_half_x_m,protected_half_z_m=protected_half_z_m,
                     protected_overlap_m2=float(region.intersection(protected).area))


def select_triangles(positions, indices, *, bottom_m, top_m, expected_triangles,
                     protected_half_x_m=58., protected_half_z_m=40.):
    import numpy as np
    from stadium_geometry import overlaps_pitch
    positions = np.asarray(positions, dtype=float)
    indices = np.asarray(indices)
    if (positions.ndim != 2 or positions.shape[1] != 3 or
            indices.ndim != 2 or indices.shape[1] != 3 or
            not np.issubdtype(indices.dtype, np.integer) or
            not np.isfinite(positions).all() or not len(indices) or
            indices.min() < 0 or indices.max() >= len(positions)):
        raise ValueError('Malformed backing geometry')
    if not -15 <= bottom_m < top_m <= 100 or not 1 <= expected_triangles <= 232:
        raise ValueError('Unbounded backing selection')
    selected = []
    for index, tri in enumerate(positions[indices]):
        normal = np.cross(tri[1]-tri[0], tri[2]-tri[0])
        area = float(np.linalg.norm(normal))
        # Source float32 positions can give a nominally vertical pane a
        # 0.003 degree residual tilt. Horizontal/roof faces remain excluded.
        if area < 1e-9 or abs(normal[1])/area > 1e-4:
            continue
        if abs(tri[:, 1].min()-bottom_m) > .002 or abs(tri[:, 1].max()-top_m) > .002:
            continue
        if overlaps_pitch(tri, protected_half_x_m, protected_half_z_m):
            raise ValueError('Reviewed backing overlaps the protected field')
        # This is the inward side of the source exterior wall, used behind
        # open entrances. Determine the winding geometrically, without
        # applying the unrelated source technique's face-culling convention.
        centre = tri.mean(axis=0)
        if float(normal[[0, 2]] @ centre[[0, 2]]) > 0:
            tri = tri[[0, 2, 1]]
            normal = -normal
            flipped = True
        else:
            flipped = False
        normal /= area
        selected.append(dict(source_triangle=index, positions=tri.tolist(),
                             normal=normal.tolist(), winding_flipped=flipped))
    if len(selected) != expected_triangles:
        raise ValueError('Reviewed vertical backing selection changed: '+str(len(selected)))
    return selected


def select_upright_panel(positions, indices, *, panel_indices, expected_bounds,
                         plane_axis, plane_m):
    """Exact source-plane receipt for an irregular roof-end backing polygon."""
    import numpy as np
    from stadium_geometry import overlaps_pitch
    p=np.asarray(positions,dtype=float);ids=np.asarray(indices)
    bounds=np.asarray(expected_bounds,dtype=float)
    if (p.ndim!=2 or p.shape[1]!=3 or ids.ndim!=2 or ids.shape[1]!=3 or
            not np.issubdtype(ids.dtype,np.integer) or not len(ids) or
            ids.min()<0 or ids.max()>=len(p) or not np.isfinite(plane_m) or
            plane_axis not in (0,2) or bounds.shape!=(2,3) or
            not np.isfinite(bounds).all() or not np.isfinite(p).all() or
            bounds[0,1]<-15 or bounds[1,1]>100 or
            not 1<=len(panel_indices)<=32 or len(set(panel_indices))!=len(panel_indices) or
            any(not isinstance(i,int) or i<0 or i>=len(ids) for i in panel_indices)):
        raise ValueError('Unbounded upright panel receipt')
    triangles=p[ids[panel_indices]]
    if (abs(triangles[:,:,plane_axis]-plane_m).max()>.002 or
            abs(np.array([triangles.min((0,1)),triangles.max((0,1))])-bounds).max()>.002):
        raise ValueError('Upright panel source plane/bounds changed')
    result=[]
    for index,tri in zip(panel_indices,triangles):
        normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);area=np.linalg.norm(normal)
        if area<1e-9 or abs(normal[1])/area>1e-4 or overlaps_pitch(tri,58.,40.):
            raise ValueError('Upright panel is degenerate, sloped or overlaps the field')
        flipped=float(normal[[0,2]]@tri.mean(0)[[0,2]])>0
        if flipped:tri=tri[[0,2,1]];normal=-normal
        result.append(dict(source_triangle=index,positions=tri.tolist(),
                           normal=(normal/area).tolist(),winding_flipped=flipped))
    return result


def select_source_surface(positions, indices, *, surface_indices, expected_bounds,
                          orientation):
    """Bounded exact source faces: outer walls or the underside of a roof."""
    import numpy as np
    from stadium_geometry import overlaps_pitch
    p=np.asarray(positions,dtype=float);ids=np.asarray(indices)
    bounds=np.asarray(expected_bounds,dtype=float)
    if (p.ndim!=2 or p.shape[1]!=3 or ids.ndim!=2 or ids.shape[1]!=3 or
            not np.issubdtype(ids.dtype,np.integer) or not len(ids) or
            ids.min()<0 or ids.max()>=len(p) or not np.isfinite(p).all() or
            bounds.shape!=(2,3) or not np.isfinite(bounds).all() or
            not 1<=len(surface_indices)<=256 or len(set(surface_indices))!=len(surface_indices) or
            any(not isinstance(i,int) or i<0 or i>=len(ids) for i in surface_indices) or
            orientation not in ('outer_wall','roof_underside','source_clockwise')):
        raise ValueError('Unbounded source surface receipt')
    triangles=p[ids[surface_indices]]
    if (abs(np.array([triangles.min((0,1)),triangles.max((0,1))])-bounds).max()>.002 or
            bounds[0,1]<-15 or bounds[1,1]>60 or abs(bounds[:,[0,2]]).max()>150):
        raise ValueError('Source surface bounds changed')
    result=[]
    for index,tri in zip(surface_indices,triangles):
        normal=np.cross(tri[1]-tri[0],tri[2]-tri[0]);area=np.linalg.norm(normal)
        if area<1e-8:raise ValueError('Degenerate source surface')
        if orientation=='outer_wall':
            if abs(normal[1])/area>1e-4 or overlaps_pitch(tri,58.,40.):
                raise ValueError('Outer backing must be upright and outside the field')
            flipped=float(normal[[0,2]]@tri.mean(0)[[0,2]])>0
        elif orientation=='source_clockwise':
            if overlaps_pitch(tri,53.5,35.):raise ValueError('Source repair overlaps the playing surface')
            flipped=True
        else:
            if tri[:,1].min()<8 or overlaps_pitch(tri,53.5,35.):
                raise ValueError('Roof backing overlaps the protected playing surface')
            # Roof sheets face the stadium interior. Upright end panes use
            # the same inward winding as the surrounding source walls.
            flipped=normal[1]>0 if abs(normal[1])/area>.1 else float(normal[[0,2]]@tri.mean(0)[[0,2]])>0
        if flipped:tri=tri[[0,2,1]];normal=-normal
        result.append(dict(source_triangle=index,positions=tri.tolist(),normal=(normal/area).tolist(),winding_flipped=bool(flipped)))
    return result


def backing_budget_allowed(recipe, base_triangles, added_triangles):
    maximum=recipe['maximum_total_triangles']
    if not 0<base_triangles or not 0<added_triangles or base_triangles+added_triangles>maximum:
        return False
    if maximum<=24560:return True
    # Explicit Old Trafford completion: preserve its accepted base instead of
    # damaging stairs/crowd again to make room for missing source roof sheets.
    return (recipe.get('key')=='OldTrafford' and base_triangles==24522 and
            maximum<=25320 and added_triangles<=798 and
            recipe.get('source_roof_completion')==dict(native_reference=24560,maximum_extra_triangles=760))


def load_selection(path, *, expected_sha256, expected_buffer_sha256, material,
                   primitive_ordinal=None, floor_receipt=None, floor_receipt_sha256=None, **selection):
    import numpy as np
    from audit_stadium_optimization import accessor
    path = Path(path).resolve(strict=True)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Backing source fingerprint changed')
    doc = json.loads(raw)
    if (doc.get('asset', {}).get('generator') != 'PES 2021 NX FMDL intermediate exporter' or
            any(any(k in n for k in ('matrix', 'scale', 'rotation', 'translation')) for n in doc['nodes']) or
            len(doc['buffers']) != 1):
        raise ValueError('Backing must use the audited native-axis intermediate')
    uri = Path(doc['buffers'][0]['uri'])
    if uri.name != str(uri) or uri.is_absolute():
        raise ValueError('Unsafe backing buffer path')
    blob = (path.parent/uri).read_bytes()
    if (len(blob) != doc['buffers'][0]['byteLength'] or
            hashlib.sha256(blob).hexdigest() != expected_buffer_sha256):
        raise ValueError('Backing buffer fingerprint/length changed')
    matches = [p for mesh in doc['meshes'] for p in mesh['primitives']
               if doc['materials'][p['material']]['name'] == material]
    if primitive_ordinal is None:
        if len(matches) != 1:
            raise ValueError('Expected one reviewed backing material')
        primitive_ordinal = 0
    elif (type(primitive_ordinal) is not int or
          not 0 <= primitive_ordinal < len(matches)):
        raise ValueError('Reviewed backing primitive ordinal is out of range')
    prim = matches[primitive_ordinal]
    if prim.get('mode', 4) != 4:
        raise ValueError('Reviewed backing primitive is not triangles')
    if floor_receipt is not None:
        payload=Path(floor_receipt).read_bytes()
        if hashlib.sha256(payload).hexdigest()!=floor_receipt_sha256:
            raise ValueError('Clipped floor receipt fingerprint changed')
        receipt=json.loads(payload)
        if (receipt['gltf_sha256']!=expected_sha256 or receipt['buffer_sha256']!=expected_buffer_sha256 or
                receipt['material']!=material or receipt['proof']['protected_overlap_m2']!=0 or
                not 1<=len(receipt['rows'])<=148):
            raise ValueError('Clipped floor receipt belongs to another source')
        from stadium_geometry import overlaps_pitch
        raw_pos=accessor(doc,blob,prim['attributes']['POSITION'])
        raw_ids=accessor(doc,blob,prim['indices']).reshape(-1,3)
        raw_tri=raw_pos[raw_ids]
        source_floor=raw_tri[np.all(abs(raw_tri[:,:,1]-receipt['proof']['plane_m'])<.002,axis=1)]
        if len(source_floor)!=receipt['proof']['source_triangles']:
            raise ValueError('Clipped receipt source floor selection changed')
        source_xz=source_floor[:,:,[0,2]]
        def inside_source(point):
            a,b,c=source_xz[:,0],source_xz[:,1],source_xz[:,2]
            cross=lambda v,w:v[:,0]*w[:,1]-v[:,1]*w[:,0]
            e0=cross(b-a,point-a);e1=cross(c-b,point-b);e2=cross(a-c,point-c)
            return np.any(((e0>=-.002)&(e1>=-.002)&(e2>=-.002))|((e0<=.002)&(e1<=.002)&(e2<=.002)))
        for row in receipt['rows']:
            points=np.array(row['positions'])
            if (points.shape!=(3,3) or not np.isfinite(points).all() or
                    np.max(abs(points[:,1]-receipt['proof']['plane_m']))>.002 or
                    overlaps_pitch(points,receipt['proof']['protected_half_x_m']-.0001,
                                   receipt['proof']['protected_half_z_m']-.0001) or
                    not all(inside_source(p[[0,2]]) for p in [*points,points.mean(0)])):
                raise ValueError('Clipped floor geometry violates its source/field bounds')
        return receipt['rows'],dict(gltf_sha256=expected_sha256,buffer_sha256=expected_buffer_sha256,
                                    material=material,floor=receipt['proof'])
    selector=(select_source_surface if 'surface_indices' in selection else
              select_upright_panel if 'panel_indices' in selection else select_triangles)
    result = selector(accessor(doc, blob, prim['attributes']['POSITION']),
                              accessor(doc, blob, prim['indices']).reshape(-1, 3), **selection)
    ids = accessor(doc, blob, prim['indices']).reshape(-1, 3)
    uv = accessor(doc, blob, prim['attributes']['TEXCOORD_0'])
    if not np.isfinite(uv).all():
        raise ValueError('Backing source UVs are nonfinite')
    for row in result:
        values = uv[ids[row['source_triangle']]]
        if row['winding_flipped']:
            values = values[[0, 2, 1]]
        # glTF UV V-down -> Blender V-up; export then restores UE's V-down.
        row['uv'] = [(float(u), 1.-float(v)) for u, v in values]
    return result, dict(gltf_sha256=hashlib.sha256(raw).hexdigest(),
                        buffer_sha256=hashlib.sha256(blob).hexdigest(), material=material,
                        primitive_ordinal=primitive_ordinal)
