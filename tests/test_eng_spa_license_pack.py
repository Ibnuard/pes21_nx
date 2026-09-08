"""Focused checks for the detached English/Spanish licensing pack."""

from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_eng_spa_license_pack import (  # noqa: E402
    ENGLISH_NAME_OFFSET,
    ENGLISH_NAME_SIZE,
    SHORT_CODE_OFFSETS,
    SHORT_CODE_SIZE,
    TEAM_ID_OFFSET,
    TEAM_RECORD_SIZE,
    content_id,
    encode_wesys,
    fixed_ascii,
    load_manifest,
    patch_team_rows,
)
from pesdb import decode_wesys  # noqa: E402


MANIFEST = ROOT / "data" / "eng_spa_license_overrides.json"
TOOL = ROOT / "tools" / "build_eng_spa_license_pack.py"
PES21_TEAM = ROOT / (
    "local-debug/efootball10-audit/compare/old_dt200_mobile_all.cpk/"
    "common/etc/pesdb/Team.bin"
)
FOOTBALL_LIFE_TEAM = (
    ROOT / "local-debug/licensing-eng-spa-audit/football-life-Team.bin"
)
FOOTBALL_LIFE_COMPETITION = ROOT / (
    "local-debug/licensing-eng-spa-audit/football-life-CompetitionEntry.bin"
)
FOOTBALL_LIFE_ROOT = (
    Path(os.environ["PESNX_FOOTBALL_LIFE_ROOT"])
    if os.environ.get("PESNX_FOOTBALL_LIFE_ROOT")
    else None
)


def make_team_row(team_id: int, name: str, code_a: str, code_b: str) -> bytes:
    row = bytearray(TEAM_RECORD_SIZE)
    struct.pack_into("<I", row, TEAM_ID_OFFSET, team_id)
    for offset, size, value in (
        (ENGLISH_NAME_OFFSET, ENGLISH_NAME_SIZE, name),
        (SHORT_CODE_OFFSETS[0], SHORT_CODE_SIZE, code_a),
        (SHORT_CODE_OFFSETS[1], SHORT_CODE_SIZE, code_b),
    ):
        encoded = value.encode("ascii")
        row[offset : offset + size] = encoded + bytes(size - len(encoded))
    return bytes(row)


class EngSpaLicenseManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.manifest, cls.teams = load_manifest(MANIFEST)
        cls.by_id = {int(team["team_id"]): team for team in cls.teams}

    def test_manifest_has_two_complete_leagues_and_ascii_names(self) -> None:
        self.assertEqual(len(self.raw_manifest["leagues"]), 2)
        self.assertEqual(
            [len(league["teams"]) for league in self.raw_manifest["leagues"]],
            [20, 20],
        )
        self.assertEqual(len(self.teams), 40)
        self.assertEqual(len(self.by_id), 40)
        self.assertTrue(
            all(
                str(team["official_name"]).isascii()
                and str(team["short_code"]).isascii()
                for team in self.teams
            )
        )
        self.assertEqual(
            self.manifest["content_id"], content_id(self.raw_manifest)
        )

    def test_official_name_sentinels_and_sunderland_gate(self) -> None:
        self.assertEqual(self.by_id[102]["official_name"], "Chelsea FC")
        self.assertEqual(self.by_id[103]["official_name"], "Liverpool FC")
        self.assertEqual(self.by_id[109]["official_name"], "Real Madrid CF")
        self.assertEqual(self.by_id[172]["official_name"], "Atletico Madrid")
        self.assertEqual(self.by_id[389]["short_code"], "FOR")
        pending = [
            team
            for team in self.teams
            if team["team_bin_policy"] == "pending_team_record"
        ]
        self.assertEqual([team["team_id"] for team in pending], [396])
        self.assertEqual(pending[0]["official_name"], "Sunderland AFC")
        self.assertEqual(pending[0]["catalog_integration"], "pending")

    def test_manifest_forbids_premature_runtime_and_pc_texture_use(self) -> None:
        policy = self.raw_manifest["policy"]
        self.assertFalse(policy["runtime_integration"])
        self.assertTrue(policy["patch_existing_team_rows_only"])
        self.assertFalse(policy["direct_pc_ftex_transplant"])
        self.assertTrue(policy["requires_mobile_cooked_texture_template"])
        self.assertFalse(policy["cpk_repacker_can_add_members"])

    def test_patch_changes_only_approved_fields(self) -> None:
        source_rows = [
            make_team_row(100, "MANCHESTER RED", "MUN", "MNR"),
            make_team_row(109, "MADRID CHAMARTIN B", "RMA", "MDC"),
            make_team_row(999, "UNRELATED", "ZZZ", "ZZZ"),
        ]
        targets = [
            {
                **self.by_id[100],
                "team_bin_policy": "patch_existing",
            },
            {
                **self.by_id[109],
                "team_bin_policy": "patch_existing",
            },
            {
                **self.by_id[396],
                "team_bin_policy": "pending_team_record",
            },
        ]
        patched, report = patch_team_rows(b"".join(source_rows), targets)
        patched_rows = [
            patched[offset : offset + TEAM_RECORD_SIZE]
            for offset in range(0, len(patched), TEAM_RECORD_SIZE)
        ]
        allowed = set(range(ENGLISH_NAME_OFFSET, ENGLISH_NAME_OFFSET + ENGLISH_NAME_SIZE))
        for offset in SHORT_CODE_OFFSETS:
            allowed.update(range(offset, offset + SHORT_CODE_SIZE))
        for before, after in zip(source_rows[:2], patched_rows[:2]):
            self.assertTrue(
                all(
                    index in allowed
                    for index, (left, right) in enumerate(zip(before, after))
                    if left != right
                )
            )
        self.assertEqual(source_rows[2], patched_rows[2])
        self.assertEqual(report["records_before"], report["records_after"])
        self.assertEqual(report["unrelated_rows_byte_identical"], 1)
        self.assertEqual(report["pending_missing_team_ids"], [396])
        self.assertEqual(
            fixed_ascii(patched_rows[0], ENGLISH_NAME_OFFSET, ENGLISH_NAME_SIZE),
            "Manchester United",
        )
        self.assertEqual(
            fixed_ascii(patched_rows[1], SHORT_CODE_OFFSETS[1], SHORT_CODE_SIZE),
            "RMA",
        )

    def test_wesys_encoder_round_trips(self) -> None:
        raw = make_team_row(100, "Manchester United", "MUN", "MUN")
        with tempfile.TemporaryDirectory(prefix="eng-spa-wesys-") as temporary:
            path = Path(temporary) / "Team.bin"
            path.write_bytes(encode_wesys(raw))
            self.assertEqual(decode_wesys(path), raw)


