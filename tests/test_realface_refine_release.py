import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from realface_refine_release import permitted_changes, check_preservation
from realface_surface_patch import FACE, BASE
from realface_refine import retry_compact_hair


def test_selective_release_only_allows_selected_mesh_and_hair_texture_files():
    changes = permitted_changes([dict(native_player_id=7, refine_face=True, refine_hair=False),
                                 dict(native_player_id=9, refine_face=False, refine_hair=True)])
    assert len(changes) == 7
    assert FACE+'7_face.uexp' in changes
    assert FACE+'9_hair_parts_color_tablet.ubulk' in changes
    assert FACE+'7_face_tablet.ubulk' not in changes
    assert FACE+'face_7.uasset' not in changes
    assert FACE+'9_face.uexp' not in changes


def test_package_preserves_neutral_normal_material_and_other_players():
    before = {FACE+'7_face.uexp':'old', FACE+'8_face.uexp':'other',
              BASE+'pesnx0_face_normal_tablet.ubulk':'normal', FACE+'face_7.uasset':'material'}
    allowed = {FACE+'7_face.uexp'}
    repaired = dict(before, **{FACE+'7_face.uexp':'new'})
    assert check_preservation(before, repaired, allowed) == [FACE+'7_face.uexp']
    for target in set(before)-allowed:
        bad = dict(repaired, **{target:'changed'})
        with pytest.raises(ValueError, match='unapproved'):
            check_preservation(before, bad, allowed)
    with pytest.raises(ValueError, match='coverage'):
        check_preservation(before, {k:v for k,v in repaired.items() if k != FACE+'8_face.uexp'}, allowed)


def test_bounded_hair_retry_requires_same_identity_source_and_converter():
    owner = dict(base_id=7, native_player_id=17, fingerprint='player-a', cache_key='original')
    code = {'converter.py':'sha'}
    old = dict(owner, baseline=owner, recipe_source_sha256=code, budgets=dict(solid_scalp=True),
               status='held_geometry', reason='Hair silhouette held: source outline differs')
    assert retry_compact_hair(old, owner, code)
    for changed in (dict(old, fingerprint='player-b'), dict(old, recipe_source_sha256={}),
                    dict(old, reason='Surface quality held face/skin')):
        assert not retry_compact_hair(changed, owner, code)
    assert retry_compact_hair(dict(old, status='prepared', budgets=dict(solid_scalp=False)), owner, code)
    assert not retry_compact_hair(dict(old, status='prepared'), owner, code)
