from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_pesdb_famous_teams_candidate as candidate  # noqa: E402


class OuterObbPackagingTests(unittest.TestCase):
    def test_slot_overflow_falls_back_to_repack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pesdb-outer-repack-") as value:
            root = Path(value)
            base = root / "base.obb"
            output = root / "candidate.obb"
            replacement = root / "dt120.cpk"
            base.write_bytes(b"base")
            replacement.write_bytes(b"replacement")
            replacements = {candidate.DT120_MEMBER: replacement}

            with (
                mock.patch.object(
                    candidate,
                    "patch_slots",
                    side_effect=ValueError("replacement needs 9; slot capacity 4"),
                ),
                mock.patch.object(
                    candidate,
                    "cpk_index",
                    return_value=({}, {candidate.DT120_MEMBER: {}}, 0),
                ),
                mock.patch.object(candidate.subprocess, "run") as run,
            ):
                mode, note = candidate.package_outer_obb(
                    base, output, replacements
                )

            self.assertEqual(mode, "repacked")
            self.assertIn("slot capacity", note or "")
            run.assert_called_once()
            manifest = json.loads(
                (root / "outer-replacement-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                manifest,
                {candidate.DT120_MEMBER: str(replacement.resolve())},
            )

    def test_non_capacity_patch_failure_does_not_repack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pesdb-outer-fail-") as value:
            root = Path(value)
            base = root / "base.obb"
            output = root / "candidate.obb"
            replacement = root / "dt120.cpk"
            base.write_bytes(b"base")
            replacement.write_bytes(b"replacement")

            with mock.patch.object(
                candidate,
                "patch_slots",
                side_effect=ValueError("nonzero bytes in proposed padding"),
            ):
                with self.assertRaisesRegex(ValueError, "nonzero bytes"):
                    candidate.package_outer_obb(
                        base,
                        output,
                        {candidate.DT120_MEMBER: replacement},
                    )

            self.assertFalse(
                (root / "outer-replacement-manifest.json").exists()
            )

    def test_repacked_validation_allows_offsets_but_not_payload_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pesdb-outer-validate-") as value:
            root = Path(value)
            base = root / "base.obb"
            output = root / "candidate.obb"
            replacement = root / "dt120.cpk"
            base.write_bytes(b"AAAABBBB")
            output.write_bytes(b"XXBBBB")
            replacement.write_bytes(b"XX")
            header = {"Align": 1, "Files": 2}
            old_rows = {
                "target": {
                    "FileOffset": 0,
                    "FileSize": 4,
                    "ExtractSize": 4,
                    "ID": 1,
                },
                "other": {
                    "FileOffset": 4,
                    "FileSize": 4,
                    "ExtractSize": 4,
                    "ID": 2,
                },
            }
            new_rows = {
                "target": {
                    "FileOffset": 0,
                    "FileSize": 2,
                    "ExtractSize": 2,
                    "ID": 1,
                },
                "other": {
                    "FileOffset": 2,
                    "FileSize": 4,
                    "ExtractSize": 4,
                    "ID": 2,
                },
            }

            def index(path: Path):
                return (
                    (header, old_rows, 0)
                    if path == base
                    else (header, new_rows, 0)
                )

            with mock.patch.object(candidate, "cpk_index", side_effect=index):
                report = candidate.validate_outer_obb(
                    base,
                    output,
                    {"target": replacement},
                    packaging_mode="repacked",
                )

            self.assertEqual(report["changed_members"], ["target"])
            self.assertEqual(
                report["metadata_changed_members"], ["other", "target"]
            )
            self.assertEqual(report["unrelated_members_byte_identical"], 1)
            self.assertEqual(report["size_delta"], -2)


class PesdbPlayerActivationTests(unittest.TestCase):
    def test_target_players_are_removed_from_delete_list(self) -> None:
        raw = b"".join(struct.pack("<I", value) for value in (10, 20, 30, 40))

        patched, report = candidate.activate_player_ids(raw, {20, 40, 50})

        values = [
            struct.unpack_from("<I", patched, offset)[0]
            for offset in range(0, len(patched), 4)
        ]
        self.assertEqual(values, [10, 30])
        self.assertEqual(report["required_active_players"], 3)
        self.assertEqual(report["already_active_players"], 1)
        self.assertEqual(report["delete_rows_removed"], 2)
        self.assertEqual(report["remaining_required_players_deleted"], 0)

    def test_duplicate_delete_rows_fail_closed(self) -> None:
        raw = struct.pack("<III", 10, 20, 20)
        with self.assertRaisesRegex(ValueError, "duplicate IDs"):
            candidate.activate_player_ids(raw, {20})


class AuthoritativeOverallRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.hooks = (ROOT / "source" / "ue4_hooks.c").read_text(encoding="utf-8")
        cls.makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    def test_authoritative_lookup_defaults_on_with_native_fallback(self) -> None:
        self.assertIn("PES_PESDB_AUTHORITATIVE_OVR ?= 1", self.makefile)
        start = self.hooks.index(
            "static uint32_t exhibition_player_overall(",
            self.hooks.index("#include \"exhibition_rosters_pesdb_generated.inc\""),
        )
        end = self.hooks.index("\n}\n", start) + 2
        wrapper = self.hooks[start:end]
        self.assertIn("const uint32_t native_overall =", wrapper)
        self.assertIn(
            "exhibition_get_player_overall(player, position, condition)",
            wrapper,
        )
        self.assertIn(
            "PES_PESDB_RUNTIME_ROSTERS && PES_PESDB_AUTHORITATIVE_OVR",
            wrapper,
        )
        self.assertIn("exhibition_find_pesdb_player_rating", wrapper)
        self.assertIn("return rating->overall;", wrapper)
        self.assertTrue(wrapper.rstrip().endswith("return native_overall;\n}"))

    def test_custom_gameplan_uses_scoped_overall_wrapper(self) -> None:
        self.assertEqual(self.hooks.count("exhibition_player_overall("), 4)
        self.assertIn(
            "entry->overall =\n          exhibition_player_overall(",
            self.hooks,
        )

    def test_selector_prefers_generated_team_ratings(self) -> None:
        signature = "static void main_menu_2p_team_selector_refresh_ratings(void)"
        start = self.hooks.index(signature, self.hooks.index(signature) + 1)
        end = self.hooks.index("\n}\n", start) + 2
        refresh = self.hooks[start:end]
        self.assertIn("exhibition_pesdb_team_rating(", refresh)
        self.assertLess(
            refresh.index("exhibition_pesdb_team_rating("),
            refresh.index("exhibition_get_position_overall"),
        )

    def test_native_picker_translates_logical_and_physical_team_ids(self) -> None:
        self.assertIn("exhibition_team_catalog_logical", self.hooks)
        self.assertIn(
            "exhibition_set_test_match_team_id(\n"
            "            exhibition_physical_team_raw(team_id));",
            self.hooks,
        )
        self.assertIn(
            "const uint32_t logical_team_id =\n"
            "      exhibition_logical_team_id(selected_team_id);",
            self.hooks,
        )

    def test_failed_custom_gameplan_rearms_hub_input(self) -> None:
        signature = "static int exhibition_gameplan_open_custom(void)"
        start = self.hooks.index(signature, self.hooks.index(signature) + 1)
        end = self.hooks.index("\n}\n", start) + 2
        opener = self.hooks[start:end]
        failure = opener[opener.index("if (!exhibition_gameplan_prepare_matchplan())") :]
        self.assertIn("main_menu_2p_prematch_hub_input_pending", failure)
        self.assertIn("main_menu_2p_prematch_hub_input_armed[0] = 0;", failure)

    def test_runtime_accepts_the_v6_barca_madrid_candidate_size(self) -> None:
        main = (ROOT / "source" / "main.c").read_text(encoding="utf-8")
        self.assertIn(
            "#define PATCH_OBB_PESDB_CANDIDATE_V6_KITS_SIZE 1391630336ULL",
            main,
        )
        self.assertIn(
            "actual_size == PATCH_OBB_PESDB_CANDIDATE_V6_KITS_SIZE",
            main,
        )


if __name__ == "__main__":
    unittest.main()
