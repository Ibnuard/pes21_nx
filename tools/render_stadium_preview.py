"""Offline inspection of a converted shell, its crowd and protected pitch."""
import argparse,sys,math,json
from pathlib import Path
import bpy
from mathutils import Vector

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--blend',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--view',choices=['bowl','roof','near','far'],default='bowl')
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
bpy.ops.wm.open_mainfile(filepath=str(a.blend.resolve()))
shell=next(o for o in bpy.context.scene.objects if o.type=='MESH')
profile_path=a.blend.parent/'fbx.local.json'
profile=json.loads(profile_path.read_text()) if profile_path.is_file() else {}
location={'roof':(0,-2,200),'bowl':(78,-67,36),'near':(0,-68,28),'far':(0,-16,28)}[a.view]
if a.view!='roof':
    # Offline approximation of the shipped pixel cutaway, only for this render.
    # Use triangle centres to remove foreground faces; never save the modified mesh.
    import bmesh
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from stadium_material_policy import camera_visible
    def ue(v):return (v[0]*100,-v[1]*100,v[2]*100)
    bm=bmesh.new();bm.from_mesh(shell.data)
    hidden=[f for f in bm.faces if not camera_visible(ue(f.calc_center_median()),ue(location))]
    bmesh.ops.delete(bm,geom=hidden,context='FACES');bm.to_mesh(shell.data);bm.free()
for mat in shell.data.materials:
    if not mat or not mat.use_nodes:continue
    img=next((n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image),None)
    # Rebuild the UE unlit hemisphere material. Imported glTF preview graphs
    # can include unrelated Fox factors; those are not used by our UE cook.
    mat.node_tree.nodes.clear()
    nodes=mat.node_tree.nodes;links=mat.node_tree.links
    output=nodes.new('ShaderNodeOutputMaterial')
    emit=nodes.new('ShaderNodeEmission')
    geometry=nodes.new('ShaderNodeNewGeometry')
    dot=nodes.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT'
    dot.inputs[1].default_value=(.25,-.35,.90)
    links.new(geometry.outputs['Normal'],dot.inputs[0])
    clamp=nodes.new('ShaderNodeClamp');links.new(dot.outputs['Value'],clamp.inputs[0])
    shade=nodes.new('ShaderNodeMath');shade.operation='MULTIPLY_ADD'
    shade.inputs[1].default_value=.3;shade.inputs[2].default_value=.65
    links.new(clamp.outputs[0],shade.inputs[0]);links.new(shade.outputs[0],emit.inputs['Strength'])
    if profile.get('baked_hemisphere'):
        baked=nodes.new('ShaderNodeVertexColor');baked.layer_name='ShellHemisphere'
        links.new(baked.outputs['Color'],emit.inputs['Strength'])
    emit.inputs['Color'].default_value=(.32,.32,.30,1)
    links.new(emit.outputs[0],output.inputs['Surface'])
    if img:
        tex=nodes.new('ShaderNodeTexImage');tex.image=img
        links.new(tex.outputs['Color'],emit.inputs['Color'])
        transparent=nodes.new('ShaderNodeBsdfTransparent')
        mask=nodes.new('ShaderNodeMath');mask.operation='GREATER_THAN';mask.inputs[1].default_value=.4
        mask_file=profile.get('mask_files',{}).get(mat.name)
        mask_tex=None
        if mask_file:
            mask_tex=nodes.new('ShaderNodeTexImage');mask_tex.image=bpy.data.images.load(mask_file)
            mask_tex.image.colorspace_settings.name='Non-Color'
            links.new(mask_tex.outputs['Color'],mask.inputs[0])
        else:
            links.new(tex.outputs['Alpha'],mask.inputs[0])
        mix=nodes.new('ShaderNodeMixShader');links.new(mask.outputs[0],mix.inputs[0])
        links.new(transparent.outputs[0],mix.inputs[1]);links.new(emit.outputs[0],mix.inputs[2])
        links.new(mix.outputs[0],output.inputs['Surface'])
        if 'crowd_seated' in mat.name:
            uv=mat.node_tree.nodes.new('ShaderNodeTexCoord')
            mapping=mat.node_tree.nodes.new('ShaderNodeVectorMath');mapping.operation='MULTIPLY'
            mapping.inputs[1].default_value=(.5,63./1024,1)
            offset=mat.node_tree.nodes.new('ShaderNodeVectorMath');offset.operation='ADD'
            offset.inputs[1].default_value=(0,.5/1024,0)
            mat.node_tree.links.new(uv.outputs['UV'],mapping.inputs[0])
            mat.node_tree.links.new(mapping.outputs[0],offset.inputs[0])
            mat.node_tree.links.new(offset.outputs[0],tex.inputs['Vector'])
            if mask_tex:links.new(offset.outputs[0],mask_tex.inputs['Vector'])
        elif mat.name in profile.get('atlas',{}).get('materials',[]):
            # Same fragment UV wrap as the cooked graph, with Blender's V-up
            # image convention (UE uses V-down). Do not wrap per vertex.
            uv=nodes.new('ShaderNodeUVMap');uv.uv_map=shell.data.uv_layers[0].name
            tile=nodes.new('ShaderNodeUVMap');tile.uv_map='AtlasTile'
            split=nodes.new('ShaderNodeSeparateXYZ');links.new(tile.outputs[0],split.inputs[0])
            def math_node(operation,first=None,second=None):
                node=nodes.new('ShaderNodeMath');node.operation=operation
                for i,value in enumerate((first,second)):
                    if value is None:continue
                    if isinstance(value,(float,int)):node.inputs[i].default_value=value
                    else:links.new(value,node.inputs[i])
                return node.outputs[0]
            row=math_node('FLOOR',math_node('MULTIPLY',split.outputs['X'],.25))
            col=math_node('SUBTRACT',split.outputs['X'],math_node('MULTIPLY',row,4))
            offset=nodes.new('ShaderNodeCombineXYZ')
            links.new(math_node('ADD',math_node('MULTIPLY',col,256),8),offset.inputs['X'])
            links.new(math_node('ADD',math_node('MULTIPLY',math_node('SUBTRACT',3,row),256),8),offset.inputs['Y'])
            frac=nodes.new('ShaderNodeVectorMath');frac.operation='FRACTION';links.new(uv.outputs[0],frac.inputs[0])
            scale=nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs['Scale'].default_value=240
            links.new(frac.outputs[0],scale.inputs[0])
            add=nodes.new('ShaderNodeVectorMath');add.operation='ADD'
            links.new(scale.outputs[0],add.inputs[0]);links.new(offset.outputs[0],add.inputs[1])
            final=nodes.new('ShaderNodeVectorMath');final.operation='SCALE';final.inputs['Scale'].default_value=1./1024
            links.new(add.outputs[0],final.inputs[0]);links.new(final.outputs[0],tex.inputs['Vector'])
            if mask_tex:links.new(final.outputs[0],mask_tex.inputs['Vector'])
        if not profile.get('material_policies',{}).get(mat.name,{}).get('two_sided',True):
            facing=nodes.new('ShaderNodeMixShader')
            links.new(geometry.outputs['Backfacing'],facing.inputs[0])
            links.new(mix.outputs[0],facing.inputs[1]);links.new(transparent.outputs[0],facing.inputs[2])
            links.new(facing.outputs[0],output.inputs['Surface'])
        mat.surface_render_method='DITHERED'
