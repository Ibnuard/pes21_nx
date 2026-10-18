"""Compare camera parameters in locally owned FL26 PC and PES21 Mobile files.

Read-only; emits hashes/counts, not extracted tables or game instructions.
PC signatures are the compatibility locators documented by nesa24/juce in
CommonCam and StadiumCam (https://mapote.com/pes/nesa24-cameras-3.3.zip).
No Sider module or PC executable code is installed in the Switch runtime.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


class PeImage:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        data = self.data
        if data[:2] != b'MZ':
            raise ValueError('Expected a PE executable')
        nt = struct.unpack_from('<I', data, 0x3c)[0]
        if data[nt:nt+4] != b'PE\0\0':
            raise ValueError('Invalid PE header')
        if struct.unpack_from('<H', data, nt+24)[0] != 0x20b:
            raise ValueError('Expected a PE32+ executable')
        self.base = struct.unpack_from('<Q', data, nt+48)[0]
        count = struct.unpack_from('<H', data, nt+6)[0]
        optional = struct.unpack_from('<H', data, nt+20)[0]
        self.sections = []
        for i in range(count):
            section = nt+24+optional+i*40
            _, rva, size, offset = struct.unpack_from('<4I', data, section+8)
            if offset+size > len(data):
                raise ValueError('Truncated PE section')
            self.sections.append((self.base+rva, offset, size))

    def address(self, offset):
        for address, start, size in self.sections:
            if start <= offset < start+size:
                return address+offset-start
        raise ValueError('Signature outside a PE section')

    def read(self, address, count):
        for start, offset, size in self.sections:
            if start <= address and address+count <= start+size:
                return self.data[offset+address-start:offset+address-start+count]
        raise ValueError('Camera table outside a PE section')

    def table(self, pattern, displacement, next_instruction, count):
        offset = self.data.find(pattern)
        if offset < 0 or self.data.find(pattern, offset+1) >= 0:
            raise ValueError('Camera locator absent or ambiguous; do not guess offsets')
        relative = struct.unpack_from('<i', self.data, offset+displacement)[0]
        address = self.address(offset)+next_instruction+relative
        return self.read(address, count)


def audit(pc_path, mobile_path):
    from elftools.elf.elffile import ELFFile
    pc = PeImage(pc_path)
    # Ten common 9-float records; five broadcast/stadium 22-float records.
    schemas = (
        ('common_pitch_side', '84c0b9060000000f45d9f30f105f0c488d0d',
         0x12, 0x16, 360, 0x81c4580),
        ('stadium_broadcast', '48894527486341784c8d05',
         11, 15, 440, 0x81c4360),
    )
    tables = {}
    with Path(mobile_path).open('rb') as stream:
        elf = ELFFile(stream)
        if elf['e_machine'] != 'EM_AARCH64' or not elf.little_endian:
            raise ValueError('Expected the compatible AArch64 Mobile ELF')

        def read(address, count):
            offsets = list(elf.address_offsets(address))
            if len(offsets) != 1:
                raise ValueError('Mobile address is not backed by one segment')
            stream.seek(offsets[0])
            result = stream.read(count)
            if len(result) != count:
                raise ValueError('Truncated Mobile camera table')
            return result

        # Validate the actual instructions loading both Mobile table bases.
        # No scanning/writing guessed addresses in a different game revision.
        guards = ((0x665ed60, (0xd000db29, 0x91160129)),
                  (0x665d7ec, (0xf000db2a, 0x52800b09, 0x910d814a)))
        for address, words in guards:
            if read(address, len(words)*4) != struct.pack('<'+'I'*len(words), *words):
                raise ValueError('Incompatible Mobile camera table locator')

        for name, signature, relative, following, size, address in schemas:
            source = pc.table(bytes.fromhex(signature), relative, following, size)
            target = read(address, size)
            tables[name] = dict(bytes=size, floats=size//4, identical=source == target,
                                pc_sha256=hashlib.sha256(source).hexdigest(),
                                mobile_sha256=hashlib.sha256(target).hexdigest())
        registry = struct.unpack('<14I', read(0x85d7958, 56))
        ids = (1,)+struct.unpack('<13I', read(0x81cef54, 52))
        routes = {name: dict(tmpdb=t, registry=registry[t], camera_id=ids[registry[t]])
                  for name, t in (('pitch_side', 3), ('stadium', 12))}
        if routes['pitch_side']['camera_id'] != 1 or routes['stadium']['camera_id'] != 6:
            raise ValueError('Unexpected native preset route')
    with Path(mobile_path).open('rb') as stream:
        mobile_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(tables=tables, routes=routes,
                pc_exe_sha256=hashlib.sha256(pc.data).hexdigest(),
                mobile_elf_sha256=mobile_digest,
                all_tables_identical=all(t['identical'] for t in tables.values()),
                scope='Parameter equality and native IDs only; not full PC behavior or hardware FPS',
                hardware_tested=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pc-exe', required=True, type=Path)
    parser.add_argument('--mobile-elf', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.pc_exe, args.mobile_elf)
    text = json.dumps(result, indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(text, end='')
    if not result['all_tables_identical']:
        raise SystemExit(1)
