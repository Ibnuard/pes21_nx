"""Resume individually completed UE imports without trusting partial projects."""
from pathlib import Path
import shutil

from realface_batch import HERE, key_of
from realface_batch_inventory import read, write
from realface_pipeline import sha


def importer_key(config):
    files=[HERE/'ue_prepare_realface.py',Path(config['ue_editor'])]
    template=Path(config['ue_template'])
    for sub in ('Content/Assets/character/BaseAssets','Config'):
        files.extend(p for p in sorted((template/sub).rglob('*')) if p.is_file())
    return key_of({str(p):sha(p) for p in files})


def profile_key(profile):
    return key_of({k:v for k,v in profile.items() if k!='report'})


def allowed_names(native):
    return {str(native)+suffix+'.uasset' for suffix in
            ('_face','_hair','_face_tablet','_hair_parts_color_tablet','_eyes_tablet')}|{
            'face_'+str(native)+'.uasset','eye_native_'+str(native)+'.uasset'}


def capture(config,rows,batch,manifest):
    batch=Path(batch);assets=batch/'PesMobile/Content/Assets/character/RealFace';result=[]
    contract=batch/'importer-contract.json'
    if not contract.is_file() or read(contract).get('importer_key')!=importer_key(config):
        raise ValueError('Cannot checkpoint imports without their matching compiler provenance')
    for row in rows:
        path=batch/'profiles'/(str(row['base_id'])+'.report.json')
        if not path.is_file():continue
        report=read(path);native=row['native_player_id']
        if report.get('status')!='imported' or report.get('player')!=native:continue
        profile=read(batch/'profiles'/(str(row['base_id'])+'.json'))
        if profile_key(profile)!=profile_key(read(Path(row['folder'])/'ue-profile.json')):
            raise ValueError('Imported profile no longer matches the prepared identity')
        hashes={name:sha(assets/name) for name in sorted(allowed_names(native))}
        result.append(dict(base_id=row['base_id'],native_player_id=native,
            prepared_key=row['cache_key'],profile_key=profile_key(profile),assets=hashes,report=report))
    write(manifest,dict(importer_key=read(contract)['importer_key'],assets_root=str(assets),players=result))
    return len(result)


def restore(config,rows,project):
    path=config.get('reuse_imported_manifest')
    if not path:return 0
    manifest=read(path)
    if manifest['importer_key']!=importer_key(config):
        raise ValueError('Import compiler or shared dependencies changed since checkpoint')
    old={r['base_id']:r for r in manifest['players']};count=0
    source=Path(manifest['assets_root']);destination=project/'Content/Assets/character/RealFace'
    destination.mkdir(parents=True,exist_ok=True)
    for row in rows:
        previous=old.get(row['base_id']);native=row['native_player_id']
        if not previous or previous['prepared_key']!=row['cache_key']:continue
        profile=read(row['ue_profile'])
        if (previous['native_player_id']!=native or previous['profile_key']!=profile_key(profile) or
                set(previous['assets'])!=allowed_names(native) or
                previous['report'].get('player')!=native or previous['report'].get('status')!='imported'):
            raise ValueError('Imported checkpoint identity or asset allowlist differs')
        # Validate every byte before copying any member of this player.
        for name,digest in previous['assets'].items():
            if sha(source/name)!=digest:raise ValueError('Imported checkpoint asset changed: '+name)
            if (destination/name).exists() and sha(destination/name)!=digest:
                raise ValueError('Import resume would replace a different asset: '+name)
        for name in previous['assets']:
            if not (destination/name).exists():shutil.copy2(source/name,destination/name)
        write(Path(profile['report']),previous['report'])
        row['restored_import']=True;count+=1
    return count
