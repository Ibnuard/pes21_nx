"""Optional, bounded original-native proofs for trophy file/path admission.

The ignored, hash-pinned library supplies code at test time. No game code is
copied here. Fake owned records and an already-reserved output vector avoid
the native allocator; model-path string/libc calls use explicit local stubs.
"""
from pathlib import Path
import ast
import hashlib
import importlib.util
import os
import struct
import subprocess
import sys

import pytest

from test_fixdemo_trophy_result import ELF_SHA256, Probe

ROOT = Path(__file__).resolve().parents[1]
FILE_NAMES = "_ZN11FixDemoList11GetFileNameEhRN5cobra3stl6vectorIPNS1_12basic_stringIcNSt6__ndk111char_traitsIcEENS1_9AllocatorIcEEEENS7_ISA_EEEE"
PLATFORM = "_Z26FixDemoReplacePlatformPathRN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS0_9AllocatorIcEEEEb"
CORRECT = "_Z23FixDemoCorrectModelPathRN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS0_9AllocatorIcEEEEb"
REPLACE = "_ZN7fixdemo11ReplacePathERN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS1_9AllocatorIcEEEEPKcSB_"
EXTENSION = "_ZN7fixdemo16ReplaceExtensionERN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS1_9AllocatorIcEEEEPKc"
CONTRACT = {
    FILE_NAMES: (0x7B52910, 0xE8, "3dcd4209615cd8602a13c7d2f08cb8c47691d7ac4f0f23fd121d10410ffb5efb"),
    PLATFORM: (0x7B54F3C, 0x22C, "a0b1abc5b8a2261eb530e9464bf073defb43574e59b77e75b88cd4d6ede55f30"),
    CORRECT: (0x7B558F4, 0x104, "2eb2c581efa11cac145e428003e01318e53d93d7f7a5ae808e7b213db04b5523"),
}


def read_contract():
    path = ROOT / "dist/pes21_nx/libUE4.so"
    if not path.is_file():
        pytest.skip("compatible ignored libUE4.so required for native loader proof")
    module = pytest.importorskip("elftools.elf.elffile")
    with path.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == ELF_SHA256
        stream.seek(0)
        elf = module.ELFFile(stream)
        assert elf.elfclass == 64 and elf.little_endian and elf["e_machine"] == "EM_AARCH64"
        symbols = elf.get_section_by_name(".dynsym")
        names = elf.get_section(symbols["sh_link"]).data()
        rows = list(struct.iter_unpack("<IBBHQQ", symbols.data()))

        def name(index):
            start = rows[index][0]
            return names[start:names.find(b"\0", start)].decode("ascii", errors="replace")

        selected = {name(i): (row[4], row[5]) for i, row in enumerate(rows)
                    if row[3] and row[4] and name(i) in CONTRACT}

        def read(address, length):
            offsets = list(elf.address_offsets(address, length))
            assert len(offsets) == 1
            stream.seek(offsets[0])
            content = stream.read(length)
            assert len(content) == length
            return content

        code = {}
        for symbol, (address, length, digest) in CONTRACT.items():
            assert selected[symbol] == (address, length)
            code[symbol] = read(address, length)
            assert hashlib.sha256(code[symbol]).hexdigest() == digest
        plt = elf.get_section_by_name(".plt")
        relocations = elf.get_section_by_name(".rela.plt")
        assert plt["sh_size"] == 32 + 16 * relocations.num_relocations()
        calls = {plt["sh_addr"] + 32 + i * 16: name(row[1] >> 32)
                 for i, row in enumerate(struct.iter_unpack("<QQq", relocations.data()))}
        constants = {address: read(address, 0x1000)
                     for address in (0x85D5000, 0x81AA000, 0x81AD000, 0x81B4000)}
    return {"symbols": selected, "code": code, "calls": calls, "constants": constants}


def branch_target(code, offset, address):
    word = struct.unpack_from("<I", code, offset)[0]
    assert word & 0x7C000000 == 0x14000000  # original direct B/BL
    immediate = word & 0x3FFFFFF
    if immediate & 0x2000000:
        immediate -= 0x4000000
    return address + offset + immediate * 4


@pytest.fixture(scope="module")
def native_contract():
    return read_contract()


def test_optional_native_loader_contract(native_contract):
    constants = native_contract["constants"]
    for address, value in ((0x85D51FD, b"common/demo/\0"),
                           (0x85D520A, b"Asset/model/\0"),
                           (0x85D52B4, b"#Win/\0"),
                           (0x81B409F, b"\0"), (0x81AD55B, b".xml\0"),
                           (0x81AA648, b".fpk\0")):
        page = address & ~0xFFF
        assert constants[page][address-page:address-page+len(value)] == value
    code = native_contract["code"][CORRECT]
    base = native_contract["symbols"][CORRECT][0]
    # Bind the ordering to original direct calls, including its native tail call.
    for offset, symbol in ((0x24, PLATFORM), (0xE4, REPLACE), (0xF8, EXTENSION)):
        assert native_contract["calls"][branch_target(code, offset, base)] == symbol


def core_files():
    tree = ast.parse((ROOT / "tools/stage_trophy_ceremony.py").read_text(encoding="utf-8"))
    value = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "CORE_FILES"
                         for target in node.targets))
    result = ast.literal_eval(value)
    assert len(result) == 4 and len(set(result)) == 4 and all(result)
    assert result[-1] == "end_obj_platform_cmn.fdc"
    return result


