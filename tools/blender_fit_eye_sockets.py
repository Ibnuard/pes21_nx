"""Automatically place both eyes using the FL26 face's own eyelid rim.

Run in Blender with -- --profile local.json. The profile explicitly selects
own native eyes or a shared geometric eye template; accepted pilots are not
inputs. Every result is checked through an FBX round-trip.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals
from blender_fit_realface import runtime_matrix,vertex_weights
from realface_reference import load_reference
from realface_eye_fit import fit_socket,pupil_position,radial_atlas_pupil,rotation_between


def repair_undefined_normals(eye_material):
    """Give only zero-length source normals a defined per-face direction.

    Opposing folded faces can cancel a smoothed vertex normal. Limit this to
    less than one per thousand corners; valid normals, topology and weights
    are preserved. A missing normal on a degenerate face is left to Blender.
    """
    rows=[]
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or eye_material in [m.name for m in obj.data.materials]:continue
        normals=[n.vector.copy() for n in obj.data.corner_normals]
        missing={i for i,n in enumerate(normals) if n.length<.5}
        if not missing:continue
        if len(missing)>max(6,len(normals)//1000):
            raise ValueError('Too many undefined source normals for local repair')
        repaired=[]
        for polygon in obj.data.polygons:
            for index in polygon.loop_indices:
                if index in missing and polygon.normal.length>.5:
                    normals[index]=polygon.normal.copy();repaired.append(index)
        obj.data.normals_split_custom_set(normals)
        rows.append(dict(mesh=obj.name,repaired_normal_corners=len(repaired)))
    return rows


def protected_snapshot(eye_material,native,cooked):
    result={}
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or eye_material in [m.name for m in obj.data.materials]:continue
        obj.data.calc_loop_triangles()
        degenerate={i for tri in obj.data.loop_triangles if tri.area<1e-8 for i in tri.loops}
        result[obj.name]=dict(
            points=np.asarray([tuple(runtime_matrix(obj,vertex_weights(obj,v),native,cooked)@v.co) for v in obj.data.vertices]),
            uv=[[tuple(v.uv) for v in layer.data] for layer in obj.data.uv_layers],
            polygons=[tuple(p.vertices) for p in obj.data.polygons],
            weights=[vertex_weights(obj,v) for v in obj.data.vertices],
            materials=[m.name for m in obj.data.materials],
            normals=[tuple(n.vector) for n in obj.data.corner_normals],degenerate_normal_corners=degenerate)
    return result


def verify_protected(before,after):
    if set(before)!=set(after):raise ValueError('Eye replacement changed the protected mesh set')
    rows=[]
    for name,old in before.items():
        new=after[name]
        for key in ('uv','polygons','materials'):
            if old[key]!=new[key]:raise ValueError('Eye replacement changed protected '+key)
        if old['points'].shape!=new['points'].shape:raise ValueError('Eye replacement changed protected topology')
        drift=float(np.max(np.linalg.norm(old['points']-new['points'],axis=1)))
        weight=max(sum(abs(a.get(b,0)-c.get(b,0)) for b in a.keys()|c.keys()) for a,c in zip(old['weights'],new['weights']))
        old_normals=np.asarray(old['normals']);new_normals=np.asarray(new['normals'])
        normal_errors=np.linalg.norm(old_normals-new_normals,axis=1)
        undefined=set(np.flatnonzero(np.linalg.norm(old_normals,axis=1)<.5))
        if not undefined<=old['degenerate_normal_corners']:
            raise ValueError('Source has undefined normals on nondegenerate protected faces')
        normal=float(max((e for i,e in enumerate(normal_errors) if i not in undefined),default=0))
        if drift>.001 or weight>1e-5 or normal>.002:
            raise ValueError('Eye replacement moved protected geometry, weights or normals: '+
                             str(dict(mesh=name,position_cm=drift,weights=weight,normals=normal,
                                      zero_source_normals=int((np.linalg.norm(old_normals,axis=1)<.5).sum()),
                                      zero_result_normals=int((np.linalg.norm(new_normals,axis=1)<.5).sum()))))
        rows.append(dict(mesh=name,vertices=len(old['points']),position_drift_cm=drift,weight_l1_drift=weight,normal_drift=normal,undefined_degenerate_normal_corners=len(undefined)))
    return rows


def audit_existing(profile):
    """Also audit a previously generated candidate without rebuilding it."""
    native=rig_globals(json.loads(Path(profile['native_rig']).read_text()))
    cooked=rig_globals(json.loads(Path(profile['cooked_rig']).read_text()))
    def snapshot(path,material):
        bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=.01
        bpy.ops.import_scene.fbx(filepath=str(Path(path).resolve()),use_anim=False)
        repair_undefined_normals(material)
        return protected_snapshot(material,native,cooked)
    before=snapshot(profile['face_fbx'],profile['replace_material'])
    after=snapshot(profile['output'],profile['eye_material'])
    return verify_protected(before,after)


def center_visible_pupil(points,faces,pupil,center,rim,skin_tree):
    """Measure the actually visible eyelid aperture, after globe placement."""
    p=np.asarray(points);pupil=np.asarray(pupil);center=np.asarray(center)
    total=np.eye(3);rows=[];bounds=np.asarray(rim)
    for iteration in range(4):
        tree=BVHTree.FromPolygons([Vector(q) for q in p],faces,all_triangles=True)
        ray_y=float(max(p[:,1])+30)
        def opening(axis,cross):
            other=2 if axis==0 else 0;visible=[]
            for delta in (-.06,-.03,0,.03,.06):
                for value in np.linspace(bounds[:,axis].min(),bounds[:,axis].max(),161):
                    origin=Vector((0,ray_y,0));origin[axis]=value;origin[other]=cross+delta
                    hit,_,_,distance=tree.ray_cast(origin,Vector((0,-1,0)))
                    skin,_,_,depth=skin_tree.ray_cast(origin,Vector((0,-1,0)))
                    if hit is not None and (skin is None or distance<depth-.005):visible.append(float(value))
            if len(visible)<50:raise ValueError('Pupil opening is too occluded for automatic gaze')
            return [min(visible),max(visible),sum(visible)/len(visible)]
        horizontal=opening(0,pupil[2]);vertical=opening(2,horizontal[2])
        error=float(np.linalg.norm(pupil[[0,2]]-[horizontal[2],vertical[2]]))
        rows.append(dict(pupil_cm=pupil.tolist(),visible_x=horizontal,visible_z=vertical,centering_error_cm=error))
        if error<=.035:return p,total,pupil,dict(iterations=rows,final_error_cm=error)
        if iteration==3:break
        old=pupil-center;radius=float(np.linalg.norm(old));dx=horizontal[2]-center[0];dz=vertical[2]-center[2]
        if dx*dx+dz*dz>=radius*radius:raise ValueError('Visible opening is unreachable by iris rotation')
        direction=np.asarray([dx,np.sqrt(radius*radius-dx*dx-dz*dz),dz])
        rotation,degrees=rotation_between(old,direction)
        if degrees>12:raise ValueError('Optical pupil correction exceeds 12 degrees')
        p=(p-center)@rotation.T+center;pupil=(pupil-center)@rotation.T+center;total=rotation@total
    raise ValueError('Optical pupil centering failed to converge')


def fit(profile):
    output=Path(profile['output']).resolve()
    if output.exists():raise ValueError('Refusing existing automatic-eye candidate')
    native=rig_globals(json.loads(Path(profile['native_rig']).read_text()))
    cooked=rig_globals(json.loads(Path(profile['cooked_rig']).read_text()))
    guide=json.loads(Path(profile['eyelid_rim']).read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=.01
    bpy.ops.import_scene.fbx(filepath=str(Path(profile['face_fbx']).resolve()),use_anim=False)
    arms=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    if len(arms)!=1 or set(b.name for b in arms[0].data.bones)!=set(native):
        raise ValueError('Unexpected eye target skeleton')
    eyes=[o for o in bpy.context.scene.objects if o.type=='MESH' and
          [m.name for m in o.data.materials]==[profile['replace_material']]]
    if len(eyes)!=1:raise ValueError('Expected one dedicated replaceable eye mesh')
    old=eyes[0]
    normal_repairs=repair_undefined_normals(profile['replace_material'])
    protected=protected_snapshot(profile['replace_material'],native,cooked)
    skin_points=[];skin_faces=[]
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or obj==old:continue
        offset=len(skin_points)
        skin_points.extend(runtime_matrix(obj,vertex_weights(obj,v),native,cooked)@v.co for v in obj.data.vertices)
        skin_faces.extend(tuple(offset+i for i in p.vertices) for p in obj.data.polygons)
    skin_tree=BVHTree.FromPolygons(skin_points,skin_faces)
    native_source=profile.get('own_native_face')
    if native_source:
        ref=load_reference(Path(native_source))
        selected={i for i,(p,uv) in enumerate(zip(ref['vertices'],ref['uv']))
                  if min(uv)>=.875 and max(uv)<=1 and 165<p[2]<175 and .1<abs(p[0])<8}
        fs=[f for f in ref['faces'] if all(i in selected for i in f)]
        ids=sorted({i for f in fs for i in f});remap={i:j for j,i in enumerate(ids)}
        if len(ids)!=102 or len(fs)!=80 or any(set(ref['weights'][i])!={'sk_head'} for i in ids):
            raise ValueError('Own native eye topology is outside the supported atlas contract')
        points=[ref['vertices'][i] for i in ids];normals=[ref['normals'][i] for i in ids]
        uv=[(ref['uv'][i][0],1-ref['uv'][i][1]) for i in ids]
        faces=[tuple(remap[i] for i in f) for f in fs]
        # Native atlas V is radial, not a rectangular image of a whole eye.
        us=sorted({ref['uv'][i][0] for i in ids});vs=sorted({ref['uv'][i][1] for i in ids})
        if len(us)!=2 or len(vs)!=4:raise ValueError('Unknown native eye atlas layout')
    else:
        weights=[vertex_weights(old,v) for v in old.data.vertices]
        if any(set(w)!={'sk_head'} for w in weights):raise ValueError('Template eye must be head-bound')
        transforms=[runtime_matrix(old,w,native,cooked) for w in weights]
        points=[tuple(m@v.co) for m,v in zip(transforms,old.data.vertices)]
        uv=[None]*len(points);normals=[None]*len(points)
        for loop in old.data.loops:
            i=loop.vertex_index;value=tuple(old.data.uv_layers[0].data[loop.index].uv)
            if uv[i] is not None and uv[i]!=value:raise ValueError('Template has split vertex UVs')
            uv[i]=value
            normals[i]=tuple((transforms[i].to_3x3().inverted().transposed()@old.data.corner_normals[loop.index].vector).normalized())
        faces=[tuple(p.vertices) for p in old.data.polygons]
        # Reconstructed points are reflected from the exported FBX frame.
        if transforms[0].determinant()<0:faces=[tuple(reversed(f)) for f in faces]
        landmark=profile['template_pupil_uv']
    points=np.asarray(points);fitted=points.copy();normals=np.asarray(normals);reports=[]
    for sign,side in [(-1,'negative_x'),(1,'positive_x')]:
        ids=[i for i,p in enumerate(points) if p[0]*sign>0];mapping={i:j for j,i in enumerate(ids)}
        fs=[tuple(mapping[i] for i in f) for f in faces if all(i in mapping for i in f)]
        if not fs:raise ValueError('Missing eye hemisphere')
        pupil=(radial_atlas_pupil(points[ids],[uv[i] for i in ids]) if native_source
               else pupil_position(points[ids],[uv[i] for i in ids],fs,landmark))
        result,rotation,report=fit_socket(points[ids],pupil,guide[side])
        result,optical,pupil_after,audit=center_visible_pupil(result,fs,report['pupil_after_cm'],report['target_center_cm'],guide[side],skin_tree)
        rotation=optical@rotation;report['pupil_after_cm']=pupil_after.tolist();report['optical_alignment']=audit
        fitted[ids]=result;normals[ids]=normals[ids]@rotation.T
        reports.append(dict(side=side,vertices=len(ids),triangles=len(fs),
            pupil_landmark='radial_atlas_pole' if native_source else 'template_uv_center',**report))
    bpy.data.objects.remove(old,do_unlink=True)
    mesh=bpy.data.meshes.new('fitted_eye_geometry');mesh.from_pydata(fitted.tolist(),[],faces);mesh.update()
    obj=bpy.data.objects.new('player_fitted_eyes',mesh);bpy.context.scene.collection.objects.link(obj)
    modifier=obj.modifiers.new('Armature','ARMATURE');modifier.object=arms[0]
    obj.vertex_groups.new(name='sk_head').add(list(range(len(points))),1.,'REPLACE')
    transform=runtime_matrix(obj,{'sk_head':1.},native,cooked)
    for v,p in zip(mesh.vertices,fitted):v.co=transform.inverted()@Vector(p)
    if transform.determinant()<0:mesh.flip_normals()
    layer=mesh.uv_layers.new(name='UVMap')
    for loop in mesh.loops:layer.data[loop.index].uv=uv[loop.vertex_index]
    for polygon in mesh.polygons:polygon.use_smooth=True
    mesh.normals_split_custom_set([(transform.to_3x3().transposed()@Vector(normals[l.vertex_index])).normalized() for l in mesh.loops])
    mesh.materials.append(bpy.data.materials.new(profile['eye_material']))
    expected_uv=[tuple(v.uv) for v in mesh.uv_layers[0].data]
    topology=[tuple(p.vertices) for p in mesh.polygons]
    armature=arms[0];armature.name='Armature';armature.data.name='Armature'
    for o in bpy.context.scene.objects:o.select_set(o.type in ('MESH','ARMATURE'))
    bpy.context.view_layer.objects.active=armature
    output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output.with_suffix('.blend')))
    bpy.ops.export_scene.fbx(filepath=str(output),use_selection=True,global_scale=1.,apply_unit_scale=True,
        apply_scale_options='FBX_SCALE_UNITS',use_space_transform=True,bake_space_transform=False,
        object_types={'ARMATURE','MESH'},mesh_smooth_type='FACE',use_tspace=True,add_leaf_bones=False,
        primary_bone_axis='Y',secondary_bone_axis='X',use_armature_deform_only=False,
        armature_nodetype='NULL',bake_anim=False,path_mode='COPY',embed_textures=True,axis_forward='-Y',axis_up='Z')
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=.01
    bpy.ops.import_scene.fbx(filepath=str(output),use_anim=False)
    obj=next(o for o in bpy.context.scene.objects if o.type=='MESH' and profile['eye_material'] in [m.name for m in o.data.materials])
    actual=np.asarray([tuple(runtime_matrix(obj,vertex_weights(obj,v),native,cooked)@v.co) for v in obj.data.vertices])
    drift=float(np.max(np.linalg.norm(actual-fitted,axis=1)))
    if drift>.001 or [tuple(p.vertices) for p in obj.data.polygons]!=topology:
        raise ValueError('Eye round-trip geometry changed')
    uv_drift=max(abs(a-b) for old,new in zip(expected_uv,obj.data.uv_layers[0].data) for a,b in zip(old,new.uv))
    if uv_drift>1e-6:raise ValueError('Eye UV changed during round-trip')
    protection=verify_protected(protected,protected_snapshot(profile['eye_material'],native,cooked))
    report=dict(base_id=profile['base_id'],source_policy=profile['source_policy'],eyes=reports,
                position_roundtrip_drift_cm=drift,uv_roundtrip_drift=uv_drift,
                vertices=len(points),triangles=len(faces),protected_meshes=protection,
                source_normal_repairs=normal_repairs,hardware_accepted=False)
    output.with_suffix('.eyes.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',type=Path,required=True)
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:]);fit(json.loads(args.profile.read_text(encoding='utf-8')))
