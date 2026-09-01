"""List direct AArch64 branch callers of matching ELF symbols/PLT entries."""
import argparse
import bisect
import re
import struct
from pathlib import Path

from elftools.elf.elffile import ELFFile


def inspect(path: Path, pattern: str):
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        dynsym = elf.get_section_by_name('.dynsym')
        symbols = list(dynsym.iter_symbols())
        targets = {}
        for symbol in symbols:
            if symbol['st_value'] and re.search(pattern, symbol.name, re.I):
                targets[symbol['st_value']] = symbol.name

        plt = elf.get_section_by_name('.plt')
        rela_plt = elf.get_section_by_name('.rela.plt')
        if plt and rela_plt:
            for index, relocation in enumerate(rela_plt.iter_relocations()):
                name = symbols[relocation['r_info_sym']].name
                if re.search(pattern, name, re.I):
                    targets[plt['sh_addr'] + 32 + index * 16] = name + '@plt'

        functions = sorted(
            (symbol['st_value'], symbol['st_value'] + symbol['st_size'],
             symbol.name)
            for symbol in symbols
            if symbol['st_value'] and symbol['st_size'] and
            symbol['st_info']['type'] == 'STT_FUNC')
        starts = [item[0] for item in functions]

        found = []
        for section in elf.iter_sections():
            if not section['sh_flags'] & 0x4:  # SHF_EXECINSTR
                continue
            data = section.data()
            base = section['sh_addr']
            # Direct AArch64 B/BL use one signed imm26.  Decoding these four
            # bytes directly is much faster than disassembling the enormous
            # UE4 text section and is immune to literal/alignment islands.
            for offset in range(0, len(data) - 3, 4):
                word, = struct.unpack_from('<I', data, offset)
                opcode = word & 0xfc000000
                if opcode not in (0x14000000, 0x94000000):
                    continue
                immediate = word & 0x03ffffff
                if immediate & 0x02000000:
                    immediate -= 0x04000000
                address = base + offset
                target = address + immediate * 4
                if target not in targets:
                    continue
                index = bisect.bisect_right(starts, address) - 1
                caller = '?'
                if index >= 0 and address < functions[index][1]:
                    caller = functions[index][2]
                found.append((address, caller, target, targets[target]))

        for address, caller, target, name in found:
            print(f'{address:08x} {caller} -> {target:08x} {name}')
        if not found:
            print('no direct branch xrefs found')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pattern')
    parser.add_argument('--library', type=Path, required=True)
    args = parser.parse_args()
    inspect(args.library, args.pattern)
