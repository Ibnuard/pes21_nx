# Cup Skip helper style, v89

The reported v88 test shows a silver cup and the custom Skip control. Its
separate cinematic renderer used regular text and a different horizontal
anchor, so it did not match the existing set-play helper reference.

Cup Skip now supplies one row to the production set-play helper renderer. It
uses the same button textures, 0.045-height sprite size, measured right anchor,
bold font, white foreground and two-pixel shadow pass. Distinct local controller
profiles show two alternative glyphs beside one SKIP label, without a chord
plus sign. Full pads retain B, horizontal left Joy-Con retains LEFT, and
horizontal right retains A. Two matching profiles share one glyph.

The row remains available only during checked ceremony playback. Loading and
modal transitions show no Skip helper. The ordinary GoalDemo renderer, native
footer hold, neutral-release input gate and result ownership remain unchanged.

Host fixtures execute the actual set-play row and shadow rendering blocks,
compare the single-glyph Cup layout with a reference row, and cover all local
profile pairs. This proves the shared style path and controller legends; the
new appearance still requires a Switch test.
