"""Offline stadium reduction with fixed stair/floor borders and original UVs.

Called inside Blender before atlasing. Whole stair surfaces receive a separate
budget so a global reducer cannot erase their treads/risers. Prefer fixed open
borders; dense disconnected stair boxes use bounded spatial clustering when
that cannot fit. Source UV values remain separate until the atlas stage.
"""
import json
from pathlib import Path
import subprocess
import bpy
import bmesh
import re


def reduce(shell, target, folder, node, module, underlay_materials=(), polygon_python=None, polygon_modules=None):
    mesh=shell.data
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
    mesh.calc_loop_triangles()
    rows=[];protected_faces=set()
    for mi,mat in enumerate(mesh.materials):
        # Keeping only treads exposes sky between them when risers disappear.
        # Treat the complete stair surface independently of facade/roof detail.
        triangles=[t for t in mesh.loop_triangles if t.material_index==mi]
        if not triangles:continue
        if not re.search(r'stair|stir|_star[0-9_]|_conc[0-9_]|_cncr324_|walkway|flatramp',mat.name):continue
        protected_faces.update(t.polygon_index for t in triangles)
        row=dict(name=mat.name,positions=[],uv=[],indices=[],originals=[],slot=mi)
        lookup={}
        for t in triangles:
            for vi,li in zip(t.vertices,t.loops):
                uv=tuple(mesh.uv_layers[0].data[li].uv)
                key=(*(round(c,3) for c in mesh.vertices[vi].co),*(round(c,5) for c in uv))
                if key not in lookup:
                    lookup[key]=len(row['originals']);row['originals'].append(vi)
                    row['positions'].extend(round(c,3) for c in mesh.vertices[vi].co);row['uv'].extend(uv)
                row['indices'].append(lookup[key])
        rows.append(row)
    before=len(mesh.loop_triangles)
    underlays=[]
    if underlay_materials:
        matched=[row for row in rows if row['name'] in underlay_materials]
        if len(matched)!=len(underlay_materials):raise ValueError('Reviewed stair backing material not found')
        request=Path(folder)/'underlay-input.json';reply=Path(folder)/'underlay-output.json'
        request.write_text(json.dumps(dict(materials=matched)))
        subprocess.run([polygon_python,str(Path(__file__).with_name('stadium_floor_underlay.py')),
                        '--input',str(request),'--output',str(reply),'--modules',polygon_modules],check=True)
        underlays=json.loads(reply.read_text())
    backing_total=sum(len(row['indices'])//3 for row in underlays)
    source=Path(folder)/'reduction-input.json';output=Path(folder)/'reduction-output.json'
    # Border/attribute constraints take priority; never silently exceed budget.
    result=None
    for cluster_error in (None,.005,.008):
        source.write_text(json.dumps(dict(materials=rows,ratio=.01,error=.5,
                                          cluster_relative_error=cluster_error)))
        subprocess.run([node,str(Path(__file__).with_name('meshopt_stadium_reduce.mjs')),
                        module,str(source),str(output)],check=True)
        result=json.loads(output.read_text())
        total=backing_total+sum(len(r['indices'])//3 for r in result)
        print('PESNX_SURFACE_REDUCTION',before,total,target,cluster_error,flush=True)
        if total<=target*.88:break
    if total>target*.88:
        raise ValueError('Protected stair surface cannot fit budget: '+str(total))
    vertices=[];faces=[];uvs=[];slots=[];metrics=[]
    for row,new in zip(rows,result):
        indices=new['indices'];used=sorted(set(indices));remap={old:i+len(vertices) for i,old in enumerate(used)}
        vertices.extend(mesh.vertices[row['originals'][i]].co.copy() for i in used)
        uvmap={remap[i]:row['uv'][i*2:i*2+2] for i in used}
        for start in range(0,len(indices),3):
            face=tuple(remap[i] for i in indices[start:start+3]);faces.append(face)
            uvs.extend(uvmap[i] for i in face);slots.append(row['slot'])
        metrics.append(dict(material=row['name'],before=len(row['indices'])//3,
                            after=len(indices)//3,error_m=new['error'],method=new['method']))
    for row in underlays:
        offset=len(vertices);slot=next(r['slot'] for r in rows if r['name']==row['name'])
        vertices.extend(tuple(row['positions'][i:i+3]) for i in range(0,len(row['positions']),3))
        for start in range(0,len(row['indices']),3):
            face=row['indices'][start:start+3];faces.append(tuple(offset+i for i in face));slots.append(slot)
            uvs.extend(row['uv'][i*2:i*2+2] for i in face)
    new=bpy.data.meshes.new(mesh.name+'_border_lite');new.from_pydata(vertices,[],faces);new.update()
    for mat in mesh.materials:new.materials.append(mat)
    uv=new.uv_layers.new(name='UVMap')
    for loop,value in zip(uv.data,uvs):loop.uv=value
    for p,slot in zip(new.polygons,slots):p.material_index=slot;p.use_smooth=True
    # Spend the remaining budget on rails, facade and roof detail. Protect
    # textured stair/concrete surfaces before this legacy detail reduction.
    bm=bmesh.new();bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.index in protected_faces],context='FACES')
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
    bm.to_mesh(mesh);bm.free();mesh.calc_loop_triangles()
    detail_before=len(mesh.loop_triangles)
    bpy.ops.object.select_all(action='DESELECT');shell.select_set(True);bpy.context.view_layer.objects.active=shell
    if detail_before>target-total:
        modifier=shell.modifiers.new('Remaining non-floor detail budget','DECIMATE')
        modifier.ratio=(target-total)/detail_before;modifier.use_collapse_triangulate=True
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    detail=bpy.data.objects.new('ProtectedSurfaces',new);bpy.context.collection.objects.link(detail)
    detail.select_set(True);bpy.ops.object.join()
    shell.data.calc_loop_triangles();after=len(shell.data.loop_triangles)
    if after>target:raise ValueError('Reduced shell exceeded structural budget')
    proof=dict(before=before,after=after,target=target,
               protected_open_borders_locked=all(r['method']=='fixed_border' for r in result),
               protected_surface='whole stair/concrete treads and risers',
               cluster_relative_error=cluster_error,
               backing_triangles=backing_total,
               backing_materials=[r['name'] for r in underlays],
               protected_vertices_uv_preserved=True,materials=metrics)
    (Path(folder)/'reduction.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof
