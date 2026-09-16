# Visual revision 15 canary - bright nine-band pitch

Status: host-validated canary, not yet tested on Switch hardware. Revision 14
remains the stable pitch and is not overwritten.

## Requested appearance

- Brighter green than revision 14.
- Nine alternating mowing bands on each half, 18 across the full pitch.
- Symmetric left/right geometry with a clean light-left/dark-right transition
  at midfield.
- Mowing transitions aligned to the two native penalty-box fronts instead of
  visibly crossing those white lines at different offsets.

## Geometry

The first equal-fit attempt used `770 / 9 = 85.5556` texture pixels per band.
It produced nine bands, but the outer penalty-box fronts landed at x494/x530
while the closest mowing transitions landed at x511/x514. The error therefore
appeared with opposite direction on the two halves.

The corrected recipe divides each half around the native line geometry:

| Segment | Bands | Width per band |
| --- | ---: | ---: |
| Goal line to goal-area front | 1 | 77 px |
| Goal-area front to penalty-box front | 2 | 81.5 px |
| Penalty-box front to midfield | 6 | 88.3333 px |

Left playable boundaries are
`254, 331, 412, 494, 582, 670, 759, 847, 935, 1024` after integer texture
rasterization. The right side is the
exact world-space mirror. Goal lines, goal-area fronts, penalty-box fronts, and
midfield are all exact mowing boundaries. The cadence continues through the
turf outside both goal lines rather than clamping the padding to one shade.

## Color and retained data

- Dark RGB: `[36, 63, 17]`.
- Light RGB: `[60, 96, 29]`.
- EF10 fine-grain gain: `[2.8, 5.6, 2.1]`.
- Native white-line ETC1 blocks are preserved at every mip.
- Dimensions, formats, headers, materials, shaders, masks, and the detail
  layer remain identical to the accepted revision 8 package structure.
- Runtime NRO, OBB, rosters, kits, Game Plan, and stable `dist/` are untouched.

## Canary output

The detached package is generated under:

`local-debug/visual-v15-bright-nine-canary/package-v4/PesMobile-Android_ETC1_P.pak`

The full-pitch preview is:

`local-debug/visual-v15-bright-nine-canary/pitch-build-v4/uniform-source/previews/pitch_lr_bsm_exLow_alp-after.png`

## Reproduction and verification

```powershell
python tools/build_uniform_pitch_patch.py --style clean-v15 --output local-debug/visual-v15-bright-nine-canary/pitch-build-v4
repak pack --version V8A --compression Zlib local-debug/visual-v15-bright-nine-canary/pitch-build-v4/pitch-stage local-debug/visual-v15-bright-nine-canary/package-v4/PesMobile-Android_ETC1_P.pak
New-Item -ItemType Directory -Force local-debug/visual-v15-bright-nine-canary/verify-v4
repak unpack local-debug/visual-v15-bright-nine-canary/package-v4/PesMobile-Android_ETC1_P.pak --output local-debug/visual-v15-bright-nine-canary/verify-v4/pitch-stage
python tools/build_uniform_pitch_patch.py --style clean-v15 --output local-debug/visual-v15-bright-nine-canary/verify-v4 --verify-only
```

The unpacked PAK must report 27 files, 19 unchanged files, nine visible bands
per half, preserved line blocks, phase-locked L/R/LR payloads, and
`device_tested: false` until the Switch canary test is complete.
