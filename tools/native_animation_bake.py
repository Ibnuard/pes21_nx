"""Offline ARM64 animation-math evaluator for an owned PES21 Mobile library.

Only memory allocation/copy imports are implemented. No file, network, Android,
UE process initialization or host code execution is provided. The input ELF and
all decoded game poses stay local; this module contains no native code payload.
Requires pyelftools and unicorn when the optional converter is used.
"""
import io, struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED
from unicorn.arm64_const import *

class NativeAnimationVM:
    def __init__(self, path):
        self.raw=Path(path).read_bytes(); self.elf=ELFFile(io.BytesIO(self.raw))
        self.uc=Uc(UC_ARCH_ARM64,UC_MODE_ARM)
        self.uc.mem_map(0x10000000,0x10000)
        self.uc.mem_map(0x20000000,0x1000000)
        self.uc.mem_map(0x30000000,0x10000)
        self.cursor=0x20000000; self.stub_cursor=0x30000000; self.stubs={}
        self.symbols=list(self.elf.get_section_by_name('.dynsym').iter_symbols())
        self.names={s.name:s['st_value'] for s in self.symbols if s['st_value']}
        for s in self.elf.iter_segments():
            if s['p_type']!='PT_LOAD':continue
            a=s['p_vaddr']&~4095; n=(s['p_vaddr']+s['p_memsz']+4095)&~4095
            self.uc.mem_map(a,n-a); self.uc.mem_write(s['p_vaddr'],s.data())
        # Link defined ELF symbols and relative data; imports remain sealed stubs.
        for section in ('.rela.dyn','.rela.plt'):
            for r in self.elf.get_section_by_name(section).iter_relocations():
                typ=r['r_info_type']; s=self.symbols[r['r_info_sym']]
                if typ==1027: value=r['r_addend']
                elif typ in (257,1025,1026):
                    value=self.target(s.name)+r['r_addend']
                else: continue
                self.uc.mem_write(r['r_offset'],struct.pack('<Q',value))
        # Internal functions bypass ELF interposition; override allocator leaves.
        for name in ('BasicMalloc','BasicFree','_ZN3fox21AllocAlignedAnnotatedEmmj',
                     '_Znwm','_ZdlPv','memcpy','memset','memmove'):
            if name in self.names:
                dest=self.stub(name)
                self.uc.mem_write(self.names[name],struct.pack('<IIQ',0x58000050,0xd61f0200,dest))
        self.uc.hook_add(UC_HOOK_CODE,self.on_stub,begin=0x30000000,end=0x3000ffff)
        self.uc.hook_add(UC_HOOK_MEM_UNMAPPED,self.invalid)

    def stub(self,name):
        p=self.stub_cursor;self.stub_cursor+=4;self.stubs[p]=name
        assert self.stub_cursor<0x30010000
        self.uc.mem_write(p,struct.pack('<I',0xd65f03c0));return p
    def target(self,name):return self.names.get(name) or self.stub(name)
    def alloc(self,size,data=None):
        assert 0<=size<=0x100000
        p=self.cursor;self.cursor+=(size+15)&~15
        assert self.cursor<0x21000000
        if data is not None:self.uc.mem_write(p,bytes(data))
        return p
    def invalid(self,uc,access,address,size,value,user):
        raise RuntimeError(f'unmapped {address:x} pc {uc.reg_read(UC_ARM64_REG_PC):x}')
    def on_stub(self,uc,address,size,user):
        name=self.stubs[address];args=[uc.reg_read(UC_ARM64_REG_X0+i) for i in range(4)]
        if name in ('BasicMalloc','_Znwm','_ZN3fox21AllocAlignedAnnotatedEmmj'):
            uc.reg_write(UC_ARM64_REG_X0,self.alloc(args[0]))
        elif name in ('BasicFree','_ZdlPv'):pass
        elif name in ('memcpy','memmove'):
            uc.mem_write(args[0],bytes(uc.mem_read(args[1],args[2])))
        elif name=='memset':uc.mem_write(args[0],bytes([args[1]&255])*args[2])
        else:raise RuntimeError(f'unimplemented {name} args {args} lr {uc.reg_read(UC_ARM64_REG_X30):x}')
    def call(self,name,*args,floats=()):
        for i,a in enumerate(args):self.uc.reg_write(UC_ARM64_REG_X0+i,a)
        for i,a in enumerate(floats):self.uc.reg_write(UC_ARM64_REG_S0+i,struct.unpack('<I',struct.pack('<f',a))[0])
        self.uc.reg_write(UC_ARM64_REG_SP,0x10010000)
        self.uc.reg_write(UC_ARM64_REG_X30,0x10000000)
        self.uc.emu_start(self.names[name],0x10000000,count=2000000)
        if self.uc.reg_read(UC_ARM64_REG_PC)!=0x10000000:raise RuntimeError('instruction limit '+name)
        return self.uc.reg_read(UC_ARM64_REG_X0)
    def read(self,p,n):return bytes(self.uc.mem_read(p,n))
