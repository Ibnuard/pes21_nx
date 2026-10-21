from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_commentary_roster_costs import pair_extremes, team_costs


def test_pair_union_deduplicates_shared_players_and_exact_recordings():
    teams = [{"team_id": 1, "name": "one", "payloads": {"a": 100, "b": 50}, "appended_cues": {"A", "B"}},
             {"team_id": 2, "name": "two", "payloads": {"a": 100, "c": 80}, "appended_cues": {"A", "C"}},
             {"team_id": 3, "name": "three", "payloads": {}, "appended_cues": set()}]
    report = pair_extremes(teams, 1000, 64019)
    assert report["pairs_examined"] == 3
    assert report["worst_payload_pair"]["additional_recording_bytes_current_one_cue_one_wave_design"] == 230
    assert report["worst_cue_count_pair"]["new_cue_names"] == 3
    assert report["worst_payload_pair"]["bank_bytes_lower_bound_before_graph_and_awb_overhead"] == 1230


def test_short_p0_is_only_a_diagnostic_and_missing_owners_are_visible():
    plan = {"teams": [{"team_id": 1}], "rosters": {"1": [100, 101]}, "players": [
        {"native_player_id": 100, "base_id": 100, "status": "source_validated_pending_stage", "calls": [
            {"source_cue": "EN_A1_P0_R000100", "native_cue": "EN_A1_P0_R000100", "source_payload": {"sha256": "a", "bytes": 10}},
            {"source_cue": "EN_A1B1_PMB_R000100_01", "native_cue": "EN_A1B1_PMB_R000100_01", "source_payload": {"sha256": "b", "bytes": 900}}]},
        {"native_player_id": 101, "base_id": 101, "status": "source_validated_pending_stage", "calls": [
            {"source_cue": "EN_A1_P3_R000101", "native_cue": "EN_A1_P3_R000101", "source_payload": {"sha256": "c", "bytes": 20}}]}]}
    full = team_costs(plan, {"EN_A1_P0_R000100"})[0]
    short = team_costs(plan, {"EN_A1_P0_R000100"}, short_p0=True)[0]
    assert sum(full["payloads"].values()) == 930 and len(full["appended_cues"]) == 2
    assert short["payloads"] == {"EN_A1_P0_R000100": 10} and short["short_p0_missing_base_ids"] == [101]
