"""Native Italy placement, source separator and v76 regression boundaries."""
from pathlib import Path
import struct
import sys

import numpy as np
from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_fl26_scoreboard_profiles as profiles
from afp_score_layout import placements, read_movies


@pytest.fixture
def native_pair():
    mobile = ROOT / "local-debug/scoreboard-v62/mobile.bin"
    prior = ROOT / "local-debug/review-v76/scoreboards/italy/game2dPes-candidate.bin"
    if not mobile.is_file() or not prior.is_file():
        pytest.skip("requires ignored owned Mobile and pinned v76 UI; no payload fixture restored")
    old = prior.read_bytes()
    assert profiles.digest(old) == "bf2a48fa16759a81f0a1d3cca23153ce9cf11dcbb9dafb2bae95e9f937313f26"
    original = mobile.read_bytes()
    assert profiles.digest(original) == profiles.v62.MOBILE_SHA256
    score = next(m for m in read_movies(original) if m.name == "game2d_score")
    changed, _ = profiles.patch_score(score.data, "italy")
    before = next(m for m in read_movies(old) if m.name == "game2d_score").data
    return before, changed


def test_native_names_center_in_blue_cells_excluding_kit_strips():
    spec = profiles.PROFILES["italy"]
    for point, cell in zip(spec["names"], spec["name_cells"]):
        assert point[0] + 60 * profiles.SCALE / 2 == (cell[0] + cell[2]) / 2
    assert spec["name_cells"][0][2] <= spec["kits"][0][0]
    assert spec["name_cells"][1][0] >= spec["kits"][1][0]


def test_v76_native_delta_is_only_uniform_field_translations(native_pair):
    old, new = map(placements, native_pair)
    expected = {63: (11, -2), 61: (9, -2), 67: (-2, -2.5),
                65: (-2, -2.5), 75: (0, -2.65), 69: (0, -2.65)}
    moved = set()
    for before, after in zip(old, new):
        expected_row = dict(before)
        if before["parent"] == 28 and before["depth"] in expected and "translate" in before:
            dx, dy = expected[before["depth"]]
            x, y = before["translate"]
            expected_row["translate"] = (round(x + dx, 2), round(y + dy, 2))
            moved.add(before["depth"])
        assert after == expected_row
    assert moved == set(expected)
    report = profiles.field_edit_report(*native_pair)
    assert report["scripts_labels_frames_bindings_flags_identical"]
    assert {e["field"] for e in report["edits"]} == {"translate"}


def test_actual_native_kit_stack_centers_with_four_pixel_margins(native_pair):
    rows = placements(native_pair[1])
    report = profiles.verify_geometry(rows, profiles.PROFILES["italy"])
    assert report["kit_palette_centered"]
    assert len(report["kit_checks"]) == 2
    for check in report["kit_checks"]:
        assert check["bounds"][1::2] == pytest.approx((24, 56), abs=.001)
    bad = bytearray(native_pair[1])
    row = next(r for r in rows if (r["parent"], r["depth"], r["frame"]) == (28, 75, 0))
    struct.pack_into("<i", bad, row["translate_offset"] + 4, 28 * 20)
    with pytest.raises(ValueError, match="kit colours are not centered"):
        profiles.verify_geometry(placements(bad), profiles.PROFILES["italy"])


def test_owned_separator_raster_moves_to_plate_center_without_repainting():
    # Synthetic stand-in exercises the bounded source-raster operation; native
    # owned crop admission remains in build_profile's pinned hash check.
    panel = Image.new("RGBA", (320, 70), "white")
    ink = Image.new("RGBA", (7, 3), (0, 12, 83, 255))
    panel.alpha_composite(ink, (155, 23))
    report = profiles.center_italy_separator(panel, 40)
    l, t, r, b = report["target_bounds"]
    assert abs((t + b) / 2 - 20) <= .5
    assert panel.crop((l, t, r, b)).tobytes() == ink.tobytes()
    assert np.asarray(panel)[23:26, 155:162].tolist() == np.full((3, 7, 4), 255).tolist()
    with pytest.raises(ValueError, match="separator is missing"):
        profiles.center_italy_separator(Image.new("RGBA", (320, 70), "white"), 40)
