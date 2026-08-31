# Visual v10 - broad pitch stripes, small alignment correction

Pitch-only stable baseline: `local-debug/visual-v10-20260831/install/`.
Host/package validation passed and the user confirmed the Switch test on
1 September 2026. V10 supersedes v8 as the stable pitch baseline. V9's ten
narrow bands per half remain rejected.

## Geometry

V8 uses six bands across each **padded** 1024px half texture, not six bands
inside the painted pitch. Its stripe width is 170.6667px. V10 uses 176.6667px:
only **3.515625% wider** than v8, instead of v9's 77px.

Three equal bands span from the native penalty-box front (left x494) to
midfield (x1024): `(1024 - 494) / 3`. The same spacing extends throughout the
texture, including beyond the goal line. No band is locally stretched or
compressed. There are five visible bands per half, with the outer one continuing
outside the goal line as in v8. This is not five complete bands fitted into each
painted half.

The penalty-box front and midfield are aligned. The goal line x254 and small-box
front x331/332 are preserved, but are **not** all stripe boundaries. Exact
alignment to all differently spaced markings would require much smaller strips
or unequal widths, contrary to the requested broad, uniform pattern.

The Low_R alias keeps v8's original shader mirror and opposite color phase:
left adjacent to midfield is light, right adjacent is dark. Standard/exLow
left/right and combined LR textures use the same world spacing. The combined
texture has half the horizontal texel density, so its width is 88.3333px.

## Unchanged

- V8 dark/light RGB `[26,46,12]` / `[49,77,23]` and EF10 grain gain `[2.8,5.6,2.1]`.
- Native white-line ETC1 blocks at every mip, package headers, dimensions,
  metadata, shaders, material bindings, masks and tiled-detail layer.
- NRO, controller/helper/cursor code, camera/frame pacing, OBB, scoreboard,
  rosters, portraits and saves. No runtime build or `dist/` overwrite.

## Verification and reproduction

15 Python tests pass, including broad-width/alignment, uniformity through the
mirrored center, L/R/LR scale and retained historical recipes. Six diffuse
textures (26 mip payloads) are rebuilt. The PAK contains 27 files: only eight
pixel-payload files change; all other 19 match v8 byte-for-byte. Independently
unpacking the final PAK passes format/metadata/paint checks and encoded color
phase checks on all six diffuse textures. V8 PAK/OBB and v9 NRO hashes remain
unchanged. These checks do not substitute for testing on Switch.

```powershell
python -m pip install -r tools/visual-patch-requirements.txt
python -m unittest discover -s tests -v
python tools/build_uniform_pitch_patch.py --style clean-v10 --output local-debug/rebuild-v10/pitch
repak pack --version V8A --compression Zlib local-debug/rebuild-v10/pitch/pitch-stage local-debug/rebuild-v10/PesMobile-Android_ETC1_P.pak
New-Item -ItemType Directory local-debug/rebuild-v10/verify
repak unpack local-debug/rebuild-v10/PesMobile-Android_ETC1_P.pak --output local-debug/rebuild-v10/verify/pitch-stage
python tools/build_uniform_pitch_patch.py --style clean-v10 --output local-debug/rebuild-v10/verify --verify-only
```

Use new output directories and locally owned source assets. Omitting `--style`
retains the historical v9 recipe for reproducibility. A recipe snapshot is in
the v10 folder. For copy paths and rollback see the
[v10 README](local-debug/visual-v10-20260831/README.md).
