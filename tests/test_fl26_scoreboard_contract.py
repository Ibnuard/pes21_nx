"""Synthetic AP2 path/contract tests; no game-owned payloads are fixtures."""
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from afp_score_layout import Movie
from audit_fl26_scoreboard_contract import (
    compare_contracts, container_contract, movie_contract, named_paths,
)
from afp_texture_patch import lzss_encode


class ScoreboardContractTests(unittest.TestCase):
    def test_equal_leaf_names_do_not_establish_native_binding_path(self):
        mobile = named_paths([
            dict(parent=None, frame=0, name="main", source=1),
            dict(parent=1, frame=0, name="scoreGroup", source=2),
            dict(parent=2, frame=0, name="teamName_home", source=5),
        ])
        pc = named_paths([
            dict(parent=None, frame=0, name="window", source=10),
            dict(parent=10, frame=0, name="mainGroup", source=11),
            dict(parent=11, frame=0, name="teamNameHome", source=12),
            dict(parent=12, frame=0, name="teamName_home", source=5),
        ])
        self.assertIn("main.scoreGroup.teamName_home", mobile)
        self.assertIn("window.mainGroup.teamNameHome.teamName_home", pc)
        self.assertTrue(set(mobile).isdisjoint(pc))

    def test_recursive_and_ambiguous_paths_rejected(self):
        with self.assertRaisesRegex(ValueError, "recursive"):
            named_paths([dict(parent=None, frame=0, name="root", source=1),
                         dict(parent=1, frame=0, name="loop", source=1)])
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            named_paths([dict(parent=None, frame=0, name="root", source=1),
                         dict(parent=None, frame=0, name="root", source=2)])

    def test_live_and_update_frames_remain_timeline_metadata(self):
        names = b"\0time_set\0"
        payload = struct.pack("<IHHHHiiI", 0x242e, 14, 55, 18, 1, 2000, 400, 0xffffff80)
        tag = struct.pack("<I", (0x7f << 22) | len(payload)) + payload
        section = struct.pack("<HHIIIII", 0, 0, 1, 1, 0, 24, 28) + struct.pack("<I", 1 << 20) + tag
        data = bytearray(68)
        data[:4] = b"\x0b\xb2\xd0\xc1"
        struct.pack_into("<I", data, 36, 68)
        start = len(data) + len(section)
        struct.pack_into("<II", data, 48, start, len(names))
        data += section + bytes((value + 128 + i) & 255 for i, value in enumerate(names))
        struct.pack_into("<I", data, 4, len(data))
        result = movie_contract(Movie("game2d_score", 0, len(data), b"", bytes(data)))
        self.assertEqual(result["placement_count"], 1)
        self.assertEqual(result["required_paths"], ["time_set"])
        self.assertEqual(result["named_timelines"]["time_set"]["initial_translate"], (100, 20))
        self.assertEqual(result["named_timelines"]["time_set"]["frames"], [0])

    def contract(self, **overrides):
        value = {"txp_bytes": 1000, "texture_count": 1,
                 "movies": {"game2d_score": {}},
                 "score": {"required_paths": ["main.scoreGroup.time_set"],
                           "header_word_0c": 571}}
        value.update(overrides)
        return value

    def test_shared_signature_never_silently_authorizes_a_port(self):
        result = compare_contracts(self.contract(), self.contract())
        self.assertEqual(result["verdict"], "compatibility_not_established")
        self.assertFalse(result["drop_in_port_validated"])
        self.assertEqual(result["blockers"], [])

    def test_actual_classes_of_mismatch_are_separate(self):
        candidate = self.contract(
            txp_bytes=4_000_000, texture_count=2,
            score={"required_paths": ["window.mainGroup.time_texts_motion"],
                   "header_word_0c": 59})
        result = compare_contracts(self.contract(), candidate)
        self.assertEqual(result["verdict"], "incompatible_drop_in")
        self.assertEqual(result["missing_native_paths"], ["main.scoreGroup.time_set"])
        self.assertEqual(len(result["blockers"]), 4)

    def test_general_container_without_score_is_not_a_scorebar_port(self):
        result = compare_contracts(self.contract(), self.contract(score=None))
        self.assertIn("candidate_has_no_game2d_score_movie", result["blockers"])
        with self.assertRaisesRegex(ValueError, "baseline"):
            compare_contracts(self.contract(score=None), self.contract())

    def test_small_declared_envelope_cannot_hide_large_referenced_payload(self):
        candidate = self.contract(
            txp_bytes=700_000, minimum_payload_span=4_500_000,
            textures=[dict(inside_declared_txp=False)])
        result = compare_contracts(self.contract(), candidate)
        self.assertIn("exceeds_existing_runtime_theme_input_limit", result["blockers"])
        self.assertIn("referenced_textures_outside_declared_txp_envelope", result["blockers"])

    def test_large_texture_metadata_needs_only_a_fixed_header_decode(self):
        header = bytearray(64)
        header[:4] = b"TXDT"
        struct.pack_into(">HH", header, 16, 3200, 2500)
        packed = lzss_encode(bytes(header))
        data = bytearray(128)
        data[:4] = b"TXP2"
        struct.pack_into(">I", data, 12, 128)
        struct.pack_into(">III", data, 20, 4, 1, 108)
        struct.pack_into(">III", data, 108, 120, len(packed) + 8, 128)
        data[120:125] = b"tex0\0"
        data += struct.pack(">II", 32_000_064, len(packed)) + packed
        # An inventory may read the header of a large texture without validating
        # or allocating its advertised full payload. It never accepts the port.
        with patch("audit_fl26_scoreboard_contract.read_movies", return_value=[]):
            result = container_contract(bytes(data))
        self.assertEqual(result["textures"][0]["dimensions"], [3200, 2500])
        self.assertEqual(result["textures"][0]["expanded_bytes"], 32_000_064)
        self.assertFalse(result["textures"][0]["inside_declared_txp"])
        self.assertEqual(result["minimum_payload_span"], len(data))
        self.assertIsNone(result["score"])

    def test_missing_or_truncated_txp_fails_before_movie_parsing(self):
        for data in (b"", b"x" * 108, b"TXP2" + b"\0" * 104):
            with self.subTest(data=data[:4]):
                with self.assertRaises(ValueError):
                    container_contract(data)


if __name__ == "__main__":
    unittest.main()
