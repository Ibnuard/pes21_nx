"""Serie A identity, mobile kit, and EF10 player-asset package checks."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from build_eng_spa_license_pack import load_manifest, decode_team_payload, split_team_rows, team_id, fixed_ascii
from build_pesdb_famous_teams_candidate import member_payload

MANIFEST = ROOT/'data/serie_a_license_overrides.json'
PACK = ROOT/'local-debug/serie-a-all-kits-v2'


class SerieAManifestTests(unittest.TestCase):
    def test_twenty_source_teams_and_single_missing_native_slot(self):
        _manifest, teams = load_manifest(MANIFEST)
        self.assertEqual(len(teams), 20)
        self.assertEqual([row['team_id'] for row in teams if row['team_bin_policy']=='pending_team_record'], [4219])
        self.assertEqual({row['order'] for row in teams}, set(range(1, 21)))
        by_id = {row['team_id']: row for row in teams}
        self.assertEqual(by_id[120]['official_name'], 'Juventus FC')
        self.assertEqual(by_id[119]['official_name'], 'Inter Milan')
        self.assertEqual(by_id[125]['official_name'], 'AS Roma')

    def test_selector_has_all_nineteen_available_licensed_names(self):
        catalog = json.loads((ROOT/'data/exhibition_team_catalog.json').read_text())
        serie_a = [row for row in catalog['teams'] if row['category']=='serie_a']
        self.assertEqual(len(serie_a), 19)
        self.assertTrue(all(row['name_source']=='football_life_license' for row in serie_a))
        self.assertTrue(all('serie-a-club-license-integration/crests/' in row['badge_source'] for row in serie_a))

    def test_native_crest_builder_updates_new_real_variants(self):
        source = (ROOT/'tools/build_eng_spa_mobile_kits.py').read_text()
        self.assertIn(
            "set(inventories['dt240']) | set(payloads['dt240'])",
            source,
        )
        self.assertIn("template = payloads['dt240'].get(name)", source)


@unittest.skipUnless((PACK/'validation-report.json').is_file(), 'local Serie A package unavailable')
class SerieAPackageTests(unittest.TestCase):
    def test_kits_crests_names_player_data_and_portraits_are_packaged(self):
        report = json.loads((PACK/'asset-report.json').read_text())
        statuses = {row['team_id']: row['status'] for row in report['teams']}
        self.assertEqual(sum(value=='converted' for value in statuses.values()), 19)
        self.assertEqual(statuses[4219], 'assets_only_missing_native_slot')
        self.assertEqual(len(report['native_crests_updated']), 19)
        self.assertEqual(report['pending_native_slots'], [4219])

        dt200 = PACK/'dt200-original-order.cpk'
        for member, expected in (
            ('common/etc/pesdb/Player.bin', ROOT/'local-debug/efootball10-all-teams-patch/Player.bin'),
            ('common/etc/pesdb/TacticsFormation.bin', ROOT/'local-debug/efootball10-all-teams-patch/TacticsFormation.bin'),
        ):
            self.assertEqual(member_payload(dt200, member), expected.read_bytes())

        team_payload = member_payload(dt200, 'common/etc/pesdb/Team.bin')
        temporary = PACK/'test-Team.bin'
        temporary.write_bytes(team_payload)
        try:
            raw, _ = decode_team_payload(temporary)
        finally:
            temporary.unlink()
        rows = {team_id(row): row for row in split_team_rows(raw)}
        self.assertEqual(fixed_ascii(rows[120], 368, 70), 'Juventus FC')
        self.assertEqual(fixed_ascii(rows[119], 368, 70), 'Inter Milan')
        self.assertEqual(rows[120][84], 15)

        portrait = ROOT/'local-debug/efootball10-all-teams-patch/dt241_mobile_all_ef10_all_teams.cpk'
        self.assertEqual(
            hashlib.sha256(member_payload(PACK/'patch.305030001.jp.nyan2021.pesam.obb', 'Expansion/dt241_mobile_all.cpk')).digest(),
            hashlib.sha256(portrait.read_bytes()).digest())
        self.assertEqual(
            member_payload(portrait, 'common/player/4522.png'),
            (ROOT/'local-debug/efootball10-all-teams-patch/normalized-portraits/4522.png').read_bytes())


if __name__ == '__main__':
    unittest.main()
