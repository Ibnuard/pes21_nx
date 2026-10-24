# Serie A native field centering v77

This supersedes the vertical/horizontal positioning in the v76 Italy review.
The v76 plate height remains 40 pixels, at physical `(38,32)` in 1280x720.
Its timer, conditional added-time clip and complete event stack do not move.

The supplied Switch capture has a concrete geometry mismatch. The native MIL
ink spans physical `(55,45)..(91,63)`, INT `(284,45)..(320,63)`, and the zero
digits `(169,44)..(181,65)` / `(216,44)..(228,65)`. Their ink centers are about
2 to 2.5 pixels below the plate center at y=52. The former home name transform
also placed a 40-pixel native field near the left of the blue region, while
the nominal away centering region included its kit strip.

The native name fields now center in separate timeline blue cells
`(6,20)..(100,60)` and `(232,20)..(326,60)`, excluding the kit strips. Relative
to the pinned v76 packet, every existing translated keyframe receives:

| Native instance | x change | y change |
| --- | ---: | ---: |
| Home name | +11 | -2 |
| Away name | +9 | -2 |
| Both scores | -2 | -2.5 |
| Both kit roots | 0 | -2.65 |

The native palette retains both own-colour children. Their decoded atlas
tiles are 5x16 pixels; the shared clip places them at y=-1.35 and y=14.65.
The new root y=25.35 gives a complete y=24..56 stack, centered in the y=20..60
plate with four-pixel margins. The builder verifies this child geometry,
including the away instance's horizontal mirror.

The owned source crop also contains a baked score separator below the plate
center. Its complete anti-aliased raster is moved up four pixels inside the
same white region; its pixels and colour are retained. Integer raster
placement leaves a half-pixel center difference. Native score transforms move
left two pixels to balance the two zeroes around that separator.

Native source IDs, scale, fonts, bindings, scripts, strings, labels, colour
and alpha updates, frame counts and reveal/exit displacement curves remain
identical to v76. The only score-movie differences are the six instances'
translation fields. Other movies remain identical; the atlas differs only
at the old and new separator location. Other league packets are unchanged.

Focused tests use the actual pinned local v76 packet to enforce that boundary,
all placement updates, separate cells, palette centering, bytecode protection
and packet admission. The diagnostic uses glyph masks from the supplied
device capture to illustrate those measured translations. It is not a native
renderer, new playback evidence, or proof that every team's ink is optically
identical; initials vary with the unchanged native font. The ordinary host
preview continues to use explicitly labelled stand-in text. Switch acceptance
of this correction remains pending.
