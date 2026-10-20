"""Final-boundary canary tests; local native probes never execute external code."""
from pathlib import Path
import ctypes
import hashlib
import importlib.util
import os
import re
import shutil
import struct
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
ELF_SHA256 = "a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187"
CREATE = "_ZN5match7FixDemo13CreateFixDemoEPKNS_8registry8RegistryENS_14FixDemoEnvWorkENS_13FIX_DEMO_KINDENS1_11WaitControl8CategoryE"
RESULT = "_ZN13FixDemoResult6CreateEj8HomeAway"
FLOW = "_ZN5match4Flow11ExecFixDemoEPNS_8registry11FixDemoInfoEbPKN5cobra4game7ContextE"
INIT = "_ZN14FixDemoManager4InitEv"
ASSIGN = "_ZN14FixDemoManager30ChangeHumanAssignListByCutDataERN7fixdemo10AssignListEPN11FixDemoList7CutDataE"
MAIN = "_ZN14FixDemoManager8ExecMainEv"
EXEC = "_ZN14FixDemoManager4ExecEPN5match8registry11FixDemoInfoE"
EXEC_ALL = "_ZN14FixDemoManager7ExecAllEPN5match8registry11FixDemoInfoEPNS1_12Screen2dInfoE"
ENV = "_ZN10FixDemoEnv11GetInstanceEv"
READY = "_ZN14FixDemoManager10IsReadyCutEP11FixDemoMainhb"
ENDING = "_ZN9game_mode13MatchListener15MatchEndingDemoEPKN5cobra4game7ContextE"
LISTENER_RESULT = "_ZN9game_mode13MatchListener17MatchHalfTimeDemoEPKN5cobra4game7ContextE"
WAIT_RESULT = "_ZN9game_mode13MatchListener19WaitSendMatchResultEPKN5cobra4game7ContextE"
PRE_RESULT = "_ZN7process23ProcessMatchPreHalfTime4MainEv"
SET_STATE = "_ZN9game_mode13MatchListener13SetMatchStateEh"
STATE_MAIN = "_ZN7process4Base9StateMainEv"
TASK_ACTION = "_ZN4flow9TaskState6ActionEv"
PRE_RESULT_VTABLE = "_ZTVN7process23ProcessMatchPreHalfTimeE"
TOP = "_ZN9game_mode13MatchListener8MatchTopEPKN5cobra4game7ContextE"
MATCH = "_ZN12FixDemoMatch6CreateEj8HomeAway"
READ_LOCK = "_ZN6common8Registry7Manager8ReadLockEPNS0_4BaseEPPv"
READ_UNLOCK = "_ZN6common8Registry7Manager10ReadUnlockEPNS0_4BaseE"
STEP = "_ZN9game_mode13MatchListener12GetMatchStepEv"
SET_STEP = "_ZN9game_mode13MatchListener12SetMatchStepEh"
SET_ENV = "_ZN9game_mode13MatchListener13SetFixDemoEnvEv"
FADE_CANCEL = "_ZN4fade7Manager6CancelENS_5LEVELE"
FADE_END = "_ZN4fade7Manager5IsEndENS_5LEVELE"
MOBILE_CANCEL = "_ZN4fade13ManagerMobile6CancelENS_5LEVELE"
MOBILE_END = "_ZN4fade13ManagerMobile5IsEndENS_5LEVELE"
IMPL_CANCEL = "_ZN4fade8FadeImpl6cancelEv"
IMPL_END = "_ZNK4fade8FadeImpl5IsEndEv"


