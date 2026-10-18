"""Opt-in diagnostic hooks must not change the native entrance lifecycle."""
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source/fixdemo_scene_trace.inc"


def test_trace_gates_lifecycle_and_bounded_output():
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        pytest.skip("host C compiler required")
    with tempfile.TemporaryDirectory(prefix="pesnx-cinematic-trace-") as temp:
        root = Path(temp)
        executable = root / "trace.exe"
        build = subprocess.run([compiler, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                                (ROOT / "tests/test_fixdemo_scene_trace.c").as_posix(),
                                "-o", executable.as_posix()], capture_output=True, text=True)
        assert build.returncode == 0, build.stdout + build.stderr
        cases = ["enabled", "absent", "bad-marker", "extra-marker", "missing-vtable"]
        cases += [f"{gate}-{i}" for gate in ("missing-method", "bad-opcode", "bad-slot")
                  for i in range(3)]
        for case in cases:
            work = root / case
            work.mkdir()
            if case != "absent":
                marker = b"PESNX_CINEMATIC_TRACE_V1\n"
                if case == "bad-marker":
                    marker = b"invalid\n"
                if case == "extra-marker":
                    marker += b"extra"
                (work / "cinematic-trace.txt").write_bytes(marker)
            result = subprocess.run([str(executable), case], cwd=work,
                                    capture_output=True, text=True, timeout=15)
            assert result.returncode == 0, (case, result.stdout, result.stderr)
            log = work / "cinematic-trace.log"
            if case != "enabled":
                assert not log.exists(), case
            else:
                lines = log.read_text().splitlines()
                assert len(lines) == 129  # One header plus at most 128 observations.
                assert lines[1:6] == [f"{event} scene=65537" for event in (
                    "entrance-selected", "entrance-start-enter", "entrance-start-return",
                    "entrance-end-enter", "entrance-end-return")]


def test_optional_native_trace_fingerprints():
    native = ROOT / "dist/pes21_nx/libUE4.so"
    if not native.is_file():
        pytest.skip("compatible local Mobile library required; never committed")
    elf_module = pytest.importorskip("elftools.elf.elffile")
    source = SOURCE.read_text()
    names = re.findall(r'"(_ZN15FixDemoEntrance[^\"]+)"', source)
    block = source.split("expected_words[][8] = {", 1)[1].split("};", 1)[0]
    words = [int(word, 16) for word in re.findall(r"0x[0-9a-f]+", block)]
    assert len(names) == 3 and len(words) == 24
    with native.open("rb") as stream:
        elf = elf_module.ELFFile(stream)
        assert elf.elfclass == 64 and elf.little_endian and elf["e_machine"] == "EM_AARCH64"
        symbols = elf.get_section_by_name(".dynsym")
        strings = elf.get_section(symbols["sh_link"]).data()
        addresses = {}
        wanted = {name.encode(): name for name in names}
        for offset, info, other, section, address, size in struct.iter_unpack(
                "<IBBHQQ", symbols.data()):
            name = strings[offset:strings.find(b"\0", offset)]
            if name in wanted and address:
                addresses[wanted[name]] = address
        segments = [segment for segment in elf.iter_segments()
                    if segment["p_type"] == "PT_LOAD"]
        for index, name in enumerate(names):
            address = addresses[name]
            segment = next(s for s in segments
                           if s["p_vaddr"] <= address and address + 32 <= s["p_vaddr"] + s["p_filesz"])
            stream.seek(segment["p_offset"] + address - segment["p_vaddr"])
            assert stream.read(32) == struct.pack("<8I", *words[index*8:index*8+8]), name


def test_trace_is_installed_without_state_or_skip_override():
    source = SOURCE.read_text()
    hooks = (ROOT / "source/ue4_hooks.c").read_text()
    assert '#include "fixdemo_scene_trace.inc"' in hooks
    assert "install_fixdemo_scene_trace(module);" in hooks
    assert "hook_arm64(" not in source
    assert "MatchEndingDemo" not in source and "IsCup" not in source
    assert "original(manager);" in source
