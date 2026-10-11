"""Optional native referee contracts; the compatible game library stays ignored."""
from pathlib import Path
import re
import struct
import unittest


ROOT = Path(__file__).resolve().parents[1]
WARP = '_ZN5match4Flow16ExecPositionWarpEPKN5cobra4game7ContextE'
RENDER = '_ZN6render11PlayerModel6UpdateEv'
QUEUE = '_ZN13RenderManager13SetLoadPlayerEP13UEPlayerModel'
LOAD = '_ZN13UEPlayerModel8LoadImplEv'
QUALITY = '_ZN8UESystem3Env10GetQualityEv'


class RefereeNativeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'dist/pes21_nx/libUE4.so'
        if not path.is_file():
            raise unittest.SkipTest('compatible local dist/pes21_nx/libUE4.so required')
        try:
            from elftools.elf.elffile import ELFFile
        except ImportError:
            raise unittest.SkipTest('pyelftools required for optional native contracts')
        cls.stream = path.open('rb')
        elf = ELFFile(cls.stream)
        if elf.elfclass != 64 or not elf.little_endian or elf['e_machine'] != 'EM_AARCH64':
            cls.stream.close()
            raise AssertionError('expected the compatible AArch64 mobile library')
        cls.segments = [(s['p_vaddr'], s['p_offset'], s['p_filesz'])
                        for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        table = elf.get_section_by_name('.dynsym')
        strings = elf.get_section(table['sh_link']).data()
        cls.symbols = {}
        indexed = []
        # Index once without the per-symbol object cost on this large ELF.
        for offset, info, other, section, address, size in struct.iter_unpack(
                '<IBBHQQ', table.data()):
            name = strings[offset:strings.find(b'\0', offset)].decode('utf-8')
            indexed.append(name)
            if address:
                cls.symbols[name] = (address, size)
        cls.plts = {}
        base = elf.get_section_by_name('.plt')['sh_addr']
        for index, (offset, info, addend) in enumerate(struct.iter_unpack(
                '<QQq', elf.get_section_by_name('.rela.plt').data())):
            cls.plts[indexed[info >> 32]] = base + 32 + 16 * index

    @classmethod
    def tearDownClass(cls):
        cls.stream.close()

    @classmethod
    def read(cls, address, size):
        start, offset, length = next(s for s in cls.segments
                                    if s[0] <= address and address + size <= s[0] + s[2])
        cls.stream.seek(offset + address - start)
        return cls.stream.read(size)

    @classmethod
    def word(cls, address):
        return struct.unpack('<I', cls.read(address, 4))[0]

    @classmethod
    def branches(cls, symbol, opcode):
        address, size = cls.symbols[symbol]
        targets = []
        for offset, (word,) in enumerate(struct.iter_unpack('<I', cls.read(address, size))):
            if word & 0xfc000000 == opcode:
                immediate = word & 0x03ffffff
                if immediate & 0x02000000:
                    immediate -= 0x04000000
                targets.append(address + 4 * offset + 4 * immediate)
        return targets

    def test_patch_sites_match_native_relocations_and_layout(self):
        source = (ROOT / 'source/referee_probe.inc').read_text(encoding='utf-8')
        for name in re.findall(r'REFEREE_BIND\([^,]+,\s*"([^"]+)"\)', source):
            with self.subTest(binding=name):
                self.assertIn(name, self.symbols)
        for label, symbol in (('warp', WARP), ('render', RENDER),
                              ('queue_player', QUEUE), ('load_player', LOAD),
                              ('quality', QUALITY)):
            with self.subTest(plt=label):
                match = re.search(r'const uintptr_t ' + label +
                                  r'_plt\s*=\s*\(uintptr_t\)module->load_base\s*\+\s*(0x[0-9a-f]+)', source)
                self.assertIsNotNone(match)
                address = int(match[1], 16)
                self.assertEqual(self.plts[symbol], address)
                array = re.search(r'const uint32_t ' + label + r'_words\[\]\s*=\s*\{([^}]+)\}', source)
                self.assertIsNotNone(array)
                expected = tuple(int(w.strip(), 16) for w in array[1].split(','))
                self.assertEqual(struct.unpack('<4I', self.read(address, 16)), expected)
        layouts = ((WARP, 0xc, 0x39754808), (RENDER, 0x44, 0xf9005a60),
                   (LOAD, 0, 0xd102c3ff),
                   ('_ZN5match4Flow9ResetFlowENS_8FlowKindE', 0xc, 0xb90cd401),
                   ('_ZN18VisionModelManager11VisionModelC2Ejj', 0x18, 0xb9003001))
        for symbol, offset, expected in layouts:
            with self.subTest(layout=symbol):
                self.assertEqual(self.word(self.symbols[symbol][0] + offset), expected)

    def test_low_actor_and_async_load_use_hooked_paths(self):
        address = self.symbols[LOAD][0]
        self.assertEqual(self.word(address + 0xa8), 0x7100041f)  # quality == Low(1)
        self.assertIn(self.plts[QUALITY], self.branches(LOAD, 0x94000000))
        self.assertIn(self.plts['_ZN15APlayerActorLow21GetPrivateStaticClassEv'],
                      self.branches(LOAD, 0x94000000))
        self.assertIn(self.plts[QUEUE],
                      self.branches('_ZN13UEPlayerModel4LoadEv', 0x14000000))
        self.assertIn(self.plts[LOAD],
                      self.branches('_ZN13RenderManager4StepEv', 0x94000000))
        # The renderer's virtual quality query delegates to the same Env PLT.
        self.assertIn(self.plts[QUALITY],
                      self.branches('_ZN8UEBridge17GetQualitySettingEv', 0x14000000))
        self.assertEqual(self.word(self.symbols[RENDER][0] + 0x120), 0xf940c108)

    def test_native_flow_task_calls_warp_through_the_hooked_plt(self):
        self.assertIn(self.plts[WARP], self.branches(
            '_ZN5match4Flow8ExecTaskEPKN5cobra4game7ContextEbPNS_8registry11FixDemoInfoE',
            0x94000000))


if __name__ == '__main__':
    unittest.main()
