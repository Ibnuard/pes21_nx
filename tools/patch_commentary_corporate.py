"""Replace the two corporate images in the legacy commentary override CPK."""
import json
import shutil
import struct
from pathlib import Path

from prepare_runtime import read_cpk_packet, decrypt_utf, parse_utf_table
from build_androswitch_corporate_splash import sha256_file


def main():
    source = Path('dist/pes21_nx/Download/dt510_mobile_eng_all.cpk')
    output = Path('local-debug/startup-brand-v3/install/Download') / source.name
    if output.exists():
        raise FileExistsError(output)
    with source.open('rb') as f:
        header = read_cpk_packet(f, 0, b'CPK ')[0]
        toc = header['TocOffset']
        f.seek(toc + 8)
        size = struct.unpack('<Q', f.read(8))[0]
        original = f.read(size)
        decoded = bytearray(decrypt_utf(original))
        # This pack deliberately damages only the first three column-name
        # offsets. Resolve those names for inspection; preserve the original
        # descriptor bytes in the released pack.
        inspect = bytearray(decoded)
        strings = 8 + struct.unpack_from('>I', inspect, 12)[0]
        for index, name in enumerate((b'DirName', b'FileName', b'FileSize')):
            struct.pack_into('>I', inspect, 33 + index * 5,
                             inspect.index(name + b'\0', strings) - strings)
        rows = parse_utf_table(bytes(inspect))
        base = min(toc, header['ContentOffset'])
        row_start = 8 + struct.unpack_from('>I', decoded, 8)[0]
        stride = struct.unpack_from('>H', decoded, 26)[0]
        assert stride == 32
        patches = []
        for i, row in enumerate(rows):
            name = row['FileName']
            if name not in ('titleCorporate_konami.bin', 'titleCorporate_konami_wide.bin'):
                continue
            replacement = Path('local-debug/startup-brand-v2/cpk-work') / name.replace('.bin', '-androswitch.bin')
            payload = replacement.read_bytes()
            assert len(payload) <= row['FileSize']
            struct.pack_into('>II', decoded, row_start + i * stride + 8, len(payload), len(payload))
            patches.append((base + row['FileOffset'], row['FileSize'], payload, name))
        assert len(patches) == 2
        modified = decrypt_utf(bytes(decoded))
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)
    with output.open('r+b') as f:
        f.seek(toc + 16)
        f.write(modified)
        for start, size, payload, name in patches:
            f.seek(start)
            f.write(payload + bytes(size - len(payload)))
    # Every non-image payload, including commentary, must remain identical.
    count = 0
    with source.open('rb') as old, output.open('rb') as new:
        for row in rows:
            if row['FileName'].startswith('titleCorporate_'):
                continue
            old.seek(base + row['FileOffset'])
            new.seek(base + row['FileOffset'])
            remaining = row['FileSize']
            while remaining:
                size = min(4 * 1024 * 1024, remaining)
                assert old.read(size) == new.read(size)
                remaining -= size
            count += 1
        for start, _size, payload, _name in patches:
            new.seek(start)
            assert new.read(len(payload)) == payload
    report = {'output': str(output), 'sha256': sha256_file(output),
              'unrelated_members_byte_identical': count,
              'replaced': [p[3] for p in patches]}
    output.with_suffix('.report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
