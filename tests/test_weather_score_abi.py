"""Optional exact-runtime ABI gates; proprietary input stays local."""
import hashlib
import io
from pathlib import Path
import re
import struct
import unittest

ROOT=Path(__file__).resolve().parents[1]

class WeatherScoreAbiTests(unittest.TestCase):
    def test_owned_mobile_runtime_bindings_and_patch_sites(self):
        path=ROOT/'dist/pes21_nx/libUE4.so'
        if not path.is_file(): self.skipTest('compatible local libUE4.so required')
        try:
            from elftools.elf.elffile import ELFFile
        except ImportError: self.skipTest('pyelftools required for local ELF verification')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!='a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187':
            self.skipTest('this ABI test requires the compatible Mobile v5.3.0 library')
        elf=ELFFile(io.BytesIO(raw))
        ds=elf.get_section_by_name('.dynsym').data(); ss=elf.get_section_by_name('.dynstr').data()
        names={}
        for offset in range(0,len(ds),24):
            n=struct.unpack_from('<I',ds,offset)[0]
            names[ss[n:ss.index(b'\0',n)].decode()]=struct.unpack_from('<Q',ds,offset+8)[0]
        for f in ('native_weather.inc','weather_scene.inc','scoreboard_runtime.inc','referee_probe.inc'):
            for symbol in re.findall(r'"(_Z[^"]+|GWorld)"',(ROOT/'source'/f).read_text()):
                with self.subTest(symbol=symbol): self.assertIn(symbol,names)
        sites={
            0x387b510:(0x9002e410,0xf9467211,0x91338210,0xd61f0220),
            0x38e8680:(0xd002e250,0xf942ce11,0x91166210,0xd61f0220),
            0x38c3dc0:(0xb002e2f0,0xf9409e11,0x9104e210,0xd61f0220),
            0x38dd250:(0xf002e270,0xf945c211,0x912e0210,0xd61f0220),
            0x38cf4a0:(0xd002e2b0,0xf9465611,0x9132a210,0xd61f0220),
            0x3924490:(0x9002e170,0xf9425211,0x91128210,0xd61f0220),
            0x38e71e0:(0xd002e250,0xf945a611,0x912d2210,0xd61f0220),
            0x37ed030:(0xf002e630,0xf9453a11,0x9129c210,0xd61f0220),
            0x381c230:(0x9002e590,0xf941ba11,0x910dc210,0xd61f0220),
        }
        for address,expected in sites.items():
            segment=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and
                         s['p_vaddr']<=address and address+16<=s['p_vaddr']+s['p_filesz'])
            offset=segment['p_offset']+address-segment['p_vaddr']
            with self.subTest(address=hex(address)):
                self.assertEqual(struct.unpack_from('<4I',raw,offset),expected)
        # Verify Mobile's own ordered weather labels, not PC enum assumptions.
        table=names['_ZN7fixdemo22NAME_CONDITION_WEATHERE']
        labels={}
        for address,_,target in struct.iter_unpack('<QQq',elf.get_section_by_name('.rela.dyn').data()):
            if table<=address<table+24:
                segment=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and
                             s['p_vaddr']<=target< s['p_vaddr']+s['p_filesz'])
                offset=segment['p_offset']+target-segment['p_vaddr']
                labels[(address-table)//8]=raw[offset:raw.index(b'\0',offset)].decode()
        self.assertEqual(labels,{0:'FINE',1:'RAIN',2:'SNOW'})
        # Actual Android callee reads scale XY at 0x1c and Z at 0x24.
        # Desktop FTransform is padded differently despite the same symbol.
        address=names['_ZN16UGameplayStatics22SpawnEmitterAtLocationEP6UWorldP15UParticleSystemRK10FTransformb14EPSCPoolMethod']+0x5c
        segment=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and
                     s['p_vaddr']<=address< s['p_vaddr']+s['p_filesz'])
        offset=segment['p_offset']+address-segment['p_vaddr']
        self.assertEqual(struct.unpack_from('<2I',raw,offset),(0xbd4026e0,0xf841c2e8))
        observer=names['_ZN5match6record17ObserverOutOfPlay4ExecERNS_8registry11RecordEventERKNS0_13ObserverInputE']
        for relative,expected in ((0x64,0x52800481),(0x80,0x91005280)):
            address=observer+relative
            segment=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and
                         s['p_vaddr']<=address< s['p_vaddr']+s['p_filesz'])
            offset=segment['p_offset']+address-segment['p_vaddr']
            self.assertEqual(struct.unpack_from('<I',raw,offset)[0],expected)
        # World/PSC fields used for optional FX initialization and diagnostics.
        def read(address, size):
            segment=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and
                         s['p_vaddr']<=address and address+size<=s['p_vaddr']+s['p_filesz'])
            offset=segment['p_offset']+address-segment['p_vaddr']
            return raw[offset:offset+size]
        # New field actor uses the same native root/mesh layout as the stadium.
        # FName travels by value as 8 bytes on Android, unlike the Win64 editor.
        scalar=names['_ZN24UMaterialInstanceDynamic23SetScalarParameterValueE5FNamef']
        root=names['_ZN6AActor23execK2_GetRootComponentEP7UObjectR6FFramePv']
        mesh=names['_ZN20UStaticMeshComponent13SetStaticMeshEP11UStaticMesh']
        for address,word in ((root+16,0xf940ac08),(mesh+40,0xf942d808),
                             (scalar+12,0xf90003e1)):
            with self.subTest(field_abi=hex(address)):
                self.assertEqual(struct.unpack('<I',read(address,4))[0],word)
        fx=names['_ZN6UWorld14CreateFXSystemEv']
        init=names['_ZN24UParticleSystemComponent16InitializeSystemEv']
        count=names['_ZNK24UParticleSystemComponent21GetNumActiveParticlesEv']
        dynamic=names['_ZN24UParticleSystemComponent32SendRenderDynamicData_ConcurrentEv']
        for address,word in ((fx+0x40,0xf940c668), (fx+0x60,0xf9021e60),
                             (init+0x6c,0x3942b268), (init+0x74,0xf9437e68),
                             (count+0x6c,0xb9877a68),
                             (dynamic+0x78,0xf9428260)):
            with self.subTest(layout=hex(address)):
                self.assertEqual(struct.unpack('<I',read(address,4))[0],word)
        # PitchSound's seven position selectors 24..30: referee is slot 29.
        # Its branch offset 60 enters the Mobile referee-position stub.
        self.assertEqual(read(0x820a55d,7),bytes((0,13,23,26,31,60,71)))
