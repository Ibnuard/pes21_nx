# Two-player corner helper styling

Device feedback on v80 showed both closed tactics entries using the frontend
text renderer: smaller navy text and smaller sprites than the existing match
helpers. V81 emits these entries through the existing set-play helper path.
They share the same bold font, rounded screen-height text size, white colour,
two-pixel shadow, 4.5%-height sprites and 1.7%-height text gap. The right entry
shares the icon and label columns with the taker, trajectory and camera rows;
the left entry uses the same spacing. Both use one bottom baseline, and the
attacking stack sits exactly one normal helper-row step above it.

Each entry is independently hidden when that owner's tactics panel opens.
Both open panels leave no closed helper entries. The compact panels, input
mapping, restart ownership and per-pad hold/release behaviour are unchanged.
The obsolete frontend entry emitter is removed; panel footer styling remains.

Host previews execute the actual production helper geometry and GL draw
passes for both attacking sides, full and horizontal controllers, either
panel open and both panels open. They are synthetic host evidence, not a
Switch capture. Existing corner/HID and restart helper checks remain relevant.

The candidate inherits the full v80 file set and replaces only the NRO.
All thirteen other runtime files, including the repaired Old Trafford PAK,
1,638 face payloads and 436 skin-selector corrections, remain byte-identical.
