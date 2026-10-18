"""Isolate the normal map of atlas-based mobile heads without recooking meshes.

Consumes a verified realface_mobile release plus its identity verification.
All payloads stay local. The native parent is cloned with name-table-only
edits; its compiled shaders are preserved. A private neutral ETC1 normal
texture replaces the unrelated native facial atlas for these heads only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import uuid
import zipfile
import zlib

import numpy as np
from PIL import Image

from build_efootball10_visual_patch import etc1
from build_low_pitch_phase_patch import name_entries, rename_package
from cooked_texture import Texture
from realface_batch import command, key_of
from realface_batch_inventory import read, write
from realface_pipeline import identify, sha

HERE = Path(__file__).resolve().parent
BASE = 'PesMobile/Content/Assets/character/BaseAssets/'
FACE = 'PesMobile/Content/Assets/character/RealFace/'
GAME = '/Game/Assets/character/BaseAssets/'
PARENT, NEW_PARENT = 'M_RealFaceBase', 'M_NXFaceSmooth'
NORMAL, NEW_NORMAL = 'common_face_normal_tablet', 'pesnx0_face_normal_tablet'
CAP = 2000
# Pin the compatible, locally supplied PES21 Mobile material revision.
NATIVE_HASHES = {
    PARENT+'.uasset': 'c7c68db1173f6a89a6bd2ea5a8d575e4b8e1dc70311055b0aa805102b9feedfc',
    PARENT+'.uexp': 'c5e676782db7180949e6f80485bbb0d135ea5601176cf5756fd3315cfbb8ecbe',
    NORMAL+'.uasset': '70bf9e10c450d02298df9350ada0895becd6c84049164354026839a63458d9f4',
    NORMAL+'.uexp': 'a5d35b9ab17cdeeb2de0558efabb2dc9dcc494f13e169532b42671fa313e5553',
    NORMAL+'.ubulk': '9c6adccf426368ac3e05cb9f724bf0b00cccbd55f8ef8fc316528046ecd9645d',
}
CODE = ('realface_surface_patch.py', 'build_low_pitch_phase_patch.py',
        'build_efootball10_visual_patch.py', 'cooked_texture.py',
        'realface_batch.py', 'realface_batch_inventory.py', 'realface_pipeline.py')


def asset_names(native):
    return {FACE+str(native)+part+suffix for part, suffixes in (
        ('_face', ('.uasset', '.uexp')), ('_hair', ('.uasset', '.uexp')),
        ('_face_tablet', ('.uasset', '.uexp', '.ubulk')),
        ('_hair_parts_color_tablet', ('.uasset', '.uexp', '.ubulk')))
        for suffix in suffixes} | {FACE+'face_'+str(native)+suffix for suffix in ('.uasset', '.uexp')}


def validate_source(report, verified, state):
    players = report['players']
    if not players or len({p['base_id'] for p in players}) != len(players):
        raise ValueError('Missing or duplicate source BaseId')
    if len(verified) != len(players) or {p['base_id'] for p in verified} != {p['base_id'] for p in players}:
        raise ValueError('Source identity verification coverage differs')
    registry = dict(players=[dict(ef_base_id=p['base_id'], native_player_id=p['native_player_id'],
                                 fingerprint=p['fingerprint'], status=p['status'])
                             for p in state['identities'].values() if p.get('status') == 'active'])
    owners = {p['base_id']: p for p in verified}
    expected = set()
    for player in players:
        owner = owners[player['base_id']]
        identify(owner, registry)
        if (owner['status'] not in ('validated', 'validated_cached') or
                owner['native_player_id'] != player['native_player_id']):
            raise ValueError('Unverified source owner')
        total = player['face_triangles'] + player['hair_triangles']
        # Cached identity rows omit counts; the verified release always has
        # the cooked totals. Cross-check fresh row counts when supplied.
        if not (0 < total <= CAP and player['sections'] == 2 and
                total == player['triangles'] == owner.get('triangles', total)):
            raise ValueError('Source violates the 2000-triangle / two-section head budget')
        expected |= asset_names(player['native_player_id'])
    if not report.get('unpack_hashes_match') or set(report['asset_hashes']) != expected:
        raise ValueError('Source must contain only verified per-player assets')
    return owners


def hash_tree(folder):
    return {p.relative_to(folder).as_posix(): sha(p) for p in folder.rglob('*') if p.is_file()}


def patch_names(source, target, replacements, template):
    """Reuse GUI-validated FName bytes; never reserialize opaque exports."""
    original = source.read_bytes()
    templated = {name: template[start:end] for name, start, end in name_entries(template)}
    entries = name_entries(original)
    if any(sum(name == old for name, _, _ in entries) != 1 for old in replacements):
        raise ValueError('Expected unique source name entries')
    result = bytearray(original)
    changed = []
    for name, start, end in entries:
        if name not in replacements:
            continue
        new = replacements[name]
        data = templated.get(new)
        if data is None or len(data) != end-start or len(new) != len(name):
            raise ValueError('Only equal-length, validated name entries are allowed')
        result[start:end] = data
        changed.append(dict(old=name, new=new, start=start, end=end))
    if [n for n, _, _ in name_entries(result)] != [replacements.get(n, n) for n, _, _ in entries]:
        raise ValueError('Unexpected name-table edit')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result)
    for suffix in ('.uexp', '.ubulk'):
        path = source.with_suffix(suffix)
        if path.exists():
            shutil.copy2(path, target.with_suffix(suffix))
    return changed


def neutralize(texture_path, encoder, work):
    texture = Texture(texture_path)
    if texture.format != 'PF_ETC1':
        raise ValueError('Neutral normal replacement requires ETC1')
    block = etc1(Image.new('RGB', (4, 4), (128, 128, 255)), work/'neutral-block.etc1', encoder)
    if len(block) != 8:
        raise ValueError('Invalid encoded ETC1 block')
    changed = texture.replace([block * (m.size//8) for m in texture.mips])
    # Check the entire metadata/trailer outside mip payloads, not only sizes.
    for suffix, output in changed.items():
        before = bytearray(texture.files[suffix])
        for mip in texture.mips:
            if mip.file == suffix:
                before[mip.offset:mip.offset+mip.size] = output[mip.offset:mip.offset+mip.size]
        if bytes(before) != output:
            raise ValueError('Normal replacement changed bytes outside payloads')
        texture_path.with_suffix('.'+suffix).write_bytes(output)
    decoded = Texture(texture_path)
    measurements = []
    for i, mip in enumerate(decoded.mips):
        rgba = np.asarray(decoded.decode(i))
        xy = rgba[:, :, :2].astype(float)/255*2-1
        angle = np.degrees(np.arcsin(np.minimum(1, np.linalg.norm(xy, axis=2))))
        if np.max(angle) >= 1 or not np.all(rgba == rgba[0, 0]):
            raise ValueError('Normal is not spatially neutral in every mip')
        measurements.append(dict(width=mip.width, height=mip.height, bytes=mip.size,
                                 rgba=rgba[0, 0].tolist(), max_tilt_degrees=float(np.max(angle))))
    decoded.decode().save(work/'neutral-normal-preview.png')
    return dict(format=decoded.format, mips=measurements, metadata_preserved=True)


def audit_native_shader(path):
    shaders = set()
    data = path.read_bytes()
    for match in re.finditer(b'\x78[\x01\x5e\x9c\xda]', data):
        try:
            raw = zlib.decompress(data[match.start():])
        except zlib.error:
            continue
        if raw.startswith(b'LSLGSP') and b'#version' in raw:
            shaders.add(raw[raw.index(b'#version'):].split(b'\0', 1)[0])
    # Evidence gate for the audited high/medium GLES branch. Other variants
    # have different source layouts; this is not a count of all normal users.
    same_uv = sum(b'texture2D(ps1,var_TEXCOORD0).xy' in code and
                  b'texture2D(ps0,var_TEXCOORD0)' in code for code in shaders)
    if not same_uv:
        raise ValueError('Expected shared diffuse/normal UV shader evidence missing')
    return dict(sha256=sha(path), unique_gles_pixel_shaders=len(shaders),
                direct_same_uv_variants=same_uv, runtime_capture=False)


def validate_stage(stage, source, players):
    actual = hash_tree(stage)
    headers = {FACE+'face_'+str(p['native_player_id'])+'.uasset' for p in players}
    extra = {BASE+NEW_PARENT+s for s in ('.uasset', '.uexp')} | {
        BASE+NEW_NORMAL+s for s in ('.uasset', '.uexp', '.ubulk')}
    if set(actual) != set(source) | extra:
        raise ValueError('Unexpected asset, missing asset or global material override')
    unchanged = set(source) - headers
    if any(actual[name] != source[name] for name in unchanged):
        raise ValueError('Geometry, textures or material export bytes changed')
    for name in headers:
        names = {v for v, _, _ in name_entries((stage/name).read_bytes())}
        if (PARENT in names or GAME+PARENT in names or
                not {NEW_PARENT, GAME+NEW_PARENT} <= names or actual[name] == source[name]):
            raise ValueError('Face instance does not use the isolated parent')
    return actual, dict(per_player_files_identical=len(unchanged), relinked_instance_headers=len(headers),
                        mesh_files_byte_identical=4*len(players), texture_files_byte_identical=6*len(players),
                        instance_export_files_byte_identical=len(players),
                        global_native_assets_overridden=False)


def build(config):
    work = Path(config['work_dir']).resolve()
    if not any(work.is_relative_to(HERE.parent/d) and work != HERE.parent/d for d in ('local-debug', 'local-inputs')):
        raise ValueError('Output must be a dedicated ignored directory')
    label = config.get('release_label', 'v36')
    if not re.fullmatch(r'v[0-9]+', label):
        raise ValueError('Invalid release label')
    scope = config.get('package_scope', 'Barca-MU')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,63}', scope):
        raise ValueError('Invalid package scope')
    names = ('source_pak', 'source_verification', 'source_identity_report', 'identity_state', 'main_pak',
             'unrealpak', 'repak', 'uassetgui', 'etc1tool')
    inputs = {name: sha(config[name]) for name in names}
    report = read(config['source_verification'])
    owners = validate_source(report, read(config['source_identity_report']), read(config['identity_state']))
    if inputs['source_pak'] != report['pak_sha256'] or inputs['main_pak'] != config['main_pak_sha256']:
        raise ValueError('Pinned source PAK changed')
    outside_path = Path(config['source_verification']).parent/'OUTSIDE-CANDIDATE.json'
    outside = read(outside_path) if outside_path.is_file() else []
    inputs['outside_candidates'] = key_of(outside)
    recipe = dict(inputs=inputs, code={name: sha(HERE/name) for name in CODE}, label=label, scope=scope,
                  baseline_device_feedback=config.get('baseline_device_feedback'))
    key = key_of(recipe)
    job = work/'builds'/key[:16]
    if (work/'latest.json').exists():
        latest = read(work/'latest.json')
        previous = Path(latest['release']).resolve().parent
        if latest['key'] == key and previous.is_relative_to(work/'builds'):
            job = previous
    stamp = job/'complete.json'
    if stamp.exists():
        complete = read(stamp)
        if complete['key'] != key or hash_tree(job/'release') != complete['release_hashes']:
            raise ValueError('Cached release bytes changed')
        print(json.dumps(dict(status='verified_cached', release=str(job/'release'))), flush=True)
        return job/'release'
    # A partial attempt is retained for diagnosis. A retry uses a new folder.
    if job.exists():
        job = work/'builds'/(key[:16]+'-retry-'+uuid.uuid4().hex[:8])
    job.mkdir(parents=True)
    write(job/'recipe.json', recipe)
    original, native, stage = job/'source', job/'native', job/'stage'
    command([config['repak'], 'unpack', config['source_pak'], '-o', original], job/'source-unpack.log')
    if hash_tree(original) != report['asset_hashes']:
        raise ValueError('Source PAK unpack differs from verified assets')
    shutil.copytree(original, stage)
    native.mkdir()
    for name, digest in NATIVE_HASHES.items():
        result = subprocess.run([config['repak'], 'get', config['main_pak'], BASE+name],
                                check=True, capture_output=True)
        (native/name).write_bytes(result.stdout)
        if sha(native/name) != digest:
            raise ValueError('Unsupported native face material revision: '+name)
    shader = audit_native_shader(native/(PARENT+'.uexp'))
    replacements = {PARENT: NEW_PARENT, GAME+PARENT: GAME+NEW_PARENT,
                    NORMAL: NEW_NORMAL, GAME+NORMAL: GAME+NEW_NORMAL}
    target = stage/BASE/(NEW_PARENT+'.uasset')
    parent_proof = rename_package(native/(PARENT+'.uasset'), target, replacements,
                                  job/'rename-parent', Path(config['uassetgui']))
    template = target.read_bytes()
    patch_names(native/(NORMAL+'.uasset'), stage/BASE/(NEW_NORMAL+'.uasset'),
                {NORMAL: NEW_NORMAL, GAME+NORMAL: GAME+NEW_NORMAL}, template)
    normal = neutralize(stage/BASE/(NEW_NORMAL+'.uexp'), config['etc1tool'], job)
    relinks = {}
    for player in report['players']:
        name = FACE+'face_'+str(player['native_player_id'])+'.uasset'
        relinks[name] = patch_names(original/name, stage/name,
                                   {PARENT: NEW_PARENT, GAME+PARENT: GAME+NEW_PARENT}, template)
    if sha(stage/BASE/(NEW_PARENT+'.uexp')) != shader['sha256']:
        raise ValueError('Compiled material export/shaders changed')
    hashes, preservation = validate_stage(stage, report['asset_hashes'], report['players'])
    players = [dict(p, fingerprint=owners[p['base_id']]['fingerprint'],
                    status='surface_validated_pending_device', material=NEW_PARENT,
                    geometry_byte_identical=True) for p in report['players']]
    release = job/'release'
    pak = release/'update/PesMobile/Content/Paks'/('PesMobile-'+scope+'-Faces-Mobile-'+label+'-Android_ETC1_P.pak')
    pak.parent.mkdir(parents=True)
    response = job/'pak-response.txt'
    response.write_text('\n'.join('"'+str(stage/n)+'" "../../../'+n+'"' for n in sorted(hashes))+'\n', encoding='utf-8')
    command([config['unrealpak'], pak, '-Create='+str(response), '-compress'], job/'package.log')
    command([config['unrealpak'], pak, '-Test'], job/'package-test.log')
    command([config['repak'], 'unpack', pak, '-o', job/'roundtrip'], job/'roundtrip.log')
    if hash_tree(job/'roundtrip') != hashes:
        raise ValueError('Independent PAK unpack hashes differ')
    verification = dict(version='Mobile '+label+' isolated face surface', players=players,
                        asset_hashes=hashes, pak_sha256=sha(pak), pak_bytes=pak.stat().st_size,
                        source_pak_sha256=inputs['source_pak'], input_hashes=inputs,
                        budget=dict(max_head_triangles=CAP, max_sections=2),
                        preservation=preservation, parent=parent_proof, normal=normal, shader=shader,
                        relinked_headers=relinks, unpack_hashes_match=True, hardware_accepted=False,
                        baseline_device_feedback=config.get('baseline_device_feedback'), runtime_code_changed=False)
    write(release/'VERIFICATION.json', verification)
    write(release/'PLAYER-STATUS.json', players)
    write(release/'OUTSIDE-CANDIDATE.json', outside)
    for filename, rows, fields in (
        ('PLAYER-STATUS.csv', sorted(players, key=lambda p:p['name']),
         ['base_id', 'native_player_id', 'name', 'status', 'face_triangles', 'hair_triangles',
          'triangles', 'vertices', 'sections', 'geometry_byte_identical', 'material']),
        ('OUTSIDE-CANDIDATE.csv', outside, ['base_id', 'native_player_id', 'name', 'status', 'team_ids'])):
        with (release/filename).open('w', newline='', encoding='utf-8-sig') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
    (release/'INSTALL.txt').write_text(
        'FootballNX Mobile '+label+' - perbaikan permukaan wajah '+scope+'\n\n'
        f'{len(players)} kepala, maksimal 2.000 segitiga, dua material per kepala.\n'
        'Mesh, rambut, UV, bobot tulang, dan tekstur warna identik dengan paket sumber.\n'
        'Normal map wajah bawaan yang tidak cocok dengan atlas diganti map netral khusus.\n'
        'Cahaya dan bayangan tetap mengikuti normal mesh. Aset pemain bawaan tidak diubah.\n\n'
        'Pasang saat game ditutup:\n'
        '1. Pindahkan PAK real face v35, Lite v34, v24, Barcelona/Yamal/Raphinha lama ke luar Paks.\n'
        '   Simpan untuk rollback. Gunakan hanya PAK wajah kandidat ini.\n'
        '2. Salin ISI folder update ke SD:/switch/pes21_nx/.\n'
        '3. Tetap gunakan NRO dan CPK roster/fisik/warna kulit yang sudah dipakai.\n\n'
        'Daftar pemain dan jumlah segitiga ada di PLAYER-STATUS.csv.\n'
        f'{len(outside)} identitas masih di luar kandidat; lihat OUTSIDE-CANDIDATE.csv.\n'
        'Paket ini belum diuji di Switch. Uji tim yang dicantumkan, DAY/NIGHT, operan dekat kamera,\n'
        'lalu close-up pipi kiri, mata, rahang dan leher pada selebrasi/replay.\n'
        'Rollback: keluarkan PAK ini dan pulihkan PAK sumber. Tidak ada NRO/CPK/OBB baru.\n', encoding='utf-8')
    (release/'SHA256SUMS.txt').write_text(sha(pak)+'  '+pak.relative_to(release).as_posix()+'\n', encoding='utf-8')
    archive = release/('FootballNX-Mobile-'+label+'-'+scope+'.zip')
    members = sorted(p for p in release.rglob('*') if p.is_file())
    root = 'FootballNX-Mobile-'+label+'/'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in members:
            bundle.write(path, root+path.relative_to(release).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None or hashlib.sha256(bundle.read(root+pak.relative_to(release).as_posix())).hexdigest() != sha(pak):
            raise ValueError('Archive CRC or embedded PAK hash differs')
    write(release/'ARCHIVE.json', dict(file=archive.name, bytes=archive.stat().st_size, sha256=sha(archive)))
    write(job/'complete.json', dict(key=key, release_hashes=hash_tree(release)))
    write(work/'latest.json', dict(key=key, release=str(release)))
    print(json.dumps(dict(release=str(release), players=len(players), assets=len(hashes),
                          pak_bytes=pak.stat().st_size, sha256=sha(pak))), flush=True)
    return release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    build(read(args.config))


if __name__ == '__main__':
    main()
