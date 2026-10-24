"""Blender: restore reviewed source backing in an existing local shell.

Uses a reviewed local recipe. Existing geometry/UVs/normals/colour survive;
the added faces reuse a reviewed opaque tile in an existing atlas material.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stadium_backing import load_selection


def restore(recipe_path, output):
    recipe = json.loads(Path(recipe_path).read_text())
    profile_path = Path(recipe['profile']).resolve(strict=True)
    profile = json.loads(profile_path.read_text())
    backing, sources = [], []
    for item in recipe['sources']:
        rows, source = load_selection(item['source_gltf'], **item['selection'])
        backing.extend(rows);sources.append(source)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Use a fresh backing output directory')
    if (recipe['maximum_total_triangles'] > 24560 or
            profile['key'] != recipe['key'] or not profile.get('vertex_camera_cull')):
        raise ValueError('Unreviewed shell contract')
    blend = Path(profile['fbx']).with_suffix('.blend')
    if hashlib.sha256(blend.read_bytes()).hexdigest() != recipe['base_blend_sha256']:
        raise ValueError('Base shell fingerprint changed')
    atlas_path=Path(recipe['atlas'])
    if hashlib.sha256(atlas_path.read_bytes()).hexdigest()!=recipe['atlas_sha256']:
        raise ValueError('Backing atlas fingerprint changed')
    atlas = json.loads(atlas_path.read_text())
    tile = atlas['mapping'][recipe['atlas_source_material']]
    material = tile['material']
    if ((tile.get('masked') and tile.get('coverage')!='all-above-native-threshold') or
            profile['material_policies'][material].get('two_sided')):
        raise ValueError('Backing must reuse a one-sided tile with reviewed opaque coverage')
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    obj = bpy.data.objects[profile['key']+'Shell'];old = obj.data
    if len(old.uv_layers) != 5 or any(len(p.vertices) != 3 for p in old.polygons):
        raise ValueError('Base shell layout changed')
    slots = [m.name for m in old.materials]
    # A reclaimed atlas tile must also be unused in the actual base blend,
    # not only in the independent cooked export used during preparation.
    if 'reclaimed_tile_proof' in recipe:
        live={round(old.uv_layers[1].data[i].uv.x) for p in old.polygons
              if slots[p.material_index]==material for i in p.loop_indices}
        if tile['tile'] in live or live!=set(recipe['reclaimed_tile_proof']['live_tiles']):
            raise ValueError('Backing atlas tile is referenced by base geometry')
    old_count = len(old.polygons)
    crowd = sum(1 for p in old.polygons if slots[p.material_index] == 'M_crowd_seated')
    if crowd != profile['crowd']['triangles'] or old_count+len(backing) > recipe['maximum_total_triangles']:
        raise ValueError('Backing exceeds stadium/crowd budget')
    positions = [tuple(v.co) for v in old.vertices]
    faces = [tuple(p.vertices) for p in old.polygons]
    slots_by_face = [p.material_index for p in old.polygons]
    smooth = [p.use_smooth for p in old.polygons]
    normals = [tuple(n.vector) for n in old.corner_normals]
    uv = [[tuple(v.uv) for v in layer.data] for layer in old.uv_layers]
    colours = [[tuple(v.color) for v in layer.data] for layer in old.color_attributes]
    if len(colours) != 1 or old.color_attributes[0].domain != 'CORNER':
        raise ValueError('Unreviewed shell colour layout')
    max_cluster = max(v[1] for v in uv[1])
    for i, row in enumerate(backing):
        # Native Fox Y-up -> the established Blender (X,-Z,Y) metre basis.
        points = [(p[0], -p[2], p[1]) for p in row['positions']]
        normal = np.array((row['normal'][0], -row['normal'][2], row['normal'][1]))
        offset = len(positions);positions.extend(points);faces.append((offset,offset+1,offset+2))
        slots_by_face.append(slots.index(material));smooth.append(False)
        normals.extend([tuple(normal)]*3)
        light = .65+.30*max(0., min(1., float(normal @ np.array((.25,-.35,.90)))))
        colours[0].extend([(light,light,light,1.)]*3)
        p = np.array(points);centre=(p.min(0)+p.max(0))*.5
        extent=(p.max(0)-p.min(0))*50+32
        packed=np.array((centre[0]*100,-centre[1]*100,centre[2]*100,*extent))/32768
        uv[0].extend(row['uv'])
        values=[(tile['tile'],max_cluster+i+1),
                (packed[0],1-packed[1]),(packed[2],1-packed[3]),(packed[4],1-packed[5])]
        for channel,value in zip(uv[1:],values):channel.extend([tuple(value)]*3)
    mesh=bpy.data.meshes.new(profile['key']+'BackedShell')
    mesh.from_pydata(positions,[],faces);mesh.update()
    for mat in old.materials:mesh.materials.append(mat)
    for p,slot,sm in zip(mesh.polygons,slots_by_face,smooth):p.material_index=slot;p.use_smooth=sm
    for original,values in zip(old.uv_layers,uv):
        layer=mesh.uv_layers.new(name=original.name);layer.data.foreach_set('uv',np.array(values,dtype=np.float32).ravel())
    mesh.normals_split_custom_set(normals)
    for original,values in zip(old.color_attributes,colours):
        layer=mesh.color_attributes.new(name=original.name,type=original.data_type,domain=original.domain)
        layer.data.foreach_set('color',np.array(values,dtype=np.float32).ravel())
        mesh.color_attributes.active_color=layer
    mesh.uv_layers.active_index=0
    # Check existing positions, material indices, UVs and colours before export.
    assert [tuple(v.co) for v in mesh.vertices[:len(old.vertices)]] == [tuple(v.co) for v in old.vertices]
    assert [tuple(p.vertices) for p in mesh.polygons[:old_count]] == [tuple(p.vertices) for p in old.polygons]
    for a,b in zip(old.uv_layers,mesh.uv_layers):
        assert [tuple(v.uv) for v in a.data] == [tuple(v.uv) for v in b.data[:len(a.data)]]
    assert slots == [m.name for m in mesh.materials]
    for original,values in zip(old.color_attributes,mesh.color_attributes):
        assert [tuple(v.color) for v in original.data] == [tuple(v.color) for v in values.data[:len(original.data)]]
    for name,row in recipe.get('texture_overrides',{}).items():
        mat=mesh.materials[slots.index(name)]
        if mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type=='TEX_IMAGE' and node.image:
                    node.image=bpy.data.images.load(row['path'])
    obj.data=mesh
    output.mkdir(parents=True);(output/'textures').mkdir()
    shutil.copyfile(atlas_path,output/'textures/atlas.local.json')
    for name, row in recipe.get('texture_overrides', {}).items():
        if name not in profile['texture_files'] or hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Backing texture override fingerprint changed')
        profile['texture_files'][name]=row['path']
    for name,row in recipe.get('mask_overrides',{}).items():
        if name not in profile['mask_files'] or hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Backing mask override fingerprint changed')
        profile['mask_files'][name]=row['path']
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    fbx=output/(profile['key']+'Shell.fbx')
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,object_types={'MESH'},global_scale=1.,
        apply_unit_scale=True,apply_scale_options='FBX_SCALE_NONE',axis_forward='-Y',axis_up='Z',
        use_mesh_modifiers=True,bake_anim=False,path_mode='ABSOLUTE',add_leaf_bones=False,
        mesh_smooth_type='FACE',colors_type='LINEAR')
    profile['fbx']=str(fbx)
    profile['shell_triangles']['reduced']+=len(backing)
    profile['vertex_camera_cull']['clusters']+=len(backing)
    profile['blender_bounds']=[[min(v.co[i] for v in mesh.vertices) for i in range(3)],
                                [max(v.co[i] for v in mesh.vertices) for i in range(3)]]
    proof=dict(sources=sources,added_triangles=len(backing),
               preserved_base_triangles=old_count,crowd_triangles=crowd,total_triangles=len(faces),
               existing_materials_preserved=True,existing_uvs_preserved=True,
               atlas_material=material,atlas_tile=tile['tile'],hardware_tested=False)
    profile['exterior_backing']=proof
    (output/'fbx.local.json').write_text(json.dumps(profile,indent=2)+'\n')
    (output/'backing-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(fbx.with_suffix('.blend')))
    print('PESNX_STADIUM_BACKING',json.dumps(proof),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--recipe',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);restore(a.recipe,a.output)
