"""Offline native-style scalp undercoat + untouched source detail cards.

Investigation only: produces reviewable candidates, never an active patch.
Facial anatomy is preserved; the optional opaque scalp base is appended to
the same section. Source detail cards are selected, never collapsed.
"""
import json
from pathlib import Path
import shutil
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals
from blender_fit_realface import vertex_weights,runtime_matrix
from blender_realface_lite import count
from blender_realface_mobile import geometry,pixels,sample_tile
from blender_realface_face_rebake import sample
from realface_native_hair_cards import select_cards,scalp_triangles,opaque_atlas_slot,fit_bulk
from realface_mobile_geometry import audit,compare


def export_only(path,arm,objects):
    # The standard single-part exporter selects the entire scene. This
    # experiment holds both sections and two imported rigs temporarily.
    bpy.ops.object.select_all(action='DESELECT')
    for obj in (arm,*objects):obj.select_set(True)
    bpy.context.view_layer.objects.active=arm
    # UE4.22 recognizes the standard Armature wrapper. A second imported rig
    # named Armature.001 otherwise becomes an extra root bone in the cook.
    previous=arm.name;other=bpy.data.objects.get('Armature')
    if other is arm:other=None
    other_name=other.name if other else None
    if other:other.name='PESNX_temporary_other_rig'
    previous_data=arm.data.name;other_data=bpy.data.armatures.get('Armature')
    if other_data is arm.data:other_data=None
    other_data_name=other_data.name if other_data else None
    if other_data:other_data.name='PESNX_temporary_other_rig_data'
    arm.name='Armature'
    arm.data.name='Armature'
    try:
        bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,
            global_scale=1.,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',
            use_space_transform=True,bake_space_transform=False,
            object_types={'ARMATURE','MESH'},mesh_smooth_type='FACE',use_tspace=True,
            add_leaf_bones=False,primary_bone_axis='Y',secondary_bone_axis='X',
            use_armature_deform_only=False,armature_nodetype='NULL',bake_anim=False,
            path_mode='ABSOLUTE',embed_textures=False,axis_forward='-Y',axis_up='Z')
    finally:
        arm.name=previous
        if other:other.name=other_name
        arm.data.name=previous_data
        if other_data:other_data.name=other_data_name


