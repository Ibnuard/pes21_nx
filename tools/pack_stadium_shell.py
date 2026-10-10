"""Pack only the locally converted Anfield namespace from a UE4.22 cook.

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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cooked', required=True, type=Path)
    p.add_argument('--repak', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    namespace = Path('PesMobile/Content/FootballNX/Stadiums/Anfield')
    source = (args.cooked / namespace).resolve(strict=True)
    files = sorted(source.iterdir())
    if not (source / 'AnfieldShell.uexp').is_file() or not files:
        raise ValueError('cooked Anfield shell is missing')
    if any(not f.is_file() or f.suffix not in ('.uasset', '.uexp', '.ubulk') for f in files):
        raise ValueError('unexpected output inside stadium namespace')
    # Android_ETC1 selects texture encoding, not GLES feature levels. The
    # stock runtime uses both, while a default UE project cooks ES2 only.
    # Refuse a shell which would have no ES3.1 material map at runtime.
    materials = [f for f in files if f.name.startswith('M_') and f.suffix == '.uexp']
    if not materials or any(material_shader_versions(f) != {'100', '310 es'} for f in materials):
        raise ValueError('Cook materials with bBuildForES2=True, bBuildForES31=True and bShareMaterialShaderCode=False')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent, prefix='anfield-pak-') as temporary:
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
    report = {'file': args.output.name, 'bytes': args.output.stat().st_size,
              'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
              'members': expected, 'hardware_tested': False}
    args.output.with_suffix('.local.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Anfield PAK: {len(files)} files, {report["bytes"]} bytes')


if __name__ == '__main__':
    main()
