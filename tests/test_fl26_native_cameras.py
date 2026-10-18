"""Execute the owned Mobile camera conversion; no proprietary fixtures in git."""
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'dist/pes21_nx/libUE4.so'


@unittest.skipUnless(LIBRARY.is_file(), 'requires ignored compatible Mobile libUE4.so')
class NativeCameraTests(unittest.TestCase):
    def test_native_presets_convert_all_registry_copies_without_custom_tracking(self):
        try:
            from elftools.elf.elffile import ELFFile
            from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED
            import unicorn.arm64_const as regs
        except ImportError:
            self.skipTest('requires local pyelftools and unicorn')

        with LIBRARY.open('rb') as stream:
            elf = ELFFile(stream)
            symbols = elf.get_section_by_name('.dynsym')
            relocs = elf.get_section_by_name('.rela.plt')
            plt = elf.get_section_by_name('.plt')
            plt_begin, plt_end = plt['sh_addr']+32, plt['sh_addr']+plt['sh_size']
            segments = [s for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']
            uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)

            def map_native(uc, access, address, size, value, user):
                page = address & ~0xfff
                for segment in segments:
                    start, count = segment['p_vaddr'], segment['p_filesz']
                    if start <= address < start+count:
                        uc.mem_map(page, 0x1000)
                        first, last = max(page, start), min(page+0x1000, start+count)
                        stream.seek(segment['p_offset']+first-start)
                        uc.mem_write(first, stream.read(last-first))
                        return True
                return False

            def resolve_plt(uc, address, size, user):
                if plt_begin <= address < plt_end and (address-plt_begin) % 16 == 0:
                    relocation = relocs.get_relocation((address-plt_begin)//16)
                    symbol = symbols.get_symbol(relocation['r_info_sym'])
                    self.assertNotEqual(symbol['st_value'], 0, symbol.name)
                    uc.reg_write(regs.UC_ARM64_REG_PC, symbol['st_value'])

            uc.hook_add(UC_HOOK_MEM_UNMAPPED, map_native)
            uc.hook_add(UC_HOOK_CODE, resolve_plt)
            stack, arena, stop = 0x100000000, 0x110000000, 0x120000000
            uc.mem_map(stack, 0x10000)
            uc.mem_map(arena, 0x40000)
            uc.mem_map(stop, 0x1000)
            registry, tmpdb, resident = arena+0x100, arena+0x500, arena+0x10000
            # Same native converter installed by the production PLT wrapper.
            entry = 0x7beae40
            native_rows = ((3, 2, 2, 2, 0), (12, 12, 2, 3, 6),
                           (5, 10, 2, 2, 0), (0, 6, 9, 7, 0),
                           (1, 7, 5, 7, 0), (2, 0, 1, 7, 0))
            for preset, converted, distance, height, angle in native_rows:
                for mode in range(7):
                    with self.subTest(preset=preset, mode=mode):
                        settings = bytes([preset, 0]+[0xa5]*13)
                        uc.mem_write(registry, bytes([0x7a]*32))
                        uc.mem_write(tmpdb, settings)
                        for slot in range(7):
                            uc.mem_write(resident+0xb78+slot*15, settings)
                        uc.mem_write(resident+0x18338, struct.pack('<I', mode))
                        uc.reg_write(regs.UC_ARM64_REG_SP, stack+0x8000)
                        uc.reg_write(regs.UC_ARM64_REG_X0, registry)
                        uc.reg_write(regs.UC_ARM64_REG_X1, tmpdb)
                        uc.reg_write(regs.UC_ARM64_REG_X2, resident)
                        uc.reg_write(regs.UC_ARM64_REG_LR, stop)
                        uc.emu_start(entry, stop, count=20000)
                        self.assertEqual(uc.reg_read(regs.UC_ARM64_REG_PC), stop)
                        result = uc.mem_read(registry, 32)
                        for offset in (0, 6, 11):
                            self.assertEqual(result[offset], converted)
                            self.assertEqual(bytes(result[offset+2:offset+5]),
                                             bytes([distance, height, angle]))
                        self.assertEqual(uc.mem_read(tmpdb, 15), settings)
                        self.assertEqual(uc.mem_read(resident+0x18338, 4), struct.pack('<I', mode))

    def test_pitch_side_and_stadium_use_separate_native_paths(self):
        try:
            from elftools.elf.elffile import ELFFile
        except ImportError:
            self.skipTest('requires pyelftools')
        with LIBRARY.open('rb') as stream:
            elf = ELFFile(stream)

            def words(address, count):
                stream.seek(next(elf.address_offsets(address)))
                return struct.unpack('<'+'I'*count, stream.read(count*4))

            registry = words(0x85d7958, 14)
            live = (1,)+words(0x81cef54, 13)
            self.assertEqual((registry[3], live[registry[3]]), (2, 1))
            self.assertEqual((registry[12], live[registry[12]]), (12, 6))
            # Update dispatches only IDs 3/6 to Broadcast; ID 1 is Horizontal.
            self.assertEqual(words(0x665acc4, 4),
                             (0x71000d1f, 0x54000060, 0x7100191f, 0x540000a1))
