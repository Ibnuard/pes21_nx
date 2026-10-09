"""Execute the owned v5.3.0 HCA packet reader; no game code or keys embedded.

This deliberately stops before PCM synthesis or device playback. It checks
whether the real decoder corrupts plaintext packet bytes with a custom cipher.
"""
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_UNMAPPED, UC_HOOK_CODE
import unicorn.arm64_const as regs


class NativeHcaProbe:
    def __init__(self, library):
        self.file = library.open('rb')
        self.elf = ELFFile(self.file)
        self.segments = [s for s in self.elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        self.dyn = self.elf.get_section_by_name('.dynsym')
        self.reloc = {r['r_offset']: r['r_info_sym']
                      for r in self.elf.get_section_by_name('.rela.plt').iter_relocations()}
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.uc.hook_add(UC_HOOK_MEM_UNMAPPED, self.page)
        self.uc.mem_map(0x100000000, 0x400000)
        self.heap, self.stop = 0x100100000, 0x100000000
        self.uc.reg_write(regs.UC_ARM64_REG_CPACR_EL1, 3 << 20)
        plt = self.elf.get_section_by_name('.plt')
        self.uc.hook_add(UC_HOOK_CODE, self.plt,
                         begin=plt['sh_addr'], end=plt['sh_addr'] + plt['sh_size'] - 1)
        # Supply a test stack guard and mark HCA initialized. No process,
        # filesystem, license, allocation callback or audio-device APIs run.
        self.write(0x95709e0, struct.pack('<Q', self.alloc(8)))
        self.write(0x9c5e278, struct.pack('<I', 1))

    def close(self):
        self.file.close()

    def page(self, uc, access, address, size, value, data):
        start = address & ~4095
        segment = next((s for s in self.segments
                        if s['p_vaddr'] <= address < s['p_vaddr'] + s['p_memsz']), None)
        if segment is None:
            raise AssertionError(f'Unexpected native memory access {address:x}')
        uc.mem_map(start, 4096)
        length = min(4096, segment['p_vaddr'] + segment['p_filesz'] - start)
        if length > 0:
            self.file.seek(segment['p_offset'] + start - segment['p_vaddr'])
            uc.mem_write(start, self.file.read(length))
        return True

    def write(self, address, data):
        for page in range(address & ~4095, (address + len(data) + 4095) & ~4095, 4096):
            if not any(lo <= page <= hi for lo, hi, _ in self.uc.mem_regions()):
                self.page(self.uc, 0, page, 1, 0, None)
        self.uc.mem_write(address, data)

    def alloc(self, length, data=None):
        address = self.heap
        self.heap += (length + 31) & ~31
        assert self.heap < 0x100400000
        if data:
            self.uc.mem_write(address, data)
        return address

    def plt(self, uc, address, size, data):
        adrp, ldr = struct.unpack('<II', uc.mem_read(address, 8))
        assert adrp & 0x9f000000 == 0x90000000, 'Unexpected PLT entry'
        immediate = ((adrp >> 29) & 3) | (((adrp >> 5) & 0x7ffff) << 2)
        if immediate & (1 << 20):
            immediate -= 1 << 21
        got = (address & ~4095) + (immediate << 12) + ((ldr >> 10) & 4095) * 8
        symbol = self.dyn.get_symbol(self.reloc[got])
        if symbol['st_value']:
            uc.reg_write(regs.UC_ARM64_REG_PC, symbol['st_value'])
            return
        args = [uc.reg_read(getattr(regs, f'UC_ARM64_REG_X{i}')) for i in range(3)]
        if symbol.name == 'memcpy':
            uc.mem_write(args[0], bytes(uc.mem_read(args[1], args[2])))
        elif symbol.name == 'memset':
            uc.mem_write(args[0], bytes([args[1] & 255]) * args[2])
        else:
            raise AssertionError('Unexpected native import ' + symbol.name)
        uc.reg_write(regs.UC_ARM64_REG_X0, args[0])
        uc.reg_write(regs.UC_ARM64_REG_PC, uc.reg_read(regs.UC_ARM64_REG_LR))

    def call(self, address, *args):
        for i, value in enumerate(args):
            self.uc.reg_write(getattr(regs, f'UC_ARM64_REG_X{i}'), value)
        self.uc.reg_write(regs.UC_ARM64_REG_SP, 0x1000ff000)
        self.uc.reg_write(regs.UC_ARM64_REG_LR, self.stop)
        self.uc.emu_start(address, self.stop, count=3000000)
        assert self.uc.reg_read(regs.UC_ARM64_REG_PC) == self.stop, 'Native call timed out'
        return self.uc.reg_read(regs.UC_ARM64_REG_W0)

    def pointer(self, address):
        return struct.unpack('<Q', self.uc.mem_read(address, 8))[0]
