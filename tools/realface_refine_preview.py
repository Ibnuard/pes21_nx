"""Render independently verified heads with decoded cooked colour textures."""
import json
from pathlib import Path

from cooked_texture import Texture
from realface_batch import command, valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_pipeline import sha
from realface_refine import baseline, HERE
from realface_surface_patch import FACE


def preview(config):
    report, owners = baseline(config)
    work = Path(config['work_dir'])
    planned = {r['base_id']:r for r in read(work/'plan.json')['players']}
    rows = read(work/'verify-report.json')
    output = work/'cooked-previews'
    output.mkdir(parents=True, exist_ok=True)
    targets = []
    for row in rows:
        if (row['status'] not in ('validated','validated_cached') or
                row['cache_key'] != planned[row['base_id']]['cache_key'] or
                not valid_cache(Path(row['cooked_folder']), row['cooked_cache_key']) or
                not valid_prepared_cache(Path(row['folder']), row['cache_key'])):
            raise ValueError('Preview requires current verified prepared and cooked geometry')
        native, base = str(row['native_player_id']), str(row['base_id'])
        before = Path(owners[row['base_id']]['cooked_folder'])/'assets'
        after = Path(row['cooked_folder'])/'assets'
        decoded = {}
        for role, suffix in (('skin','_face_tablet'), ('hair','_hair_parts_color_tablet')):
            source = after if role=='hair' and row['refine_hair'] else before
            for ext in ('.uasset','.uexp','.ubulk'):
                if source == before and sha(source/(native+suffix+ext)) != report['asset_hashes'][FACE+native+suffix+ext]:
                    raise ValueError('Baseline preview texture differs from mounted release')
            target = output/(base+'-'+role+'.png')
            Texture(source/(native+suffix+'.uexp')).decode().save(target)
            decoded[role] = str(target)
        recipe = dict(folder=row['folder'], native_rig=config['native_rig'], cooked_rig=config['cooked_rig'],
                      texture_overrides=decoded)
        targets.append(dict(recipe=recipe, output=str(output/(base+'-front.png'))))
        if row['refine_hair']:
            targets.append(dict(recipe=dict(recipe, view_offset=[-35,80,20]), output=str(output/(base+'-angle.png'))))
    if {r['base_id'] for r in rows} != set(planned):
        raise ValueError('Preview coverage differs from the repair plan')
    write(output/'targets.json', targets)
    command([config['blender'], '--background', '--threads', '2', '--python-exit-code', '1',
             '--python', HERE/'blender_preview_realface.py', '--', output/'targets.json'], output/'render.log')
    write(output/'PROVENANCE.json', dict(prepared_geometry_verified_against_cooked=True,
                                        decoded_cooked_colour_textures=True, hardware_capture=False,
                                        players=[dict(base_id=r['base_id'],name=r['name']) for r in rows],
                                        render_code_sha256=sha(HERE/'blender_preview_realface.py')))
    print(json.dumps(dict(previews=str(output), views=len(targets), hardware_capture=False)), flush=True)
