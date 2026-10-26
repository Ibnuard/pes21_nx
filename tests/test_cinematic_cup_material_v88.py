"""The editor repair must never admit a runtime/source project or path alias."""
from pathlib import Path
import importlib.util
import os

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cup_material', ROOT / 'tools/cinematic_cup_material.py')
cup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cup)


def test_only_exact_ignored_project_is_admitted(tmp_path):
    repo = tmp_path / 'repo'
    expected = repo / 'local-debug' / 'cup-88' / 'PesMobile'
    assert cup.require_isolated_project(expected, expected, repo) == os.path.normcase(str(expected.resolve()))
    for actual in (repo / 'dist/pes21_nx', repo / 'source',
                   repo / 'local-debug-other/PesMobile',
                   repo / 'local-debug/cup-89/PesMobile',
                   expected / '../../../../../outside'):
        with pytest.raises(ValueError):
            cup.require_isolated_project(actual, expected, repo)
    with pytest.raises(ValueError):
        cup.require_isolated_project(repo / 'dist', repo / 'dist', repo)


def test_reparse_escape_is_resolved_before_admission(tmp_path):
    repo = tmp_path / 'repo'
    debug = repo / 'local-debug'
    debug.mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    alias = debug / 'alias'
    try:
        alias.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Directory symlink capability unavailable')
    with pytest.raises(ValueError):
        cup.require_isolated_project(alias, alias, repo)
