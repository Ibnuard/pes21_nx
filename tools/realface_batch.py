"""Resumable local realface factory: plan, prepare, cook, verify and package.

Configuration supplies user-owned tools/assets, leagues, identity state and
runtime. Cache keys include source payloads, recipes, references and tool code.
Nothing modifies the active runtime. No online service or generative model is
needed when processing or repeating a batch.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import time

from extract_team_realfaces import extract
from export_pes_fmdl_gltf import load_fmdl, export_model, load_ue4_skeleton_contract, _mobile_bone_name
from realface_batch_inventory import inventory, read, write
from realface_material_policy import classify
from realface_material_atlas import build_atlas
from realface_source_geometry import prune_collapsed_fillers, prune_disabled_nan_meshes, prune_collapsed_triangles
from realface_pipeline import sha

HERE = Path(__file__).resolve().parent
PREFIX = 'PesMobile/Content/Assets/character/RealFace/'
CODE = ('realface_batch.py', 'realface_batch_inventory.py', 'blender_realface_batch.py',
        'blender_export_ue_fbx.py', 'export_pes_fmdl_gltf.py', 'realface_material_policy.py',
        'blender_fit_realface.py', 'blender_fit_eye_sockets.py', 'realface_eye_fit.py',
        'realface_reference.py', 'validate_realface_fit.py', 'realface_material_atlas.py',
        'extract_team_realfaces.py', 'realface_source_identity.py', 'realface_source_geometry.py',
        'realface_eye_registration.py', 'realface_eye_boundary.py', 'blender_realface_empty_hair.py',
        'realface_neck_support.py')


def key_of(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def command(args, log):
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with Path(log).open('w', encoding='utf-8') as stream:
        subprocess.run([str(a) for a in args], check=True, stdout=stream, stderr=subprocess.STDOUT)


def output_hashes(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in sorted(folder.rglob('*'))
            if p.is_file() and p.name not in ('complete.json', 'failure.json') and p.suffix != '.log'}


def valid_cache(folder, key):
    stamp = folder / 'complete.json'
    if not stamp.is_file():
        return False
    saved = read(stamp)
    return (saved.get('cache_key') == key and bool(saved.get('outputs')) and
            saved['outputs'] == output_hashes(folder))


def valid_prepared_cache(folder, key):
    """UE's FBX importer can extract embedded images beside a verified FBX.

    Keep the original proof immutable. Only extra .fbm PNG files with exactly
    the same name AND bytes as a verified texture are benign. Missing or
    modified original files, arbitrary images and other extras still fail.
    """
    stamp = folder / 'complete.json'
    if not stamp.is_file():
        return False
    saved = read(stamp)
    expected = saved.get('outputs', {})
    if saved.get('cache_key') != key or not expected:
        return False
    actual = output_hashes(folder)
    if any(actual.get(name) != digest for name,digest in expected.items()):
        return False
    textures = {(Path(name).name, digest) for name,digest in expected.items() if name.endswith('.png')}
    for name in actual.keys() - expected.keys():
        path = Path(name)
        sibling = path.parent.with_suffix('.fbx').as_posix()
        if (path.parent.suffix != '.fbm' or sibling not in expected
                or (path.name, actual[name]) not in textures):
            return False
    return True


def previous_verified(config, inv):
    """Explicitly carry independently validated assets into an incremental run.

    A new converter recipe need not rebuild successful older assets. Their
    original keys/proofs remain intact; only failed/new players use the new
    recipe. Changed identity, source bytes or cache contents prevent reuse.
    """
    if not config.get('reuse_verified_batch'):
        return {}
    work = Path(config['reuse_verified_batch'])
    old = read(work / 'inventory.local.json')
    for key in ('source_state_sha256', 'source_cpk_sha256', 'selector_sha256', 'catalog_sha256'):
        if inv[key] != old[key]:
            raise ValueError('Previous batch runtime/identity changed: ' + key)
    if inv['archives'] != old['archives']:
        raise ValueError('Previous source archives changed')
    previous = {p['base_id']: p for p in old['players']}
    current = {p['base_id']: p for p in inv['players']}
    rows = {}
    for row in read(work / 'verify-report.json'):
        if row['status'] not in ('validated', 'validated_cached'):
            continue
        base = row['base_id']
        a, b = previous[base], current.get(base)
        if not b or b['status'] != 'source_ready':
            continue
        if any(a[k] != b[k] for k in ('native_player_id', 'fingerprint', 'source_player', 'source_members')):
            continue
        rows[base] = dict(row, reused_from=str(work))
    return rows


def reuse_verified(row):
    # The independently validated cooked assets are the reusable product.
    # Their old .blend/glTF intermediates will not enter this release or be
    # recooked; only the locked identity profile is needed from preparation.
    if not valid_cache(Path(row['cooked_folder']), row['cooked_cache_key']):
        raise ValueError('Previously verified cache changed: ' + str(row['base_id']))
    prepared = Path(row['folder'])
    stamp = read(prepared / 'complete.json')
    if (stamp.get('cache_key') != row['cache_key'] or
            sha(prepared / 'ue-profile.json') != stamp['outputs'].get('ue-profile.json')):
        raise ValueError('Previously verified identity profile changed')
    profile = read(prepared / 'ue-profile.json')
    if any(profile[k] != row[k] for k in ('base_id','native_player_id')):
        raise ValueError('Previously verified identity ownership changed')
    return dict(row, status='prepared_cached', elapsed_seconds=0,
                reuse_cooked={k: row[k] for k in ('cooked_folder', 'cooked_cache_key', 'reused_from')})


def verify_inputs(config, inv):
    for path, expected in ((config['identity_state'], inv['source_state_sha256']),
                           (Path(config['runtime_base']) / 'LooseCpk/dt200_mobile_all.cpk', inv['source_cpk_sha256']),
                           (config['selector'], inv['selector_sha256']),
                           (config['catalog'], inv['catalog_sha256'])):
        if sha(path) != expected:
            raise ValueError('Runtime/identity/selection changed since plan: ' + str(path))


def classify_documents(documents):
    """Give materials globally unique role names before merging glTF parts.

    File names and source material labels do not determine skin/hair roles.
    Unsupported multi-atlas shaders are held, never flattened by guessing.
    """
    roles, counts = {}, Counter()
    for part, doc in documents.items():
        roles[part] = []
        for material in doc['materials']:
            role = classify(material)
            if role['role'] == 'hair':
                if role['requires_texture_bake']:
                    raise ValueError('Hair uses multiple atlases; explicit bake policy required')
                if role['textures'].get('Base_Tex_SRGB', '').lower() not in ('hair_parts_bsm_alp.dds', 'native_hair_bsm_alp.dds'):
                    raise ValueError('Hair base atlas differs from supported native hair texture')
            kind = role['role']
            if kind in ('skin', 'hair'):
                number = counts[kind]
                name = 'rf_' + kind + ('.%03d' % number if number else '')
                counts[kind] += 1
            else:
                name = 'excluded_' + part + '_' + str(len(roles[part]))
            role['output_name'] = name
            material['name'] = name
            roles[part].append(role)
    if not counts['skin']:
        raise ValueError('No supported main skin surface')
    if counts['hair']:
        face = [r['output_name'] for rows in roles.values() for r in rows if r['role'] == 'skin']
        hair = [r['output_name'] for rows in roles.values() for r in rows if r['role'] == 'hair']
        scalp = []
    else:
        # Bald source: keep its scalp in the runtime hair slot, using skin.
        face = [r['output_name'] for r in roles['face'] if r['role'] == 'skin']
        scalp = [r['output_name'] for r in roles['hair'] if r['role'] == 'skin']
        hair = scalp
        if not face or not scalp:
            raise ValueError('No separate scalp/hair surface for native hair slot')
    return roles, dict(face=face + ['eye_mat'], hair=hair), scalp


def reference_hashes(config):
    files = {str(HERE / name): sha(HERE / name) for name in CODE}
    for name in ('blender', 'skeleton_contract', 'native_rig', 'cooked_rig',
                 'template_eye', 'template_eye_texture', 'native_neck', 'native_body'):
        p = Path(config[name])
        files[str(p)] = sha(p)
        if p.suffix == '.gltf':
            for b in read(p)['buffers']:
                binary = (p.parent / b['uri']).resolve()
                if not binary.is_relative_to(p.parent.resolve()):
                    raise ValueError('Reference buffer escaped input directory')
                files[str(binary)] = sha(binary)
    for parser in ('fmdl_parser', 'texture_parser'):
        for p in sorted(Path(config[parser]).rglob('*.py')):
            files[str(p)] = sha(p)
    return files


def native_reference(config, player, names, work):
    base = player['base_id']
    if (player['registry'].get('face_owner_id') != base or
            player['native_player_id'] != base or PREFIX + str(base) + '_face.uasset' not in names):
        return None
    folder = work / 'native-v2' / str(base)
    out = folder / ('gltf/Assets/character/RealFace/' + str(base) + '_face.gltf')
    stamp = folder / 'complete.json'
    key = key_of(dict(base=base, main_pak=config['main_pak_sha256'], umodel=sha(config['umodel'])))
    if valid_cache(folder, key):
        return out
    if folder.exists():
        raise ValueError('Incomplete/changed native reference; choose a fresh cache directory')
    folder.mkdir(parents=True)
    wanted = sorted(n for n in names if n.startswith(PREFIX + str(base) + '_face.') or
                    n.startswith(PREFIX + str(base) + '_face_tablet.'))
    args = [config['repak'], 'unpack', config['main_pak'], '-o', folder / 'assets', '-q']
    for name in wanted:
        args += ['-i', name]
    command(args, folder / 'extract.log')
    command([config['umodel'], '-export', '-gltf', '-png', '-game=ue4.22',
             '-path=' + str(folder / 'assets/PesMobile/Content'), '-out=' + str(folder / 'gltf'),
             str(base) + '_face'], folder / 'export.log')
    command([config['umodel'], '-export', '-png', '-game=ue4.22',
             '-path=' + str(folder / 'assets/PesMobile/Content'), '-out=' + str(folder / 'gltf'),
             str(base) + '_face_tablet'], folder / 'export-texture.log')
    if not out.is_file() or not out.with_name(str(base) + '_face_tablet.png').is_file():
        raise ValueError('Native eye atlas export missing')
    write(stamp, dict(cache_key=key, outputs=output_hashes(folder)))
    return out


def prepare_player(config, inv, p, references, names):
    start = time.monotonic()
    work = Path(config['cache_dir'])
    base = p['base_id']
    record = dict(base_id=base, native_player_id=p['native_player_id'], name=p['name'])
    folder = None
    try:
        extraction = extract(dict(archives=inv['archives'], players=[p]), work / 'inputs-v2', Path(config['texture_parser']), all_textures=True)[0]
        own = native_reference(config, p, names, work)
        native_files = {str(own): sha(own)} if own else {}
        if own:
            for b in read(own)['buffers']:
                path = own.parent / b['uri']
                native_files[str(path)] = sha(path)
            atlas = own.with_name(str(base) + '_face_tablet.png')
            native_files[str(atlas)] = sha(atlas)
        key = key_of(dict(extraction=extraction, references=references, native=native_files,
                          identity={k:p[k] for k in ('base_id', 'native_player_id', 'fingerprint')}, fit=config['fit']))
        folder = work / 'jobs' / (str(base) + '-' + key[:16])
        record.update(cache_key=key, folder=str(folder))
        if valid_prepared_cache(folder, key):
            return dict(record, status='prepared_cached', elapsed_seconds=0)
        if folder.exists():
            reason = read(folder / 'failure.json')['reason'] if (folder / 'failure.json').exists() else 'Incomplete or changed cache output'
            return dict(record, status='held_conversion', reason=reason, cached_failure=True)
        folder.mkdir(parents=True)
        source = work / 'inputs-v2' / str(base) / 'source'
        png = next(source.rglob('face_bsm_alp.png')).parent
        contract = load_ue4_skeleton_contract(Path(config['skeleton_contract']))
        docs, models = {}, {}
        for part in ('face', 'hair'):
            fmdl = next(source.rglob(part + '_high.fmdl'))
            models[part] = load_fmdl(fmdl, Path(config['fmdl_parser']))
        textures = folder / 'textures'
        textures.mkdir()
        for name in ('face_bsm_alp.png', 'hair_parts_bsm_alp.png'):
            if (png / name).is_file():
                shutil.copy2(png / name, textures / name)
        guide = [(-v.position.x * 100, v.position.z * 100, v.position.y * 100)
                 for model in models.values() for m in model.meshes
                 if m.materialInstance.technique == 'pes3DFW_EyeOcclusion' for v in m.vertices]
        globes = []
        for model in models.values():
            for m in model.meshes:
                base_texture = dict(m.materialInstance.textures).get('Base_Tex_SRGB')
                if base_texture and Path(base_texture.filename).name.lower() in ('eye.dds', 'eye_sclera_bsm.dds'):
                    globes.extend((-v.position.x*100,v.position.z*100,v.position.y*100) for v in m.vertices)
        excluded = []
        mobile_names={b['name'] for b in contract}
        for part, model in models.items():
            # Helper planes and PC-only eyes are references, not runtime
            # surfaces. Do not validate/export their unused bones or textures.
            def role(material):
                return classify(dict(name=material.name, extras=dict(fmdlTechnique=material.technique,
                    fmdlTextures=[dict(role=k,filename=t.filename) for k,t in material.textures])))['role']
            excluded.extend(dict(part=part, material=m.materialInstance.name, role=role(m.materialInstance))
                            for m in model.meshes if role(m.materialInstance) not in ('skin','hair'))
            model.meshes = [m for m in model.meshes if role(m.materialInstance) in ('skin','hair')]
            excluded.extend(dict(part=part,role='disabled_nonrendering_mesh',**r)
                            for r in prune_disabled_nan_meshes(model))
            excluded.extend(dict(part=part, role='collapsed_nonrendering_filler', **r)
                            for r in prune_collapsed_fillers(model,lambda b:_mobile_bone_name(b.name,mobile_names)))
            excluded.extend(dict(part=part,role='collapsed_nonrendering_triangles',**r)
                            for r in prune_collapsed_triangles(model,lambda b:_mobile_bone_name(b.name,mobile_names)))
        # Nonrendering source fillers must be removed before resolving textures;
        # their intentionally absent images are not visible hair dependencies.
        atlas, atlas_audit = build_atlas(models, png, textures / 'native_hair_bsm_alp.png')
        write(folder / 'atlas-policy.json', dict(policy='native_primary_diffuse_alpha_v1', materials=atlas_audit))
        for part, model in models.items():
            used_materials = {id(m.materialInstance) for m in model.meshes}
            model.materialInstances = [m for m in model.materialInstances if id(m) in used_materials]
            used_bones = {id(b) for m in model.meshes for v in m.vertices
                          for b,w in (v.boneMapping or {}).items() if w>0}
            model.bones = [b for b in model.bones if id(b) in used_bones]
            path = folder / ('gltf/' + part + '.gltf')
            path.parent.mkdir(parents=True, exist_ok=True)
            docs[part] = export_model(model, path, source_name=part + '_high.fmdl', texture_root=textures,
                                     target_skeleton=contract, position_scale=100)
        write(folder / 'excluded-helpers.json', excluded)
        roles, materials, scalp = classify_documents(docs)
        for part, doc in docs.items():
            write(folder / ('gltf/' + part + '.gltf'), doc)
        write(folder / 'material-policy.json', roles)
        rim = folder / 'eyelid-rim.json'
        write(rim, dict(negative_x=[v for v in guide if v[0] < 0], positive_x=[v for v in guide if v[0] > 0]))
        eye = dict(eyelid_rim=str(rim), replace_material='eye_mat', eye_material='batch_eye_mat',
                   template_pupil_uv=[.5, .5], register_eye_pair=True, skin_boundary_fallback=True,
                   source_policy='Shared neutral FL26 iris template; no donor player identity')
        if globes:
            globe_path = folder / 'source-eyeballs.json'
            write(globe_path,dict(negative_x=[v for v in globes if v[0]<0],positive_x=[v for v in globes if v[0]>0]))
            eye['source_globes'] = str(globe_path)
        if own:
            eye.update(own_native_face=str(own), source_policy='Own native eye geometry/atlas fitted to own FL26 eyelid guide')
        profile = dict(base_id=base, native_player_id=p['native_player_id'], folder=str(folder),
                       native_rig=config['native_rig'], cooked_rig=config['cooked_rig'],
                       template_eye=config['template_eye'], materials=materials, hair_skin_materials=scalp,
                       gltf={part: str(folder / ('gltf/' + part + '.gltf')) for part in docs}, eye=eye,
                       fit=dict(native_face=str(own) if own else config['native_neck'], native_body=config['native_body'],
                                skin_material='rf_skin', fit=config['fit']))
        write(folder / 'recipe.json', profile)
        # A long batch may overlap tool edits during development. Never stamp
        # output with the old recipe key if the Blender code changed mid-job.
        def check_recipe_code():
            if any(sha(HERE/name)!=references[str(HERE/name)] for name in CODE):
                raise ValueError('Converter code changed during preparation; retry with a fresh recipe')
        check_recipe_code()
        command([config['blender'], '--background', '--threads', '2', '--python-exit-code', '1', '--python',
                 HERE / 'blender_realface_batch.py', '--', folder / 'recipe.json'], folder / 'blender.log')
        check_recipe_code()
        result = read(folder / 'blender-result.json')
        ue = dict(base_id=base, native_player_id=p['native_player_id'], fingerprint=p['fingerprint'],
                  face_fbx=result['outputs']['face'], hair_fbx=result['outputs']['hair'],
                  face_texture=str(textures / 'face_bsm_alp.png'), hair_texture=str(atlas or (textures / 'face_bsm_alp.png' if scalp else textures / 'hair_parts_bsm_alp.png')),
                  hair_texture_size=256 if atlas and len(atlas_audit) > 1 else 128,
                  native_eye_texture=str(own.with_name(str(base) + '_face_tablet.png')) if own else config['template_eye_texture'],
                  eye_material='batch_eye_mat', skin_materials=[n.replace('.', '_') for n in materials['face'] if n != 'eye_mat'],
                  hair_materials=[n.replace('.', '_') for n in materials['hair'] if n not in scalp],
                  hair_skin_materials=[n.replace('.', '_') for n in scalp])
        if result.get('empty_hair_slot'):
            from PIL import Image
            blank = textures / 'empty_hair.png'
            # Match the native mobile texture size. UE stores a 4x4 image
            # inline, omitting the .ubulk required by the asset contract.
            Image.new('RGBA', (128, 128), (0, 0, 0, 0)).save(blank)
            ue.update(hair_texture=str(blank), hair_texture_size=128,
                      hair_materials=[result['empty_hair_slot']['material']], hair_skin_materials=[],
                      empty_hair_slot=result['empty_hair_slot'])
        write(folder / 'ue-profile.json', ue)
        write(folder / 'complete.json', dict(cache_key=key, outputs=output_hashes(folder), hardware_accepted=False))
        return dict(record, status='prepared', elapsed_seconds=round(time.monotonic() - start, 2))
    except Exception as error:
        reason = str(error)
        if folder and (folder / 'blender.log').exists():
            lines = (folder / 'blender.log').read_text(encoding='utf-8', errors='replace').splitlines()
            tail = [line for line in lines if ('Error:' in line or 'Exception:' in line) and not line.startswith('Error: script failed')]
            if tail:
                reason = tail[-1]
        record.update(status='held_conversion', reason=reason)
        if folder:
            write(folder / 'failure.json', record)
        return record


def prepare(config, inv, selected=None, workers=2):
    if sha(config['main_pak']) != config['main_pak_sha256']:
        raise ValueError('Main native PAK changed')
    names = set(subprocess.check_output([config['repak'], 'list', config['main_pak']], text=True).splitlines())
    references = reference_hashes(config)
    previous = previous_verified(config, inv)
    players = [p for p in inv['players'] if p['status'] == 'source_ready' and
               (not selected or p['base_id'] in selected)]
    work = Path(config['work_dir'])
    records = [r for r in read(work / 'prepare-report.json') if r['base_id'] not in selected] if selected and (work / 'prepare-report.json').exists() else []
    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(reuse_verified, previous[p['base_id']]) if p['base_id'] in previous
                   else pool.submit(prepare_player, config, inv, p, references, names) for p in players]
        try:
            for future in as_completed(futures):
                row = future.result()
                records.append(row)
                write(work / 'prepare-report.json', records)
                completed += 1
                print(json.dumps(dict(completed=completed, total=len(players), **row), ensure_ascii=True), flush=True)
        except Exception as error:
            print(json.dumps(dict(fatal_error=str(error))), flush=True)
            for future in futures:
                future.cancel()
            raise
    return records


def pending_players(inv, records):
    prepared = {r['base_id']: r for r in records if r['status'] in ('prepared', 'prepared_cached')}
    result = set()
    for player in inv['players']:
        if player['status'] != 'source_ready':
            continue
        old = prepared.get(player['base_id'])
        if old and old['native_player_id'] != player['native_player_id']:
            raise ValueError('Prepared identity moved; create a new locked batch')
        if not old:
            result.add(player['base_id'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'prepare', 'cook', 'verify', 'package', 'run'))
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--player', type=int, action='append')
    parser.add_argument('--retry-held', action='store_true',
                        help='Prepare only failed/new sources; explicit --player values add targeted retries')
    parser.add_argument('--workers', type=int, default=2, choices=range(1, 5))
    args = parser.parse_args()
    if args.player and args.command in ('package', 'run', 'verify'):
        parser.error('--player is only supported by prepare and cook')
    if args.retry_held and args.command != 'prepare':
        parser.error('--retry-held is only supported by prepare')
    config = read(args.config)
    work = Path(config['work_dir']).resolve()
    root = HERE.parent
    for name in ('work_dir', 'cache_dir'):
        p = Path(config[name]).resolve()
        if not any(p.is_relative_to(root / d) and p != root / d for d in ('local-inputs', 'local-debug')):
            raise ValueError('Batch output must be a dedicated ignored local directory')
    if args.command == 'plan' or (args.command == 'run' and not (work / 'inventory.local.json').exists()):
        result = inventory(config)
        write(work / 'inventory.local.json', result)
        print(json.dumps(dict(teams=len(result['teams']), players=len(result['players']), counts=result['counts'])))
    if args.command != 'plan':
        inv = read(work / 'inventory.local.json')
        verify_inputs(config, inv)
        if args.command in ('prepare', 'run'):
            selected = set(args.player or [])
            if args.retry_held:
                records = read(work / 'prepare-report.json') if (work / 'prepare-report.json').exists() else []
                selected |= pending_players(inv, records)
            if args.retry_held and not selected:
                print(json.dumps(dict(pending=0, message='No failed/new sources to prepare')))
            else:
                prepare(config, inv, selected, args.workers)
        if args.command in ('cook', 'run'):
            from realface_batch_release import cook
            cook(config, set(args.player or []))
        if args.command in ('verify', 'run'):
            from realface_batch_release import verify
            verify(config, args.workers)
        if args.command in ('package', 'run'):
            from realface_batch_package import package
            result = package(config)
            print(json.dumps({k: result[k] for k in ('new_faces', 'preserved_faces', 'pak_entries', 'pak_sha256')}))


if __name__ == '__main__':
    main()
