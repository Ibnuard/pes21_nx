#!/usr/bin/env python3
"""Build a concise GitHub release body from the public changelog."""

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


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
    parser.add_argument("--version", required=True, help="Release tag, e.g. v0.1.95")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    version = args.version.removeprefix("v")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    changes = extract_changelog(changelog, version)

    notes = f"""## Changelog

{changes}

## Notes

- Supported target: PES 2021 Mobile v5.3.0 Nyan Mod Offline
  (`versionCode 305030001`, package `jp.nyan2021.pesam`).
- Follow the **How to install** section in the repository README.
- Release files contain only the compatibility wrapper and project-authored
  preparation tools. Users must supply a legally obtained compatible APK and
  both OBB files; proprietary game content is not included.
"""
    args.output.write_text(notes, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
