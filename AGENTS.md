# Agent workspace guide

## Project boundary

PES 2021 NX is a Nintendo Switch compatibility wrapper for the legally
obtained PES 2021 Mobile v5.3.0 Nyan Mod Offline runtime. Repository source,
project-authored tools, tests, documentation, and generated public assets may
be committed. APK/OBB/CPK/PAK files, extracted game libraries, saves, private
keys, raw disassembly, and other proprietary game data must remain local and
ignored.

## Canonical layout

- `source/`: wrapper and runtime hook sources.
- `tools/`: data conversion, packaging, and diagnostic utilities.
- `scripts/`: repository checks and build helpers.
- `tests/`: automated tests; some integration tests require ignored local
  fixtures and should report that requirement clearly when unavailable.
- `data/`: committed project-authored runtime data and manifests.
- `art/`: editable project artwork and previews.
- `docs/`: implementation notes, migration reports, and historical audits.
- `guides/`: maintained guides. Raw reverse-engineering references belong in
  ignored `guides/decompiler/raw/`, never in the public tree.
- `local-inputs/`: one canonical local copy of the compatible APK/OBB inputs.
- `dist/pes21_nx/`: active prepared runtime only, not an archive directory.
- `local-checkpoints/`: at most two complete recent binary checkpoints.
- `local-debug/`: disposable output only. Do not use it as permanent storage.

## Working rules

1. Read `README.md`, `DEVELOPMENT.md`, and the relevant file under `docs/`
   before changing a subsystem.
2. Preserve unrelated dirty changes. Never reset, overwrite, or reformat user
   work outside the requested scope.
3. Search with `rg`/`rg --files`. Treat paths in ignored local directories as
   optional inputs, not repository guarantees.
4. Do not duplicate OBBs between experiment folders. Reuse `local-inputs/`,
   generate into a temporary directory, promote only the validated runtime,
   and retain no more than two checkpoints.
5. Remove obsolete logs, dumps, extracted trees, and intermediate archives
   after a test is resolved. Keep durable findings as concise documentation.
6. Never commit copyrighted game payloads or raw decompiler output. Run
   `scripts/check-public-tree.ps1` before committing.
7. Many legacy integration tests require fixtures regenerated under
   `local-debug/`. A missing ignored fixture is an unavailable local test, not
   permission to restore or commit proprietary extracted data.

## Build and verification

From PowerShell, the normal build entry point is:

```powershell
.\build-wsl.ps1
```

Run focused tests for the changed subsystem first, then the broader suite when
its optional fixtures are available:

```powershell
python -m pytest tests/<relevant_test>.py -q
python -m pytest -q
```

Verify the public tree before a commit:

```powershell
.\scripts\check-public-tree.ps1
git status --short
```

## PESDB identity policy

- Use eFootball `BaseId` as the master cross-update identity.
- Keep a persistent `BaseId -> NativePES21Id` mapping; native IDs are engine
  storage keys and may be pinned to preserve face or commentary assets.
- Build one canonical player per BaseId, then attach club and national-team
  assignments. Never duplicate a player because they have multiple teams or
  card variations.
- Validate identity using BaseId plus a fingerprint before carrying an old
  face/commentary asset. A reused numeric ID alone is not proof of identity.
- Rebuild all dependent PESDB references together and preserve fixed record
  counts, sort requirements, and version tables.
- New portraits, faces, and commentary require explicit asset policies; do
  not silently inherit donor assets from a reused slot.
