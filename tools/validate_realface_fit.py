"""Blender round-trip and synthetic-pose audit for a native-reference face fit."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_fit_realface import vertex_weights, runtime_matrix
from blender_export_ue_fbx import rig_globals


def validate(profile, candidate):
    native_rows = json.loads(Path(profile['native_rig']).read_text())
    native = rig_globals(native_rows)
    cooked = rig_globals(json.loads(Path(profile['cooked_rig']).read_text()))
    stop = profile['fit']['stop_z_cm']

    def snapshot(path):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.unit_settings.system = 'METRIC'
        bpy.context.scene.unit_settings.scale_length = .01
        bpy.ops.import_scene.fbx(filepath=str(path), use_anim=False)
        result = {}
        armatures = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
        if len(armatures) != 1 or set(b.name for b in armatures[0].data.bones) != set(native):
            raise ValueError('Candidate exported reference armatures or has wrong bones')
        for obj in bpy.context.scene.objects:
            if obj.type != 'MESH':
                continue
            if obj.get('reference_only') or obj.name.startswith('native_'):
                raise ValueError('Reference geometry leaked into the export')
            weights = [vertex_weights(obj, v) for v in obj.data.vertices]
            result[obj.name] = dict(
                points=[runtime_matrix(obj,w,native,cooked)@v.co for w,v in zip(weights,obj.data.vertices)],
                weights=weights, normals=[n.vector.copy() for n in obj.data.corner_normals],
                loops=[l.vertex_index for l in obj.data.loops],
                uv=[[tuple(l.uv) for l in layer.data] for layer in obj.data.uv_layers],
                polys=[tuple(p.vertices) for p in obj.data.polygons],
                materials=[m.name.split('.')[0] for m in obj.data.materials])
        return result

    before, after = snapshot(Path(profile['face_fbx'])), snapshot(candidate/'face.fbx')
    if set(before) != set(after):
        raise ValueError('Exported mesh set differs')
    rows = []
    for name, old in before.items():
        new = after[name]
        for key in ('uv', 'polys', 'materials', 'loops'):
            if old[key] != new[key]:
                raise ValueError(name + ': round-trip changed ' + key)
        eye = profile.get('eye') and profile['eye']['material'] in old['materials']
        protected = [i for i,p in enumerate(old['points']) if
                     (p.x < 0 if profile.get('eye', {}).get('reference_side') == 'negative_x' else p.x > 0)
                     ] if eye else [i for i,p in enumerate(old['points']) if p.z >= stop]
        drift = max(((old['points'][i]-new['points'][i]).length for i in protected), default=0)
        if drift > .001:
            raise ValueError(name + ': protected region moved')
        if any(sum(abs(old['weights'][i].get(n,0)-new['weights'][i].get(n,0)) for n in native) > 1e-5 for i in protected):
            raise ValueError(name + ': protected skin weights changed')
        normal_drift = max(((a-b).length for a,b,v in zip(old['normals'],new['normals'],old['loops']) if v in protected), default=0)
        if normal_drift > .002:
            raise ValueError(name + ': protected normals changed')
        if any(len(w)>4 for w in new['weights']):
            raise ValueError('Too many vertex influences')
        rows.append(dict(mesh=name,vertices=len(old['points']),protected_vertices=len(protected),
                         protected_drift_cm=drift,protected_normal_drift=normal_drift,
                         uv_topology_materials_preserved=True))

    parents = {b['name']: native_rows[b['parent']]['name'] if b['parent'] >= 0 else None for b in native_rows}
    def descendant(name, ancestor):
        while name:
            if name == ancestor:
                return True
            name = parents[name]
        return False
    samples = json.loads((candidate/'motion-samples.json').read_text())
    poses = [('rest',[]), ('head_left',[('sk_head','Z',35)]),
             ('head_right',[('sk_head','Z',-35)]), ('neck_forward',[('sk_neck','X',25)]),
             ('neck_back',[('sk_neck','X',-20)]),
             ('celebration',[('sk_shoulder_l','Y',-25),('sk_shoulder_r','Y',25),('sk_neck','X',-10)])]
    pose_report = []
    for label, actions in poses:
        posed = {n:m.copy() for n,m in native.items()}
        for joint, axis, degrees in actions:
            pivot = posed[joint].translation
            change = Matrix.Translation(pivot) @ Matrix.Rotation(math.radians(degrees),4,axis) @ Matrix.Translation(-pivot)
            for name in posed:
                if descendant(name,joint):
                    posed[name] = change @ posed[name]
        def animate(p, w, converted):
            if converted:
                rest = Matrix([[sum((native[n]@cooked[n].inverted())[r][c]*v for n,v in w.items()) for c in range(4)] for r in range(4)])
                position = rest.inverted() @ Vector(p)
                return sum((posed[n]@cooked[n].inverted()@position*v for n,v in w.items()),Vector())
            return sum((posed[n]@native[n].inverted()@Vector(p)*v for n,v in w.items()),Vector())
        errors_old, errors_new = [], []
        for sample in samples:
            target = animate(sample['native_surface'],sample['target_weights'],False)
            errors_old.append((animate(sample['before'],sample['before_weights'],True)-target).length)
            errors_new.append((animate(sample['after'],sample['after_weights'],True)-target).length)
        pose_report.append(dict(pose=label,mean_surface_error_before_cm=sum(errors_old)/len(errors_old),
                                mean_surface_error_after_cm=sum(errors_new)/len(errors_new),
                                max_surface_error_before_cm=max(errors_old),max_surface_error_after_cm=max(errors_new)))
    report = dict(meshes=rows,poses=pose_report,pose_test_scope='Synthetic bone rotations, not captured native animations; Switch validation required')
    (candidate/'roundtrip-pose-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    validate(json.loads(args.profile.read_text()),args.candidate)
