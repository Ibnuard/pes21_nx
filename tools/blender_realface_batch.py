"""Run one prepared face's conversion stages in one Blender process.

Reuses the audited exporters/validators without paying startup cost per stage.
The external controller caches only fully verified output sets.
"""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import main as export_fbx
from blender_fit_eye_sockets import fit as fit_eyes
from blender_fit_realface import fit
from validate_realface_fit import validate
from blender_realface_empty_hair import ensure_hair_slot


def run(profile):
    folder = Path(profile['folder'])
    timings = {}
    empty_hair = None
    for part in ('face', 'hair'):
        start = time.monotonic()
        args = ['worker', '--', '--input', profile['gltf']['face'],
                '--additional-input', profile['gltf']['hair'],
                '--output', str(folder / ('prepared/' + part + '.fbx')),
                '--flip-faces', '--recompute-normals', '--runtime-bind-reference',
                profile['native_rig'], profile['cooked_rig'], '--runtime-mirror-x']
        if part == 'face':
            args += ['--additional-input', profile['template_eye']]
        for name in profile['materials'][part]:
            args += ['--include-material', name]
        sys.argv = args
        export_fbx()
        if part == 'hair':
            empty_hair = ensure_hair_slot(profile, folder / 'prepared/hair.fbx')
        timings['export_' + part] = time.monotonic() - start
    start = time.monotonic()
    eye = dict(profile['eye'], face_fbx=str(folder / 'prepared/face.fbx'),
               native_rig=profile['native_rig'], cooked_rig=profile['cooked_rig'],
               output=str(folder / 'eyes/face.fbx'), base_id=profile['base_id'])
    fit_eyes(eye)
    timings['eyes'] = time.monotonic() - start
    outputs = {}
    for part in ('face', 'hair'):
        if part == 'hair' and (empty_hair or not profile['hair_skin_materials']):
            outputs[part] = str(folder / 'prepared/hair.fbx')
            continue
        start = time.monotonic()
        candidate = folder / ('fitted_' + part)
        recipe = dict(profile['fit'], base_id=profile['base_id'],
                      face_fbx=str(folder / ('eyes/face.fbx' if part == 'face' else 'prepared/hair.fbx')),
                      native_rig=profile['native_rig'], cooked_rig=profile['cooked_rig'],
                      output=str(candidate))
        fit(recipe)
        validate(recipe, candidate)
        outputs[part] = str(candidate / 'face.fbx')
        timings['fit_validate_' + part] = time.monotonic() - start
    (folder / 'blender-result.json').write_text(
        json.dumps(dict(outputs=outputs, timings=timings, empty_hair_slot=empty_hair), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    path = Path(sys.argv[sys.argv.index('--') + 1])
    run(json.loads(path.read_text(encoding='utf-8')))
