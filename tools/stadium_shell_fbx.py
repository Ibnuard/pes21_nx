"""Blender background stage: glTF shell -> UE4 FBX, merged by base texture.

Usage: blender --background --python stadium_shell_fbx.py -- local-output-dir
Fox X/Z are horizontal, Y is height. glTF import gives Blender (X,-Z,Y);
FBX's -Y forward conversion then gives the intended UE4 centimetre basis.
"""
import json
from pathlib import Path
import sys
import argparse
import bpy
import bmesh

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('work', type=Path)
parser.add_argument('--triangle-ratio', type=float, default=1.0)
parser.add_argument('--crowd-area', type=Path)
parser.add_argument('--crowd-atlas', type=Path)
parser.add_argument('--crowd-flipbook', action='store_true')
parser.add_argument('--target-triangles', type=int)
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
if not .5 <= args.triangle_ratio <= 1 or bool(args.crowd_area) != bool(args.crowd_atlas):
    raise ValueError('Use ratio .5..1 and provide both crowd area and atlas')
work = args.work.resolve()
sys.path.insert(0, str(Path(__file__).resolve().parent))
from stadium_assets import asset_key, material_key
report = json.loads((work / "conversion.local.json").read_text())
stadium_key = asset_key(report.get('key', 'Anfield'))
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for part in report["parts"]:
    bpy.ops.import_scene.gltf(filepath=str(work / (part["name"] + ".gltf")))
materials = {}
for obj in list(bpy.context.scene.objects):
    if obj.type != "MESH":
        bpy.data.objects.remove(obj, do_unlink=True)
        continue
    # Fox stores clockwise front faces; glTF/Blender use counter-clockwise.
    # The old two-sided material hid this mismatch. Correct it before enabling
    # source backface culling and before decimation; native crowd is added later.
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    for slot in obj.material_slots:
        material = slot.material
        images = [n.image for n in material.node_tree.nodes
                  if n.type == "TEX_IMAGE" and n.image] if material and material.use_nodes else []
        texture_key = Path(images[0].filepath).stem if images else "plain_concrete"
        masked = bool(material.get('nxMasked', 'alp' in texture_key))
        two_sided = bool(material.get('nxTwoSided', True))
        key = texture_key + ('_cut' if masked else '_solid') + ('_two' if two_sided else '_one')
        if key not in materials:
            material.name = material_key("M_" + key)
            materials[key] = material
            if images:
                report.setdefault('texture_files', {})[material.name] = str(Path(bpy.path.abspath(images[0].filepath)).resolve())
            report.setdefault('material_policies', {})[material.name] = dict(masked=masked, two_sided=two_sided)
            if texture_key in report['textures']:
                report['textures'][material.name[2:]] = report['textures'][texture_key]
        slot.material = materials[key]
bpy.ops.object.select_all(action="SELECT")
bpy.context.view_layer.objects.active = next(o for o in bpy.context.scene.objects if o.type == "MESH")
bpy.ops.object.join()
shell = bpy.context.object
shell.name = stadium_key + 'Shell'
shell.data.calc_loop_triangles()
original_triangles = len(shell.data.loop_triangles)
ratio = args.triangle_ratio
if args.target_triangles is not None:
    if not 30000 <= args.target_triangles <= 140000:
        raise ValueError('Invalid final shell triangle budget')
    ratio = min(1., args.target_triangles / original_triangles)
if ratio < 1:
    modifier = shell.modifiers.new('Mobile shell reduction', 'DECIMATE')
    modifier.ratio = ratio
    modifier.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=modifier.name)
shell.data.calc_loop_triangles()
report['shell_triangles'] = {'original': original_triangles,
                             'reduced': len(shell.data.loop_triangles)}
