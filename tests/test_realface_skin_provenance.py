from pathlib import Path
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_skin_provenance import matching_identity, compare_necks


def test_same_slot_different_person_or_missing_fingerprint_rejected():
    first = dict(base_id=1, native_player_id=10, fingerprint='own-person')
    matching_identity(first, dict(first))
    for changed in (dict(first, base_id=2), dict(first, native_player_id=11),
                    dict(first, fingerprint='another-person'),
                    dict(base_id=1, native_player_id=10)):
        with pytest.raises(ValueError, match='identities disagree'):
            matching_identity(first, changed)


def test_decoded_quantization_and_wrong_texture_are_distinguished():
    palette = {i: [240 - i * 25, 210 - i * 25, 190 - i * 25] for i in range(1, 7)}
    source = Image.new('RGBA', (256, 256), (*palette[3], 255))
    small = Image.new('RGBA', (256, 256), (*(v + 1 for v in palette[3]), 255))
    assert compare_necks(source, small, palette, 1)['palette_recommendation_stable']
    wrong = Image.new('RGBA', (256, 256), (*palette[6], 255))
    assert not compare_necks(source, wrong, palette, 1)['palette_recommendation_stable']


def test_default_selector_is_not_an_automatic_patch_and_transparency_rejected():
    palette = {i: [240 - i * 25, 210 - i * 25, 190 - i * 25] for i in range(1, 7)}
    opaque = Image.new('RGBA', (256, 256), (*palette[3], 255))
    proof = compare_necks(opaque, opaque, palette, 7)
    assert proof['palette_recommendation_stable']
    assert proof['cooked_classification']['status'] == 'held_measurement'
    assert not proof['cooked_classification']['automatic_patch']
    transparent = Image.new('RGBA', (256, 256), (*palette[3], 0))
    with pytest.raises(ValueError, match='not opaque'):
        compare_necks(opaque, transparent, palette, 1)
