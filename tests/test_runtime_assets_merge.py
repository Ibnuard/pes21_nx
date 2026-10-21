"""Typed archive limits and a pinned merge preserve every approved byte."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from pack_runtime_assets import (ENTRY, HEADER, MAGIC, PLAYER_AUDIO_PREFIX,
                                 checksum, collect, pack_entries, read_archive, verify)
from merge_runtime_assets import APPROVED_FILES, merge, record


def raw_archive(path, entries):
    """Independent format writer, including non-runtime standalone members."""
    cursor = HEADER.size + len(entries) * ENTRY.size
    index, payload = bytearray(), bytearray()
    for key, data in entries:
        index += ENTRY.pack(key.encode("ascii"), cursor, len(data), checksum(data), 0, 0)
        payload += data
        cursor += len(data)
    path.write_bytes(HEADER.pack(MAGIC, len(entries), ENTRY.size, cursor,
                                HEADER.size + len(index)) + index + payload)


class RuntimeAssetPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pesnx-assets-policy-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "FootballNX.assets"

    def test_large_seed_is_scoped_and_collect_includes_audio_marker_token(self):
        files = {"Commentary/players-v53.nxcp": bytes(2_000_001),
                 "Commentary/players-v59/audio/one.hca": b"HCA\0synthetic",
                 "Commentary/players-v59/catalog-id.txt": b"pair-id\n",
                 "referee-probe.txt": b"PESNX_REFEREE_PROBE_V1\n"}
        for name, data in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        report = pack_entries(collect(self.root), self.archive)
        self.assertEqual(verify(self.archive), report)
        self.assertEqual(read_archive(self.archive)[1], {k.lower(): v for k, v in files.items()})
        before = self.archive.read_bytes()
        for name in ("Commentary/indonesia.nxcp", "Commentary/unapproved.nxcp"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "limit"):
                pack_entries({name: bytes(1_048_577)}, self.archive)
            self.assertEqual(self.archive.read_bytes(), before)

    def test_caps_are_enforced_by_reader_before_payload_allocation(self):
        cases = {"commentary/indonesia.nxcp": 1_048_576,
                 "commentary/players-v53.nxcp": 8 * 1024 * 1024,
                 "commentary/players-v59/audio/one.hca": 2 * 1024 * 1024,
                 "commentary/players-v59/catalog-id.txt": 64,
                 "animations/referee.nxra": 524_288, "referee-probe.txt": 128}
        for name, cap in cases.items():
            with self.subTest(name=name):
                size = cap + 1
                payload = HEADER.size + ENTRY.size
                with self.archive.open("wb") as stream:
                    stream.write(HEADER.pack(MAGIC, 1, ENTRY.size, payload + size, payload))
                    stream.write(ENTRY.pack(name.encode(), payload, size, 0, 0, 0))
                    stream.seek(payload + size - 1)
                    stream.write(b"\0")
                with self.assertRaises(ValueError):
                    verify(self.archive)

    def test_unknown_paths_and_standalone_names_require_explicit_namespace(self):
        for name in ("audio/one.hca", "commentary/other/audio/one.hca", "catalog-id.txt",
                     "commentary/players-v59/other.hca", "commentary/players-v59/audio/sub/one.hca",
                     "Commentary/players-v53.nxcp", "commentary/../players-v53.nxcp"):
            with self.subTest(name=name):
                raw_archive(self.archive, [(name, b"x")])
                with self.assertRaises(ValueError):
                    verify(self.archive)
        raw_archive(self.archive, [("audio/one.hca", b"sound"), ("catalog-id.txt", b"pair\n")])
        self.assertEqual(len(verify(self.archive, namespace_prefix=PLAYER_AUDIO_PREFIX)["entries"]), 2)
        with self.assertRaises(ValueError):
            verify(self.archive, namespace_prefix="Commentary/elsewhere")

    def test_index_sort_case_padding_overlap_and_count_rejections(self):
        for entries in ([('cuplogos/b.png', b'b'), ('cuplogos/a.png', b'a')],
                        [('cuplogos/a.png', b'a'), ('cuplogos/a.png', b'b')]):
            raw_archive(self.archive, entries)
            with self.assertRaises(ValueError):
                verify(self.archive)
        raw_archive(self.archive, [('cuplogos/a.png', b'a'), ('cuplogos/b.png', b'b')])
        good = self.archive.read_bytes()
        for offset, value, fmt in ((HEADER.size + 127, 1, '<B'),
                (HEADER.size + ENTRY.size + 128, HEADER.size + 2 * ENTRY.size, '<Q'),
                (HEADER.size + 156, 1, '<I'), (8, 4097, '<I')):
            bad = bytearray(good)
            struct.pack_into(fmt, bad, offset, value)
            self.archive.write_bytes(bad)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                verify(self.archive)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            pack_entries({'CupLogos/a.png': b'a', 'cuplogos/A.png': b'b'}, self.archive)
        with self.assertRaises(ValueError):
            pack_entries({f'cuplogos/{i}.png': b'x' for i in range(4097)}, self.archive)


class RuntimeAssetMergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pesnx-assets-merge-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "base.assets"
        self.base_report = self.root / "base.json"
        self.approved = self.root / "approved"
        self.approved_report = self.root / "approved.json"
        self.roster = self.root / "roster.nxpa"
        self.roster_report = self.root / "roster.json"
        self.output = self.root / "merged.assets"
        self.base_data = {'animations/referee.nxra': b'old motion',
                          'commentary/indonesia.nxcp': b'accepted indonesia',
                          'scoreboards/c9.nxsb': b'accepted board',
                          'cuplogos/a.png': b'accepted cup'}
        self.pin_base()
        self.approved_data = {'animations/referee.nxra': b'approved motion',
                              'commentary/players-v53.nxcp': b'accepted canary seed',
                              'referee-probe.txt': b'PESNX_REFEREE_PROBE_V1\n'}
        pins = {}
        for key, relative in APPROVED_FILES.items():
            path = self.approved / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.approved_data[key])
            pins['switch/pes21_nx/' + relative] = record(self.approved_data[key])
        self.approved_report.write_text(json.dumps({'files': pins}))
        self.audio = [('audio/one.hca', b'HCA\0first'), ('audio/two.hca', b'HCA\0second'),
                      ('catalog-id.txt', b'pair-id\n')]
        self.pin_roster()

    def pin_base(self):
        proof = pack_entries(self.base_data, self.base)
        self.base_report.write_text(json.dumps(proof))

    def pin_roster(self):
        raw_archive(self.roster, self.audio)
        proof = verify(self.roster, namespace_prefix=PLAYER_AUDIO_PREFIX)
        self.roster_report.write_text(json.dumps({'archive': proof}))

    def run_merge(self):
        return merge(self.base, self.base_report, self.approved, self.approved_report,
                     self.roster, self.roster_report, self.output)

    def test_deterministic_merge_preserves_base_and_imports_every_member(self):
        source_files = [self.base, self.roster] + [self.approved / n for n in APPROVED_FILES.values()]
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
        result = self.run_merge()
        expected = {**self.base_data, **self.approved_data,
                    **{PLAYER_AUDIO_PREFIX + '/' + name: data for name, data in self.audio}}
        self.assertEqual(read_archive(self.output)[1], expected)
        self.assertEqual(result['protected_members_exact'], len(self.base_data) - 1)
        self.assertEqual(result['roster_import']['audio_recordings'], 2)
        first = self.output.read_bytes()
        self.assertEqual(self.run_merge(), result)
        self.assertEqual(self.output.read_bytes(), first)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files})

    def test_pin_mismatches_fail_before_existing_output_changes(self):
        self.output.write_bytes(b'previous output')
        for path in (self.base_report, self.approved_report, self.roster_report):
            old = path.read_text()
            changed = json.loads(old)
            if path == self.base_report:
                changed['sha256'] = '0' * 64
            elif path == self.roster_report:
                changed['archive']['sha256'] = '0' * 64
            else:
                changed['files']['switch/pes21_nx/Animations/referee.nxra']['sha256'] = '0' * 64
            path.write_text(json.dumps(changed))
            with self.subTest(path=path.name), self.assertRaisesRegex(ValueError, 'pinned'):
                self.run_merge()
            self.assertEqual(self.output.read_bytes(), b'previous output')
            path.write_text(old)
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_conflicts_and_unknown_roster_members_are_rejected(self):
        self.base_data['commentary/players-v53.nxcp'] = b'existing seed'
        self.pin_base()
        with self.assertRaisesRegex(ValueError, 'unapproved replacement'):
            self.run_merge()
        self.assertFalse(self.output.exists())
        del self.base_data['commentary/players-v53.nxcp']
        self.pin_base()
        self.audio.insert(0, ('animations/referee.nxra', b'unknown replacement'))
        raw_archive(self.roster, self.audio)
        with self.assertRaises(ValueError):
            self.run_merge()
        self.assertFalse(self.output.exists())

    def test_missing_marker_and_input_overwrite_are_rejected(self):
        self.audio.pop()
        self.pin_roster()
        with self.assertRaisesRegex(ValueError, 'catalog-id'):
            self.run_merge()
        self.output = self.base
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            self.run_merge()


if __name__ == '__main__':
    unittest.main()
