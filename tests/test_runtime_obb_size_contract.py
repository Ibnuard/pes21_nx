"""Guard the production package's explicit OBB-size contract (not a hardware test)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT/'source/main.c').read_text()
OBB = ROOT/'local-debug/eng-spa-all-kits-v3/patch.305030001.jp.nyan2021.pesam.obb'
SERIE_A_OBB = ROOT/'local-debug/serie-a-all-kits-v2/patch.305030001.jp.nyan2021.pesam.obb'
NATIONAL_OBB = ROOT/'local-debug/national-team-all-kits-v2/patch.305030001.jp.nyan2021.pesam.obb'
RECOVERY_OBB = ROOT/'local-debug/player-identity-recovery-v5/patch.305030001.jp.nyan2021.pesam.obb'
LICENSE_PORTRAIT_OBB = ROOT/'local-debug/licensed-crests-inter-miami-portraits-v1/patch.305030001.jp.nyan2021.pesam.obb'
EF10_NAMES_PROBE_OBB = ROOT/'local-debug/ef10-native-names-native-input-probe-v1/patch.305030001.jp.nyan2021.pesam.obb'
INTER_MIAMI_FL2026_OBB = ROOT/'local-debug/inter-miami-fl2026-kits-native-crests-v1/patch.305030001.jp.nyan2021.pesam.obb'


class RuntimeObbSizeContractTests(unittest.TestCase):
    def test_current_size_is_primary_expectation(self):
        self.assertIn('{ PATCH_OBB_PATH, PATCH_OBB_INTER_MIAMI_FL2026_V1_SIZE }', SOURCE)
        size = int(re.search(r'#define PATCH_OBB_NATIONAL_ALL_KITS_V2_SIZE (\d+)ULL', SOURCE)[1])
        self.assertEqual(size, 1410308096)
        recovery_size = int(re.search(r'#define PATCH_OBB_PLAYER_IDENTITY_RECOVERY_V5_SIZE (\d+)ULL', SOURCE)[1])
        self.assertEqual(recovery_size, 1409579008)
        current_size = int(re.search(r'#define PATCH_OBB_LICENSE_PORTRAIT_FIX_V1_SIZE (\d+)ULL', SOURCE)[1])
        self.assertEqual(current_size, 1409914880)
        probe_size = int(re.search(r'#define PATCH_OBB_EF10_NATIVE_NAMES_PROBE_V1_SIZE (\d+)ULL', SOURCE)[1])
        self.assertEqual(probe_size, 1409912832)
        inter_miami_size = int(re.search(r'#define PATCH_OBB_INTER_MIAMI_FL2026_V1_SIZE (\d+)ULL', SOURCE)[1])
        self.assertEqual(inter_miami_size, 1410254848)

    @unittest.skipUnless(OBB.is_file(), 'local proprietary OBB unavailable')
    def test_actual_artifact_matches_allowance(self):
        old_size = int(re.search(r'#define PATCH_OBB_ENG_SPA_ALL_KITS_V3_SIZE (\d+)ULL', SOURCE)[1])
        self.assertEqual(OBB.stat().st_size, old_size)
        if SERIE_A_OBB.is_file():
            new_size = int(re.search(r'#define PATCH_OBB_SERIE_A_ALL_KITS_V2_SIZE (\d+)ULL', SOURCE)[1])
            self.assertEqual(SERIE_A_OBB.stat().st_size, new_size)
        if NATIONAL_OBB.is_file():
            national_size = int(re.search(r'#define PATCH_OBB_NATIONAL_ALL_KITS_V2_SIZE (\d+)ULL', SOURCE)[1])
            self.assertEqual(NATIONAL_OBB.stat().st_size, national_size)
        if RECOVERY_OBB.is_file():
            recovery_size = int(re.search(r'#define PATCH_OBB_PLAYER_IDENTITY_RECOVERY_V5_SIZE (\d+)ULL', SOURCE)[1])
            self.assertEqual(RECOVERY_OBB.stat().st_size, recovery_size)
        if LICENSE_PORTRAIT_OBB.is_file():
            current_size = int(re.search(r'#define PATCH_OBB_LICENSE_PORTRAIT_FIX_V1_SIZE (\d+)ULL', SOURCE)[1])
            self.assertEqual(LICENSE_PORTRAIT_OBB.stat().st_size, current_size)
        if EF10_NAMES_PROBE_OBB.is_file():
            probe_size = int(re.search(r'#define PATCH_OBB_EF10_NATIVE_NAMES_PROBE_V1_SIZE (\d+)ULL', SOURCE)[1])
            self.assertEqual(EF10_NAMES_PROBE_OBB.stat().st_size, probe_size)
        if INTER_MIAMI_FL2026_OBB.is_file():
            inter_miami_size = int(re.search(r'#define PATCH_OBB_INTER_MIAMI_FL2026_V1_SIZE (\d+)ULL', SOURCE)[1])
            self.assertEqual(INTER_MIAMI_FL2026_OBB.stat().st_size, inter_miami_size)

    def test_keeps_recovery_sizes_and_actionable_error(self):
        self.assertIn('actual_size == PATCH_OBB_ORIGINAL_SIZE', SOURCE)
        self.assertIn('actual_size == PATCH_OBB_NATIVE_LICENSE_KITS_V4_SIZE', SOURCE)
        self.assertIn('S_ISREG(st.st_mode) && size_matches', SOURCE)
        self.assertIn('Actual bytes: %lld', SOURCE)
        self.assertIn('Build: Inter Miami FL2026 v1', SOURCE)


if __name__ == '__main__':
    unittest.main()
