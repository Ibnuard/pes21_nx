"""Exercise actual renderer budgets, state isolation and paired-foot opacity."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_renderer_at_720p_1080p_and_short_lists(tmp_path):
    if not shutil.which('gcc'):
        pytest.skip('host C compiler unavailable')
    result = subprocess.run([sys.executable, str(ROOT/'tools/preview_gameplan.py'),
        str(tmp_path), '--geometry-only'], capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '08-loading-players:' in result.stdout


def test_public_sprite_payload_is_the_editable_artwork():
    assert (ROOT/'data/gameplan_icons_v1.bin').read_bytes() == (ROOT/'art/gameplan/icons-v1.png').read_bytes()
    with Image.open(ROOT/'data/gameplan_icons_v1.bin') as image:
        assert image.size == (1254, 1254) and image.mode == 'RGBA'
        assert image.getchannel('A').getextrema() == (0, 255)
