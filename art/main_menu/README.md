# Main menu assets

Generated with the built-in image generation tool for the approved blue/yellow full-page main menu.

- `background-v1.png`: background only, without text, UI, logos or players.
- `androswitch-boot-splash-v3.png`: authored 1920x1080 replacement for the
  stock Konami intro; the plain-blue backdrop and centered AndroSwitch Project
  wordmark are baked into one frame.
- `androswitch-boot-splash-v3.png` is converted into the native normal/wide
  `titleCorporate` atlases by `tools/build_androswitch_corporate_splash.py`;
  it is not linked into the NRO.
- `icons-mask-v1.png`: monochrome source mask, 2x2 layout: Exhibition, 2 Player, Settings, Credits.
- `background-runtime.png` and `icons-runtime.png`: normalized assets embedded in the NRO. The runtime icon atlas converts mask luminance into transparency.
- `brand-logo-source.png`: approved two-line `Football` / `NX26` wordmark with its yellow NX accent.
- `brand-logo-runtime.png`: transparent, tightly cropped two-line branding embedded in the NRO; the asset builder removes the source preview's baked checkerboard, colors the X eFootball yellow, and changes the N/X accent to bright pink.
- `portrait-*-source.png`: the four supplied transparent player cutouts.
- `portrait-*.png`: normalized 768x1024 runtime portraits, bottom-aligned without changing the foreground artwork.

Background prompt: Preserve the approved cobalt/navy sports background, halftone corners, subtle pitch geometry and yellow edge accents; remove all players, logos, text and UI; keep the left side quiet for separately rendered controls.

Icon prompt: Four pristine flat white geometric pictograms on black, uniform 2x2 grid, soccer ball, two people, settings gear, credits document; no labels, texture, shading or glow.

Runtime mapping: Exhibition uses Yamal, 2 Player uses Mbappe, Settings uses Messi, and Credits uses Ronaldo. Labels use the existing eFootball stencil atlas. Portraits crossfade when focus changes. Alpha-noise-resistant cropping gives every subject the same vertical occupancy as the Ronaldo anchor, followed by one shared color/sharpness grade.

The title page reuses the same background and four portraits. It cycles the
large left portrait every 10 seconds with a 450 ms crossfade, places the
FootballNX26 wordmark in the center of the right-hand area above the Switch A
sprite plus `PRESS` / `TO START` above the `ANDROSWITCH PROJECT 2026` footer.

Both pages give portraits top padding. The tile menu uses a smaller logo.
`tools/build_startup_blue_backdrop.py` changes the native corporate fade
rectangle from red to the splash's blue (`#001C61`), preserving the timeline.

Visual order: Exhibition, 2 Player, Settings, Credits. Existing native action indices are 0, 2, 3, 1 respectively; the custom vertical navigation preserves that action mapping.

Regenerate all embedded payloads with `python tools/build_main_menu_assets.py`.
