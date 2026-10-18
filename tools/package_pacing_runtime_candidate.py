"""Verify and package local quality-preserving wrapper candidates."""
import argparse
import json
from pathlib import Path
import shutil
import zipfile
from package_realface_runtime_probe import ROOT,inspect_build,sha

INSTALL="""FootballNX v44 - compatibility CPU hot paths

The user reports no blinking with either v43 cache mode. Remaining pacing
in the supplied normal-cache run is about 53-56 FPS in measured play zones.
v44 removes unnecessary global logging atomics in clock/TLS access.
This is a performance candidate; stable 60 FPS is not yet device verified.

1. Back up the installed pes21_nx.nro.
2. Copy update/pes21_nx.nro into sdmc:/switch/pes21_nx/ beside the game files.
   Use this ORDINARY build first. It has no per-draw diagnostic probes and
   ignores the earlier render-control.txt file; normal GL caching is enabled.
3. Keep the same v41-7k face PAK and the already restored entrance baseline.
   No PAK, CPK, OBB, roster, texture, mesh, shader or quality changes are needed.
4. Fully restart and test the same Barca/MU lineup, Konami, camera, weather,
   quality and resolution. Pass near the camera and farther away, then Pause
   and preserve scene-runtime.log. The header must identify v44.

Optional detailed log: copy BOTH files from diagnostic/ into the NRO folder,
fully restart, repeat and Pause. The included control file selects normal
caching. Diagnostic overhead is not ordinary-build performance.

Rollback: restore the NRO backed up in step 1. This package generator does
not install anything or modify the active prepared runtime or game payloads.
"""

INSTALL_V45="""FootballNX v45 - thread/buffer overhead and native stadium preview

The user reports much smoother pacing with v44. v45 keeps that fix, caches
successful native thread IDs per thread, removes duplicate buffer free-list
searches and releases the custom VS cover when the native entrance starts.
The entrance's native scene, camera, FPS callbacks and Skip remain native.
STADIUM-V2 and the FL26 entrance canary remain suspended.
Stable 60 FPS and the restored preview still require device verification.

1. Back up the installed pes21_nx.nro (the accepted v44).
2. Copy update/pes21_nx.nro to sdmc:/switch/pes21_nx/ beside the game files.
   Use this ORDINARY build first; it omits per-draw diagnostic probes.
3. Keep the same v41-7k face PAK and the restored native dt220 baseline.
   This NRO-only update requires no new face/stadium assets or quality changes.
4. Fully restart. Check custom loading -> native stadium preview -> kickoff.
   Do not press Skip during the preview check. Play Barca/MU in native STADIUM
   with the same lineup/settings as v44, near and far from the camera.
5. Pause and preserve scene-runtime.log. It must start with v45. The native
   entrance callback records 'native prematch: entrance started; VS cover released'.
   If that entry is absent, retain the log so selection/loading can be checked;
   this update does not force an absent or failed native cinematic to play.

Optional detailed log: copy BOTH diagnostic/ files into the NRO folder,
fully restart, repeat and Pause. Normal caching is selected. Do not compare
diagnostic overhead directly with ordinary-build performance.
Rollback: restore the backed-up v44 NRO. No active runtime is modified by
this package generator, and no proprietary game payload is included.
"""

INSTALL_V46="""FootballNX v46 - repeated blend-state overhead

The user reports much smoother pacing with v45. v46 suppresses repeated,
identical glBlendFuncSeparate state within the current context/frame. It
retains the v44/v45 clock/TLS/thread-ID/buffer fixes and native preview reveal.
Texture/program shared-object binds still acquire uploads. Unknown/extension
blend factors retain native validation. STADIUM-V2 remains suspended.
Stable 60 FPS still requires measurement on Switch.

1. Back up the accepted v45 NRO. Copy update/pes21_nx.nro into the runtime.
2. First keep the exact same v41-7k face PAK and other installed assets.
   Fully restart and compare Barca/MU, native STADIUM, same lineup, quality,
   resolution and passing route. Test DAY and NIGHT separately.
3. Pause and preserve scene-runtime.log. Its header must identify v46.
4. For CPU/GPU and blend-savings measurements, copy BOTH diagnostic files
   into the NRO folder, restart, play near/far for 20 seconds each and Pause.
   The near-camera rows identify camera=6 for native STADIUM, frame times,
   blend_requests and blend_skipped. Diagnostic overhead differs from ordinary.
5. If also testing reduced-head packages, change only the face PAK after
   measuring the unchanged v41-7k control. Use exactly one extra face PAK,
   and preserve one log per run. A smaller PAK is not proof of 60 FPS.

Rollback: restore the backed-up v45 NRO and original v41-7k PAK if changed.
The package generator never modifies the active runtime. This NRO-only ZIP
includes no game payload and requires no CPK, OBB, roster or save updates.
"""

