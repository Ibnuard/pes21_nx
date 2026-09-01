"""Read-only ABI audit for the isolated native-pad experiment (owned PES21 ELF)."""
import argparse
import json
import re
import struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from capstone.arm64 import ARM64_OP_REG, ARM64_OP_IMM, ARM64_OP_MEM


def audit(path):
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        symbols = list(elf.get_section_by_name('.dynsym').iter_symbols())
        names = {s.name: s for s in symbols}
        relocs = {}
        for relocation in elf.get_section_by_name('.rela.dyn').iter_relocations():
            value = relocation['r_addend']
            if relocation['r_info_sym']:
                value += symbols[relocation['r_info_sym']]['st_value']
            relocs[relocation['r_offset']] = value

        def read(address, size):
            stream.seek(next(elf.address_offsets(address)))
            return stream.read(size)

        # Tiny straight-line constant tracker, not an ARM emulator. Only use
        # known register values and known ELF loads. Never execute the library.
        decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
        decoder.detail = True
        base = 0x10000000000

        def stores(symbol):
            sym = names[symbol]
            registers, memory = {'x0': base, 'xzr': 0}, {}

            def reg(op):
                return decoder.reg_name(op.reg).replace('w', 'x', 1)

            def value(op):
                if op.type == ARM64_OP_IMM:
                    return op.imm << op.shift.value
                if op.type == ARM64_OP_REG:
                    return registers.get(reg(op))
                return None

            for instruction in decoder.disasm(read(sym['st_value'], sym['st_size']), sym['st_value']):
                op, mnemonic = instruction.operands, instruction.mnemonic
                if mnemonic in ('mov', 'adrp', 'adr') and op[0].type == ARM64_OP_REG:
                    registers[reg(op[0])] = value(op[1])
                elif mnemonic == 'add' and op[0].type == ARM64_OP_REG:
                    a, b = value(op[1]), value(op[2])
                    registers[reg(op[0])] = a+b if a is not None and b is not None else None
                elif mnemonic in ('ldr', 'ldur') and op[0].type == ARM64_OP_REG and op[1].type == ARM64_OP_MEM:
                    source = registers.get(decoder.reg_name(op[1].mem.base))
                    result = None
                    if source is not None and not op[1].mem.index:
                        address = source+op[1].mem.disp
                        if address in relocs:
                            result = relocs[address]
                        elif address < base:
                            try:
                                result = int.from_bytes(read(address, 8), 'little')
                            except StopIteration:
                                pass
                    registers[reg(op[0])] = result
                elif mnemonic in ('str', 'stur') and op[1].type == ARM64_OP_MEM:
                    source = registers.get(decoder.reg_name(op[1].mem.base))
                    item = value(op[0])
                    if source is not None and item is not None and not op[1].mem.index:
                        memory[source+op[1].mem.disp-base] = item
                elif mnemonic in ('bl', 'blr'):
                    for i in range(19):
                        registers.pop('x'+str(i), None)
            return memory

        work = stores('_ZN5match3pad17ThinkUnitListWorkC2Ev')
        table = stores('_ZN5match3pad13ThinkUnitListC1Ev')
        vtables = {s['st_value']+16: s.name for s in symbols if s.name.startswith('_ZTV')}
        units = []
        for kind in range(97):
            offset = table.get(0x3bf8+kind*8, base)-base
            units.append({'kind': kind, 'offset': hex(offset),
                          'vtable': vtables.get(work.get(offset), '?'),
                          'pad_key': work.get(offset+8),
                          'enabled': work.get(offset+0x18)})
        plt = elf.get_section_by_name('.plt')['sh_addr']
        entries = {}
        for i, r in enumerate(elf.get_section_by_name('.rela.plt').iter_relocations()):
            name = symbols[r['r_info_sym']].name
            if name in (
                '_ZN5match3pad13ThinkUnitList6UpdateERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindEj',
                '_ZN5match8registry12PadInputUnit6UpdateEjPKNS0_9KeyConfigEPKNS0_9MatchInfoE',
            ):
                address = plt+32+i*16
                entries[name] = {'address': hex(address),
                                 'words': [hex(x) for x in struct.unpack('<4I', read(address,16))]}
        return {'units': units, 'plt': entries,
                'pad_key_to_cobra_key': list(struct.unpack('<36I', read(0x81ce140, 144))),
                'cobra_key_to_mask': [hex(x) for x in struct.unpack('<32I', read(0x8595270, 128))]}


def check_source(result, source):
    content = source.read_text(encoding='utf-8')
    checked = 0
    for kind, symbol in re.findall(r'\{(\d+), "(_ZTV[^"]+)", 0\}', content):
        assert result['units'][int(kind)]['vtable'] == symbol, (kind, symbol)
        checked += 1
    assert checked == 24
    for entry in result['plt'].values():
        assert entry['address'] in content
        assert all(word in content for word in entry['words'])
    assert len(result['plt']) == 2
    # Native action keys: B pass, A loft/slide, X through, Y shoot/friend press.
    key_map = result['pad_key_to_cobra_key']
    assert [key_map[x] for x in (14,13,12,15,18,17,19,10)] == [0,1,3,2,0,1,2,4]
    return {'unit_types_checked': checked, 'plt_stubs_checked': 2,
            'native_button_table_checked': True, 'device_tested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=Path('dist/pes21_nx/libUE4.so'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-source', type=Path)
    args = parser.parse_args()
    report = audit(args.library)
    if args.check_source:
        report['validation'] = check_source(report, args.check_source)
    result = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(result, encoding='utf-8')
        print(args.output)
    else:
        print(result)
