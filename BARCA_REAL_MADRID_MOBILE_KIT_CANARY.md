# Barcelona + Real Madrid Mobile Kit Canary

For the hardware-verified release and final integration procedure, see
[Stable migration guide](KITS_LOGOS_STABLE_MIGRATION.md). This document describes
asset preparation; its intermediate CPKs are not release-ready archives.

This is a detached data/assets experiment for team IDs `108` (FC Barcelona)
and `109` (Real Madrid CF). It converts Football Life PC uniform textures to
the PES21 Mobile `Uniform16` atlas and prepares isolated CPK candidates. It
does not wire the runtime, modify the OBB, overwrite `dist`, or change the
stable build.

## Scope

- Home, away, and goalkeeper body atlases: `p1`, `p2`, `g1`.
- Number/back textures for all six kits.
- Football Life `realUni` descriptors, replacing existing Barcelona rows and
  adding the missing Real Madrid rows.
- Team names/codes for rows `108` and `109` only.
- Real-uniform flag at Team.bin offset `84`: Madrid `4 -> 15`; Barcelona stays
  `15`.

The PC/mobile mask audit found the same part layout across 158 paired masks.
The approved transform is anisotropic bicubic resize from `2048x2048` to
`256x384`, with no crop and no part reordering. Back textures become `320x40`
RGBA PNGs.

## Generate the detached candidate

From the repository root:

```text
python tools/build_barca_real_madrid_mobile_kit_canary.py
python tools/build_barca_real_madrid_mobile_kit_canary.py --package-cpks
```

To layer the pack onto a newer explicitly selected candidate without relaxing
the Football Life asset hashes, use a fresh output directory:

```text
python tools/build_barca_real_madrid_mobile_kit_canary.py --dt120 <new-dt120.cpk> --dt200 <new-dt200.cpk> --allow-base-drift --output-dir <fresh-output-dir> --package-cpks
```

Outputs are written under `local-debug/barca-madrid-license-canary/generated-v6`:

- `payloads/dt120`: 12 converted PNGs.
- `payloads/dt200`: six descriptors and a patched `Team.bin`.
- `dt120_barca_real_madrid_canary.cpk`: six replacements and six additions.
- `dt200_barca_real_madrid_canary.cpk`: four replacements and three additions.
- `canary-report.json`: source hashes, actions, and byte-identity audit.

The dt200 base is the gameplay agent's v5 candidate. `Team.bin` is extracted
from that selected archive before patching, so unrelated candidate changes are
preserved. The detached repacker verifies every non-target member byte-for-byte.

## Validation

```text
python -m unittest -q tests/test_barca_real_madrid_mobile_kit_canary.py
python tools/build_barca_real_madrid_mobile_kit_canary.py --check
```

The optional local integration test is skipped when the Football Life source
directory or canary archives are unavailable. Do not copy these CPKs into the
runtime/OBB until the gameplay agent's hardware test and an explicit integration
checkpoint are complete.
