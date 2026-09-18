"""Optional local ELF audit. Native bytes are read locally, never copied to git."""
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'dist/pes21_nx/libUE4.so'


@unittest.skipUnless(LIBRARY.is_file(), 'requires ignored compatible libUE4.so fixture')
class StadiumNativeAbiTests(unittest.TestCase):
    def test_rematch_stadium_snapshot_and_console_integer_abi(self):
        try:
            from elftools.elf.elffile import ELFFile
        except ImportError:
            self.skipTest('requires pyelftools')
        names = [
            '_ZNK5tmpdb5Match19GetStadiumInitParamEv',
            '_ZN5tmpdb5Match19SetStadiumInitParamERKN6common9InitParamE',
            '_ZN5tmpdb5Match11SetTimeZoneEN6common12TimeZoneTypeE',
            '_ZNK16FConsoleVariableIiE6GetIntEv',
            '_ZN16FConsoleVariableIiE3SetEPKDs21EConsoleVariableFlags',
            '_ZNK20FConsoleVariableBase8GetFlagsEv',
            '_ZTV16FConsoleVariableIiE', '_ZN15IConsoleManager9SingletonE',
            '_ZNK15FConsoleManager19FindConsoleVariableEPKDs',
        ]
        with LIBRARY.open('rb') as f:
            elf = ELFFile(f)
            symbols = elf.get_section_by_name('.dynsym')
            found = {s.name: s.entry for s in symbols.iter_symbols() if s.name in names}
            self.assertEqual(set(found), set(names))
            def words(addr, count):
                f.seek(next(elf.address_offsets(addr)))
                return struct.unpack('<' + 'I'*count, f.read(4*count))
            # Rule lives at Match+0x13c. Renderer snapshot is separately
            # copied from Match+0x170 through hidden x8, including its tail.
            self.assertEqual(words(found[names[2]]['st_value'], 2), (0xb9013c01, 0xd65f03c0))
            self.assertEqual(found[names[0]]['st_size'], 60)
            self.assertEqual(words(found[names[0]]['st_value']+4, 1), (0x3dc05c01,))
            self.assertEqual(words(found[names[0]]['st_value']+44, 1), (0xf9005109,))
            # Native initializer copies input TimeZone to InitParam+4.
            self.assertEqual(words(0x6d827f0,3), (0xb94003a8,0xeb1a029f,0xb9006fe8))
            table = found[names[6]]
            self.assertEqual(table['st_size'],160)
            entries = []
            for r in elf.get_section_by_name('.rela.dyn').iter_relocations():
                if table['st_value']+16 <= r['r_offset'] < table['st_value']+160:
                    base = symbols.get_symbol(r['r_info_sym'])['st_value'] if r['r_info_sym'] else 0
                    entries.append(base+r['r_addend'])
            for name in names[3:6]:
                self.assertIn(found[name]['st_value'], entries)
            # MatchMain retains both native speed refresh call sites. No
            # wrapper timing override is necessary to keep gameplay speed.
            for addr in (0x7bf9920, 0x7bf9ad4):
                instruction = words(addr,1)[0]
                imm = instruction & 0x3ffffff
                if imm & 0x2000000: imm -= 0x4000000
                self.assertEqual(addr+imm*4,0x3930c60)
            # Native view initialization writes the bounded cascade count to
            # FSceneView+0x278; directional-light shadow gathering reads it.
            self.assertEqual(words(0x4d59c30, 5),
                             (0x6b18011f, 0x1a98b109, 0x7100011f,
                              0x1a89b3e8, 0xb9027a68))
            self.assertEqual(words(0x5421710, 1), (0xb9427821,))
            # GetNumShadowMappedCascades clamps the component count to this
            # view limit instead of unconditionally rendering every cascade.
            self.assertEqual(words(0x5423154, 2), (0x6b13011f, 0x1a88c260))
            stream_offset = next(elf.address_offsets(0x7f0e1da))
            f.seek(stream_offset)
            label = 'r.Shadow.CSM.MaxCascades'.encode('utf-16-le')
            self.assertEqual(f.read(len(label)), label)

    def test_shadow_hook_prologues_and_proxy_lifecycle_slots(self):
        try:
            from elftools.elf.elffile import ELFFile
        except ImportError:
            self.skipTest('requires pyelftools')
        expected = {
            '_ZN20UStaticMeshComponent16CreateSceneProxyEv':
                (0xa9be4ff4, 0xa9017bfd, 0x910043fd, 0xf942d809),
            '_ZN29FGatherShadowPrimitivesPacket25FilterPrimitiveForShadowsERK16FBoxSphereBounds22FPrimitiveFlagsCompactP19FPrimitiveSceneInfoP20FPrimitiveSceneProxy':
                (0xd101c3ff, 0xa9016ffc, 0xa90267fa, 0xa9035ff8),
        }
        extra = ['_ZTV20UStaticMeshComponent', '_ZTV21FStaticMeshSceneProxy',
                 '_ZN21FStaticMeshSceneProxyD1Ev', '_ZN21FStaticMeshSceneProxyD0Ev',
                 '_ZNK18UObjectBaseUtility11GetPathNameEPK7UObjectR7FString',
                 '_ZN7FMemory4FreeEPv',
                 '_ZNK5match8registry8BallInfo16GetFutureMoveVecEj',
                 '_ZN5match6camera6plugin12InplayCamera23ShotBroadcastBallActiveERN4draw15CameraParameterERKNS2_7DATA_TVE']
        needed = set(expected) | set(extra)
        with LIBRARY.open('rb') as f:
            elf = ELFFile(f)
            found = {s.name: s.entry for s in elf.get_section_by_name('.dynsym').iter_symbols()
                     if s.name in needed}
            self.assertEqual(set(found), needed)
            for name, words in expected.items():
                offset = next(elf.address_offsets(found[name]['st_value']))
                f.seek(offset)
                self.assertEqual(struct.unpack('<4I', f.read(16)), words, name)
            f.seek(next(elf.address_offsets(0x37ec320)))
            self.assertEqual(struct.unpack('<4I', f.read(16)),
                             (0x9002e650,0xf941f611,0x910fa210,0xd61f0220))
            call=found[extra[-1]]['st_value']+0xd6c
            f.seek(next(elf.address_offsets(call)))
            instruction=struct.unpack('<I',f.read(4))[0]
            self.assertEqual(instruction,0x9746368b)
            imm=instruction & 0x03ffffff
            if imm & 0x02000000: imm -= 0x04000000
            self.assertEqual(call+imm*4,0x37ec320)
            # Confirm this is precisely GetFutureMoveVec's PLT, not a nearby
            # physics getter. This also validates the saved return-PC scope.
            plt=elf.get_section_by_name('.plt')['sh_addr']
            symbols=elf.get_section_by_name('.dynsym')
            plt_index=(0x37ec320-plt-32)//16
            r=elf.get_section_by_name('.rela.plt').get_relocation(plt_index)
            self.assertEqual(symbols.get_symbol(r['r_info_sym']).name,extra[-2])
            # Lifecycle vtables are data relocations, not executable aliases.
            tables = {'_ZTV20UStaticMeshComponent': (312, [next(iter(expected))]),
                      '_ZTV21FStaticMeshSceneProxy': (52, extra[2:4])}
            ranges = [(found[n]['st_value'], found[n]['st_value']+found[n]['st_size'])
                      for n in tables]
            relocations = {}
            symbols = elf.get_section_by_name('.dynsym')
            for r in elf.get_section_by_name('.rela.dyn').iter_relocations():
                if any(lo <= r['r_offset'] < hi for lo, hi in ranges):
                    value = symbols.get_symbol(r['r_info_sym'])['st_value'] if r['r_info_sym'] else 0
                    relocations[r['r_offset']] = value + r['r_addend']
            for name, (slots, methods) in tables.items():
                table = found[name]
                self.assertEqual(table['st_size'], slots*8)
                entries = [relocations.get(table['st_value']+i*8) for i in range(2, slots)]
                for method in methods:
                    self.assertIn(found[method]['st_value'], entries, method)
