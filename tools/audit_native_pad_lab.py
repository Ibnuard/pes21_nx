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
        action_methods = (
            ('_ZTVN5match3pad21ThinkUnitSetplayGuideE',
             '_ZN5match3pad21ThinkUnitSetplayGuide4MainERKNS0_18ThinkUnitInputDataENS0_13ThinkUnitKindE'),
            ('_ZTVN5match3pad18ThinkUnitShortPassE',
             '_ZN5match3pad18ThinkUnitShortPass9ExecPressERKNS0_18ThinkUnitInputDataE'),
            ('_ZTVN5match3pad18ThinkUnitShortPassE',
             '_ZN5match3pad18ThinkUnitShortPass8ExecPullERKNS0_18ThinkUnitInputDataE'),
            ('_ZTVN5match3pad17ThinkUnitLongPassE',
             '_ZN5match3pad17ThinkUnitLongPass9ExecPressERKNS0_18ThinkUnitInputDataE'),
            ('_ZTVN5match3pad17ThinkUnitLongPassE',
             '_ZN5match3pad17ThinkUnitLongPass8ExecPullERKNS0_18ThinkUnitInputDataE'),
            ('_ZTVN5match3pad14ThinkUnitShootE',
             '_ZN5match3pad14ThinkUnitShoot9ExecPressERKNS0_18ThinkUnitInputDataE'),
            ('_ZTVN5match3pad14ThinkUnitShootE',
             '_ZN5match3pad14ThinkUnitShoot8ExecPullERKNS0_18ThinkUnitInputDataE'),
            ('_ZTVN5match3pad28ThinkUnitGoalkickPassSupportE',
             '_ZN5match3pad28ThinkUnitGoalkickPassSupport8ExecPullERKNS0_18ThinkUnitInputDataE'),
        )
        action_audit = []
        for vtable_name, method_name in action_methods:
            vtable, method = names[vtable_name], names[method_name]
            begin = vtable['st_value']
            end = begin + vtable['st_size']
            slots = [offset for offset, value in relocs.items()
                     if begin <= offset < end and value == method['st_value']]
            if not slots:
                raise AssertionError((vtable_name, method_name))
            action_audit.append({'vtable': vtable_name,
                                 'method': method_name,
                                 'slots': [hex(slot) for slot in slots]})
        two_player_symbols = {}
        for name in (
            '_ZN9matchPlan4Data10SetPadPortE8HomeAwayj',
            '_ZN9matchPlan4Data10GetPadPortE8HomeAway',
            '_ZNK5match8registry10CursorInfo14IsUserPlayTeamE8HomeAway',
            '_ZN9game_mode13MatchListener22SetCursorInfoFromTmpdbEPN5match8registry10CursorInfoEjib',
        ):
            symbol = names[name]
            two_player_symbols[name] = {
                'address': hex(symbol['st_value']),
                'size': symbol['st_size'],
            }
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
        cursor_info_symbol = names[
            '_ZN9game_mode13MatchListener22SetCursorInfoFromTmpdbEPN5match8registry10CursorInfoEjib'
        ]
        cursor_info_words = list(struct.unpack(
            '<4I', read(cursor_info_symbol['st_value'], 16)))
        return {'units': units, 'plt': entries,
                'setplay_action_methods': action_audit,
                'two_player_symbols': two_player_symbols,
                'cursor_info_entry_words': [hex(x) for x in cursor_info_words],
                # Pad::GetAxis uses this six-byte boundary table. The last
                # two pairs resolve to value slots 16..19 (left stick) and
                # 20..23 (right stick) in cobra::game::Pad.
                'cobra_axis_pair_boundaries': list(read(0x8595268, 6)),
                'pad_key_to_cobra_key': list(struct.unpack('<36I', read(0x81ce140, 144))),
                'cobra_key_to_mask': [hex(x) for x in struct.unpack('<32I', read(0x8595270, 128))]}


def check_source(result, source):
    content = source.read_text(encoding='utf-8')
    checked = 0
    for kind, symbol in re.findall(r'\{(\d+), "(_ZTV[^"]+)", 0\}', content):
        assert result['units'][int(kind)]['vtable'] == symbol, (kind, symbol)
        checked += 1
    assert checked == 32
    for kind in (26, 64, 65, 70, 72, 75, 90, 95):
        assert result['units'][kind]['vtable'] != '?', kind
    for entry in result['setplay_action_methods']:
        assert entry['method'] in content
    assert len(result['setplay_action_methods']) == 8
    for symbol in (
        '_ZN9matchPlan4Data10SetPadPortE8HomeAwayj',
        '_ZN9matchPlan4Data10GetPadPortE8HomeAway',
    ):
        assert symbol in source.parent.joinpath('ue4_hooks.c').read_text(
            encoding='utf-8')
    assert len(result['two_player_symbols']) == 4
    assert result['cursor_info_entry_words'] == [
        '0xd10783ff', '0xa9186ffc', '0xa91967fa', '0xa91a5ff8'
    ]
    hooks = source.parent.joinpath('ue4_hooks.c').read_text(encoding='utf-8')
    assembly = source.parent.joinpath('cobra_pad_hook.s').read_text(
        encoding='utf-8')
    assert 'pes_match_cursor_info_from_tmpdb_resume' in hooks
    assert 'pes_match_cursor_info_from_tmpdb_hook' in assembly
    for entry in result['plt'].values():
        assert entry['address'] in content
        assert all(word in content for word in entry['words'])
    assert len(result['plt']) == 2
    # Native action keys: B pass, A loft/slide, X through, Y shoot/friend press.
    key_map = result['pad_key_to_cobra_key']
    assert [key_map[x] for x in (14,13,12,15,18,17,19,10)] == [0,1,3,2,0,1,2,4]
    assert result['units'][64]['pad_key'] == 10
    assert result['cobra_axis_pair_boundaries'] == [0, 5, 8, 11, 14, 16]
    assert 'pad + 140 + 20 * 4' in source.parent.joinpath('ue4_hooks.c').read_text(encoding='utf-8')
    shim = source.parent.joinpath('android_shim.c').read_text(encoding='utf-8')
    assert 'HidNpadIdType_No2' in shim
    assert 'padConfigureInput(2, HidNpadStyleSet_NpadStandard)' in shim
    return {'unit_types_checked': checked, 'plt_stubs_checked': 2,
            'setplay_action_methods_checked': 8,
            'two_player_ownership_symbols_checked': 4,
            'cursor_info_post_hook_checked': True,
            'native_button_table_checked': True,
            'goalkick_support_key_checked': True,
            'dual_stick_axis_layout_checked': True, 'device_tested': False}


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
