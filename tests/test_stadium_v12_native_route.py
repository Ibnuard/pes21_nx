"""Native route/compiled trampoline checks; not on-device visual validation."""
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'dist/pes21_nx/libUE4.so'
BUILD = ROOT / 'local-debug/native-stadium-v12/pes21_nx.elf'


class NativeRouteTests(unittest.TestCase):
    def test_compatible_live_ball_branch_and_low_shadow_selector(self):
        if not LIBRARY.exists():
            self.skipTest('optional user-owned compatible ELF unavailable')
        from elftools.elf.elffile import ELFFile
        with LIBRARY.open('rb') as f:
            elf = ELFFile(f)
            def words(address, count):
                f.seek(next(elf.address_offsets(address)))
                return struct.unpack('<'+'I'*count, f.read(count*4))
            self.assertEqual(words(0x665c134, 4),
                             (0x39409288,0x35000788,0xf940f696,0x2a1f03e1))
            # The selected native branch copies the original GetTrans sample
            # from stack+0x110 into x25, sets its ordinary zoom=1.6, returns 1.
            self.assertEqual(words(0x665c228, 7),
                             (0x910443e8,0xeb19011f,0x540000a0,0xf9408be8,
                              0xf9000328,0xb9411be8,0xb9000b28))
            self.assertEqual(words(0x665c244, 4),
                             (0x529999a8,0x72a7f988,0x14000011,0xbd4113e1))
            # Camera-only target prediction contains both TeamAI registration
            # and predicted ball sampling; neither world registry is changed.
            for address, target in ((0x665c0f0,0x38a9190),(0x665ce28,0x38de130)):
                word=words(address,1)[0]; imm=word&0x3ffffff
                if imm&0x2000000: imm-=0x4000000
                self.assertEqual(address+imm*4,target)
            self.assertEqual(words(0x3f0bba4,1),(0x2a0003f4,))
            self.assertEqual(words(0x3f0bb9c,1),(0x2a0003f5,))
            self.assertEqual(words(0x3f0b610,5),
                             (0x710006bf,0x54000061,0x97e5eeba,0x14000002,0x97e584c4))

    def test_compiled_midfunction_trampoline_preserves_live_registers(self):
        if not BUILD.exists():
            self.skipTest('optional V12 cross-built ELF unavailable; build then rerun')
        try:
            from elftools.elf.elffile import ELFFile
            from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_UNMAPPED, UC_HOOK_CODE
            import unicorn.arm64_const as regs
        except ImportError:
            self.skipTest('optional pyelftools/unicorn unavailable')
        with BUILD.open('rb') as f:
            elf=ELFFile(f)
            symtab=elf.get_section_by_name('.symtab')
            def symbol(name):
                matches=symtab.get_symbol_by_name(name)
                self.assertTrue(matches, name)
                return matches[0]['st_value']
            entry=symbol('pes_stadium_ball_target_branch')
            selector=symbol('pes_stadium_ball_target_mode')
            normal_ptr=symbol('stadium_ball_target_native_resume')
            live_ptr=symbol('stadium_ball_target_live_resume')
            for selected in (0,1,3):
                with self.subTest(selected=selected):
                    uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
                    def page(uc,access,address,size,value,data):
                        base=address&~4095
                        uc.mem_map(base,4096)
                        offset=next(elf.address_offsets(base),None)
                        if offset is not None:
                            f.seek(offset);uc.mem_write(base,f.read(4096))
                        return True
                    uc.hook_add(UC_HOOK_MEM_UNMAPPED,page)
                    # Map the wrapper's two resume slots, including zeroed BSS.
                    for addr in (normal_ptr,live_ptr):
                        if not any(lo<=addr<=hi for lo,hi,_ in uc.mem_regions()):
                            page(uc,0,addr,8,0,None)
                    stack, camera, normal, live = 0x100008000,0x110000000,0x120000000,0x120001000
                    uc.mem_map(stack-0x8000,0x10000);uc.mem_map(camera,0x1000)
                    uc.mem_map(normal,0x2000)
                    uc.mem_write(normal_ptr,struct.pack('<Q',normal))
                    uc.mem_write(live_ptr,struct.pack('<Q',live))
                    uc.mem_write(camera+0x1e8,struct.pack('<Q',0x99887766))
                    original={}
                    for n in range(31):
                        reg=getattr(regs,f'UC_ARM64_REG_X{n}')
                        value=camera if n==20 else 0x12340000+n
                        original[reg]=value;uc.reg_write(reg,value)
                    vectors={}
                    for n in range(32):
                        reg=getattr(regs,f'UC_ARM64_REG_Q{n}')
                        value=(0x1122334455667700+n)<<64 | (0x7766554433221100+n)
                        vectors[reg]=value;uc.reg_write(reg,value)
                    uc.reg_write(regs.UC_ARM64_REG_SP,stack)
                    uc.reg_write(regs.UC_ARM64_REG_NZCV,0xa0000000)
                    uc.reg_write(regs.UC_ARM64_REG_CPACR_EL1,3<<20)
                    def visit(uc,address,size,data):
                        if address in (normal,live): uc.emu_stop()
                        elif address==selector:
                            self.assertEqual(uc.reg_read(regs.UC_ARM64_REG_X0),camera)
                            ret=uc.reg_read(regs.UC_ARM64_REG_LR)
                            # A hostile but ABI-conforming C callee exercises
                            # every volatile register, including SIMD high halves.
                            for n in range(19):uc.reg_write(getattr(regs,f'UC_ARM64_REG_X{n}'),0xfeed+n)
                            for n in range(32):
                                old=vectors[getattr(regs,f'UC_ARM64_REG_Q{n}')]
                                value=(0xbad<<64)|(old&((1<<64)-1)) if 8<=n<=15 else 0xbad
                                uc.reg_write(getattr(regs,f'UC_ARM64_REG_Q{n}'),value)
                            uc.reg_write(regs.UC_ARM64_REG_NZCV,0)
                            uc.reg_write(regs.UC_ARM64_REG_X0,selected)
                            uc.reg_write(regs.UC_ARM64_REG_PC,ret)
                    uc.hook_add(UC_HOOK_CODE,visit)
                    uc.emu_start(entry,0,count=500)
                    self.assertEqual(uc.reg_read(regs.UC_ARM64_REG_PC),live if selected else normal)
                    self.assertEqual(uc.reg_read(regs.UC_ARM64_REG_SP),stack)
                    self.assertEqual(uc.reg_read(regs.UC_ARM64_REG_NZCV),0xa0000000)
                    for n in range(31):
                        if n==17:continue # hook/continuation scratch
                        reg=getattr(regs,f'UC_ARM64_REG_X{n}'); expected=original[reg]
                        if n==8:expected=selected
                        elif n==1 and not selected:expected=0
                        elif n==22 and not selected:expected=0x99887766
                        self.assertEqual(uc.reg_read(reg),expected,f'x{n}')
                    for reg,value in vectors.items():self.assertEqual(uc.reg_read(reg),value)
