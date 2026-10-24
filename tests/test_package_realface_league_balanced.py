"""A final league release needs complete results and preserves the v54 runtime."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import package_realface_league_balanced as pack
from realface_league_balanced import POLICY


def rows():
    row = dict(base_id=1, native_player_id=7, fingerprint='identity', cache_key='recipe', status='prepared')
    proof = dict(row, status='validated')
    return row, proof


def test_incomplete_cook_and_changed_identity_are_rejected():
    row, proof = rows(); scope=dict(policy=POLICY, selected_base_ids=[1])
    review=dict(decision='offline_candidate_reviewed', reviewed_base_ids=[1], held_base_ids=[])
    assert pack.validate_completion(scope, [row], [proof], review) == [proof]
    with pytest.raises(ValueError, match='independent cook'):
        pack.validate_completion(scope, [row], [], review)
    with pytest.raises(ValueError, match='identity'):
        pack.validate_completion(scope, [row], [dict(proof, fingerprint='donor')], review)
    with pytest.raises(ValueError, match='recipe'):
        pack.validate_completion(scope, [row], [dict(proof, cache_key='another')], review)


def test_visual_review_cannot_be_replaced_by_numeric_success():
    row, proof = rows(); scope=dict(policy=POLICY, selected_base_ids=[1])
    with pytest.raises(ValueError, match='review'):
        pack.validate_completion(scope, [row], [proof], {})
    review=dict(decision='offline_candidate_reviewed', reviewed_base_ids=[1], held_base_ids=[1])
    with pytest.raises(ValueError, match='review'):
        pack.validate_completion(scope, [row], [proof], review)
    review['held_reasons']={'1':'visible scalp gap'}
    assert pack.validate_completion(scope, [row], [proof], review) == []


def test_v54_copy_is_byte_identical_and_rejects_changes_or_traversal(tmp_path):
    original = tmp_path/'original'; original.mkdir()
    path = original/'switch/pes21_nx/pes21_nx.nro'; path.parent.mkdir(parents=True)
    path.write_bytes(b'owned synthetic NRO')
    proof={'bytes':path.stat().st_size,'sha256':pack.sha(path)}
    config=dict(v54_candidate=str(original), v54_pinned_files={'switch/pes21_nx/pes21_nx.nro':proof})
    output=tmp_path/'release'; pack.copy_v54(config, output)
    assert (output/'switch/pes21_nx/pes21_nx.nro').read_bytes()==path.read_bytes()
    path.write_bytes(b'changed')
    with pytest.raises(ValueError, match='changed'):
        pack.copy_v54(config, tmp_path/'bad')
    config['v54_pinned_files']={'../outside':proof}
    with pytest.raises(ValueError, match='changed'):
        pack.copy_v54(config, tmp_path/'bad')


def test_preview_hashes_and_current_keys_are_required(tmp_path):
    import json
    row, proof = rows(); proof['cooked_cache_key']='cooked'
    image=tmp_path/'1-front.png'; image.write_bytes(b'synthetic reviewed image')
    metadata=dict(prepared_key='recipe', cooked_key='cooked', image_sha256=pack.sha(image), view='front')
    image.with_suffix('.json').write_text(json.dumps(metadata))
    review=dict(images=[dict(base_id=1,path=str(image),sha256=pack.sha(image))])
    pack.validate_preview_evidence(tmp_path, [proof], review)
    with pytest.raises(ValueError, match='views missing'):
        pack.validate_preview_evidence(tmp_path, [dict(proof, league_exception={'reason':'hair'})], review)
    metadata['cooked_key']='stale';image.with_suffix('.json').write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match='current prepared/cooked'):
        pack.validate_preview_evidence(tmp_path, [proof], review)


def test_budget_priority_needs_explicit_current_cohort_decision(tmp_path):
    import json
    row, proof = rows()
    (tmp_path/'prepare-report.json').write_text(json.dumps([row]))
    (tmp_path/'verify-report.json').write_text(json.dumps([proof]))
    path = tmp_path/'RELEASE-DECISION.json'
    decision = dict(policy=pack.BUDGET_PRIORITY, user_directive='Budget first; retain existing appearance.',
                    prepare_sha256=pack.sha(tmp_path/'prepare-report.json'),
                    verify_sha256=pack.sha(tmp_path/'verify-report.json'), included_base_ids=[1],
                    normal_complete_head_limit=5000, exceptional_complete_head_limit=7000,
                    appearance_notes_advisory=True, preserve_original_cooked_mips_outside_tiny_guard=True)
    config = dict(release_policy=pack.BUDGET_PRIORITY, release_decision=str(path))
    path.write_text(json.dumps(decision))
    assert pack.release_policy(config, tmp_path, [row], [proof])['preserve_cooked_outside_tiny_guard']
    # Held sources are still bound by the complete report hash and remain
    # native fallbacks; they are not falsely listed as included cooked heads.
    held = dict(row, base_id=2, native_player_id=8, status='held_source')
    assert pack.release_policy(config, tmp_path, [row, held], [proof])['preserve_cooked_outside_tiny_guard']
    assert not pack.release_policy({}, tmp_path, [row], [proof])['preserve_cooked_outside_tiny_guard']
    for change in [dict(user_directive=''), dict(verify_sha256='stale'), dict(included_base_ids=[2]),
                   dict(normal_complete_head_limit=7000), dict(appearance_notes_advisory=False)]:
        path.write_text(json.dumps(dict(decision, **change)))
        with pytest.raises(ValueError, match='budget-priority'):
            pack.release_policy(config, tmp_path, [row], [proof])


def test_budget_release_preserves_rejected_mip_bytes_without_forcing_alpha(tmp_path, monkeypatch):
    path = tmp_path/'hair.uexp'
    path.write_bytes(b'original cooked payload')
    path.with_suffix('.uasset').write_bytes(b'original asset header')
    def rejected(_):
        raise ValueError('Discarded hair mip exceeds the bounded tiny-mip policy')
    class Texture:
        def __init__(self, _): pass
        def payload(self, index): return bytes([10, 20, 30, 255])
    monkeypatch.setattr(pack, 'protect_texture', rejected)
    monkeypatch.setattr(pack, 'Texture', Texture)
    with pytest.raises(ValueError, match='bounded tiny-mip'):
        pack.release_hair_mips(path, dict(preserve_cooked_outside_tiny_guard=False))
    proof = pack.release_hair_mips(path, dict(preserve_cooked_outside_tiny_guard=True))
    assert path.read_bytes() == b'original cooked payload'
    assert path.with_suffix('.uasset').read_bytes() == b'original asset header'
    assert proof['changed_mips'] == [] and proof['alpha_forced'] is False
    assert proof['original_cooked_payloads_byte_identical']
    def unrelated_failure(_):
        raise ValueError('Only native BGRA is supported')
    monkeypatch.setattr(pack, 'protect_texture', unrelated_failure)
    with pytest.raises(ValueError, match='native BGRA'):
        pack.release_hair_mips(path, dict(preserve_cooked_outside_tiny_guard=True))


def test_budget_policy_cannot_hide_mutation_during_failed_mip_repair(tmp_path, monkeypatch):
    path = tmp_path/'hair.uexp'; path.write_bytes(b'original')
    def rejected_with_mutation(path):
        path.write_bytes(b'changed')
        raise ValueError('Discarded hair mip exceeds the bounded tiny-mip policy')
    monkeypatch.setattr(pack, 'protect_texture', rejected_with_mutation)
    with pytest.raises(ValueError, match='changed cooked bytes'):
        pack.release_hair_mips(path, dict(preserve_cooked_outside_tiny_guard=True))


def test_budget_review_is_explicit_and_never_claims_new_visual_acceptance():
    row, proof = rows()
    held = dict(row, base_id=2, native_player_id=8, status='held_geometry')
    scope = dict(policy=POLICY, selected_base_ids=[1, 2])
    review = dict(decision='budget_integrity_reviewed', budget_reviewed_base_ids=[1],
                  held_base_ids=[], new_visual_acceptance=False)
    assert pack.validate_completion(scope, [row, held], [proof], review, pack.BUDGET_PRIORITY) == [proof]
    for bad in [dict(review, budget_reviewed_base_ids=[]), dict(review, new_visual_acceptance=True)]:
        with pytest.raises(ValueError, match='review'):
            pack.validate_completion(scope, [row, held], [proof], bad, pack.BUDGET_PRIORITY)
    with pytest.raises(ValueError, match='review'):
        pack.validate_completion(scope, [row, held], [proof], review)
    with pytest.raises(ValueError, match='independent cook'):
        pack.validate_completion(scope, [row, held], [], review, pack.BUDGET_PRIORITY)


def test_explicit_runtime_pins_override_historical_v54_and_keep_every_file(tmp_path):
    original = tmp_path/'latest'
    names = ['switch/pes21_nx/pes21_nx.nro', 'switch/pes21_nx/new-weather.pak']
    pins = {}
    for i, name in enumerate(names):
        p = original/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(bytes([i])*8)
        pins[name] = dict(bytes=8, sha256=pack.sha(p))
    config = dict(runtime_candidate=str(original), runtime_pinned_files=pins,
                  v54_candidate='must-never-be-read', v54_pinned_files={'wrong': {}})
    output = tmp_path/'release'
    pack.copy_v54(config, output)
    assert all(pack.sha(output/n) == pins[n]['sha256'] for n in names)
    with pytest.raises(ValueError, match='Complete explicit'):
        pack.runtime_binding(dict(config, runtime_pinned_files={}))


def test_all_preserved_heads_reject_texture_mutation_and_changed_identity():
    row, _ = rows()
    hashes = {n: 'exact' for n in pack.asset_names(row['native_player_id'])}
    preservation = dict(players={1: row}, hashes=hashes)
    pack.validate_preserved_head(row, preservation, hashes)
    changed = dict(hashes)
    changed[next(iter(changed))] = 'mutated'
    with pytest.raises(ValueError, match='bytes changed'):
        pack.validate_preserved_head(row, preservation, changed)
    with pytest.raises(ValueError, match='identity'):
        pack.validate_preserved_head(dict(row, fingerprint='donor'), preservation, hashes)


@pytest.mark.parametrize('name', ['../outside', 'FootballNX-../../outside', 'D:/FootballNX-test'])
def test_release_directory_cannot_escape_staging(name):
    with pytest.raises(ValueError, match='Safe FootballNX'):
        pack.release_name(dict(release_directory_name=name))
