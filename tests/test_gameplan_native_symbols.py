"""Check editor hooks against the user-owned runtime's real dynamic exports."""

import os
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
EDITOR_BINDINGS = (
    "match_formation_copy_assign",
    "match_squad_data_set_formation",
    "match_squad_data_set_player_role_position",
    "match_formation_set_position",
    "match_formation_set_role",
)


class GameplanNativeSymbolTests(unittest.TestCase):
    def test_editor_bindings_exist_as_defined_functions_in_runtime(self):
        configured = os.environ.get("PES21_NX_LIBUE4")
        library = Path(configured) if configured else ROOT / "dist/pes21_nx/libUE4.so"
        if not library.is_file() and not configured:
            self.skipTest("User-owned libUE4.so fixture is not installed")
        from elftools.elf.elffile import ELFFile

        hooks = (ROOT / "source/ue4_hooks.c").read_text(encoding="utf-8")
        bindings = {}
        for name in EDITOR_BINDINGS:
            match = re.search(
                rf'\b{re.escape(name)}\s*=\s*\(void \*\)so_find_addr_rx\('
                r'\s*module,\s*"([^"]+)"\s*\);', hooks,
            )
            self.assertIsNotNone(match, f"Missing required editor binding: {name}")
            bindings[name] = match.group(1)
        expected = set(bindings.values())
        with library.open("rb") as stream:
            elf = ELFFile(stream)
            self.assertEqual(elf.header.e_machine, "EM_AARCH64")
            dynsym = elf.get_section_by_name(".dynsym")
            self.assertIsNotNone(dynsym)
            found = {
                symbol.name for symbol in dynsym.iter_symbols()
                if symbol.name in expected
                and symbol["st_info"]["type"] == "STT_FUNC"
                and symbol["st_shndx"] != "SHN_UNDEF"
                and symbol["st_value"] != 0
            }
        for name, symbol in bindings.items():
            with self.subTest(binding=name):
                self.assertIn(symbol, found, f"{name}: unresolved in {library}: {symbol}")


if __name__ == "__main__":
    unittest.main()
