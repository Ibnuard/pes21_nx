"""UE4.22 commandlet: import two verified, rigid cinematic props in isolation.

The caller supplies PESNX_CINEMATIC_IMPORT_PROFILE. Converted proprietary inputs
remain in the caller's isolated local project, never the active runtime. This
does not install hooks or replace existing assets. Python 2.7 syntax is
intentional for the editor bundled with this runtime.
"""
import json
import os
import unreal


def assign_rigid_materials(mesh, materials):
    # StaticMaterials is not reflected for Python in UE4.22. These two rigid
    # props each contain one material/LOD0 section. Use its reflected APIs;
    # the independent cooked audit checks the final section/material set.
    if mesh.get_num_sections(0) != len(materials):
        raise RuntimeError('Unexpected imported mesh section count')
    assigned = {}
    for name in materials:
        index = mesh.get_material_index(name)
        if index < 0 or index in assigned.values():
            raise RuntimeError('Missing or ambiguous imported material slot: ' + name)
        mesh.set_material(index, materials[name])
        actual = mesh.get_material(index)
        if actual is None or actual.get_path_name() != materials[name].get_path_name():
            raise RuntimeError('Material assignment did not persist: ' + name)
        assigned[name] = index
    if sorted(assigned.values()) != list(range(len(materials))):
        raise RuntimeError('Unexpected material slot indices')
    return assigned


def main():
    if not unreal.SystemLibrary.get_engine_version().startswith('4.22.'):
        raise RuntimeError('Cinematic props require the audited UE4.22 cooker')
    with open(os.environ['PESNX_CINEMATIC_IMPORT_PROFILE'], 'r') as stream:
        profile = json.load(stream)
    if profile['schema'] != 'PESNX_CINEMATIC_IMPORT_V1':
        raise RuntimeError('Wrong import contract')
    if [p['key'] for p in profile['props']] != ['cup_int_hi', 'platform_cmn']:
        raise RuntimeError('Unsupported prop set')
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    library = unreal.MaterialEditingLibrary
    report = {'schema': 'PESNX_CINEMATIC_UE_IMPORT_V1', 'props': [],
              'runtime_installed': False, 'hardware_tested': False}

    def absent(path):
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            raise RuntimeError('Refusing to replace an existing asset: ' + path)

    def scalar(material, value, target):
        node = library.create_material_expression(material, unreal.MaterialExpressionConstant)
        node.set_editor_property('r', value)
        if not library.connect_material_property(node, '', target):
            raise RuntimeError('Scalar material connection failed')

    for prop in profile['props']:
        key = prop['key']
        destination = '/Game/Assets/FootballNX/FixDemo/' + key
        expected_path = destination + '/' + key + '.' + key
        if prop['target_object_path'] != expected_path:
            raise RuntimeError('Unexpected target namespace')
        materials = {}
        asset_names = [key]
        for slot in prop['materials']:
            texture_name, material_name = 'T_' + slot['name'], 'M_' + slot['name']
            for name in (texture_name, material_name):
                absent(destination + '/' + name)
            task = unreal.AssetImportTask()
            for name, value in {'filename': slot['base_texture'], 'destination_path': destination,
                                'destination_name': texture_name, 'automated': True,
                                'save': True, 'replace_existing': False}.items():
                task.set_editor_property(name, value)
            asset_tools.import_asset_tasks([task])
            texture = unreal.load_asset(destination + '/' + texture_name)
            if texture is None:
                raise RuntimeError('Missing imported base texture')
            texture.set_editor_property('srgb', True)
            texture.set_editor_property('max_texture_size', 512)
            texture.set_editor_property('compression_no_alpha', True)
            unreal.EditorAssetLibrary.save_asset(texture.get_path_name())
            material = asset_tools.create_asset(material_name, destination, unreal.Material,
                                               unreal.MaterialFactoryNew())
            if material is None:
                raise RuntimeError('Material creation failed')
            material.set_editor_property('blend_mode', unreal.BlendMode.BLEND_OPAQUE)
            material.set_editor_property('two_sided', False)
            material.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_DEFAULT_LIT)
            colour = library.create_material_expression(material, unreal.MaterialExpressionTextureSample)
            colour.set_editor_property('texture', texture)
            colour.set_editor_property('sampler_type', unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
            if not library.connect_material_property(colour, 'RGB', unreal.MaterialProperty.MP_BASE_COLOR):
                raise RuntimeError('Base colour connection failed')
            # Explicit preview approximation, not a guessed decoding of Fox's
            # packed normal/specular maps. Keep that limitation in the report.
            scalar(material, slot['metallic'], unreal.MaterialProperty.MP_METALLIC)
            scalar(material, slot['roughness'], unreal.MaterialProperty.MP_ROUGHNESS)
            library.recompile_material(material)
            unreal.EditorAssetLibrary.save_asset(material.get_path_name())
            materials[slot['name']] = material
            asset_names.extend((texture_name, material_name))

        absent(destination + '/' + key)
        options = unreal.FbxImportUI()
        for name, value in {'import_as_skeletal': False, 'import_mesh': True,
                            'import_materials': False, 'import_textures': False,
                            'import_animations': False}.items():
            options.set_editor_property(name, value)
        mesh_options = options.get_editor_property('static_mesh_import_data')
        for name, value in {'combine_meshes': True, 'auto_generate_collision': False,
                            'generate_lightmap_u_vs': False,
                            'normal_import_method': unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS}.items():
            mesh_options.set_editor_property(name, value)
        task = unreal.AssetImportTask()
        for name, value in {'filename': prop['fbx'], 'destination_path': destination,
                            'destination_name': key, 'automated': True, 'save': True,
                            'replace_existing': False, 'options': options}.items():
            task.set_editor_property(name, value)
        asset_tools.import_asset_tasks([task])
        mesh = unreal.load_asset(destination + '/' + key)
        if mesh is None or mesh.get_class().get_name() != 'StaticMesh':
            raise RuntimeError('A rigid StaticMesh was not imported')
        assigned = assign_rigid_materials(mesh, materials)
        bounds = mesh.get_bounds()
        origin, extent = bounds.origin, bounds.box_extent
        actual = [[getattr(origin, axis) - getattr(extent, axis) for axis in ('x', 'y', 'z')],
                  [getattr(origin, axis) + getattr(extent, axis) for axis in ('x', 'y', 'z')]]
        if any(abs(actual[i][j] - prop['expected_ue_bounds_cm'][i][j]) > 0.02
               for i in range(2) for j in range(3)):
            raise RuntimeError('Unreal axes/centimetre scale changed: ' + str(actual))
        unreal.EditorAssetLibrary.save_asset(mesh.get_path_name())
        report['props'].append({'key': key, 'object_path': mesh.get_path_name(),
                                'bounds_cm': actual, 'material_slots': assigned,
                                'asset_names': asset_names})
    report['status'] = 'imported'
    report['material_policy'] = 'opaque base colour plus explicit scalar PBR approximation; packed Fox maps unused'
    with open(profile['report'], 'w') as stream:
        json.dump(report, stream, indent=2)
    unreal.log('PESNX_CINEMATIC_UE_IMPORT_OK')


if __name__ == '__main__':
    main()
