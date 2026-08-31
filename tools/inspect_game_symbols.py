"""Read-only ELF symbol/disassembly inspection of a user-owned native library."""
import argparse
from contextlib import redirect_stdout
import re
from pathlib import Path

from elftools.elf.elffile import ELFFile


def inspect(path, pattern, disassemble=False, limit=1200):
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        symbols = list(elf.get_section_by_name('.dynsym').iter_symbols())
        by_address = {s['st_value']: s.name for s in symbols if s['st_value']}
        plt, relocations = elf.get_section_by_name('.plt'), elf.get_section_by_name('.rela.plt')
        if plt and relocations:
            for index, relocation in enumerate(relocations.iter_relocations()):
                by_address[plt['sh_addr']+32+index*16] = symbols[relocation['r_info_sym']].name+'@plt'
        if disassemble:
            from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
            decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        for symbol in symbols:
            if not re.search(pattern, symbol.name, re.I):
                continue
            address, size = symbol['st_value'], symbol['st_size']
            print(f'{address:08x} {size:6d} {symbol.name}')
            if not disassemble or not address or symbol['st_info']['type'] != 'STT_FUNC':
                continue
            offsets = list(elf.address_offsets(address))
            if not offsets:
                continue
            stream.seek(offsets[0])
            for instruction in decoder.disasm(stream.read(min(size, limit)), address):
                note = ''
                if instruction.mnemonic in ('bl', 'b') and instruction.op_str.startswith('#'):
                    note = by_address.get(int(instruction.op_str[1:], 16), '')
                print(f'  {instruction.address:08x} {instruction.bytes.hex()} '
                      f'{instruction.mnemonic:8} {instruction.op_str:35} {note}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pattern')
    parser.add_argument('--library', type=Path, default=Path('local-debug/apk-arm64/libUE4.so'))
    parser.add_argument('--disassemble', action='store_true')
    parser.add_argument('--limit', type=int, default=1200)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('w', encoding='utf-8') as out, redirect_stdout(out):
            inspect(args.library, args.pattern, args.disassemble, args.limit)
        print(args.output)
    else:
        inspect(args.library, args.pattern, args.disassemble, args.limit)
