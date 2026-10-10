"""Author bounded CPU Cascade rain/snow in a local UE4.22 PesMobile project.

Run via -run=pythonscript; PESNX_WEATHER_TOOLS must point to this tools folder.
No source game assets are required. Only /Game/FootballNX/Weather is created.
"""
import os
import sys
sys.path.insert(0, os.environ['PESNX_WEATHER_TOOLS'])
import unreal
from ue_editor_properties import new, object_ptr, set_value, ref, refs, post_edit

assets = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.MaterialEditingLibrary
destination = '/Game/FootballNX/Weather'


def material(name, snow):
    m = unreal.load_asset(destination + '/' + name)
    if m is None:
        m = assets.create_asset(name, destination, unreal.Material, unreal.MaterialFactoryNew())
    lib.delete_all_material_expressions(m)
    m.set_editor_property('shading_model', unreal.MaterialShadingModel.MSM_UNLIT)
    # v9 regressed before the first weather report. Restore the v8 translucent
    # path as crash recovery while retaining the larger footprint and
    # full central opacity. It does not write into the opaque/depth-only pass.
    m.set_editor_property('blend_mode', unreal.BlendMode.BLEND_TRANSLUCENT)
    m.set_editor_property('two_sided', True)
    m.set_editor_property('used_with_particle_sprites', True)
    uv = lib.create_material_expression(m, unreal.MaterialExpressionTextureCoordinate)
    world = lib.create_material_expression(m, unreal.MaterialExpressionWorldPosition)
    shape = lib.create_material_expression(m, unreal.MaterialExpressionCustom)
    shape.set_editor_property('output_type', unreal.CustomMaterialOutputType.CMOT_FLOAT1)
    inputs = []
    for name in ('UV', 'World'):
        item = unreal.CustomInput()
        item.set_editor_property('input_name', name)
        inputs.append(item)
    shape.set_editor_property('inputs', inputs)
    # Field rectangle excludes the covered stands. Depth testing remains on.
    # Hide particles below turf; no collision/trace per particle is required.
    code = ('float2 q=(UV-0.5)*2.0; float a=saturate(1.0-dot(q,q));'
            if snow else 'float a=saturate(1.0-abs(UV.x-0.5)*2.0)*saturate(1.0-abs(UV.y-0.5)*2.0);')
    code += '''
float openPitch=step(abs(World.x),5350.0)*step(abs(World.y),3450.0);
float ground=saturate(World.z/60.0);
return a*openPitch*ground;'''
    shape.set_editor_property('code', code)
    lib.connect_material_expressions(uv, '', shape, 'UV')
    lib.connect_material_expressions(world, '', shape, 'World')
    lib.connect_material_property(shape, '', unreal.MaterialProperty.MP_OPACITY)
    color = lib.create_material_expression(m, unreal.MaterialExpressionConstant3Vector)
    color.set_editor_property('constant', unreal.LinearColor(0.65, 0.70, 0.75, 1))
    lib.connect_material_property(color, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(m)
    unreal.EditorAssetLibrary.save_asset(m.get_path_name())
    return object_ptr(m)


def scalar(module, owner, field, value):
    d = new('DistributionFloatConstant', module)
    set_value(d, 'DistributionFloatConstant', 'Constant', value)
    set_value(module, owner, field, '(Distribution=' + ref(d) + ')')


def vector(module, owner, field, low, high=None):
    kind = 'DistributionVectorUniform' if high is not None else 'DistributionVectorConstant'
    d = new(kind, module)
    fmt = lambda v: '(X=%s,Y=%s,Z=%s)' % tuple(v)
    if high is None:
        set_value(d, kind, 'Constant', fmt(low))
    else:
        set_value(d, kind, 'Min', fmt(low))
        set_value(d, kind, 'Max', fmt(high))
    set_value(module, owner, field, '(Distribution=' + ref(d) + ')')


def system(name, snow):
    # Saving a material can collect unreferenced native subobjects. Finish it
    # before constructing the emitter, then attach the complete graph at once.
    mat = material('M_' + name, snow)
    path = destination + '/' + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    p = assets.create_asset(name, destination, unreal.ParticleSystem, unreal.ParticleSystemFactoryNew())
    parent = object_ptr(p)
    emitter = new('ParticleSpriteEmitter', parent)
    lod = new('ParticleLODLevel', emitter)
    required = new('ParticleModuleRequired', parent)
    spawn = new('ParticleModuleSpawn', parent)
    set_value(required, 'ParticleModuleRequired', 'Material', ref(mat))
    for field, value in [('EmitterDuration', 1), ('EmitterLoops', 0),
                         ('bUseLocalSpace', False), ('bKillOnDeactivate', True),
                         ('ScreenAlignment', 'PSA_Square' if snow else 'PSA_Velocity'),
                         ('bUseMaxDrawCount', True), ('MaxDrawCount', 900 if snow else 720)]:
        set_value(required, 'ParticleModuleRequired', field, value)
    scalar(spawn, 'ParticleModuleSpawn', 'Rate', 140 if snow else 450)
    set_value(spawn, 'ParticleModuleSpawn', 'bApplyGlobalSpawnRateScale', False)
    modules = []
    for kind, field, value in [('ParticleModuleLifetime', 'Lifetime', 6 if snow else 1.4),
                              # At an 80 m broadcast camera the previous 1.2 cm
                              # rain / 4 cm snow mostly covered <1 pixel at 720p.
                              # Increase footprint without adding particles.
                              ('ParticleModuleSize', 'StartSize', (14, 14, 14) if snow else (7, 65, 7)),
                              ('ParticleModuleVelocity', 'StartVelocity', (35, 10, -280) if snow else (65, 20, -1600)),
                              ('ParticleModuleLocation', 'StartLocation', None)]:
        mod = new(kind, parent)
        if kind == 'ParticleModuleLifetime':
            scalar(mod, kind, field, value)
        elif kind == 'ParticleModuleLocation':
            vector(mod, kind, field, (-2500, -1800, 1000 if snow else 1600),
                   (2500, 1800, 1600 if snow else 2100))
        else:
            vector(mod, kind, field, value)
        modules.append(mod)
    for mod in [required, spawn] + modules:
        set_value(mod, 'ParticleModule', 'LODValidity', 1)
    set_value(lod, 'ParticleLODLevel', 'Level', 0)
    set_value(lod, 'ParticleLODLevel', 'bEnabled', True)
    set_value(lod, 'ParticleLODLevel', 'RequiredModule', ref(required))
    set_value(lod, 'ParticleLODLevel', 'SpawnModule', ref(spawn))
    set_value(lod, 'ParticleLODLevel', 'Modules', refs(modules))
    set_value(emitter, 'ParticleEmitter', 'LODLevels', refs([lod]))
    set_value(parent, 'ParticleSystem', 'Emitters', refs([emitter]))
    set_value(parent, 'ParticleSystem', 'LODDistances', '(0.0)')
    set_value(parent, 'ParticleSystem', 'LODSettings', '((bLit=False))')
    # One bounded emitter per match uses the component's normal UE tick. Do
    # not depend on the stripped game's optional batched particle manager.
    set_value(parent, 'ParticleSystem', 'bAllowManagedTicking', False)
    p.set_editor_property('warmup_time', 0.0)
    p.set_editor_property('use_fixed_relative_bounding_box', True)
    p.set_editor_property('fixed_relative_bounding_box', unreal.Box(
        min=unreal.Vector(-2800, -2100, -1000), max=unreal.Vector(2800, 2100, 2400)))
    post_edit(parent)
    unreal.EditorAssetLibrary.save_asset(path)
    unreal.log('NX_WEATHER_CREATED ' + path)


system('Rain', False)
system('Snow', True)
unreal.log('NX_WEATHER_ASSETS_OK')
