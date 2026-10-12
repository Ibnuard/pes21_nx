"""Package identity-verified cooked faces, preserving earlier verified payloads.

Only per-player RealFace assets may enter the local PAK. Shared cook dependencies
are excluded. The PAK is independently unpacked and every payload hashed before
a ZIP is produced. Proprietary inputs and output packages remain ignored.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import zipfile
import re

from realface_batch import PREFIX, command, key_of, output_hashes, valid_cache, verify_inputs
from realface_batch_inventory import read, write
from realface_pipeline import sha


def allowed_assets(native, legacy=False):
    native = str(int(native))
    if int(native) <= 0:
        raise ValueError('Invalid native player slot')
    textures = [native + suffix for suffix in
                ('_face_tablet', '_hair_parts_color_tablet', '_eyes_tablet')]
    materials = ['face_' + native, 'eye_native_' + native]
    if legacy:
        textures += [native + '_eye_tablet']
        materials += ['eye_' + native]
    return ({name + suffix for name in textures for suffix in ('.uasset', '.uexp', '.ubulk')} |
            {name + suffix for name in [native + '_face', native + '_hair', *materials]
             for suffix in ('.uasset', '.uexp')})


def check_asset_path(name, owners, legacy=False):
    path = PurePosixPath(name)
    if str(path.parent) + '/' != PREFIX or path.name not in {
            name for native in owners for name in allowed_assets(native, legacy)}:
        raise ValueError('Unowned/shared asset in package: ' + name)


def preserved_marker(name):
    # Earlier Yamal/Raphinha pilots used PES21NX; the Barcelona batch used
    # PESNX. These verified root labels are omitted from the combined PAK.
    return ('/' not in name and '\\' not in name and name.endswith('.txt') and
            name.startswith(('PESNX_', 'PES21NX_')))


def release_rows(inv, prepared, verified):
    pre = {r['base_id']: r for r in prepared}
    cooked = {r['base_id']: r for r in verified}
    if len(pre) != len(prepared) or len(cooked) != len(verified):
        raise ValueError('Duplicate player report')
    rows = []
    for owner in inv['players']:
        base = owner['base_id']
        row = {key: owner.get(key) for key in
               ('base_id', 'native_player_id', 'name', 'fingerprint', 'team_ids')}
        result = cooked.get(base, pre.get(base, owner))
        if result.get('native_player_id') != owner['native_player_id']:
            raise ValueError('Cooked ownership differs from inventory')
        status = result['status']
        row['status'] = ('candidate_pending_device' if status in ('validated', 'validated_cached')
                         else 'preserved_verified' if status == 'preserve_existing'
                         else 'held_not_cooked' if status in ('prepared', 'prepared_cached') else status)
        if status in ('validated', 'validated_cached'):
            row['batch_origin'] = 'reused_verified' if result.get('reused_from') else 'new_conversion'
        if owner.get('source_identity_evidence'):
            row['source_identity_evidence'] = owner['source_identity_evidence']
        if result.get('reason'):
            row['reason'] = result['reason'].split(': {')[0][:220]
        rows.append(row)
    return rows


def recovery_summary(current, previous):
    """Track failed conversions separately from unavailable source assets."""
    now={r['base_id']:r for r in current}
    players=[]
    for old in previous:
        if old['status'] not in ('held_conversion','held_import','held_cook_validation','held_not_cooked'):
            continue
        row=now.get(old['base_id'])
        if row is None:
            continue
        if any(row[k]!=old[k] for k in ('native_player_id','fingerprint')):
            raise ValueError('Recovery comparison changed player identity')
        players.append(dict(row,previous_status=old['status'],previous_reason=old.get('reason',''),
                            recovered=row['status']=='candidate_pending_device'))
    recovered=sum(r['recovered'] for r in players)
    return dict(targeted=len(players),recovered=recovered,pending=len(players)-recovered,players=players)


def package(config):
    work = Path(config['work_dir'])
    version = config.get('release_version', 'v22')
    if not re.fullmatch(r'v[0-9]+', version):
        raise ValueError('Release version must be v followed by digits')
    inv = read(work / 'inventory.local.json')
    verify_inputs(config, inv)
    prepared = read(work / 'prepare-report.json')
    verified = read(work / 'verify-report.json')
    if ({r['base_id'] for r in prepared} !=
            {r['base_id'] for r in inv['players'] if r['status'] == 'source_ready'} or
            len(prepared) != inv['counts'].get('source_ready', 0)):
        raise ValueError('The complete selected source batch must finish before packaging')
    ready = [r for r in verified if r['status'] in ('validated', 'validated_cached')]
    expected = {r['base_id'] for r in prepared if r['status'] in ('prepared', 'prepared_cached')}
    if {r['base_id'] for r in verified} != expected:
        raise ValueError('Every prepared face needs a cook/verification result')
    if not ready:
        raise ValueError('No independently validated cooked faces')
    proof = read(config['preserved_verification']) if config.get('preserved_verification') else None
    prior_sha = sha(config['preserved_pak']) if proof else None
    if proof and prior_sha != proof['pak_sha256']:
        raise ValueError('Preserved PAK changed')
    rows = release_rows(inv, prepared, verified)
    recovery=None
    if config.get('reuse_verified_batch'):
        previous=Path(config['reuse_verified_batch'])
        previous_rows=release_rows(read(previous/'inventory.local.json'),read(previous/'prepare-report.json'),
                                   read(previous/'verify-report.json'))
        recovery=dict(recovery_summary(rows,previous_rows),baseline=previous.name)
    key = key_of(dict(version=version, inventory=sha(work / 'inventory.local.json'),
                      players=rows,recovery=recovery,
                      cooked=sorted((r['base_id'], r['cooked_cache_key']) for r in ready),
                      preserved=prior_sha, code=[sha(__file__), sha(Path(__file__).with_name('realface_batch_status.py'))],
                      tools={k: sha(config[k]) for k in ('unrealpak', 'repak')}))
    release = work / 'release' / key[:16]
    if valid_cache(release, key):
        return read(release / 'VERIFICATION.json')
    if release.exists():
        raise ValueError('Incomplete or changed release; preserve it for investigation: ' + str(release))
    job = work / 'package-jobs' / key[:16]
    staging = job / 'staging'
    if job.exists():
        raise ValueError('Incomplete package job: ' + str(job))
    staging.mkdir(parents=True)
    owners = {r['base_id']: r for r in inv['players']}
    hashes = {}

    def add(path, name):
        if name in hashes:
            raise ValueError('Duplicate package asset: ' + name)
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        hashes[name] = sha(target)

    for row in ready:
        folder = Path(row['cooked_folder'])
        owner = owners[row['base_id']]
        if not valid_cache(folder, row['cooked_cache_key']):
            raise ValueError('Cooked face cache changed: ' + str(row['base_id']))
        check = read(folder / 'verification.json')
        profile = read(Path(row['folder']) / 'ue-profile.json')
        if any(check[k] != owner[k] or profile[k] != owner[k]
               for k in ('base_id', 'native_player_id')) or profile['fingerprint'] != owner['fingerprint']:
            raise ValueError('Cooked face belongs to another identity')
        files = list((folder / 'assets').iterdir())
        if {p.name for p in files} != allowed_assets(owner['native_player_id']):
            raise ValueError('Incomplete per-player asset allowlist')
        for path in files:
            add(path, PREFIX + path.name)
    preserved = [r for r in inv['players'] if r['status'] == 'preserve_existing']
    if preserved:
        old = job / 'preserved'
        command([config['repak'], 'unpack', config['preserved_pak'], '-o', old, '-q'], job / 'preserved.log')
        actual = {p.relative_to(old).as_posix(): sha(p) for p in old.rglob('*') if p.is_file()}
        if actual != proof['asset_hashes']:
            raise ValueError('Preserved payload hashes differ from verified source')
        slots = {r['native_player_id'] for r in preserved}
        for name in actual:
            if name.startswith(PREFIX):
                check_asset_path(name, slots, legacy=True)
                add(old / name, name)
            elif not preserved_marker(name):
                raise ValueError('Unexpected preserved package entry')
    response = job / 'pak-response.txt'
    response.write_text('\n'.join('"' + (staging / n).as_posix() + '" "../../../' + n + '"'
                                  for n in sorted(hashes)) + '\n', encoding='utf-8')
    pak = release / ('update/PesMobile/Content/Paks/PesMobile-League-Faces-' + version + '-Android_ETC1_P.pak')
    pak.parent.mkdir(parents=True)
    command([config['unrealpak'], pak, '-Create=' + str(response), '-compress'], job / 'create.log')
    command([config['unrealpak'], pak, '-Test'], job / 'test.log')
    if 'healthy, ' + str(len(hashes)) + ' files checked' not in (job / 'test.log').read_text(errors='replace'):
        raise ValueError('UnrealPak did not confirm all entries')
    unpacked = job / 'roundtrip'
    command([config['repak'], 'unpack', pak, '-o', unpacked, '-q'], job / 'roundtrip.log')
    actual = {p.relative_to(unpacked).as_posix(): sha(p) for p in unpacked.rglob('*') if p.is_file()}
    if actual != hashes:
        raise ValueError('PAK round-trip payload checksum mismatch')
    team_counts = {str(t['team_id']): dict(Counter(r['status'] for r in rows if t['team_id'] in r['team_ids']))
                   for t in inv['teams']}
    report = dict(version='League realface ' + version, runtime_build=inv['build_id'], teams=inv['teams'],
                  players=rows, counts=dict(Counter(r['status'] for r in rows)), team_counts=team_counts,
                  new_faces=len(ready), preserved_faces=len(preserved), pak_entries=len(hashes),
                  pak_sha256=sha(pak), pak_bytes=pak.stat().st_size, asset_hashes=hashes,
                  unpack_hashes_match=True, shared_runtime_assets_packaged=False, hardware_accepted=False,
                  material_policy='Native own diffuse/alpha; explicit own-secondary UV1 fallback when primary is absent; PC hair blend/shading excluded',
                  body_palette_changed=False)
    report['reused_faces'] = sum(bool(r.get('reused_from')) for r in ready)
    report['additional_faces'] = len(ready) - report['reused_faces']
    if recovery is not None:
        report['recovery']=recovery
    write(release / 'VERIFICATION.json', report)
    from realface_batch_status import exports
    exports(report, release)
    write(release / 'CHECKSUMS.json', {pak.relative_to(release).as_posix(): dict(sha256=sha(pak), bytes=pak.stat().st_size)})
    (release / 'INSTALL-ID.txt').write_text(
        f'REALFACE LIGA INGGRIS + SPANYOL {version} - KANDIDAT UJI SWITCH\n\n'
        f"Roster build {inv['build_id']}: {len(inv['teams'])} tim, {len(rows)} pemain diaudit.\n"
        f"{len(ready) + len(preserved)} wajah tersedia: {report['additional_faces']} tambahan baru, "
        f"{report['reused_faces']} hasil batch sebelumnya, {len(preserved)} wajah Barcelona.\n"
        'Status tiap pemain/tim ada di VERIFICATION.json. Pemain tertunda memakai face bawaan/fallback.\n\n'
        'PASANG\n1. Tutup game sepenuhnya dan backup PAK wajah lama di luar folder Paks.\n'
        '2. Keluarkan PAK Barcelona-Faces, LamineYamal, Raphinha, dan seluruh League-Faces lama\n'
        '   dari Paks. Wajah Barcelona sudah digabung byte-for-byte dalam paket ini.\n'
        '3. Salin isi update ke folder pes21_nx pada SD. PAK utama/stadium/weather tetap digunakan.\n'
        '4. Gunakan runtime dengan roster build di atas (checkpoint v20/v21 yang sama).\n'
        '   Paket ini tidak mengganti NRO, database fisik, SaveData, atau FootballNX.assets.\n\n'
        'UJI\nPeriksa close-up kedua mata, rambut, kerah dan warna wajah/tubuh; lakukan\n'
        'beberapa pertandingan dan rematch. Audit cook bukan bukti animasi/FPS di Switch.\n'
        'Palet tubuh belum diubah untuk wajah tambahan. Iris template netral dipakai\n'
        'bila mata native milik pemain tidak tersedia; warna iris bukan data faktual.\n\n'
        f'ROLLBACK\nTutup game, keluarkan hanya PAK League-Faces {version}, lalu kembalikan PAK wajah lama.\n', encoding='utf-8')
    archive = release / ('FootballNX-League-Realfaces-' + version + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        package_files=[pak, release/'VERIFICATION.json',release/'CHECKSUMS.json',release/'INSTALL-ID.txt',
                       release/'PLAYER-STATUS.txt',release/'PLAYER-STATUS.html']
        if recovery is not None:
            package_files += [release/'RECOVERY-STATUS.json',release/'RECOVERY-STATUS.txt']
        for path in package_files:
            zipped.write(path, path.relative_to(release).as_posix())
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() or zipped.read(pak.relative_to(release).as_posix()) != pak.read_bytes():
            raise ValueError('ZIP integrity or embedded PAK checksum failed')
    (release / 'ZIP-SHA256.txt').write_text(sha(archive) + '  ' + archive.name + '\n')
    write(release / 'complete.json', dict(cache_key=key, outputs=output_hashes(release)))
    write(work / 'package-report.json', dict(release=str(release), archive=str(archive), sha256=sha(archive),
                                           new_faces=len(ready), preserved_faces=len(preserved),
                                           additional_faces=report['additional_faces'], reused_faces=report['reused_faces'],
                                           counts=report['counts']))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    config = read(args.config)
    work = Path(config['work_dir']).resolve()
    root = Path(__file__).resolve().parents[1]
    if not work.is_relative_to(root / 'local-debug') or work == root / 'local-debug':
        raise ValueError('Package work must be a dedicated ignored local-debug directory')
    result = package(config)
    print({k: result[k] for k in ('new_faces', 'preserved_faces', 'pak_entries', 'pak_bytes', 'pak_sha256')})
