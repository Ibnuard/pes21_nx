"""Optional execution of the owned native LOD setter; no game code is stored."""
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_realface_performance import audit_runtime_lod

LIBRARY = ROOT / "dist/pes21_nx/libUE4.so"


@unittest.skipUnless(LIBRARY.is_file(), "requires ignored compatible Mobile libUE4.so")
class NativeFaceLODTests(unittest.TestCase):
    def test_actor_quality_uses_same_face_loader_and_forcing_cannot_invent_lods(self):
        try:
            from elftools.elf.elffile import ELFFile
            from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
            import unicorn.arm64_const as regs
        except ImportError:
            self.skipTest("requires local pyelftools and unicorn")
        proof = audit_runtime_lod(LIBRARY)
        self.assertEqual(len(proof["actor_face_loaders"]), 3)
        self.assertEqual({r["virtual_byte_offset"] for r in proof["actor_face_loaders"].values()}, {0x630})
        with LIBRARY.open("rb") as stream:
            elf = ELFFile(stream)
            address = proof["force_lod_address"]
            stream.seek(next(elf.address_offsets(address)))
            code = stream.read(proof["force_lod_bytes"])
        uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        page = address & ~0xfff
        uc.mem_map(page, 0x2000)
        uc.mem_write(address, code)
        arena, stop = 0x110000000, 0x120000000
        uc.mem_map(arena, 0x10000)
        uc.mem_map(stop, 0x1000)
        component, mesh_object, render_data = arena, arena + 0x2000, arena + 0x4000
        uc.mem_write(mesh_object + 0x40, struct.pack("<Q", render_data))
        for slot in (0x5a0, 0x6c0):
            uc.mem_write(component + 0x5a0, struct.pack("<Q", 0))
            uc.mem_write(component + 0x6c0, struct.pack("<Q", 0))
            uc.mem_write(component + slot, struct.pack("<Q", mesh_object))
            self.check_lod_counts(uc, regs, address, stop, component, render_data, slot)

    def check_lod_counts(self, uc, regs, address, stop, component, render_data, slot):
        for lod_count in (1, 2, 3):
            uc.mem_write(render_data + 8, struct.pack("<I", lod_count))
            for requested in (-1, 0, 1, 2, 3, 99):
                with self.subTest(mesh_slot=hex(slot), available=lod_count, requested=requested):
                    uc.reg_write(regs.UC_ARM64_REG_X0, component)
                    uc.reg_write(regs.UC_ARM64_REG_X1, requested & 0xffffffff)
                    uc.reg_write(regs.UC_ARM64_REG_LR, stop)
                    uc.emu_start(address, stop, count=100)
                    self.assertEqual(uc.reg_read(regs.UC_ARM64_REG_PC), stop)
                    forced, = struct.unpack("<I", uc.mem_read(component + 0x660, 4))
                    self.assertEqual(forced, max(0, min(requested, lod_count)))
                    if lod_count == 1 and requested > 0:
                        # Native ForcedLOD is 1-based: 1 always selects LOD0.
                        self.assertEqual(forced - 1, 0)
