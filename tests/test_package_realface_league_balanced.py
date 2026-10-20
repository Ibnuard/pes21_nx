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
