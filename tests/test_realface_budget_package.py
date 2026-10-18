from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from realface_budget_package import counts, validate_cohort, head_limit
import json
from realface_pipeline import sha


def test_cooked_budget_enforces_two_sections_without_legacy_2k_clamp():
    proof = dict(parts={part:dict(components={role:dict(triangles=number,cooked_vertices=100)})
                        for part,role,number in [('face','skin',4150),('hair','hair',1820)]})
    assert counts(proof, 6000)['triangles'] == 5970
    with pytest.raises(ValueError, match='ceiling'): counts(proof, 4500)
    proof['parts']['face']['components']['eye'] = dict(triangles=0,cooked_vertices=0)
    with pytest.raises(ValueError, match='section'): counts(proof, 6000)


def test_incomplete_duplicate_or_changed_identity_cannot_be_packaged():
    scope = dict(teams=[100,108], selected_base_ids=[1,2])
    ready = dict(base_id=1,native_player_id=11,fingerprint='a',cache_key='k',status='prepared')
    held = dict(base_id=2,native_player_id=12,fingerprint='b',cache_key='l',status='held_geometry')
    verified = dict(ready,status='validated')
    assert validate_cohort(scope,[ready,held],[verified]) == [verified]
    with pytest.raises(ValueError, match='finish preparation'):
        validate_cohort(scope,[ready],[verified])
    with pytest.raises(ValueError, match='verification result'):
        validate_cohort(scope,[ready,held],[])
    with pytest.raises(ValueError, match='identity'):
        validate_cohort(scope,[ready,held],[dict(verified,fingerprint='changed')])
    with pytest.raises(ValueError, match='Duplicate'):
        validate_cohort(scope,[ready,dict(held,native_player_id=11)],[verified])


def test_failed_cook_is_recorded_but_never_packaged():
    row = dict(base_id=1,native_player_id=11,fingerprint='a',cache_key='k',status='prepared')
    assert validate_cohort(dict(teams=[100,108],selected_base_ids=[1]), [row],
                           [dict(row,status='held_cook_validation')]) == []


def test_retained_original_requires_pinned_identity_cache_and_exact_count(tmp_path):
    path=tmp_path/'accepted.json'
    row=dict(base_id=1,native_player_id=11,fingerprint='a',cache_key='prepared',
             cooked_folder='accepted',cooked_cache_key='cooked',triangles=6932,status='validated')
    path.write_text(json.dumps([row]))
    candidate=dict(row,accepted_baseline=dict(verification=str(path),
        verification_sha256=sha(path),triangles=6932,reason='5k hair reduction held'))
    assert head_limit(row,5000)==5000
    assert head_limit(candidate,5000)==7000
    with pytest.raises(ValueError,match='identity or cooked cache'):
        head_limit(dict(candidate,cooked_cache_key='new-unverified'),5000)
    with pytest.raises(ValueError,match='triangle count'):
        head_limit(dict(candidate,accepted_baseline=dict(candidate['accepted_baseline'],triangles=6000)),5000)
    path.write_text(json.dumps([dict(row,triangles=6000)]))
    with pytest.raises(ValueError,match='verification changed'):head_limit(candidate,5000)
