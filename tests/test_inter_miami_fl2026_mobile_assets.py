import io
import json
import struct
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_barca_real_madrid_mobile_kit_canary import (  # noqa: E402
    cpk_inventory,
    decode_wesys_payload,
    descriptor_texture_names,
)
from build_pesdb_famous_teams_candidate import member_payload  # noqa: E402


MANIFEST = ROOT / "data/inter_miami_fl2026_mobile_kit_override.json"
CANDIDATE = ROOT / "local-debug/inter-miami-fl2026-kits-native-crests-v1"
BASE_OBB = (
    ROOT
    / "local-debug/ef10-native-names-native-input-probe-v1/"
    "patch.305030001.jp.nyan2021.pesam.obb"
)


class InterMiamiMappingTests(unittest.TestCase):
    def test_football_life_id_maps_to_existing_mobile_slot(self):
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        team = payload["leagues"][0]["teams"][0]
        self.assertEqual(team["team_id"], 2473)
        self.assertEqual(team["source_team_id"], 5738)
        self.assertEqual(team["official_name"], "INTER MIAMI CF")


@unittest.skipUnless(
    (CANDIDATE / "validation-report.json").is_file(),
    "local proprietary Inter Miami candidate is unavailable",
)
class PackagedInterMiamiAssetsTests(unittest.TestCase):
    def test_real_kit_flag_name_and_descriptors(self):
        dt200 = CANDIDATE / "dt200-original-order.cpk"
        team_member = "common/etc/pesdb/Team.bin"
        raw = decode_wesys_payload(member_payload(dt200, team_member), team_member)[0]
        row = next(
            raw[offset : offset + 1532]
            for offset in range(0, len(raw), 1532)
            if struct.unpack_from("<I", raw, offset + 8)[0] == 2473
        )
        self.assertEqual(row[84], 15)
        self.assertEqual(row[368:438].split(b"\0", 1)[0], b"INTER MIAMI CF")
        self.assertEqual(row[882:886].split(b"\0", 1)[0], b"MIA")

        for kind, suffix in (("1st", "p1"), ("2nd", "p2"), ("GK1st", "g1")):
            member = f"common/etc/uniform/team/2473/2473_DEF_{kind}_realUni.bin"
            descriptor = member_payload(dt200, member)
            self.assertEqual(len(descriptor), 120)
            self.assertEqual(descriptor_texture_names(descriptor)[0], f"u2473{suffix}")

    def test_mobile_textures_are_complete(self):
        dt120 = CANDIDATE / "dt120-original-order.cpk"
        inventory = cpk_inventory(dt120)
        for suffix in ("p1", "p2", "g1"):
            body = f"Models/character/Uniform16/D/u2473{suffix}.png"
            back = f"Models/character/Uniform16/Font/u2473{suffix}_back.png"
            self.assertIn(body, inventory)
            self.assertIn(back, inventory)
            with Image.open(io.BytesIO(member_payload(dt120, body))) as image:
                self.assertEqual((image.size, image.mode), ((256, 384), "P"))
            with Image.open(io.BytesIO(member_payload(dt120, back))) as image:
                self.assertEqual((image.size, image.mode), ((320, 40), "RGBA"))

    def test_native_crest_variants_match_approved_sources(self):
        dt240 = CANDIDATE / "dt240-original-order.cpk"
        inventory = cpk_inventory(dt240)
        sources = {
            2473: ROOT / "data/exhibition_badges/5738.png",
            68113: ROOT / "data/exhibition_badges/18961.png",
        }
        for team_id, source in sources.items():
            expected = Image.open(source).convert("RGBA")
            names = [name for name in inventory if f"e_{team_id:06d}_" in name]
            self.assertGreaterEqual(len(names), 3)
            for name in names:
                with Image.open(io.BytesIO(member_payload(dt240, name))) as actual:
                    actual = actual.convert("RGBA")
                resized = expected.resize(actual.size, Image.Resampling.LANCZOS)
                self.assertIsNone(ImageChops.difference(actual, resized).getbbox(), name)

    @unittest.skipUnless(BASE_OBB.is_file(), "previous local candidate is unavailable")
    def test_portraits_and_scoreboard_are_preserved(self):
        candidate = CANDIDATE / "patch.305030001.jp.nyan2021.pesam.obb"
        for member in (
            "Expansion/dt210_mobile_android.cpk",
            "Expansion/dt241_mobile_all.cpk",
        ):
            self.assertEqual(
                member_payload(candidate, member), member_payload(BASE_OBB, member), member
            )


if __name__ == "__main__":
    unittest.main()
