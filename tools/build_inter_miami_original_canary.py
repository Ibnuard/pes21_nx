#!/usr/bin/env python3
"""Build a rollback-safe CPK canary for the Inter Miami original-ID test.

The player experiment was generated from one exact PES21 database base. This
tool refuses to patch a different CPK (including the deployed custom OBB), so
the canary cannot accidentally overwrite unrelated roster/catalog work.
It only replaces the three player-table members listed by the experiment
manifest; Team.bin, selector data, kits, and the release tree stay untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT = Path("local-debug/efootball10-original-inter-miami-canary")
DEFAULT_BASE_CPK = Path("local-debug/efootball10-audit/old-cpk/dt200_mobile_all.cpk")
DEFAULT_OUTPUT = (
    DEFAULT_ARTIFACT / "cpk" / "dt200_mobile_all_inter_miami_canary.cpk"
)
EXPECTED_MEMBERS = 2435
REPLACED_MEMBERS = (
    "common/etc/pesdb/InstallVersionPlayer.bin",
    "common/etc/pesdb/Player.bin",
    "common/etc/pesdb/PlayerDeleteList.bin",
)


def resolve(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def member_name(row: dict[str, Any]) -> str:
    return "/".join(
        part
        for part in (str(row.get("DirName") or ""), str(row.get("FileName") or ""))
        if part and part != "<NULL>"
    )


def cpk_rows(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    sys.path.insert(0, str(ROOT / "tools"))
    from prepare_runtime import read_cpk_packet

    with path.open("rb") as source:
        header = read_cpk_packet(source, 0, b"CPK ")[0]
        rows = read_cpk_packet(source, int(header["TocOffset"]), b"TOC ")
    return header, rows, min(int(header["TocOffset"]), int(header["ContentOffset"]))


def member_bytes(path: Path, header: dict[str, Any], row: dict[str, Any], base: int) -> bytes:
    with path.open("rb") as source:
        source.seek(base + int(row["FileOffset"]))
        payload = source.read(int(row["FileSize"]))
    if len(payload) != int(row["FileSize"]):
        raise RuntimeError(f"truncated CPK member: {member_name(row)}")
    return payload


def load_report(artifact: Path) -> dict[str, Any]:
    report_path = artifact / "validation-report.json"
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("validation report must be an object")
    return payload


def validate_base(base_cpk: Path, artifact: Path, report: dict[str, Any]) -> dict[str, Any]:
    header, rows, data_base = cpk_rows(base_cpk)
    if len(rows) != EXPECTED_MEMBERS:
        raise RuntimeError(
            f"unexpected CPK member count: expected {EXPECTED_MEMBERS}, found {len(rows)}"
        )
    by_name = {member_name(row): row for row in rows}
    source_hashes = report.get("source_sha256", {})
    if not isinstance(source_hashes, dict):
        raise ValueError("validation report has no source_sha256 object")
    observed: dict[str, str] = {}
    for short_name in ("Player.bin", "InstallVersionPlayer.bin", "PlayerDeleteList.bin"):
        member = f"common/etc/pesdb/{short_name}"
        if member not in by_name:
            raise RuntimeError(f"base CPK is missing {member}")
        digest = sha256_bytes(member_bytes(base_cpk, header, by_name[member], data_base))
        observed[short_name] = digest
        expected = source_hashes.get(short_name)
        if expected != digest:
            raise RuntimeError(
                f"base CPK mismatch for {short_name}: expected {expected}, observed {digest}"
            )

    manifest = artifact / "cpk-replacement-manifest.json"
    if not manifest.is_file():
        raise FileNotFoundError(manifest)
    replacements = json.loads(manifest.read_text(encoding="utf-8"))
    if set(replacements) != set(REPLACED_MEMBERS):
        raise RuntimeError("replacement manifest does not match the three player tables")
    replacement_hashes: dict[str, str] = {}
    replacement_sizes: dict[str, int] = {}
    for member, filename in replacements.items():
        replacement = (manifest.parent / filename).resolve()
        if not replacement.is_file():
            raise FileNotFoundError(replacement)
        replacement_hashes[member] = sha256_file(replacement)
        replacement_sizes[member] = replacement.stat().st_size

    return {
        "base_cpk": str(base_cpk),
        "base_size": base_cpk.stat().st_size,
        "base_sha256": sha256_file(base_cpk),
        "member_count": len(rows),
        "source_member_sha256": observed,
        "replacement_member_sha256": replacement_hashes,
        "replacement_member_sizes": replacement_sizes,
        "replaced_members": list(REPLACED_MEMBERS),
    }


def validate_output(
    base_cpk: Path, output_cpk: Path, report: dict[str, Any]
) -> dict[str, Any]:
    old_header, old_rows, old_base = cpk_rows(base_cpk)
    new_header, new_rows, new_base = cpk_rows(output_cpk)
    if len(old_rows) != len(new_rows):
        raise RuntimeError("repack changed the CPK member count")
    old_by_name = {member_name(row): row for row in old_rows}
    new_by_name = {member_name(row): row for row in new_rows}
    if set(old_by_name) != set(new_by_name):
        raise RuntimeError("repack changed the CPK member set")
    changed: list[str] = []
    unrelated = 0
    with base_cpk.open("rb") as old, output_cpk.open("rb") as new:
        for name, old_row in old_by_name.items():
            new_row = new_by_name[name]
            old.seek(old_base + int(old_row["FileOffset"]))
            old_payload = old.read(int(old_row["FileSize"]))
            new.seek(new_base + int(new_row["FileOffset"]))
            new_payload = new.read(int(new_row["FileSize"]))
            if name in REPLACED_MEMBERS:
                changed.append(name)
                continue
            if old_row["FileSize"] != new_row["FileSize"] or old_payload != new_payload:
                raise RuntimeError(f"unrelated CPK member changed: {name}")
            unrelated += 1

    expected_output = report.get("output_sha256", {})
    output_hashes: dict[str, str] = {}
    for short_name in ("Player.bin", "InstallVersionPlayer.bin", "PlayerDeleteList.bin"):
        name = f"common/etc/pesdb/{short_name}"
        row = new_by_name[name]
        payload = member_bytes(output_cpk, new_header, row, new_base)
        output_hashes[short_name] = sha256_bytes(payload)
        if expected_output.get(short_name) != output_hashes[short_name]:
            raise RuntimeError(f"output hash mismatch for {short_name}")

    return {
        "output_cpk": str(output_cpk),
        "output_size": output_cpk.stat().st_size,
        "output_sha256": sha256_file(output_cpk),
        "member_count": len(new_rows),
        "changed_members": changed,
        "unrelated_members_byte_identical": unrelated,
        "output_member_sha256": output_hashes,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    artifact = resolve(args.artifact)
    base_cpk = resolve(args.base_cpk)
    output_cpk = resolve(args.output)
    report = load_report(artifact)
    preflight = validate_base(base_cpk, artifact, report)
    if args.check:
        print(json.dumps({"check": "pass", "preflight": preflight}, indent=2))
        return {"check": "pass", "preflight": preflight}
    if output_cpk.exists() and not args.force:
        raise RuntimeError(f"refusing to overwrite existing canary: {output_cpk}")

    manifest = artifact / "cpk-replacement-manifest.json"
    output_cpk.parent.mkdir(parents=True, exist_ok=True)
    repacker = Path(__file__).with_name("repack_cpk_members.py")
    subprocess.run(
        [
            sys.executable,
            str(repacker),
            str(base_cpk),
            str(output_cpk),
            "--expect-members",
            str(EXPECTED_MEMBERS),
            "--replace-manifest",
            str(manifest),
        ],
        check=True,
    )
    output = validate_output(base_cpk, output_cpk, report)
    package_report = {
        "schema_version": 1,
        "experiment": "inter_miami_original_id",
        "mode": report.get("mode", "canary"),
        "status": "player_table_cpk_canary",
        "runtime_integration": False,
        "team_record_import": False,
        "stable_release_tree_touched": False,
        "rollback": {
            "action": "remove the canary CPK and restore the original base CPK",
            "base_cpk": str(base_cpk),
            "release_obb_modified": False,
        },
        "preflight": preflight,
        "output": output,
    }
    report_path = output_cpk.parent / "canary-package-validation.json"
    report_path.write_text(json.dumps(package_report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(package_report, indent=2))
    return package_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--base-cpk", type=Path, default=DEFAULT_BASE_CPK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--force", action="store_true")
    build(parser.parse_args())


if __name__ == "__main__":
    main()
