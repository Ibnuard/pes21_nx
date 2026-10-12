"""Pack only a locally converted stadium namespace from a UE4.22 cook.

Pass the Android_ETC1 cooked root (containing PesMobile/Content), not the
uncooked editor project. Engine defaults and native game assets are excluded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zlib
from stadium_assets import asset_key


def material_shader_versions(path):
    versions = set()
    data = path.read_bytes()
    for match in re.finditer(b'\x78[\x01\x5e\x9c\xda]', data):
        try:
            block = zlib.decompress(data[match.start():])
        except zlib.error:
            continue
        if block.startswith(b'LSLG'):
            version = re.search(rb'#version\s+(100|310 es)', block)
            if version:
                versions.add(version.group(1).decode())
    return versions


def vertex_cull_shader_present(path):
    """Check the cooked ES3.1 vertex map, not just the editor graph nodes."""
    data = path.read_bytes()
    for match in re.finditer(b'\x78[\x01\x5e\x9c\xda]', data):
        try:
            block = zlib.decompress(data[match.start():])
        except zlib.error:
            continue
        if (block.startswith(b'LSLGSV') and b'#version 310 es' in block and
                b'3.276800e+04' in block and b'View_WorldCameraOrigin' in block and
                b'Primitive_LocalToWorld' in block):
            return True
    return False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cooked', required=True, type=Path)
    p.add_argument('--repak', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--key', default='Anfield')
    p.add_argument('--profile', type=Path, help='FBX profile: omit stale assets from earlier imports')
    args = p.parse_args()
    key = asset_key(args.key)
    namespace = Path('PesMobile/Content/FootballNX/Stadiums') / key
    source = (args.cooked / namespace).resolve(strict=True)
    files = sorted(source.iterdir())
    profile = {}
    if args.profile:
        profile = json.loads(args.profile.read_text())
        if profile.get('key', 'Anfield') != key:
            raise ValueError('Profile belongs to another stadium')
        allowed = {key + 'Shell'} | set(profile['material_slots'])
        for name in profile['material_slots']:
            texture = profile.get('texture_files', {}).get(name) or str(args.profile.parent/'textures'/(name[2:]+'.png'))
            if Path(texture).is_file():
                allowed.add('T_crowd_flipbook_v16' if name == 'M_crowd_seated' and profile.get('crowd_flipbook') else 'T_' + name[2:])
            mask = profile.get('mask_files', {}).get(name)
            if mask:
                if not Path(mask).is_file():
                    raise ValueError('Missing cutout mask source: ' + name)
                allowed.add('T_' + name[2:] + '_mask')
        for name in allowed:
            if not all((source/(name+ext)).is_file() for ext in ('.uasset','.uexp')):
                raise ValueError('Missing cooked dependency: ' + name)
        files = [f for f in files if f.stem in allowed]
    if not (source / (key + 'Shell.uexp')).is_file() or not files:
        raise ValueError('cooked stadium shell is missing')
    if any(not f.is_file() or f.suffix not in ('.uasset', '.uexp', '.ubulk') for f in files):
        raise ValueError('unexpected output inside stadium namespace')
    # Android_ETC1 selects texture encoding, not GLES feature levels. The
    # stock runtime uses both, while a default UE project cooks ES2 only.
    # Refuse a shell which would have no ES3.1 material map at runtime.
    materials = [f for f in files if f.name.startswith('M_') and f.suffix == '.uexp']
    if not materials or any(material_shader_versions(f) != {'100', '310 es'} for f in materials):
        raise ValueError('Cook materials with bBuildForES2=True, bBuildForES31=True and bShareMaterialShaderCode=False')
    if args.profile and any(vertex_cull_shader_present(f) != bool(profile.get('vertex_camera_cull')) for f in materials):
        raise ValueError('Cooked ES3.1 camera rejection differs from the requested profile; reimport and recook')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent, prefix='stadium-pak-') as temporary:
        stage = Path(temporary) / 'stage'
        target = stage / namespace
        target.mkdir(parents=True)
        for f in files:
            shutil.copyfile(f, target / f.name)
        subprocess.run([str(args.repak), 'pack', '--version', 'V8A', '--compression', 'Zlib',
                        str(stage), str(args.output)], check=True)
        names = subprocess.check_output([str(args.repak), 'list', str(args.output)], text=True).splitlines()
        expected = sorted((namespace / f.name).as_posix() for f in files)
        if sorted(names) != expected:
            raise ValueError('unexpected PAK membership')
        restored = Path(temporary) / 'roundtrip'
        subprocess.run([str(args.repak),'unpack','-q','-o',str(restored),str(args.output)],check=True)
        actual = sorted(p.relative_to(restored).as_posix() for p in restored.rglob('*') if p.is_file())
        if actual != expected:
            raise ValueError('PAK roundtrip membership mismatch')
        for f in files:
            if (restored / namespace / f.name).read_bytes() != f.read_bytes():
                raise ValueError('PAK roundtrip bytes differ: ' + f.name)
    report = {'file': args.output.name, 'bytes': args.output.stat().st_size,
              'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
              'members': expected, 'roundtrip_members_verified': len(expected),
              'hardware_tested': False}
    args.output.with_suffix('.local.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{key} PAK: {len(files)} files, {report["bytes"]} bytes')


if __name__ == '__main__':
    main()
