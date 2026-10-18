"""Reject native overrides, traversal, duplicate or mixed stadium packages."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_stadium_package_scope import inspect_names


def test_native_named_material_is_safe_only_within_the_addon_namespace():
    assert inspect_names(['PesMobile/Content/FootballNX/Stadiums/CampNou/M_st029_b.uasset'])['passed']
    assert not inspect_names(['PesMobile/Content/Assets/bg_lighting_AM1/Meshes/st029_b.uasset'])['passed']


@pytest.mark.parametrize('names', [
    [], ['PesMobile/Content/FootballNX/Stadiums/CampNou/../../Assets/st029_b.uasset'],
    ['PesMobile/Content/FootballNX/Stadiums/CampNou/A.ini'],
    ['PesMobile/Content/FootballNX/Stadiums/CampNou/A.uasset',
     'PesMobile/Content/FootballNX/Stadiums/CampNou/a.uasset'],
    ['PesMobile/Content/FootballNX/Stadiums/CampNou/A.uasset',
     'PesMobile/Content/FootballNX/Stadiums/Anfield/B.uasset'],
])
def test_ambiguous_or_out_of_scope_payloads_fail(names):
    assert not inspect_names(names)['passed']