def write_string(probe, address, value, buffer):
    value = value.encode("ascii") if isinstance(value, str) else value
    probe.vm.mem_write(address, b"\0" * 24)
    if len(value) <= 22:
        probe.vm.mem_write(address, bytes([len(value) << 1]) + value + b"\0")
    else:
        capacity = (len(value) + 16) & ~15
        probe.put(address, capacity | 1)
        probe.put(address + 8, len(value))
        probe.put(address + 16, buffer)
        probe.vm.mem_write(buffer, value + b"\0")


def read_string(probe, address):
    first = probe.get(address, 1)
    length = probe.get(address + 8) if first & 1 else first >> 1
    buffer = probe.get(address + 16) if first & 1 else address + 1
    assert length < 1024
    return bytes(probe.vm.mem_read(buffer, length))


def probe_file_names(contract, files, expected):
    def no_external(probe, name, args):
        raise AssertionError("reserved native output vector must not allocate: " + name)

    probe = Probe(contract, FILE_NAMES, no_external)
    owner, rows, output, pointers = [Probe.BASE + offset
                                     for offset in (0x1000, 0x2000, 0x4000, 0x5000)]
    # Native count arithmetic excludes its trailing sentinel record. Supply one
    # live CutData row and one fake owned terminator; each row is 0x190 bytes.
    probe.put(owner + 0x20, rows)
    probe.put(owner + 0x28, rows + 2 * 0x190)
    probe.put(output, pointers)
    probe.put(output + 8, pointers + 8)  # original clears an existing output count
    probe.put(output + 16, pointers + 10 * 8)
    for index, value in enumerate(files):
        write_string(probe, rows + 0x80 + index * 24, value,
                     Probe.BASE + 0x10000 + index * 0x400)
    probe.run(owner, 0, output)
    assert not probe.calls
    start, end = probe.get(output), probe.get(output + 8)
    assert start == pointers and 0 <= end-start <= 10 * 8
    result = [read_string(probe, probe.get(pointers + i * 8)).decode("ascii")
              for i in range((end-start)//8)]
    assert result == expected
    return result


def probe_platform_path(contract, value, expected):
    heap = [Probe.BASE + 0x20000]

    def allocate(size):
        assert 0 < size < 4096
        address = heap[0]
        heap[0] += (size + 31) & ~15
        assert heap[0] < Probe.BASE + 0x40000
        return address

    def callback(probe, name, args):
        a, b, c = args[:3]
        if name == "memchr":
            content = bytes(probe.vm.mem_read(a, c))
            index = content.find(bytes([b & 255]))
            return a + index if index >= 0 else 0
        if name == "memcmp":
            left, right = bytes(probe.vm.mem_read(a, c)), bytes(probe.vm.mem_read(b, c))
            return 0 if left == right else (1 if left > right else 0xFFFFFFFF)
        if name == "memcpy":
            probe.vm.mem_write(a, bytes(probe.vm.mem_read(b, c)))
            return a
        if name == "BasicMalloc":
            assert b == 0
            return allocate(a)
        if name == "BasicFree":
            return 0
        if name.endswith("6appendEPKcm") or name.endswith("6assignEPKcm"):
            value = bytes(probe.vm.mem_read(b, c))
            if name.endswith("6appendEPKcm"):
                value = read_string(probe, a) + value
            write_string(probe, a, value, allocate(len(value) + 1))
            return a
        raise AssertionError("unexpected external native call: " + name)

    probe = Probe(contract, PLATFORM, callback)
    address = Probe.BASE + 0x1000
    write_string(probe, address, value, Probe.BASE + 0x10000)
    probe.run(address, 0)
    assert read_string(probe, address).decode("ascii") == expected


def native_probes():
    contract = read_contract()
    files = core_files()
    # V86's gap before the platform is terminal to the actual native reader.
    old = list(files[:3]) + ["", files[3]] + [""] * 5
    fixed = list(files) + [""] * 6
    assert len(probe_file_names(contract, old, list(files[:3]))) == 3
    assert len(probe_file_names(contract, fixed, list(files))) == 4
    for value in ("common/demo/prop/cup_int_hi/cup_int_hi.fpk",
                  "common/demo/fixdemoobj/winners_platform_common/winners_platform_common.fpk",
                  "cpk_dat/common/demo/prop/cup_int_hi/cup_int_hi.fpk"):
        suffix = value[value.index("common/demo/"):]
        probe_platform_path(contract, value, "cpk_dat/" + suffix)
    print("native first-gap file-list and cpk_dat model-prefix probes: pass")


def test_optional_native_loader_execution(native_contract):
    del native_contract
    for dependency in ("unicorn", "capstone"):
        if importlib.util.find_spec(dependency) is None:
            pytest.skip(dependency + " required for bounded native loader execution")
    environment = os.environ.copy()
    environment.pop("PYTHONFAULTHANDLER", None)
    ran = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--native-probes"],
                         cwd=ROOT, env=environment, capture_output=True, text=True, timeout=45)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.strip() == "native first-gap file-list and cpk_dat model-prefix probes: pass"


if __name__ == "__main__" and sys.argv[1:] == ["--native-probes"]:
    native_probes()
