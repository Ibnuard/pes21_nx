"""Validate the production library ABI used by the pause snapshot bridge."""
from pathlib import Path
import struct
import unittest
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]


class PauseNativeAbiTests(unittest.TestCase):
    def test_layout_and_prematch_callbacks_have_patchable_vtable_slots(self):
        path = ROOT / 'dist/pes21_nx/libUE4.so'
        if not path.exists(): self.skipTest('Native library not installed')
        with path.open('rb') as stream:
            elf = ELFFile(stream)
            symtab = elf.get_section_by_name('.dynsym')
            symbols = {s.name: s for s in symtab.iter_symbols()}
            pairs = (
                ('_ZTVN4menu23MatchTouchIconMenuScoreE', '_ZN4menu23MatchTouchIconMenuScore10InitMobileEv'),
                ('_ZTVN10menusystem12GuiBarWindowE', '_ZN10menusystem12GuiBarWindow23UpdatePostControlWindowENS_6Window10PAD_STATUSE'),
                ('_ZTVN7match2D6Screen13DemoMatchCardE', '_ZN7match2D6Screen13DemoMatchCard8NeedDispEv'),
            )
            relocs = {r['r_offset']: r for r in elf.get_section_by_name('.rela.dyn').iter_relocations()}
            for table, method in pairs:
                base = symbols[table]['st_value']
                target = symbols[method]['st_value']
                found = []
                for index in range(2, 128):
                    address = base + index * 8
                    r = relocs.get(address)
                    if r is not None:
                        value = r['r_addend']
                        if r['r_info_sym']:
                            value += symtab.get_symbol(r['r_info_sym'])['st_value']
                    else:
                        stream.seek(next(elf.address_offsets(address)))
                        value = struct.unpack('<Q', stream.read(8))[0]
                    if value == target: found.append(index)
                self.assertTrue(found, (table, method))

    def test_hook_install_uses_backing_before_runtime_mapping(self):
        hooks = (ROOT / 'source/ue4_hooks.c').read_text()
        start = hooks.index('const uint32_t stats_getter_expected[4]')
        end = hooks.index('match_global_registry_get_order_info =', start)
        block = hooks[start:end]
        self.assertIn('uintptr_t site = so_find_addr(module, stats_symbols[i]);', block)
        self.assertNotIn('uintptr_t site = so_find_addr_rx(', block)
        self.assertIn('hook_arm64(site,', block)
        main = (ROOT / 'source/main.c').read_text()
        self.assertLess(main.index('install_ue4_hooks(&ue4_mod)'),
                        main.index('so_finalize(&ue4_mod)'))

    def test_stats_getters_and_live_substitution_symbols(self):
        path = ROOT / 'dist/pes21_nx/libUE4.so'
        if not path.exists():
            self.skipTest('Native library not installed')
        with path.open('rb') as stream:
            elf = ELFFile(stream)
            symbols = {s.name: s for s in elf.get_section_by_name('.dynsym').iter_symbols()}
            for name in (
                '_ZN5match8registry10RecordInfo13GetMatchStatsEv',
                '_ZNK5match8registry10RecordInfo13GetMatchStatsEv',
            ):
                symbol = symbols[name]
                self.assertEqual(symbol['st_size'], 16)
                stream.seek(next(elf.address_offsets(symbol['st_value'])))
                self.assertEqual(struct.unpack('<4I', stream.read(16)),
                                 (0x528a1988, 0x72a000e8, 0x8b080000, 0xd65f03c0))
            for name in (
                '_ZNK5match6output14StatsMatchInfo11GetTeamInfoE8HomeAway',
                '_ZNK5match6output13StatsTeamInfo8GetScoreE8HalfKind',
                '_ZNK5match6output13StatsTeamInfo7GetDataENS0_13StatsDataKindE8HalfKind',
                '_ZNK5match6output14StatsMatchInfo14GetControlRateE8HomeAway8HalfKind',
                '_ZN5tmpdb9SquadData11CanReservedE8MemberIdS1_',
                '_ZN5tmpdb9SquadData23SetMemberChangeReservedE8MemberIdS1_',
                '_ZN4menu15MyClubSquadEdit19PadEventFooterTouchEN10menusystem17MOBILE_FOOTER_KEYE',
            ):
                self.assertGreater(symbols[name]['st_value'], 0)


if __name__ == '__main__':
    unittest.main()
