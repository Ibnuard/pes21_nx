"""Cook and independently validate prepared faces; package only their assets.

Cooked caches are per player, so new batches cook only new/changed recipes.
Shared skeletons and materials are cook dependencies and never enter a PAK.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import zipfile

from realface_batch import HERE, PREFIX, command, key_of, output_hashes, valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_pipeline import sha


def engine_key(config):
    files = {str(HERE / name): sha(HERE / name) for name in
             ('ue_prepare_realface.py', 'validate_realface_cooked.py', 'audit_realface_rig.py',
              'realface_cook_policy.py', 'blender_fit_realface.py', 'realface_batch_release.py',
              'blender_realface_validate_worker.py', 'realface_validation_process.py',
              'realface_import_cache.py', 'realface_neck_support.py',
              'realface_triangle_audit.py', 'realface_vertex_audit.py')}
    for name in ('ue_editor', 'uassetgui', 'umodel'):
        files[config[name]] = sha(config[name])
    template = Path(config['ue_template'])
    for sub in ('Content/Assets/character/BaseAssets', 'Config'):
        for p in sorted((template / sub).rglob('*')):
            if p.is_file(): files[str(p)] = sha(p)
    return key_of(files)


def check_import_completion(profiles, marker):
    """Allow UE's error exit only for a completed, individually reported batch."""
    if not marker.is_file() or read(marker).get('profiles') != len(profiles):
        raise ValueError('Import commandlet did not complete the entire batch')
    failed = 0
    for path in profiles:
        profile = read(path)
        result = read(profile['report'])
        if result.get('status') == 'imported':
            if (result.get('player') != profile['native_player_id'] or
                    set(result.get('parts', {})) != {'face', 'hair'}):
                raise ValueError('Import report identity or mesh parts differ: ' + str(path))
        elif result.get('status') == 'failed' and result.get('reason'):
            failed += 1
        else:
            raise ValueError('Import report is incomplete: ' + str(path))
    return failed


