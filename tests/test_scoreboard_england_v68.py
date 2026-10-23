"""Actual owned timeline regressions; no native rendering/playback is claimed."""
from pathlib import Path
import struct
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_fl26_scoreboard_profiles as profiles
from afp_score_layout import placements, read_movies


@pytest.fixture
def score_pair():
    path = ROOT / 'local-debug/scoreboard-v62/mobile.bin'
    if not path.is_file():
        pytest.skip('requires ignored owned Mobile UI; no proprietary fixture restored')
    data = path.read_bytes()
    assert profiles.digest(data) == profiles.v62.MOBILE_SHA256
    movie = next(m for m in read_movies(data) if m.name == 'game2d_score')
    changed, _ = profiles.patch_score(movie.data, 'england')
    return movie.data, changed


def node(rows, parent, depth, frame=0):
    return next(r for r in rows if (r['parent'], r['depth'], r['frame']) == (parent, depth, frame))


def colour_at(rows, parent, depth, frame):
    """Bounded native placement colour semantics, not an AP2 interpreter.

    Explicit packed ARGB updates and payload-less colour resets are enough
    to reproduce the white UIR number against the white loss-time plate.
    """
    value = 0xffffffff
    for row in rows:
        if row['parent'] != parent or row['depth'] != depth or row['frame'] > frame:
            continue
        if 'mult8' in row:
            value = int(row['mult8'][0])
        elif row['flags'] & 8:
            value = 0xffffffff
    return value


def test_native_uir_name_width_restored_without_stretching_height(score_pair):
    original, changed = map(placements, score_pair)
    for depth in (61, 63):
        before, after = node(original, 28, depth), node(changed, 28, depth)
        assert after['scale'][0] == pytest.approx(before['scale'][0] * profiles.SCALE, abs=.0015)
        assert after['scale'][1] == pytest.approx(before['scale'][1] * profiles.SCALE, abs=.001)
        assert after['source'] == before['source'] == 5
    # Both full-width name fields retain a common centre in separate cells.
    spec = profiles.PROFILES['england']
    for point, cell in zip(spec['names'], spec['name_cells']):
        assert point[0] + 26 == (cell[0] + cell[2]) / 2


def test_only_conditional_plate_is_visible_and_it_abuts_clock_right(score_pair):
    rows = placements(score_pair[1])
    # The always-present old clock tile cannot leave a white box below the board.
    for row in rows:
        if row['parent'] == 28 and row['depth'] == 13 and 'translate' in row:
            x, y = row['translate']
            assert x + 32 + 48 < 0 and y + 12 + 24 < 0
    origin = node(rows, 28, 56)['translate']
    image = node(rows, 22, 1)['translate']
    l, t = (a + b for a, b in zip(origin, image))
    cell = profiles.PROFILES['england']['added_time_cell']
    clock = profiles.PROFILES['england']['clock_cell']
    assert (l, t, l + 48, t + 24) == cell
    assert cell[0] == clock[2] and cell[1::2] == clock[1::2]
    assert node(rows, 24, 1)['name'] == 'plate_lossTime'
    assert node(rows, 24, 3)['name'] == 'losstime_contents'
    assert node(rows, 23, 2)['name'] == 'numbers'


def test_dynamic_white_number_becomes_readable_through_entire_show_hide(score_pair):
    original, changed = map(placements, score_pair)
    assert colour_at(original, 24, 3, 24) == 0xffffffff
    assert colour_at(changed, 24, 3, 1) == 0
    assert colour_at(changed, 24, 3, 24) == 0x000000ff
    for frame in range(17, 41):
        colour = colour_at(changed, 24, 3, frame)
        assert colour >> 8 == 0  # black even when the UIR glyph itself is white
        assert colour_at(changed, 24, 1, frame) >> 8 == 0xffffff
    assert colour_at(changed, 24, 3, 41) == 0
    assert colour_at(changed, 24, 1, 41) & 255 == 0
    # Native fade endpoints/curve survive, except the last reveal keyframe
    # supplies full alpha previously provided by the now-disabled white reset.
    for row in original:
        if row['parent'] == 24 and row['depth'] == 3 and 'mult8' in row:
            actual = node(changed, 24, 3, row['frame'])
            expected = 255 if row['frame'] == 23 else int(row['mult8'][0]) & 255
            assert int(actual['mult8'][0]) & 255 == expected


def test_approved_colour_reset_is_the_only_flag_edit(score_pair):
    report = profiles.field_edit_report(*score_pair)
    assert report['scripts_labels_frames_bindings_identical']
    changes = report['placement_flag_changes']
    assert len(changes) == 1
    assert (changes[0]['parent'], changes[0]['depth'], changes[0]['frame']) == (24, 3, 24)
    changed = bytearray(score_pair[1])
    wrong = node(placements(changed), 24, 1, 24)
    struct.pack_into('<I', changed, wrong['offset'], wrong['flags'] & ~8)
    with pytest.raises(ValueError, match='unapproved native placement flag'):
        profiles.field_edit_report(score_pair[0], bytes(changed))


def test_no_bytecode_or_binding_edits_are_hidden_in_field_allowlist(score_pair):
    bad = bytearray(score_pair[1])
    # Change a movie header feature byte outside the placement edit envelope.
    bad[12] ^= 1
    with pytest.raises(ValueError, match='outside verified placement fields'):
        profiles.field_edit_report(score_pair[0], bytes(bad))


@pytest.mark.parametrize('depth,point,error', [
    (56, (6, 90), 'right edge'),
    (13, (6, 90), 'visible blank plate'),
])
def test_verifier_rejects_regression_to_separate_lower_blank_plate(score_pair, depth, point, error):
    bad = bytearray(score_pair[1])
    row = node(placements(bad), 28, depth)
    struct.pack_into('<ii', bad, row['translate_offset'], *(round(v * 20) for v in point))
    with pytest.raises(ValueError, match=error):
        profiles.verify_geometry(placements(bad), profiles.PROFILES['england'])


def test_optical_lift_changes_only_four_text_translations_uniformly(score_pair):
    baseline = ROOT / 'local-debug/scoreboard-england-v68/candidate/england'
    if not (baseline / 'game2dPes-candidate.bin').is_file():
        pytest.skip('requires ignored pinned v68 UI for the vertical-only delta check')
    from build_competition_scoreboards import txp
    packet = (baseline / 'c9.nxsb').read_bytes()
    assert profiles.digest(packet) == 'e7345d53683034db7041f458a99fbbdd00a2e3dca1cd13eda10bdecc936123cc'
    data = (baseline / 'game2dPes-candidate.bin').read_bytes()
    assert txp(data) == packet[32:]
    previous = placements(next(m for m in read_movies(data) if m.name == 'game2d_score').data)
    current = placements(score_pair[1])
    assert len(previous) == len(current)
    moved = set()
    for old, new in zip(previous, current):
        if old['parent'] == 28 and old['depth'] in (61, 63, 65, 67) and 'translate' in old:
            old = dict(old)
            x, y = old['translate']
            old['translate'] = (x, round(y - 3, 2))
            moved.add(old['depth'])
        assert new == old
    assert moved == {61, 63, 65, 67}
