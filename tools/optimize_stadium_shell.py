"""Blender stage: reduce a prepared shell, preserve crowd, merge atlas pages.

Run after stadium_atlas.py. Reads the existing blend/profile without modifying
them, writes a new FBX/profile/blend into a separate local output directory.
"""
import argparse
import json
from pathlib import Path
import sys
import math
import bpy
import bmesh

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--profile', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
p.add_argument('--triangles', type=int, default=35000)
p.add_argument('--vertex-camera-cull', action='store_true')
a = p.parse_args(sys.argv[sys.argv.index('--') + 1:])
if not 10000 <= a.triangles <= 100000:
    raise ValueError('Invalid shell budget')
profile = json.loads(a.profile.read_text())
atlas = json.loads((a.output / 'textures/atlas.local.json').read_text())
if Path(atlas['source_profile']).resolve() != a.profile.resolve():
    raise ValueError('Atlas belongs to another source')
key = profile['key']
bpy.ops.wm.open_mainfile(filepath=str(Path(profile['fbx']).with_suffix('.blend')))
shell = bpy.data.objects[key + 'Shell']
# Separate the already fitted native rows before decimation. Their seats,
# UVs, frame count and number remain exactly as in the reviewed v25 model.
crowd_indices = {i for i, m in enumerate(shell.data.materials) if m.name == 'M_crowd_seated'}
crowd = shell.copy()
crowd.data = shell.data.copy()
bpy.context.collection.objects.link(crowd)
for obj, keep_crowd in ((shell, False), (crowd, True)):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if (f.material_index in crowd_indices) != keep_crowd], context='FACES')
    # FACES keeps loose vertices from the original shell. Remove those too:
    # they inflate FBX bounds even though UE discards them during mesh import.
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
bpy.ops.object.select_all(action='DESELECT')
shell.select_set(True)
bpy.context.view_layer.objects.active = shell
shell.data.calc_loop_triangles()
before = len(shell.data.loop_triangles)
if before > a.triangles:
    modifier = shell.modifiers.new('Switch shell budget', 'DECIMATE')
    modifier.ratio = a.triangles / before
    modifier.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
shell.data.calc_loop_triangles()
reduced = len(shell.data.loop_triangles)
crowd.select_set(True)
bpy.ops.object.join()
mesh = shell.data
# Extra UV layers from the PC source are not used by the unlit mobile shell.
while len(mesh.uv_layers) > 1:
    mesh.uv_layers.remove(mesh.uv_layers[-1])
tile_uv = mesh.uv_layers.new(name='AtlasTile')
old_names = [m.name for m in mesh.materials]
page_names = [row['material'] for row in atlas['pages']]
indices = []
for poly in mesh.polygons:
    name = old_names[poly.material_index]
    entry = atlas['mapping'].get(name)
    if entry:
        index, tile = page_names.index(entry['material']), entry['tile']
    elif name == 'M_crowd_seated':
        index, tile = page_names.index(name), 0
    else:
        raise ValueError('Unmapped source material: ' + name)
    indices.append(index)
    for loop in poly.loop_indices:
        tile_uv.data[loop].uv = (tile, 0)
mesh.materials.clear()
for row in atlas['pages']:
    # Use a fresh material ID so FBX slot names cannot retain old suffixes.
    old = bpy.data.materials.get(row['material'])
    if old:
        old.name = 'source_' + old.name
    mat = bpy.data.materials.new(row['material'])
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(row['color'])
    mesh.materials.append(mat)
for poly, index in zip(mesh.polygons, indices):
    poly.material_index = index
# The shell's hemisphere light is static and unlit. Bake it per corner so its
# fragment shaders no longer need interpolated normal/tangent vectors. Native
# pitch/player light and the roof visibility policy remain runtime effects.
for old in list(mesh.color_attributes):
    mesh.color_attributes.remove(old)
shade = mesh.color_attributes.new(name='ShellHemisphere', type='FLOAT_COLOR', domain='CORNER')
for loop, normal in zip(shade.data, mesh.corner_normals):
    n = normal.vector
    value = .65 + .30 * max(0.0, min(1.0, n.x*.25-n.y*.35+n.z*.90))
    loop.color = (value, value, value, 1.0)
