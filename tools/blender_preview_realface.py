"""Render an explicit prepared recipe for visual QA; never a device screenshot."""
import json
from pathlib import Path
import sys
import shutil
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals
from blender_fit_realface import vertex_weights, runtime_matrix


def render(recipe, output):
    output = Path(output).resolve()
    native = rig_globals(json.loads(Path(recipe['native_rig']).read_text()))
    cooked = rig_globals(json.loads(Path(recipe['cooked_rig']).read_text()))
    profile = recipe.get('ue') or json.loads((Path(recipe['folder']) / 'ue-profile.json').read_text(encoding='utf-8'))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.scale_length = .01
    for part in recipe.get('parts', ('face', 'hair')):
        if part not in ('face', 'hair'):
            raise ValueError('Unknown preview part: ' + str(part))
        before = set(scene.objects)
        inputs = output.parent / (output.stem + '-inputs')
        inputs.mkdir(parents=True, exist_ok=True)
        copied = inputs / (part + '.fbx')
        shutil.copy2(profile[part + '_fbx'], copied)
        bpy.ops.import_scene.fbx(filepath=str(copied), use_anim=False)
        for obj in set(scene.objects) - before:
            if obj.type != 'MESH': continue
            names = [m.name for m in obj.data.materials]
            transforms = [runtime_matrix(obj, vertex_weights(obj, v), native, cooked) for v in obj.data.vertices]
            points = [m @ v.co for m,v in zip(transforms,obj.data.vertices)]
            normals = {}
            for poly in obj.data.polygons:
                for li in poly.loop_indices:
                    vi=obj.data.loops[li].vertex_index
                    normals[(poly.index,vi)]=(transforms[vi].to_3x3().inverted().transposed() @
                                             obj.data.corner_normals[li].vector).normalized()
            for v, p in zip(obj.data.vertices, points): v.co = p
            obj.parent = None
            obj.matrix_world = Matrix.Identity(4)
            obj.modifiers.clear()
            mirrored=[m.to_3x3().determinant()<0 for m in transforms]
            if len(set(mirrored))!=1:raise ValueError('Mixed bind-space orientation in preview')
            if mirrored[0]:obj.data.flip_normals()
            obj.data.normals_split_custom_set([normals[(poly.index,obj.data.loops[li].vertex_index)]
                                               for poly in obj.data.polygons for li in poly.loop_indices])
            normalize = lambda n: n.replace('_00', '.00')
            # Some sources reuse fox_skin_mat for a scalp surface in the hair
            # FBX. Classify within the current part, as the converter does;
            # otherwise a source face can be previewed with the hair texture.
            skin_names = profile['skin_materials'] if part == 'face' else profile.get('hair_skin_materials', [])
            skin = any(normalize(n) in {normalize(v) for v in skin_names} for n in names)
            hair = not skin and any(normalize(n) in {normalize(v) for v in profile.get('hair_materials', [])} for n in names)
            eye = any(normalize(n) == normalize(profile['eye_material']) for n in names)
            if sum((skin,hair,eye))!=1:
                raise ValueError('Unclassified/ambiguous preview material in '+part+': '+str(names))
            texture = profile['native_eye_texture'] if eye else profile['hair_texture'] if hair else profile['face_texture']
            texture = recipe.get('texture_overrides', {}).get('eye' if eye else 'hair' if hair else 'skin', texture)
            mat = bpy.data.materials.new('preview')
            mat.use_nodes = True
            tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
            tex.image = bpy.data.images.load(texture)
            tex.image.alpha_mode = 'CHANNEL_PACKED'
            shader = mat.node_tree.nodes['Principled BSDF']
            shader.inputs['Roughness'].default_value = .8
            mat.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
            if part=='face' and recipe.get('holdout_face'):
                holdout=mat.node_tree.nodes.new('ShaderNodeHoldout')
                path=mat.node_tree.nodes.new('ShaderNodeLightPath')
                mix=mat.node_tree.nodes.new('ShaderNodeMixShader')
                mat.node_tree.links.new(path.outputs['Is Camera Ray'],mix.inputs[0])
                mat.node_tree.links.new(shader.outputs[0],mix.inputs[1])
                mat.node_tree.links.new(holdout.outputs[0],mix.inputs[2])
                mat.node_tree.links.new(mix.outputs[0],mat.node_tree.nodes['Material Output'].inputs['Surface'])
            if not hair and recipe.get('diagnostic_normal_texture'):
                # Diagnostic only: the shipped parent samples its common
                # normal atlas using the same UV0 as the remapped diffuse.
                # Reconstruct Z from RG as its GLES shader does. This is not
                # an emulation of the game's complete lighting pipeline.
                import numpy as np
                image = bpy.data.images.load(recipe['diagnostic_normal_texture'])
                image.colorspace_settings.name = 'Non-Color'
                pixels = np.empty(len(image.pixels), np.float32)
                image.pixels.foreach_get(pixels)
                pixels = pixels.reshape((-1, 4))
                xy = pixels[:, :2] * 2 - 1
                pixels[:, 2] = np.sqrt(np.maximum(0, 1-(xy*xy).sum(axis=1))) * .5 + .5
                image.pixels.foreach_set(pixels.ravel())
                normal_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
                normal_tex.image = image
                # PNG loading and the existing FBX UV conversion already
                # account for the cooked texture's top-to-bottom row order.
                normal = mat.node_tree.nodes.new('ShaderNodeNormalMap')
                mat.node_tree.links.new(normal_tex.outputs['Color'], normal.inputs['Color'])
                mat.node_tree.links.new(normal.outputs['Normal'], shader.inputs['Normal'])
            if hair:
                if recipe.get('diagnostic_hair_normal_texture'):
                    normal_tex=mat.node_tree.nodes.new('ShaderNodeTexImage')
                    normal_tex.image=bpy.data.images.load(recipe['diagnostic_hair_normal_texture'])
                    normal_tex.image.colorspace_settings.name='Non-Color'
                    normal=mat.node_tree.nodes.new('ShaderNodeNormalMap')
                    normal.space=recipe.get('diagnostic_hair_normal_space','WORLD')
                    mat.node_tree.links.new(normal_tex.outputs['Color'],normal.inputs['Color'])
                    mat.node_tree.links.new(normal.outputs['Normal'],shader.inputs['Normal'])
                # The shipped mobile material is alpha-tested, not translucent.
                # Fractional transparency plus Cycles' short ray-depth default
                # made overlapping invisible cards render as dark face shards.
                if recipe.get('hair_alpha_mode', 'masked') == 'fractional_reference':
                    mat.node_tree.links.new(tex.outputs['Alpha'], shader.inputs['Alpha'])
                else:
                    cutoff = mat.node_tree.nodes.new('ShaderNodeMath')
                    cutoff.operation = 'GREATER_THAN'
                    cutoff.inputs[1].default_value = .333
                    mat.node_tree.links.new(tex.outputs['Alpha'], cutoff.inputs[0])
                    mat.node_tree.links.new(cutoff.outputs[0], shader.inputs['Alpha'])
            obj.data.materials.clear()
            obj.data.materials.append(mat)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = recipe.get('samples',12)
    scene.cycles.transparent_max_bounces = recipe.get('transparent_bounces',64)
    scene.render.resolution_x = recipe.get('resolution',480)
    scene.render.resolution_y = recipe.get('resolution',480)
    scene.render.film_transparent = bool(recipe.get('holdout_face'))
    scene.render.resolution_percentage = 100
    scene.world = bpy.data.worlds.new('neutral')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (.25, .25, .25, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = .7
    scene.view_settings.view_transform = 'Standard'
    target = Vector(recipe.get('target',(0,4,170)))
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
    data.ortho_scale = recipe.get('ortho_scale',27)
    camera.location = target + Vector(recipe.get('view_offset', (0, 90, 0)))
    camera.rotation_euler = (target - camera.location).to_track_quat('-Z', 'Y').to_euler()
    if recipe.get('view_basis'):
        camera.rotation_euler=Matrix(recipe['view_basis']).transposed().to_euler()
    output.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(output)
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    args = sys.argv[sys.argv.index('--') + 1:]
    recipe = json.loads(Path(args[0]).read_text(encoding='utf-8'))
    if isinstance(recipe, list):
        for target in recipe:
            render(target['recipe'], Path(target['output']))
    else:
        render(recipe, Path(args[1]))
