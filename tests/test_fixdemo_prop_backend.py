"""Isolated backend candidate; native probes stub every external call in bounded ARM64 memory."""
from pathlib import Path
import ctypes
import hashlib
import importlib.util
import os
import shutil
import struct
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
ELF_SHA256 = "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187"
CREATE = "_ZN13FixDemoObject12CreateObjectENS_4TYPEEPKcPN5cobra3And8SkelFileEPNS3_6texlib5ColorE"
CTOR = "_ZN4draw10DemoObjectC1Ev"
INIT = "_ZN4draw10DemoObject4InitERNS_4load16DemoObjectLoadIdE"
DELETE = "_ZN4draw10DemoObjectD0Ev"
DISPLAY = "_ZN4draw10DemoObject7SetDispEb"
ASSIGN = "_ZNSt6__ndk112basic_stringIcNS_11char_traitsIcEEN5cobra3stl9AllocatorIcEEE6assignEPKcm"
MANAGER = "_ZN4draw4load7Manager11GetInstanceEv"
LOAD = "_ZN4draw4load7Manager4LoadERKNS0_16DemoObjectLoadIdE"
GET_MODEL = "_ZN4draw4load7Manager15GetDemoObjectIdEjRPN6render11ObjectModelE"
UNLOAD = "_ZN4draw4load7Manager6UnloadENS1_4KindEjb"
LIST_UNLOAD = "_ZN4draw4load4ListINS0_4DataIPN6render11ObjectModelENS0_16DemoObjectLoadIdEEES5_S6_Lm192EE6UnloadEj"

# Whole-function digests bind the ABI findings without retaining raw game code.
NATIVE_CONTRACT = {
    CREATE: (0x7B8D8F8, 0x6F4, "20f71625327b9d92cf6d0b57a774ffa42d4278215a3981e1cbf5b8e0d6025e47"),
    "_ZN13FixDemoObjectD1Ev": (0x7B8D82C, 0xB4, "a20db1187af26cb02236db5067807627f520636b7dea7acc44e40a2a943fbfde"),
    "_ZN13FixDemoObject9DrawModelEv": (0x7B8E728, 0x580, "f2f539a9940c69a71196a65ff316356cf693ad615db1d226a613fdacf12965ca"),
    CTOR: (0x7E225C4, 0x20, "1785dd7e0f2a8ff3227021286ce64993d095d6424e45ccea3edfb72cf3b8bfe3"),
    DELETE: (0x7E22624, 0x40, "efc78677d48edb724fdb557a0276ee238217b4a365eb8e4c56154b2328f18760"),
    INIT: (0x7E22664, 0x40, "b37d0101b940e7ce576b95a79d91297fc1bec530e444e85704f32b474a5c40b3"),
    DISPLAY: (0x7E2274C, 0x3C, "c33e5daf71c62636622c7bf0357ec6a9f65f14696438b211ebb22c1f4a6aa06b"),
    LOAD: (0x7B26B18, 0x134, "ecdd7eb0d7d1a80bb99594e51c93d36452ff60c9ede5bd96f7255d1bf620e05d"),
    GET_MODEL: (0x7B26D20, 0x8C, "2b210987ac57dcdb2c11d003d6b2e9906a8edc748e84937aa7d1d4cb80f6e186"),
    "_ZN4draw4load4ListINS0_4DataIPN6render11ObjectModelENS0_16DemoObjectLoadIdEEES5_S6_Lm192EE10CreateDataERKS6_b":
        (0x7B2E320, 0x144, "7c0de1d54897edcd310dbb55887dbf52f59bad5e718065d6558c43a5346e06b9"),
    ASSIGN: (0x61EC5F0, 0x144, "5273446340f1a8a75f1a88148fb2e2e8fb13f9af2e885a83b5e4a821814da967"),
    LIST_UNLOAD: (0x7B2C8D8, 0x80, "0760d8dfd10c85bd8bc47756bf9843b79b914cbab508f4eff238fb0c9c63f662"),
}