if args.crowd_area:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from stadium_crowd import read_areas, crowd_rows
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    vertices, faces, uvs = crowd_rows(read_areas(args.crowd_area.read_bytes()))
    # Reconcile the FL crowd layout with the shell actually imported. Some
    # stadium add-ons include newer seating tiers absent from the shell.
    # Keep only rows whose centre has a seat surface nearby, below its feet.
    bvh = BVHTree.FromObject(shell, bpy.context.evaluated_depsgraph_get())
    kept_vertices, kept_faces, kept_uvs = [], [], []
    for face in faces:
        row = [(vertices[i][0], -vertices[i][2], vertices[i][1]) for i in face]
        centre = (Vector(row[0])+Vector(row[1]))*.5
        hit, normal, index, distance = bvh.ray_cast(centre+Vector((0, 0, .35)), Vector((0, 0, -1)), 1.4)
        if hit is None or abs(normal.z) < .35 or (abs(centre.x)<55 and abs(centre.y)<36):
            continue
        start = len(kept_vertices)
        kept_vertices.extend(row)
        kept_faces.append(tuple(start+i for i in range(4)))
        kept_uvs.extend(uvs[i] for i in face)
    if not 100 <= len(kept_faces) <= 6000:
        raise ValueError('Crowd does not fit the imported seating geometry')
    crowd_mesh = bpy.data.meshes.new('CrowdRows')
    crowd_mesh.from_pydata(kept_vertices, [], kept_faces)
    uv = crowd_mesh.uv_layers.new(name='UVMap')
    for poly in crowd_mesh.polygons:
        for loop in poly.loop_indices:
            uv.data[loop].uv = kept_uvs[crowd_mesh.loops[loop].vertex_index]
    crowd = bpy.data.objects.new('CrowdRows', crowd_mesh)
    bpy.context.collection.objects.link(crowd)
    material = bpy.data.materials.new('M_crowd_seated')
    material.use_nodes = True
    tex = material.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(str(args.crowd_atlas.resolve()))
    crowd_mesh.materials.append(material)
    # Asset conversion preserves the existing native atlas pixels verbatim.
    import shutil
    shutil.copyfile(args.crowd_atlas, work/'textures/crowd_seated.png')
    report['textures']['crowd_seated'] = {'alpha_range': [0,255],
        'max_texture_size': 1024, 'source': 'owned native seated audience atlas'}
    report['crowd'] = {'authored_rows': len(faces), 'fitted_rows': len(kept_faces),
                       'triangles': 2*len(kept_faces), 'animated': args.crowd_flipbook}
    report['crowd_flipbook'] = args.crowd_flipbook
    bpy.ops.object.select_all(action='DESELECT')
    shell.select_set(True)
    crowd.select_set(True)
    bpy.context.view_layer.objects.active = shell
    bpy.ops.object.join()
# Deduplicate material slots without combining vertices/UV seams.
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.object.mode_set(mode="OBJECT")
used, remap = [], {}
old = list(shell.data.materials)
active_slots = {p.material_index for p in shell.data.polygons}
for i, material in enumerate(old):
    if i not in active_slots:
        continue
    if material not in used:
        used.append(material)
    remap[i] = used.index(material)
indices = [remap[p.material_index] for p in shell.data.polygons]
shell.data.materials.clear()
for material in used:
    shell.data.materials.append(material)
for polygon, index in zip(shell.data.polygons, indices):
    polygon.material_index = index
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 1.0
bpy.ops.export_scene.fbx(filepath=str(work / (stadium_key + 'Shell.fbx')),
    use_selection=True, object_types={"MESH"}, global_scale=1.0,
    apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
    axis_forward="-Y", axis_up="Z", use_mesh_modifiers=True,
    bake_anim=False, path_mode="ABSOLUTE", add_leaf_bones=False)
report["fbx"] = str(work / (stadium_key + 'Shell.fbx'))
report['close_camera_cutaway'] = True
report['source_winding'] = 'Fox clockwise converted to counter-clockwise before reduction'
report["material_slots"] = [m.name for m in used]
report["blender_bounds"] = [list(min(v.co[i] for v in shell.data.vertices) for i in range(3)),
                             list(max(v.co[i] for v in shell.data.vertices) for i in range(3))]
(work / "fbx.local.json").write_text(json.dumps(report, indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(work / (stadium_key + 'Shell.blend')))
print("PESNX_STADIUM_FBX_OK", len(shell.data.polygons), len(used))