INSTALL_V47="""FootballNX v47 - overlay render-state repair and mixed model quality

The supplied v46 report describes players, ball, goals and stadium blinking
or disappearing until a transition. The wrapper overlay modified the engine's
vertex-array layout without restoring its attribute pointers/buffer formats.
v47 gives the overlay a private VAO per EGL context and restores the complete
engine VAO. Read/draw framebuffers are now kept separate, and the redundant
state cache is invalidated on both sides of the overlay boundary.
This fixes a reproduced state-restoration defect; whether it resolves every
reported device symptom still needs the following Switch test.

Model policy (player / stadium):
  LOW      = Low / Low
  STANDARD = Standard / Standard
  HIGH     = Standard / High
Only the native High player-class choice changes. Saved quality, stadium
selection, face PAK geometry/texture dimensions, animation and FPS mode remain
native. This does not force 2k heads or manufacture a missing face LOD.
Earlier v44-v46 overhead fixes and native stadium preview are retained.
STADIUM-V2 and the experimental FL26 entrance remain suspended.

1. Back up the currently installed v46 NRO.
2. Copy update/pes21_nx.nro to sdmc:/switch/pes21_nx/ beside the game files.
   Use this ORDINARY build first. Keep your current balanced-5000 face PAK,
   with only one extra face PAK active; no face/stadium recook is required.
3. Fully exit/restart. Select High, Barca/MU, native STADIUM, same lineup and
   resolution. Check ball, both goals, players and stadium from kickoff,
   through near-camera passes, an out-of-play transition and a celebration.
   Test DAY/NIGHT separately. Check a custom stadium as well as Konami.
4. Pause and preserve scene-runtime.log after each run. Its header must say
   v47, and the model quality row must report the three mappings above.
   A 'native fallback' row means the quality patch did not apply.
5. Check Low and Standard in fresh matches: their original model choices
   remain, while High should now use Standard players with High stadium.

If blinking remains, install BOTH files from diagnostic/ beside the NRO,
restart, repeat the same scene and Pause to save the detailed log. Keep the
ordinary and diagnostic logs separate; diagnostic timing is not release FPS.
The included diagnostic control retains normal GL state caching.

Rollback: restore the backed-up v46 NRO. No PAK/CPK/OBB/save update is needed.
The package generator never installs to or mutates your prepared runtime.
Stable 60 FPS, all-stadium visibility and native Standard-player appearance
are not yet verified on Switch.
"""

INSTALL_V48="""FootballNX v48 - render audit and compositor probe isolation

The reported Konami holes also occur WITHOUT the extra face PAK. A fresh
native stadium bypasses addon replacement; addon triangle budgets are offline
conversion limits, not runtime truncation of native meshes. The device
visibility failure is not yet isolated.

A reproduced defect let debug compositor glReadPixels/glGetError probes run
in ordinary and pacing builds. v48 removes them while retaining accepted
scene composition and GL state. This removes an avoidable synchronization
and error-drain path, not a measured 60 FPS guarantee.
The v47 overlay fix and quality mapping remain: Low=Low/Low,
Standard=Standard/Standard, High=Standard/High (players/stadium).
STADIUM-V2 and the experimental FL26 entrance remain suspended.

1. Back up your v47 NRO and existing scene-runtime.log.
2. Copy update/pes21_nx.nro to sdmc:/switch/pes21_nx/ beside the game files.
   Keep the same balanced-5000 face PAK and other assets/settings.
   No PAK, CPK, OBB, save or shader-cache replacement is included.
3. Fully restart. Test Barca/MU, Konami, High, native STADIUM. Pass along the
   far/top touchline, both goal ends and near-camera. Check the stand behind
   both goals from kickoff and through a corner. Pause before closing so the
   timing window is journaled.
4. Restart a second time with the same sequence. The wrapper now retains
   scene-runtime.previous.log for the prior launch and scene-runtime.log for
   this launch. Save BOTH after the second test, before another restart.
   Check the v48 header and stadium inventory.
5. If holes/pacing persist, use BOTH diagnostic/ files in the NRO folder for
   a detailed repeat. The log records near/far regions, CPU calls, sampled
   GPU stream spans and engine GL error observations, without compositor pixel
   probes. Keep ordinary/diagnostic timings separate. The supplied control
   selects normal state caching.

Optional impact check for the v47 mixed player-class patch: after measuring
the diagnostic build with its default control, replace ONLY render-control.txt
beside the NRO with controls/native-player-class/render-control.txt. Fully
restart with the same High setting and PAKs. The log must say
'diagnostic control: native player classes'. This temporarily uses original
High players with High stadium; it does not change the saved setting or assets.
If the same Konami hole remains, the mixed class patch is not sufficient to
explain it. Restore diagnostic/render-control.txt and restart to return to the
requested Standard players / High stadium policy. Ordinary NROs ignore this
control entirely. This comparison is for visibility, not a matched FPS gain.

Rollback: restore the backed-up v47 NRO. Keep assets unchanged.
The generator does not modify the active prepared runtime.
Konami visibility and stable 60 FPS still require device confirmation.
"""