@pytest.fixture(scope="module")
def backend_executable(tmp_path_factory):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler or ctypes.sizeof(ctypes.c_void_p) != 8:
        pytest.skip("64-bit host C compiler required for backend candidate tests")
    executable = tmp_path_factory.mktemp("fixdemo-prop-backend") / "backend.exe"
    result = subprocess.run(
        [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic",
         (ROOT / "tests/test_fixdemo_prop_backend.c").as_posix(), "-o", executable.as_posix()],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return executable


@pytest.mark.parametrize("case", ["forward", "attach", "rollback", "ownership"])
def test_backend_candidate_callbacks(backend_executable, tmp_path, case):
    result = subprocess.run([str(backend_executable), case], cwd=tmp_path,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, (case, result.stdout, result.stderr)
    assert result.stdout.strip() == f"fixdemo prop backend {case}: pass"
    assert not list(tmp_path.iterdir())


def read_native_contract():
    native = ROOT / "dist/pes21_nx/libUE4.so"
    if not native.is_file():
        pytest.skip("compatible local Mobile ELF required at dist/pes21_nx/libUE4.so; never committed")
    elf_module = pytest.importorskip("elftools.elf.elffile")
    with native.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == ELF_SHA256
        stream.seek(0)
        elf = elf_module.ELFFile(stream)
        assert elf.elfclass == 64 and elf.little_endian and elf["e_machine"] == "EM_AARCH64"
        symtab = elf.get_section_by_name(".dynsym")
        strings = elf.get_section(symtab["sh_link"]).data()
        rows = list(struct.iter_unpack("<IBBHQQ", symtab.data()))

        def name_at(index):
            offset = rows[index][0]
            return strings[offset:strings.find(b"\0", offset)].decode("ascii", errors="replace")

        symbols = {name_at(i): (row[4], row[5]) for i, row in enumerate(rows) if row[3] and row[4]}
        code = {}
        for name, (address, size, digest) in NATIVE_CONTRACT.items():
            assert symbols[name] == (address, size), name
            offsets = list(elf.address_offsets(address, size))
            assert len(offsets) == 1, name
            stream.seek(offsets[0])
            code[name] = stream.read(size)
            assert hashlib.sha256(code[name]).hexdigest() == digest, name
        plt = elf.get_section_by_name(".plt")
        relocations = elf.get_section_by_name(".rela.plt")
        assert plt["sh_size"] == 32 + 16 * relocations.num_relocations()
        calls = {plt["sh_addr"] + 32 + index * 16: name_at(reloc["r_info_sym"])
                 for index, reloc in enumerate(relocations.iter_relocations())}
        stream.seek(next(elf.address_offsets(0x85D5000, 0x1000)))
        constants = stream.read(0x1000)
    return {"code": code, "calls": calls, "constants": constants,
            "demo_vtable": symbols["_ZTVN4draw10DemoObjectE"][0]}


@pytest.fixture(scope="module")
def native_contract():
    return read_native_contract()


def test_optional_native_backend_contract(native_contract):
    assert len(native_contract["code"]) == len(NATIVE_CONTRACT)


def test_optional_native_backend_probes(native_contract):
    for dependency in ("unicorn", "capstone"):
        if importlib.util.find_spec(dependency) is None:
            pytest.skip(f"{dependency} required for optional bounded native probes")
    # The emulator may use handled Windows exceptions during memory setup.
    # Isolate it from pytest's process-wide faulthandler; an actual crash or
    # timeout is still a failing child exit, not a skipped or successful test.
    environment = os.environ.copy()
    environment.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--native-probes"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "8 bounded native backend probes: pass"


class NativeProbe:
    """A single verified function plus explicit callbacks, with no real target process."""
    BASE = 0x10000000
    STOP = BASE + 0x3F000

    def __init__(self, contract, method, handler):
        self.unicorn = pytest.importorskip("unicorn")
        self.regs = pytest.importorskip("unicorn.arm64_const")
        capstone = pytest.importorskip("capstone")
        self.vm = self.unicorn.Uc(self.unicorn.UC_ARCH_ARM64, self.unicorn.UC_MODE_ARM)
        self.method, self.handler = method, handler
        self.start, self.size, _ = NATIVE_CONTRACT[method]
        first, last = self.start & ~0xFFF, (self.start + self.size + 0xFFF) & ~0xFFF
        self.vm.mem_map(first, last - first)
        self.vm.mem_write(self.start, contract["code"][method])
        self.vm.mem_map(self.BASE, 0x40000)
        self.vm.mem_map(0x9578000, 0x1000)
        self.write_u64(0x9578C40, contract["demo_vtable"])
        self.vm.mem_map(0x85D5000, 0x1000)
        self.vm.mem_write(0x85D5000, contract["constants"])
        self.calls = []
        self.call_sites = {}
        decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        for instruction in decoder.disasm(contract["code"][method], self.start):
            if instruction.mnemonic in ("bl", "b"):
                target = int(instruction.op_str.lstrip("#"), 0)
                if not self.start <= target < self.start + self.size:
                    assert target in contract["calls"], (method, instruction.address, target)
                    self.call_sites[instruction.address] = (instruction.mnemonic, contract["calls"][target])
            elif instruction.mnemonic in ("blr", "br"):
                self.call_sites[instruction.address] = (instruction.mnemonic, instruction.op_str)
        self.vm.hook_add(self.unicorn.UC_HOOK_CODE, self.on_instruction)

    def register(self, name):
        return getattr(self.regs, "UC_ARM64_REG_" + name.upper())

    def read_u64(self, address):
        return struct.unpack("<Q", self.vm.mem_read(address, 8))[0]

    def write_u64(self, address, value):
        self.vm.mem_write(address, struct.pack("<Q", value))

    def on_instruction(self, vm, address, _size, _context):
        assert self.start <= address < self.start + self.size, "external code must never execute"
        if address not in self.call_sites:
            return
        kind, name = self.call_sites[address]
        if kind in ("blr", "br"):
            name = f"indirect:{vm.reg_read(self.register(name)):#x}"
        args = tuple(vm.reg_read(self.register(f"x{i}")) for i in range(5))
        self.calls.append((name, args))
        value = self.handler(self, name, args)
        if value is not None:
            vm.reg_write(self.register("x0"), value)
        if kind in ("bl", "blr"):
            vm.reg_write(self.register("lr"), address + 4)
            vm.reg_write(self.register("pc"), address + 4)
        else:
            vm.reg_write(self.register("pc"), vm.reg_read(self.register("lr")))

    def run(self, *args):
        for index, value in enumerate(args):
            self.vm.reg_write(self.register(f"x{index}"), value)
        stack = self.BASE + 0x3E000
        self.vm.reg_write(self.register("sp"), stack)
        self.vm.reg_write(self.register("lr"), self.STOP)
        self.vm.emu_start(self.start, self.STOP, timeout=1_000_000, count=20_000)
        assert self.vm.reg_read(self.register("pc")) == self.STOP, "bounded probe did not return"
        assert self.vm.reg_read(self.register("sp")) == stack
        return self.vm.reg_read(self.register("x0"))


def probe_native_create_cleans_slots_and_skips_props(native_contract, path, skeleton_present):
    base = NativeProbe.BASE
    owner, path_pointer, skeleton, colors = base + 0x1000, base + 0x3000, base + 0x4000, base + 0x5000
    old = [base + 0x6000, base + 0x6100, base + 0x6200]
    destroyed = []

    def callback(probe, name, args):
        if name.startswith("indirect:"):
            destroyed.append(args[0])
            assert name == f"indirect:{0x20000000 + old.index(args[0]) * 16:#x}"
        elif name == "strlen":
            assert args[0] == path_pointer
            return len(path)
        elif name == ASSIGN:
            assert args[:3] == (owner + 248, path_pointer, len(path))
            probe.vm.mem_write(args[0], struct.pack("<QQQ", 0x101, len(path), path_pointer))
            return args[0]
        else:
            pytest.fail(f"unexpected external call: {name}")

    probe = NativeProbe(native_contract, CREATE, callback)
    before = bytearray(b"\xA5" * 320)
    struct.pack_into("<QQQ", before, 184, *old)
    struct.pack_into("<H", before, 232, 0x1234)
    before[248:272] = bytes(24)
    probe.vm.mem_write(owner, bytes(before))
    probe.vm.mem_write(path_pointer, path.encode() + b"\0")
    for index, pointer in enumerate(old):
        table = base + 0x7000 + index * 0x100
        probe.write_u64(pointer, table)
        probe.write_u64(table + 8, 0x20000000 + index * 16)
    probe.run(owner, 0, path_pointer, skeleton if skeleton_present else 0, colors)
    assert destroyed == [old[1], old[0], old[2]]
    after = bytes(probe.vm.mem_read(owner, 320))
    before[184:208] = bytes(24)
    if skeleton_present:
        assert after == before
    else:
        assert struct.unpack_from("<H", after, 240)[0] == 0x1234
        assert struct.unpack_from("<QQQ", after, 248) == (0x101, len(path), path_pointer)
        before[240:272] = after[240:272]
        assert after == before


def probe_native_demo_init_and_delete_contract(native_contract, key, model):
    base = NativeProbe.BASE
    demo, load_id, manager = base + 0x2000, base + 0x3000, base + 0x8000

    def callback(probe, name, args):
        if name == MANAGER:
            return manager
        if name == LOAD:
            assert args[:2] == (manager, load_id)
            return key
        if name == GET_MODEL:
            assert args[:3] == (manager, key, demo + 8)
            probe.write_u64(demo + 8, model)
            return int(model != 0)
        if name == "_ZN6render11ObjectModel7SetDispEb":
            assert args[:2] == (model, 0)
            return None
        if name == UNLOAD:
            assert args[:4] == (manager, 5, key, 0)
            return 1
        if name == "_ZdlPv":
            assert args[0] == demo
            return None
        pytest.fail(f"unexpected external call: {name}")

    ctor = NativeProbe(native_contract, CTOR, callback)
    ctor.run(demo)
    data = bytes(ctor.vm.mem_read(demo, 24))
    assert struct.unpack_from("<QQI", data) == (native_contract["demo_vtable"] + 16, 0, 0)
    assert data[20] == 1 and not ctor.calls
    init = NativeProbe(native_contract, INIT, callback)
    init.vm.mem_write(demo, data)
    assert init.run(demo, load_id) == 1  # Also true for key=192, model=NULL.
    data = bytes(init.vm.mem_read(demo, 24))
    assert struct.unpack_from("<QI", data, 8) == (model, key)
    display = NativeProbe(native_contract, DISPLAY, callback)
    display.vm.mem_write(demo, data)
    display.run(demo, 0)
    data = bytes(display.vm.mem_read(demo, 24))
    assert data[20] == 0
    assert len(display.calls) == int(model != 0)
    delete = NativeProbe(native_contract, DELETE, callback)
    delete.vm.mem_write(demo, data)
    delete.run(demo)
    assert [name for name, _ in delete.calls] == [MANAGER, MANAGER, UNLOAD, "_ZdlPv"]


def probe_native_invalid_key_unload_is_bounded(native_contract, populated):
    base = NativeProbe.BASE
    table, node, item = base + 0x9000, base + 0xA000, base + 0xB000

    def callback(_probe, name, args):
        assert name in ("_ZN5basic5Mutex4LockEv", "_ZN5basic5Mutex6UnlockEv")
        assert args[0] == table + 88

    probe = NativeProbe(native_contract, LIST_UNLOAD, callback)
    probe.write_u64(table + 48, node if populated else table + 40)
    probe.write_u64(node + 8, table + 40)
    probe.write_u64(node + 16, item)
    probe.vm.mem_write(item + 72, struct.pack("<II", 17, 2))
    before = bytes(probe.vm.mem_read(base, 0xC000))
    probe.run(table, 192)
    assert bytes(probe.vm.mem_read(base, 0xC000)) == before
    assert len(probe.calls) == 2


if __name__ == "__main__":
    assert sys.argv[1:] == ["--native-probes"]
    evidence = read_native_contract()
    for runtime_path in (
        "common/demo/prop/cup_int_hi/cup_int_hi.xml",
        "common/demo/fixdemoobj/winners_platform_common/winners_platform_common.xml",
    ):
        for has_skeleton in (False, True):
            probe_native_create_cleans_slots_and_skips_props(evidence, runtime_path, has_skeleton)
    for load_key, model_pointer in ((17, NativeProbe.BASE + 0x9000), (192, 0)):
        probe_native_demo_init_and_delete_contract(evidence, load_key, model_pointer)
    for has_other_item in (False, True):
        probe_native_invalid_key_unload_is_bounded(evidence, has_other_item)
    print("8 bounded native backend probes: pass")
