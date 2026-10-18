from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from realface_league_merge_prepared import merge_rows


def sample():
    row = dict(base_id=12, native_player_id=44, fingerprint='owner', status='prepared',
               triangles=1998, cache_key='new', budgets={}, recipe_source_sha256={'code':'current'},
               folder='unused')
    return row


def run(existing, retry):
    return merge_rows(existing, [('retry', retry)], {12: sample()},
                      lambda _: {'code':'current'}, lambda *_: True)


def test_current_retry_replaces_preparation_but_failure_does_not():
    row = sample()
    rows, changed = run([dict(row, cache_key='old')], [row])
    assert rows == [row] and changed[0]['previous_key'] == 'old'
    failed = dict(row, cache_key='failed', status='held_geometry')
    assert run(rows, [failed]) == (rows, [])


def test_accepted_head_cannot_be_replaced():
    row = sample()
    inherited = dict(row, reuse_cooked={'cooked_cache_key':'accepted'})
    assert run([inherited], [inherited]) == ([inherited], [])
    with pytest.raises(ValueError, match='accepted'):
        run([inherited], [row])


@pytest.mark.parametrize('change,match', [
    ({'fingerprint':'other'}, 'identity'),
    ({'recipe_source_sha256':{'code':'old'}}, 'recipe'),
    ({'triangles':2001}, 'triangle'),
])
def test_rejects_wrong_owner_stale_recipe_and_oversize(change, match):
    with pytest.raises(ValueError, match=match):
        run([], [dict(sample(), **change)])


def test_asset_hash_mismatch_prevents_merge():
    with pytest.raises(ValueError, match='assets changed'):
        merge_rows([], [('retry', [sample()])], {12:sample()},
                   lambda _: {'code':'current'}, lambda *_: False)
