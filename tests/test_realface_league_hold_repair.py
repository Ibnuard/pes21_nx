from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import realface_budget_experiment as trial
from realface_league_hold_repair import hair_search, SEARCHES
from realface_league_finalize import recovery_allocation
from realface_preview_cache import index_views, seed_views
from realface_batch_inventory import write
from realface_pipeline import sha


@pytest.mark.parametrize('error,weight', SEARCHES)
def test_search_preserves_face_and_locks_and_keys_new_recipe(error, weight):
    config = dict(experimental_head_cap=7000,
                  experimental_allocations={'1':recovery_allocation(7000,3000,True)})
    old = trial.effective_allocation(config, 1)
    with hair_search(error, weight):
        new = trial.effective_allocation(config, 1)
        assert new == dict(old,hair_error_cm=error,hair_uv_weight=weight)
        assert new['hair_face_lock'] and new['face_skin']==3000
        assert 'realface_league_hold_repair.py' in trial.recipe_code(new)
    assert trial.effective_allocation(config, 1)==old


def test_search_restores_after_failure_and_rejects_unbounded_inputs():
    original = trial.effective_allocation,trial.recipe_code
    with pytest.raises(RuntimeError):
        with hair_search(*SEARCHES[0]):
            raise RuntimeError('interrupted')
    assert (trial.effective_allocation,trial.recipe_code)==original
    with pytest.raises(ValueError):
        with hair_search(5,.01):
            pass


def test_preview_reuse_requires_exact_current_inputs_and_bytes(tmp_path):
    old = tmp_path/'front'/'old'; old.mkdir(parents=True)
    png = old/'1-front.png'; png.write_bytes(b'existing inspected render')
    metadata = dict(view='front',prepared_key='p',cooked_key='c',renderer_sha256='r',image_sha256=sha(png))
    write(png.with_suffix('.json'),metadata)
    row = dict(base_id=1,cache_key='p',cooked_cache_key='c')
    assert not index_views(tmp_path,[dict(row,cache_key='other')],'r')
    assert not index_views(tmp_path,[row],'other')
    cache = index_views(tmp_path,[row],'r'); assert cache[(1,'front')]==png
    output = tmp_path/'front'/'new'; seed_views(output,[row],('front',),cache)
    assert (output/png.name).read_bytes()==png.read_bytes()
    png.write_bytes(b'changed')
    assert not index_views(tmp_path,[row],'r').get((1,'front'))==png
    with pytest.raises(ValueError):
        seed_views(output,[row],('front',),cache)