def test_real_result_runtime_host(tmp_path):
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler or ctypes.sizeof(ctypes.c_void_p) != 8:
        pytest.skip("64-bit host C compiler required")
    executable = tmp_path / "trophy-result.exe"
    built = subprocess.run(
        [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
         "-I", str(ROOT / "source"), str(ROOT / "tests/test_fixdemo_trophy_result.c"),
         "-o", str(executable)], capture_output=True, text=True, timeout=60,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    ran = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.strip() == "trophy result capture, native ownership and fallback: pass"


def read_contract():
    path = ROOT / "dist/pes21_nx/libUE4.so"
    if not path.is_file():
        pytest.skip("compatible ignored dist/pes21_nx/libUE4.so required for native result probes")
    elf_module = pytest.importorskip("elftools.elf.elffile")
    source = (ROOT / "source/fixdemo_trophy_result.inc").read_text()
    checks = re.findall(r'\{"([^"]+)", (0x[0-9a-f]+), (0x[0-9a-f]+), UINT64_C\((0x[0-9a-f]+)\)\}', source)
    assert len(checks) >= 32
    with path.open("rb") as stream:
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

        def read(address, size):
            offsets = list(elf.address_offsets(address, size))
            assert len(offsets) == 1
            stream.seek(offsets[0])
            return stream.read(size)

        code = {}
        for name, address, size, digest in checks:
            address, size, digest = int(address, 0), int(size, 0), int(digest, 0)
            assert symbols[name] == (address, size), name
            content = read(address, size)
            actual = 0xCBF29CE484222325
            for byte in content:
                actual = ((actual ^ byte) * 0x100000001B3) & ((1 << 64) - 1)
            assert actual == digest, name
            code[name] = content
        for name in (INIT, ASSIGN, MAIN, EXEC_ALL, TOP, LISTENER_RESULT, WAIT_RESULT,
                     PRE_RESULT, SET_STATE, STATE_MAIN, TASK_ACTION):
            code[name] = read(*symbols[name])
        plt = elf.get_section_by_name(".plt")
        relocations = elf.get_section_by_name(".rela.plt")
        assert plt["sh_size"] == 32 + 16 * relocations.num_relocations()
        calls = {plt["sh_addr"] + 32 + i * 16: name_at(row[1] >> 32)
                 for i, row in enumerate(struct.iter_unpack("<QQq", relocations.data()))}
        constants = {address: read(address, 0x1000)
                     for address in (0x81A9000, 0x85D5000, 0x85D6000, 0x85D7000)}
        plt_addresses = re.search(r"fixdemo_trophy_result_plt_rvas\[(\d+)\] = \{([^}]+)", source)
        plt_words = re.search(r"fixdemo_trophy_result_plt_words\[(\d+)\]\[4\] = \{(.*?)\n\};", source, re.S)
        addresses = [int(value, 16) for value in re.findall(r"0x[0-9a-f]+", plt_addresses[2])]
        words = [int(value, 16) for value in re.findall(r"0x[0-9a-f]+", plt_words[2])]
        assert len(addresses) == int(plt_addresses[1]) == int(plt_words[1])
        assert len(words) == 4 * len(addresses)
        for index, address in enumerate(addresses):
            assert read(address, 16) == struct.pack("<4I", *words[index * 4:index * 4 + 4])
        # The derived Main has no PLT. Its actual constructor-selected vtable
        # contains ABS64 relocations, not on-disk function-pointer values.
        table, table_size = symbols[PRE_RESULT_VTABLE]
        assert (table, table_size) == (0x942F4F8, 0x108)
        pre_result_slots = {}
        for section in elf.iter_sections():
            if section["sh_type"] != "SHT_RELA":
                continue
            for offset, info, addend in struct.iter_unpack("<QQq", section.data()):
                if table <= offset < table + table_size:
                    assert info & 0xFFFFFFFF == 257 and addend == 0  # R_AARCH64_ABS64
                    pre_result_slots[offset - table] = name_at(info >> 32)
    return {"code": code, "symbols": symbols, "calls": calls, "constants": constants,
            "hook_plts": addresses, "runtime_abi": {row[0] for row in checks},
            "pre_result_slots": pre_result_slots}


@pytest.fixture(scope="module")
def native_contract():
    return read_contract()


def test_optional_native_result_abi(native_contract):
    assert native_contract["calls"][0x39040C0] == RESULT
    assert native_contract["calls"][0x37E2A40] == CREATE
    assert native_contract["calls"][0x391C230] == FLOW
    assert native_contract["calls"][0x391BC10] == READY
    assert native_contract["calls"][0x381E6E0] == ENDING
    assert native_contract["calls"][0x383DBA0] == MATCH
    assert native_contract["calls"][0x3822010] == LISTENER_RESULT
    assert native_contract["calls"][0x38DBEC0] == WAIT_RESULT
    assert set(native_contract["hook_plts"]) == {
        0x37E2A40, 0x39040C0, 0x391C230, 0x391BC10,
        0x381E6E0, 0x383DBA0, 0x3822010, 0x38DBEC0,
    }
    assert {LISTENER_RESULT, WAIT_RESULT, PRE_RESULT} <= native_contract["runtime_abi"]
    assert native_contract["pre_result_slots"][0xA0] == STATE_MAIN
    assert native_contract["pre_result_slots"][0xE0] == PRE_RESULT
    assert PRE_RESULT not in native_contract["calls"].values()


def test_optional_native_result_execution(native_contract):
    for dependency in ("unicorn", "capstone"):
        if importlib.util.find_spec(dependency) is None:
            pytest.skip(f"{dependency} required for bounded native result probes")
    environment = os.environ.copy()
    environment.pop("PYTHONFAULTHANDLER", None)
    ran = subprocess.run(
        [sys.executable, "-B", str(Path(__file__).resolve()), "--native-probes"],
        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=45,
    )
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert ran.stdout.strip() == "25 result/ending probes, 6 fade cleanup cases and listener-result/UI lifecycle: pass"


class Probe:
    """One original function, fake owned memory, and explicit external callbacks."""
    BASE = 0x10000000
    STOP = BASE + 0x7F000

    def __init__(self, contract, name, callback):
        import unicorn
        from unicorn import arm64_const
        import capstone
        self.regs = arm64_const
        self.vm = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
        self.start, self.size = contract["symbols"][name]
        self.callback, self.calls = callback, []
        first, last = self.start & ~0xFFF, (self.start + self.size + 0xFFF) & ~0xFFF
        self.vm.mem_map(first, last - first)
        self.vm.mem_write(self.start, contract["code"][name])
        self.vm.mem_map(self.BASE, 0x80000)
        self.vm.mem_map(0x959D000, 0x1000)  # only the captain function's GOT read
        self.vm.mem_map(0x9583000, 0x1000)  # MatchTop's singleton cell
        self.vm.mem_map(0x958E000, 0x1000)  # ending cleanup fade singleton cell
        self.vm.mem_map(0x95CA000, 0x1000)  # Mobile fade mutex GOT cell
        for address, content in contract["constants"].items():
            self.vm.mem_map(address, 0x1000)
            self.vm.mem_write(address, content)
        self.sites = {}
        decoder = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        for instruction in decoder.disasm(contract["code"][name], self.start):
            if instruction.mnemonic in ("bl", "b"):
                target = int(instruction.op_str.lstrip("#"), 0)
                if not self.start <= target < self.start + self.size:
                    assert target in contract["calls"], (name, instruction.address, target)
                    self.sites[instruction.address] = instruction.mnemonic, contract["calls"][target]
            elif instruction.mnemonic in ("blr", "br"):
                self.sites[instruction.address] = instruction.mnemonic, instruction.op_str
        self.vm.hook_add(unicorn.UC_HOOK_CODE, self.instruction)

    def reg(self, name):
        return getattr(self.regs, "UC_ARM64_REG_" + name.upper())

    def put(self, address, value, size=8):
        self.vm.mem_write(address, int(value).to_bytes(size, "little"))

    def get(self, address, size=8):
        return int.from_bytes(self.vm.mem_read(address, size), "little")

    def instruction(self, vm, address, _size, _context):
        assert self.start <= address < self.start + self.size, "external native code must never execute"
        if address not in self.sites:
            return
        kind, name = self.sites[address]
        if kind in ("br", "blr"):
            target = vm.reg_read(self.reg(name))
            if kind == "br" and self.start <= target < self.start + self.size:
                return  # original bounded switch table
            name = f"indirect:{target:#x}"
        args = tuple(vm.reg_read(self.reg(f"x{i}")) for i in range(5))
        self.calls.append((name, args, address))
        value = self.callback(self, name, args)
        if value is not None:
            vm.reg_write(self.reg("x0"), value)
        if kind in ("bl", "blr"):
            vm.reg_write(self.reg("lr"), address + 4)
            vm.reg_write(self.reg("pc"), address + 4)
        else:
            vm.reg_write(self.reg("pc"), vm.reg_read(self.reg("lr")))

    def run(self, *args):
        for index, value in enumerate(args):
            self.vm.reg_write(self.reg(f"x{index}"), value)
        stack = self.BASE + 0x7E000
        self.vm.reg_write(self.reg("sp"), stack)
        self.vm.reg_write(self.reg("lr"), self.STOP)
        try:
            self.vm.emu_start(self.start, self.STOP, timeout=1_000_000, count=30_000)
        except Exception as error:
            raise AssertionError(f"bounded native probe PC={self.vm.reg_read(self.reg('pc')):#x} calls={self.calls[-4:]}") from error
        assert self.vm.reg_read(self.reg("pc")) == self.STOP
        assert self.vm.reg_read(self.reg("sp")) == stack
        return self.vm.reg_read(self.reg("x0"))


def probe_result_invocation(contract):
    owner, registry, envwork = Probe.BASE + 0x1000, Probe.BASE + 0x2000, Probe.BASE + 0x3000
    env, candidate = Probe.BASE + 0x10000, Probe.BASE + 0x20000

    def callback(probe, name, args):
        if name == ENV:
            return env
        if name == "_ZN10FixDemoEnv10SetInMatchERKN5match8registry8RegistryE":
            assert args[:2] == (env, registry)
            return None
        if name == RESULT:
            assert args[:2] == (0x80001, 2)
            assert probe.calls[-1][2] + 4 == 0x620C1A4
            return candidate
        raise AssertionError(name)

    probe = Probe(contract, CREATE, callback)
    probe.put(owner, 0x80001, 4)
    probe.vm.mem_write(envwork, struct.pack("<6I", 2, 11, 12, 13, 14, 15))
    probe.run(owner, registry, envwork, 5, 2)
    assert probe.get(owner + 0x1E0) == candidate
    assert probe.get(owner + 0x1D8, 4) == 1 and probe.get(owner + 0x1D0, 4) == 2
    assert probe.get(env + 0x5234, 4) == probe.get(env + 0x5244, 4) == 2


def probe_winner_init(contract, side):
    manager, table, env = Probe.BASE + 0x1000, Probe.BASE + 0x2000, Probe.BASE + 0x10000

    def callback(_probe, name, args):
        if name == ENV:
            return env
        assert name in {"indirect:0x2010", "indirect:0x2020", "indirect:0x2030", "indirect:0x2040"}
        assert args[0] == manager

    probe = Probe(contract, INIT, callback)
    probe.put(manager, table)
    for offset, function in ((0xD0, 0x2010), (0x20, 0x2020), (0x78, 0x2030), (0x68, 0x2040)):
        probe.put(table + offset, function)
    probe.put(manager + 0x38, side, 4)
    probe.put(env + 0x5234, 2, 4)
    probe.put(env + 0x5244, 2, 4)
    probe.put(env + 0x525D, 1, 1)
    assert probe.run(manager) == 1
    assert probe.get(env + 0x5234, 4) == side
    assert probe.get(env + 0x5244, 4) == 2


def probe_real_captain(contract, side):
    manager, assign, cut = Probe.BASE + 0x1000, Probe.BASE + 0x2000, Probe.BASE + 0x3000
    humans, env = Probe.BASE + 0x4000, Probe.BASE + 0x10000
    selected = []

    def callback(_probe, name, args):
        if name == ENV:
            return env
        assert name == "_ZN7fixdemo10AssignList6ChangeEss"
        selected.append(args[:3])

    probe = Probe(contract, ASSIGN, callback)
    probe.put(manager + 0x38, side, 4)
    probe.put(manager + 0x80, humans)
    probe.put(manager + 0x88, humans + 4 * 8)
    probe.put(assign + 0x10, 1)
    probe.vm.mem_write(cut + 0x1C, bytes([1, 0, 0, 0]))
    # Actor IDs differ from starter indices; captains are intentionally not zero.
    for i, (actor, team, player) in enumerate(((20, 0, 0), (31, 0, 7), (42, 1, 0), (53, 1, 4))):
        probe.vm.mem_write(humans + i * 8, bytes([actor, 0, 0, 0, 0, team, player, 0]))
    probe.put(env + 0x129 + 7 * 0x100, 1, 1)
    probe.put(env + 0x2830 + 0x129 + 4 * 0x100, 1, 1)
    probe.put(env + 0x5244, 2, 4)  # original neutral result env must not affect kind 1
    probe.run(manager, assign, cut)
    assert selected == [(assign, 0, 31 if side == 0 else 53)]


def probe_cut_gate(contract, ready, permitted, skipped):
    manager, table, cut = Probe.BASE + 0x1000, Probe.BASE + 0x2000, Probe.BASE + 0x3000
    cut_table, env = Probe.BASE + 0x4000, Probe.BASE + 0x10000
    started = []

    def callback(_probe, name, args):
        if name == ENV:
            return env
        if name == READY:
            assert args[:4] == (manager, cut, 0, 1)
            return int(ready)
        if name == "indirect:0x2000":
            started.append(args[0])
            return None
        assert name in {
            "_ZN14FixDemoManager9UpdateFPSEv", "_ZN11FixDemoList11GetFadeTypeEh",
            "_ZN14FixDemoManager13StartCutReadyEP11FixDemoMainh", "_ZN14FixDemoManager8StartCutEv",
            "_ZN7fixdemo11DataManager18UpdateInGameThreadEv", "indirect:0x2010",
        }, name
        return 0

    probe = Probe(contract, MAIN, callback)
    probe.put(manager, table)
    probe.put(table + 0xC0, 0x2000)
    probe.put(manager + 0xE8, cut)
    probe.put(manager + 0x60, manager + 0x68)  # native empty actor-tree sentinel
    probe.put(cut, cut_table)
    probe.put(cut_table + 0x10, 0x2010)
    probe.put(manager + 0x1E0, 2, 4)
    probe.put(manager + 0x54, permitted, 1)
    probe.put(manager + 0x55, skipped, 1)
    probe.run(manager)
    assert started == ([manager] if ready and permitted and not skipped else [])
    expected = 7 if skipped else 2 if not ready else 5 if permitted else 4
    assert probe.get(manager + 0x1E0, 4) == expected
    assert any(name == "_ZN7fixdemo11DataManager18UpdateInGameThreadEv" for name, _, _ in probe.calls)


def probe_flow_exec(contract, state):
    owner, manager, table = Probe.BASE + 0x1000, Probe.BASE + 0x20000, Probe.BASE + 0x21000
    info, context, status, wait = Probe.BASE + 0x22000, Probe.BASE + 0x23000, Probe.BASE + 0x24000, Probe.BASE + 0x25000
    executed = []

    def callback(_probe, name, args):
        if name == "indirect:0x2000":
            assert args[:2] == (manager, info)
            executed.append(manager)
            return 0
        if name == "_ZN3sys6Status11GetInstanceEv":
            return status
        if name == "_ZN5match8registry11WaitControl11GetInstanceENS1_8CategoryE":
            return wait
        assert name in {
            "_ZN5match8registry11WaitControl19IsReceiveEndRequestEv",
            "_ZN5match8registry11WaitControl6IsWaitEv",
            "_ZN5match4Flow21FixDemoRefreshSettingEv",
            "_ZN14FixDemoManager23WarningNextCutStartLateEf",
            "_ZN5match8registry11WaitControl22IsReceiveCancelRequestEv",
        }, name
        return 0

    probe = Probe(contract, FLOW, callback)
    probe.put(owner + 0x1D8, state, 4)
    probe.put(owner + 0x1D4, 1, 1)
    probe.put(owner + 0x1E0, manager)
    probe.put(manager, table)
    probe.put(table + 0x30, 0x2000)
    probe.put(manager + 0x1E0, 2, 4)  # fresh result still loading
    probe.put(manager + 0x54, 1, 1)  # transferred native Start permission
    probe.put(status + 0x35, 1, 1)
    probe.run(owner, info, 1, context)
    assert executed == [manager]
    assert probe.get(owner + 0x1E0) == manager and probe.get(manager + 0x54, 1) == 1
    assert probe.get(owner + 0x1D8, 4) == {2: 3, 3: 3, 4: 5, 10: 10}[state]


def probe_match_top_dispatch(contract, state, expected):
    """Exercise the real switch table for both distinct listener owners."""
    listener, context, cell = Probe.BASE + 0x1000, Probe.BASE + 0x30000, Probe.BASE + 0x31000
    table = contract["constants"][0x85D7000]
    destination, callsite = {18: (0x7BF9270, 0x7BF9288),
                             19: (0x7BF9290, 0x7BF92A8)}[state]
    states = [index for index in range(22) if 0x7BF8F88 + 4 * table[0xBA2 + index] == destination]
    assert states == [state]
    entries = []

    def callback(probe, name, args):
        if name == expected:
            assert args[:2] == (listener, context)
            assert probe.calls[-1][2] == callsite
            entries.append(name)
            return None
        assert name in {
            "_ZN3sys6Status11GetInstanceEv", "_ZN5cobra3And11AnimManager11GetInstanceEj",
            "_ZN4draw32SetReserveAnimUpdateRequestStateEb", "_ZN4draw20SetAnimUpdateRequestEb",
            "_ZN9game_mode13MatchListener19UpdateSimulationOffEv",
            "_ZN9game_mode13MatchListener14CheckMatchWaitEv",
            "_ZN9game_mode13MatchListener17MatchCheckTimeOutEjj",
            "_ZN9game_mode13MatchListener19WaitSendMatchResultEPKN5cobra4game7ContextE",
            "_ZN9game_mode13MatchListener13ExecSyncStateEPKN5cobra4game7ContextE",
            "_ZN9game_mode13MatchListener14ExecPauseStateEPKN5cobra4game7ContextE",
            "_ZN9game_mode13MatchListener15ExecPkOrderSyncEPKN5cobra4game7ContextE",
        }, name
        return 0

    probe = Probe(contract, TOP, callback)
    probe.put(0x9583548, cell)
    probe.put(listener + 0x118, state, 1)
    probe.run(listener, context)
    assert entries == [expected]
    assert probe.get(listener + 0x118, 1) == state


def probe_wait_result_dispatch(contract):
    """The result request itself selects state 19, independently of Ending."""
    listener, context = Probe.BASE + 0x1000, Probe.BASE + 0x30000
    tmpdb, transient = Probe.BASE + 0x31000, Probe.BASE + 0x32000
    # State, result requested, result already enabled, native UI ready.
    for state, requested, complete, ui_ready in (
            (16, 1, 0, 1), (0, 1, 0, 1), (21, 1, 0, 1),
            (16, 0, 0, 1), (16, 1, 1, 1), (16, 1, 0, 0)):
        events = []

        def callback(probe, name, args):
            if name == "_ZN10onlinemode20TaskSendMatchCommand11GetInstanceEv":
                return 0  # ordinary offline result, no online task required
            if name == "_ZN5tmpdb7Manager11GetInstanceEv":
                return tmpdb
            if name == "_ZN9game_mode13MatchListener13PushFlowEventEPKN5cobra4game7ContextEj":
                assert args[:3] == (listener, context, 0x1050016)
                events.append("result-request")
                return None
            if name == SET_STATE:
                assert args[:2] == (listener, 19)
                # Execute the real setter too: it resets the native substep.
                setter = Probe(contract, SET_STATE, lambda *_: None)
                setter.vm.mem_write(listener, bytes(probe.vm.mem_read(listener, 0x1E8)))
                setter.run(*args[:2])
                probe.vm.mem_write(listener, bytes(setter.vm.mem_read(listener, 0x1E8)))
                events.append("state-19")
                return None
            if name == "_ZN5tmpdb13TransientWork15SetResultEnableEb":
                assert args[:2] == (transient, 1)
                probe.put(transient + 0x6CE0, 1, 1)
                events.append("ui-enabled")
                return None
            raise AssertionError(name)

        probe = Probe(contract, WAIT_RESULT, callback)
        probe.put(tmpdb + 0x50, transient)
        probe.put(listener + 0x118, state, 1)
        probe.put(listener + 0x119, 3, 1)
        probe.put(listener + 0x18FF0, requested, 1)
        probe.put(listener + 0x18FF2, complete, 1)
        probe.put(listener + 0x18FF3, ui_ready, 1)
        probe.run(listener, context)
        if state == 16 and requested and not complete and ui_ready:
            assert events == ["result-request", "state-19", "ui-enabled"]
            assert probe.get(listener + 0x118, 1) == 19
            assert probe.get(listener + 0x119, 1) == 0
            assert probe.get(listener + 0x18FF2, 1) == 1
            assert probe.get(transient + 0x6CE0, 1) == 1
            probe_match_top_dispatch(contract, probe.get(listener + 0x118, 1), LISTENER_RESULT)
        else:
            assert events == []
            assert probe.get(listener + 0x118, 1) == state
            assert probe.get(transient + 0x6CE0, 1) == 0


def probe_listener_result_invocation(contract, phase, cached):
    """Despite its name, the same native factory runs at half and full time."""
    listener, context = Probe.BASE + 0x1000, Probe.BASE + 0x30000
    match, mode, candidate = Probe.BASE + 0x32000, Probe.BASE + 0x34000, Probe.BASE + 0x35000
    factories, released = [], []

    def callback(probe, name, args):
        if name == STEP:
            return probe.get(listener + 0x119, 1)
        if name == SET_ENV:
            assert args[0] == listener
            return None
        if name == READ_LOCK:
            assert not cached
            expected = {listener + 0x1B308: (listener + 0x1B338, match),
                        listener + 0x1B768: (listener + 0x1B798, mode)}
            output, value = expected[args[0]]
            assert args[1] == output
            probe.put(output, value)
            return None
        if name == RESULT:
            assert args[:2] == (0x80001, 2)
            assert probe.calls[-1][2] + 4 == 0x7BF3340
            assert probe.get(match + 0x1168, 4) == phase
            # These native registered reads are still open during this factory.
            assert probe.get(listener + 0x1B338) == match
            assert probe.get(listener + 0x1B798) == mode
            assert released == []
            factories.append(candidate)
            return candidate
        if name == READ_UNLOCK:
            released.append(args[0])
            return None
        if name == "_ZN5match5Match15SetDispAllHumanEb":
            assert args[1] == 0
            return None
        if name == SET_STEP:
            assert args[:2] == (listener, 1)
            probe.put(listener + 0x119, args[1], 1)
            return None
        raise AssertionError(name)

    probe = Probe(contract, LISTENER_RESULT, callback)
    probe.put(listener + 0x118, 19, 1)
    probe.put(listener + 0x1B300, 1, 1)
    probe.put(listener + 0x1B338, match if cached else 0)
    probe.put(listener + 0x1B760, 1, 1)
    probe.put(listener + 0x1B798, mode if cached else 0)
    probe.put(match + 0x132C, 2, 4)
    probe.put(match + 0x1168, phase, 4)
    probe.run(listener, context)
    assert factories == [candidate]
    assert released == [listener + 0x1B308, listener + 0x1B768]
    assert probe.get(listener + 0x1B338) == probe.get(listener + 0x1B798) == 0
    assert probe.get(listener + 0x19018) == candidate
    assert probe.get(listener + 0x119, 1) == 1


def probe_result_ui_gate(contract, enabled):
    process, tmpdb, transient = Probe.BASE + 0x1000, Probe.BASE + 0x2000, Probe.BASE + 0x3000
    events = []

    def callback(probe, name, args):
        if name == "_ZN5tmpdb7Manager11GetInstanceEv":
            return tmpdb
        if name == "_ZNK5tmpdb13TransientWork15GetResultEnableEv":
            assert args[0] == transient
            return probe.get(transient + 0x6CE0, 1)
        if name == "_ZN5tmpdb13TransientWork15SetResultEnableEb":
            assert args[:2] == (transient, 0)
            probe.put(transient + 0x6CE0, 0, 1)
            events.append("consume-flag")
            return None
        if name == "_ZN7process4Base11PushFadeOutERKN5cobra3stl12basic_stringIcNSt6__ndk111char_traitsIcEENS2_9AllocatorIcEEEE":
            assert args[0] == process
            assert bytes(probe.vm.mem_read(args[1], 9)) == b"\x0eproceed\0"
            events.append("fade-proceed")
            return None
        raise AssertionError(name)

    probe = Probe(contract, PRE_RESULT, callback)
    probe.put(tmpdb + 0x50, transient)
    probe.put(transient + 0x6CE0, enabled, 1)
    returned = probe.run(process)
    assert returned == enabled
    assert events == (["consume-flag", "fade-proceed"] if enabled else [])
    assert probe.get(transient + 0x6CE0, 1) == 0

    # StateMain calls the derived Main through the actual vtable offset.
    table, main = Probe.BASE + 0x20000, 0x2000
    calls = []

    def virtual_callback(_probe, name, args):
        assert name == "indirect:0x2000" and args[0] == process
        calls.append(main)
        return returned

    dispatch = Probe(contract, STATE_MAIN, virtual_callback)
    dispatch.put(process, table)
    dispatch.put(table + 0xD0, main)
    assert dispatch.run(process) == returned
    assert calls == [main]


def probe_listener_result_owner(contract, step, present=True, ready=4, closed=1, fade_done=1):
    """Exercise native background restart and the distinct result close path."""
    listener, context, manager = Probe.BASE + 0x1000, Probe.BASE + 0x30000, Probe.BASE + 0x31000
    table, fade, fade_table, fade_cell = (Probe.BASE + n for n in (0x32000, 0x33000, 0x34000, 0x35000))
    events = []

    def callback(probe, name, args):
        if name == STEP:
            return probe.get(listener + 0x119, 1)
        if name == SET_STEP:
            assert args[0] == listener
            events.append(("step", args[1]))
            probe.put(listener + 0x119, args[1], 1)
            return None
        if name == SET_STATE:
            assert args[:2] == (listener, 17)
            events.append(("state", 17))
            probe.put(listener + 0x118, 17, 1)
            return None
        if name == "indirect:0x2000":
            assert present and args[:3] == (manager, 0, 0)
            events.append(("exec", manager))
            return None
        if name == "indirect:0x2010":
            assert present and args[0] == manager
            events.append(("delete", manager))
            return None
        assert args[0] == fade
        if name == "indirect:0x2020":
            assert args[1] == 0  # result cleanup owns fade level zero
            events.append(("fade-state", 0))
            return 3
        if name == "indirect:0x2030":
            assert args[1] == 0
            events.append(("fade-cancel", 0))
            return 1
        if name == "indirect:0x2040":
            assert args[:5] == (fade, 6, 0, 0, 0)
            assert probe.vm.reg_read(probe.reg("s0")) == (0 if closed else 0x3F000000)
            events.append(("fade-start", 6))
            return 1
        assert name == "indirect:0x2050" and args[1] == 0
        events.append(("fade-end", fade_done))
        return fade_done

    probe = Probe(contract, LISTENER_RESULT, callback)
    probe.put(listener + 0x118, 19, 1)
    probe.put(listener + 0x119, step, 1)
    probe.put(listener + 0x11C, closed, 1)
    probe.put(listener + 0x1D2, 1, 1)
    probe.put(listener + 0x19018, manager if present else 0)
    probe.put(manager, table)
    probe.put(table + 0x48, 0x2000)
    probe.put(table + 8, 0x2010)
    probe.put(manager + 0x1E0, ready, 4)
    probe.put(manager + 0x55, 1, 1)  # native loader preserves an existing Skip
    probe.put(0x958E7F8, fade_cell)
    probe.put(fade_cell, fade)
    probe.put(fade, fade_table)
    for offset, target in ((0x30, 0x2020), (0x20, 0x2030), (0x10, 0x2040), (0x48, 0x2050)):
        probe.put(fade_table + offset, target)
    if step == 1 and not present:
        # This intentional bounded fault proves why the adapter must not enter
        # loader step 1 after an ordinary Result factory returned NULL.
        with pytest.raises(AssertionError, match="PC=0x7bf33ac"):
            probe.run(listener, context)
        assert events == []
        return
    probe.run(listener, context)
    expected = [("exec", manager)] if present else []
    expected_step, expected_state = step, 19
    if step == 1:
        expected_step = 2 if ready == 4 else 1
        if ready == 4:
            expected.append(("step", 2))
        assert probe.get(manager + 0x54, 1) == int(ready == 4)
    elif step == 2:
        # With no manager the original function advances immediately, even
        # while the overview remains open. The adapter must hold this branch.
        if not present or closed:
            expected_step = 3
            expected.append(("step", 3))
    elif step == 3:
        expected_step = 5
        expected += [("fade-state", 0), ("fade-cancel", 0), ("fade-start", 6), ("step", 5)]
    elif step == 5:
        expected.append(("fade-end", fade_done))
        if fade_done:
            if present:
                expected.append(("delete", manager))
            if closed:
                expected_state = 17
                expected.append(("state", 17))
            else:
                expected_step = 7
                expected.append(("step", 7))
            assert probe.get(listener + 0x19018) == 0
            assert probe.get(listener + 0x1D2, 1) == 0
    else:
        raise AssertionError(step)
    assert events == expected, events
    assert probe.get(listener + 0x119, 1) == expected_step
    assert probe.get(listener + 0x118, 1) == expected_state
    assert probe.get(manager + 0x55, 1) == 1


def probe_manager_null_outputs(contract, ready, permitted, skipped):
    """Compose real ExecAll, Exec and ExecMain with only service calls mocked.

    Each function executes in its own bounded VM. Shared fake object memory is
    copied at the call boundary; external library code never executes.
    """
    manager, table, cut, cut_table, env = (Probe.BASE + n for n in (0x1000, 0x2000, 0x3000, 0x4000, 0x10000))
    events = []

    def callback(probe, name, args):
        nested_name = {"indirect:0x2000": EXEC, MAIN: MAIN}.get(name)
        if nested_name:
            if nested_name == EXEC:
                assert args[:2] == (manager, 0)
            nested = Probe(contract, nested_name, callback)
            nested.vm.mem_write(Probe.BASE, bytes(probe.vm.mem_read(Probe.BASE, 0x60000)))
            value = nested.run(*args[:2])
            probe.vm.mem_write(Probe.BASE, bytes(nested.vm.mem_read(Probe.BASE, 0x60000)))
            return value
        if name == ENV:
            return env
        if name == READY:
            assert args[:4] == (manager, cut, 0, 1)
            return ready
        if name == "indirect:0x2050":
            assert args[:2] == (manager, 0)  # final info publisher receives NULL too
            events.append("publish-null")
            return 0
        if name == "indirect:0x2060":
            assert args[0] == manager
            events.append("start")
            return 0
        if name == "indirect:0x2080":
            assert args[0] == cut
            events.append("cut-delete")
            return 0
        if name == "_ZN14FixDemoManager8CheckEndEv":
            return 1  # current cut has finished, without fabricating terminal state
        assert name in {
            "_ZN14FixDemoManager11SetDataLoadEv", "_ZN14FixDemoManager9UpdateFPSEv",
            "_ZN11FixDemoList11GetFadeTypeEh", "_ZN14FixDemoManager13StartCutReadyEP11FixDemoMainh",
            "_ZN14FixDemoManager8StartCutEv", "_ZN7fixdemo11DataManager18UpdateInGameThreadEv",
            "indirect:0x2010", "indirect:0x2020", "indirect:0x2030", "indirect:0x2040",
            "indirect:0x2090",
        }, name
        return 0

    probe = Probe(contract, EXEC_ALL, callback)
    probe.put(manager, table)
    for offset, target in ((0x30, 0x2000), (0x38, 0x2010), (0x40, 0x2020),
                           (0xB0, 0x2040), (0x90, 0x2050), (0xC0, 0x2060), (0x70, 0x2090)):
        probe.put(table + offset, target)
    probe.put(manager + 0xE8, cut)
    probe.put(manager + 0x60, manager + 0x68)
    probe.put(cut, cut_table)
    probe.put(cut_table + 0x10, 0x2030)
    probe.put(cut_table + 8, 0x2080)
    probe.put(manager + 0x1DC, 3, 4)  # native data loader has completed
    probe.put(manager + 0x1E0, 2, 4)  # first cut is checking readiness
    probe.put(manager + 0x54, permitted, 1)
    probe.put(manager + 0x55, skipped, 1)
    probe.run(manager, 0, 0)
    assert events.count("start") == int(ready and permitted and not skipped)
    assert probe.get(manager + 0x1E0, 4) == (7 if skipped else 2 if not ready else 5 if permitted else 4)
    assert probe.get(manager + 0x1DC, 4) == 3
    assert events.count("publish-null") == 1
    if skipped or (ready and permitted):
        if not skipped:
            # Seed the native playing-cut substate, then let CheckEnd select
            # cleanup and Exec select terminal state on the following tick.
            probe.put(manager + 0x1E0, 6, 4)
            probe.run(manager, 0, 0)
            assert probe.get(manager + 0x1E0, 4) == 7
            assert probe.get(manager + 0x1DC, 4) == 3
        probe.run(manager, 0, 0)
        assert probe.get(manager + 0x1DC, 4) == 4
        assert probe.get(manager + 0xE8) == 0
        assert events.count("cut-delete") == 1
        assert events.count("start") == int(not skipped)


def probe_manager_skip_before_load(contract):
    """Skip before load reaches Exec terminal state without waiting for Start."""
    manager, table, env = Probe.BASE + 0x1000, Probe.BASE + 0x2000, Probe.BASE + 0x10000
    events = []

    def callback(_probe, name, args):
        if name == ENV:
            return env
        assert name in {"indirect:0x2000", "indirect:0x2010"}
        assert args[0] == manager
        if name == "indirect:0x2010":
            assert args[1] == 0
        events.append(name)
        return 0

    probe = Probe(contract, EXEC, callback)
    probe.put(manager, table)
    probe.put(table + 0xB0, 0x2000)
    probe.put(table + 0x90, 0x2010)
    probe.put(manager + 0x55, 1, 1)
    probe.run(manager, 0)
    assert probe.get(manager + 0x1DC, 4) == 4
    assert probe.get(manager + 0x54, 1) == 0
    assert events == ["indirect:0x2000", "indirect:0x2010"]


def probe_result_ui_cooperative_wait(contract):
    """Returning false yields the process task; it never spins or blocks MatchTop."""
    # This private direct helper is decoded but must not execute on the wait path.
    contract = dict(contract, calls={**contract["calls"], 0x7BB6B40: "native-state-transition"})
    process, table, control = Probe.BASE + 0x1000, Probe.BASE + 0x2000, Probe.BASE + 0x3000
    events = []

    def callback(_probe, name, args):
        assert args[0] == process
        stage = {"indirect:0x2000": "pre", "indirect:0x2010": "main",
                 "indirect:0x2020": "post"}[name]
        events.append(stage)
        return 0

    probe = Probe(contract, TASK_ACTION, callback)
    probe.put(process, table)
    probe.put(process + 0x70, control)
    probe.put(control + 0x48, 1, 1)  # native task enabled
    probe.put(control + 0x4C, 10, 4)
    probe.put(table + 0x38, 0x2000)
    probe.put(table + 0x90, 0x2010)
    probe.put(table + 0x40, 0x2020)
    probe.run(process)
    assert events == ["pre", "main", "post"], events
    assert probe.get(control + 0x4C, 4) == 10


def probe_ending_invocation(contract, cached):
    listener, context, match = Probe.BASE + 0x1000, Probe.BASE + 0x30000, Probe.BASE + 0x32000
    candidate = Probe.BASE + 0x35000
    scene, side = (0x70004, 2) if not cached else (0x6000F, 1)
    released = []

    def callback(probe, name, args):
        if name == STEP:
            assert args[0] == listener
            return 0
        if name == SET_ENV:
            assert args[0] == listener
            return None
        if name == READ_LOCK:
            assert not cached and args[:2] == (listener + 0x1B308, listener + 0x1B338)
            probe.put(args[1], match)
            return None
        if name == READ_UNLOCK:
            assert args[0] == listener + 0x1B308
            released.append(args[0])
            return None
        if name == MATCH:
            assert released == [listener + 0x1B308]
            assert args[:2] == (scene, side)
            assert probe.calls[-1][2] + 4 == 0x7BF3C78
            assert probe.get(listener + 0x1B338) == 0  # native borrowed slot closed before factory
            return candidate
        if name == SET_STEP:
            assert args[:2] == (listener, 1)
            probe.put(listener + 0x119, args[1], 1)
            return None
        raise AssertionError(name)

    probe = Probe(contract, ENDING, callback)
    probe.put(listener + 0x1B300, 1, 1)
    probe.put(listener + 0x1B338, match if cached else 0)
    probe.put(match + 0x1324, scene, 4)
    probe.put(match + 0x1328, side, 4)
    probe.run(listener, context)
    assert probe.get(listener + 0x19018) == candidate
    assert probe.get(listener + 0x119, 1) == 1
    assert not any(name == RESULT for name, _, _ in probe.calls)


def probe_registry_read(contract, available):
    base, published, record, destination = (Probe.BASE + n for n in (0x1000, 0x2000, 0x3000, 0x4000))

    def callback(_probe, name, _args):
        raise AssertionError(name)

    probe = Probe(contract, READ_LOCK, callback)
    probe.put(base + 0x20, published if available else 0)
    probe.put(published + 8, record)
    probe.put(destination, 0xBAD)
    probe.run(base, destination)
    assert probe.get(destination) == (record if available else 0)
    assert probe.get(base + 0x20) == (published if available else 0)


def probe_ending_owner(contract, step, present=True):
    listener, context, manager = Probe.BASE + 0x1000, Probe.BASE + 0x30000, Probe.BASE + 0x31000
    table, info, screen = Probe.BASE + 0x32000, Probe.BASE + 0x33000, Probe.BASE + 0x34000
    fade, fade_table, fade_cell = Probe.BASE + 0x35000, Probe.BASE + 0x36000, Probe.BASE + 0x37000
    tmpdb, transient = Probe.BASE + 0x38000, Probe.BASE + 0x39000
    executed, deleted, result_enabled = [], [], []

    def callback(probe, name, args):
        if name == STEP:
            return step
        if name == SET_STEP:
            assert args[0] == listener
            probe.put(listener + 0x119, args[1], 1)
            return None
        if name == "indirect:0x2000":
            assert args[:3] == (manager, info, screen)
            executed.append(manager)
            return None
        if name == "indirect:0x2010":
            assert args[0] == manager
            deleted.append(manager)
            return None
        if name == "indirect:0x2020":
            assert args[:2] == (fade, 1)
            return 1
        if name == "_ZN9game_mode13MatchListener13SetMatchStateEh":
            assert args[:2] == (listener, 19)
            probe.put(listener + 0x118, 19, 1)
            return None
        if name == "_ZN5tmpdb7Manager11GetInstanceEv":
            return tmpdb
        if name == "_ZN5tmpdb13TransientWork15SetResultEnableEb":
            assert args[:2] == (transient, 1)
            result_enabled.append(1)
            return None
        assert name in {
            "_ZN6common8Registry7Manager11WriteUnlockEPNS0_4BaseE",
            "_ZN5match5Match19DeleteModelAllHumanEv",
            "_ZN9game_mode13MatchListener17SendMessageDirectEPKN5cobra4game7ContextEjPKvj",
        }, name
        return None

    probe = Probe(contract, ENDING, callback)
    probe.put(listener + 0x119, step, 1)
    probe.put(listener + 0x19018, manager if present else 0)
    probe.put(listener + 0x1BB20, 1, 1)
    probe.put(listener + 0x1BB60, info)
    probe.put(listener + 0x1B8A0, 1, 1)
    probe.put(listener + 0x1B8E0, screen)
    probe.put(manager, table)
    probe.put(table + 0x48, 0x2000)
    probe.put(table + 8, 0x2010)
    probe.put(manager + 0x1E0, 2, 4)
    probe.put(manager + 0x54, 0 if step == 4 else 1, 1)
    probe.put(manager + 0x55, 1, 1)  # native listener must preserve pending Skip
    probe.put(0x958E7F8, fade_cell)
    probe.put(fade_cell, fade)
    probe.put(fade, fade_table)
    probe.put(fade_table + 0x48, 0x2020)
    probe.put(tmpdb + 0x50, transient)
    probe.run(listener, context)
    assert executed == ([manager] if step != 7 and present else [])
    if step == 7:
        assert deleted == ([manager] if present else []) and result_enabled == [1]
        assert probe.get(listener + 0x19018) == 0
        assert probe.get(listener + 0x118, 1) == 19
    else:
        assert not deleted and not result_enabled
        assert probe.get(listener + 0x119, 1) == (7 if not present else 6 if step in (4, 5) else step)
        assert probe.get(manager + 0x54, 1) == probe.get(manager + 0x55, 1) == 1


def probe_base_fade(contract):
    def unexpected(_probe, name, _args):
        raise AssertionError(name)
    for function in (FADE_CANCEL, FADE_END):
        probe = Probe(contract, function, unexpected)
        assert probe.run(Probe.BASE + 0x1000, 1) == 1


def probe_impl_fade(contract, state):
    impl = Probe.BASE + 0x1000

    def unexpected(_probe, name, _args):
        raise AssertionError(name)

    before = Probe(contract, IMPL_END, unexpected)
    before.put(impl + 8, state, 4)
    assert before.run(impl) == int(state in (0, 2))
    cancel = Probe(contract, IMPL_CANCEL, unexpected)
    cancel.put(impl + 8, state, 4)
    cancel.put(impl + 12, 0x1234, 4)
    cancel.put(impl + 16, 0x5678, 4)
    assert cancel.run(impl) == 1
    assert cancel.get(impl + 8, 8) == cancel.get(impl + 16, 4) == 0
    after = Probe(contract, IMPL_END, unexpected)
    after.vm.mem_write(impl, bytes(cancel.vm.mem_read(impl, 0x18)))
    assert after.run(impl) == 1


def probe_mobile_fade(contract):
    manager, container, impl, table, mutex = (Probe.BASE + n for n in (0x1000, 0x2000, 0x3000, 0x4000, 0x5000))
    called = []

    def callback(probe, name, args):
        if name == "_ZN5basic5Mutex4LockEv":
            assert args[0] == mutex
            called.append("lock")
        elif name == "_ZN5basic5Mutex6UnlockEv":
            assert args[0] == mutex and called[-1] in ("cancel", "end")
            called.append("unlock")
        else:
            assert args[0] == impl and called[-1] == "lock"
            assert name in ("indirect:0x2000", "indirect:0x2010")
            called.append("cancel" if name.endswith("2000") else "end")
            return 1

    for function in (MOBILE_CANCEL, MOBILE_END):
        probe = Probe(contract, function, callback)
        probe.put(0x95CA0D8, mutex)
        probe.put(manager + 8 + 8, container)  # exactly fade level 1
        probe.put(container + 4, 2, 4)  # a nonzero active FADE_ID
        probe.put(container + 0x18 + 2 * 8, impl)
        probe.put(impl, table)
        probe.put(table + 0x40, 0x2000)
        probe.put(table + 0x30, 0x2010)
        assert probe.run(manager, 1) == 1
    assert called == ["lock", "cancel", "unlock", "lock", "end", "unlock"]


if __name__ == "__main__":
    assert sys.argv[1:] == ["--native-probes"]
    contract = read_contract()
    probe_result_invocation(contract)
    for side in (0, 1):
        probe_winner_init(contract, side)
        probe_real_captain(contract, side)
    for ready, permitted, skipped in ((0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1)):
        probe_cut_gate(contract, ready, permitted, skipped)
    for state in (2, 3, 4, 10):
        probe_flow_exec(contract, state)
    probe_match_top_dispatch(contract, 18, ENDING)
    probe_wait_result_dispatch(contract)
    for phase in (2, 10):
        for cached in (False, True):
            probe_listener_result_invocation(contract, phase, cached)
    for enabled in (0, 1):
        probe_result_ui_gate(contract, enabled)
    for ready in (2, 4):
        probe_listener_result_owner(contract, 1, ready=ready)
    probe_listener_result_owner(contract, 1, present=False)
    for present in (False, True):
        for closed in (0, 1):
            for step in (2, 3):
                probe_listener_result_owner(contract, step, present=present, closed=closed)
            for fade_done in (0, 1):
                probe_listener_result_owner(contract, 5, present=present, closed=closed, fade_done=fade_done)
    for ready, permitted, skipped in ((0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1)):
        probe_manager_null_outputs(contract, ready, permitted, skipped)
    probe_manager_skip_before_load(contract)
    probe_result_ui_cooperative_wait(contract)
    for cached in (False, True):
        probe_ending_invocation(contract, cached)
    for available in (False, True):
        probe_registry_read(contract, available)
    for step in (1, 4, 6, 7):
        probe_ending_owner(contract, step)
    probe_ending_owner(contract, 6, False)
    probe_ending_owner(contract, 7, False)
    probe_base_fade(contract)
    for state in range(4):
        probe_impl_fade(contract, state)
    probe_mobile_fade(contract)
    print("25 result/ending probes, 6 fade cleanup cases and listener-result/UI lifecycle: pass")
