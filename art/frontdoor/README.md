# Flat Matchday assets

Direction: a white-to-ice-blue gradient, restrained pitch-line and dot patterns,
blue/red accents, a compact icon/title menu rail on the left and an unframed
existing player hero on the right. Main-menu descriptions are intentionally absent.
The active row expands with a 260ms focus transition; the neighbouring rows
shrink while the overall rail height stays fixed.
The active blue pattern uses a bounded six-second UV drift loop; it needs no
additional generated frames or video asset.
The reference informs the graphic hierarchy, not a copied interface. No stadium
photography, rendered architecture or reused Master League fabric cards.

Generated using the built-in image-generation tool on 2026-10-08. Full final
prompts, dimensions and runtime filenames are in `prompts-v2.json` and
`prompts-v3.json` (the clean background edit).

- `flat-white-v2.png`: full-screen background; quiet centre for readable content.
- `flat-white-v3.png`: current clean white/pale-blue base, without baked saturated
  corner stripes. Four independent flat vector ribbons move with the portrait
  transition and drift over six seconds; portraits slide horizontally in/out.
- `flat-panels-v2.png`: four horizontal strips (blue, red, navy, focus), each
  1536 x 256. `fd_art` samples within each strip with a 2px gutter and an
  aspect-preserving crop. Rounding and focus rings are applied by the renderer.

The `data/frontdoor_*.bin` files are byte-identical PNGs, embedded by the normal
build. Existing wordmark, portraits, controller glyphs and Master League header
icons are reused unchanged. The wordmark uses source alpha with navy ink.

The rejected realistic-stadium draft is not packaged. Regenerate synthetic
screens with `python tools/preview_frontdoor.py`; see `docs/FRONTDOOR_UI.md`.
