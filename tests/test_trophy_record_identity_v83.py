"""Optional bounded native record-copy oracle; never executes game code.

The v65 oracle separately verifies SetExhibitionTeamId's native side keys.
This probe establishes that the stats writer/getter do not strip those bits.
It does not observe a live device's actual team values or ceremony playback.
"""
from pathlib import Path
import hashlib
import mmap
import struct

import pytest

ROOT = Path(__file__).resolve().parents[1]
NATIVE_SHA = "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187"


def native_blocks():
    capstone = pytest.importorskip("capstone")
    elfmod = pytest.importorskip("elftools.elf.elffile")
    path = ROOT / "dist/pes21_nx/libUE4.so"
    if not path.is_file():
        pytest.skip("requires the optional ignored compatible owned native ELF")
    with path.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == NATIVE_SHA
        image = mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ)
        elf = elfmod.ELFFile(image)
        symbols = elf.get_section_by_name(".dynsym")
        strings = elf.get_section(symbols["sh_link"]).data()
        table = {}
        for name, _, _, section, address, size in struct.iter_unpack("<IBBHQQ", symbols.data()):
            if section:
                table[strings[name:strings.find(b"\0", name)]] = (address, size)
        writer = b"_ZN5match6record6Record22UpdateStatsMatchStatusERNS_6output14StatsMatchInfoEPKNS_8registry8RegistryERKNS5_11RecordEventE"
        getter = b"_ZNK5match6output14StatsMatchInfo9GetTeamIdE8HomeAway"
        assert table[writer] == (0x67d5ed0, 0x3bc)
        assert table[getter] == (0x66b4230, 0x24)
        blocks = []
        for address, size in ((0x67d5f74, 16), table[getter]):
            image.seek(next(elf.address_offsets(address)))
            code = image.read(size)
            decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
            decoder.detail = True
            blocks.append(list(decoder.disasm(code, address)))
        image.close()
    return blocks


def test_native_stats_writer_copies_the_complete_team_key():
    from capstone import arm64_const as arm
    writer, getter = native_blocks()
    # Interpret only this four-instruction load/store block. Dependency calls,
    # registry access and all other game code remain outside the probe.
    assert [i.mnemonic for i in writer] == ["mov", "ldr", "mov", "str"]
    for physical in (1, 108, 900, 901, 0x3ffff):
        for side in (0, 1):
            raw = (physical << 14) | (0x3ffd + side)
            registers = {"x0": 0x1000, "x22": 0x20000}
            memory = {0x1000 + 0xa278: raw}

            def register(instruction, operand):
                name = instruction.reg_name(operand.reg)
                return "x" + name[1:] if name.startswith("w") else name

            for instruction in writer:
                destination, source = instruction.operands
                if instruction.mnemonic == "mov":
                    value = source.imm if source.type == arm.ARM64_OP_IMM else 0
                    if source.type != arm.ARM64_OP_IMM:
                        assert instruction.reg_name(source.reg) in ("wzr", "xzr")
                    registers[register(instruction, destination)] = value
                else:
                    assert source.type == arm.ARM64_OP_MEM
                    assert instruction.reg_name(destination.reg).startswith("w")
                    address = registers[instruction.reg_name(source.mem.base)] + source.mem.disp
                    if source.mem.index:
                        address += registers[instruction.reg_name(source.mem.index)]
                    key = register(instruction, destination)
                    if instruction.mnemonic == "ldr":
                        registers[key] = memory[address] & 0xffffffff
                    else:
                        memory[address] = registers[key] & 0xffffffff
            assert memory[0x20028] == raw
            assert memory[0x20028] != physical << 14
    # The actual accessor returns the side's raw field address, with a distinct
    # invalid-side fallback; no key normalization occurs in the getter either.
    assert [i.mnemonic for i in getter][-5:] == ["umaddl", "add", "cmp", "csel", "ret"]
    assert getter[-4].operands[2].imm == 0x28
    assert getter[-3].operands[1].imm == 2
    assert getter[-2].cc == arm.ARM64_CC_LO
