"""Bounded trophy lifecycle, callback identity, and exact optional native ABI."""
from pathlib import Path
import ctypes
import hashlib
import re
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def lifecycle_executable(tmp_path_factory):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler or ctypes.sizeof(ctypes.c_void_p) != 8:
        pytest.skip("64-bit host C compiler required")
    output = tmp_path_factory.mktemp("trophy-prop-lifecycle") / "probe.exe"
    result = subprocess.run(
        [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
         (ROOT / "tests/test_fixdemo_prop_lifecycle.c").as_posix(), "-o", output.as_posix()],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return output


@pytest.mark.parametrize("case", ["readiness", "bounds", "teardown", "failure", "failure-epoch-race", "cut-reload", "started"])
def test_lifecycle(lifecycle_executable, case):
    result = subprocess.run([str(lifecycle_executable), case], capture_output=True,
                            text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "prop lifecycle: pass"


@pytest.fixture(scope="module")
def runtime_executable(tmp_path_factory):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler or ctypes.sizeof(ctypes.c_void_p) != 8:
        pytest.skip("64-bit host C compiler required")
    output = tmp_path_factory.mktemp("trophy-prop-runtime") / "probe.exe"
    result = subprocess.run(
        [compiler, "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-unused-function",
         (ROOT / "tests/test_fixdemo_trophy_props_runtime.c").as_posix(), "-o", output.as_posix()],
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return output


@pytest.mark.parametrize("case", ["inactive", "ready", "fast-or-cached", "missing-mesh", "late-callback"])
def test_runtime_callbacks(runtime_executable, case):
    result = subprocess.run([str(runtime_executable), case], capture_output=True,
                            text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "prop runtime callbacks: pass"


def test_optional_native_prop_runtime_hooks():
    native = ROOT / "dist/pes21_nx/libUE4.so"
    if not native.is_file():
        pytest.skip("compatible local Mobile ELF required; never committed")
    elf_module = pytest.importorskip("elftools.elf.elffile")
    source = (ROOT / "source/fixdemo_trophy_props.inc").read_text(encoding="utf-8")
    block = source.split("fixdemo_trophy_prop_hooks[] = {", 1)[1].split("};", 1)[0]
    hooks = re.findall(r'\{"([^\"]+)",\s*(0x[0-9a-f]+)u,\s*(0x[0-9a-f]+)u,\s*'
                       r'\{([^}]+)\},\s*\{([^}]+)\}\}', block)
    assert len(hooks) == 5
    boundary_block = source.split("boundaries[] = {", 1)[1].split("};", 1)[0]
    boundaries = re.findall(r'\{"([^\"]+)",\s*(0x[0-9a-f]+)u,\s*(0x[0-9a-f]+)u,\s*'
                            r'\{([^}]+)\}\}', boundary_block)
    assert len(boundaries) == 4
    with native.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == (
            "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187")
        stream.seek(0)
        elf = elf_module.ELFFile(stream)
        symtab = elf.get_section_by_name(".dynsym")
        strings = elf.get_section(symtab["sh_link"]).data()
        rows = list(struct.iter_unpack("<IBBHQQ", symtab.data()))
        names = [strings[r[0]:strings.find(b"\0", r[0])].decode("ascii", "replace") for r in rows]
        symbols = {name: (r[4], r[5]) for name, r in zip(names, rows) if r[3] and r[4]}
        plt = elf.get_section_by_name(".plt")
        relocs = elf.get_section_by_name(".rela.plt")
        calls = {names[r["r_info_sym"]]: plt["sh_addr"] + 32 + i * 16
                 for i, r in enumerate(relocs.iter_relocations())}

        def check_words(address, words):
            expected = [int(x, 16) for x in re.findall(r"0x[0-9a-f]+", words)]
            assert len(expected) == 4
            stream.seek(next(elf.address_offsets(address, 16)))
            assert stream.read(16) == struct.pack("<4I", *expected), hex(address)

        for name, rva, plt_rva, body_words, plt_words in hooks:
            address = int(rva, 16)
            assert symbols[name][0] == address
            assert calls[name] == int(plt_rva, 16)
            check_words(address, body_words)
            check_words(calls[name], plt_words)
        for name, rva, offset, words in boundaries:
            assert symbols[name][0] == int(rva, 16)
            check_words(int(rva, 16) + int(offset, 16), words)
        # Destruction is virtual D0 -> D2 PLT; registered UE callbacks use the
        # native callback-manager lifetime. Verify exact slot identities.
        expected_slots = {symbols["_ZTV8UEObject"][0] + 0x20: "_ZN8UEObject16OnHandleCallbackEPN8UESystem17UECallbackDefDataE",
                          symbols["_ZTV13FixDemoObject"][0] + 0x10: "_ZN13FixDemoObjectD2Ev"}
        observed = {}
        for offset, info, addend in struct.iter_unpack("<QQq", elf.get_section_by_name(".rela.dyn").data()):
            if offset in expected_slots:
                observed[offset] = names[info >> 32]
                assert addend == 0
        assert observed == expected_slots
