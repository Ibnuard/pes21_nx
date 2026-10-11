import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from stadium_material_policy import crowd_uv, camera_visible, CROWD_FRAMES, CROWD_FPS


def test_crowd_uses_every_native_frame_without_crossing_neighbour():
    for frame in range(CROWD_FRAMES):
        for v in (-1, 0, .5, 1, 2):
            u, y = crowd_uv(.75, v, (frame+.2)/CROWD_FPS)
            assert u == .375  # Same projected person size as the old 8:1 row.
            assert frame/CROWD_FRAMES < y < (frame+1)/CROWD_FRAMES
        assert crowd_uv(.75, .5, frame/CROWD_FPS) == pytest.approx(
            crowd_uv(.75, .5, frame/CROWD_FPS + CROWD_FRAMES/CROWD_FPS))


def test_shell_clears_every_layer_before_corner_players_at_all_camera_heights():
    import math
    for x in (-5500., 5500.):
        for y in (-3700., 3700.):
            for height in (160., 600., 1200., 2000., 3200.):
                for angle in range(0, 360, 15):
                    camera = (x+4000*math.cos(math.radians(angle)),
                              y+4000*math.sin(math.radians(angle)), height)
                    for player_height in (15., 140., 240.):
                        target = (x, y, player_height)
                        for fraction in (.01, .25, .5, .75, .99):
                            wall = tuple(c+(t-c)*fraction for c, t in zip(camera, target))
                            assert not camera_visible(wall, camera)


def test_far_stands_and_rays_away_from_pitch_remain_visible():
    for sign_x in (-1, 1):
        for sign_y in (-1, 1):
            camera = (sign_x*6200, sign_y*4400, 300)
            assert camera_visible((-sign_x*8000, -sign_y*6000, 800), camera)
            assert camera_visible((sign_x*9000, sign_y*8000, 1500), camera)
    assert camera_visible((0, 8000, 2000), (0, 0, 2500))
    assert camera_visible((0, 8000, 2000), (0, -4500, 2500))


def test_parallel_axis_and_lens_inside_shell_are_finite_and_safe():
    assert not camera_visible((0, 5000, 140), (0, 7000, 140))
    assert not camera_visible((0, 0, 1999), (0, 0, 2000))
    assert camera_visible((0, 8000, 4000), (0, 4000, 4000))


def test_outside_camera_clears_surrounding_wall_above_the_player():
    # These upward rays miss the player box. The enclosing stand must still
    # disappear across the shot, instead of leaving a small hole in a wall.
    for sx in (-1, 1):
        for sy in (-1, 1):
            camera = (sx*7000, sy*5000, 1000)
            assert not camera_visible((sx*6000, sy*4800, 1100), camera)
    # Height alone must not turn the clearance sphere into an empty stadium.
    assert camera_visible((0, 4500, 1000), (0, 0, 12000))