def paint_undercoat(source,texture,base,output):
    """Project only this player's alpha-visible hair onto the existing skin UV.

    Scalp projects along bounded head rays; short facial hair uses a much
    smaller distance. No nearest-colour flood, generic fill or donor hairstyle.
    """
    p,t,uv=source
    area=np.linalg.norm(np.cross(p[t[:,1]]-p[t[:,0]],p[t[:,2]]-p[t[:,0]]),axis=1)
    live=area>1e-6;t=t[live];uv=uv[live]
    tree=BVHTree.FromPolygons([Vector(q) for q in p],t.tolist(),all_triangles=True)
    request=json.loads((base/'lite_skin-meshopt.json').read_text())
    skin=np.asarray(request['positions']).reshape(-1,3)
    faces=np.asarray(json.loads((base/'lite_skin-meshopt-result.json').read_text())['indices']).reshape(-1,3)
    coords=np.asarray(request['uv']).reshape(-1,2)
    atlas=pixels(str((base/'opaque-atlas.png').resolve())).copy();original=atlas.copy()
    tile=json.loads((base/'atlas-proof.json').read_text())['tiles']['skin']
    start,end=np.asarray(tile['destination_bounds']);lower,upper=np.asarray(tile['source_bounds'])
    depth=np.full(atlas.shape[:2],-np.inf);painted=np.zeros(atlas.shape[:2],bool);maximum=0.
    hits_by_region={'scalp':0,'short_facial_hair':0}
    for tri in faces:
        vertex=skin[tri]
        xy=start+(coords[tri]-lower)/(upper-lower)*(end-start)-.5
        lo=np.maximum(np.ceil(xy.min(axis=0)).astype(int),start)
        hi=np.minimum(np.floor(xy.max(axis=0)).astype(int),end-1)
        a,b,c=xy;den=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        if abs(den)<1e-8:continue
        for y in range(lo[1],hi[1]+1):
            for x in range(lo[0],hi[0]+1):
                d=np.array([x,y])-a
                v=(d[0]*(c[1]-a[1])-d[1]*(c[0]-a[0]))/den
                w=((b[0]-a[0])*d[1]-(b[1]-a[1])*d[0])/den
                bary=np.array([1-v-w,v,w])
                if min(bary)<-1e-6:continue
                point=bary@vertex
                # Exclude the torso and ears. A forehead ray can paint only
                # where original visible hair actually crosses that ray.
                if point[1]<depth[y,x] or abs(point[0])>9.2 or point[2]<155:continue
                scalp=point[2]>174 or (point[1]<3 and point[2]>166)
                if scalp:center=np.array([0.,4.,173.]);reach=3.;region='scalp'
                elif point[1]>5 and point[2]<174:
                    center=np.array([0.,1.,164.5]);reach=.67;region='short_facial_hair'
                else:continue
                direction=Vector(point-center)
                if direction.length<1e-5:continue
                direction.normalize();origin=Vector(point)+direction*reach
                for _ in range(64):
                    remaining=(origin-Vector(point)).dot(direction)
                    if remaining<=.005:break
                    hit,normal,index,_=tree.ray_cast(origin,-direction,remaining)
                    if index is None:break
                    aa,bb,cc=p[t[index]];e0=bb-aa;e1=cc-aa;e2=np.asarray(hit)-aa
                    d00=e0@e0;d01=e0@e1;d11=e1@e1;det=d00*d11-d01*d01
                    if abs(det)>1e-12:
                        v0=(d11*(e2@e0)-d01*(e2@e1))/det
                        v1=(d00*(e2@e1)-d01*(e2@e0))/det
                        color=sample(texture,np.array([1-v0-v1,v0,v1])@uv[index])
                        if color[3]>=.3333:
                            atlas[y,x,:3]=color[:3];painted[y,x]=True;depth[y,x]=point[1]
                            maximum=max(maximum,float((hit-Vector(point)).length))
                            hits_by_region[region]+=1;break
                    origin=hit-direction*.003
    atlas[:,:,3]=1.
    image=bpy.data.images.new('native_style_opaque_undercoat',atlas.shape[1],atlas.shape[0],alpha=False)
    image.pixels.foreach_set(atlas.ravel());image.filepath_raw=str(output);image.file_format='PNG';image.save()
    # The eye tile is outside every painted texel. This assertion also guards
    # accidental generic filling or changes to unprojected facial features.
    if not np.array_equal(atlas[~painted],original[~painted]):
        raise ValueError('Undercoat changed an unprojected atlas texel')
    return dict(painted_texels=int(painted.sum()),region_hits=hits_by_region,max_projection_cm=maximum,
        scalp_maximum_cm=3.,facial_hair_maximum_cm=.67,opaque=True,geometry_changed=False,
        original_eye_and_unprojected_texels_unchanged=True,visual_approval=False)


def subset(obj,selected,source,local,normals,weights):
    chosen=source[1][selected];used=np.unique(chosen);mapping={int(v):i for i,v in enumerate(used)}
    mesh=bpy.data.meshes.new('untouched_source_card_subset')
    mesh.from_pydata([local[int(i)] for i in used],[],[[mapping[int(i)] for i in t] for t in chosen])
    mesh.update();layer=mesh.uv_layers.new(name='UVMap')
    for poly,uv in zip(mesh.polygons,source[2][selected]):
        poly.use_smooth=True
        for li,value in zip(poly.loop_indices,uv):layer.data[li].uv=value
    obj.data=mesh;obj.vertex_groups.clear()
    for name in sorted({name for i in used for name in weights[int(i)]}):obj.vertex_groups.new(name=name)
    for i,old_i in enumerate(used):
        for name,value in weights[int(old_i)].items():obj.vertex_groups[name].add([i],value,'REPLACE')
    mesh.normals_split_custom_set(normals[selected].reshape(-1,3))
    mesh.materials.append(bpy.data.materials.get('lite_hair') or bpy.data.materials.new('lite_hair'))
    return obj


def triangle_records(data,weights):
    p,t,uv=data
    return [dict(points=p[face].tolist(),uv=coords.tolist(),weights=[weights[int(i)] for i in face])
            for face,coords in zip(t,uv)]


