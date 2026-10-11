import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_skin_palette import lab


def test_srgb_reference_colors_and_invalid_channels():
    assert lab([0,0,0]) == pytest.approx([0,0,0], abs=.001)
    assert lab([255,255,255]) == pytest.approx([100,0,0], abs=.001)
    assert lab([255,0,0]) == pytest.approx([53.2408,80.0925,67.2032], abs=.001)
    for color in ([256,0,0], [float('nan'),0,0], [1,2]):
        with pytest.raises(ValueError):lab(color)
