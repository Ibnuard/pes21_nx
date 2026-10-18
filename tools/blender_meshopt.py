"""Attribute-aware reduction adapter shared by owned face/stadium conversions."""
import json
from pathlib import Path
import subprocess
import bpy
from mathutils import Vector
from realface_surface_quality import unique_triangle_offsets, collapsed_skin_marker


def split_invalid_normal_fans(mesh, expected, weights):
    """Split only numerically invalid smooth fans; positions/UVs stay exact.

    Some coincident exporter islands form a singular Blender normal space.
    A few corner splits avoid zero/non-unit encoded normals without adding
    triangles or changing the source shading direction or bone weights.
    """
    bad = {loop.vertex_index for loop,normal,actual in zip(mesh.loops,expected,mesh.corner_normals)
           if normal.dot(actual.vector) < .999}
    if not bad:
        return mesh, weights, 0
    vertices=[]; faces=[]; mapped_weights=[]; lookup={}
    for poly in mesh.polygons:
        face=[]
        for vi in poly.vertices:
            key=(vi,poly.index if vi in bad else -1)
            if key not in lookup:
                lookup[key]=len(vertices);vertices.append(mesh.vertices[vi].co.copy())
                mapped_weights.append(weights[vi])
            face.append(lookup[key])
        faces.append(face)
    repaired=bpy.data.meshes.new(mesh.name+'_split_fans')
    repaired.from_pydata(vertices,[],faces);repaired.update()
    uv=repaired.uv_layers.new(name='UVMap')
    for target,source in zip(uv.data,mesh.uv_layers[0].data):target.uv=source.uv
    for poly in repaired.polygons:poly.use_smooth=True
    for material in mesh.materials:repaired.materials.append(material)
    repaired.normals_split_custom_set(expected)
    return repaired,mapped_weights,len(bad)


