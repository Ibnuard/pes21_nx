"""Move an explicitly skin-only source hair slot into the opaque face section.

Every source skin triangle is retained before mobile reduction. The now empty
hair slot gets a transparent engine placeholder; no visible scalp is removed.
"""
import json
from pathlib import Path
import shutil
import sys

import bpy
from mathutils import Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals, rebuild_smooth_normals
from blender_fit_realface import runtime_matrix
from blender_realface_lite import export, normalized, points


def run(job):
    profile=job['profile'];folder=Path(job['folder']);folder.mkdir(parents=True,exist_ok=True)
    if profile['hair_materials'] or not profile['hair_skin_materials']:
        raise ValueError('Repartition requires an explicitly skin-only hair source')
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=.01
    native,cooked=(rig_globals(json.loads(Path(job[n]).read_text())) for n in ('native_rig','cooked_rig'))
    for part in ('face','hair'):
        path=folder/('input-'+part+'.fbx');shutil.copy2(profile[part+'_fbx'],path)
        bpy.ops.import_scene.fbx(filepath=str(path),use_anim=False)
        if part=='face':
            arm=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
            existing=set(bpy.context.scene.objects)
    extra=[o for o in bpy.context.scene.objects if o not in existing]
    other=next(o for o in extra if o.type=='ARMATURE')
    if (set(b.name for b in arm.data.bones)!=set(native) or
            set(b.name for b in other.data.bones)!=set(native) or
            max(abs(arm.matrix_world[i][j]-other.matrix_world[i][j]) for i in range(4) for j in range(4))>1e-5 or
            any(max(abs(b.matrix_local[i][j]-other.data.bones[b.name].matrix_local[i][j])
                    for i in range(4) for j in range(4))>.005 for b in arm.data.bones)):
        raise ValueError('Skin-only slots use different native bind frames')
    meshes=[o for o in extra if o.type=='MESH'];before={}
    for obj in meshes:
        # Blender suffixes imported duplicate names; this source has no hair
        # material, so every imported mesh must be from the verified skin slot.
        if any(not normalized(m.name).startswith('rf_skin') for m in obj.data.materials):
            raise ValueError('Unexpected non-skin geometry')
        before[obj.name]=points(obj,native,cooked)
        world=obj.matrix_world.copy();obj.parent=arm;obj.matrix_world=world
        for modifier in obj.modifiers:
            if modifier.type=='ARMATURE':modifier.object=arm
        obj.data.calc_loop_triangles()
    bpy.data.objects.remove(other,do_unlink=True)
    maximum=0.
    for obj in meshes:
        after=points(obj,native,cooked)
        maximum=max(maximum,max((a-b).length for a,b in zip(before[obj.name],after)))
    if maximum>1e-4:raise ValueError('Repartition moved native skin vertices')
    materials=sorted({m.name for obj in bpy.context.scene.objects if obj.type=='MESH' for m in obj.data.materials
                      if m.name!=profile['eye_material']})
    export(folder/'face.fbx',arm)
    count=sum(len(o.data.loop_triangles) for o in meshes)
    for obj in list(bpy.context.scene.objects):
        if obj.type=='MESH':bpy.data.objects.remove(obj,do_unlink=True)
    mesh=bpy.data.meshes.new('empty_mobile_hair');mesh.from_pydata([(0,0,0)]*3,[],[(0,1,2)]);mesh.update()
    obj=bpy.data.objects.new('empty_mobile_hair',mesh);bpy.context.scene.collection.objects.link(obj)
    obj.vertex_groups.new(name='sk_head').add([0,1,2],1.,'REPLACE')
    modifier=obj.modifiers.new('Armature','ARMATURE');modifier.object=arm
    matrix=runtime_matrix(obj,{'sk_head':1.},native,cooked)
    desired=[Vector((0,4,174)),Vector((.05,4,174)),Vector((0,4.05,174))]
    for vertex,p in zip(mesh.vertices,desired):vertex.co=matrix.inverted()@p
    if matrix.determinant()<0:mesh.flip_normals()
    uv=mesh.uv_layers.new(name='UVMap')
    for loop in uv.data:loop.uv=(.5,.5)
    mesh.materials.append(bpy.data.materials.new('rf_hair_empty'));rebuild_smooth_normals(obj)
    export(folder/'hair.fbx',arm)
    image=bpy.data.images.new('empty_hair',width=128,height=128,alpha=True);image.alpha_mode='CHANNEL_PACKED'
    image.pixels[:]=[0.]*(128*128*4);image.filepath_raw=str(folder/'empty-hair.png');image.file_format='PNG';image.save()
    out=dict(profile,face_fbx=str(folder/'face.fbx'),hair_fbx=str(folder/'hair.fbx'),
        skin_materials=materials,hair_materials=['rf_hair_empty'],hair_skin_materials=[],
        hair_texture=str(folder/'empty-hair.png'),hair_texture_size=128,
        empty_hair_slot=dict(policy='all_source_skin_transferred_to_face'))
    (folder/'ue-profile.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
    (folder/'partition-proof.json').write_text(json.dumps(dict(source_skin_triangles_moved=count,
        source_skin_vertices_max_displacement_cm=maximum,masked_placeholder_triangles=1,
        source_profile=job['source_profile_path']),indent=2),encoding='utf-8')


if __name__=='__main__':run(json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text(encoding='utf-8')))