def clean_generated_base(obj,native,cooked):
    """Remove only invisible slivers created in our new opaque bulk mesh."""
    import realface_mobile_geometry as gm
    data=geometry(obj,native,cooked);p,t,uv=data
    area=np.linalg.norm(np.cross(p[t[:,1]]-p[t[:,0]],p[t[:,2]]-p[t[:,0]]),axis=1)
    discarded=set(np.flatnonzero(area<1e-4).tolist());duplicate_count=0;seen={}
    cross=np.cross(p[t[:,1]]-p[t[:,0]],p[t[:,2]]-p[t[:,0]])
    radial=p[t].mean(axis=1)-[0,4,173]
    orientation=np.sign(np.median(np.sum(cross*radial,axis=1))) or 1
    for index,face in enumerate(t):
        if index in discarded:continue
        key=tuple(sorted(tuple(point) for point in np.round(p[face],5)))
        if key not in seen:seen[key]=index;continue
        previous=seen[key]
        score=lambda i:float(np.dot(cross[i],radial[i]))*orientation
        if score(index)>score(previous):discarded.add(previous);seen[key]=index
        else:discarded.add(index)
        duplicate_count+=1
    discard=np.asarray(sorted(discarded),dtype=int)
    proof=dict(removed_triangles=0,duplicate_triangles=duplicate_count,views=0,source_face_touched=False)
    if not len(discard):return proof
    keep=np.asarray(sorted(set(range(len(t)))-discarded),dtype=int)
    for basis in gm.views():
        before=gm.raster(p,t,uv,np.ones((1,1)),basis,size=128)
        after=gm.raster(p,t[keep],uv[keep],np.ones((1,1)),basis,before['bounds'],size=128)
        mask=before['mask']
        if not np.array_equal(mask,after['mask']) or np.max(np.abs(before['depth'][mask]-after['depth'][mask]),initial=0)>1e-5:
            raise ValueError('Generated hair sliver is visible; retain the held source')
        proof['views']+=1
    local=[v.co[:] for v in obj.data.vertices]
    normals=np.asarray([[obj.data.corner_normals[i].vector[:] for i in tri.loops] for tri in obj.data.loop_triangles])
    weights=[vertex_weights(obj,v) for v in obj.data.vertices]
    subset(obj,keep,data,local,normals,weights)
    proof.update(removed_triangles=len(discard),maximum_area_cm2=float(area[discard].max()),
                 maximum_visibility_depth_difference_cm=1e-5)
    return proof


