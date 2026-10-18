"""Package reviewed recovery heads without replacing any baseline head.

The prior TEST package is carried byte-for-byte with its original approval
state. New heads need current identity, geometry, visual-screen and cooked
evidence. This command never installs a PAK or grants device approval.
"""
import argparse
from collections import Counter
import hashlib
from pathlib import Path
import shutil
import zipfile

from realface_batch import command, key_of, valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_joined_recovery import CODE, HERE
from realface_league_progress import owner_matches
from realface_mobile import cooked_counts, PROFILE_POLICY
from realface_native_hair_candidate import coverage_tables
from realface_native_hair_screen_gate import require_screened
from realface_pipeline import sha
from realface_surface_patch import BASE, FACE, GAME, PARENT, NEW_PARENT, asset_names, hash_tree, patch_names


def select_new(rows, baseline, owners):
    existing = {r['base_id'] for r in baseline['players_in_package']}
    storage = {r['native_player_id'] for r in baseline['players_in_package']}
    selected = []; identities = set()
    for row in rows:
        if row.get('composite_geometry_pass') is not True:
            raise ValueError('Recovery has no passing geometry evidence')
        base = row['base_id']
        if base in existing or row['native_player_id'] in storage:
            raise ValueError('Recovery cannot replace a baseline head or storage slot')
        if base in identities:
            raise ValueError('Duplicate recovery identity')
        identities.add(base); storage.add(row['native_player_id'])
        if not owner_matches(row, owners.get(base, {})):
            raise ValueError('Recovery identity does not match the canonical fingerprint')
        if row['status'] not in ('validated', 'validated_cached'):
            raise ValueError('Recovery has not passed independent cooked validation')
        selected.append(row)
    return selected


