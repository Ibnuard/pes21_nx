"""Master identity versus the native match-local HOME/AWAY storage key.

The optional owned-ELF oracle interprets two bounded identity-write blocks from
SetExhibitionTeamId over synthetic memory. It does not execute the entire
function, boot the game or mount assets. No game bytes are retained by the test.
"""
from pathlib import Path
import hashlib
import mmap
import os
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_selected_identity_requires_physical_team_and_native_side_locator(tmp_path):
    cc = shutil.which("gcc") or shutil.which("clang")
    if not cc:
        pytest.skip("host C compiler required")
    source = tmp_path / "team.c"
    source.write_text(r'''
#include <assert.h>
#include "exhibition_match_identity.h"
int main(void){
 for(uint32_t team=1;team<0x3ffffu;team+=101u){
  const uint32_t master=team<<14;
  for(uint32_t side=0;side<2;side++){
   const uint32_t actual=master|(0x3ffdu+side);
   assert(exhibition_match_team_identity(actual,master,side));
   assert(!exhibition_match_team_identity(actual,master,1u-side));
   assert(!exhibition_match_team_identity(actual,master^0x4000u,side));
   assert(!exhibition_match_team_identity(master,master,side));
   assert(!exhibition_match_team_identity(actual,master|1u,side));
  }
 }
 assert(!exhibition_match_team_identity(0x3ffdu,0u,0u));
 assert(!exhibition_match_team_identity(108u<<14,(108u<<14),2u));
}
''')
    exe = tmp_path / "team.exe"
    subprocess.run([cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-I",
        str(ROOT / "source"), str(source), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


def native_identity_blocks():
    capstone = pytest.importorskip("capstone")
    elfmod = pytest.importorskip("elftools.elf.elffile")
    path = Path(os.environ.get("PESNX_NATIVE_LIBRARY", ROOT / "dist/pes21_nx/libUE4.so"))
    if not path.is_file():
        pytest.skip("optional native oracle requires the ignored compatible owned libUE4.so")
    with path.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == (
            "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187")
    symbol = "_ZN5tmpdb4util19SetExhibitionTeamIdEN6common6TeamIdEhb"
    with path.open("rb") as stream:
        image = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        elf = elfmod.ELFFile(image)
        dyn = elf.get_section_by_name(".dynsym")
        strings = elf.get_section(dyn["sh_link"]).data()
        offset = strings.find(symbol.encode() + b"\0")
        assert offset >= 0
        matches = [(addr, size) for name, _, _, _, addr, size in
                   struct.iter_unpack("<IBBHQQ", dyn.data()) if name == offset]
        assert len(matches) == 1
        address, size = matches[0]
        assert address == 0x6d85158 and size == 484
        image.seek(next(elf.address_offsets(address)))
        code = image.read(size)
        image.close()
    dis = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    dis.detail = True
    # First block writes TeamId/coach locator; second writes a player carrier.
    # Dependency calls and later loops are deliberately outside this oracle.
    return [list(dis.disasm(code[a:b], address+a)) for a, b in
            ((0x6c, 0x98), (0xe4, 0xf0))]


def interpret_identity_block(instructions, registers, memory):
    """Bounded ARM64 integer/load/store oracle; reject any unmodelled opcode."""
    from capstone import arm64_const as arm
    zero = False

    def name(ins, operand):
        value = ins.reg_name(operand.reg)
        return "x" + value[1:] if value.startswith("w") else value

    def get(ins, operand):
        if operand.type == arm.ARM64_OP_IMM:
            return operand.imm
        assert operand.type == arm.ARM64_OP_REG
        result = registers.get(name(ins, operand), 0)
        return result & (0xffffffff if ins.reg_name(operand.reg).startswith("w") else 0xffffffffffffffff)

    def put(ins, operand, value):
        registers[name(ins, operand)] = value & (0xffffffff if ins.reg_name(operand.reg).startswith("w") else 0xffffffffffffffff)

    def address(ins, operand):
        assert operand.type == arm.ARM64_OP_MEM and not operand.mem.index
        base = ins.reg_name(operand.mem.base)
        return registers[base] + operand.mem.disp

    for ins in instructions:
        ops = ins.operands
        if ins.mnemonic == "tst":
            zero = (get(ins, ops[0]) & get(ins, ops[1])) == 0
        elif ins.mnemonic == "mov":
            put(ins, ops[0], get(ins, ops[1]))
        elif ins.mnemonic in ("and", "orr"):
            a, b = get(ins, ops[1]), get(ins, ops[2])
            put(ins, ops[0], a & b if ins.mnemonic == "and" else a | b)
        elif ins.mnemonic == "cinc":
            assert ins.cc == arm.ARM64_CC_NE
            put(ins, ops[0], get(ins, ops[1]) + (not zero))
        elif ins.mnemonic == "ldr":
            width = 4 if ins.reg_name(ops[0].reg).startswith("w") else 8
            raw = bytes(memory.get(address(ins, ops[1])+i, 0) for i in range(width))
            put(ins, ops[0], int.from_bytes(raw, "little"))
        elif ins.mnemonic in ("str", "strh", "stur"):
            width = 2 if ins.mnemonic == "strh" else (4 if ins.reg_name(ops[0].reg).startswith("w") else 8)
            raw = (get(ins, ops[0]) & ((1 << (width*8))-1)).to_bytes(width, "little")
            at = address(ins, ops[1])
            memory.update((at+i, v) for i, v in enumerate(raw))
        else:
            raise AssertionError("unmodelled native opcode: " + ins.mnemonic)


@pytest.mark.parametrize("side,team,count", [(0, 108, 28), (1, 109, 34),
                                            (0, 100, 40), (1, 108, 11)])
def test_owned_native_identity_blocks_rewrite_locator_without_changing_identity(side, team, count):
    header, player = native_identity_blocks()
    assert len(header) == 11 and len(player) == 3
    arg, team_addr, coach, record = 0x1000, 0x2000, 0x3000, 0x4000
    registers = dict(x19=side, x23=arg, x22=team_addr, x0=coach)
    memory = {}

    def write(at, value, size):
        memory.update((at+i, v) for i, v in enumerate(value.to_bytes(size, "little")))

    def read(at, size):
        return int.from_bytes(bytes(memory.get(at+i, 0) for i in range(size)), "little")

    write(arg, team << 14, 4)
    write(team_addr, team << 14, 4)
    write(team_addr + 0x3a6, count << 9, 4)
    interpret_identity_block(header, registers, memory)
    actual = read(team_addr, 4)
    assert actual == (team << 14) | (0x3ffd + side)
    assert actual != team << 14  # v64's exact comparison always refused this.
    assert read(team_addr + 0x3a6, 4) == count << 9
    assert registers['x23'] == 0xfffd + side
    for member in range(count):
        registers['x0'] = record
        registers['x28'] = ((100000 + member) << 32) | (0x1200 + member)
        interpret_identity_block(player, registers, memory)
        assert read(record+44, 8) == ((100000+member) << 32) | (0xfffd+side)
