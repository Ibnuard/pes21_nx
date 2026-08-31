"""Validate new visual-hook ABI/offsets against the owned PES21 ELF, offline."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile


def validate(library):
    with library.open('rb') as stream:
        elf = ELFFile(stream)
        symbols = {s.name: s for s in elf.get_section_by_name('.dynsym').iter_symbols()}

        def read(address, size):
            stream.seek(next(elf.address_offsets(address)))
            return stream.read(size)

        action = symbols['_ZN7match2D5Model7Manager6ActionEv']['st_value']
        disp = symbols['_ZN7match2D5Model4Base7SetDispEb']['st_value']
        alpha = symbols['_ZN10menusystem4Node8SetAlphaEf']
        root = symbols['_ZN10menusystem6Window7GetRootEv']
        assert struct.unpack('<4I', read(action,16)) == (0xa9bf7bf3,0xb9415808,0xaa0003f3,0x71000d1f)
        assert struct.unpack('<4I', read(disp,16)) == (0xf9400000,0xb4000060,0x12000021,0x16ed7a85)
        assert alpha['st_size'] == 84
        assert struct.unpack('<3I',read(root['st_value'],12)) == (0xf9403c08,0xf9404900,0xd65f03c0)
        vt = symbols['_ZTVN7match2D5Model7ManagerE']
        slots = list(struct.unpack('<'+'Q'*(vt['st_size']//8), read(vt['st_value'],vt['st_size'])))
        # This Android ELF leaves symbol-based vtable pointers zero on disk.
        # Resolve the exact R_AARCH64_ABS64 relocations as the loader does.
        dynsym = elf.get_section_by_name('.dynsym')
        for relocation in elf.get_section_by_name('.rela.dyn').iter_relocations():
            offset = relocation['r_offset']-vt['st_value']
            if 0 <= offset < vt['st_size']:
                assert offset % 8 == 0 and relocation['r_info_type'] == 257
                target = dynsym.get_symbol(relocation['r_info_sym'])
                slots[offset//8] = target['st_value']+relocation['r_addend']
        assert action in slots and 2 <= slots.index(action) < 64
        # Audited native data table from CreateModel/GetModelType/Base ctor.
        table = read(0x85d8b10,17*4)
        paths = struct.unpack('<21Q',read(0x94af118,21*8))
        models = []
        for i in range(17):
            index, kind, priority, pad = table[i*4:i*4+4]
            assert index == i and 6 <= kind <= 18 and pad == 0
            name = read(paths[kind],100).split(b'\0')[0].decode('ascii')
            keep = i in (10,15,16)
            models.append({'index':i,'manager_offset':hex(0x160+i*8),'path':name,'keep_when_hidden':keep})
        assert 'd2_offside_line/' in models[10]['path']
        assert 'd2_shoot_gauge.' in models[15]['path']
        assert 'd2_shoot_base.' in models[16]['path']
        assert all('shoot' not in m['path'] for m in models if not m['keep_when_hidden'])
        stubs = {}
        for name in ('_ZNK5match8registry8ModeInfo5IsCupEN6common18MatchCompetitionIdE',
                     '_ZNK5match8registry8ModeInfo13IsGroupLeagueEN6common18MatchCompetitionIdE'):
            s = symbols[name]
            assert read(s['st_value'],8) == bytes.fromhex('e0031f2ac0035fd6')
            stubs[name] = 'returns false unconditionally'
        master = [n for n in symbols if 'MasterLeague' in n]
        return {'library':str(library),'model_action_vtable_index':slots.index(action),
                'prologues_match_runtime_guards':True,'model_slots':models,
                'setplay_alpha_changes_flash_color_only':True,
                'setplay_root':'Window::GetRoot (same root as native SetupSwf)',
                'master_league_symbols':master,'competition_stubs':stubs,
                'device_tested':False}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',type=Path,default=Path('local-debug/apk-arm64/libUE4.so'))
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=validate(a.library)
    with a.library.open('rb') as f:
        result['library_sha256']=hashlib.file_digest(f,'sha256').hexdigest()
    a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
