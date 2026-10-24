import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from realface_source_empty_part import source_part_proof


def test_explicit_extraction_root_still_rejects_wrong_owner(tmp_path):
    owner = dict(base_id=42, native_player_id=71, fingerprint='current')
    folder = tmp_path / '42'
    folder.mkdir()
    for field, wrong in (('base_id', 43), ('native_player_id', 72), ('fingerprint', 'old')):
        (folder / 'extraction.json').write_text(json.dumps(dict(owner, **{field: wrong})))
        with pytest.raises(ValueError, match='different identity'):
            source_part_proof({'source_input_root': str(tmp_path)}, owner)


def test_missing_extraction_never_establishes_invisibility(tmp_path):
    assert source_part_proof({'source_input_root': str(tmp_path)},
                             dict(base_id=42, native_player_id=71, fingerprint='current')) is None
