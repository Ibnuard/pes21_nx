"""Optional owned-ELF leaf oracle. Bounded ARM64 interpretation, no native execution."""
from pathlib import Path
import hashlib
import mmap
import os
import re
import struct
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def owned_corner():
    elfmod=pytest.importorskip('elftools.elf.elffile')
    capstone=pytest.importorskip('capstone')
    path=Path(os.environ.get('PESNX_NATIVE_LIBRARY',ROOT/'dist/pes21_nx/libUE4.so'))
    if not path.is_file():pytest.skip('ignored compatible owned libUE4.so required')
    with path.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()=='a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187'
        image=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ);elf=elfmod.ELFFile(image)
        dyn=elf.get_section_by_name('.dynsym');strings=elf.get_section(dyn['sh_link']).data()
        guards=re.findall(r'\{"([^"]+)",(\d+),0x([0-9a-f]+)u\}',
            (ROOT/'source/corner_tactics_native.inc').read_text())
        wanted={n:(int(size),int(h,16)) for n,size,h in guards};found={}
        for no,_,_,_,address,size in struct.iter_unpack('<IBBHQQ',dyn.data()):
            name=strings[no:strings.find(b'\0',no)].decode()
            if name not in wanted:continue
            assert size==wanted[name][0]
            off=next(elf.address_offsets(address));body=image[off:off+size];value=2166136261
            for byte in body:value=((value^byte)*16777619)&0xffffffff
            assert value==wanted[name][1]
            found[name]=(address,body)
        assert set(found)==set(wanted)
        tables={}
        for address,size in [(0x81ce104,16),(0x81ace24,8),(0x81ac398,4)]:
            off=next(elf.address_offsets(address));tables[address]=image[off:off+size]
        image.close()
    dis=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM);dis.detail=True
    return dis,found,tables

def interpret(dis,address,body,tables,argument):
    """Reject unmodelled instructions; memory reads only admitted ELF table bytes."""
    from capstone import arm64_const as arm
    instructions={i.address:i for i in dis.disasm(body,address)}
    registers={'0':argument};comparison=(0,0)
    def get(ins,o):
        if o.type==arm.ARM64_OP_IMM:return o.imm
        assert o.type==arm.ARM64_OP_REG
        name=ins.reg_name(o.reg)
        if name in ('wzr','xzr'):return 0
        value=registers.get(name[1:],0)
        return value & (0xffffffff if name[0]=='w' else 0xffffffffffffffff)
    def put(ins,o,value):
        name=ins.reg_name(o.reg);assert name not in ('wzr','xzr')
        registers[name[1:]]=value & (0xffffffff if name[0]=='w' else 0xffffffffffffffff)
    pc=address
    for _ in range(24):
        ins=instructions[pc];ops=ins.operands;m=ins.mnemonic;pc+=4
        if m=='ret':return registers['0']
        if m in ('sub','add','and','lsl'):
            a,b=get(ins,ops[1]),get(ins,ops[2])
            put(ins,ops[0],a-b if m=='sub' else a+b if m=='add' else a&b if m=='and' else a<<b)
        elif m in ('mov','adrp'):put(ins,ops[0],get(ins,ops[1]))
        elif m=='cmp':comparison=(get(ins,ops[0]),get(ins,ops[1]))
        elif m=='b.hi':
            if comparison[0]>comparison[1]:pc=ops[0].imm
        elif m=='cset':
            assert ins.cc==arm.ARM64_CC_EQ;put(ins,ops[0],int(comparison[0]==comparison[1]))
        elif m=='csinc':
            assert ins.cc==arm.ARM64_CC_NE
            put(ins,ops[0],get(ins,ops[1]) if comparison[0]!=comparison[1] else get(ins,ops[2])+1)
        elif m=='sxtb':
            value=get(ins,ops[1])&255;put(ins,ops[0],value if value<128 else value-256)
        elif m=='ldr':
            assert ops[1].type==arm.ARM64_OP_MEM
            base=registers[ins.reg_name(ops[1].mem.base)[1:]]
            index=registers[ins.reg_name(ops[1].mem.index)[1:]]
            at=base+(index<<ops[1].shift.value)+ops[1].mem.disp
            raw=next(data[at-start:at-start+4] for start,data in tables.items() if start<=at<=start+len(data)-4)
            put(ins,ops[0],int.from_bytes(raw,'little'))
        else:raise AssertionError('unmodelled opcode '+m)
    raise AssertionError('leaf oracle exceeded bound')

@pytest.mark.parametrize('kind,expected',[
    ('21ConvertOption2Tactics',[8,7,6,5,2,8,8]),
    ('32ConvertOption2ShortCornerTactics',[4,0,1,2,3,4,4]),
    ('25ConvertOption2DefenceType',[0,0,2,1,0,0,0])])
def test_actual_native_leaf_options(owned_corner,kind,expected):
    dis,functions,tables=owned_corner
    address,body=next(v for k,v in functions.items() if kind in k)
    for option,value in enumerate(expected):
        assert interpret(dis,address,body,tables,option)==value

def test_own_elf_formation_jump_tables(owned_corner):
    _,_,tables=owned_corner
    assert [0x63e881c+b*4 for b in tables[0x81ace24]][2:]==[
        0x63e8854,0x63e8860,0x63e899c,0x63e89a8,0x63e89b4,0x63e89c0]
    assert [0x62c8ed4+b*4 for b in tables[0x81ac398]]==[
        0x62c8ed4,0x62c8ee4,0x62c8ef4,0x62c8f04]
