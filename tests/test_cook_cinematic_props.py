"""Asset pipeline guards, using synthetic inputs only (no editor needed)."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import cook_cinematic_props as cook
from cinematic_props_fbx import PROP_PATHS


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


@pytest.fixture
def prepared(tmp_path):
    preparation = {'schema': 'PESNX_CINEMATIC_PROPS_V1', 'cooked': False, 'props': [], 'outputs': []}
    exported = {'schema': 'PESNX_CINEMATIC_PROP_FBX_V1',
                'preparation': str(tmp_path / 'preparation.local.json'), 'props': []}
    for key in cook.KEYS:
        texture = tmp_path / key / 'textures/base.png'
        texture.parent.mkdir(parents=True)
        texture.write_bytes(b'synthetic opaque texture')
        blob = texture.parent.parent / (key + '.bin')
        blob.write_bytes(b'synthetic buffer')
        gltf = blob.with_suffix('.gltf')
        save(gltf, {'nodes': [{'mesh': 0}], 'meshes': [{'primitives': [{'attributes': {}}]}],
                    'buffers': [{'uri': blob.name}], 'images': [{'uri': 'textures/base.png'}]})
        for resource in (texture, blob, gltf):
            preparation['outputs'].append({'file': resource.relative_to(tmp_path).as_posix(),
                                          'bytes': resource.stat().st_size, 'sha256': cook.digest(resource)})
        path = '/Game/Assets/FootballNX/FixDemo/{0}/{0}.{0}'.format(key)
        bounds = [[-10, -20, 0], [10, 20, 60]]
        prop = {'key': key, 'target_object_path': path,
                'gltf': key + '/' + key + '.gltf', 'target_class': 'StaticMesh',
                'descriptor_model_path': PROP_PATHS[key] + '.fpk',
                'runtime_model_path': PROP_PATHS[key] + '.xml',
                'geometry': {'triangles': 4, 'uv_sets': [2], 'expected_ue_bounds_cm': bounds},
                'materials': [{'name': 'gold', 'inputs': [
                    {'role': 'Base_Tex_SRGB', 'texture': 0, 'srgb': True}],
                    'preview_metallic': 1., 'preview_roughness': .35}],
                'textures': [{'file': 'textures/base.png', 'alpha_range': [255, 255]}]}
        mesh = tmp_path / 'fbx' / (key + '.fbx')
        mesh.parent.mkdir(exist_ok=True)
        mesh.write_bytes(b'synthetic rigid fbx')
        check = {'winding_and_uv_corners_verified': True, 'triangles_matched': 4,
                 'uv_channels': 2, 'max_position_delta_m': 1e-7, 'max_uv_delta': 0.}
        snapshot = {'has_skin': False, 'triangles': 4,
                    'normal_winding_votes': {'aligned': 4, 'opposed': 0, 'degenerate': 0}}
        out = {'key': key, 'target_object_path': path, 'fbx': str(mesh), 'sha256': cook.digest(mesh),
               'roundtrip_verified': True, 'faces_reversed': True, 'source_to_blender': check,
               'roundtrip_corner_check': copy.deepcopy(check), 'before': snapshot, 'after': snapshot,
               'fbx_contract': {'serialized_cm_bounds_verified': True, 'version': 7400,
                                'unit_scale_factor_cm': 1., 'axes': {
                                    'UpAxis': 2, 'UpAxisSign': 1, 'FrontAxis': 1,
                                    'FrontAxisSign': 1, 'CoordAxis': 0, 'CoordAxisSign': -1}},
               'expected_ue_bounds_cm': bounds}
        preparation['props'].append(prop)
        exported['props'].append(out)
    save(tmp_path / 'preparation.local.json', preparation)
    save(tmp_path / 'fbx/fbx.local.json', exported)
    return tmp_path, preparation, exported


def test_import_profile_is_narrow_and_explicit(prepared):
    root, _, _ = prepared
    report = cook.import_profile(root / 'fbx/fbx.local.json', root / 'ue-report.json')
    assert tuple(p['key'] for p in report['props']) == cook.KEYS
    assert report['props'][0]['materials'][0]['base_texture'].endswith('base.png')
    assert report['props'][0]['materials'][0]['metallic'] == 1.
    assert cook.expected_assets(report) == {
        'cup_int_hi/cup_int_hi', 'cup_int_hi/M_gold', 'cup_int_hi/T_gold',
        'platform_cmn/platform_cmn', 'platform_cmn/M_gold', 'platform_cmn/T_gold'}


@pytest.mark.parametrize('mutation', ['namespace', 'roundtrip', 'winding', 'skin', 'triangles',
                                      'uv', 'drift', 'nan', 'fbx_hash', 'bounds', 'axis', 'unit', 'normal'])
def test_refuses_unverified_or_changed_fbx(prepared, mutation):
    root, _, report = prepared
    item = report['props'][0]
    if mutation == 'namespace':
        item['target_object_path'] = '/Game/Assets/character/Body/001a01p.001a01p'
    elif mutation == 'roundtrip':
        item['roundtrip_verified'] = False
    elif mutation == 'winding':
        item['faces_reversed'] = False
    elif mutation == 'skin':
        item['before']['has_skin'] = True
    elif mutation == 'triangles':
        item['roundtrip_corner_check']['triangles_matched'] -= 1
    elif mutation == 'uv':
        item['roundtrip_corner_check']['uv_channels'] = 1
    elif mutation in ('drift', 'nan'):
        item['roundtrip_corner_check']['max_uv_delta'] = .1 if mutation == 'drift' else float('nan')
    elif mutation == 'fbx_hash':
        item['sha256'] = '0' * 64
    elif mutation == 'bounds':
        item['expected_ue_bounds_cm'][1][2] = 6000
    elif mutation == 'axis':
        item['fbx_contract']['axes']['UpAxis'] = 1
    elif mutation == 'unit':
        item['fbx_contract']['unit_scale_factor_cm'] = 100
    elif mutation == 'normal':
        item['before']['normal_winding_votes']['opposed'] = 4
    save(root / 'fbx/fbx.local.json', report)
    with pytest.raises(ValueError):
        cook.import_profile(root / 'fbx/fbx.local.json', root / 'ue-report.json')


@pytest.mark.parametrize('mutation', ['hash', 'traversal', 'duplicate', 'alpha', 'material', 'scalar'])
def test_refuses_unverified_preparation(prepared, mutation):
    root, report, _ = prepared
    if mutation == 'hash':
        report['outputs'][0]['sha256'] = '0' * 64
    elif mutation == 'traversal':
        report['outputs'][0]['file'] = '../base.png'
    elif mutation == 'duplicate':
        report['outputs'].append(report['outputs'][0])
    elif mutation == 'alpha':
        report['props'][0]['textures'][0]['alpha_range'] = [0, 255]
    elif mutation == 'material':
        report['props'][0]['materials'][0]['name'] = '../gold'
    elif mutation == 'scalar':
        report['props'][0]['materials'][0]['preview_roughness'] = float('inf')
    save(root / 'preparation.local.json', report)
    with pytest.raises(ValueError):
        cook.import_profile(root / 'fbx/fbx.local.json', root / 'ue-report.json')


def test_never_reuses_an_existing_project(tmp_path):
    with pytest.raises(FileExistsError, match='NEW isolated'):
        cook.cook(tmp_path / 'absent.json', tmp_path, 'editor', 'repak', 'unrealpak')


def test_generated_payloads_cannot_escape_ignored_workspace(tmp_path):
    with pytest.raises(ValueError, match='inside ignored local-debug'):
        cook.cook(tmp_path / 'absent.json', tmp_path / 'new-project', 'editor', 'repak', 'unrealpak')


def test_missing_proprietary_fixture_is_explicit():
    report = Path(__file__).resolve().parents[1] / 'local-debug/cinematic-props-20261015-v1/fbx-v2/fbx.local.json'
    if not report.exists():
        pytest.skip('Optional local prop FBX roundtrip fixture has not been generated')
    profile = cook.import_profile(report, report.parent / 'not-written.json')
    assert tuple(p['key'] for p in profile['props']) == cook.KEYS


@pytest.fixture
def material_binding(monkeypatch):
    # The editor module is unavailable on the host; isolate the helper and
    # model only APIs actually reflected by the installed UE4.22 headers.
    monkeypatch.setitem(sys.modules, 'unreal', SimpleNamespace())
    spec = importlib.util.spec_from_file_location(
        'cinematic_import_test', cook.HERE / 'ue_import_cinematic_props.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.assign_rigid_materials


class RigidMesh:
    def __init__(self, slots, sections=None, discard_binding=False):
        self.slots = slots
        self.sections = len(slots) if sections is None else sections
        self.bound = {}
        self.discard_binding = discard_binding

    def get_num_sections(self, lod):
        assert lod == 0
        return self.sections

    def get_material_index(self, name):
        return self.slots.get(name, -1)

    def set_material(self, index, material):
        if not self.discard_binding:
            self.bound[index] = material.get_path_name()

    def get_material(self, index):
        path = self.bound.get(index)
        # Return a fresh wrapper, as an engine binding may do.
        return SimpleNamespace(get_path_name=lambda: path) if path else None


def test_material_binding_uses_ue422_reflected_apis(material_binding):
    material = SimpleNamespace(get_path_name=lambda: '/Game/Assets/FootballNX/FixDemo/cup_int_hi/M_gold')
    mesh = RigidMesh({'gold': 0})
    assert material_binding(mesh, {'gold': material}) == {'gold': 0}
    assert mesh.bound == {0: material.get_path_name()}


@pytest.mark.parametrize('mutation', ['section', 'missing', 'duplicate', 'gap', 'discard'])
def test_material_binding_rejects_unexpected_mesh_contract(material_binding, mutation):
    material = SimpleNamespace(get_path_name=lambda: '/Game/Materials/M_gold')
    slots = {'gold': 0, 'plastic': 1}
    materials = {'gold': material, 'plastic': material}
    if mutation == 'missing':
        slots = {'renamed': 0, 'plastic': 1}
    elif mutation == 'duplicate':
        slots['plastic'] = 0
    elif mutation == 'gap':
        slots['plastic'] = 2
    mesh = RigidMesh(slots, sections=3 if mutation == 'section' else 2,
                     discard_binding=mutation == 'discard')
    with pytest.raises(RuntimeError):
        material_binding(mesh, materials)


def test_actual_ue422_integrity_verdict_requires_exact_count():
    line = 'LogPakFile: Display: Pak file "D:/local canary/props.pak" healthy, 14 files checked.\n'
    assert cook.unrealpak_confirmed(line, 14)
    assert not cook.unrealpak_confirmed(line, 13)
    assert not cook.unrealpak_confirmed(line + 'LogPakFile: Error: broken entry\n', 14)
    assert not cook.unrealpak_confirmed(line + line, 14)
    assert not cook.unrealpak_confirmed('All commands exited with code 0', 14)


def test_repack_cannot_use_arbitrary_or_changed_project(prepared, monkeypatch):
    root, _, _ = prepared
    with pytest.raises(ValueError, match='inside ignored local-debug'):
        cook.package_existing_cook(root / 'fbx/fbx.local.json', root, 'repak', 'unrealpak')
    monkeypatch.setattr(cook, 'HERE', root / 'tools')
    output = root / 'local-debug/cook'
    output.mkdir(parents=True)
    profile = cook.import_profile(root / 'fbx/fbx.local.json', output / 'ue-import.local.json')
    profile['props'][0]['materials'][0]['roughness'] = .9
    save(output / 'import-profile.local.json', profile)
    with pytest.raises(ValueError, match='different verified import profile'):
        cook.package_existing_cook(root / 'fbx/fbx.local.json', output, 'repak', 'unrealpak')
