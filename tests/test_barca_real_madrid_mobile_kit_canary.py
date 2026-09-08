"""Focused checks for the detached Barcelona/Real Madrid kit canary."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_barca_real_madrid_mobile_kit_canary import (  # noqa: E402
    decode_wesys_payload,
    index_cpk,
    read_indexed,
)
from PIL import Image  # noqa: E402


MANIFEST = ROOT / "data/barca_real_madrid_mobile_kit_canary.json"
TOOL = ROOT / "tools/build_barca_real_madrid_mobile_kit_canary.py"
BASE_DT120 = ROOT / "local-debug/real-madrid-mobile-kit-canary/mobile-source/dt120_mobile_all.cpk"
BASE_DT200 = ROOT / "local-debug/pesdb-famous-teams-candidate-v5/base-dt200_mobile_all.cpk"
PC_REFERENCE = ROOT / "local-debug/real-madrid-mobile-kit-canary/pc-edit-reference"
MOBILE_REFERENCE = ROOT / "local-debug/real-madrid-mobile-kit-canary/mobile-edit-reference"
FOOTBALL_LIFE_ROOT = Path("D:/Games/SP Football Life 2026")


def _inputs_available() -> bool:
    return all(
        path.exists()
        for path in (
            MANIFEST,
            TOOL,
            BASE_DT120,
            BASE_DT200,
            PC_REFERENCE,
            MOBILE_REFERENCE,
            FOOTBALL_LIFE_ROOT,
        )
    )


def _member_names(source: dict) -> set[str]:
    return {entry["name"] for entry in source["rows"].values()}


def _read_all(source: dict, names: set[str]) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with source["path"].open("rb") as stream:
        for name in names:
            entry = source["rows"].get(name.lower())
            if entry is None:
                raise KeyError(name)
            row = entry["row"]
            if int(row["FileSize"]) != int(row["ExtractSize"]):
                raise ValueError(f"compressed CPK member is unsupported: {name}")
            stream.seek(source["data_base"] + int(row["FileOffset"]))
            payload = stream.read(int(row["FileSize"]))
            if len(payload) != int(row["FileSize"]):
                raise ValueError(f"truncated CPK member: {name}")
            result[name] = payload
    return result


class BarcaRealMadridManifestTests(unittest.TestCase):
    def test_manifest_contract(self) -> None:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(
            [team["team_id"] for team in payload["teams"]], [108, 109]
        )
        self.assertEqual(
            [
                [kit["suffix"] for kit in team["kits"]]
                for team in payload["teams"]
            ],
            [["p1", "p2", "g1"], ["p1", "p2", "g1"]],
        )
        self.assertFalse(payload["policy"]["runtime_integration"])
        self.assertFalse(payload["policy"]["stable_dist_overwrite"])
        self.assertTrue(payload["policy"]["allow_cpk_member_addition"])
        self.assertEqual(
            payload["licensing"]["team_source_policy"],
            "extract_from_selected_dt200",
        )
        self.assertEqual(
            payload["pes21_mobile"]["dt120_source_sha256"],
            "e5c53b21dcfb4aa1db8cf4f01ec932ea8b3b250120728cb347c6902873286c31",
        )
        self.assertEqual(
            payload["pes21_mobile"]["dt200_source_sha256"],
            "f7fce4ceb9e6092f0b66effe4664f0835c7a18b4f649a98dafe81fe42171c996",
        )
        transform = payload["atlas_transform"]
        self.assertEqual(transform["source_size"], [2048, 2048])
        self.assertEqual(transform["target_size"], [256, 384])
        self.assertIsNone(transform["crop"])
        self.assertFalse(transform["part_reordering"])

    def test_new_candidate_base_has_a_separate_explicit_gate(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOL), "--help"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertIn("--allow-base-drift", result.stdout)
        self.assertIn("--allow-source-drift", result.stdout)


@unittest.skipUnless(_inputs_available(), "local Football Life/canary inputs are unavailable")
class BarcaRealMadridIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="barca-madrid-canary-")
        cls.output = Path(cls.temporary.name) / "generated"
        command = [
            sys.executable,
            str(TOOL),
            "--root",
            str(ROOT),
            "--output-dir",
            str(cls.output),
            "--package-cpks",
        ]
        subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        cls.report = json.loads(
            (cls.output / "canary-report.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_all_converted_assets_have_mobile_shapes(self) -> None:
        payload_dir = self.output / "payloads/dt120"
        for path in sorted(payload_dir.glob("*.png")):
            with Image.open(path) as image:
                if path.name.endswith("_back.png"):
                    self.assertEqual(image.size, (320, 40), path.name)
                    self.assertEqual(image.mode, "RGBA", path.name)
                else:
                    self.assertEqual(image.size, (256, 384), path.name)
                    self.assertEqual(image.mode, "P", path.name)
                    self.assertLessEqual(len(image.getcolors(maxcolors=257) or []), 256)
        self.assertEqual(len(list(payload_dir.glob("*.png"))), 12)

    def test_only_canary_team_rows_and_madrid_license_flag_change(self) -> None:
        base = index_cpk(BASE_DT200, "base", 0)
        candidate = index_cpk(self.output / "dt200_barca_real_madrid_canary.cpk", "candidate", 0)
        base_raw, _ = decode_wesys_payload(
            read_indexed(base, "common/etc/pesdb/Team.bin"), "base Team.bin"
        )
        candidate_raw, _ = decode_wesys_payload(
            read_indexed(candidate, "common/etc/pesdb/Team.bin"),
            "candidate Team.bin",
        )
        changed_ids: list[int] = []
        for offset in range(0, len(base_raw), 1532):
            before = base_raw[offset : offset + 1532]
            after = candidate_raw[offset : offset + 1532]
            if before != after:
                changed_ids.append(struct.unpack_from("<I", before, 8)[0])
        self.assertEqual(changed_ids, [108, 109])
        rows = {
            struct.unpack_from("<I", candidate_raw, offset + 8)[0]:
            candidate_raw[offset : offset + 1532]
            for offset in range(0, len(candidate_raw), 1532)
        }
        row108 = rows[108]
        row109 = rows[109]
        self.assertEqual(row108[84], 15)
        self.assertEqual(row109[84], 15)
        self.assertEqual(
            row109[368:438].split(b"\0", 1)[0], b"Real Madrid CF"
        )
        self.assertEqual(self.report["licensing"]["team_patch"]["unrelated_rows_byte_identical"], 734)

    def test_detached_cpk_preserves_all_unrelated_members(self) -> None:
        targets = {
            "Models/character/Uniform16/D/u0108g1.png",
            "Models/character/Uniform16/D/u0108p1.png",
            "Models/character/Uniform16/D/u0108p2.png",
            "Models/character/Uniform16/D/u0109g1.png",
            "Models/character/Uniform16/D/u0109p1.png",
            "Models/character/Uniform16/D/u0109p2.png",
            "Models/character/Uniform16/Font/u0108g1_back.png",
            "Models/character/Uniform16/Font/u0108p1_back.png",
            "Models/character/Uniform16/Font/u0108p2_back.png",
            "Models/character/Uniform16/Font/u0109g1_back.png",
            "Models/character/Uniform16/Font/u0109p1_back.png",
            "Models/character/Uniform16/Font/u0109p2_back.png",
        }
        base = index_cpk(BASE_DT120, "base", 0)
        candidate = index_cpk(self.output / "dt120_barca_real_madrid_canary.cpk", "candidate", 0)
        old_names = _member_names(base)
        new_names = _member_names(candidate)
        self.assertEqual(new_names, old_names | {
            name for name in targets if name not in old_names
        })
        common = old_names - targets
        old_payloads = _read_all(base, common)
        new_payloads = _read_all(candidate, common)
        self.assertEqual(old_payloads, new_payloads)
        self.assertEqual(
            self.report["cpks"]["dt120"]["unrelated_members_byte_identical"],
            len(common),
        )
        self.assertEqual(
            self.report["cpks"]["dt200"]["unrelated_members_byte_identical"],
            2431,
        )


if __name__ == "__main__":
    unittest.main()
