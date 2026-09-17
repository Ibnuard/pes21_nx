"""Optional local ELF audit. Native bytes are read locally, never copied to git."""
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'dist/pes21_nx/libUE4.so'


@unittest.skipUnless(LIBRARY.is_file(), 'requires ignored compatible libUE4.so fixture')
class StadiumNativeAbiTests(unittest.TestCase):
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
