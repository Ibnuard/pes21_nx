"""Optional bounded ARM64 proofs: hidden/cached props keep receiving UE callbacks.

Only exact locally supplied functions execute in synthetic memory. Every external
call is intercepted; these probes do not run the game or prove device rendering.
"""
from pathlib import Path
import hashlib
import importlib.util
import os
import struct
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
UPDATE = "_ZN6render11ObjectModel6UpdateEv"
CALLBACK = "_ZN8UEObject16OnHandleCallbackEPN8UESystem17UECallbackDefDataE"
TICK = "_ZN8UESystem17UECallbackManager4TickEf"
MODEL_LOAD = "_ZN6render11ObjectModel8LoadImplEv"
UE_LOAD = "_ZN8UEObject8LoadImplEv"
IMPL_CALLBACK = "_ZN12UEObjectImpl16OnHandleCallbackEv"
VISIBLE = "_ZN16AObjectBaseActor10SetVisibleEb"
CONTRACT = {
    UPDATE: (0x7E145F8, 0xD94, "6ca2b20127ba3f367e5f3c4432cd3797736a4bb683a6dfc572325216101bf14f"),
    CALLBACK: (0x3F01600, 0x1BC, "8437af4110c1d21e49c06151513f0be5803876e2845841579e9da38e1e89e850"),
    TICK: (0x3F1AFFC, 0xE0, "0344ba8df52005384535240dc45060cbe84af64d8860027b3aac7047f550015e"),
}


def read_contract():
    native = ROOT / "dist/pes21_nx/libUE4.so"
    if not native.is_file():
        pytest.skip("compatible local Mobile ELF required; never committed")
    elf_module = pytest.importorskip("elftools.elf.elffile")
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
        code = {}
        for name, (address, size, digest) in CONTRACT.items():
            assert symbols[name] == (address, size)
            stream.seek(next(elf.address_offsets(address, size)))
            code[name] = stream.read(size)
            assert hashlib.sha256(code[name]).hexdigest() == digest
        plt = elf.get_section_by_name(".plt")
        relocs = elf.get_section_by_name(".rela.plt")
        calls = {plt["sh_addr"] + 32 + i * 16: names[r["r_info_sym"]]
                 for i, r in enumerate(relocs.iter_relocations())}
    return code, calls


class Probe:
    BASE = 0x10000000
    STOP = BASE + 0x3F000

    def __init__(self, contract, name, handler):
        self.unicorn = pytest.importorskip("unicorn")
        self.regs = pytest.importorskip("unicorn.arm64_const")
        capstone = pytest.importorskip("capstone")
        self.vm = self.unicorn.Uc(self.unicorn.UC_ARCH_ARM64, self.unicorn.UC_MODE_ARM)
        self.start, self.size, _ = CONTRACT[name]
        self.handler, self.calls, self.sites = handler, [], {}
        first, last = self.start & ~0xFFF, (self.start + self.size + 0xFFF) & ~0xFFF
        self.vm.mem_map(first, last - first)
        self.vm.mem_write(self.start, contract[0][name])
        self.vm.mem_map(self.BASE, 0x40000)
        decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        for instruction in decoder.disasm(contract[0][name], self.start):
            if instruction.mnemonic in ("bl", "b"):
                target = int(instruction.op_str.lstrip("#"), 0)
                if not self.start <= target < self.start + self.size:
                    # Other branches may call an internal native helper. It is
                    # intercepted too, and rejected unless this scenario's
                    # explicit handler accepts it; no helper bytes are mapped.
                    target_name = contract[1].get(target, f"native:{target:#x}")
                    self.sites[instruction.address] = (instruction.mnemonic, target_name)
            elif instruction.mnemonic in ("blr", "br"):
                self.sites[instruction.address] = (instruction.mnemonic, instruction.op_str)
        self.vm.hook_add(self.unicorn.UC_HOOK_CODE, self.step)

    def reg(self, name):
        return getattr(self.regs, "UC_ARM64_REG_" + name.upper())

    def u64(self, address, value=None):
        if value is not None:
            self.vm.mem_write(address, struct.pack("<Q", value))
        return struct.unpack("<Q", self.vm.mem_read(address, 8))[0]

    def step(self, vm, address, _size, _context):
        assert self.start <= address < self.start + self.size, "external native code must not execute"
        if address not in self.sites:
            return
        kind, name = self.sites[address]
        if kind in ("blr", "br"):
            name = f"indirect:{vm.reg_read(self.reg(name)):#x}"
        args = tuple(vm.reg_read(self.reg(f"x{i}")) for i in range(5))
        self.calls.append((name, args))
        result = self.handler(self, name, args)
        if result is not None:
            vm.reg_write(self.reg("x0"), result)
        if kind in ("bl", "blr"):
            vm.reg_write(self.reg("lr"), address + 4)
            vm.reg_write(self.reg("pc"), address + 4)
        else:
            vm.reg_write(self.reg("pc"), vm.reg_read(self.reg("lr")))

    def run(self, *args):
        for i, value in enumerate(args):
            self.vm.reg_write(self.reg(f"x{i}"), value)
        stack = self.BASE + 0x3E000
        self.vm.reg_write(self.reg("sp"), stack)
        self.vm.reg_write(self.reg("lr"), self.STOP)
        self.vm.emu_start(self.start, self.STOP, timeout=1_000_000, count=20_000)
        assert self.vm.reg_read(self.reg("pc")) == self.STOP, "bounded native function did not return"
        assert self.vm.reg_read(self.reg("sp")) == stack


