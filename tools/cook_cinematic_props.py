"""Cook verified rigid props in a NEW isolated UE4.22 project; no installation.

This prepares an asset-only PAK, not a playable trophy ceremony. Native scene
selection, prop lifecycle/parenting and hardware acceptance are separate gates.
All proprietary inputs and generated output must remain local and ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from cinematic_props_fbx import child_file, validate_preparation
from pack_stadium_shell import material_shader_versions

HERE = Path(__file__).resolve().parent
KEYS = ('cup_int_hi', 'platform_cmn')
NAMESPACE = Path('PesMobile/Content/Assets/FootballNX/FixDemo')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def import_profile(fbx_path, report_path):
    """Recheck both measured stages rather than trusting a success flag alone."""
    fbx_path = Path(fbx_path).resolve(strict=True)
    fbx = read(fbx_path)
    if fbx.get('schema') != 'PESNX_CINEMATIC_PROP_FBX_V1':
        raise ValueError('Wrong FBX report schema')
    preparation_path = Path(fbx['preparation']).resolve(strict=True)
    preparation = validate_preparation(preparation_path)
    for report in (preparation, fbx):
        if tuple(p['key'] for p in report['props']) != KEYS:
            raise ValueError('Expected only the two audited props in canonical order')
    outputs = {}
    for item in preparation['outputs']:
        if item['file'] in outputs:
            raise ValueError('Duplicate preparation member')
        path = child_file(preparation_path.parent, item['file'])
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('Prepared source changed: ' + item['file'])
        outputs[item['file']] = path
    result = {'schema': 'PESNX_CINEMATIC_IMPORT_V1', 'props': [],
              'report': str(Path(report_path).resolve()),
              'preparation_sha256': digest(preparation_path), 'fbx_report_sha256': digest(fbx_path)}
    for prop, exported in zip(preparation['props'], fbx['props']):
        key = prop['key']
        expected_path = '/Game/Assets/FootballNX/FixDemo/{0}/{0}.{0}'.format(key)
        if any(p['target_object_path'] != expected_path for p in (prop, exported)):
            raise ValueError('Unexpected prop namespace')
        mesh = Path(exported['fbx']).resolve(strict=True)
        if mesh.parent != fbx_path.parent or mesh.name != key + '.fbx' or digest(mesh) != exported['sha256']:
            raise ValueError('FBX changed or escaped the verified output directory')
        if exported.get('roundtrip_verified') is not True or exported.get('faces_reversed') is not True:
            raise ValueError('Missing verified FBX roundtrip/winding')
        for label in ('source_to_blender', 'roundtrip_corner_check'):
            check = exported.get(label, {})
            if (check.get('winding_and_uv_corners_verified') is not True or
                    check.get('triangles_matched') != prop['geometry']['triangles'] or
                    check.get('uv_channels') != prop['geometry']['uv_sets'][0]):
                raise ValueError('Missing exact topology/UV verification: ' + label)
            for name in ('max_position_delta_m', 'max_uv_delta'):
                value = check.get(name)
                if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 2e-6:
                    raise ValueError('FBX drift exceeds audited tolerance')
        for stage in ('before', 'after'):
            snapshot = exported[stage]
            votes = snapshot.get('normal_winding_votes', {})
            if (snapshot.get('has_skin') is not False or
                    snapshot['triangles'] != prop['geometry']['triangles'] or
                    votes.get('opposed') != 0 or votes.get('degenerate') != 0 or
                    votes.get('aligned') != prop['geometry']['triangles']):
                raise ValueError('Rigid mesh contract changed')
        contract = exported.get('fbx_contract', {})
        if (contract.get('serialized_cm_bounds_verified') is not True or
                contract.get('version') != 7400 or contract.get('unit_scale_factor_cm') != 1. or
                contract.get('axes') != {'UpAxis': 2, 'UpAxisSign': 1, 'FrontAxis': 1,
                                         'FrontAxisSign': 1, 'CoordAxis': 0, 'CoordAxisSign': -1}):
            raise ValueError('Missing verified FBX axis/unit contract')
        bounds = prop['geometry']['expected_ue_bounds_cm']
        if exported['expected_ue_bounds_cm'] != bounds or len(bounds) != 2 or any(len(row) != 3 for row in bounds):
            raise ValueError('Bounds contract changed')
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for row in bounds for v in row):
            raise ValueError('Non-finite prop bounds')
        materials = []
        for slot in prop['materials']:
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', slot['name']):
                raise ValueError('Unsafe material name')
            base = [v for v in slot['inputs'] if v['role'] == 'Base_Tex_SRGB']
            if len(base) != 1 or base[0]['srgb'] is not True:
                raise ValueError('Exactly one audited base colour required')
            texture = prop['textures'][base[0]['texture']]
            member = key + '/' + texture['file']
            if member not in outputs or texture['alpha_range'] != [255, 255]:
                raise ValueError('Base texture must be hashed and opaque')
            metallic, roughness = slot['preview_metallic'], slot['preview_roughness']
            if not all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1
                       for v in (metallic, roughness)):
                raise ValueError('Invalid material scalar')
            materials.append({'name': slot['name'], 'base_texture': str(outputs[member]),
                              'metallic': metallic, 'roughness': roughness})
        if not materials or len({m['name'] for m in materials}) != len(materials):
            raise ValueError('Missing/duplicate material slots')
        result['props'].append({'key': key, 'fbx': str(mesh), 'target_object_path': expected_path,
                                'expected_ue_bounds_cm': bounds, 'materials': materials})
    return result


def expected_assets(profile):
    members = set()
    for prop in profile['props']:
        key = prop['key']
        names = [key]
        for slot in prop['materials']:
            names.extend(('M_' + slot['name'], 'T_' + slot['name']))
        for name in names:
            members.add((Path(key) / name).as_posix())
    return members


def unrealpak_confirmed(output, count):
    # UE4.22 includes the archive name in this verdict. Require the complete
    # member count as well as its success text, not merely exit code zero.
    verdicts = re.findall(r'Pak file "[^"\r\n]+" healthy, ([0-9]+) files checked\.', output)
    return verdicts == [str(count)] and not re.search(r'\b(?:Error|Fatal):', output, re.I)


def pack(cooked, profile, repak, unrealpak, output):
    source = Path(cooked) / NAMESPACE
    assets = expected_assets(profile)
    files = sorted(p for p in source.rglob('*') if p.is_file())
    found = {p.relative_to(source).with_suffix('').as_posix() for p in files}
    if found != assets or any(p.suffix not in ('.uasset', '.uexp', '.ubulk') for p in files):
        raise ValueError('Unexpected/missing cinematic cooked assets')
    for asset in assets:
        if not all((source / (asset + ext)).is_file() for ext in ('.uasset', '.uexp')):
            raise ValueError('Incomplete cooked package: ' + asset)
        if Path(asset).name.startswith('M_') and material_shader_versions(source / (asset + '.uexp')) != {'100', '310 es'}:
            raise ValueError('Cinematic material needs embedded ES2 and ES3.1 shader maps')
    if Path(output).exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory(prefix='pesnx-props-pack-') as temporary:
        stage = Path(temporary) / 'stage'
        for path in files:
            target = stage / NAMESPACE / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        subprocess.run([str(repak), 'pack', '--version', 'V8A', '--compression', 'Zlib',
                        str(stage), str(output)], check=True)
        expected = sorted((NAMESPACE / p.relative_to(source)).as_posix() for p in files)
        names = subprocess.check_output([str(repak), 'list', str(output)], text=True).splitlines()
        if sorted(names) != expected:
            raise ValueError('Unexpected PAK member set')
        test = subprocess.run([str(unrealpak), str(output), '-Test'], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if not unrealpak_confirmed(test.stdout, len(expected)):
            raise ValueError('UnrealPak did not confirm archive integrity')
        restored = Path(temporary) / 'roundtrip'
        subprocess.run([str(repak), 'unpack', '-q', '-o', str(restored), str(output)], check=True)
        actual = sorted(p.relative_to(restored).as_posix() for p in restored.rglob('*') if p.is_file())
        if actual != expected:
            raise ValueError('PAK roundtrip membership changed')
        for path in files:
            if digest(path) != digest(restored / NAMESPACE / path.relative_to(source)):
                raise ValueError('PAK roundtrip payload changed')
    return {'sha256': digest(output), 'bytes': Path(output).stat().st_size, 'members': expected,
            'shader_versions': ['100', '310 es'], 'unrealpak_test': True,
            'roundtrip_verified': True, 'runtime_installed': False, 'hardware_tested': False}


def package_cooked(output, profile, repak, unrealpak):
    output = Path(output).resolve(strict=True)
    imported = read(output / 'ue-import.local.json')
    if imported.get('status') != 'imported' or tuple(p['key'] for p in imported['props']) != KEYS:
        raise ValueError('Editor import did not complete')
    package = output / 'PesMobile-CinematicProps-Android_ETC1_P.pak'
    report = pack(output / 'PesMobile/Saved/Cooked/Android_ETC1', profile, repak, unrealpak, package)
    report.update({'schema': 'PESNX_CINEMATIC_PROP_PACKAGE_V1', 'stage': 'asset-only-not-playable',
                   'preparation_sha256': profile['preparation_sha256'],
                   'fbx_report_sha256': profile['fbx_report_sha256'], 'package': str(package),
                   'material_policy': imported['material_policy']})
    write(output / 'package.local.json', report)
    print(json.dumps(report, indent=2), flush=True)
    return report


def package_existing_cook(fbx_path, output, repak, unrealpak):
    """Resume only packaging after a successful import/cook, never overwrite."""
    output = Path(output).resolve(strict=True)
    if (HERE.parent / 'local-debug').resolve() not in output.parents:
        raise ValueError('Existing cooked project must be inside ignored local-debug')
    profile = import_profile(fbx_path, output / 'ue-import.local.json')
    if read(output / 'import-profile.local.json') != profile:
        raise ValueError('Existing cook uses a different verified import profile')
    return package_cooked(output, profile, repak, unrealpak)


def cook(fbx_path, output, editor, repak, unrealpak):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Use a NEW isolated output directory: ' + str(output))
    allowed = (HERE.parent / 'local-debug').resolve()
    if allowed not in output.parents:
        raise ValueError('Generated proprietary assets must remain inside ignored local-debug')
    profile = import_profile(fbx_path, output / 'ue-import.local.json')
    for executable in (editor, repak, unrealpak):
        if not Path(executable).is_file():
            raise FileNotFoundError(executable)
    project = output / 'PesMobile'
    (project / 'Config').mkdir(parents=True)
    write(project / 'PesMobile.uproject', {'FileVersion': 3, 'EngineAssociation': '4.22',
          'Description': 'Isolated local cinematic prop canary', 'Plugins': [
              {'Name': 'PythonScriptPlugin', 'Enabled': True},
              {'Name': 'EditorScriptingUtilities', 'Enabled': True}]})
    (project / 'Config/DefaultEngine.ini').write_text(
        '[/Script/EngineSettings.GameMapsSettings]\nGameDefaultMap=/Engine/Maps/Entry\n'
        'EditorStartupMap=/Engine/Maps/Entry\n\n'
        '[/Script/UnrealEd.ProjectPackagingSettings]\nbUsePakFile=False\n'
        'bShareMaterialShaderCode=False\nbShareMaterialNativeLibraries=False\n\n'
        '[/Script/AndroidRuntimeSettings.AndroidRuntimeSettings]\n'
        'bBuildForES2=True\nbBuildForES31=True\nTextureFormat=ETC1\n', encoding='utf-8')
    write(output / 'import-profile.local.json', profile)
    environment = os.environ.copy()
    environment['PESNX_CINEMATIC_IMPORT_PROFILE'] = str(output / 'import-profile.local.json')

    def run(phase, arguments):
        print('CINEMATIC ' + phase.upper(), flush=True)
        with (output / (phase + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run([str(editor), str(project / 'PesMobile.uproject'), *arguments,
                            '-unattended', '-nop4', '-nosplash', '-nullrhi', '-stdout', '-FullStdOutLogOutput'],
                           env=environment, check=True, stdout=log, stderr=subprocess.STDOUT,
                           timeout=900 if phase == 'import' else 1800)

    with tempfile.TemporaryDirectory(prefix='pesnx-props-import-') as temporary:
        bootstrap = Path(temporary) / 'import_props.py'
        if ' ' in str(bootstrap):
            raise ValueError('UE4.22 requires a space-free temporary bootstrap path')
        bootstrap.write_text('import runpy\nrunpy.run_path(' + repr(str(HERE / 'ue_import_cinematic_props.py')) +
                             ', run_name="__main__")\n', encoding='utf-8')
        # The serial commandlet also avoids the observed multithreaded startup
        # stall on this host. It never changes the game's threading settings.
        run('import', ['-run=pythonscript', '-script=' + str(bootstrap), '-nothreading'])
    imported = read(output / 'ue-import.local.json')
    if imported.get('status') != 'imported' or tuple(p['key'] for p in imported['props']) != KEYS:
        raise ValueError('Editor import did not complete')
    run('cook', ['-run=cook', '-targetplatform=Android_ETC1',
                 '-CookDir=/Game/Assets/FootballNX/FixDemo', '-unversioned', '-nothreading'])
    return package_cooked(output, profile, repak, unrealpak)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('fbx-report', 'output', 'editor', 'repak', 'unrealpak'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--package-existing-cook', action='store_true',
                        help='reuse an unchanged verified import/cooked project; refuse an existing PAK')
    args = parser.parse_args()
    if args.package_existing_cook:
        package_existing_cook(args.fbx_report, args.output, args.repak, args.unrealpak)
    else:
        cook(args.fbx_report, args.output, args.editor, args.repak, args.unrealpak)
