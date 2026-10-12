"""Blender fixture: empty hair conversion is bounded, rigid and nondegenerate."""
import bpy,json,sys
from pathlib import Path
from mathutils import Matrix
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'tools'))
from blender_realface_empty_hair import ensure_hair_slot
from blender_fit_realface import runtime_matrix,vertex_weights
from blender_export_ue_fbx import rig_globals
w=root/'local-debug/league-realfaces-v23/empty-hair-canary';w.mkdir(parents=True,exist_ok=True)
rig=[dict(name='sk_head',parent=-1,trs=[0,0,0,1,0,0,0,1,1,1])]
(w/'rig.json').write_text(json.dumps(rig))
p=dict(native_rig=str(w/'rig.json'),cooked_rig=str(w/'rig.json'),hair_skin_materials=[])
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=.01
arm=bpy.data.armatures.new('Armature');obj=bpy.data.objects.new('Armature',arm)
bpy.context.scene.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
bpy.ops.object.mode_set(mode='EDIT');bone=arm.edit_bones.new('sk_head');bone.head=(0,0,0);bone.tail=(0,0,1);bpy.ops.object.mode_set(mode='OBJECT')
mesh=bpy.data.meshes.new('source');mesh.from_pydata([(0,0,170)]*3,[],[(0,1,2)]);mesh.update()
hair=bpy.data.objects.new('source',mesh);bpy.context.scene.collection.objects.link(hair)
mesh.materials.append(bpy.data.materials.new('rf_hair'))
hair.vertex_groups.new(name='sk_head').add([0,1,2],1.,'REPLACE')
mod=hair.modifiers.new('Armature','ARMATURE');mod.object=obj
mesh.vertices[2].co.x=.01;mesh.update()
assert ensure_hair_slot(dict(p,hair_skin_materials=['rf_skin']),w/'scalp.fbx') is None
mesh.vertices[2].co.x=0;mesh.update()
audit=ensure_hair_slot(p,w/'empty.fbx');assert audit['source_extent_cm']==[0,0,0]
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=.01
bpy.ops.import_scene.fbx(filepath=str(w/'empty.fbx'),use_anim=False)
hair=next(o for o in bpy.context.scene.objects if o.type=='MESH');hair.data.calc_loop_triangles()
assert len(hair.data.loop_triangles)==1 and hair.data.loop_triangles[0].area>1e-6
assert [m.name for m in hair.data.materials]==['rf_hair_empty']
native=rig_globals(rig)
pts=[runtime_matrix(hair,vertex_weights(hair,v),native,native)@v.co for v in hair.data.vertices]
assert all(abs(v.z-174)<.001 and abs(v.x)<.051 and abs(v.y-4)<.051 for v in pts)
assert ensure_hair_slot(p,w/'not-empty.fbx') is None
print('Empty hair: exact empty source only; native rig, material, and renderable triangle verified')
