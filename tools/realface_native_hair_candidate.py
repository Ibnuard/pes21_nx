"""Package a clearly labelled league TEST candidate after independent checks.

This does not approve or install a release. Unresolved sources and held heads
remain on the base runtime. The 51 accepted v37 heads and neutral material are
copied byte-for-byte. Only current native trials passing cook checks are added.
"""
import argparse
from collections import Counter
import csv
import hashlib
from pathlib import Path
import shutil
import zipfile

from realface_batch import command, key_of, valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_league_mobile import inherited
from realface_league_progress import indexed, owner_matches
from realface_mobile import PROFILE_POLICY, cooked_counts
from realface_native_hair_leagues import coverage
import realface_native_hair_screen_gate as screen_gate
from realface_native_hair_validate import candidates
from realface_pipeline import sha
from realface_surface_patch import BASE, FACE, GAME, PARENT, NEW_PARENT, NEW_NORMAL, asset_names, hash_tree, patch_names


def select_verified(trials, verified):
    latest = indexed(trials, 'native candidates'); selected = []
    for row in verified:
        candidate = latest.get(row['base_id'], {})
        if (candidate.get('cache_key') != row.get('cache_key') or
                candidate.get('status') != 'prepared'):
            raise ValueError('Cooked native head no longer matches the selected trial')
        if row['status'] in ('validated', 'validated_cached'):
            selected.append(row)
    if len({r['base_id'] for r in selected}) != len(selected):
        raise ValueError('Duplicate cooked native identity')
    if {r['base_id'] for r in verified} != set(latest):
        raise ValueError('Every geometry-passing native head requires an independent cook result')
    return sorted(selected, key=lambda r: r['base_id'])


def archive_release(release, archive, pak):
    """An interrupted retry must never include the old ZIP inside itself."""
    temporary = archive.with_suffix('.zip.tmp')
    excluded = {archive, temporary, release / 'ARCHIVE.json'}
    members = [p for p in release.rglob('*') if p.is_file() and p not in excluded]
    prefix = 'FootballNX-NativeHair-v39-TEST/'
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for member in members: bundle.write(member, prefix + member.relative_to(release).as_posix())
    with zipfile.ZipFile(temporary) as bundle:
        if (bundle.testzip() or hashlib.sha256(bundle.read(prefix + pak.relative_to(release).as_posix())).hexdigest()
                != sha(pak)):
            raise ValueError('Test archive CRC or PAK hash differs')
    temporary.replace(archive)


def status_reason(row):
    """Explain every coverage hold without replacing a specific diagnostic."""
    if row.get('reason'):
        return row['reason']
    return {
        'held_composite_geometry': 'Opaque scalp and detail cards did not pass the required multi-view hair coverage gate.',
        'source_unresolved': 'No identity-verified face source is available in the pinned source inventory.',
        'held_geometry': 'Source face preparation did not pass the required head geometry constraints.',
        'native_cooked_visual_hold': 'Cook checks passed; full visual, animation and Switch performance review remain pending.',
        'accepted_v37_retained': 'Previously accepted v37 head retained byte-for-byte.',
    }.get(row['status'], 'No detailed diagnostic recorded; consult the preparation report.')


def publish_latest(work, release):
    write(work / 'latest-test.json', dict(release=str(release),
        pak=str(release / 'update/PesMobile/Content/Paks/PesMobile-League-Faces-NativeHair-v39-TEST-Android_ETC1_P.pak'),
        archive=str(release / 'FootballNX-NativeHair-v39-TEST-Leagues.zip'), test_only=True))


