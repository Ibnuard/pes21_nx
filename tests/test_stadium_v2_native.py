"""Optional owned-PES21 oracle for native Stadium geometry; no game data stored."""
from pathlib import Path
import importlib.util
import struct
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
LIBRARY=ROOT/'dist/pes21_nx/libUE4.so'


def native_anchor_oracle():
    from elftools.elf.elffile import ELFFile
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_UNMAPPED, UC_HOOK_CODE
    import unicorn.arm64_const as regs
    with LIBRARY.open('rb') as stream:
        elf=ELFFile(stream)
        segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
        uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
        def native_page(uc,access,address,size,value,user):
            page=address&~0xfff
            for seg in segments:
                start,end=seg['p_vaddr'],seg['p_vaddr']+seg['p_filesz']
                if start<=address<end:
                    uc.mem_map(page,4096)
                    lo,hi=max(page,start),min(page+4096,end)
                    stream.seek(seg['p_offset']+lo-start)
                    uc.mem_write(lo,stream.read(hi-lo))
                    return True
            return False
        uc.hook_add(UC_HOOK_MEM_UNMAPPED,native_page)
        stack,arena,stop=0x100000000,0x110000000,0x120000000
        uc.mem_map(stack,0x10000);uc.mem_map(arena,0x10000);uc.mem_map(stop,4096)
        camera,parameter,record=arena,arena+0x1000,arena+0x2000
        captured=[]
        def callee(uc,address,size,user):
            if address==0x384da00:  # ShotBroadcast -> ShotBroadcastBallActive
                captured.append(bytes(uc.mem_read(uc.reg_read(regs.UC_ARM64_REG_X2),88)))
                uc.reg_write(regs.UC_ARM64_REG_PC,uc.reg_read(regs.UC_ARM64_REG_LR))
            elif address==0x3890070:  # Native Change step, outside this oracle.
                uc.reg_write(regs.UC_ARM64_REG_PC,uc.reg_read(regs.UC_ARM64_REG_LR))
        uc.hook_add(UC_HOOK_CODE,callee)
        # Do not assume that UI distance 2 means float .2. The native getter
        # inverts distance (1 - value/10), unlike height and panning.
        settings = arena+0x3000
        uc.mem_write(settings,bytes([12,0,2,3,6]))
        normalized=[]
        for address in (0x67faf38,0x67faf70,0x67fafa0):
            uc.reg_write(regs.UC_ARM64_REG_X0,settings)
            uc.reg_write(regs.UC_ARM64_REG_LR,stop)
            uc.emu_start(address,stop,count=30)
            normalized.append(struct.unpack('<f',struct.pack('<I',uc.reg_read(regs.UC_ARM64_REG_S0)))[0])
        assert all(abs(a-b)<.0001 for a,b in zip(normalized,(.8,.3,.6))),normalized
        uc.mem_write(camera+8,struct.pack('<I3f',6,*normalized))
        uc.reg_write(regs.UC_ARM64_REG_SP,stack+0x8000)
        uc.reg_write(regs.UC_ARM64_REG_X0,camera)
        uc.reg_write(regs.UC_ARM64_REG_X1,parameter)
        uc.reg_write(regs.UC_ARM64_REG_LR,stop)
        uc.emu_start(0x665d7e0,stop,count=3000)
        assert uc.reg_read(regs.UC_ARM64_REG_PC)==stop and len(captured)==1
        data=struct.unpack('<22f',captured[0])
        assert abs(data[4]-70)<.0001 and abs(data[2]*data[4]-21)<.0001, data
        assert abs(data[3]-.5)<.0001, data[3]
        # Execute ground target-height shaping, not just synthetic eye stores.
        uc.mem_write(record,captured[0])
        uc.reg_write(regs.UC_ARM64_REG_X20,record)
        uc.mem_write(stack+0x8000+0x134,struct.pack('<f',.11))
        uc.emu_start(0x665e258,0x665e290,count=40)
        target_y=struct.unpack('<f',uc.mem_read(stack+0x8000+0x134,4))[0]
        assert abs(target_y-.5)<.0001,target_y
        # Native neutral gameplay zoom expression (centre ball, not a future
        # pass). This is a reference frame, NOT a claim of constant native FOV.
        pitch_size,ball=arena+0x4000,arena+0x5000
        uc.mem_write(pitch_size,struct.pack('<2f',52.5,34))
        uc.mem_write(ball,struct.pack('<3f',0,.11,0))
        uc.mem_write(stack+0x8000+0x50,struct.pack('<Q',pitch_size))
        uc.mem_write(stack+0x8000+0x5c,struct.pack('<f',52.5))
        uc.mem_write(stack+0x8000+0x130,struct.pack('<3f',0,target_y,0))
        uc.reg_write(regs.UC_ARM64_REG_X26,ball)
        uc.reg_write(regs.UC_ARM64_REG_W23,6)
        for reg,value in ((regs.UC_ARM64_REG_S10,34),(regs.UC_ARM64_REG_S15,.2),
                          (regs.UC_ARM64_REG_S11,0),(regs.UC_ARM64_REG_S9,1)):
            uc.reg_write(reg,struct.unpack('<I',struct.pack('<f',value))[0])
        uc.emu_start(0x665e2bc,0x665e474,count=150)
        zoom=struct.unpack('<f',struct.pack('<I',uc.reg_read(regs.UC_ARM64_REG_S0)))[0]
        assert abs(zoom-1.2)<.0001,zoom
        uc.reg_write(regs.UC_ARM64_REG_S13,uc.reg_read(regs.UC_ARM64_REG_S0))
        uc.reg_write(regs.UC_ARM64_REG_X19,parameter)
        uc.emu_start(0x665e868,0x665e88c,count=40)
        fov=struct.unpack('<f',uc.mem_read(parameter+0x34,4))[0]
        import math
        assert abs(math.degrees(fov)-17.292)<.001,fov
        # Execute the native final eye write with a centre-pitch target. This
        # establishes output offsets and the centre anchor, not native motion.
        uc.mem_write(record,captured[0])
        uc.mem_write(stack+0x8000+0x134,struct.pack('<f',target_y))
        uc.reg_write(regs.UC_ARM64_REG_X19,parameter)
        uc.reg_write(regs.UC_ARM64_REG_X20,record)
        uc.reg_write(regs.UC_ARM64_REG_W28,6)
        uc.reg_write(regs.UC_ARM64_REG_S0,0)
        uc.reg_write(regs.UC_ARM64_REG_S1,0)
        uc.emu_start(0x665e9b0,0x665e9f0,count=100)
        p=struct.unpack('<6f',uc.mem_read(parameter,24))
        assert all(abs(a-b)<.0001 for a,b in zip(p,(0,.5,0,0,21,70))),p
        # The new motion-only policy deliberately does NOT pin eye X to zero.
        # Execute native stores away from centre and preserve the exact lens:
        # Stadium's own pan ratio determines the rail position and hence tilt.
        assert abs(data[8]-.39)<.0001,data[8]
        for x in (-40.,-20.,0.,20.,40.):
            for z in (-25.,0.,25.):
                uc.mem_write(parameter,struct.pack('<24f',*([9.25]*24)))
                uc.mem_write(parameter+0x34,struct.pack('<f',fov))
                uc.reg_write(regs.UC_ARM64_REG_X19,parameter)
                uc.reg_write(regs.UC_ARM64_REG_X20,record)
                uc.reg_write(regs.UC_ARM64_REG_W28,6)
                uc.reg_write(regs.UC_ARM64_REG_S0,struct.unpack('<I',struct.pack('<f',z))[0])
                uc.reg_write(regs.UC_ARM64_REG_S1,struct.unpack('<I',struct.pack('<f',x))[0])
                uc.emu_start(0x665e9b0,0x665e9f0,count=100)
                output=struct.unpack('<24f',uc.mem_read(parameter,96))
                expected=(x,.5,z,x*data[8],21,70)
                assert all(abs(a-b)<.0001 for a,b in zip(output[:6],expected)),output
                assert output[13]==fov
                assert all(output[i]==9.25 for i in range(6,24) if i not in (13,14))
        print('Owned native D2/H3: distance .8, eye=(0,21,70), ground target Y=.5, neutral FOV=17.292 deg.')
        print('15 off-centre native eye writes: native X pan ratio .39, native height/rail/lens preserved.')


class NativeAnchorTests(unittest.TestCase):
    def test_native_centre_anchor(self):
        if not LIBRARY.is_file(): self.skipTest('optional owned compatible PES21 ELF unavailable')
        if not all(importlib.util.find_spec(n) for n in ('elftools','unicorn')):
            self.skipTest('optional pyelftools/unicorn unavailable')
        # Isolate Unicorn from pytest's Windows in-process hook machinery.
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--oracle'],
                              capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':
    if '--oracle' in sys.argv: native_anchor_oracle()
    else: unittest.main()