def reduce(obj, positions, target, role, job):
    mesh = obj.data; mesh.calc_loop_triangles()
    originals = []; coords = []; uvs = []; indices = []; lookup = {}; locks = []
    normals = []; corner_normals = []; weight_keys=[]
    keep_normals = job.get('mobile_v35') and role == 'skin'
    for tri in mesh.loop_triangles:
        for vi, li in zip(tri.vertices, tri.loops):
            uv = tuple(mesh.uv_layers[0].data[li].uv)
            v=mesh.vertices[vi]
            # Source exporters can duplicate entire surfaces/triangle corners.
            # Weld only identical position, UV and skin attributes; different
            # skinning at a coincident position must stay a separate vertex.
            weights=tuple(sorted((g.group,round(g.weight,7)) for g in v.groups))
            key = (*(round(c,5) for c in v.co),*(round(c,6) for c in uv),weights)
            if key not in lookup:
                lookup[key] = len(originals); originals.append(vi)
                coords.extend(positions[vi]);uvs.extend(uv)
                normals.append(Vector((0.,0.,0.)))
                weight_keys.append(weights)
                # Keep the fitted shoulder/neck attachment exactly.
                locks.append(int(role=='skin' and positions[vi].z < 155))
            indices.append(lookup[key])
            if keep_normals:
                corner_normals.append(mesh.corner_normals[li].vector.copy())
    if role=='skin' and job.get('eyelid_rim_points'):
        from mathutils.kdtree import KDTree
        tree=KDTree(len(job['eyelid_rim_points']))
        for i,p in enumerate(job['eyelid_rim_points']):tree.insert(Vector(p),i)
        tree.balance()
        for i in range(len(originals)):
            if tree.find(Vector(coords[i*3:i*3+3]))[2]<job['budgets'].get('eyelid_lock_cm',.18):locks[i]=1
    unique=[];collapsed_markers=0
    for start in unique_triangle_offsets(indices):
        face=indices[start:start+3]
        if keep_normals and collapsed_skin_marker(
                [coords[i*3:i*3+3] for i in face],[weight_keys[i] for i in face]):
            collapsed_markers+=1
            continue
        unique.extend(face)
        if keep_normals:
            # Only retained surfaces own shading directions. Oppositely wound
            # duplicate exports used to cancel valid normals before deduplication.
            for offset,vertex in enumerate(face):
                normals[vertex] += corner_normals[start+offset]
    indices=unique
    # The simplifier builds position aliases across its complete vertex table.
    # Vertices orphaned by the duplicate/degenerate filter must not be possible
    # collapse targets: their retained-surface normal is deliberately absent.
    active=sorted(set(indices));active_map={old:new for new,old in enumerate(active)}
    originals=[originals[i] for i in active]
    coords=[c for i in active for c in coords[i*3:i*3+3]]
    uvs=[c for i in active for c in uvs[i*2:i*2+2]]
    normals=[normals[i] for i in active]
    locks=[locks[i] for i in active]
    indices=[active_map[i] for i in indices]
    if role in ('skin','hair'):
        parents=list(range(len(originals)))
        def root(i):
            while parents[i]!=i:
                parents[i]=parents[parents[i]];i=parents[i]
            return i
        for start in range(0,len(indices),3):
            a,b,c=map(root,indices[start:start+3]);parents[b]=a;parents[c]=a
        components={}
        for i in range(len(originals)):components.setdefault(root(i),[]).append(i)
        # Small separate skin islands (nostril/ear details and source markers)
        # otherwise disappear despite negligible simplifier error. Retain them.
        for values in components.values():
            extent2=sum((max(coords[i*3+axis] for i in values)-min(coords[i*3+axis] for i in values))**2
                        for axis in range(3))
            # Retain point-size source hair islands as well: collapsing their
            # already microscopic triangles can create a false surface away
            # from the visible scalp. Do not lock normal-sized hair cards.
            if (role=='skin' and len(values)<=20) or (role=='hair' and extent2<.25**2):
                for i in values:locks[i]=1
    if role=='hair' and job['budgets'].get('hair_face_lock'):
        # A permissive collapse can join sparse beard cards into wide fins.
        # Preserve the original forward facial-hair surface; scalp sheets
        # retain the ordinary reduction path and the same whole-head ceiling.
        for i in range(len(originals)):
            x,y,z=coords[i*3:i*3+3]
            if z<170. and y>5. and abs(x)<9.:
                locks[i]=1
    flags = ['ErrorAbsolute']
    if role=='hair': flags += ['Permissive']
    if role=='skin' and job['budgets'].get('skin_feature_policy'):
        from blender_realface_mobile import pixels
        from realface_surface_quality import feature_locks
        locks, proof = feature_locks(coords, indices, uvs, locks, pixels(job['source_profile']['face_texture']))
        (Path(job['folder'])/'skin-feature-locks.json').write_text(json.dumps(proof, indent=2))
    request = dict(positions=coords,uv=uvs,indices=indices,locks=locks,target=target,
                   error={'skin':job['budgets'].get('skin_error_cm',.65),'eye':job['budgets'].get('eye_error_cm',.04),'hair':job['budgets'].get('hair_error_cm',3.)}[role],
                   uvWeight={'skin':job['budgets'].get('skin_uv_weight',.3),'eye':job['budgets'].get('eye_uv_weight',.5),'hair':job['budgets'].get('hair_uv_weight',.1)}[role],flags=flags)
    if keep_normals:
        # Surface directions are an error attribute as well as an exported
        # shading attribute. UV/position alone preferentially erase narrow
        # lips, nose wings and eyelid folds on otherwise smooth skin.
        def smooth(value):
            value=max(0.,min(1.,value));return value*value*(3-2*value)
        attributes=[]
        for i,n in enumerate(normals):
            x,y,z=coords[i*3:i*3+3]
            importance=.15+.85*smooth((y-5)/5)*smooth((z-153)/7)*smooth((183-z)/5)
            attributes.extend(c*importance for c in n.normalized())
        request.update(normals=attributes,normalWeight=job['budgets'].get('skin_normal_weight',.5),error=max(.65,request['error']))
        # Attribute error now mixes centimetres and weighted directions.
        # Independent face/neck surface limits still gate the output in cm.
    folder=Path(job['folder']);request_path=folder/(obj.name+'-meshopt.json')
    result_path=folder/(obj.name+'-meshopt-result.json')
    source_indices=indices[:]
    for attempt in range(3 if job.get('mobile_v35') and role=='skin' else 1):
        request_path.write_text(json.dumps(request))
        subprocess.run([job['node'],str(Path(__file__).with_name('meshopt_reduce.mjs')),
                        job['meshoptimizer'],str(request_path),str(result_path)],check=True)
        indices=json.loads(result_path.read_text())['indices']
        if not (job.get('mobile_v35') and role=='skin') or attempt==2:break
        from mathutils.bvhtree import BVHTree
        pos=[Vector(coords[i:i+3]) for i in range(0,len(coords),3)]
        tree=BVHTree.FromPolygons(pos,[indices[i:i+3] for i in range(0,len(indices),3)],all_triangles=True)
        protect=set()
        for start in range(0,len(source_indices),3):
            face=source_indices[start:start+3];a,b,c=(pos[i] for i in face)
            area2=(b-a).cross(c-a).length
            if area2<=2e-6 or (area2<=2e-4 and max((b-a).length,(c-a).length,(c-b).length)<.03):continue
            if (tree.find_nearest((a+b+c)/3)[3]>.70 or
                    any(tree.find_nearest(pos[i])[3]>.70 for i in face)):
                protect.update(face)
        if not any(not request['locks'][i] for i in protect):break
        # Protect the missing local feature and simplify other regions under
        # the same budget; never loosen the face/neck quality threshold.
        for i in protect:request['locks'][i]=1
    # Collapses can leave identical triangles. Blender's FBX importer removes
    # them while UE preserves them, so remove them explicitly before export.
    # Surviving vertex UVs and bone weights are unchanged.
    reduced=[];seen=set()
    for start in range(0,len(indices),3):
        face=indices[start:start+3];key=tuple(sorted(face))
        if len(set(face))==3 and key not in seen:
            reduced.extend(face);seen.add(key)
    if not reduced or len(reduced)%3 or max(reduced)>=len(originals):
        raise ValueError('Simplifier returned an invalid index buffer')
    used=sorted(set(reduced));remap={old:new for new,old in enumerate(used)}
    source_vertices=[mesh.vertices[originals[i]] for i in used]
    weights=[[(obj.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in source_vertices]
    names=[g.name for g in obj.vertex_groups]
    new=bpy.data.meshes.new(mesh.name+'_lite')
    new.from_pydata([v.co.copy() for v in source_vertices],[],
                    [tuple(remap[i] for i in reduced[start:start+3]) for start in range(0,len(reduced),3)])
    new.update()
    layer=new.uv_layers.new(name='UVMap')
    for poly in new.polygons:
        poly.use_smooth=True
        for vi,li in zip(poly.vertices,poly.loop_indices):layer.data[li].uv=uvs[used[vi]*2:used[vi]*2+2]
    for mat in mesh.materials:new.materials.append(mat)
    if keep_normals:
        # Index-only reduction keeps original vertex locations. Retain the
        # original smooth surface directions there too; recomputing normals
        # from the much sparser triangles creates false cheek/chin facets.
        expected=[normals[used[loop.vertex_index]].normalized() for loop in new.loops]
        if any(n.length < .99 for n in expected):
            raise ValueError('Cannot transfer a valid source skin normal')
        new.normals_split_custom_set(expected)
        new,weights,split_fans=split_invalid_normal_fans(new,expected,weights)
        minimum=min(n.dot(c.vector) for n,c in zip(expected,new.corner_normals))
        if minimum < .999:
            bad=[]
            for poly in new.polygons:
                for li in poly.loop_indices:
                    dot=expected[li].dot(new.corner_normals[li].vector)
                    if dot < .999:
                        bad.append(dict(corner=li,vertex=new.loops[li].vertex_index,
                            polygon=poly.index,area=poly.area,dot=dot,
                            expected=list(expected[li]),actual=list(new.corner_normals[li].vector)))
            (folder/(obj.name+'-normal-transfer-failure.json')).write_text(json.dumps(
                dict(minimum_dot=minimum,bad_corners=bad),indent=2))
            raise ValueError('Skin normal transfer differs from the source')
        (folder/(obj.name+'-normal-transfer.json')).write_text(json.dumps(dict(
            corners=len(expected),minimum_dot=minimum,source_normals_preserved=True,
            invalid_smooth_fans_split=split_fans,fan_split_preserves_triangles=True,
            collapsed_marker_triangles_removed=collapsed_markers)))
    obj.data=new
    obj.vertex_groups.clear()
    groups={name:obj.vertex_groups.new(name=name) for name in names}
    for vi,values in enumerate(weights):
        for name,value in values:groups[name].add([vi],value,'REPLACE')
    return len(reduced)//3