def coverage_tables(release, report, included):
    """Keep roster scope separate from the heads actually present in the PAK."""
    teams = {r['team_id']: r for r in report['teams']}
    fields = ('base_id', 'native_player_id', 'name', 'team_ids', 'teams', 'leagues',
              'status', 'triangles', 'included', 'reason')
    with (release / 'PLAYER-STATUS.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for row in report['players']:
            memberships = [teams[t] for t in row.get('team_ids') or []]
            item = dict(row, included=row['base_id'] in included,
                        team_ids=';'.join(map(str, row.get('team_ids') or [])),
                        teams=';'.join(t['name'] for t in memberships),
                        leagues=';'.join(sorted({t['category'] for t in memberships})))
            writer.writerow({key: item.get(key) for key in fields})
    team_fields = ('team_id', 'team', 'league', 'roster_players', 'included', 'native_test',
                   'accepted_v37', 'not_included', 'status_counts')
    with (release / 'TEAM-COVERAGE.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=team_fields); writer.writeheader()
        for team in report['teams']:
            members = [r for r in report['players'] if team['team_id'] in (r.get('team_ids') or [])]
            packaged = [r for r in members if r['base_id'] in included]
            retained = sum(r['status'] == 'accepted_v37_retained' for r in packaged)
            counts = Counter(r['status'] for r in members)
            writer.writerow(dict(team_id=team['team_id'], team=team['name'], league=team['category'],
                roster_players=len(members), included=len(packaged), native_test=len(packaged)-retained,
                accepted_v37=retained, not_included=len(members)-len(packaged),
                status_counts='; '.join(f'{status}={count}' for status, count in sorted(counts.items()))))
    counts = Counter(r['status'] for r in report['players'])
    retained = sum(r['status'] == 'accepted_v37_retained' and r['base_id'] in included for r in report['players'])
    lines = ['CAKUPAN KANDIDAT UJI v39', '',
             f'Target katalog: {len(report["players"])} identitas pemain, {len(teams)} tim.',
             f'Masuk PAK: {len(included)} kepala ({retained} v37 dipertahankan identik, '
             f'{len(included)-retained} metode baru).',
             f'Belum masuk PAK: {len(report["players"])-len(included)} identitas.', '',
             'Metode baru masih kandidat uji; belum ada persetujuan visual menyeluruh atau pengukuran FPS Switch.',
             'PLAYER-STATUS.csv: daftar lengkap pemain, tim/liga, status, alasan, dan kolom included.',
             'TEAM-COVERAGE.csv: jumlah yang benar-benar masuk PAK per tim.',
             'Satu identitas dapat memiliki beberapa keanggotaan tim; total pemain dihitung unik.', '',
             'RINCIAN STATUS']
    lines += [f'{status}: {count}' for status, count in sorted(counts.items())]
    lines += ['', 'accepted_v37_retained = kepala lama diterima dan dipertahankan.',
              'native_cooked_visual_hold = lolos pemeriksaan cook, masih perlu review visual/perangkat.',
              'held_* = ditahan; alasan ada di CSV. source_unresolved = belum ada sumber identitas yang valid.',
              'Pemain yang tidak masuk PAK menggunakan aset runtime dasar.', '']
    (release / 'COVERAGE.txt').write_text('\n'.join(lines), encoding='utf-8')


def package(config, work):
    work = Path(work).resolve()
    from realface_native_hair_trial import HERE
    if not work.is_relative_to(HERE.parent / 'local-debug') or work == HERE.parent / 'local-debug':
        raise ValueError('Candidate must use a dedicated ignored league work directory')
    snapshot = read(work / 'coverage.json')
    if snapshot['counts'].get('native_pending', 0):
        raise ValueError('Finish the full league conversion queue before packaging')
    native = candidates(config, [work])
    rows = select_verified(native, read(work / 'verify-report.json'))
    rejected_path = work / 'VISUAL-REJECT.json'
    rejected = indexed(read(rejected_path), 'visual rejects') if rejected_path.exists() else {}
    for base, reject in rejected.items():
        current = next((r for r in native if r['base_id'] == base), {})
        if current.get('cache_key') != reject.get('cache_key') or not reject.get('reason'):
            raise ValueError('Visual rejection must pin the exact current candidate and reason')
    rows = [r for r in rows if r['base_id'] not in rejected]
    if not rows: raise ValueError('No independently validated native hair candidates')
    screened = (screen_gate.require_screened(rows, config['screen_reviews'])
                if 'screen_reviews' in config else None)
    owners = indexed(read(config['source_profiles']), 'sources')
    carried = inherited(config, owners)
    if set(carried) & {r['base_id'] for r in rows}:
        raise ValueError('Native candidate cannot replace an accepted inherited head')
    all_rows = list(carried.values()) + rows
    if len({r['native_player_id'] for r in all_rows}) != len(all_rows):
        raise ValueError('Conflicting native storage identities')
    baseline = read(config['inherit_verification'])
    recipe = dict(verified=sha(work / 'verify-report.json'), trials=sha(work / 'trial-report.json'),
                  coverage=sha(work / 'coverage.json'), visual_rejects=rejected,
                  inherited=baseline['pak_sha256'], tool=sha(__file__))
    if screened is not None:
        recipe.update(front_screen=screened, screen_gate_tool=sha(screen_gate.__file__))
    key = key_of(recipe); job = work / 'test-packages' / key[:16]; release = job / 'release'
    stamp = job / 'complete.json'
    if stamp.exists():
        if read(stamp).get('key') != key or hash_tree(release) != read(stamp)['release_hashes']:
            raise ValueError('Cached test package bytes changed')
        publish_latest(work, release)
        return release
    original = job / 'inherited'
    if not original.exists():
        command([config['repak'], 'unpack', config['inherit_pak'], '-o', original], job / 'inherit-unpack.log')
    if hash_tree(original) != baseline['asset_hashes']:
        raise ValueError('Accepted inherited package bytes differ')
    stage = job / 'stage'
    private = {BASE + NEW_PARENT + suffix for suffix in ('.uasset', '.uexp')} | {
        BASE + NEW_NORMAL + suffix for suffix in ('.uasset', '.uexp', '.ubulk')}
    for name in private:
        target = stage / name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original / name, target)
    template = (stage / BASE / (NEW_PARENT + '.uasset')).read_bytes()
    players = []; hashes = {name: sha(stage / name) for name in private}; relinked = {}
    for row in all_rows:
        base = row['base_id']; native_id = row['native_player_id']
        if not owner_matches(row, owners.get(base, {})):
            raise ValueError('Candidate source identity differs')
        folder = Path(row['folder']); cache = Path(row['cooked_folder'])
        if not valid_cache(cache, row['cooked_cache_key']) or not valid_prepared_cache(folder, row['cache_key']):
            raise ValueError('Prepared/cooked bytes changed before packaging')
        proof = read(cache / 'verification.json'); counts = cooked_counts(proof)
        names = asset_names(native_id)
        if base in carried:
            for name in names:
                target = stage / name; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original / name, target)
        else:
            profile = read(folder / 'ue-profile.json')
            if any(profile.get(k) != v for k, v in PROFILE_POLICY.items()):
                raise ValueError('Candidate material policy differs')
            if {p.name for p in (cache / 'assets').iterdir()} != {Path(n).name for n in names}:
                raise ValueError('Unexpected shared/extra asset in native head')
            for name in names:
                target = stage / name; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cache / 'assets' / Path(name).name, target)
            name = FACE + 'face_' + str(native_id) + '.uasset'
            relinked[name] = patch_names(cache / 'assets' / Path(name).name, stage / name,
                {PARENT: NEW_PARENT, GAME + PARENT: GAME + NEW_PARENT}, template)
        players.append(dict({k: row[k] for k in ('base_id', 'native_player_id', 'fingerprint', 'name')},
                            **counts, inherited_v37=base in carried, visual_approved=base in carried,
                            hardware_profiled=base in carried))
        hashes.update({name: sha(stage / name) for name in names})
    if hash_tree(stage) != hashes: raise ValueError('Unexpected candidate package asset')
    pak = release / 'update/PesMobile/Content/Paks/PesMobile-League-Faces-NativeHair-v39-TEST-Android_ETC1_P.pak'
    pak.parent.mkdir(parents=True, exist_ok=True)
    response = job / 'pak-response.txt'
    response.write_text('\n'.join('"' + str(stage / n) + '" "../../../' + n + '"' for n in sorted(hashes)) + '\n', encoding='utf-8')
    command([config['unrealpak'], pak, '-Create=' + str(response), '-compress'], job / 'package.log')
    command([config['unrealpak'], pak, '-Test'], job / 'package-test.log')
    command([config['repak'], 'unpack', pak, '-o', job / 'roundtrip'], job / 'roundtrip.log')
    if hash_tree(job / 'roundtrip') != hashes: raise ValueError('Independent candidate PAK unpack differs')
    report = coverage(snapshot, indexed(read(Path(config['work_dir']) / 'prepare-report.json'), 'canonical'),
                      indexed(read(work / 'trial-report.json'), 'trials'), read(work / 'verify-report.json'))
    included = {r['base_id'] for r in players}
    for player in report['players']:
        if player['base_id'] in rejected:
            player.update(status='held_visual', reason=rejected[player['base_id']]['reason'])
        player['reason'] = status_reason(player)
    report['counts'] = dict(Counter(r['status'] for r in report['players']))
    for team in report['teams']:
        team['native_counts'] = dict(Counter(r['status'] for r in report['players']
                                            if team['team_id'] in (r.get('team_ids') or [])))
    report.update(test_candidate=True, packaged_heads=len(players), inherited_heads_byte_identical=len(carried),
                  native_heads=len(rows), pak_sha256=sha(pak), asset_hashes=hashes, players_in_package=players,
                  release_approved=False, hardware_accepted=False, runtime_code_changed=False,
                  neutral_material_byte_identical_to_v37=True, relinked_headers=relinked, unpack_hashes_match=True)
    report['front_screened_new_heads'] = screened['selected_heads'] if screened is not None else 0
    if screened is not None:
        write(release / 'FRONT-SCREEN-VERIFICATION.json', screened)
    write(release / 'VERIFICATION.json', report)
    write(release / 'QUALITY-HOLD.json', dict(approved=False, reason='TEST ONLY: full appearance and Switch review pending'))
    coverage_tables(release, report, included)
    write(release / 'TEAM-STATUS.json', report['teams'])
    (release / 'INSTALL.txt').write_text(
        'FootballNX v39 Native Hair - KANDIDAT UJI Liga Inggris/Spanyol\n\n'
        f'{len(rows)} kepala metode baru + {len(carried)} kepala v37 yang dipertahankan identik.\n'
        'Maksimal 2.000 segitiga per kepala lengkap, dua section/material.\n'
        'Belum disetujui visual menyeluruh dan belum diuji FPS di Switch.\n'
        'PLAYER-STATUS.csv mencatat SEMUA identitas roster dan siapa yang masuk paket.\n'
        'Pemain gagal pemeriksaan / belum ada sumber menggunakan aset runtime dasar.\n\n'
        'Saat game ditutup, pindahkan semua PAK wajah lama ke luar folder Paks untuk rollback.\n'
        'Gunakan hanya satu PAK wajah. Salin isi update ke SD:/switch/pes21_nx/.\n'
        'Tidak perlu NRO, OBB, atau CPK baru. Uji Barca/MU dan tim lain pada DAY/NIGHT,\n'
        'operan dekat kamera serta close-up mata, rambut, wajah dan leher.\n'
        'Rollback: keluarkan PAK uji ini dan pulihkan PAK wajah sebelumnya.\n', encoding='utf-8')
    digest = sha(pak)
    (release / 'SHA256SUMS.txt').write_text(digest + '  ' + pak.relative_to(release).as_posix() + '\n')
    archive = release / 'FootballNX-NativeHair-v39-TEST-Leagues.zip'
    archive_release(release, archive, pak)
    write(release / 'ARCHIVE.json', dict(file=archive.name, bytes=archive.stat().st_size, sha256=sha(archive)))
    write(stamp, dict(key=key, release_hashes=hash_tree(release)))
    publish_latest(work, release)
    print(dict(test_candidate=str(release), heads=len(players), inherited=len(carried), approved=False), flush=True)
    return release


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--work-dir', required=True)
    a = p.parse_args(); package(read(a.config), a.work_dir)
