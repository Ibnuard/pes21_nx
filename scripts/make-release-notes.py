#!/usr/bin/env python3
"""Build GitHub release notes from the public changelog and progress docs."""

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def extract_heading(text: str, heading: str) -> str:
    lines = text.splitlines()
    marker = f"## {heading}".lower()
    start = next(
        (index for index, line in enumerate(lines) if line.strip().lower() == marker),
        None,
    )
    if start is None:
        raise ValueError(f"Missing section: ## {heading}")

    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    return "\n".join(lines[start + 1 : end]).strip()


def extract_changelog(text: str, version: str) -> str:
    lines = text.splitlines()
    pattern = re.compile(
        rf"^##\s+\[?v?{re.escape(version)}\]?(?:\s+-\s+.*)?$", re.IGNORECASE
    )
    start = next(
        (index for index, line in enumerate(lines) if pattern.match(line.strip())),
        None,
    )
    if start is None:
        raise ValueError(f"CHANGELOG.md has no section for {version}")

    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    return "\n".join(lines[start + 1 : end]).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="Release tag, e.g. v0.1.94")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    version = args.version.removeprefix("v")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    development = (ROOT / "DEVELOPMENT.md").read_text(encoding="utf-8")

    compatibility = extract_heading(readme, "Compatibility target")
    changes = extract_changelog(changelog, version)
    progress = extract_heading(development, f"Wrapper version {version}")
    runtime_preparer = extract_heading(development, "Runtime preparer")
    rendering_fix = extract_heading(development, "Rendering fix")

    notes = f"""# PES 2021 NX v{version}

## Compatibility target

{compatibility}

## Changelog

{changes}

## Development progress

{progress}

## Runtime preparer

{runtime_preparer}

## Rendering fix

{rendering_fix}

## Release files

- `pes21_nx-v{version}.nro` - source-built Nintendo Switch wrapper
- `pes21_nx-v{version}.nro.sha256` - SHA-256 checksum
- `PES21NX-Prepare-v{version}.zip` - Windows one-folder preparation bundle
- `PES21NX-Prepare-v{version}.zip.sha256` - bundle SHA-256 checksum
- `PES21NX-Prepare.exe` - standalone Windows runtime preparer

This release contains the compatibility wrapper and project-owned preparation
tools only. It does not contain an APK, OBB, native game libraries, PAK/CPK
archives, extracted assets, generated offline response payloads, private keys,
or other proprietary game content.
"""
    args.output.write_text(notes, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
