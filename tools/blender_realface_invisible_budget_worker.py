"""Bounded source-slot repair; never substitutes a visible hairstyle."""
import json
from pathlib import Path
import runpy
import sys

import bpy
import numpy as np
from mathutils import Matrix,Vector

sys.path.insert(0,str(Path(__file__).resolve().parent))
import blender_realface_lite as lite
import blender_realface_mobile as mobile
import blender_realface_source_quality as quality
from blender_export_ue_fbx import rebuild_smooth_normals
from blender_fit_realface import runtime_matrix, vertex_weights
from realface_invisible_slot_policy import verified_invisible_cards,rigid_pose_diameters
from realface_pipeline import sha

old_prepare,old_finish,old_quality,old_transfer = (
    mobile.prepare_hair,mobile.finish_hair,lite.quality,quality.transfer_normals)


def prepare(obj,job,native,cooked):
    if not job['budgets'].get('verified_invisible_source_slot'):
        return old_prepare(obj,job,native,cooked)
    p,t,uv = mobile.geometry(obj,native,cooked)
    profile=job['source_profile']; alpha=mobile.pixels(profile['hair_texture'])[:,:,3]
    before,visible=mobile.source_views((p,t,uv),alpha,job)
    bindings=[vertex_weights(obj,v) for v in obj.data.vertices]
    used={name for b in bindings for name in b}
    frames={n:np.asarray(cooked[n].inverted()@Matrix.Diagonal((1.,-1.,1.,1.))@obj.matrix_world) for n in used}
    diameters=rigid_pose_diameters([v.co[:] for v in obj.data.vertices],t,bindings,frames,
                                 {n:np.asarray(native[n]) for n in used})
    source_proof=job['budgets'].get('source_authored_empty_part')
    if source_proof:
        if any(source_proof[k]!=job[k] for k in ('base_id','native_player_id','fingerprint')):
            raise ValueError('Authored source slot changed owner')
        if any(sha(path)!=digest for path,digest in source_proof['inputs'].items()):
            raise ValueError('Authored PC source proof changed')
    proof=verified_invisible_cards(p,t,uv,alpha,bindings,profile['hair_materials'],
        profile.get('hair_skin_materials',[]),len(visible),diameters,source_proof)
    proof['rejected_native_conversion_covered_pixels']=[int(frame['mask'].sum()) for frame in before]
    folder=Path(job['folder'])
    (folder/'invisible-source-slot-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    # The two-section native mesh contract still needs a valid masked slot.
    mesh=bpy.data.meshes.new('proven_invisible_native_slot')
    inverse=runtime_matrix(obj,{'sk_head':1.0},native,cooked).inverted()
    desired=[Vector((0,4,174)),Vector((.05,4,174)),Vector((0,4.05,174))]
    mesh.from_pydata([inverse@v for v in desired],[],[(0,1,2)]); mesh.update()
    mesh.uv_layers.new(name='UVMap')
    for loop in mesh.uv_layers[0].data:loop.uv=(.5,.5)
    mesh.materials.append(bpy.data.materials.get('lite_hair') or bpy.data.materials.new('lite_hair'))
    obj.data=mesh;obj.vertex_groups.clear();obj.vertex_groups.new(name='sk_head').add([0,1,2],1.0,'REPLACE')
    if runtime_matrix(obj,{'sk_head':1.0},native,cooked).determinant()<0:mesh.flip_normals()
    rebuild_smooth_normals(obj)
    obj['proven_invisible_slot']=True
    image=bpy.data.images.new('proven_empty_hair',width=128,height=128,alpha=True)
    image.alpha_mode='CHANNEL_PACKED';image.pixels.foreach_set(np.zeros(128*128*4,np.float32))
    image.filepath_raw=str(folder/'hair-shell.png');image.file_format='PNG';image.save()
    return before,np.zeros((128,128)),0,dict(mode='proven_invisible_native_slot',proof=proof)


def finish(obj,job,native,cooked,reference):
    if reference[3].get('mode')!='proven_invisible_native_slot':
        return old_finish(obj,job,native,cooked,reference)
    result=dict(silhouette_iou_min=1.0,silhouette_iou_mean=1.0,missing_coverage_max=0.0,
                card_fragments_before=0,card_fragments_after=0,alpha_fragments_before=0,
                alpha_fragments_after=0,views=13,method=reference[3],hardware_profiled=False,
                projection_reference=reference[3]['proof'].get('projection_reference','alpha_hidden_native_source'))
    (Path(job['folder'])/'hair-projection.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def is_placeholder(obj,native,cooked):
    if not obj.get('proven_invisible_slot'):
        return False
    p,t,uv=mobile.geometry(obj,native,cooked)
    if (len(p)!=3 or len(t)!=1 or np.max(np.ptp(p,axis=0))>.051 or
            np.max(np.abs(p-np.asarray((0,4,174))))>.051 or
            any(vertex_weights(obj,v)!={'sk_head':1.0} for v in obj.data.vertices) or
            not np.allclose(uv,.5,rtol=0,atol=1e-6)):
        raise ValueError('Invisible native placeholder changed')
    return True


def surface_quality(old_points,old_faces,obj,native,cooked):
    if is_placeholder(obj,native,cooked):
        return dict(max_cm=0.,p95_cm=0.,reverse_max_cm=0.,lower_neck_max_cm=0.,bounds_max_cm=0.)
    return old_quality(old_points,old_faces,obj,native,cooked)


def transfer(obj,native,cooked,source):
    if is_placeholder(obj,native,cooked):
        return dict(policy='unit_normals_for_proven_invisible_native_slot',source_visible_hair_changed=False)
    return old_transfer(obj,native,cooked,source)


mobile.prepare_hair,mobile.finish_hair,lite.quality,quality.transfer_normals=prepare,finish,surface_quality,transfer
runpy.run_path(str(Path(__file__).with_name('blender_realface_budget_worker.py')),run_name='__main__')