def cook(config, selected=None):
    work = Path(config['work_dir'])
    rows = [p for p in read(work / 'prepare-report.json') if p['status'] in ('prepared', 'prepared_cached')
            and (not selected or p['base_id'] in selected)]
    if not rows: raise ValueError('No validated prepared faces to cook')
    engine = engine_key(config)
    pending, records = [], []
    def classify_cache(row):
        if row.get('reuse_cooked'):
            previous = row['reuse_cooked']
            if not valid_cache(Path(previous['cooked_folder']), previous['cooked_cache_key']):
                raise ValueError('Previously verified cooked cache changed: ' + str(row['base_id']))
            # These assets will not be recooked. Only the identity profile is
            # read from the prepared cache; gigabytes of unused .blend/glTF
            # intermediates need not be hashed again at this stage.
            prepared = Path(row['folder'])
            stamp = read(prepared / 'complete.json')
            if (stamp.get('cache_key') != row['cache_key'] or
                    sha(prepared / 'ue-profile.json') != stamp['outputs'].get('ue-profile.json')):
                raise ValueError('Previously verified identity profile changed')
            return dict(row, **previous, status='cooked_cached')
        if not valid_prepared_cache(Path(row['folder']), row['cache_key']):
            raise ValueError('Prepared face cache changed: ' + str(row['base_id']))
        key = key_of(dict(prepared=row['cache_key'], engine=engine))
        destination = Path(config['cache_dir']) / 'cooked' / (str(row['base_id']) + '-' + key[:16])
        entry = dict(row, cooked_cache_key=key, cooked_folder=str(destination))
        if valid_cache(destination, key):
            entry['status'] = 'cooked_cached'
        else:
            if destination.exists():
                raise ValueError('Changed/incomplete cooked cache: ' + str(destination))
            entry['status'] = 'needs_cook'
        return entry
    # Hash independent player caches concurrently, with bounded file buffers.
    # Reading thousands of small files serially dominates reruns on Windows.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for number, entry in enumerate(pool.map(classify_cache, rows), 1):
            (records if entry['status'] == 'cooked_cached' else pending).append(entry)
            if number % 50 == 0 or number == len(rows):
                print(json.dumps(dict(cache_checked=number, total=len(rows))), flush=True)
    write(work / 'cook-report.json', records)
    if not pending:
        print(json.dumps(dict(cached=len(records), cooked=0)), flush=True)
        return records
    batch = work / 'cook-jobs' / key_of([p['cooked_cache_key'] for p in pending])[:16]
    project = batch / 'PesMobile'
    from realface_import_cache import importer_key
    contract_path=batch/'importer-contract.json'
    contract_key=importer_key(config)
    if contract_path.exists() and read(contract_path).get('importer_key')!=contract_key:
        raise ValueError('Importer provenance changed inside an existing build')
    write(contract_path,dict(importer_key=contract_key))
    if not project.exists():
        template = Path(config['ue_template'])
        (project / 'Content/Assets/character').mkdir(parents=True)
        shutil.copytree(template / 'Content/Assets/character/BaseAssets', project / 'Content/Assets/character/BaseAssets')
        shutil.copytree(template / 'Config', project / 'Config')
        shutil.copy2(template / 'PesMobile.uproject', project / 'PesMobile.uproject')
    profiles = []
    for row in pending:
        p = read(Path(row['folder']) / 'ue-profile.json')
        report = batch / 'profiles' / (str(row['base_id']) + '.report.json')
        p['report'] = str(report)
        profile = report.with_name(str(row['base_id']) + '.json')
        write(profile, p)
        row['ue_profile'] = str(profile)
        profiles.append(str(profile))
    from realface_import_cache import restore
    restored=restore(config,pending,project)
    if restored:print(json.dumps(dict(imports_restored=restored)),flush=True)
    profiles=[row['ue_profile'] for row in pending if not row.get('restored_import')]
    # Bound the editor lifetime: FBX import retains native allocations that
    # Python/UE GC alone cannot reliably release across hundreds of players.
    for start in range(0,len(profiles),8):
        import_chunk(config,project,batch,profiles[start:start+8],start//8)
    command([config['ue_editor'], project / 'PesMobile.uproject', '-run=cook', '-targetplatform=Android_ETC1',
             '-unversioned', '-cookall', '-unattended', '-nop4', '-nosplash', '-nullrhi'], batch / 'cook.log')
    for row in pending:
        profile = read(row['ue_profile'])
        report = read(profile['report'])
        row['status'] = 'cooked_pending_verification' if report['status'] == 'imported' else 'held_import'
        row['cooked_content'] = str(project / 'Saved/Cooked/Android_ETC1/PesMobile/Content')
        if row['status'] == 'held_import': row['reason'] = report.get('reason')
        records.append(row)
    write(work / 'cook-report.json', records)
    print(json.dumps(dict(imported=sum(p['status'] == 'cooked_pending_verification' for p in records), cached=len(records)-len(pending))), flush=True)
    return records


def import_chunk(config,project,batch,profiles,index):
    # A crash/missing completion marker stops the batch; failed individual
    # imports retain their explicit failure reports and never enter a PAK.
    batch=batch/('import-%03d'%index)
    batch.mkdir(exist_ok=True)
    script = batch / 'import_faces.py'
    marker = batch / 'import-complete.json'
    marker.unlink(missing_ok=True)
    script.write_text("import os, runpy, json, traceback, gc, unreal\nprofiles=" + repr(profiles) +
        "\nfor path in profiles:\n with open(path) as stream: p=json.load(stream)\n"
        " if os.path.exists(p['report']): continue\n"
        " os.environ['PESNX_REALFACE_IMPORT_PROFILE']=path\n"
        " try:\n  runpy.run_path(" + repr(str(HERE / 'ue_prepare_realface.py')) + ",run_name='__main__')\n"
        " except Exception as error:\n  traceback.print_exc()\n  with open(p['report'],'w') as stream: json.dump({'status':'failed','reason':str(error)},stream)\n"
        " gc.collect()\n unreal.SystemLibrary.collect_garbage()\n" +
        "with open(" + repr(str(marker)) + ",'w') as stream: json.dump({'profiles':len(profiles)},stream)\n",
        encoding='utf-8')
    # UE4.22 parses -script itself before Python sees it. A space in the script
    # path is interpreted as inline Python even when subprocess quotes argv.
    # Copy only this generated entry point into a space-free temporary path.
    with tempfile.NamedTemporaryFile(prefix='pesnx-faces-', suffix='.py', delete=False) as stream:
        temporary_script = Path(stream.name)
        stream.write(script.read_bytes())
    try:
        if ' ' in str(temporary_script):
            raise ValueError('UE4.22 needs a space-free temporary script directory (set TEMP)')
        try:
            command([config['ue_editor'], project / 'PesMobile.uproject', '-run=pythonscript', '-script=' + str(temporary_script),
                     '-unattended', '-nop4', '-nosplash', '-nullrhi'], batch / 'import.log')
        except subprocess.CalledProcessError as error:
            # UE counts logged per-player FBX errors even when Python catches
            # them. Never mistake a crash or truncated batch for this case.
            if error.returncode != 1 or not check_import_completion(profiles, marker):
                raise
        check_import_completion(profiles, marker)
    finally:
        temporary_script.unlink()
    print(json.dumps(dict(import_chunk=index+1,players=len(profiles))),flush=True)


def verify_one(config, row, validator=None):
    if row['status'] in ('cooked_cached', 'cooked_pending_verification'):
        if valid_cache(Path(row['cooked_folder']), row['cooked_cache_key']):
            return dict(row, status='validated_cached')
        if row['status'] == 'cooked_cached':
            return dict(row, status='held_cook_validation', reason='Cooked cache changed since cook report')
    if row['status'] != 'cooked_pending_verification': return row
    work = Path(config['work_dir']) / 'verification' / (str(row['base_id']) + '-' + row['cooked_cache_key'][:16])
    work.mkdir(parents=True, exist_ok=True)
    try:
        profile = read(row['ue_profile'])
        content = Path(row['cooked_content'])
        assets = content / 'Assets/character/RealFace'
        native = str(row['native_player_id'])
        parts = {}
        for part in ('face', 'hair'):
            # Blender's FBX importer may extract embedded images beside its
            # input. Audit a private copy so immutable prepared caches stay
            # untouched by validation.
            fbx = work / 'input' / (part + '.fbx')
            fbx.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(profile[part + '_fbx'], fbx)
            doc = work / (part + '.json')
            command([config['uassetgui'], 'tojson', assets / (native + '_' + part + '.uasset'), doc, 'VER_UE4_22'], work / (part + '-asset.log'))
            command([config['umodel'], '-export', '-gltf', '-png', '-game=ue4.22', '-path=' + str(content),
                     '-out=' + str(work / 'gltf'), native + '_' + part], work / (part + '-gltf.log'))
            source_map = {n.replace('_00', '.00'): 'skin' for n in
                          (profile['skin_materials'] if part == 'face' else profile['hair_skin_materials'])}
            cooked_map = {'face_' + native: 'skin'} if source_map else {}
            if part == 'face':
                source_map[profile['eye_material']] = 'eye'
                cooked_map['eye_native_' + native] = 'eye'
            else:
                source_map.update({n.replace('_00', '.00'): 'hair' for n in profile['hair_materials']})
                if profile['hair_materials']: cooked_map['hair_parts_tablet_ss'] = 'hair'
            parts[part] = dict(fbx=str(fbx), cooked_mesh_json=str(doc),
                               gltf=str(work / ('gltf/Assets/character/RealFace/' + native + '_' + part + '.gltf')),
                               material_map=source_map, cooked_material_map=cooked_map,
                               permit_exact_source_collapses=True)
        check = dict(base_id=row['base_id'], native_player_id=row['native_player_id'], native_rig=config['native_rig'],
                     cooked_rig=config['cooked_rig'], parts=parts, report=str(work / 'verified.json'))
        write(work / 'profile.json', check)
        if validator is None:
            command([config['blender'], '--background', '--threads', '2', '--python-exit-code', '1', '--python',
                     HERE / 'validate_realface_cooked.py', '--', '--profile', work / 'profile.json'], work / 'validate.log')
        else:
            validator(work / 'profile.json', work / 'validate.log')
        checked = read(work / 'verified.json')
        checked['validation_source_sha256'] = {
            name: sha(HERE / name) for name in
            ('validate_realface_cooked.py', 'audit_realface_rig.py', 'realface_cook_policy.py',
             'blender_fit_realface.py', 'realface_reference.py', 'blender_realface_validate_worker.py',
             'realface_triangle_audit.py', 'realface_vertex_audit.py')}
        destination = Path(row['cooked_folder'])
        destination.mkdir(parents=True)
        own = read(Path(row['folder']) / 'recipe.json')['eye'].get('own_native_face')
        names = [(native + '_face', ('.uasset', '.uexp')), (native + '_hair', ('.uasset', '.uexp')),
                 (native + '_face_tablet', ('.uasset', '.uexp', '.ubulk')),
                 (native + '_hair_parts_color_tablet', ('.uasset', '.uexp', '.ubulk')),
                 ('face_' + native, ('.uasset', '.uexp')), ('eye_native_' + native, ('.uasset', '.uexp'))]
        if not own: names += [(native + '_eyes_tablet', ('.uasset', '.uexp', '.ubulk'))]
        staged = destination / 'assets'
        staged.mkdir()
        for name, suffixes in names:
            for suffix in suffixes:
                shutil.copy2(assets / (name + suffix), staged / (name + suffix))
        if own:
            from build_low_pitch_phase_patch import rename_package
            source = Path(own).parents[4] / ('assets/' + PREFIX + native + '_face_tablet.uasset')
            changes = {native + '_face_tablet': native + '_eyes_tablet',
                       '/Game/Assets/character/RealFace/' + native + '_face_tablet': '/Game/Assets/character/RealFace/' + native + '_eyes_tablet'}
            rename_package(source, staged / (native + '_eyes_tablet.uasset'), changes, work / 'eye-rename', Path(config['uassetgui']))
        write(destination / 'verification.json', checked)
        write(destination / 'complete.json', dict(cache_key=row['cooked_cache_key'], outputs=output_hashes(destination), hardware_accepted=False))
        return dict(row, status='validated')
    except Exception as error:
        reason = str(error)
        log = work / 'validate.log'
        if log.exists():
            errors = [s for s in log.read_text(encoding='utf-8', errors='replace').splitlines() if
                      ('Error:' in s or 'Exception:' in s) and not s.startswith('Error: script failed')]
            if errors: reason = errors[-1]
        return dict(row, status='held_cook_validation', reason=reason)


def verify(config, workers=2):
    work = Path(config['work_dir'])
    records = []
    rows = read(work / 'cook-report.json')
    from realface_validation_process import ValidationProcess
    state, validators = threading.local(), []
    def task(row):
        if not hasattr(state, 'validator'):
            state.validator = ValidationProcess(config['blender'])
            validators.append(state.validator)
        return verify_one(config, row, state.validator)
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for future in as_completed([pool.submit(task, row) for row in rows]):
                record = future.result()
                records.append(record)
                write(work / 'verify-report.json', records)
                print(json.dumps(dict(completed=len(records), total=len(rows), base_id=record['base_id'], status=record['status'],
                                      reason=record.get('reason')), ensure_ascii=True), flush=True)
    finally:
        for validator in validators:
            validator.close()
    return records