mesh.color_attributes.active_color = shade
profile['baked_hemisphere'] = dict(version=1, minimum=.65, maximum=.95, sun_blender=[.25,-.35,.90])
# Re-optimizing a previously optimized input must not inherit its old policy.
profile['vertex_camera_cull'] = False
if a.vertex_camera_cull:
    # Four-metre spatial clusters preserve shared vertices within each cell.
    # Store the SAME enclosing box at all corners, never an interpolated
    # per-vertex decision. FBX flips V; compensate that flip on both channels.
    groups = {}
    for poly in mesh.polygons:
        points = [mesh.vertices[i].co for i in poly.vertices]
        centre = [sum(p[i] for p in points)/len(points) for i in range(3)]
        cluster = tuple(math.floor(v/4) for v in centre)+(poly.material_index,)
        groups.setdefault(cluster, []).append(poly)
    xy = mesh.uv_layers.new(name='CullCentreXY')
    ze = mesh.uv_layers.new(name='CullCentreZExtentX')
    yz = mesh.uv_layers.new(name='CullExtentYZ')
    for cluster_id, polygons in enumerate(groups.values(), start=1):
        points = [mesh.vertices[i].co for poly in polygons for i in poly.vertices]
        centre = [(min(p[i] for p in points)+max(p[i] for p in points))*.5 for i in range(3)]
        extent = [(max(p[i] for p in points)-min(p[i] for p in points))*50+32 for i in range(3)]
        # 32cm per axis encloses half-float UV quantization, checked again on
        # the cooked mesh. A box stays tight around flat floors and walls.
        packed = [v/32768 for v in (centre[0]*100, -centre[1]*100, centre[2]*100, *extent)]
        for poly in polygons:
            for loop in poly.loop_indices:
                # UE's mesh builder welds UVs within 1/1024 (~32cm in the
                # packed bounds). An otherwise unused UV1.y separates cells
                # during that build, even when their box values are close.
                # The atlas shader reads only UV1.x, and the ID is not used
                # by culling, so later half-float ID rounding is harmless.
                tile_uv.data[loop].uv.y = cluster_id
                xy.data[loop].uv = (packed[0], 1-packed[1])
                ze.data[loop].uv = (packed[2], 1-packed[3])
                yz.data[loop].uv = (packed[4], 1-packed[5])
    profile['vertex_camera_cull'] = dict(version=2, bounds_uv=[2, 3, 4], weld_seam_uv='UV1.y', clusters=len(groups), cell_m=4, quantization_padding_cm=32)
mesh.uv_layers.active_index = 0
shell.name = key + 'Shell'
output = a.output.resolve()
bpy.ops.export_scene.fbx(filepath=str(output / (key + 'Shell.fbx')),
    use_selection=True, object_types={'MESH'}, global_scale=1.0,
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
    axis_forward='-Y', axis_up='Z', use_mesh_modifiers=True,
    bake_anim=False, path_mode='ABSOLUTE', add_leaf_bones=False, mesh_smooth_type='FACE', colors_type='LINEAR')
profile['fbx'] = str(output / (key + 'Shell.fbx'))
profile['shell_triangles'] = dict(original=before, reduced=reduced)
profile['material_slots'] = page_names
profile['material_policies'] = {r['material']: dict(masked=r.get('masked', False), two_sided=r.get('two_sided', True)) for r in atlas['pages']}
profile['texture_files'] = {r['material']: r['color'] for r in atlas['pages']}
profile['mask_files'] = {r['material']: r['mask'] for r in atlas['pages'] if 'mask' in r}
profile['textures'] = {r['material'][2:]: dict(max_texture_size=r['max_texture_size'], alpha_range=[255, 255]) for r in atlas['pages']}
profile['atlas'] = dict(version=1, tile_uv_channel=1, materials=[r['material'] for r in atlas['pages'] if not r.get('animated')])
profile['optimization'] = dict(source_profile=str(a.profile.resolve()), shell_before=before,
    shell_after=reduced, materials_before=atlas['old_materials'], materials_after=len(page_names),
    crowd_rows_preserved=profile['crowd']['fitted_rows'])
referenced = {v for poly in mesh.polygons for v in poly.vertices}
profile['blender_bounds'] = [[min(mesh.vertices[v].co[i] for v in referenced) for i in range(3)],
                             [max(mesh.vertices[v].co[i] for v in referenced) for i in range(3)]]
(output / 'fbx.local.json').write_text(json.dumps(profile, indent=2) + '\n')
bpy.ops.wm.save_as_mainfile(filepath=str(output / (key + 'Shell.blend')))
print('PESNX_STADIUM_OPTIMIZED', key, before, reduced, atlas['old_materials'], len(page_names))
