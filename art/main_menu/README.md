# Main menu assets

Generated with the built-in image generation tool for the approved blue/yellow full-page main menu.

- `background-v1.png`: background only, without text, UI, logos or players.
- `icons-mask-v1.png`: monochrome source mask, 2x2 layout: Exhibition, 2 Player, Settings, Credits.
- `background-runtime.png` and `icons-runtime.png`: normalized assets embedded in the NRO. The runtime icon atlas converts mask luminance into transparency.
- `brand-logo-source.png`: eFootball/PES2021 branding isolated from the original PES21 title renderer, not generated typography.
- `brand-logo-runtime.png`: tightly cropped transparent branding embedded in the NRO.
- `portrait-*-source.png`: the four supplied transparent player cutouts.
- `portrait-*.png`: normalized 768x1024 runtime portraits, bottom-aligned without changing the foreground artwork.

Background prompt: Preserve the approved cobalt/navy sports background, halftone corners, subtle pitch geometry and yellow edge accents; remove all players, logos, text and UI; keep the left side quiet for separately rendered controls.

Icon prompt: Four pristine flat white geometric pictograms on black, uniform 2x2 grid, soccer ball, two people, settings gear, credits document; no labels, texture, shading or glow.

Runtime mapping: Exhibition uses Yamal, 2 Player uses Mbappe, Settings uses Messi, and Credits uses Ronaldo. Labels use the existing eFootball stencil atlas. Portraits crossfade when focus changes. Alpha-noise-resistant cropping gives every subject the same vertical occupancy as the Ronaldo anchor, followed by one shared color/sharpness grade.

Visual order: Exhibition, 2 Player, Settings, Credits. Existing native action indices are 0, 2, 3, 1 respectively; the custom vertical navigation preserves that action mapping.

Regenerate all embedded payloads with `python tools/build_main_menu_assets.py`.