# A dimensioned reference plane is authored here, not the game's pitch asset.
bpy.ops.mesh.primitive_plane_add(size=2,location=(0,0,.025))
pitch=bpy.context.object;pitch.scale=(52.5,34,1)
green=bpy.data.materials.new('ReferencePitch');green.diffuse_color=(.08,.23,.07,1)
pitch.data.materials.append(green)
for x,y,sx,sy in ((0,-34,52.5,.12),(0,34,52.5,.12),(-52.5,0,.12,34),(52.5,0,.12,34),(0,0,.12,34)):
    bpy.ops.mesh.primitive_plane_add(size=2,location=(x,y,.03));bpy.context.object.scale=(sx,sy,1)
    white=bpy.data.materials.get('PitchWhite') or bpy.data.materials.new('PitchWhite')
    white.diffuse_color=(.8,.9,.8,1);bpy.context.object.data.materials.append(white)
target=Vector((0,-20,0) if a.view=='near' else (0,32,0) if a.view=='far' else (0,0,0 if a.view=='roof' else 5))
bpy.ops.object.camera_add(location=location)
camera=bpy.context.object;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=325 if a.view=='roof' else 165
if a.view in ('near','far'):
    camera.data.type='PERSP';camera.data.lens=30
scene=bpy.context.scene;scene.camera=camera
scene.render.engine='CYCLES';scene.cycles.samples=12;scene.cycles.use_denoising=True
scene.render.resolution_x=1000;scene.render.resolution_y=750;scene.render.resolution_percentage=100
if a.view in ('near','far'):scene.render.resolution_y=563
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.72,.85,1)
scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
bpy.ops.object.light_add(type='SUN',location=(0,0,100));bpy.context.object.rotation_euler=(.3,-.4,-.3);bpy.context.object.data.energy=2
scene.view_settings.view_transform='Standard';scene.render.image_settings.file_format='PNG'
a.output.parent.mkdir(parents=True,exist_ok=True);scene.render.filepath=str(a.output.resolve())
bpy.ops.render.render(write_still=True)
