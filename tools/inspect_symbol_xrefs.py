"""List direct AArch64 branch callers of matching ELF symbols/PLT entries."""
import argparse
import bisect
import re
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
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

        decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        found = []
        for section in elf.iter_sections():
            if not section['sh_flags'] & 0x4:  # SHF_EXECINSTR
                continue
            for instruction in decoder.disasm(section.data(), section['sh_addr']):
                if instruction.mnemonic not in ('bl', 'b') or not instruction.op_str.startswith('#'):
                    continue
                target = int(instruction.op_str[1:], 16)
                if target not in targets:
                    continue
                index = bisect.bisect_right(starts, instruction.address) - 1
                caller = '?'
                if index >= 0 and instruction.address < functions[index][1]:
                    caller = functions[index][2]
                found.append((instruction.address, caller, target, targets[target]))

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
