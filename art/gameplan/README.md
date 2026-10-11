# Game Plan sprite atlas

`icons-v1.png` is project-generated artwork made with the built-in ImageGen
tool. The style reference was the existing project artwork
`art/master-league/header-icons-v8.png`. No game texture was used as a source.
`icons-v1.json` records the inspected pixel bounds of each sprite, rather than
assuming the generator produced perfectly equal cells.

The runtime copy, `data/gameplan_icons_v1.bin`, is the same PNG byte-for-byte.
The overlay uploads it once per graphics context. Left and right boots are
separate sprites; the player's nondominant boot is drawn at 20% opacity.
Player portraits are loaded separately from the user's local runtime and are
not part of this public atlas.

## Generation prompt

Create one production game UI sprite atlas, square 4 by 4 grid, exactly 16
separate centered icons. Use the attached image ONLY as art-style reference:
crisp chunky navy outlines, pearl white fills, bright cyan accents, subtle
blue shading, professional football game menu aesthetic. Create different
new symbols specified below. No background, genuinely transparent RGBA.
Equal cells, each icon wholly within central 72% of its cell with wide empty
gutters; nothing touches or crosses a cell. No labels or numbers or text
except a single capital C on captain armband. Reading order left to right,
top to bottom: row 1 = captain armband with C; right corner flag over L-shaped
pitch corner; left corner flag with mirrored L-shaped pitch corner; football
boot striking a football for free kick. Row 2 = football on penalty spot in
front of small goal; attacking forward arrow behind football; defensive
shield with football; offside flag held upright. Row 3 = substitution two
opposing arrows; save lineup clipboard with down arrow; load lineup open
folder with up arrow; tactics miniature pitch with three player dots and
arrows. Row 4 = left boot viewed from above, left toe clearly curved inward;
right boot viewed from above mirror of previous; bold confirmation tick in
circle; neutral bust silhouette used only when player portrait is unavailable.
Make the pair of boots visibly a left and a right pair, no lettering on boots.
This is one reusable atlas asset with exactly sixteen symbols, not a
screenshot or UI mockup. All contours clean and readable at 32px. Transparent
outside icons. Same navy/white/cyan art direction as reference, no yellow,
purple, red, logos or ornamental motifs.
