"""Package verified league heads with the byte-identical delivered v54 runtime.

Requires completed preparation/cook results and explicit offline visual review.
No source donor substitution, geometry fallback, runtime installation or NRO
rebuild is performed here. Proprietary outputs must remain ignored on D.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import shutil
import zipfile

from realface_batch import command, key_of, valid_cache, valid_prepared_cache
from realface_batch_inventory import read, write
from realface_budget_package import counts
from realface_league_balanced import (POLICY, READY, VERIFIED, assert_owner,
                                      local_output, scope_for, unique, validate_head)
from realface_lite import sources
from realface_pipeline import sha
from realface_surface_patch import (BASE, FACE, GAME, PARENT, NEW_PARENT,
                                   NEW_NORMAL, asset_names, hash_tree, patch_names)
from audit_realface_runtime_assets import dependency_names, texture_evidence
from cooked_texture import Texture
from realface_hair_mips import protect_texture

BUDGET_PRIORITY = 'budget-priority-v1'


def release_policy(config, work, prepared, verified):
    """An explicit current user decision can make appearance notes advisory."""
    policy = config.get('release_policy', 'strict-visual-v1')
    if policy == 'strict-visual-v1':
        return dict(policy=policy, preserve_cooked_outside_tiny_guard=False)
    if policy != BUDGET_PRIORITY:
        raise ValueError('Unknown league release policy')
    path = Path(config['release_decision']).resolve()
    if not path.is_relative_to(Path(work).resolve()):
        raise ValueError('Release decision must be local to this cohort')
    decision = read(path)
    if (decision.get('policy') != BUDGET_PRIORITY or
            not decision.get('user_directive', '').strip() or
            decision.get('prepare_sha256') != sha(Path(work)/'prepare-report.json') or
            decision.get('verify_sha256') != sha(Path(work)/'verify-report.json') or
            set(decision.get('included_base_ids', [])) != {r['base_id'] for r in verified} or
            decision.get('normal_complete_head_limit') != 5000 or
            decision.get('exceptional_complete_head_limit') != 7000 or
            decision.get('appearance_notes_advisory') is not True or
            decision.get('preserve_original_cooked_mips_outside_tiny_guard') is not True):
        raise ValueError('Explicit current budget-priority release decision required')
    if {r['base_id'] for r in prepared} != set(decision['included_base_ids']):
        raise ValueError('Budget release decision differs from prepared cohort')
    return dict(policy=policy, decision=str(path), decision_sha256=sha(path),
                preserve_cooked_outside_tiny_guard=True)


def release_hair_mips(path, policy):
    """Keep the strict default; budget release preserves out-of-policy mips.

    This never forces medium-mip alpha or calls a failed guard a successful
    repair. Such existing cooked chains are copied unchanged and reported.
    """
    preserve = policy['preserve_cooked_outside_tiny_guard']
    before = {suffix: path.with_suffix(suffix).read_bytes()
              for suffix in ('.uasset', '.uexp', '.ubulk')
              if path.with_suffix(suffix).exists()} if preserve else {}
    try:
        return protect_texture(path)
    except ValueError as error:
        if not preserve or str(error) != 'Discarded hair mip exceeds the bounded tiny-mip policy':
            raise
        if any(path.with_suffix(suffix).read_bytes() != raw for suffix, raw in before.items()):
            raise ValueError('Failed mip protection changed cooked bytes') from error
        texture = Texture(path)
        return dict(source_has_visible_hair=max(texture.payload(0)[3::4]) >= 85,
                    changed_mips=[], policy='original_cooked_chain_preserved',
                    warning=str(error), alpha_forced=False,
                    original_cooked_payloads_byte_identical=True)


def validate_completion(scope, prepared, verified, review):
    if scope.get('policy') != POLICY:
        raise ValueError('Explicit league policy required')
    selected = set(scope['selected_base_ids'])
    owners = unique(prepared, 'preparations')
    if owners.keys() != selected:
        raise ValueError('Every selected league source must finish preparation')
    expected = {b for b, r in owners.items() if r['status'] in READY}
    proofs = unique(verified, 'verification')
    if proofs.keys() != expected:
        raise ValueError('Every prepared head needs an independent cook result')
    for base, result in proofs.items():
        assert_owner(result, owners[base])
        if result['cache_key'] != owners[base]['cache_key']:
            raise ValueError('Cook result changed its preparation recipe')
    ready = {b for b, r in proofs.items() if r['status'] in VERIFIED}
    if (review.get('decision') != 'offline_candidate_reviewed' or
            set(review.get('reviewed_base_ids', [])) != ready or
            not set(review.get('held_base_ids', [])) <= ready or
            any(not review.get('held_reasons', {}).get(str(base)) for base in review.get('held_base_ids', []))):
        raise ValueError('Complete offline preview review required')
    return [proofs[b] for b in sorted(ready - set(review.get('held_base_ids', [])))]


def copy_v54(config, destination):
    root = Path(config['v54_candidate']).resolve()
    for name, proof in config['v54_pinned_files'].items():
        source = root / name
        target = destination / name
        if (not source.resolve().is_relative_to(root) or
                not target.resolve().is_relative_to(destination.resolve()) or
                sha(source) != proof['sha256'] or source.stat().st_size != proof['bytes']):
            raise ValueError('Delivered v54 payload changed')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if sha(target) != proof['sha256']:
            raise ValueError('v54 payload copy changed')


def validate_preview_evidence(work, proofs, review):
    """Bind inspected images to the exact meshes and cooked textures released."""
    work = Path(work).resolve(); players = unique(proofs, 'preview proofs')
    seen = {base: set() for base in players}
    for row in review.get('images', []):
        base = row['base_id']; path = Path(row['path']).resolve()
        if base not in players or not path.is_relative_to(work) or not path.is_file():
            raise ValueError('Preview image is outside this cohort/output')
        metadata = read(path.with_suffix('.json')); proof = players[base]
        if (sha(path) != row['sha256'] or metadata.get('image_sha256') != row['sha256'] or
                metadata.get('prepared_key') != proof['cache_key'] or
                metadata.get('cooked_key') != proof['cooked_cache_key'] or
                metadata.get('view') not in ('front', 'left', 'right', 'above')):
            raise ValueError('Preview does not match current prepared/cooked keys')
        seen[base].add(metadata['view'])
    for base, proof in players.items():
        required = {'front'}
        if (proof.get('league_exception') or proof.get('facial_hair_policy', {}).get('locked') or
                proof.get('budgets', {}).get('hair_face_lock')):
            required.update(('left', 'right', 'above'))
        if not required <= seen[base]:
            raise ValueError('Required current preview views missing: ' + str(base))


def package(config):
    work = local_output(config['work_dir'])
    if config.get('policy') != POLICY:
        raise ValueError('Explicit league policy required')
    for path, expected in config['pinned_inputs'].items():
        if sha(path) != expected:
            raise ValueError('Pinned league input changed')
    scope = read(work / 'league-scope.json')
    if scope != scope_for(config, unique(sources(config), 'package sources')):
        raise ValueError('Final package must cover the complete pinned league scope')
    prepared = read(work / 'prepare-report.json'); verified = read(work / 'verify-report.json')
    policy = release_policy(config, work, prepared, verified)
    review = read(work / 'VISUAL-REVIEW.json')
    if (review.get('prepare_sha256') != sha(work / 'prepare-report.json') or
            review.get('verify_sha256') != sha(work / 'verify-report.json')):
        raise ValueError('Visual review refers to a different prepared/cooked cohort')
    ready = validate_completion(scope, prepared, verified, review)
    if policy['policy'] != BUDGET_PRIORITY:
        validate_preview_evidence(work, [r for r in verified if r['status'] in VERIFIED], review)
    if not ready:
        raise ValueError('No approved offline candidates')
    baseline = read(Path(config['accepted_release']) / 'VERIFICATION.json')
    original_heads = {p['base_id']: p for p in baseline['players_in_package']}
    originals = set(original_heads)
    if not originals <= {r['base_id'] for r in ready}:
        raise ValueError('Accepted Barca/MU coverage must remain complete')
    recipe = dict(policy=POLICY, prepare_sha256=sha(work / 'prepare-report.json'),
                  verify_sha256=sha(work / 'verify-report.json'), review_sha256=sha(work / 'VISUAL-REVIEW.json'),
                  package_code_sha256=sha(__file__), v54=config['v54_pinned_files'],
                  materials=baseline['neutral_material_hashes'])
    recipe['release_policy'] = policy
    key = key_of(recipe); job = work / 'release-builds' / key[:16]
    complete = job / 'complete.json'
    if complete.exists():
        proof = read(complete)
        if proof['key'] != key or hash_tree(Path(proof['directory'])) != proof['file_hashes'] or sha(proof['zip']) != proof['zip_sha256']:
            raise ValueError('Existing release changed')
        return proof
    if job.exists():
        raise ValueError('Preserve incomplete release for inspection: ' + str(job))
    job.mkdir(parents=True); write(job / 'recipe.json', recipe)
    stage = job / 'stage'; stage_source = Path(config['accepted_stage'])
    private = {BASE+NEW_PARENT+s for s in ('.uasset', '.uexp')} | {
        BASE+NEW_NORMAL+s for s in ('.uasset', '.uexp', '.ubulk')}
    for name in private:
        if sha(stage_source/name) != baseline['neutral_material_hashes'][name]:
            raise ValueError('Private neutral material changed')
        target = stage/name; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stage_source/name, target)
    template = (stage/BASE/(NEW_PARENT+'.uasset')).read_bytes()
    owners = unique(scope['owners'], 'scope owners'); players = []
    for row in ready:
        assert_owner(row, owners[row['base_id']])
        folder, cooked = Path(row['folder']), Path(row['cooked_folder'])
        if not valid_cache(cooked, row['cooked_cache_key']):
            raise ValueError('Cooked cache changed')
        if not row.get('reuse_cooked') and not valid_prepared_cache(folder, row['cache_key']):
            raise ValueError('Prepared cache changed')
        total = validate_head(row)
        actual = counts(read(cooked/'verification.json'), row['budgets']['head_cap'])
        if total != actual['triangles'] or total > 7000:
            raise ValueError('Cooked complete head budget differs')
        native = row['native_player_id']; names = asset_names(native)
        if {p.name for p in (cooked/'assets').iterdir()} != {Path(n).name for n in names}:
            raise ValueError('Unexpected per-player assets')
        for name in names:
            target = stage/name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cooked/'assets'/Path(name).name, target)
        patch_names(cooked/'assets'/f'face_{native}.uasset', stage/FACE/f'face_{native}.uasset',
                    {PARENT: NEW_PARENT, GAME+PARENT: GAME+NEW_PARENT}, template)
        if dependency_names(stage, native):
            raise ValueError('Native import/material dependency differs')
        mip = release_hair_mips(stage/FACE/f'{native}_hair_parts_color_tablet.uexp', policy)
        textures = {part: texture_evidence(Texture(stage/FACE/(str(native)+suffix+'.uexp')))
                    for part, suffix in (('face','_face_tablet'), ('hair','_hair_parts_color_tablet'))}
        if not textures['face']['every_mip_opaque'] or (
                not policy['preserve_cooked_outside_tiny_guard'] and
                mip['source_has_visible_hair'] and textures['hair']['fully_discarded_mips']):
            raise ValueError('Opaque face/visible hair mip contract failed')
        if row['base_id'] in originals:
            if any(sha(stage/name) != baseline['asset_hashes'].get(name) for name in names):
                raise ValueError('Accepted Barca/MU asset bytes changed')
        players.append(dict(**{k: row[k] for k in ('base_id', 'native_player_id', 'fingerprint', 'name')},
                            **actual, team_ids=owners[row['base_id']]['team_ids'],
                            league_exception=row.get('league_exception'),
                            accepted_cohort_unchanged=row['base_id'] in originals,
                            textures=textures, hair_mip_repair=mip))
        if len(players) % 50 == 0 or len(players) == len(ready):
            print(dict(stage='staging_verified_heads', completed=len(players), total=len(ready)), flush=True)
    hashes = hash_tree(stage)
    if set(hashes) != private | {n for r in ready for n in asset_names(r['native_player_id'])}:
        raise ValueError('Unexpected final payload allowlist')
    destination = job/'FootballNX-v54-LEAGUE-FACES-v55-SIAP-COPY'
    copy_v54(config, destination)
    pak = destination/'switch/pes21_nx/PesMobile/Content/Paks/PesMobile-League-Faces-Balanced-v55-Android_ETC1_P.pak'
    pak.parent.mkdir(parents=True, exist_ok=True)
    response = job/'response.txt'
    response.write_text('\n'.join('"'+str(stage/n)+'" "../../../'+n+'"' for n in sorted(hashes))+'\n', encoding='utf-8')
    print(dict(stage='creating_pak', heads=len(players)), flush=True)
    command([config['unrealpak'], pak, '-Create='+str(response), '-compress'], job/'package.log')
    print(dict(stage='pak_test_and_independent_unpack'), flush=True)
    command([config['unrealpak'], pak, '-Test'], job/'pak-test.log')
    roundtrip = job/'roundtrip'
    command([config['repak'], 'unpack', pak, '-o', roundtrip], job/'roundtrip.log')
    if hash_tree(roundtrip) != hashes:
        raise ValueError('Independent PAK extraction hashes differ')
    evidence = {r['base_id']: r for r in prepared+verified}; included = {p['base_id'] for p in players}
    status = []
    for base, owner in sorted(owners.items()):
        row = evidence.get(base, owner)
        reason = '' if base in included else row.get('reason', row.get('status', 'offline visual hold'))
        if base in review.get('held_base_ids', []):
            reason = 'Offline visual hold: ' + review['held_reasons'][str(base)]
        status.append(dict(base_id=base, native_player_id=owner['native_player_id'], name=owner['name'],
                           team_ids=owner['team_ids'], status='candidate_pending_device' if base in included else 'native_fallback',
                           reason=reason))
    exceptions = [dict(base_id=p['base_id'], name=p['name'], triangles=p['triangles'],
                       reason=p['league_exception']['reason']) for p in players if p['triangles'] > 5000]
    proof = dict(policy=POLICY, players_in_package=players, players=status,
                 roster_count=len(status), teams=scope['teams'], category_team_counts=scope['category_team_counts'],
                 target_head_triangles=5000, exceptional_head_limit_inclusive=7000, exceptions=exceptions,
                 actual_max_triangles=max(p['triangles'] for p in players), asset_hashes=hashes,
                 pak_sha256=sha(pak), pak_bytes=pak.stat().st_size, pak_roundtrip_hashes_match=True,
                 v54_unchanged_files=config['v54_pinned_files'], accepted_barca_mu_unchanged=True,
                 full_pc_referee_ai=False, hardware_accepted=False, runtime_installed=False)
    proof['release_policy'] = policy
    proof['appearance_notes_advisory'] = policy['policy'] == BUDGET_PRIORITY
    proof['fresh_preview_hash_validation'] = policy['policy'] != BUDGET_PRIORITY
    proof['preserved_cooked_mip_warning_base_ids'] = [p['base_id'] for p in players
        if p['hair_mip_repair'].get('policy') == 'original_cooked_chain_preserved']
    write(destination/'VERIFICATION.json', proof)
    for filename, rows, fields in (
        ('PLAYER-STATUS.csv', status, ('base_id','native_player_id','name','team_ids','status','reason')),
        ('PLAYER-BUDGET.csv', players, ('base_id','native_player_id','name','triangles','face_triangles','hair_triangles','vertices','sections'))):
        with (destination/filename).open('w', newline='', encoding='utf-8-sig') as stream:
            writer=csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(rows)
    (destination/'BACA-DULU.txt').write_text(
        f'FootballNX NRO v54 + real face liga Inggris/Spanyol v55\n'
        f'{len(players)} kandidat dari {len(status)} pemain di {len(scope["teams"])} tim katalog aktif.\n'
        f'Target 5000 segitiga; {len(exceptions)} pengecualian, maksimum aktual {proof["actual_max_triangles"]}; maksimal 7000.\n'
        'Tutup game. Cadangkan NRO dan PAK wajah lama di luar folder Paks.\n'
        'Pindahkan SEMUA PAK wajah tambahan lama keluar folder Paks agar tidak bertabrakan.\n'
        'Salin seluruh folder switch ke ROOT SD, gabungkan dan timpa.\n'
        'Pertahankan PAK game utama, stadion/weather, OBB, LooseCpk, intro dan save yang sudah ada.\n'
        'NRO, animasi wasit, token dan commentary identik dengan kandidat v54.\n'
        'Tes Exhibition, kamera biasa/STADIUM, DAY/NIGHT, rematch dan close-up.\n'
        'Pemain fallback dan alasannya ada di PLAYER-STATUS.csv; anggaran ada di PLAYER-BUDGET.csv.\n'
        'Sunderland belum ada di katalog sumber ini. Angkat piala/AI wasit PC penuh tetap belum selesai.\n'
        'Validasi offline bukan jaminan animasi atau 60 FPS Switch. Simpan scene-runtime.log.\n'
        f'Kebijakan rilis: {policy["policy"]}; catatan visual tetap tercatat, bukan klaim semua rambut sempurna.\n'
        f'{len(proof["preserved_cooked_mip_warning_base_ids"])} rantai mip rambut dipertahankan dari hasil cook tanpa memaksa alpha; lihat VERIFICATION.json.\n'
        'Rollback: keluarkan PAK v55, pulihkan PAK dan NRO sebelumnya.\n', encoding='utf-8')
    archive = destination.with_suffix('.zip'); file_hashes = hash_tree(destination)
    print(dict(stage='zip_and_payload_readback'), flush=True)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name in sorted(file_hashes): z.write(destination/name, name)
    with zipfile.ZipFile(archive) as z:
        import hashlib
        if z.testzip() is not None or set(z.namelist()) != set(file_hashes):
            raise ValueError('ZIP membership or CRC failure')
        for name, expected in file_hashes.items():
            with z.open(name) as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                    raise ValueError('ZIP payload hash changed')
    result = dict(key=key, directory=str(destination), file_hashes=file_hashes,
                  zip=str(archive), zip_sha256=sha(archive), pak_sha256=proof['pak_sha256'],
                  players=len(players), fallbacks=len(status)-len(players), zip_readback_verified=True)
    write(complete, result); write(work/'latest-candidate.json', result)
    return result


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--config', required=True)
    args=p.parse_args(); import json
    print(json.dumps(package(read(args.config)), indent=2))
