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
PLAYER_AUDIO_PREFIX = "commentary/players-v59"
PLAYER_SEED = "commentary/players-v53.nxcp"
REFEREE_TOKEN = "referee-probe.txt"


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


def asset_limit(name: str) -> int:
    """Keep large payload exceptions confined to their runtime namespaces."""
    key = normalize(name)
    if key == PLAYER_SEED:
        return 8 * 1024 * 1024
    if key == REFEREE_TOKEN:
        return 128
    if key == PLAYER_AUDIO_PREFIX + "/catalog-id.txt":
        return 64
    parts = key.split("/")
    if (len(parts) == 4 and "/".join(parts[:3]) == PLAYER_AUDIO_PREFIX + "/audio"
            and parts[3].endswith(".hca")):
        return 2 * 1024 * 1024
    for folder, (suffix, limit) in FOLDERS.items():
        if len(parts) == 2 and parts[0] == folder.lower() and parts[1].endswith(suffix):
            return limit
    raise ValueError(f"unsupported archive asset: {name!r}")


def collect(root: Path) -> dict[str, Path]:
    result = {}
    base = root.resolve(strict=True)

    def add(path: Path, name: str) -> None:
        path.resolve(strict=True).relative_to(base)
        key = normalize(name)
        if key in result:
            raise ValueError(f"duplicate case-insensitive path: {key}")
        if not 0 < path.stat().st_size <= asset_limit(key):
            raise ValueError(f"asset exceeds reader limit: {path}")
        result[key] = path

    for folder, (suffix, _) in FOLDERS.items():
        directory = base / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or path.suffix.lower() != suffix:
                continue
            add(path, folder + "/" + path.name)
    audio = base / "Commentary/players-v59/audio"
    if audio.is_dir():
        for path in sorted(audio.iterdir()):
            if path.is_file() and path.suffix.lower() == ".hca":
                add(path, PLAYER_AUDIO_PREFIX + "/audio/" + path.name)
    for name in (REFEREE_TOKEN, "Commentary/players-v59/catalog-id.txt"):
        path = base / name
        if path.is_file():
            add(path, name)
    if not 0 < len(result) <= 4096:
        raise ValueError("archive requires 1..4096 supported assets")
    return dict(sorted(result.items()))


def _read_archive(archive: Path, expected: dict[str, Path | bytes] | None,
                  namespace_prefix: str | None, retain: bool) -> tuple[dict, dict[str, bytes]]:
    if namespace_prefix is not None and normalize(namespace_prefix) != PLAYER_AUDIO_PREFIX:
        raise ValueError("unsupported archive namespace prefix")
    entries = {}
    contents = {}
    archive_hash = hashlib.sha256()
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
        if len(index) != count * stride:
            raise ValueError("truncated archive index")
        archive_hash.update(header)
        archive_hash.update(index)
        cursor = payload
        previous = ""
        for i in range(count):
            name, offset, size, digest, flags, reserved = ENTRY.unpack_from(index, i * stride)
            key_bytes, separator, padding = name.partition(b"\0")
            key = key_bytes.decode("ascii")
            policy_key = key if namespace_prefix is None else PLAYER_AUDIO_PREFIX + "/" + key
            if (not separator or any(padding) or normalize(key) != key or key <= previous
                    or offset != cursor or not size or size > asset_limit(policy_key)
                    or size > total - cursor or flags or reserved):
                raise ValueError("invalid archive entry")
            f.seek(offset)
            data = f.read(size)
            if len(data) != size or checksum(data) != digest:
                raise ValueError(f"damaged asset: {key}")
            if expected is not None:
                source = expected.get(key)
                if source is None or data != (source.read_bytes() if isinstance(source, Path) else source):
                    raise ValueError(f"archive/source mismatch: {key}")
            archive_hash.update(data)
            entries[key] = {"bytes": size, "sha256": hashlib.sha256(data).hexdigest()}
            if retain:
                contents[key] = data
            previous, cursor = key, cursor + size
        if cursor != total or f.read(1) or (expected is not None and entries.keys() != expected.keys()):
            raise ValueError("unexpected or missing archive data")
    return {"entries": entries, "bytes": total, "sha256": archive_hash.hexdigest()}, contents


def verify(archive: Path, expected: dict[str, Path | bytes] | None = None, *,
           namespace_prefix: str | None = None) -> dict:
    """Verify a runtime archive, or a standalone roster pack with explicit prefix."""
    return _read_archive(archive, expected, namespace_prefix, False)[0]


def read_archive(archive: Path, *, namespace_prefix: str | None = None) -> tuple[dict, dict[str, bytes]]:
    """Return verified member bytes from the same read used for their hashes."""
    return _read_archive(archive, None, namespace_prefix, True)


def pack(root: Path, output: Path) -> dict:
    return pack_entries(collect(root), output)


def pack_entries(files: dict[str, Path | bytes], output: Path) -> dict:
    """Atomically write normalized typed entries and verify all bytes on readback."""
    if not 0 < len(files) <= 4096:
        raise ValueError("archive requires 1..4096 supported assets")
    normalized = {}
    for name, source in files.items():
        key = normalize(name)
        if key in normalized:
            raise ValueError(f"duplicate case-insensitive path: {key}")
        size = source.stat().st_size if isinstance(source, Path) else len(source)
        if not 0 < size <= asset_limit(key):
            raise ValueError(f"asset exceeds reader limit: {name}")
        normalized[key] = source
    files = dict(sorted(normalized.items()))
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.resolve() in {p.resolve() for p in files.values() if isinstance(p, Path)}:
        raise ValueError("output would overwrite an input asset")
    payload = HEADER.size + len(files) * ENTRY.size
    cursor = payload
    index = bytearray()
    for key, source in files.items():
        data = source.read_bytes() if isinstance(source, Path) else source
        index += ENTRY.pack(key.encode("ascii"), cursor, len(data), checksum(data), 0, 0)
        cursor += len(data)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=output.name + ".", suffix=".tmp", delete=False) as f:
            temp_name = Path(f.name)
            f.write(HEADER.pack(MAGIC, len(files), ENTRY.size, cursor, payload))
            f.write(index)
            for source in files.values():
                f.write(source.read_bytes() if isinstance(source, Path) else source)
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
    parser.add_argument("--namespace-prefix", help="explicit standalone roster archive namespace for verification")
    args = parser.parse_args()
    if not args.verify_only and args.root is None:
        parser.error("--root is required when packing")
    if args.namespace_prefix and (not args.verify_only or args.root):
        parser.error("--namespace-prefix requires --verify-only without --root")
    report = (verify(args.output, collect(args.root) if args.root else None,
                     namespace_prefix=args.namespace_prefix) if args.verify_only else pack(args.root, args.output))
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Verified {len(report['entries'])} assets, {report['bytes']} bytes: {args.output}")


if __name__ == "__main__":
    main()
