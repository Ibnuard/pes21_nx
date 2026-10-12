"""Import, cook and independently verify prepared stadiums in one UE session.

All input and output paths are local. Config JSON requires editor, project and
repak paths. Prepare FBX profiles with stadium_shell_fbx.py first. Re-running
repairs existing imported materials/meshes and packs only live dependencies.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from stadium_assets import asset_key


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--keys', nargs='+', required=True)
    p.add_argument('--pack-only', action='store_true')
    p.add_argument('--reuse-materials', action='store_true',
                   help='Apron geometry repair only: retain verified materials in the existing UE project')
    args = p.parse_args()
    config = json.loads(args.config.read_text())
    work = args.work.resolve(); tools = Path(__file__).resolve().parent
    keys = [asset_key(key) for key in args.keys]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate stadium keys')
    profiles = [work/'prepared'/key/'fbx.local.json' for key in keys]
    for key, path in zip(keys, profiles):
        profile = json.loads(path.read_text())
        if profile.get('key') != key or not Path(profile['fbx']).is_file():
            raise ValueError('Mismatched or incomplete FBX profile: '+str(path))
    project = Path(config['project']).resolve(strict=True)
    env = os.environ.copy()
    env.update(PESNX_STADIUM_RESUME='1', PESNX_STADIUM_REIMPORT='1')
    env['PESNX_STADIUM_REUSE_MATERIALS'] = '1' if args.reuse_materials else '0'
    def run_editor(phase, arguments):
        print(phase.upper(), ', '.join(keys), flush=True)
        with (work/('batch-'+phase+'.log')).open('w') as log:
            subprocess.run([config['editor'],str(project),*arguments,'-unattended',
                '-nosplash','-nullrhi','-stdout','-FullStdOutLogOutput'],
                stdout=log,stderr=subprocess.STDOUT,check=True,env=env)
    if not args.pack_only:
        # UE4.22 embeds Python 2.7. Keep this bootstrap syntax compatible and
        # outside project paths with spaces (commandlet parses script= itself).
        with tempfile.TemporaryDirectory(prefix='pesnx-stadium-') as temporary:
            bootstrap = Path(temporary)/'import.py'
            if ' ' in str(bootstrap):
                raise ValueError('Use a TEMP path without spaces for UE4.22')
            bootstrap.write_text('import os,runpy\nfor profile in '+repr([str(v) for v in profiles])+':\n'
                '    os.environ["PESNX_STADIUM_PROFILE"]=profile\n'
                '    runpy.run_path('+repr(str(tools/'ue_import_stadium_shell.py'))+',run_name="__main__")\n')
            run_editor('import',['-run=pythonscript','-script='+str(bootstrap)])
        log = (work/'batch-import.log').read_text(errors='replace')
        if log.count('LogPython: PESNX_STADIUM_IMPORT_OK') != len(keys):
            # Some engine builds prefix Python log messages differently.
            if log.count('PESNX_STADIUM_IMPORT_OK') != len(keys):
                raise RuntimeError('Not every import reported success')
        # The bundled legacy Qonvert DLL can race during concurrent format
        # initialization, spinning in its shared registry. Serialize this
        # offline commandlet; texture format/quality and runtime are unchanged.
        cook_args = ['-run=Cook','-TargetPlatform=Android_ETC1',
            '-CookDir=/Game/FootballNX/Stadiums']
        if config.get('serial_texture_cook', True):
            cook_args.append('-nothreading')
        run_editor('cook',cook_args)
    for key,path in zip(keys,profiles):
        subprocess.run([sys.executable,str(tools/'pack_stadium_shell.py'),
            '--cooked',str(project.parent/'Saved/Cooked/Android_ETC1'),
            '--repak',config['repak'],'--key',key,'--profile',str(path),
            '--output',str(work/'packages'/('PesMobile-'+key+'-Android_ETC1_P.pak'))],check=True)
        print('PACKAGED',key,flush=True)


if __name__ == '__main__':
    main()
