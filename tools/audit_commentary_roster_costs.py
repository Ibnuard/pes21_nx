#!/usr/bin/env python3
"""Read-only selected-roster bounds for the detached commentary batch.

Bounds are not rebuilt-bank sizes. Graph/AWB alignment overhead is additional;
this does not approve a short-call policy or change the native runtime limit.
"""
from __future__ import annotations

import argparse
from itertools import combinations
import json
from pathlib import Path
import re

from batch_player_commentary import (ACB_MEMBER, file_record, key, local_output,
                                     read, write)
from build_fl26_cup_catalog import cpk_member
from stage_indonesia_commentary import Utf, mobile_index

CAP = 8 * 1024 * 1024


def team_costs(plan, existing_names, *, short_p0=False):
    players = {row["native_player_id"]: row for row in plan["players"]}
    result = []
    for team in plan["teams"]:
        payloads, appends, calls, absent = {}, set(), 0, []
        for native in plan["rosters"][str(team["team_id"])]:
            row = players[native]
            selected = row.get("calls", [])
            if short_p0:
                selected = [call for call in selected if re.fullmatch(r"EN_(?:A1|B1)_P0_R\d{6}", call["source_cue"])]
                if row["status"] == "source_validated_pending_stage" and not selected:
                    absent.append(row["base_id"])
            for call in selected:
                payload = call["source_payload"]
                # Current v53 builder embeds one recording for each cue, even
                # if two contexts happen to have identical PCM/HCA content.
                # This also works before the serial decoder has read payloads.
                identity = call["native_cue"]
                if identity in payloads and payloads[identity] != payload["bytes"]:
                    raise ValueError("Conflicting payload hash/size")
                payloads[identity] = payload["bytes"]
                if call["native_cue"] not in existing_names:
                    appends.add(call["native_cue"])
                calls += 1
        result.append({"team_id": team["team_id"], "name": team.get("display_name"),
            "payloads": payloads, "appended_cues": appends, "source_cue_count": calls,
            "short_p0_missing_base_ids": absent})
    return result


def pair_extremes(teams, bank_bytes, bank_cues):
    worst_bytes, worst_cues = None, None
    overflowing_lower_bounds = 0
    for a, b in combinations(teams, 2):
        payloads = a["payloads"] | b["payloads"]
        additional = sum(payloads.values())
        appends = len(a["appended_cues"] | b["appended_cues"])
        row = {"team_ids": [a["team_id"], b["team_id"]],
               "team_names": [a["name"], b["name"]],
               "additional_recording_bytes_current_one_cue_one_wave_design": additional,
               "bank_bytes_lower_bound_before_graph_and_awb_overhead": bank_bytes + additional,
               "new_cue_names": appends, "result_cue_count": bank_cues + appends}
        if worst_bytes is None or additional > worst_bytes["additional_recording_bytes_current_one_cue_one_wave_design"]:
            worst_bytes = row
        if worst_cues is None or appends > worst_cues["new_cue_names"]:
            worst_cues = row
        if bank_bytes + additional + 48 > CAP or bank_cues + appends > 65535:
            overflowing_lower_bounds += 1
    return {"worst_payload_pair": worst_bytes, "worst_cue_count_pair": worst_cues,
            "pairs_already_over_cap_before_overhead": overflowing_lower_bounds,
            "pairs_examined": len(teams) * (len(teams) - 1) // 2}


def audit(config_path):
    config = read(config_path)
    work = local_output(config["work_dir"])
    pointer = read(work / "LATEST-PLAN.json")
    plan_path = Path(pointer["path"]).resolve()
    if not plan_path.is_relative_to(work / "plans") or file_record(plan_path)["sha256"] != pointer["sha256"]:
        raise ValueError("Current commentary plan proof changed")
    plan, accepted = read(plan_path), read(config["accepted_report"])
    index, base = mobile_index(Path(config["mobile_cpk"]))
    top = Utf(cpk_member(Path(config["mobile_cpk"]), index, base, ACB_MEMBER))
    names = {row["CueName"] for row in top.child("CueNameTable").rows}
    names.update(cue["cue"] for cue in accepted["cues"])
    report = {"input_key": plan["input_key"], "plan_sha256": pointer["sha256"],
        "accepted_bank_bytes": accepted["result_bytes"], "accepted_cue_count": accepted["result_cues"],
        "bank_and_delta_limit": CAP, "effective_result_limit_after_delta_header": CAP-48,
        "baseline_remaining_result_bytes": CAP-48-accepted["result_bytes"],
        "remaining_cue_indices": 65535-accepted["result_cues"],
        "scope": "distinct home/away teams from active catalog; same-team cases cannot be worse",
        "assumptions": ["preserve all accepted canary bytes and existing native graph",
                        "current one-cue/one-memory-wave builder; a new shared-wave graph would need separate proof",
                        "additional UTF/AWB/alignment overhead is not included",
                        "missing P0 contexts are reported, not substituted or accepted"],
        "all_available_source_variations": pair_extremes(team_costs(plan, names), accepted["result_bytes"], accepted["result_cues"]),
        "literal_short_p0_subset_diagnostic_only": pair_extremes(team_costs(plan, names, short_p0=True),
                                                                 accepted["result_bytes"], accepted["result_cues"]),
        "runtime_modified": False, "policy_approved": False, "runtime_accepted": False}
    report["short_p0_missing_players"] = sorted({base for team in team_costs(plan, names, short_p0=True)
                                                 for base in team["short_p0_missing_base_ids"]})
    report["report_key"] = key(report)
    output = work / "runtime-cost" / report["report_key"] / "REPORT.json"
    write(output, report)
    write(work / "ROSTER-COST-LATEST.json", {"path": str(output), "payload": file_record(output)})
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    audit(args.config)


if __name__ == "__main__":
    main()
