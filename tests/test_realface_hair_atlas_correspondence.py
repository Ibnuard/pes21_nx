"""Synthetic provenance regressions; no proprietary face fixtures required."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from realface_hair_atlas_correspondence import correspondence


@pytest.fixture
def fixture(tmp_path):
    fbx = tmp_path/'source.fbx'; fbx.write_bytes(b'project-authored synthetic mesh')
    texture = tmp_path/'source.png'; texture.write_bytes(b'synthetic atlas bytes')
    owner = dict(base_id=123, native_player_id=456, fingerprint='synthetic-owner')
    profile = dict(owner, hair_fbx=str(fbx), hair_texture=str(texture))
    prepared = dict(owner, cache_key='prepared-source-recipe')
    job = dict(owner, source_profile=copy.deepcopy(profile), budgets={'hair_mode': 'cards'})
    return prepared, owner, job, profile


def test_original_source_correspondence_is_only_a_provenance_result(fixture):
    result = correspondence(*fixture)
    assert result['recipe_correspondence'] == 'same_source_fbx_atlas_cards'
    assert result['prepared_key'] == 'prepared-source-recipe'
    assert not result['geometry_validated'] and not result['visual_accepted'] and not result['promoted']


def test_byte_identical_copied_paths_are_supported(fixture, tmp_path):
    prepared, owner, job, dense = fixture
    for role in ('hair_fbx', 'hair_texture'):
        target = tmp_path/('copied-'+Path(dense[role]).name)
        target.write_bytes(Path(dense[role]).read_bytes())
        job['source_profile'][role] = str(target)
    assert correspondence(*fixture)['recipe_correspondence'] == 'same_source_fbx_atlas_cards'


@pytest.mark.parametrize('role', ['hair_fbx', 'hair_texture'])
def test_existing_own_uv_repair_cannot_inherit_raw_uv0_correspondence(fixture, tmp_path, role):
    repaired = tmp_path/'own-repaired-input'; repaired.write_bytes(b'explicit own-source UV repair')
    fixture[2]['source_profile'][role] = str(repaired)
    result = correspondence(*fixture)
    assert result['recipe_correspondence'] == 'requires_own_repair_uv_proof_do_not_promote_rgb'
    assert not result['promoted']


@pytest.mark.parametrize('slot', [1, 2, 3])
def test_reused_numeric_slot_without_matching_fingerprint_is_rejected(fixture, slot):
    values = copy.deepcopy(fixture)
    values[slot]['fingerprint'] = 'different-owner'
    with pytest.raises(ValueError, match='identity'):
        correspondence(*values)


def test_nested_source_owner_must_match_too(fixture):
    fixture[2]['source_profile']['base_id'] += 1
    with pytest.raises(ValueError, match='identity'):
        correspondence(*fixture)


def test_non_card_uv_recipe_requires_specific_proof(fixture):
    fixture[2]['budgets']['hair_mode'] = 'shell'
    assert correspondence(*fixture)['recipe_correspondence'] == 'requires_own_repair_uv_proof_do_not_promote_rgb'


def test_missing_ignored_input_is_unavailable(fixture):
    Path(fixture[3]['hair_fbx']).unlink()
    with pytest.raises(FileNotFoundError, match='Optional local'):
        correspondence(*fixture)


def test_same_prepared_and_dense_wrong_owner_cannot_be_hidden(fixture):
    fixture[0]['native_player_id'] += 1
    fixture[3]['native_player_id'] += 1
    with pytest.raises(ValueError, match='identity'):
        correspondence(*fixture)