CANDIDATES = {
    44: (INSTALL, b'compat hotpaths v44: release clock/TLS trace atomics removed'),
    45: (INSTALL_V45, b'compat hotpaths v45: cached native thread IDs; single-pass buffer free lists; native prematch reveal'),
    46: (INSTALL_V46,
         b'compat hotpaths v46: context-local separate blend suppression; diagnostic savings counts'),
    47: (INSTALL_V47,
         b'render stability v47: private overlay vertex state; High uses Standard players'),
    48: (INSTALL_V48,
         b'render audit v48: no compositor pixel probes/error drains in ordinary or pacing builds; native stadium inventory'),
}


def package(build_root,output,pair,version=44):
    if version not in CANDIDATES:raise ValueError('Unsupported candidate version')
    instructions,marker=CANDIDATES[version]
    build_root,output=Path(build_root).resolve(),Path(output).resolve()
    if not output.is_relative_to(ROOT/'local-debug') or output.exists():
        raise ValueError('Use a fresh ignored local-debug output')
    archive=output.with_suffix('.zip')
    if archive.exists():raise ValueError('Archive already exists')
    builds={}
    for kind in ('production','diagnostic'):
        builds[kind]=inspect_build(build_root/kind,kind=='diagnostic',pair)
        data=(build_root/kind/'pes21_nx.nro').read_bytes()
        if (f'FootballNX scene v{version} session'.encode() not in data or marker not in data):
            raise ValueError(f'Not the v{version} hot-path candidate')
        del data
    for kind,dest in (('production','update'),('diagnostic','diagnostic')):
        (output/dest).mkdir(parents=True)
        shutil.copy2(build_root/kind/'pes21_nx.nro',output/dest/'pes21_nx.nro')
    (output/'diagnostic/render-control.txt').write_bytes(b'PESNX_GL_CACHE_DEFAULT_V1\n')
    if version>=48:
        control=output/'controls/native-player-class/render-control.txt'
        control.parent.mkdir(parents=True)
        control.write_bytes(b'PESNX_NATIVE_PLAYER_CLASS_V1\n')
    (output/'INSTALL.txt').write_text(instructions,encoding='utf-8')
    proof=dict(candidate=f'Compatibility pacing hot paths v{version}',runtime_pair=pair,builds=builds,
               face_quality_changed=None if version>=47 else False,
               face_assets_changed=False,game_payload_included=False,
               model_quality_policy=(
                   {'low':['low','low'],'standard':['standard','standard'],
                    'high':['standard','high']} if version>=47 else None),
               native_high_player_class_changed=version>=47,
               compositor_diagnostic_probes_removed=version>=48,
               previous_session_journal_preserved=version>=48,
               diagnostic_native_player_class_control=version>=48,
               device_stadium_visibility_verified=False,
               device_blinking_resolved=False,
               stable_60_fps_verified=False,active_runtime_modified=False,
               files={p.relative_to(output).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
                      for p in sorted(output.rglob('*')) if p.is_file()})
    (output/'VERIFICATION.json').write_text(json.dumps(proof,indent=2)+'\n')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(output.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(output).as_posix())
    return dict(zip=str(archive),zip_bytes=archive.stat().st_size,zip_sha256=sha(archive),verification=proof)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pair',required=True)
    p.add_argument('--version',type=int,choices=tuple(CANDIDATES),default=44)
    a=p.parse_args();print(json.dumps(package(a.build_root,a.output,a.pair,a.version),indent=2))


if __name__=='__main__':main()
