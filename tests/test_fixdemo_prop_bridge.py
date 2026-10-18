"""The future cup/platform bridge validates evidence but cannot activate props."""
from pathlib import Path
import ctypes
import hashlib
import re
import shutil
import struct
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source/fixdemo_prop_bridge.inc"
EXPECTED_ELF_SHA256 = "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187"


@pytest.fixture(scope="module")
def bridge_executable(tmp_path_factory):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler or ctypes.sizeof(ctypes.c_void_p) != 8:
        pytest.skip("64-bit host C compiler required for synthetic bridge tests")
    executable = tmp_path_factory.mktemp("fixdemo-prop-bridge") / "bridge.exe"
    result = subprocess.run(
        [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
         (ROOT / "tests/test_fixdemo_prop_bridge.c").as_posix(), "-o", executable.as_posix()],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return executable


@pytest.mark.parametrize("case", [
    "paths", "packages", "abi", "preflight", "pointer-bounds", "memory-chain", "lifecycle",
])
def test_inactive_bridge_helpers(bridge_executable, tmp_path, case):
    result = subprocess.run(
        [str(bridge_executable), case], cwd=tmp_path,
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (case, result.stdout, result.stderr)
    assert result.stdout.strip() == f"fixdemo prop bridge {case}: pass"
    assert not list(tmp_path.iterdir()), "preflight must not write runtime state"


def test_optional_native_elf_fingerprint_and_windows():
    """Static file evidence only: no native execution, hooks, extraction or copying."""
    native = ROOT / "dist/pes21_nx/libUE4.so"
    if not native.is_file():
        pytest.skip("compatible local Mobile ELF required at dist/pes21_nx/libUE4.so; never committed")
    elf_module = pytest.importorskip("elftools.elf.elffile")
    source = SOURCE.read_text(encoding="utf-8")
    pinned_sha = re.search(r'fixdemo_prop_elf_sha256\[\]\s*=\s*"([0-9a-f]{64})"', source)
    assert pinned_sha and pinned_sha[1] == EXPECTED_ELF_SHA256
    block = source.split("fixdemo_prop_abi_windows[] = {", 1)[1].split("};", 1)[0]
    windows = re.findall(
        r'\{"([^"]+)",\s*(0x[0-9a-f]+)u,\s*(0x[0-9a-f]+|0)u,\s*\{([^}]+)\}\}',
        block,
    )
    assert len(windows) == 9, "all bridge ABI windows must be checked against the native file"
    wanted = {name.encode(): name for name, _, _, _ in windows}
    with native.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        assert digest == EXPECTED_ELF_SHA256, "local native ELF is not the supported revision"
        stream.seek(0)
        elf = elf_module.ELFFile(stream)
        assert elf.elfclass == 64 and elf.little_endian and elf["e_machine"] == "EM_AARCH64"
        symbols = elf.get_section_by_name(".dynsym")
        assert symbols is not None and symbols["sh_entsize"] == 24
        strings = elf.get_section(symbols["sh_link"]).data()
        found = {}
        for offset, info, _, section, address, size in struct.iter_unpack("<IBBHQQ", symbols.data()):
            name = strings[offset:strings.find(b"\0", offset)]
            if name in wanted and section != 0 and address:
                assert (info & 15) == 2, wanted[name]  # STT_FUNC, defined rather than an import.
                assert wanted[name] not in found, f"ambiguous native symbol: {wanted[name]}"
                found[wanted[name]] = (address, size)
        assert set(found) == set(wanted.values())
        segments = [segment for segment in elf.iter_segments() if segment["p_type"] == "PT_LOAD"]
        for name, rva, offset, word_text in windows:
            expected_rva, offset = int(rva, 16), int(offset, 0)
            address, size = found[name]
            assert address == expected_rva, name
            assert offset + 32 <= size, f"fingerprint extends outside {name}"
            words = [int(word, 16) for word in re.findall(r"0x[0-9a-f]+", word_text)]
            assert len(words) == 8
            start = address + offset
            mappings = [segment for segment in segments
                        if segment["p_vaddr"] <= start and
                        start + 32 <= segment["p_vaddr"] + segment["p_filesz"]]
            assert len(mappings) == 1 and mappings[0]["p_flags"] & 1, name
            stream.seek(mappings[0]["p_offset"] + start - mappings[0]["p_vaddr"])
            assert stream.read(32) == struct.pack("<8I", *words), f"{name}+{offset:#x}"
