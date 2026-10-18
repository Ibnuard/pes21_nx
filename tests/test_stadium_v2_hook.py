"""Execute the real AArch64 mid-hook with hostile helper clobbers.

The compiled fixture is project-authored assembly in a temporary directory.
The optional no-op comparison reads four instructions from the owned local ELF;
no proprietary instruction bytes are embedded or copied into the public tree.
"""
from pathlib import Path
import importlib.util
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'dist/pes21_nx/libUE4.so'
SOURCE = ROOT / 'source/stadium_v2_hook.s'
NATIVE_SITE = 0x665e258
SCALAR_PAGE = 0x7e46000
STACK_BASE, STACK_SIZE = 0x20000000, 0x10000
ORIGINAL_SP = STACK_BASE + 0x8000
CAMERA, BALL = 0x30000000, 0x30001000


def compiler_command():
    """Use an installed cross toolchain only; never acquire a compiler."""
    candidates = [shutil.which('aarch64-none-elf-gcc'),
                  shutil.which('aarch64-linux-gnu-gcc')]
    if os.environ.get('DEVKITA64'):
        candidates.append(str(Path(os.environ['DEVKITA64']) / 'bin' /
                              ('aarch64-none-elf-gcc.exe' if os.name == 'nt'
                               else 'aarch64-none-elf-gcc')))
    if os.name == 'nt':
        candidates.append('C:/devkitPro/devkitA64/bin/aarch64-none-elf-gcc.exe')
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return [candidate]
    clang, linker = shutil.which('clang'), shutil.which('ld.lld')
    if clang and linker:
        return [clang, '--target=aarch64-none-elf', '-fuse-ld=lld']
    return None


def helper_source():
    # The helper deliberately violates SIMD callee preservation too: the
    # mid-function hook promises to save all live vector bits, not merely the
    # low halves of q8..q15 required by an ordinary C function-call boundary.
    lines = ['.text', '.align 2', '.global pes_stadium_v2_target',
             'pes_stadium_v2_target:',
             'adrp x9, hook_arguments', 'add x9, x9, :lo12:hook_arguments',
             'stp x0, x1, [x9]', 'str x2, [x9, #16]',
             'mov x10, sp', 'str x10, [x9, #24]',
             'adrp x10, hook_enabled', 'ldr w10, [x10, :lo12:hook_enabled]',
             'cbz w10, 1f', 'ldr x10, [x2]', 'ldr w11, [x2, #8]',
             'str x10, [x1]', 'str w11, [x1, #8]', '1:',
             'sub sp, sp, #16', 'str x30, [sp]']
    lines += [f'mov x{i}, #{0x6000 + i}' for i in range(19)]
    lines += [f'movi v{i}.16b, #{0x80 + i}' for i in range(32)]
    lines += ['mov x17, #0xf0000000', 'msr nzcv, x17',
              'mov x17, #0x9f', 'msr fpsr, x17',
              'mov x30, #0xfeed', 'ldr x30, [sp]', 'add sp, sp, #16', 'ret',
              '.global hook_resume', 'hook_resume:', 'nop', 'ret',
              '.data', '.align 3', '.global stadium_v2_height_page',
              'stadium_v2_height_page: .quad 0',
              '.global stadium_v2_target_resume',
              'stadium_v2_target_resume: .quad 0',
              '.global hook_arguments', 'hook_arguments: .zero 32',
              '.global hook_enabled', 'hook_enabled: .word 0']
    return '\n'.join(lines) + '\n'


