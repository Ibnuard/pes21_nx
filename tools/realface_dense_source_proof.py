"""Admission of identity-bound dense inputs, before reduction or cooked proof.

This explicit policy never calls a dense conversion a cooked/accepted head.
It supplements the historical accepted-PAK path; it does not relax that path.
"""
from pathlib import Path

from realface_batch import key_of, valid_prepared_cache
from realface_batch_inventory import read
from realface_pipeline import sha

POLICY = 'identity-bound-dense-v1'


def identity_evidence(config, owner):
    evidence = owner.get('source_identity_evidence', {})
    base=owner['base_id'];source_id=owner.get('source_player',{}).get('player_id')
    if (evidence.get('policy')=='base_id_name_biography_v1' and
            evidence.get('base_id')==base and source_id==base and
            evidence.get('canonical_fingerprint')==owner['fingerprint'] and
            evidence.get('source_row_sha256')):
        return evidence
    # Explicit v71 supplement: a direct BaseId with full name/country/age/GK
    # agreement can carry disclosed height/foot data variance. A different
    # source ID still needs all the independent biography checks, not a slot.
    if not config.get('source_identity_supplement'):
        raise ValueError('Dense source requires BaseId and independent biography')
    from realface_source_identity import name_relation
    report=read(config['source_identity_supplement'])
    if report.get('inventory_sha256')!=sha(config['dense_inventory']):
        raise ValueError('Source biography supplement inventory differs')
    matches=[p for p in report['players'] if p['base_id']==base]
    current=[p for p in read(config['identity_state'])['identities'].values()
             if p.get('status')=='active' and p['base_id']==base]
    if len(matches)!=1 or len(current)!=1 or owner.get('identity_status')!='verified_name_country':
        raise ValueError('Source biography supplement owner is not unique')
    item,canonical=matches[0],current[0];bio=item['source']
    for key in ('base_id','native_player_id','fingerprint'):
        if item[key]!=owner[key] or canonical[key]!=owner[key]:
            raise ValueError('Source biography supplement identity differs')
    archives={(p['path'],p['player_table_sha256']) for p in report['archives']}
    if ((bio['archive'],bio['player_table_sha256']) not in archives or
            bio['source_player_id']!=source_id or
            bio['name']!=owner['source_player']['name'] or
            name_relation(canonical['name'],bio['name'])!='full_name' or
            canonical['country']!=bio['country'] or
            (canonical['position']==0)!=(bio['position']==0) or
            abs(canonical['age']-bio['age'])>3 or abs(canonical['height']-bio['height'])>15):
        raise ValueError('Source full identity/biography differs')
    same_foot=canonical['foot']==bio['foot'];height_delta=bio['height']-canonical['height']
    if source_id!=base and (not same_foot or abs(height_delta)>3):
        raise ValueError('Source alias requires concordant independent biography')
    return dict(policy='own_source_full_identity_v71',base_id=base,source_player_id=source_id,
        canonical_fingerprint=owner['fingerprint'],source_row_sha256=bio['row_sha256'],
        source_player_table_sha256=bio['player_table_sha256'],source_archive=bio['archive'],
        full_name_country_age_goalkeeper_agree=True,height_delta_cm=height_delta,same_foot=same_foot,
        direct_base_id=source_id==base,supplement_sha256=sha(config['source_identity_supplement']))


def validate(config, row, accepted, inventory=None, inventory_sha256=None):
    if config.get('source_preparation_policy') != POLICY:
        raise ValueError('Explicit dense source policy required')
    binding = accepted.get('dense_source', {})
    path = Path(config['dense_inventory'])
    if binding.get('inventory_sha256') != (sha(path) if inventory_sha256 is None else inventory_sha256):
        raise ValueError('Dense source inventory changed')
    inventory = read(path) if inventory is None else inventory
    matches = [p for p in inventory['players'] if p.get('base_id') == row['base_id']]
    if len(matches) != 1:
        raise ValueError('Dense source owner is not unique')
    owner = matches[0]
    identity = ('base_id', 'native_player_id', 'fingerprint')
    if any(owner.get(k) != row.get(k) or accepted.get(k) != row.get(k) for k in identity):
        raise ValueError('Dense source identity differs')
    if owner.get('status') != 'source_ready':
        raise ValueError('Dense source requires BaseId and independent biography')
    identity_evidence(config,owner)
    if binding.get('inventory_row_key') != key_of(owner):
        raise ValueError('Dense source row binding differs')
    folder = Path(binding['folder'])
    if not valid_prepared_cache(folder, binding['cache_key']):
        raise ValueError('Dense preparation cache changed')
    profile = folder / 'ue-profile.json'
    if (profile.resolve() != Path(row['profile']).resolve() or
            row.get('input_hashes', {}).get(str(profile)) != sha(profile)):
        raise ValueError('Dense profile binding differs')
    profile_data = read(profile)
    if any(profile_data.get(k) != row[k] for k in identity):
        raise ValueError('Dense profile identity differs')
    required = {str(profile)} | {profile_data[k] for k in
        ('face_fbx', 'hair_fbx', 'face_texture', 'hair_texture', 'native_eye_texture')}
    if not required <= row['input_hashes'].keys():
        raise ValueError('Dense geometry/texture hashes missing')
    for name, digest in row['input_hashes'].items():
        if sha(name) != digest:
            raise ValueError('Dense source payload changed: ' + name)
    return True
