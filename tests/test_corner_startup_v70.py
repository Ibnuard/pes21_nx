"""Actual installer before RX mapping; owned opcodes remain ignored fixtures."""
from pathlib import Path
import hashlib
import mmap
import os
import re
import shutil
import struct
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def corner_install(tmp_path_factory):
    cc=shutil.which('gcc') or shutil.which('clang')
    if not cc:pytest.skip('host C compiler required')
    elfmod=pytest.importorskip('elftools.elf.elffile')
    owned=Path(os.environ.get('PESNX_NATIVE_LIBRARY',ROOT/'dist/pes21_nx/libUE4.so'))
    if not owned.is_file():pytest.skip('ignored compatible owned libUE4.so required')
    folder=tmp_path_factory.mktemp('corner-install-v70')
    guards=re.findall(r'\{"([^"]+)",(\d+),0x([0-9a-f]+)u\}',
        (ROOT/'source/corner_tactics_native.inc').read_text())
    assert len(guards)==7
    with owned.open('rb') as f:
        assert hashlib.file_digest(f,'sha256').hexdigest()=='a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187'
        with mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as image:
            elf=elfmod.ELFFile(image);dyn=elf.get_section_by_name('.dynsym')
            strings=elf.get_section(dyn['sh_link']).data()
            names={n for n,_,_ in guards};bodies={}
            for no,_,_,_,address,size in struct.iter_unpack('<IBBHQQ',dyn.data()):
                name=strings[no:strings.find(b'\0',no)].decode()
                if name in names:
                    at=next(elf.address_offsets(address))
                    bodies[name]=image[at:at+size]
    records=[]
    for i,(name,size,h) in enumerate(guards):
        body=bodies[name];assert len(body)==int(size)
        value=2166136261
        for byte in body:value=((value^byte)*16777619)&0xffffffff
        assert value==int(h,16)
        records.append((name,0x100+i*0x400,body))
    records.extend([
        ('_ZNK5match8registry14GlobalRegistry12GetAnimeInfoE8PlayerNo',0x3000,b'\0'*4),
        ('_ZN5match8registry22IsSetPlayMoveAnimeKindENS_15AnimeActionKindE',0x3100,b'\0'*4),
        ('_ZTVN5match3pad26ThinkUnitCornerKickTacticsE',0x4000,b'\0'*160),
        ('_ZTVN5match3pad30ThinkUnitCornerKickDefenceTypeE',0x4100,b'\0'*160)])
    data=struct.pack('<I',len(records))
    for name,offset,body in records:
        encoded=name.encode();data+=struct.pack('<I',len(encoded))+encoded+struct.pack('<II',offset,len(body))+body
    fixture=folder/'owned-opcodes.bin';fixture.write_bytes(data)
    out=folder/'install.exe'
    subprocess.run([cc,'-std=c11','-D_GNU_SOURCE','-Wall','-Wextra','-Werror','-pthread',
        '-I',(ROOT/'source').as_posix(),(ROOT/'tests/corner_install_cases.c').as_posix(),
        (ROOT/'source/corner_tactics.c').as_posix(),'-o',out.as_posix()],check=True,capture_output=True,text=True)
    return out,fixture

@pytest.mark.parametrize('fault',range(12))
def test_pre_finalize_installer_never_reads_unmapped_RX(corner_install,fault):
    out,fixture=corner_install
    result=subprocess.run([str(out),str(fixture),str(fault)],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stdout+result.stderr