def package(config, verified_path, reviews, baseline_path, baseline_pak, status_path, work):
    work = Path(work).resolve()
    if not work.is_relative_to(HERE.parent / 'local-debug') or work == HERE.parent / 'local-debug':
        raise ValueError('Candidate output must be a dedicated ignored directory')
    baseline = read(baseline_path)
    if sha(baseline_pak) != baseline['pak_sha256']:
        raise ValueError('Baseline PAK changed')
    state = read(config['identity_state'])
    owners = {r['base_id']: r for r in state['identities'].values() if r.get('status') == 'active'}
    rows = select_new(read(verified_path), baseline, owners)
    if not rows:
        raise ValueError('No new validated recovery heads')
    code = {name: sha(HERE / name) for name in CODE}
    for row in rows:
        if row.get('recipe_source_sha256') != code:
            raise ValueError('Recovery recipe changed before packaging')
        if not valid_prepared_cache(Path(row['folder']), row['cache_key']):
            raise ValueError('Recovered prepared bytes changed')
        if not valid_cache(Path(row['cooked_folder']), row['cooked_cache_key']):
            raise ValueError('Recovered cooked bytes changed')
    screened = require_screened(rows, reviews)
    status = read(status_path)
    roster = {r['base_id']: r for r in status['players']}
    if len(roster) != len(status['players']):
        raise ValueError('Coverage has duplicate canonical identities')
    if set(roster) != {r['base_id'] for r in baseline['players']}:
        raise ValueError('Recovery coverage must retain the complete baseline roster scope')
    for row in baseline['players_in_package'] + rows:
        if not owner_matches(row, roster.get(row['base_id'], {})) or not owner_matches(row, owners.get(row['base_id'], {})):
            raise ValueError('Package ownership differs from roster scope')
    for row in rows:
        if any(r.get('cache_key') == row['cache_key']
               for r in roster[row['base_id']].get('visual_rejections', [])):
            raise ValueError('Known visual rejection is still selected')
    key = key_of(dict(baseline=sha(baseline_path), pak=baseline['pak_sha256'], verified=sha(verified_path),
                      screened=screened, status=sha(status_path), code=code, package_tool=sha(__file__)))
    job = work / 'test-packages' / key[:16]; release = job / 'release'
    pak_name = 'PesMobile-League-Faces-NativeHair-v40-TEST-Android_ETC1_P.pak'
    archive_name = 'FootballNX-NativeHair-v40-TEST-Leagues.zip'
    pak = release / 'update/PesMobile/Content/Paks' / pak_name
    def publish():
        write(work / 'latest-test.json', dict(release=str(release), pak=str(pak),
              archive=str(release / archive_name), test_only=True))
    stamp = job / 'complete.json'
    if stamp.exists():
        if read(stamp) != dict(key=key, release_hashes=hash_tree(release)):
            raise ValueError('Published incremental package changed')
        publish(); return release
    stage = job / 'stage'
    if not stage.exists():
        command([config['repak'], 'unpack', baseline_pak, '-o', stage], job / 'baseline-unpack.log')
    hashes = dict(baseline['asset_hashes'])
    actual = hash_tree(stage)
    if any(actual.get(name) != digest for name, digest in hashes.items()):
        raise ValueError('Baseline assets differ in staging')
    allowed = set(hashes) | {name for row in rows for name in asset_names(row['native_player_id'])}
    if set(actual) - allowed:
        raise ValueError('Unexpected staged asset')
    template = (stage / BASE / (NEW_PARENT + '.uasset')).read_bytes()
    players = list(baseline['players_in_package']); relinked = {}
    for row in rows:
        folder = Path(row['folder']); cache = Path(row['cooked_folder'])
        profile = read(folder / 'ue-profile.json')
        if any(profile.get(k) != v for k, v in PROFILE_POLICY.items()):
            raise ValueError('Recovered head violates the mobile material policy')
        names = asset_names(row['native_player_id'])
        if {p.name for p in (cache / 'assets').iterdir()} != {Path(n).name for n in names}:
            raise ValueError('Unexpected shared asset in recovery cook')
        counts = cooked_counts(read(cache / 'verification.json'))
        for name in names:
            if name in baseline['asset_hashes']:
                raise ValueError('Recovery attempted to overwrite a baseline asset')
            target = stage / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cache / 'assets' / Path(name).name, target)
        name = FACE + 'face_' + str(row['native_player_id']) + '.uasset'
        relinked[name] = patch_names(cache / 'assets' / Path(name).name, stage / name,
            {PARENT: NEW_PARENT, GAME + PARENT: GAME + NEW_PARENT}, template)
        hashes.update({n: sha(stage / n) for n in names})
        players.append(dict({k: row[k] for k in ('base_id', 'native_player_id', 'fingerprint', 'name')},
                            **counts, inherited_v37=False, visual_approved=False, hardware_profiled=False,
                            recovery_mode=row['recovery_mode']))
        roster[row['base_id']].update(status='recovered_cooked_visual_hold', triangles=counts['triangles'],
            reason='Recovered and front-screened; cooked gates passed. Full appearance and Switch FPS review pending.')
    if hash_tree(stage) != hashes:
        raise ValueError('Staged package asset inventory differs')
    pak.parent.mkdir(parents=True, exist_ok=True)
    response = job / 'pak-response.txt'
    response.write_text('\n'.join('"' + str(stage / n) + '" "../../../' + n + '"' for n in sorted(hashes)) + '\n')
    command([config['unrealpak'], pak, '-Create=' + str(response), '-compress'], job / 'package.log')
    command([config['unrealpak'], pak, '-Test'], job / 'package-test.log')
    roundtrip = job / 'roundtrip'
    command([config['repak'], 'unpack', pak, '-o', roundtrip], job / 'roundtrip.log')
    if hash_tree(roundtrip) != hashes:
        raise ValueError('Independent PAK unpack differs')
    status.update(counts=dict(Counter(r['status'] for r in status['players'])),
        packaged_heads=len(players), recovered_heads=len(rows), players_in_package=players,
        native_heads=len(players)-baseline['inherited_heads_byte_identical'],
        baseline_heads_byte_identical=len(baseline['players_in_package']), baseline_pak_sha256=baseline['pak_sha256'],
        inherited_heads_byte_identical=baseline['inherited_heads_byte_identical'],
        pak_sha256=sha(pak), asset_hashes=hashes, relinked_headers=relinked,
        baseline_approval_states_preserved=True, neutral_material_byte_identical_to_v37=True,
        unpack_hashes_match=True, runtime_code_changed=False, release_approved=False,
        hardware_accepted=False, test_candidate=True, front_screened_new_heads=len(rows))
    write(release / 'VERIFICATION.json', status)
    write(release / 'FRONT-SCREEN-VERIFICATION.json', screened)
    write(release / 'QUALITY-HOLD.json', dict(approved=False, reason='TEST: full appearance and Switch review pending'))
    included = {r['base_id'] for r in players}
    coverage_tables(release, status, included)
    coverage = release / 'COVERAGE.txt'
    coverage.write_text(coverage.read_text(encoding='utf-8').replace('KANDIDAT UJI v39', 'KANDIDAT UJI v40'), encoding='utf-8')
    (release / 'INSTALL.txt').write_text(
        'FootballNX Native Hair v40 TEST\n\n'
        f'{len(players)} kepala: {len(baseline["players_in_package"])} v39 identik + {len(rows)} pemulihan.\n'
        'Maksimal 2.000 segitiga per kepala, dua section/material.\n'
        'Paket uji; belum ada pengukuran FPS Switch atau persetujuan visual menyeluruh.\n'
        'Tutup game. Simpan PAK wajah lama di luar Paks untuk rollback.\n'
        'Gunakan hanya satu PAK wajah. Salin folder update ke SD:/switch/pes21_nx/.\n'
        'Tidak memerlukan NRO, CPK atau OBB baru.\n'
        'PLAYER-STATUS.csv dan TEAM-COVERAGE.csv mencatat semua pemain termasuk yang belum masuk.\n'
        'Uji Barca/MU, tim lain, close-up, animasi kepala/leher, DAY/NIGHT, dan bola dekat kamera.\n', encoding='utf-8')
    (release / 'SHA256SUMS.txt').write_text(sha(pak) + '  ' + pak.relative_to(release).as_posix() + '\n')
    archive = release / archive_name; temporary = archive.with_suffix('.zip.tmp')
    excluded = {archive, temporary, release / 'ARCHIVE.json'}
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(release.rglob('*')):
            if path.is_file() and path not in excluded:
                bundle.write(path, 'FootballNX-NativeHair-v40-TEST/' + path.relative_to(release).as_posix())
    with zipfile.ZipFile(temporary) as bundle:
        if (bundle.testzip() or hashlib.sha256(bundle.read('FootballNX-NativeHair-v40-TEST/' +
                pak.relative_to(release).as_posix())).hexdigest() != sha(pak)):
            raise ValueError('ZIP CRC or embedded PAK hash differs')
    temporary.replace(archive)
    write(release / 'ARCHIVE.json', dict(file=archive.name, bytes=archive.stat().st_size, sha256=sha(archive)))
    write(stamp, dict(key=key, release_hashes=hash_tree(release)))
    publish()
    print(dict(packaged=len(players), recovered=len(rows), test_only=True, release=str(release)), flush=True)
    return release


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--verified', required=True)
    p.add_argument('--reviews', required=True, help='JSON list of report/screen_dir specifications')
    p.add_argument('--baseline', required=True)
    p.add_argument('--baseline-pak', required=True); p.add_argument('--status', required=True)
    p.add_argument('--work-dir', required=True)
    a = p.parse_args()
    package(read(a.config), a.verified, read(a.reviews), a.baseline, a.baseline_pak, a.status, a.work_dir)
