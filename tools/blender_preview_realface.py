"""Render an explicit prepared recipe for visual QA; never a device screenshot."""
import json
from pathlib import Path
import sys
import shutil
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals, rebuild_smooth_normals
from blender_fit_realface import vertex_weights, runtime_matrix


def render(recipe, output):
    output = Path(output).resolve()
    native = rig_globals(json.loads(Path(recipe['native_rig']).read_text()))
    cooked = rig_globals(json.loads(Path(recipe['cooked_rig']).read_text()))
    profile = recipe.get('ue') or json.loads((Path(recipe['folder']) / 'ue-profile.json').read_text(encoding='utf-8'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.scale_length = .01
    for part in ('face', 'hair'):
        before = set(scene.objects)
        inputs = output.parent / (output.stem + '-inputs')
        inputs.mkdir(parents=True, exist_ok=True)
        copied = inputs / (part + '.fbx')
        shutil.copy2(profile[part + '_fbx'], copied)
        bpy.ops.import_scene.fbx(filepath=str(copied), use_anim=False)
        for obj in set(scene.objects) - before:
            if obj.type != 'MESH': continue
            names = [m.name for m in obj.data.materials]
            points = [runtime_matrix(obj, vertex_weights(obj, v), native, cooked) @ v.co for v in obj.data.vertices]
            for v, p in zip(obj.data.vertices, points): v.co = p
            obj.parent = None
            obj.matrix_world = Matrix.Identity(4)
            obj.modifiers.clear()
            obj.data.flip_normals()
            rebuild_smooth_normals(obj)
            hair = any(n.startswith('rf_hair') for n in names)
            texture = profile['native_eye_texture'] if 'batch_eye_mat' in names else profile['hair_texture'] if hair else profile['face_texture']
            mat = bpy.data.materials.new('preview')
            mat.use_nodes = True
            tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
            tex.image = bpy.data.images.load(texture)
            tex.image.alpha_mode = 'CHANNEL_PACKED'
            shader = mat.node_tree.nodes['Principled BSDF']
            shader.inputs['Roughness'].default_value = .8
            mat.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
            if hair: mat.node_tree.links.new(tex.outputs['Alpha'], shader.inputs['Alpha'])
            obj.data.materials.clear()
            obj.data.materials.append(mat)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 12
    scene.render.resolution_x = 480
    scene.render.resolution_y = 480
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new('neutral')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.25, .25, .25, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .7
    scene.view_settings.view_transform = 'Standard'
    target = Vector((0, 4, 170))
    for loc in ((35, 45, 205), (-35, 20, 185)):
        data = bpy.data.lights.new('softbox', 'AREA')
        data.energy = 18000
        data.shape = 'DISK'
        data.size = 40
        obj = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(obj)
        obj.location = loc
        obj.rotation_euler = (target - obj.location).to_track_quat('-Z', 'Y').to_euler()
    data = bpy.data.cameras.new('camera')
    camera = bpy.data.objects.new('camera', data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    data.type = 'ORTHO'
    data.ortho_scale = 27
    camera.location = target + Vector((0, 90, 0))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    output.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    render(json.loads(Path(args[0]).read_text(encoding='utf-8')), Path(args[1]))