def opaque_base(obj,source,local,normals,weights,job,native,cooked):
    """Put the source-derived hair bulk in the existing opaque face section."""
    from blender_realface_hair_volume import prepare
    from blender_realface_source_quality import transfer_normals,capture_normals
    from blender_realface_native_hair_detail import detail,fresh_pixels
    folder=Path(job['folder']);scalp=scalp_triangles(source[0],source[1])
    selected=np.flatnonzero(scalp)
    if not len(selected):raise ValueError('No source scalp for an opaque native-style base')
    base=obj.copy();bpy.context.collection.objects.link(base)
    subset(base,selected,source,local,normals,weights)
    scalp_source=geometry(base,native,cooked)
    scalp_normals=capture_normals(base,native,cooked)[2]
    requested=int(job['opaque_base_triangles'])
    budget=min(requested,int(job['hair_budget'])-64)
    if budget<100:raise ValueError('No bounded opaque scalp/detail-card remainder after face')
    if job.get('base_mode')=='source_surface':
        # Native opaque bulk can follow the source's existing clump contours.
        # Closing/remeshing every clump first can flatten those contours into
        # a dome even while a silhouette test passes.
        from blender_realface_hair_reduce import reduce
        reduce(base,scalp_source[0],budget-6,native,cooked)
        proof=dict(mode='source_scalp_surface_collapse',source_triangles=len(scalp_source[1]),
                   budget=budget,source_shading_preserved=True,voxel_remesh=False)
        shade=transfer_normals(base,native,cooked,(scalp_source[0],scalp_source[1],scalp_normals))
    else:
        volume_job=dict(job,budgets=dict(hair=budget,volume_closing_steps=3))
        import blender_realface_hair_volume as volume
        closing=int(job.get('closing_steps',3))
        original_neighbours=volume.neighbours;calls={True:0,False:0}
        def bounded_closing(array,dilate):
            calls[dilate]+=1
            # Preserve the generator's first sampling dilation, then bound
            # closing separately. The shared v38 recipe remains unchanged.
            limit=closing+1 if dilate else closing
            return original_neighbours(array,dilate) if calls[dilate]<=limit else array
        volume.neighbours=bounded_closing
        try:before,alpha,removed,proof=prepare(base,volume_job,native,cooked)
        finally:volume.neighbours=original_neighbours
        proof['closing_steps']=closing
        shade=transfer_normals(base,native,cooked,volume.LAST_SURFACE)
    if count(base)>budget:raise ValueError('Opaque source scalp exceeds its complete-head allocation')
    request=json.loads((Path(job['face_folder'])/'lite_skin-meshopt.json').read_text())
    skin=np.asarray(request['positions']).reshape(-1,3)
    faces=np.asarray(json.loads((Path(job['face_folder'])/'lite_skin-meshopt-result.json').read_text())['indices']).reshape(-1,3)
    positions,triangles,_=geometry(base,native,cooked)
    fitted,fit_proof=fit_bulk(positions,triangles,source,pixels(str(folder/'hair-cards.png')),
                             (skin,faces),int(job['hair_budget'])-count(base))
    for vertex,point in zip(base.data.vertices,fitted):
        vertex.co=runtime_matrix(base,vertex_weights(base,vertex),native,cooked).inverted()@Vector(point)
    proof['bounded_source_envelope_fit']=fit_proof
    cleanup=clean_generated_base(base,native,cooked)
    (folder/'generated-base-cleanup.json').write_text(json.dumps(cleanup,indent=2))
    colour_detail=detail(base,scalp_source,pixels(job['source_profile']['hair_texture']),
                         scalp_normals,native,cooked,folder)
    if job.get('colour_mode')=='cycles_relief':
        from blender_realface_native_hair_bake import relief
        colour_detail['source_self_shadow']=relief(base,scalp_source,job['source_profile']['hair_texture'],
                                                   scalp_normals,native,cooked,folder)
    atlas=fresh_pixels(folder/'opaque-atlas.png')
    base_texture=fresh_pixels(folder/'hair-shell.png')
    size=atlas.shape[0]
    if atlas.shape[1]!=size:raise ValueError('Native opaque atlas must be square')
    # This slot is outside both the existing skin and eye tiles. Two-pixel
    # borders are extruded within the free atlas area for linear sampling.
    occupied=json.loads((Path(job['face_folder'])/'atlas-proof.json').read_text())['tiles']
    destination=opaque_atlas_slot(size,occupied)
    sample_tile(base_texture,[[0,0],[1,1]],destination,atlas);atlas[:,:,3]=1.
    image=bpy.data.images.new('face_with_opaque_hair_bulk',size,size,alpha=False)
    image.pixels.foreach_set(atlas.ravel());image.filepath_raw=str(folder/'opaque-atlas.png')
    image.file_format='PNG';image.save()
    for value in base.data.uv_layers[0].data:value.uv=(destination[0]+np.asarray(value.uv)*(destination[1]-destination[0]))/size
    base_count=count(base)
    # Import the original prepared skin/eyes and append only the scalp base.
    existing=set(bpy.context.scene.objects)
    bpy.ops.import_scene.fbx(filepath=str(folder/'face.fbx'),use_anim=False)
    imported=set(bpy.context.scene.objects)-existing
    faces=[o for o in imported if o.type=='MESH']
    if len(faces)!=1:raise ValueError('Opaque native-style merge expects one prepared face section')
    face=faces[0];face_arm=next(o for o in imported if o.type=='ARMATURE')
    old_geometry=geometry(face,native,cooked)
    base_before=geometry(base,native,cooked)[0]
    matrix=base.matrix_world.copy();base.parent=face_arm;base.matrix_world=matrix
    for modifier in base.modifiers:
        if modifier.type=='ARMATURE':modifier.object=face_arm
    if not np.allclose(geometry(base,native,cooked)[0],base_before,atol=.0002):
        raise ValueError('Opaque base changed bind-space position during face merge')
    material=face.data.materials[0];base.data.materials.clear();base.data.materials.append(material)
    for poly in base.data.polygons:poly.material_index=0
    bpy.ops.object.select_all(action='DESELECT');face.select_set(True);base.select_set(True)
    bpy.context.view_layer.objects.active=face;bpy.ops.object.join()
    merged=geometry(face,native,cooked)
    if not np.allclose(old_geometry[0],merged[0][:len(old_geometry[0])],atol=.0002):
        raise ValueError('Face vertices changed while appending the native-style hair base')
    if not np.array_equal(old_geometry[1],merged[1][:len(old_geometry[1])]):
        raise ValueError('Facial topology changed while appending the scalp base')
    if not np.allclose(old_geometry[2],merged[2][:len(old_geometry[2])],atol=1e-6):
        raise ValueError('Facial UVs changed while appending the scalp base')
    # Export the audited triangles explicitly. Leaving a quad/n-gon in the
    # merged part lets FBX choose another diagonal or omit a thin corner.
    local_face=[v.co[:] for v in face.data.vertices]
    face_normals=np.asarray([[face.data.corner_normals[i].vector[:] for i in tri.loops]
                            for tri in face.data.loop_triangles])
    face_weights=[vertex_weights(face,v) for v in face.data.vertices]
    subset(face,np.arange(len(merged[1])),merged,local_face,face_normals,face_weights)
    face.data.materials.clear();face.data.materials.append(material)
    face_reference=triangle_records(geometry(face,native,cooked),[vertex_weights(face,v) for v in face.data.vertices])
    export_only(folder/'face.fbx',face_arm,[face])
    return base_count,dict(triangles=base_count,source_face_triangles=len(old_geometry[1]),
        requested_maximum=requested,effective_budget=budget,
        minimum_reserved_detail_cards=64,atlas_bounds=destination.tolist(),volume=proof,
        smooth_shading=shade,generated_sliver_cleanup=cleanup,colour_detail=colour_detail,
        original_face_vertices_topology_uv_unchanged=True,
        integrated_in_opaque_face_section=True),(base_before,merged[1][len(old_geometry[1]):]-len(old_geometry[0])),\
        face_reference


