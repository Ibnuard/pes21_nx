"""Bake high-source self-shadow detail into a low opaque scalp colour atlas.

All lighting/projection work happens offline. Divide by the low surface's
illumination so broad directional lighting remains the existing shader's job.
No shader, normal-map sampler or material section is added to the runtime.
"""
import bpy
import numpy as np
from mathutils import Vector

from blender_realface_mobile import geometry
from blender_realface_source_quality import capture_normals
from blender_realface_native_hair_detail import fresh_pixels
from blender_fit_realface import runtime_matrix,vertex_weights


def relief(obj,source,texture,source_normals,native,cooked,folder):
    scene=bpy.context.scene;original_hidden={o:o.hide_render for o in scene.objects}
    p,t,uv=source;current,_,_=geometry(obj,native,cooked)
    determinant=runtime_matrix(obj,vertex_weights(obj,obj.data.vertices[0]),native,cooked).determinant()
    flip=determinant<0
    mesh=bpy.data.meshes.new('source_hair_offline_bake')
    mesh.from_pydata(p.tolist(),[],(t[:,::-1] if flip else t).tolist());mesh.update()
    layer=mesh.uv_layers.new(name='UVMap')
    for poly,coords in zip(mesh.polygons,uv[:,::-1] if flip else uv):
        poly.use_smooth=True
        for li,value in zip(poly.loop_indices,coords):layer.data[li].uv=value
    mesh.normals_split_custom_set((source_normals[:,::-1] if flip else source_normals).reshape(-1,3))
    high=bpy.data.objects.new('offline_source_hair',mesh);scene.collection.objects.link(high)
    low=bpy.data.objects.new('offline_target_scalp',obj.data.copy());scene.collection.objects.link(low)
    for vertex,point in zip(low.data.vertices,current):vertex.co=point
    _,_,low_normals=capture_normals(obj,native,cooked)
    if flip:low.data.flip_normals()
    low.data.normals_split_custom_set((low_normals[:,::-1] if flip else low_normals).reshape(-1,3))
    lights=[]
    try:
        for o in original_hidden:o.hide_render=True
        for name,loc in (('hair_key',(35,45,205)),('hair_fill',(-35,20,185))):
            light=bpy.data.lights.new(name,'AREA');light.energy=18000;light.shape='DISK';light.size=40
            lamp=bpy.data.objects.new(name,light);scene.collection.objects.link(lamp);lights.append(lamp)
            lamp.location=loc;lamp.rotation_euler=(Vector((0,4,175))-lamp.location).to_track_quat('-Z','Y').to_euler()
        scene.world=bpy.data.worlds.new('offline_hair_neutral')
        scene.world.use_nodes=True
        scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.25,.25,.25,1)
        scene.world.node_tree.nodes['Background'].inputs[1].default_value=.7
        scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.transparent_max_bounces=64
        material=bpy.data.materials.new('offline_original_hair');material.use_nodes=True
        tree=material.node_tree;shader=tree.nodes['Principled BSDF'];shader.inputs['Roughness'].default_value=.8
        tex=tree.nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(texture),check_existing=False)
        tex.image.alpha_mode='CHANNEL_PACKED';tree.links.new(tex.outputs['Color'],shader.inputs['Base Color'])
        clip=tree.nodes.new('ShaderNodeMath');clip.operation='GREATER_THAN';clip.inputs[1].default_value=.3333
        tree.links.new(tex.outputs['Alpha'],clip.inputs[0]);tree.links.new(clip.outputs[0],shader.inputs['Alpha'])
        high.data.materials.clear();high.data.materials.append(material)
        target_mat=bpy.data.materials.new('offline_white_scalp');target_mat.use_nodes=True
        target_mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(1,1,1,1)
        target_mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.8
        node=target_mat.node_tree.nodes.new('ShaderNodeTexImage');target_mat.node_tree.nodes.active=node
        low.data.materials.clear();low.data.materials.append(target_mat)
        lit=bpy.data.images.new('source_hair_lighting',128,128,alpha=True,float_buffer=True)
        illumination=bpy.data.images.new('target_hair_illumination',128,128,alpha=True,float_buffer=True)
        node.image=lit
        bpy.ops.object.select_all(action='DESELECT');high.select_set(True);low.select_set(True)
        bpy.context.view_layer.objects.active=low
        settings=scene.render.bake;settings.use_selected_to_active=True;settings.use_cage=False
        settings.cage_extrusion=2.5;settings.max_ray_distance=5.;settings.margin=3
        settings.use_pass_direct=True;settings.use_pass_indirect=True;settings.use_pass_color=True
        bpy.ops.object.bake(type='DIFFUSE')
        high.hide_render=True;high.select_set(False);settings.use_selected_to_active=False;node.image=illumination
        bpy.ops.object.bake(type='DIFFUSE')
        def values(image):
            array=np.empty(len(image.pixels),np.float32);image.pixels.foreach_get(array)
            return array.reshape((128,128,4))
        shaded=values(lit);light=values(illumination);original=fresh_pixels(folder/'hair-shell.png')
        luma=np.array([.2126,.7152,.0722]);expected=(original[:,:,:3]*light[:,:,:3])@luma
        ratio=np.clip((shaded[:,:,:3]@luma)/np.maximum(expected,.0005),.35,2.5)
        valid=(shaded[:,:,3]>.5)&(light[:,:,:3].max(axis=2)>.02)&(expected>.0005)
        original[valid,:3]*=ratio[valid,None];original[:,:,3]=1.
        result=bpy.data.images.new('hair_baked_source_self_shadow',128,128,alpha=False)
        result.pixels.foreach_set(original.ravel());result.filepath_raw=str(folder/'hair-shell.png')
        result.file_format='PNG';result.save()
        return dict(method='source_to_scalp_diffuse_relief_ratio',samples=16,baked_texels=int(valid.sum()),
            contrast_range=[.35,2.5],runtime_lights_added=0,visual_approval=False)
    finally:
        for o in (high,low,*lights):bpy.data.objects.remove(o,do_unlink=True)
        for o,hidden in original_hidden.items():o.hide_render=hidden
