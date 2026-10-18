"""Blender offline repair: native floor owns its exact coplanar footprint.

Read a previously optimized shell and an owned UModel glTF native pitch. Cut
only nearly flat shell floors near pitch height against the actual native
footprint, never its bounding rectangle (which has uncovered corners). The
default height range is +/-6 cm; audited buried slopes can lower the minimum.
No material, camera, texture, crowd or runtime shader work is added.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_stadium_optimization import accessor
from stadium_apron_geometry import height_band


def repair(profile_path, native_path, output, polygon_python, polygon_modules, floor_min_height,
           omit_floor_decals=False, raise_floor_materials=(), raise_floor_ranges=()):
    profile = json.loads(profile_path.read_text())
    key = profile['key']
    if output.exists():
        raise FileExistsError('Use a fresh output: '+str(output))
    native = json.loads(native_path.read_text())
    blob = (native_path.parent/native['buffers'][0]['uri']).read_bytes()
    clips = []
    for primitive in native['meshes'][0]['primitives']:
        positions = accessor(native, blob, primitive['attributes']['POSITION'])
        indices = accessor(native, blob, primitive['indices']).reshape(-1, 3)
        # UModel uses (UE X,Z,Y); Blender uses (UE X,-Y,Z), both in metres.
        for triangle in positions[indices]:
            if np.abs(triangle[:, 1]).max() > .001:
                raise ValueError('Native floor is not the expected zero-height pitch')
            xy = [(float(v[0]), -float(v[2])) for v in triangle]
            area = sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(xy, xy[1:]+xy[:1]))
            if abs(area) > 1e-9:
                clips.append((xy, np.min(xy, axis=0), np.max(xy, axis=0)))
    if not 100 <= len(clips) <= 5000:
        raise ValueError('Unexpected native ground geometry')
    bpy.ops.wm.open_mainfile(filepath=str(Path(profile['fbx']).with_suffix('.blend')))
    obj = bpy.data.objects[key+'Shell']; old = obj.data
    vertices = [tuple(v.co) for v in old.vertices]
    faces, materials, normals = [], [], []
    uv_names = [u.name for u in old.uv_layers]
    uv_values = [[] for _ in uv_names]
    changed = removed = generated = 0
    old_normals = [tuple(n.vector) for n in old.corner_normals]
    crowd_before = sum(len(p.vertices)-2 for p in old.polygons if old.materials[p.material_index].name == 'M_crowd_seated')
    old.calc_loop_triangles()
    # Optional imported pitch paint/debris duplicates the retained native
    # floor. Select exact atlas entries, then constrain removal to flat ground;
    # crowd, signs, fences and physical stadium surfaces are not candidates.
    decal_tiles = set()
    if omit_floor_decals:
        atlas = json.loads((profile_path.parent/'textures/atlas.local.json').read_text())
        prefixes = ('M_cm000_line', 'M_cm000_pich', 'M_cm000_tire_decal_',
                    'M_cm000_whit', 'M_cm000_pape')
        for name, entry in atlas['mapping'].items():
            if name.startswith(prefixes) and entry.get('masked'):
                decal_tiles.add((entry['material'], entry['tile']))
    omitted_decals = set()
    eligible = {}
    for index, face in enumerate(old.loop_triangles):
        points = [vertices[v] for v in face.vertices]
        if decal_tiles and (old.materials[face.material_index].name,
                round(old.uv_layers[1].data[face.loops[0]].uv.x)) in decal_tiles:
            if min(p[2] for p in points)>=-.5 and max(p[2] for p in points)<=.2 and abs(face.normal.z)>=.95:
                omitted_decals.add(index)
                continue
        if (old.materials[face.material_index].name != 'M_crowd_seated'
                and min(p[2] for p in points) <= .06
                and max(p[2] for p in points) >= floor_min_height and abs(face.normal.z) >= .95):
            # A long, shallow ramp may cross the native floor while its far
            # vertex exceeds the height band. Cut only the band, retaining
            # the elevated portion and its interpolated UVs/normals.
            eligible[str(index)] = dict(points=[p[:2] for p in points],
                clip=height_band(points, floor_min_height, .06))
    with tempfile.TemporaryDirectory(prefix='pesnx-apron-') as directory:
        request, result = Path(directory)/'input.json', Path(directory)/'output.json'
        request.write_text(json.dumps(dict(native=[c[0] for c in clips], faces=eligible)))
        import os
        env = os.environ.copy()
        if polygon_modules:
            env['PYTHONPATH'] = str(polygon_modules)
        subprocess.run([str(polygon_python), str(Path(__file__).with_name('stadium_apron_geometry.py')),
                        str(request), str(result)], check=True, env=env)
        repaired = json.loads(result.read_text())
    for index, face in enumerate(old.loop_triangles):
        if index in omitted_decals:
            changed += 1; removed += 1
            continue
        loops = tuple(face.loops)
        points = [vertices[v] for v in face.vertices]
        original = [tuple(p[:2]) + tuple(float(i == j) for j in range(3)) for i, p in enumerate(points)]
        fragments = [original]
        if str(index) in repaired:
            fragments = []
            a, b, c = np.array(points)[:, :2]
            matrix = np.column_stack((b-a, c-a))
            orientation = np.linalg.det(matrix)
            for triangle in repaired[str(index)]:
                polygon = []
                for xy in triangle:
                    v, w = np.linalg.solve(matrix, np.array(xy)-a)
                    polygon.append(tuple(xy)+(1-v-w, v, w))
                # GEOS outputs CCW; preserve the original floor's face winding.
                signed = sum(p[0]*q[1]-p[1]*q[0] for p, q in zip(polygon, polygon[1:]+polygon[:1]))
                if signed*orientation < 0:
                    polygon.reverse()
                fragments.append(polygon)
        if fragments == [original]:
            faces.append(tuple(face.vertices)); materials.append(face.material_index)
            normals.extend(old_normals[i] for i in loops)
            for u, layer in zip(uv_values, old.uv_layers):
                u.extend(tuple(layer.data[i].uv) for i in loops)
            continue
        changed += 1
        if not fragments:
            removed += 1
        for polygon in fragments:
            for j in range(1, len(polygon)-1):
                triangle = [polygon[0], polygon[j], polygon[j+1]]
                cross = (triangle[1][0]-triangle[0][0])*(triangle[2][1]-triangle[0][1])-(triangle[1][1]-triangle[0][1])*(triangle[2][0]-triangle[0][0])
                if abs(cross) < 1e-8:
                    continue
                face_ids = []
                for point in triangle:
                    w = point[2:]
                    face_ids.append(len(vertices))
                    vertices.append(tuple(sum(w[i]*points[i][c] for i in range(3)) for c in range(3)))
                    n = np.array([sum(w[i]*old_normals[loops[i]][c] for i in range(3)) for c in range(3)])
                    normals.append(tuple(n/np.linalg.norm(n)))
                    for u, layer in zip(uv_values, old.uv_layers):
                        u.append(tuple(sum(w[i]*layer.data[loops[i]].uv[c] for i in range(3)) for c in range(2)))
                faces.append(tuple(face_ids)); materials.append(face.material_index); generated += 1
    # Give explicitly reviewed opaque floor overlays 3 cm of physical separation
    # from their concrete base. Duplicate only their ground vertices so nearby
    # walls, normals, UVs and the original surface remain untouched.
    raised_faces = 0
    if raise_floor_materials or raise_floor_ranges:
        atlas = json.loads((profile_path.parent/'textures/atlas.local.json').read_text())
        raise_tiles = {}
        ranges = [(name, -.25, .06) for name in raise_floor_materials]
        ranges += [(name, float(low), float(high)) for name, low, high in raise_floor_ranges]
        for name, low, high in ranges:
            if not -.5 <= low < high <= 2.:
                raise ValueError('Reviewed floor range must stay within -0.5..2 metres')
            entry = atlas['mapping'][name]
            if entry.get('masked'):
                raise ValueError('Raised floor must be an opaque source material')
            raise_tiles[(entry['material'], entry['tile'])] = (low, high)
        for index, face in enumerate(faces):
            tile = round(uv_values[1][index*3][0])
            points = np.array([vertices[v] for v in face])
            normal = np.cross(points[1]-points[0], points[2]-points[0])
            bounds = raise_tiles.get((old.materials[materials[index]].name, tile))
            if (bounds is None or points[:,2].min()<bounds[0] or points[:,2].max()>bounds[1]
                    or abs(normal[2])<.95*np.linalg.norm(normal)):
                continue
            faces[index] = tuple(range(len(vertices), len(vertices)+3))
            vertices.extend((float(x),float(y),float(z)+.03) for x,y,z in points)
            raised_faces += 1
    # A reducer may leave almost-collinear long triangles. FBX centimetre
    # conversion/UE float rounding can turn a subset into exact degenerates,
    # making independently cooked counts disagree. Strip only sub-0.01 mm
    # altitudes before export, keeping all surviving corner attributes intact.
    live=[]
    for index,face in enumerate(faces):
        points=np.asarray([vertices[i] for i in face],dtype=float)
        edge=max(np.linalg.norm(points[(i+1)%3]-points[i]) for i in range(3))
        area2=np.linalg.norm(np.cross(points[1]-points[0],points[2]-points[0]))
        if edge>0 and area2/edge>=1e-5:live.append(index)
        elif old.materials[materials[index]].name=='M_crowd_seated':
            raise ValueError('Unexpected degenerate preserved crowd triangle')
    degenerate_removed=len(faces)-len(live)
    if degenerate_removed:
        faces=[faces[i] for i in live];materials=[materials[i] for i in live]
        normals=[value for i in live for value in normals[i*3:i*3+3]]
        uv_values=[[value for i in live for value in values[i*3:i*3+3]] for values in uv_values]
    # Remove vertices made unreferenced by the cut without welding UV/bound seams.
    used = sorted({v for f in faces for v in f}); remap = {old: i for i, old in enumerate(used)}
    mesh = bpy.data.meshes.new(key+'RepairedFloor')
    mesh.from_pydata([vertices[i] for i in used], [], [tuple(remap[i] for i in f) for f in faces])
    live_materials = sorted(set(materials))
    slot_map = {previous: current for current, previous in enumerate(live_materials)}
    for index in live_materials:
        mesh.materials.append(old.materials[index])
    for face, index in zip(mesh.polygons, materials):
        face.material_index = slot_map[index]; face.use_smooth = True
    for name, values in zip(uv_names, uv_values):
        layer = mesh.uv_layers.new(name=name)
        layer.data.foreach_set('uv', np.array(values).ravel())
    mesh.normals_split_custom_set(normals)
    shade = mesh.color_attributes.new(name='ShellHemisphere', type='FLOAT_COLOR', domain='CORNER')
    for colour, normal in zip(shade.data, mesh.corner_normals):
        n = normal.vector
        light = .65+.30*max(0., min(1., n.x*.25-n.y*.35+n.z*.90))
        colour.color = (light, light, light, 1.)
    mesh.color_attributes.active_color = shade
    mesh.uv_layers.active_index = 0
    obj.data = mesh
    crowd_after = sum(len(p.vertices)-2 for p in mesh.polygons if mesh.materials[p.material_index].name == 'M_crowd_seated')
    assert crowd_after == crowd_before == profile['crowd']['triangles']
    output.mkdir(parents=True)
    (output/'textures').mkdir()
    shutil.copyfile(profile_path.parent/'textures/atlas.local.json', output/'textures/atlas.local.json')
    # Texture paths are absolute and reused; no bitmap or OBB copies are needed.
    for name in ('texture_files', 'mask_files'):
        for value in profile.get(name, {}).values():
            if not Path(value).is_file():
                raise FileNotFoundError(value)
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    fbx = output/(key+'Shell.fbx')
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={'MESH'},
        global_scale=1., apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
        axis_forward='-Y', axis_up='Z', use_mesh_modifiers=True, bake_anim=False,
        path_mode='ABSOLUTE', add_leaf_bones=False, mesh_smooth_type='FACE', colors_type='LINEAR')
    report = dict(version=3, native_triangles=len(clips), height_tolerance_m=.06,
        floor_min_height_m=floor_min_height,
        sloped_floor_band_clipping=True,
        omitted_native_floor_decal_triangles=len(omitted_decals),
        raised_floor_triangles=raised_faces, raised_floor_clearance_m=.03 if raised_faces else 0.,
        changed_faces=changed, removed_faces=removed, generated_fragments=generated,
        removed_degenerate_faces=degenerate_removed,
        source_shell_triangles=profile['shell_triangles']['reduced'],
        result_shell_triangles=len(faces)-crowd_after, crowd_triangles=crowd_after)
    profile['fbx'] = str(fbx)
    profile['material_slots'] = [m.name for m in mesh.materials]
    for field in ('material_policies', 'texture_files', 'mask_files'):
        profile[field] = {k: v for k, v in profile.get(field, {}).items() if k in profile['material_slots']}
    profile['atlas']['materials'] = [n for n in profile['atlas']['materials'] if n in profile['material_slots']]
    profile['shell_triangles']['reduced'] = len(faces)-crowd_after
    # Clipping, decimation and removal of loose vertices can change extrema.
    # The UE validation must compare the exported, referenced geometry.
    profile['blender_bounds'] = [[min(v.co[i] for v in mesh.vertices) for i in range(3)],
                                 [max(v.co[i] for v in mesh.vertices) for i in range(3)]]
    profile['apron_repair'] = report
    (output/'fbx.local.json').write_text(json.dumps(profile, indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(fbx.with_suffix('.blend')))
    print('PESNX_APRON_REPAIR', key, json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--native-pitch', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--polygon-python', required=True, type=Path, help='Host Python with numpy and Shapely 2.1')
    parser.add_argument('--polygon-modules', type=Path, help='Optional local Shapely module directory')
    parser.add_argument('--floor-min-height', type=float, default=-.06,
                        help='Lowest clipped floor vertex in metres; -0.25 also covers audited below-ground slopes')
    parser.add_argument('--omit-native-floor-decals', action='store_true',
                        help='Omit imported ground paint/debris atlas surfaces already supplied by the native floor')
    parser.add_argument('--raise-floor-material', action='append', default=[],
                        help='Exact opaque source atlas material whose floor overlay needs 3 cm base clearance')
    parser.add_argument('--raise-floor-range', action='append', nargs=3, default=[],
                        metavar=('MATERIAL', 'MIN_M', 'MAX_M'),
                        help='Reviewed opaque platform overlay and its exact height band; adds 3 cm clearance')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if not -.5 <= args.floor_min_height <= -.06:
        raise ValueError('Floor minimum must be -0.5..-0.06 metres')
    repair(args.profile.resolve(), args.native_pitch.resolve(), args.output.resolve(),
           args.polygon_python.resolve(), args.polygon_modules.resolve() if args.polygon_modules else None,
           args.floor_min_height, args.omit_native_floor_decals, args.raise_floor_material, args.raise_floor_range)
