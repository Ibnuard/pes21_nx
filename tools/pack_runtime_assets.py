"""Pack locally supplied optional logos/commentary/motions into FootballNX.assets.

No source files are removed. The archive is deterministic and the CLI verifies
every entry after writing it. Keep archives containing game assets ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile

MAGIC = b"FNXAS01\0"
HEADER = struct.Struct("<8sIIQQ")
ENTRY = struct.Struct("<128sQQQII")
FOLDERS = {"CupLogos": (".png", 2_000_000),
           "LeagueLogos": (".png", 2_000_000),
           "Commentary": (".nxcp", 1_048_576),
           "Animations": (".nxra", 524_288),
           "Scoreboards": (".nxsb", 2_000_000)}


def normalize(name: str) -> str:
    encoded = name.encode("ascii")
    if (not encoded or len(encoded) >= 128 or any(c < 32 or c >= 127 for c in encoded)
            or ":" in name or "\\" in name
            or any(part in ("", ".", "..") for part in name.split("/"))):
        raise ValueError(f"invalid archive path: {name!r}")
    return name.lower()


def checksum(data: bytes) -> int:
    value = 0xcbf29ce484222325
    for byte in data:
        value = ((value ^ byte) * 0x100000001b3) & 0xffffffffffffffff
    return value


def collect(root: Path) -> dict[str, Path]:
    result = {}
    base = root.resolve(strict=True)
    for folder, (suffix, limit) in FOLDERS.items():
        directory = base / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.suffix.lower() != suffix:
                continue
            path.resolve(strict=True).relative_to(base)
            key = normalize(folder + "/" + path.name)
            if key in result:
                raise ValueError(f"duplicate case-insensitive path: {key}")
            if not 0 < path.stat().st_size <= limit:
                raise ValueError(f"asset exceeds reader limit: {path}")
            result[key] = path
    if not 0 < len(result) <= 4096:
        raise ValueError("archive requires 1..4096 supported assets")
    return dict(sorted(result.items()))


def verify(archive: Path, expected: dict[str, Path] | None = None) -> dict:
    entries = {}
    with archive.open("rb") as f:
        header = f.read(HEADER.size)
        if len(header) != HEADER.size:
            raise ValueError("truncated header")
        magic, count, stride, total, payload = HEADER.unpack(header)
        if (magic != MAGIC or not 0 < count <= 4096 or stride != ENTRY.size
                or total != archive.stat().st_size or payload != HEADER.size + count * stride
                or payload > total):
            raise ValueError("invalid archive header")
        index = f.read(count * stride)
        cursor = payload
        previous = ""
        for i in range(count):
            name, offset, size, digest, flags, reserved = ENTRY.unpack_from(index, i * stride)
            key_bytes, separator, padding = name.partition(b"\0")
            key = key_bytes.decode("ascii")
            if (not separator or any(padding) or normalize(key) != key or key <= previous
                    or offset != cursor or not size or size > 2_000_000
                    or size > total - cursor or flags or reserved):
                raise ValueError("invalid archive entry")
            f.seek(offset)
            data = f.read(size)
            if len(data) != size or checksum(data) != digest:
                raise ValueError(f"damaged asset: {key}")
            if expected is not None and (key not in expected or data != expected[key].read_bytes()):
                raise ValueError(f"archive/source mismatch: {key}")
            entries[key] = {"bytes": size, "sha256": hashlib.sha256(data).hexdigest()}
            previous, cursor = key, cursor + size
        if cursor != total or (expected is not None and entries.keys() != expected.keys()):
            raise ValueError("unexpected or missing archive data")
    return {"entries": entries, "bytes": total,
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}


def pack(root: Path, output: Path) -> dict:
    files = collect(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.resolve() in {p.resolve() for p in files.values()}:
        raise ValueError("output would overwrite an input asset")
    payload = HEADER.size + len(files) * ENTRY.size
    cursor = payload
    index = bytearray()
    for key, path in files.items():
        data = path.read_bytes()
        index += ENTRY.pack(key.encode("ascii"), cursor, len(data), checksum(data), 0, 0)
        cursor += len(data)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=output.name + ".", suffix=".tmp", delete=False) as f:
            temp_name = Path(f.name)
            f.write(HEADER.pack(MAGIC, len(files), ENTRY.size, cursor, payload))
            f.write(index)
            for path in files.values():
                f.write(path.read_bytes())
        report = verify(temp_name, files)
        os.replace(temp_name, output)
        temp_name = None
        return report
    finally:
        if temp_name is not None:
            temp_name.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="runtime folder containing loose assets")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.verify_only and args.root is None:
        parser.error("--root is required when packing")
    report = verify(args.output, collect(args.root) if args.root else None) if args.verify_only else pack(args.root, args.output)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Verified {len(report['entries'])} assets, {report['bytes']} bytes: {args.output}")


if __name__ == "__main__":
    main()
