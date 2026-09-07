"""Validation for the detachable Inter Miami release-base merge."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "build_inter_miami_release_experiment.py"
CURRENT_CPK = ROOT / "local-debug" / "inter-miami-runtime-base" / "dt200-current.cpk"
CURRENT_DT210 = ROOT / "local-debug" / "visual-v8-20260831" / "cpk-work" / "dt210-score.cpk"
CURRENT_DT240 = ROOT / "local-debug" / "efootball10-audit" / "old-cpk" / "dt240_mobile_all.cpk"
CURRENT_DT241 = ROOT / "local-debug" / "efootball10-all-teams-patch" / "dt241_mobile_all_ef10_all_teams.cpk"
PORTRAIT_DIR = ROOT / "local-debug" / "inter-miami-portraits" / "q128"
FULL_ARTIFACT = ROOT / "local-debug" / "efootball10-original-inter-miami-full"
RELEASE_OBB = ROOT / (
    "local-debug/inter-miami-runtime-base/patch.pre-inter-miami.obb"
)
EF10_ASSIGNMENTS = (
    ROOT
    / "local-debug/efootball10-audit/tables/common/etc/pesdb/PlayerAssignment.bin"
)
EF10_CATEGORIES = (
    ROOT
    / "local-debug/efootball10-audit/tables/common/etc/pesdb/CategoryTeamList.bin"
)


def inputs_available() -> bool:
    return all(
        path.is_file()
        for path in (
            CURRENT_CPK,
            CURRENT_DT210,
            CURRENT_DT240,
            CURRENT_DT241,
            PORTRAIT_DIR / "7511.png",
            FULL_ARTIFACT / "Player.bin",
            FULL_ARTIFACT / "validation-report.json",
            EF10_ASSIGNMENTS,
            EF10_CATEGORIES,
            RELEASE_OBB,
        )
    )


class InterMiamiReleaseExperimentTests(unittest.TestCase):
    def test_runtime_team_alias_is_stable_with_compile_time_rollback(self):
        hooks = (ROOT / "source" / "ue4_hooks.c").read_text(encoding="utf-8")
        header = (ROOT / "source" / "experimental_inter_miami.h").read_text(
            encoding="utf-8"
        )
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("PES_EXPERIMENT_INTER_MIAMI ?= 1", makefile)
        self.assertIn(
            "-DPES_EXPERIMENT_INTER_MIAMI=$(PES_EXPERIMENT_INTER_MIAMI)",
            makefile,
        )
        self.assertIn("#define PES_EXPERIMENT_INTER_MIAMI 1", header)
        self.assertIn("EXHIBITION_INTER_MIAMI_LOGICAL_TEAM_ID 5738u", header)
        self.assertIn("EXHIBITION_INTER_MIAMI_PHYSICAL_TEAM_ID 2473u", header)
        self.assertIn("EXHIBITION_INTER_MIAMI_EF10_CATEGORY_ID 603u", header)
        self.assertIn("EXHIBITION_INTER_MIAMI_BADGE_SLOT 502u", header)
        self.assertIn("EXHIBITION_INTER_MIAMI_CATEGORY_BADGE_SLOT 496u", header)
        self.assertIn('"N AMERICA CLUBS"', header)
        self.assertIn('"NAM"', header)
        self.assertNotIn('"EXPERIMENTAL CLUBS"', header)
        self.assertIn("MAIN_MENU_2P_INTER_MIAMI_CATEGORY_INDEX 25u", hooks)
        roster = re.search(
            r"experimental_inter_miami_players\[\] = \{(.*?)\n\};",
            header,
            re.DOTALL,
        ).group(1)
        shirts = re.search(
            r"experimental_inter_miami_shirts\[\] = \{(.*?)\n\};",
            header,
            re.DOTALL,
        ).group(1)
        player_ids = [int(value) for value in re.findall(r"(\d+)u", roster)]
        shirt_numbers = [int(value) for value in re.findall(r"(\d+)u", shirts)]
        self.assertEqual(len(player_ids), 27)
        self.assertEqual(len(shirt_numbers), 27)
        self.assertEqual(player_ids[0], 34430)
        self.assertEqual(shirt_numbers[0], 18)
        self.assertEqual(player_ids[11], 135359)
        self.assertIn("experimental_inter_miami_portrait_id(id)", hooks)
        self.assertIn("return 141552u;", header)
        self.assertIn("exhibition_physical_team_raw", hooks)
        self.assertIn("exhibition_native_team_id(home_raw)", hooks)
        self.assertIn("exhibition_native_team_id(away_raw)", hooks)
        self.assertNotIn("const uint32_t home_team_id = home_raw << 14", hooks)
        self.assertNotIn("const uint32_t away_team_id = away_raw << 14", hooks)
        self.assertIn('return "INTER MIAMI CF";', hooks)

    def test_preflight_uses_current_release_base_and_full_roster(self):
        if not inputs_available():
            self.skipTest("local Inter Miami release inputs are unavailable")
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--check"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        merge = payload["preflight"]["player_merge"]
        cleanup = payload["preflight"]["assignment_cleanup"]
        league = payload["preflight"]["league_membership"]
        self.assertEqual(payload["check"], "pass")
        self.assertEqual(merge["records_before"], merge["records_after"])
        self.assertEqual(merge["direct_rows_replaced"], 8)
        self.assertEqual(merge["donor_rows_replaced"], 19)
        self.assertEqual(merge["unrelated_rows_byte_identical"], 43047)
        self.assertEqual(payload["preflight"]["artifact_mode"], "full")
        self.assertEqual(cleanup["physical_roster_replaced"], 25)
        self.assertEqual(cleanup["inter_miami_memberships_added"], 27)
        self.assertEqual(cleanup["legacy_club_memberships_removed"], 7)
        self.assertEqual(cleanup["national_memberships_preserved"], 3)
        self.assertEqual(
            {(row["player_id"], row["team_id"]) for row in cleanup["removed"]},
            {
                (7511, 108),
                (34881, 172),
                (38568, 108),
                (40425, 108),
                (109842, 1256),
                (118960, 2722),
                (127201, 1239),
            },
        )
        self.assertEqual(
            {(row["player_id"], row["team_id"]) for row in cleanup["preserved_national"]},
            {(7511, 50), (34881, 49), (38568, 7)},
        )
        self.assertEqual(league["ef10_category_id"], 603)
        self.assertEqual(league["selector_label"], "N AMERICA CLUBS")
        self.assertEqual(league["source_order"], 541)
        self.assertEqual(
            payload["preflight"]["team_patch"]["old_name"], "PUNTIHUERVA"
        )
        self.assertEqual(
            payload["preflight"]["team_patch"]["new_name"], "INTER MIAMI CF"
        )
        self.assertEqual(
            payload["preflight"]["current_cpk_sha256"],
            payload["preflight"]["release_obb"]["slots"]
            ["Expansion/dt200_mobile_all.cpk"]["sha256"],
        )
        self.assertEqual(
            payload["preflight"]["current_dt240_sha256"],
            payload["preflight"]["release_obb"]["slots"]
            ["Expansion/dt240_mobile_all.cpk"]["sha256"],
        )
        self.assertEqual(payload["preflight"]["latest_scoreboard_size"], 359266514)
        self.assertEqual(payload["preflight"]["ef10_portraits"]["count"], 27)
        self.assertEqual(
            payload["preflight"]["latest_scoreboard_sha256"],
            "65b58eabce8eb7eabef18fa2837acaece24ba78d39dc54805526b7a0caccd5c4",
        )

    def test_rebuilt_cpks_change_only_inter_miami_resources(self):
        if not inputs_available():
            self.skipTest("local Inter Miami release inputs are unavailable")
        with tempfile.TemporaryDirectory(prefix="inter-miami-merge-") as temporary:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--output-dir",
                    temporary,
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout[completed.stdout.index("{") :])
            dt200 = payload["outputs"]["dt200"]
            dt240 = payload["outputs"]["dt240"]
            dt210 = payload["outputs"]["dt210"]
            dt241 = payload["outputs"]["dt241"]
            self.assertEqual(dt200["member_count"], 2435)
            self.assertEqual(dt200["unrelated_members_byte_identical"], 2427)
            self.assertEqual(
                dt200["changed_members"],
                [
                    "common/etc/pesdb/InstallVersionPlayer.bin",
                    "common/etc/pesdb/Player.bin",
                    "common/etc/pesdb/PlayerAssignment.bin",
                    "common/etc/pesdb/PlayerDeleteList.bin",
                    "common/etc/pesdb/Team.bin",
                    "common/etc/uniform/team/2473/2473_DEF_1st.bin",
                    "common/etc/uniform/team/2473/2473_DEF_2nd.bin",
                    "common/etc/uniform/team/2473/2473_DEF_GK1st.bin",
                ],
            )
            self.assertLessEqual(
                dt200["size"],
                payload["preflight"]["release_obb"]["slots"]
                ["Expansion/dt200_mobile_all.cpk"]["size"],
            )
            self.assertEqual(dt240["member_count"], 6550)
            self.assertEqual(dt240["unrelated_members_byte_identical"], 6547)
            self.assertEqual(
                dt240["changed_members"],
                [
                    "common/render/symbol/flag/e_002473_f.png",
                    "common/render/symbol/flag/e_002473_f_l.png",
                    "common/render/symbol/flag/e_002473_f_s.png",
                ],
            )
            self.assertEqual(dt210["member_count"], 422)
            self.assertEqual(dt210["sha256"], "65b58eabce8eb7eabef18fa2837acaece24ba78d39dc54805526b7a0caccd5c4")
            self.assertEqual(dt241["member_count"], 28119)
            self.assertEqual(len(dt241["changed_members"]), 27)
            self.assertLessEqual(
                dt241["size"],
                payload["preflight"]["release_obb"]["slots"]
                ["Expansion/dt241_mobile_all.cpk"]["size"],
            )
            self.assertFalse(payload["stable_release_files_overwritten"])
            self.assertIsNone(payload["outputs"]["obb"])

    def test_packaging_patches_all_four_slots_and_validates_outer_obb(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("patch_slots(", source)
        self.assertIn("OBB_DT200_MEMBER: output_cpk", source)
        self.assertIn("OBB_DT210_MEMBER: current_dt210", source)
        self.assertIn("OBB_DT240_MEMBER: output_dt240", source)
        self.assertIn("OBB_DT241_MEMBER: output_dt241", source)
        self.assertIn("OBB_DT210_MEMBER", source)
        self.assertIn("OBB_DT241_MEMBER", source)
        self.assertIn("validate_patched_obb(", source)


if __name__ == "__main__":
    unittest.main()
