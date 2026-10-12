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
from blender_fit_realface import runtime_matrix, vertex_weights, weighted_bind_matrix
from realface_reference import load_reference
from realface_cook_policy import collapsed_triangle, audited_triangle_drop
from realface_triangle_audit import surviving_triangles
from realface_vertex_audit import match_vertices


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
        row = expected.setdefault(kind, dict(points=[], bind_points=[], uv=[], weights=[], triangles=0, collapsed=0, faces=[]))
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
        for triangle in obj.data.loop_triangles:
            ids=[base+i for i in triangle.vertices]
            uv=[obj.data.uv_layers[0].data[i].uv for i in triangle.loops]
            row['faces'].append(dict(points=[tuple(row['bind_points'][i]) for i in ids],
                uv=[(u,1-v) for u,v in uv],weights=[imported_weights(row['weights'][i]) for i in ids]))
        row['triangles'] += len(obj.data.loop_triangles)
        row['collapsed'] += sum(collapsed_triangle([row['bind_points'][base+i]
                                for i in triangle.vertices])
                                for triangle in obj.data.loop_triangles)

    path = Path(spec['gltf'])
    document = json.loads(path.read_text())
    mesh = load_reference(path)
    actual = {}
    start = 0;face_start=0
    for primitive in document['meshes'][0]['primitives']:
        material = document['materials'][primitive['material']]['name']
        if material not in spec['cooked_material_map']:
            raise ValueError('Unexpected cooked material: ' + material)
        kind = spec['cooked_material_map'][material]
        count = document['accessors'][primitive['attributes']['POSITION']]['count']
        row = actual.setdefault(kind, dict(points=[], bind_points=[], uv=[], weights=[], triangles=0, faces=[]))
        for index in range(start, start+count):
            weights = mesh['weights'][index]
            transform = weighted_bind_matrix(weights, native, actual_rig)
            row['points'].append(transform @ Vector(mesh['vertices'][index]))
            row['bind_points'].append(Vector(mesh['vertices'][index]))
            row['uv'].append(mesh['uv'][index])
            row['weights'].append(weights)
        face_count=document['accessors'][primitive['indices']]['count']//3
        for ids in mesh['faces'][face_start:face_start+face_count]:
            row['faces'].append(dict(points=[mesh['vertices'][i] for i in ids],
                uv=[mesh['uv'][i] for i in ids],weights=[mesh['weights'][i] for i in ids]))
        face_start+=face_count
        row['triangles'] += face_count
        start += count
    if set(actual) != set(expected):
        raise ValueError('Cooked mesh omitted or added a material component')
    results = {}
    for kind, old in expected.items():
        new = actual[kind]
        surface_proof=None
        dropped = spec.get('expected_collapsed_triangles', {}).get(kind, 0)
        if spec.get('permit_exact_source_collapses'):
            # Deterministic batch policy: only triangles whose three source
            # bind-space corners all coincide within 0.00001 cm may disappear.
            # A thin but extended card still fails the exact count check.
            try:
                dropped = audited_triangle_drop(old['triangles'], new['triangles'], old['collapsed'])
            except ValueError as error:
                dropped=old['triangles']-new['triangles']
                if not 0<dropped<=old['collapsed']:
                    raise ValueError('Cooked triangle count changed: ' + kind) from error
                surface_proof=surviving_triangles(old['faces'],new['faces'],.005 if kind=='eye' else .03)
        if dropped and old['collapsed'] != dropped and surface_proof is None:
            raise ValueError('Audited collapsed triangle count changed: ' + kind)
        if old['triangles'] - dropped != new['triangles']:
            raise ValueError('Cooked triangle count changed: ' + kind)
        limit = .005 if kind == 'eye' else .03
        source_weights = [imported_weights(weights) for weights in old['weights']]
        errors,uv_errors,weight_errors=match_vertices(new['bind_points'],new['uv'],new['weights'],
            old['bind_points'],old['uv'],source_weights,limit)
        reverse = KDTree(len(new['points']))
        for i, point in enumerate(new['bind_points']):
            reverse.insert(point, i)
        reverse.balance()
        coverage = max(reverse.find(p)[2] for p in old['bind_points'])
        if coverage >= limit:
            raise ValueError('Cooked geometry dropped source vertices: ' + kind)
        results[kind] = dict(source_vertices=len(old['points']), cooked_vertices=len(new['points']),
            source_triangles=old['triangles'], triangles=new['triangles'],
            audited_collapsed_triangles_removed=dropped,surviving_surface_proof=surface_proof,
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