def hidden_model_starts_loading(contract):
    model, ue = Probe.BASE + 0x1000, Probe.BASE + 0x2000

    def handle(probe, name, args):
        assert name == MODEL_LOAD and args[0] == model
        probe.u64(model + 24, ue)

    probe = Probe(contract, UPDATE, handle)
    # State zero + load pending, but native entity/display flag remains false.
    probe.vm.mem_write(model + 0x38, b"\x01\x00")
    probe.run(model)
    assert [name for name, _ in probe.calls] == [MODEL_LOAD]
    assert probe.u64(model + 24) == ue
    assert struct.unpack("<I", probe.vm.mem_read(model + 0x34, 4))[0] == 1
    assert probe.vm.mem_read(model + 0x39, 1) == b"\x00"


def callback_without_started_scene(contract, pending, actor_present, entity_present):
    ue, impl = Probe.BASE + 0x1000, Probe.BASE + 0x2000
    actor, entity = Probe.BASE + 0x3000, Probe.BASE + 0x4000

    def handle(_probe, name, args):
        if name == UE_LOAD:
            assert pending and args[0] == ue
        elif name == IMPL_CALLBACK:
            assert actor_present and args[0] == impl
        elif name == VISIBLE:
            assert entity_present and args[:2] == (actor, 0)
        else:
            pytest.fail(f"unexpected visible scene work: {name}")

    probe = Probe(contract, CALLBACK, handle)
    probe.u64(ue + 8, impl)
    probe.vm.mem_write(impl + 0x202, bytes([pending]))
    probe.u64(impl + 0x208, actor if actor_present else 0)
    probe.u64(impl + 0x220, entity)
    probe.vm.mem_write(impl + 0x2A0, bytes([entity_present]))
    probe.run(ue, 0)
    expected = ([UE_LOAD] if pending else []) + ([VISIBLE] if entity_present else [])
    expected += [IMPL_CALLBACK] if actor_present else []
    assert [name for name, _ in probe.calls] == expected
    assert probe.vm.mem_read(impl + 0x202, 1) == b"\x00"
    # A cached/hidden object is still called on the next tick without another load.
    if actor_present:
        probe.calls.clear()
        probe.run(ue, 0)
        assert [name for name, _ in probe.calls] == expected


def manager_dispatches_hidden_registered_handler(contract):
    manager, impl = Probe.BASE + 0x1000, Probe.BASE + 0x2000
    ue, vtable, entries = Probe.BASE + 0x3000, Probe.BASE + 0x4000, Probe.BASE + 0x5000
    target = Probe.BASE + 0x6000
    lock, callbacks = [], []

    def handle(probe, name, args):
        if name == "pthread_mutex_lock":
            assert args[0] in (impl + 0x30, impl + 0x70) and not lock
            lock.append(args[0])
            return 0
        if name == "pthread_mutex_unlock":
            assert lock.pop() == args[0]
            return 0
        if name.startswith("_ZNSt6__ndk16vector") and "6assign" in name:
            assert args[:3] == (impl + 0x18, entries, entries + 8)
            assert lock == [impl + 0x30]
            probe.u64(impl + 0x18, entries)
            probe.u64(impl + 0x20, entries + 8)
            return
        assert name == f"indirect:{target:#x}" and args[0] == ue
        assert lock == [impl + 0x30]
        callbacks.append(args[0])

    probe = Probe(contract, TICK, handle)
    probe.u64(manager + 8, impl)
    probe.u64(impl, entries)
    probe.u64(impl + 8, entries + 8)
    probe.u64(entries, ue)
    probe.u64(ue, vtable)
    probe.u64(vtable + 0x10, target)
    # No scene object, visible entity, or actor is necessary for Tick dispatch.
    probe.run(manager)
    probe.run(manager)
    assert callbacks == [ue, ue] and not lock


def test_optional_hidden_and_cached_native_callbacks():
    read_contract()
    for name in ("unicorn", "capstone"):
        if importlib.util.find_spec(name) is None:
            pytest.skip(f"{name} required for optional bounded native probes")
    # Keep emulator handled Windows exceptions separate from pytest faulthandler.
    environment = os.environ.copy()
    environment.pop("PYTHONFAULTHANDLER", None)
    result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--native-probes"],
                            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "5 bounded hidden/cached prop native probes: pass"


if __name__ == "__main__":
    assert sys.argv[1:] == ["--native-probes"]
    contract = read_contract()
    hidden_model_starts_loading(contract)
    callback_without_started_scene(contract, pending=1, actor_present=0, entity_present=0)
    callback_without_started_scene(contract, pending=0, actor_present=1, entity_present=0)
    callback_without_started_scene(contract, pending=0, actor_present=1, entity_present=1)
    manager_dispatches_hidden_registered_handler(contract)
    print("5 bounded hidden/cached prop native probes: pass")