def roundtrip(path,native,cooked,expected,material,reference=None):
    """Catch duplicated sections/rigs and name/binding changes in actual FBX."""
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=.01
    bpy.ops.import_scene.fbx(filepath=str(path),use_anim=False)
    arms=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
    if len(arms)!=1 or len(meshes)!=1 or set(b.name for b in arms[0].data.bones)!=set(native):
        raise ValueError('Exported native-style part has duplicate/mismatched sections or rig')
    obj=meshes[0]
    actual=count(obj)
    if actual>expected or (actual!=expected and reference is None) or [m.name for m in obj.data.materials]!=[material]:
        raise ValueError('Exported native-style triangle/material count differs from proof: '+
            json.dumps(dict(part=path.name,expected_triangles=expected,actual_triangles=count(obj),
                            expected_material=material,actual_materials=[m.name for m in obj.data.materials])))
    data=geometry(obj,native,cooked)
    if not np.isfinite(data[0]).all() or not np.isfinite(data[2]).all():
        raise ValueError('Non-finite native-style exported geometry/UV')
    for vertex in obj.data.vertices:
        w=vertex_weights(obj,vertex)
        if not w or abs(sum(w.values())-1)>.01:raise ValueError('Exported native-style weights changed')
    connectivity=None
    if actual!=expected:
        from realface_triangle_audit import surviving_triangles
        connectivity=surviving_triangles(reference,
            triangle_records(data,[vertex_weights(obj,v) for v in obj.data.vertices]),position_limit=.002)
    return dict(triangles=actual,allocated_triangles=expected,exact_collapsed_triangles=expected-actual,
                surviving_connectivity=connectivity,sections=1,bones=len(native),material=material,
                bounds_cm=[data[0].min(axis=0).tolist(),data[0].max(axis=0).tolist()])


