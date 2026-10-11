"""Compare an exported cooked face/hair with its validated FBX in native space.

Run inside Blender with -- --profile local.json. The profile supplies native
and cooked rig contracts, face/hair FBXs, UE Viewer glTFs and material names.
This audits rest geometry, UVs, skin weights and triangle counts, not device
animation or appearance. An embedded cooked-rig audit is also required.
"""
import argparse
import json
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_realface_rig import audit_rig
from blender_export_ue_fbx import rig_globals
from blender_fit_realface import runtime_matrix, vertex_weights
from realface_reference import load_reference
from realface_cook_policy import collapsed_triangle


def imported_weights(source):
    # UE4's FBX importer removes influences below one percent before the
    # Android vertex buffer quantizes its remaining weights to eight bits.
    kept={name:value for name,value in source.items() if value>.01}
    total=sum(kept.values())
    if not total:raise ValueError('Source has no supported bone influence')
    return {name:value/total for name,value in kept.items()}


def validate_part(spec, native, contract, contract_rows):
    rig = audit_rig(json.loads(Path(spec['cooked_mesh_json']).read_text(encoding='utf-8-sig')), contract_rows, True)
    actual_rig=rig_globals(rig.pop('embedded_rig'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.scale_length = .01
    bpy.ops.import_scene.fbx(filepath=str(Path(spec['fbx']).resolve()), use_anim=False)
    expected = {}
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        materials = [m.name for m in obj.data.materials]
        if len(materials) != 1 or materials[0] not in spec['material_map']:
            raise ValueError('Unexpected FBX material: ' + str(materials))
        kind = spec['material_map'][materials[0]]
        row = expected.setdefault(kind, dict(points=[], bind_points=[], uv=[], weights=[], triangles=0, collapsed=0))
        base = len(row['points'])
        weights = [vertex_weights(obj, v) for v in obj.data.vertices]
        row['points'].extend(runtime_matrix(obj, w, native, contract) @ v.co
                             for v, w in zip(obj.data.vertices, weights))
        # FBX's Unreal import basis reflects Blender Y. This is the same
        # reflection used by runtime_matrix, before weighted rig compensation.
        basis=Matrix.Diagonal((1.,-1.,1.,1.)) @ obj.matrix_world
        row['bind_points'].extend(basis @ v.co for v in obj.data.vertices)
        row['weights'].extend(weights)
        row['uv'].extend(set() for _ in obj.data.vertices)
        for loop in obj.data.loops:
            u, v = obj.data.uv_layers[0].data[loop.index].uv
            row['uv'][base + loop.vertex_index].add((u, 1-v))
        obj.data.calc_loop_triangles()
        row['triangles'] += len(obj.data.loop_triangles)
        row['collapsed'] += sum(collapsed_triangle([row['bind_points'][base+i]
                                for i in triangle.vertices])
                                for triangle in obj.data.loop_triangles)

    path = Path(spec['gltf'])
    document = json.loads(path.read_text())
    mesh = load_reference(path)
    actual = {}
    start = 0
    for primitive in document['meshes'][0]['primitives']:
        material = document['materials'][primitive['material']]['name']
        if material not in spec['cooked_material_map']:
            raise ValueError('Unexpected cooked material: ' + material)
        kind = spec['cooked_material_map'][material]
        count = document['accessors'][primitive['attributes']['POSITION']]['count']
        row = actual.setdefault(kind, dict(points=[], bind_points=[], uv=[], weights=[], triangles=0))
        for index in range(start, start+count):
            weights = mesh['weights'][index]
            transform = Matrix([[sum((native[b] @ actual_rig[b].inverted())[j][k]*v
                                    for b, v in weights.items())
                                 for k in range(4)] for j in range(4)])
            row['points'].append(transform @ Vector(mesh['vertices'][index]))
            row['bind_points'].append(Vector(mesh['vertices'][index]))
            row['uv'].append(mesh['uv'][index])
            row['weights'].append(weights)
        row['triangles'] += document['accessors'][primitive['indices']]['count']//3
        start += count
    if set(actual) != set(expected):
        raise ValueError('Cooked mesh omitted or added a material component')
    results = {}
    for kind, old in expected.items():
        new = actual[kind]
        dropped = spec.get('expected_collapsed_triangles', {}).get(kind, 0)
        if dropped and old['collapsed'] != dropped:
            raise ValueError('Audited collapsed triangle count changed: ' + kind)
        if old['triangles'] - dropped != new['triangles']:
            raise ValueError('Cooked triangle count changed: ' + kind)
        limit = .005 if kind == 'eye' else .03
        tree = KDTree(len(old['points']))
        source_weights = [imported_weights(weights) for weights in old['weights']]
        for i, point in enumerate(old['bind_points']):
            tree.insert(point, i)
        tree.balance()
        errors, uv_errors, weight_errors = [], [], []
        for point, uv, weights in zip(new['bind_points'], new['uv'], new['weights']):
            candidates = tree.find_range(point, limit)
            if not candidates:
                raise ValueError('Cooked geometry moved beyond tolerance: ' + kind)
            errors.append(min(d for _, _, d in candidates))
            # Require a single matching position/UV/weight tuple. Independent
            # minima could accidentally approve UVs from another seam vertex.
            matches = [(d, max(abs(uv[k]-st[k]) for k in (0, 1)),
                        sum(abs(weights.get(b, 0)-source_weights[i].get(b, 0))
                            for b in weights.keys() | source_weights[i].keys()))
                       for _, i, d in candidates for st in old['uv'][i]]
            eligible = [m for m in matches if m[1] < .001 and m[2] < .025]
            if not eligible:
                raise ValueError('Cooked UV or skin weights changed: ' + str(dict(kind=kind,
                    best=min(matches,key=lambda m:m[1]+m[2]),weights=weights,
                    source_weights=old['weights'][candidates[0][1]])))
            _, u, w = min(eligible, key=lambda m: m[0])
            uv_errors.append(u); weight_errors.append(w)
        reverse = KDTree(len(new['points']))
        for i, point in enumerate(new['bind_points']):
            reverse.insert(point, i)
        reverse.balance()
        coverage = max(reverse.find(p)[2] for p in old['bind_points'])
        if coverage >= limit:
            raise ValueError('Cooked geometry dropped source vertices: ' + kind)
        results[kind] = dict(source_vertices=len(old['points']), cooked_vertices=len(new['points']),
            source_triangles=old['triangles'], triangles=new['triangles'],
            audited_collapsed_triangles_removed=dropped,
            comparison_space='cooked_bind_cm',max_position_error_cm=max(errors),
            max_source_coverage_error_cm=coverage, max_uv_error=max(uv_errors),
            weight_comparison='UE4_minimum_one_percent_then_8bit',max_weight_l1_error=max(weight_errors))
    return dict(rig=rig, components=results)


def validate(profile):
    native = rig_globals(json.loads(Path(profile['native_rig']).read_text()))
    rows = json.loads(Path(profile['cooked_rig']).read_text())
    contract = rig_globals(rows)
    parts = {name: validate_part(spec, native, contract, rows)
             for name, spec in profile['parts'].items()}
    report = dict(base_id=profile['base_id'], native_player_id=profile['native_player_id'],
                  parts=parts, hardware_accepted=False)
    Path(profile['report']).write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    print(json.dumps(validate(json.loads(args.profile.read_text())), indent=2))
