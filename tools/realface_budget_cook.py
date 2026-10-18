"""Cook the completed team trial in one bounded editor process at a time.

Chunk size controls editor restarts only; geometry/material recipes and cook
verification are unchanged. This avoids reloading the whole editor for each
tiny group when DLL startup dominates on a memory-constrained Windows host.
"""
import argparse
import json
from pathlib import Path

from realface_batch_inventory import read, write
import realface_batch_release as factory
from realface_budget_experiment import CAPS, ROOT
from realface_pipeline import sha


def completed_imports(project, profiles):
    """Reuse only complete two-section imports in the same keyed cook job.

    The factory already verifies prepared hashes and the importer contract
    before calling this hook. Its normal import script also skips existing
    reports; this avoids an empty editor launch for that same case. Cooked
    geometry/rig/UV/normal verification is still mandatory afterwards.
    """
    evidence = {}
    for path in profiles:
        profile = read(path)
        report = Path(profile['report'])
        if not profile.get('opaque_eye_atlas') or not report.is_file():
            return None
        result = read(report)
        native = profile['native_player_id']
        if (result.get('status') != 'imported' or result.get('player') != native
                or set(result.get('parts', {})) != {'face', 'hair'}):
            return None
        names = [str(native)+suffix for suffix in
                 ('_face', '_hair', '_face_tablet', '_hair_parts_color_tablet')]
        names.append('face_'+str(native))
        for name in names:
            asset = Path(project)/'Content/Assets/character/RealFace'/(name+'.uasset')
            if not asset.is_file() or not asset.stat().st_size:
                return None
            evidence[str(asset)] = sha(asset)
        evidence[str(report)] = sha(report)
    return evidence or None


def resume_import_chunk(config, project, batch, profiles, index):
    evidence = completed_imports(project, profiles)
    if evidence is None:
        return ORIGINAL_IMPORT(config, project, batch, profiles, index)
    write(batch/('import-%03d'%index)/'resume-complete.json',
          dict(profiles=profiles, imported_asset_hashes=evidence,
               cooked_verification_required=True))
    print(json.dumps(dict(import_chunk_reused=index+1, players=len(profiles))), flush=True)


ORIGINAL_IMPORT = factory.import_chunk


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--chunk-size', type=int, choices=range(1,17), default=8)
    a = p.parse_args()
    config = read(a.config)
    work = Path(config['work_dir']).resolve()
    if (not work.is_relative_to(ROOT/'local-debug') or
            config.get('experimental_head_cap') not in CAPS or
            config.get('experimental_teams') != [100,108]):
        raise ValueError('Only the explicit local Barca/MU experiment is supported')
    config['import_chunk_size'] = a.chunk_size
    write(work/'config.local.json', config)
    factory.import_chunk = resume_import_chunk
    try:
        factory.cook(config)
    finally:
        factory.import_chunk = ORIGINAL_IMPORT


if __name__ == '__main__':
    main()
