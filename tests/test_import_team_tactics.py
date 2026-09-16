import json
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from import_team_tactics import convert_team
from generate_pesdb_runtime_rosters import _choose_balanced_xi_with_score
from pes21_player_migration import patch_canary_formation_roles, table_raw
from convert_efootball10_players import encode_pes21_wesys


def test_missing_preferred_player_uses_natural_role_before_rating():
    roles = [0, 1, 1, 3, 2, 4, 5, 8, 10, 9, 12]
    players = [(100+i, 60, role) for i, role in enumerate(roles)]
    players.append((999, 99, 8, tuple(2 if i in (8, 12) else 0 for i in range(13))))
    preferred = [100+i for i in range(11)]
    preferred[10] = 123456  # API striker absent from our locked roster.
    xi, bench, _ = _choose_balanced_xi_with_score(players, roles, preferred)
    assert players[xi[10]][0] == 110
    assert len(set(xi)) == 11
    assert sorted(xi + bench) == list(range(len(players)))


def test_import_rejects_duplicate_slots():
    import pytest
    payload = {'data': {'pes_id': 108, 'english_name': 'Test',
        'player_assignments': [], 'tactics': [{'strategy_type': 0, 'formations': []}]}}
    with pytest.raises(ValueError, match='slots 0..10'):
        convert_team(payload)


def test_available_api_starter_keeps_exact_slot_despite_registered_role():
    roles = [0,1,1,3,2,4,5,5,10,9,12]
    players = [(100+i, 80, role) for i, role in enumerate(roles)]
    # Website asks for an AMF at CMF and a LWF at CF. Preserve those assignments.
    players.extend([(200, 70, 8), (201, 70, 9)])
    preferred = [100+i for i in range(11)]
    preferred[6], preferred[10] = 200, 201
    xi, _, _ = _choose_balanced_xi_with_score(players, roles, preferred)
    assert [players[i][0] for i in xi] == preferred


def test_native_coordinates_and_roles_update_both_strategies_by_encoded_slot():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tactics = b''.join(struct.pack('<III', tid, 108, 0) for tid in (100, 101))
        # Deliberately reverse physical row order: the encoded slot is authoritative.
        rows = b''.join(struct.pack('<III', tid, 7, (phase << 20) | (slot << 16) | (88 << 8) | 29)
                        for tid in (100, 101) for phase in range(3) for slot in reversed(range(11)))
        (root/'Tactics.bin').write_bytes(encode_pes21_wesys(tactics))
        (root/'TacticsFormation.bin').write_bytes(encode_pes21_wesys(rows))
        coords = [[3+i*4, 10+i*8] for i in range(11)]
        roles = [0,1,1,3,2,4,5,8,10,9,12]
        patch_canary_formation_roles([{'physical_team_id':108,
            'native_formation_roles':[7]*11, 'formation_roles':roles,
            'formation_coordinates':coords}], root, root/'patched.bin')
        output = table_raw(root/'patched.bin')
        for offset in range(0, len(output), 12):
            tid, role, packed = struct.unpack_from('<III', output, offset)
            slot = (packed >> 16) & 15
            assert role == roles[slot]
            assert [packed & 255, (packed >> 8) & 255] == coords[slot]
            assert output[offset+10:offset+12] == rows[offset+10:offset+12]