def execute_oracle(compare_native=False):
    from elftools.elf.elffile import ELFFile
    from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
    import unicorn.arm64_const as regs

    command = compiler_command()
    assert command, 'installed AArch64 cross assembler/linker unavailable'
    with tempfile.TemporaryDirectory(prefix='stadium-v2-hook-') as temp:
        temp = Path(temp)
        helper, binary = temp / 'helper.s', temp / 'hook.elf'
        helper.write_text(helper_source())
        built = subprocess.run(command + ['-nostdlib', '-Wl,--build-id=none',
            '-Wl,-Ttext=0x100000', '-Wl,-e,pes_stadium_v2_target_hook',
            str(SOURCE), str(helper), '-o', str(binary)],
            capture_output=True, text=True, timeout=30)
        assert built.returncode == 0, built.stdout + built.stderr
        with binary.open('rb') as stream:
            elf = ELFFile(stream)
            symbols = {s.name: s['st_value']
                       for s in elf.get_section_by_name('.symtab').iter_symbols()}
            segments = [(s['p_vaddr'], s['p_memsz'], s.data())
                        for s in elf.iter_segments() if s['p_type'] == 'PT_LOAD']

        scalar = struct.pack('<f', .2)
        native = None
        if compare_native:
            with LIBRARY.open('rb') as stream:
                elf = ELFFile(stream)
                stream.seek(next(elf.address_offsets(NATIVE_SITE)))
                native = stream.read(16)
                stream.seek(next(elf.address_offsets(SCALAR_PAGE + 0xeb8)))
                scalar = stream.read(4)

        initial_target = struct.pack('<3f', -33.5, 2.75, 18.25)
        physical_ball = struct.pack('<3f', 14.5, 1.125, -23.75)
        original_x = [0x1234000000000100 + i * 0x101 for i in range(31)]
        original_x[21], original_x[26] = CAMERA, BALL
        original_q = [int.from_bytes(bytes((i * 17 + j * 11) & 255
                                          for j in range(16)), 'little')
                      for i in range(32)]
        xregs = [getattr(regs, f'UC_ARM64_REG_X{i}') for i in range(29)] + [
                 regs.UC_ARM64_REG_FP, regs.UC_ARM64_REG_LR]
        qregs = [getattr(regs, f'UC_ARM64_REG_Q{i}') for i in range(32)]

        def machine():
            uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
            mapped = set()
            for address, size, data in segments:
                for page in range(address & ~4095, (address + size + 4095) & ~4095, 4096):
                    if page not in mapped:
                        uc.mem_map(page, 4096)
                        mapped.add(page)
                uc.mem_write(address, data)
            uc.mem_map(STACK_BASE, STACK_SIZE)
            uc.mem_write(STACK_BASE, b'\xa5' * STACK_SIZE)
            uc.mem_map(CAMERA, 0x2000)
            uc.mem_map(SCALAR_PAGE, 4096)
            uc.mem_write(SCALAR_PAGE + 0xeb8, scalar)
            uc.mem_write(BALL, physical_ball)
            uc.mem_write(ORIGINAL_SP + 0x130, initial_target)
            uc.mem_write(symbols['stadium_v2_height_page'], struct.pack('<Q', SCALAR_PAGE))
            uc.mem_write(symbols['stadium_v2_target_resume'], struct.pack('<Q', symbols['hook_resume']))
            for reg, value in zip(xregs, original_x):
                uc.reg_write(reg, value)
            for reg, value in zip(qregs, original_q):
                uc.reg_write(reg, value)
            uc.reg_write(regs.UC_ARM64_REG_SP, ORIGINAL_SP)
            uc.reg_write(regs.UC_ARM64_REG_NZCV, 0x60000000)
            uc.reg_write(regs.UC_ARM64_REG_FPSR, 0x10)
            uc.reg_write(regs.UC_ARM64_REG_FPCR, 0)
            return uc

        def snapshot(uc):
            return ([uc.reg_read(r) for r in xregs],
                    [uc.reg_read(r) for r in qregs],
                    [uc.reg_read(r) for r in (regs.UC_ARM64_REG_SP,
                     regs.UC_ARM64_REG_NZCV, regs.UC_ARM64_REG_FPSR,
                     regs.UC_ARM64_REG_FPCR)])

        for enabled in (False, True):
            uc = machine()
            untouched = bytes(uc.mem_read(ORIGINAL_SP, 0x200))
            uc.mem_write(symbols['hook_enabled'], struct.pack('<I', enabled))
            uc.emu_start(symbols['pes_stadium_v2_target_hook'], symbols['hook_resume'], count=1000)
            assert uc.reg_read(regs.UC_ARM64_REG_PC) == symbols['hook_resume']
            arguments = struct.unpack('<4Q', uc.mem_read(symbols['hook_arguments'], 32))
            assert arguments == (CAMERA, ORIGINAL_SP + 0x130, BALL, ORIGINAL_SP - 0x2b0), arguments
            target = physical_ball if enabled else initial_target
            expected_memory = bytearray(untouched)
            expected_memory[0x130:0x13c] = target
            assert bytes(uc.mem_read(ORIGINAL_SP, 0x200)) == expected_memory
            xs, qs, status = snapshot(uc)
            expected_x = original_x.copy()
            expected_x[8], expected_x[17] = SCALAR_PAGE, symbols['hook_resume']
            expected_q = original_q.copy()
            expected_q[0] = struct.unpack('<I', struct.pack('<f', 4))[0]
            expected_q[1] = struct.unpack('<I', target[4:8])[0]
            expected_q[15] = struct.unpack('<I', scalar)[0]
            for i, (actual, expected) in enumerate(zip(xs, expected_x)):
                assert actual == expected, ('GPR', enabled, i, hex(actual), hex(expected))
            for i, (actual, expected) in enumerate(zip(qs, expected_q)):
                assert actual == expected, ('SIMD', enabled, i, hex(actual), hex(expected))
            assert status == [ORIGINAL_SP, 0x60000000, 0x10, 0], status
            if native is not None and not enabled:
                direct = machine()
                direct.mem_map(NATIVE_SITE & ~4095, 4096)
                direct.mem_write(NATIVE_SITE, native)
                direct.emu_start(NATIVE_SITE, NATIVE_SITE + 16, count=4)
                native_x, native_q, native_status = snapshot(direct)
                # x17 is the hook_arm64/resume branch scratch, explicitly
                # dead at this site; all other instruction results must match.
                native_x[17] = xs[17]
                assert (xs, qs, status) == (native_x, native_q, native_status)
                assert bytes(direct.mem_read(ORIGINAL_SP, 0x200)) == untouched
        print('Actual AArch64 target trampoline: helper ABI, GPR/SIMD/status preservation and displaced replay passed.'
              + (' Owned native no-op equivalence passed.' if native is not None else ''))


class StadiumV2HookTests(unittest.TestCase):
    def run_oracle(self, native=False):
        if not all(importlib.util.find_spec(name) for name in ('elftools', 'unicorn')):
            self.skipTest('optional pyelftools/unicorn unavailable')
        if not compiler_command():
            self.skipTest('optional installed AArch64 cross assembler/linker unavailable')
        if native and not LIBRARY.is_file():
            self.skipTest('optional owned compatible PES21 ELF unavailable')
        # Keep Unicorn out of pytest's Windows in-process hook machinery.
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                 '--native-oracle' if native else '--oracle'],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_actual_trampoline_registers_and_helper_contract(self):
        self.run_oracle()

    def test_owned_native_displaced_noop_equivalence(self):
        self.run_oracle(native=True)


if __name__ == '__main__':
    if '--oracle' in sys.argv or '--native-oracle' in sys.argv:
        execute_oracle(compare_native='--native-oracle' in sys.argv)
    else:
        unittest.main()