def run(job):
    folder=Path(job['folder']);base=Path(job['face_folder'])
    native,cooked=(rig_globals(json.loads(Path(job[k]).read_text())) for k in ('native_rig','cooked_rig'))
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=.01
    copied=folder/'input-hair.fbx';shutil.copy2(job['source_profile']['hair_fbx'],copied)
    bpy.ops.import_scene.fbx(filepath=str(copied),use_anim=False)
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    if len(objects)>1:bpy.ops.object.join()
    obj=bpy.context.object;source=geometry(obj,native,cooked)
    weights=[vertex_weights(obj,v) for v in obj.data.vertices]
    if any(not w or set(w)-{'sk_head','sk_neck','sk_chest'} for w in weights):
        raise ValueError('Source card binding is outside the audited head/neck chain')
    normals=np.asarray([[obj.data.corner_normals[i].vector[:] for i in tri.loops] for tri in obj.data.loop_triangles])
    local=[v.co[:] for v in obj.data.vertices]
    original=pixels(job['source_profile']['hair_texture'])
    paint=paint_undercoat(source,original,base,folder/'opaque-atlas.png')
    texture=pixels(str(folder/'hair-cards.png'))
    # Score only alpha-visible original surfaces in front of the actual skin.
    request=json.loads((base/'lite_skin-meshopt.json').read_text())
    skin=np.asarray(request['positions']).reshape(-1,3)
    faces=np.asarray(json.loads((base/'lite_skin-meshopt-result.json').read_text())['indices']).reshape(-1,3)
    if job.get('fast_raster'):
        from realface_fast_raster import load
        import realface_mobile_geometry
        realface_mobile_geometry.raster=load(job['fast_raster'])
    base_count,base_proof,base_geometry,face_reference=(opaque_base(obj,source,local,normals,weights,job,native,cooked)
                           if job.get('opaque_base_triangles') else (0,None,None,None))
    before,_=audit(*source,texture[:,:,3],skin=(skin,faces))
    # Facial hair belongs to the painted opaque face, matching the native
    # construction. Keep optional detail cards above the brow or behind it.
    details=None
    if base_count:
        details=scalp_triangles(source[0],source[1])
        for frame in before:
            visible=frame['front']>=0
            discard=visible.copy();discard[visible]=~details[frame['front'][visible]]
            frame['front'][discard]=-1;frame['mask']=frame['front']>=0
    selected,proof=select_cards(source[1],before,int(job['hair_budget'])-base_count,details)
    if not len(selected):raise ValueError('No visible native-style detail cards selected')
    subset(obj,selected,source,local,normals,weights)
    after,_=audit(*geometry(obj,native,cooked),texture[:,:,3],reference=before)
    projection=compare(before,after)
    composite=projection
    if base_count:
        # Compare the new opaque bulk AND sparse cards together. Hair-only
        # masks cannot represent a native opaque scalp contribution.
        from realface_mobile_geometry import views
        import realface_mobile_geometry as gm
        old_scalp,_=audit(source[0],source[1][details],source[2][details],texture[:,:,3],skin=(skin,faces))
        detail_frames,_=audit(*geometry(obj,native,cooked),texture[:,:,3],reference=old_scalp)
        bp,bt=base_geometry;combined=[]
        for basis,reference,card in zip(views(),old_scalp,detail_frames):
            bulk=gm.raster(bp,bt,np.zeros((len(bt),3,2)),np.ones((1,1)),basis,
                           reference['bounds'],skin_depth=reference['skin_depth'])
            merged=dict(card,mask=card['mask']|bulk['mask'],cards=card['cards']+bulk['cards'],
                        opaque=card['opaque']+bulk['opaque'])
            combined.append(merged)
        composite=compare(old_scalp,combined)
    export_only(folder/'hair.fbx',next(m.object for m in obj.modifiers if m.type=='ARMATURE'),[obj])
    face_count=base_proof['source_face_triangles'] if base_count else job['face_triangles']
    total=face_count+base_count+len(selected)
    if not 0<total<=2000:raise ValueError('Complete head exceeds 2000 triangles')
    face_material=json.loads((base/'ue-profile.json').read_text())['skin_materials']
    if len(face_material)!=1:raise ValueError('Native-style opaque face needs one material')
    reimport=dict(face=roundtrip(folder/'face.fbx',native,cooked,face_count+base_count,face_material[0],face_reference),
                  hair=roundtrip(folder/'hair.fbx',native,cooked,len(selected),'lite_hair'))
    total=sum(part['triangles'] for part in reimport.values())
    (folder/'native-hair-proof.json').write_text(json.dumps(dict(base_id=job['base_id'],
        native_player_id=job['native_player_id'],face_triangles=reimport['face']['triangles'],hair_triangles=reimport['hair']['triangles'],
        total_triangles=total,sections=2,undercoat=paint,cards=proof,hair_only_projection=projection,
        original_face_fbx_unchanged=not base_count,hair_texture_size=128,opaque_base=base_proof,
        composite_scalp_projection=composite,
        exported_fbx_reimport=reimport,
        method='native_style_opaque_undercoat_and_original_masked_cards',
        visual_approval=False,hardware_profiled=False),indent=2)+'\n')


if __name__=='__main__':run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text()))
