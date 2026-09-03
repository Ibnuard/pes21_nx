"""List AArch64 direct-call sites targeting selected virtual addresses."""
import argparse
import struct
from pathlib import Path

from elftools.elf.elffile import ELFFile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library", type=Path)
    parser.add_argument("targets", nargs="+", type=lambda value: int(value, 0))
    args = parser.parse_args()

    with args.library.open("rb") as stream:
        elf = ELFFile(stream)
        text = elf.get_section_by_name(".text")
        data = text.data()
        base = text["sh_addr"]
        targets = set(args.targets)
        for offset in range(0, len(data), 4):
            word = struct.unpack_from("<I", data, offset)[0]
            if word >> 26 != 0x25:  # BL immediate
                continue
            immediate = word & 0x03FFFFFF
            if immediate & (1 << 25):
                immediate -= 1 << 26
            address = base + offset
            target = address + (immediate << 2)
            if target in targets:
                print(f"{address:#x} -> {target:#x}")


if __name__ == "__main__":
    main()