@unittest.skipUnless(
    PES21_TEAM.is_file()
    and FOOTBALL_LIFE_TEAM.is_file()
    and FOOTBALL_LIFE_COMPETITION.is_file(),
    "local PES21/Football Life audit tables are unavailable",
)
class EngSpaLicensePackIntegrationTests(unittest.TestCase):
    def test_data_only_pack_and_check_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eng-spa-license-") as temporary:
            output = Path(temporary) / "pack"
            command = [
                sys.executable,
                str(TOOL),
                "--root",
                str(ROOT),
                "--manifest",
                str(MANIFEST),
                "--pes21-team",
                str(PES21_TEAM),
                "--football-life-team",
                str(FOOTBALL_LIFE_TEAM),
                "--football-life-competition-entry",
                str(FOOTBALL_LIFE_COMPETITION),
                "--output-dir",
                str(output),
            ]
            if FOOTBALL_LIFE_ROOT is not None and FOOTBALL_LIFE_ROOT.is_dir():
                command.extend(["--football-life-root", str(FOOTBALL_LIFE_ROOT)])
            subprocess.run(
                command,
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            subprocess.run(
                [*command, "--check"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            report = json.loads(
                (output / "validation-report.json").read_text(encoding="utf-8")
            )
            overrides = json.loads(
                (output / "selector-name-overrides.json").read_text(
                    encoding="utf-8"
                )
            )
            kit_manifest = json.loads(
                (output / "kit-source-manifest.json").read_text(encoding="utf-8")
            )
            self.assertFalse(report["runtime_integration"])
            self.assertEqual(report["team_patch"]["records_before"], 736)
            self.assertEqual(report["team_patch"]["records_after"], 736)
            self.assertEqual(report["team_patch"]["patched_team_rows"], 39)
            self.assertEqual(
                report["team_patch"]["unrelated_rows_byte_identical"], 697
            )
            self.assertEqual(
                report["team_patch"]["pending_missing_team_ids"], [396]
            )
            self.assertEqual(
                report["source"]["football_life_competition_entry"][
                    "verified_target_teams"
                ],
                40,
            )
            self.assertEqual(len(overrides["teams"]), 40)
            self.assertFalse(overrides["runtime_integration"])
            self.assertEqual(
                {row["team_id"] for row in overrides["teams"] if row["catalog_integration"] == "pending"},
                {396},
            )
            self.assertEqual(kit_manifest["counts"]["teams"], 40)
            if FOOTBALL_LIFE_ROOT is not None and FOOTBALL_LIFE_ROOT.is_dir():
                self.assertEqual(
                    kit_manifest["counts"]["descriptor_complete_teams"], 40
                )
                self.assertEqual(
                    kit_manifest["counts"]["texture_complete_teams"], 40
                )
                by_id = {
                    int(row["team_id"]): row for row in kit_manifest["teams"]
                }
                self.assertEqual(
                    by_id[102]["kits"]["1st"]["descriptor"]["archive"],
                    "season_c",
                )
                base_texture = next(
                    row
                    for row in by_id[102]["kits"]["1st"]["texture_members"]
                    if row["member"].lower().endswith("u0102p1.ftex")
                )
                self.assertEqual(base_texture["archive"], "season_a")
                self.assertEqual(
                    by_id[396]["mobile_template"]["status"],
                    "generic_or_missing",
                )

            patched_raw = decode_wesys(output / "Team.bin")
            source_raw = decode_wesys(PES21_TEAM)
            self.assertEqual(len(patched_raw), len(source_raw))
            rows = {
                struct.unpack_from("<I", patched_raw, offset + TEAM_ID_OFFSET)[0]:
                patched_raw[offset : offset + TEAM_RECORD_SIZE]
                for offset in range(0, len(patched_raw), TEAM_RECORD_SIZE)
            }
            self.assertNotIn(396, rows)
            self.assertEqual(
                fixed_ascii(rows[102], ENGLISH_NAME_OFFSET, ENGLISH_NAME_SIZE),
                "Chelsea FC",
            )
            self.assertEqual(
                fixed_ascii(rows[109], ENGLISH_NAME_OFFSET, ENGLISH_NAME_SIZE),
                "Real Madrid CF",
            )


if __name__ == "__main__":
    unittest.main()
