import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_batch_release import validation_path


def test_legacy_default_path_is_unchanged(tmp_path):
    path = tmp_path / 'content' / 'face.uasset'
    assert validation_path({}, path) == path


def test_alias_requires_same_physical_root_and_preserves_relative_asset(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    alias = root / '..' / 'root'
    config = dict(validation_canonical_root=str(root), validation_root_alias=str(alias))
    asset = root / 'Content' / 'Assets' / 'face.uasset'
    assert validation_path(config, asset) == alias / 'Content' / 'Assets' / 'face.uasset'
    with pytest.raises(ValueError, match='outside'):
        validation_path(config, tmp_path / 'other' / 'face.uasset')
    with pytest.raises(ValueError, match='same canonical'):
        validation_path(dict(config, validation_root_alias=str(tmp_path / 'different')), asset)
    with pytest.raises(ValueError, match='same canonical'):
        validation_path(dict(validation_root_alias=str(alias)), asset)
