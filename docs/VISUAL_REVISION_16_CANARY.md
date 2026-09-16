# Visual revision 16 canary - softer nine-band contrast

Status: host-validated canary, not yet tested on Switch hardware. Revision 15
remains unchanged and available for rollback.

## Requested adjustment

- Raise only the dark mowing shade so it sits closer to the light shade.
- Preserve revision 15's brighter overall look.
- Preserve nine alternating bands on each half, 18 across the full pitch.
- Preserve every goal-line, goal-area, penalty-box, and midfield alignment.

## Palette-only change

| Revision | Dark RGB | Light RGB | Green-channel separation |
| --- | --- | --- | ---: |
| v15 | `[36, 63, 17]` | `[60, 96, 29]` | 33 |
| v16 | `[42, 72, 20]` | `[60, 96, 29]` | 24 |

The light band and EF10 fine-grain gain `[2.8, 5.6, 2.1]` are unchanged.
The dark band increases by `[6, 9, 3]`, reducing the green-channel contrast by
about 27 percent without flattening the mowing pattern.

## Geometry and retained data

Revision 16 uses the exact revision 15 mowing mask at every supported texture
width. The left playable boundaries remain
`254, 331, 412, 494, 582, 670, 759, 847, 935, 1024`, and the right half remains
its world-space mirror. Native white-line ETC1 blocks are preserved at every
mip. Dimensions, formats, headers, materials, shaders, masks, and detail layer
remain unchanged.

Runtime NRO, OBB, rosters, kits, Game Plan, Makefile, stable `dist/`, and all
revision 15 outputs are untouched.

## Canary output

PAK:

`local-debug/visual-v16-soft-contrast-canary/package-v1/PesMobile-Android_ETC1_P.pak`

- Size: 4,274,166 bytes
- SHA-256: `0DBE633D6FBF7C91D044F82A3A1C436B9E52DB6C1EA44EFFD6D046285EF91C58`
- Unreal PAK version: V8A, Zlib, 27 files

Full-pitch preview:

`local-debug/visual-v16-soft-contrast-canary/pitch-build-v1/uniform-source/previews/pitch_lr_bsm_exLow_alp-after.png`

## Reproduction and verification

```powershell
python tools/build_uniform_pitch_patch.py --style clean-v16 --output local-debug/visual-v16-soft-contrast-canary/pitch-build-v1
repak pack --version V8A --compression Zlib local-debug/visual-v16-soft-contrast-canary/pitch-build-v1/pitch-stage local-debug/visual-v16-soft-contrast-canary/package-v1/PesMobile-Android_ETC1_P.pak
New-Item -ItemType Directory -Force local-debug/visual-v16-soft-contrast-canary/verify-v1
repak unpack local-debug/visual-v16-soft-contrast-canary/package-v1/PesMobile-Android_ETC1_P.pak --output local-debug/visual-v16-soft-contrast-canary/verify-v1/pitch-stage
python tools/build_uniform_pitch_patch.py --style clean-v16 --output local-debug/visual-v16-soft-contrast-canary/verify-v1 --verify-only
```

The verified package contains 27 files, round-trips with zero byte differences,
keeps 19 files byte-identical to v15, and changes only the eight diffuse
payload files expected from the palette adjustment.

## Device test and rollback

For the Switch canary, replace only
`switch/pes21_nx/PesMobile/Content/Paks/PesMobile-Android_ETC1_P.pak`, then fully
restart the game. Check the contrast under multiple stadium lighting conditions
and camera distances.

To restore the immediately preceding look, use:

`local-debug/visual-v15-bright-nine-canary/package-v4/PesMobile-Android_ETC1_P.pak`

The older accepted revision 14 remains at:

`local-debug/visual-v14-stable-20260901/install/PesMobile-Android_ETC1_P.pak`
