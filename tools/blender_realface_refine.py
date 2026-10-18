"""Batch worker: repair selected surfaces without exceeding mobile head limits."""
import json
from pathlib import Path
import shutil
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_export_ue_fbx import rig_globals
from blender_realface_lite import reduce_part
from realface_pipeline import sha
from realface_surface_quality import audit, needs_refinement


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def output_hashes(folder):
    # Blender's bundled Python intentionally has no dependency on the host's
    # Pillow/CPK inventory stack imported by realface_batch.
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*'))
            if p.is_file() and p.name not in ('complete.json', 'failure.json') and p.suffix != '.log'}


def prepare(entry):
    folder, old = Path(entry['folder']), Path(entry['baseline']['folder'])
    if (folder/'complete.json').exists():
        stamp = read(folder/'complete.json')
        if stamp['cache_key'] == entry['cache_key'] and stamp['outputs'] == output_hashes(folder):
            return dict(entry, status='prepared_cached')
        raise ValueError('Previously prepared refinement cache changed')
    folder.mkdir(parents=True, exist_ok=True)
    job = read(old/'job.json')
    job.update(folder=str(folder), budgets=entry['budgets'])
    write(folder/'job.json', job)
    native, cooked = (rig_globals(read(job[name])) for name in ('native_rig', 'cooked_rig'))
    old_proof, ue = read(old/'simplification.json'), read(old/'ue-profile.json')
    proof = {}
    for part in ('face', 'hair'):
        if entry['refine_'+part]:
            proof[part] = reduce_part(job, part, native, cooked)
        else:
            shutil.copy2(ue[part+'_fbx'], folder/(part+'.fbx'))
            proof[part] = old_proof[part]
    if not entry['refine_face']:
        shutil.copy2(old/'opaque-atlas.png', folder/'opaque-atlas.png')
    # A changed skin index buffer must not move the eye atlas or its UV crop.
    # Reusing the original cooked colour texture is then independently safe.
    if sha(folder/'opaque-atlas.png') != sha(old/'opaque-atlas.png'):
        raise ValueError('Face atlas changed; this selective recipe preserves original colour assets')
    projection = None
    if entry['refine_face']:
        projection = audit(read(folder/'lite_skin-meshopt.json'),
                           read(folder/'lite_skin-meshopt-result.json')['indices'])
        write(folder/'surface-projection.json', projection)
        if needs_refinement(projection):
            raise ValueError('Visible face UV distortion remains above the refinement gate')
        for metric in ('mouth_uv_p95_max', 'face_uv_p95_max'):
            if projection[metric] > entry['baseline_projection'][metric]:
                raise ValueError('Refinement regresses '+metric)
    total = sum(p['total'] for p in proof.values())
    if not 0 < total <= 2000:
        raise ValueError('Refined complete head exceeds the 2,000-triangle ceiling')
    proof.update(base_id=entry['base_id'], native_player_id=entry['native_player_id'],
                 total_triangles=total, hardware_accepted=False)
    write(folder/'simplification.json', proof)
    ue.update(face_fbx=str(folder/'face.fbx'), hair_fbx=str(folder/'hair.fbx'),
              face_texture=str(folder/'opaque-atlas.png'))
    if entry['refine_hair']:
        ue['hair_texture'] = str(folder/'hair-shell.png')
    ue.pop('report', None)
    write(folder/'ue-profile.json', ue)
    write(folder/'recipe.json', dict(eye={}, source=entry['baseline'], mobile_v35=True,
                                     refinement=dict(face=entry['refine_face'], hair=entry['refine_hair'])))
    write(folder/'complete.json', dict(cache_key=entry['cache_key'], outputs=output_hashes(folder)))
    return dict(entry, status='prepared', triangles=total)


def run(manifest):
    records = []
    for entry in manifest['players']:
        try:
            record = prepare(entry)
        except Exception as error:
            traceback.print_exc()
            record = dict(entry, status='held_geometry', reason=str(error))
            write(Path(entry['folder'])/'held.json', dict(reason=str(error)))
        records.append(record)
        write(manifest['report'], records)
        print(json.dumps({k: record[k] for k in ('base_id', 'name', 'status', 'triangles', 'reason') if k in record}), flush=True)


if __name__ == '__main__':
    run(read(sys.argv[sys.argv.index('--')+1]))
