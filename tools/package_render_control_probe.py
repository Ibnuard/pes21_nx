"""Create a local, NRO-only A/B package without changing face/stadium payloads."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import zipfile

from package_realface_runtime_probe import ROOT, inspect_build, sha

INSTALL = """FootballNX v43 - whole-player blinking isolation

Use the same v41-7k face PAK in BOTH tests. Do not recook/remove faces.
This is a diagnostic candidate, not a confirmed rendering/60 FPS fix.
Keep the already installed v42 native entrance baseline and other game files.

1. Back up your installed pes21_nx.nro. Copy the TWO files from update/
   into sdmc:/switch/pes21_nx/, beside the installed NRO.
   Start the game, reproduce the blinking, then Pause and preserve
   scene-runtime.log as v43-cache-enabled.log.
2. Fully exit the game. Copy test-2-bypass/render-control.txt into the SAME
   sdmc:/switch/pes21_nx/ folder, replacing the first control file.
   Restart and repeat the same teams, lineup, camera, quality, weather and
   near-camera passing sequence. Pause and preserve scene-runtime.log as
   v43-cache-bypassed.log. Note whether WHOLE BODIES still blink in each run.

The log must say state_cache=enabled for test 1 and state_cache=bypassed
for test 2. Settings are read once at boot, so Pause/Resume is insufficient.
The bypass applies to redundant GL state suppression only; face detail,
textures, triangle count, shaders and gameplay remain the same.
It may run slower and is not a performance recommendation.

Rollback: restore your backed-up ordinary NRO and remove render-control.txt.
The v42 ordinary NRO ignores this diagnostic marker. No saves, PAK, OBB,
CPK, roster or installed manifest are modified by this package generator.

Buffer outcomes are RAM counters written on leaving play. GL errors are
observed only when the engine itself calls glGetError; zero error checks
cannot establish an error-free frame. No new GPU wait/readback is added.
"""


def package(build: Path, output: Path, pair: str):
    build, output = Path(build).resolve(), Path(output).resolve()
    if not output.is_relative_to(ROOT/'local-debug') or output.exists():
        raise ValueError('Use a fresh ignored local-debug output directory')
    archive=output.with_suffix('.zip')
    if archive.exists():raise ValueError('Archive already exists')
    proof=inspect_build(build,True,pair)
    with (build/'pes21_nx.nro').open('rb') as stream:
        data=stream.read()
    for marker in (b'FootballNX scene v43 session',b'PESNX_GL_CACHE_BYPASS_V1',
                   b'map_failures=',b'unmap_failures=',b'render control: state_cache='):
        if marker not in data:raise ValueError('Not the v43 render-control diagnostic build')
    del data
    (output/'update').mkdir(parents=True)
    (output/'test-2-bypass').mkdir()
    shutil.copy2(build/'pes21_nx.nro',output/'update/pes21_nx.nro')
    (output/'update/render-control.txt').write_bytes(b'PESNX_GL_CACHE_DEFAULT_V1\n')
    (output/'test-2-bypass/render-control.txt').write_bytes(b'PESNX_GL_CACHE_BYPASS_V1\n')
    (output/'INSTALL.txt').write_text(INSTALL,encoding='utf-8')
    report=dict(candidate='Whole-player render control v43',runtime_pair=pair,build=proof,
                face_payload_included=False,face_quality_changed=False,
                whole_player_blink_fixed=False,stable_60_fps_verified=False,
                active_runtime_modified=False,
                files={p.relative_to(output).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
                       for p in sorted(output.rglob('*')) if p.is_file()})
    (output/'VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(output.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(output).as_posix())
    return dict(package=str(output),zip=str(archive),zip_sha256=sha(archive),verification=report)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--pair',required=True)
    args=parser.parse_args()
    print(json.dumps(package(args.build,args.output,args.pair),indent=2))


if __name__=='__main__':main()
