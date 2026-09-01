# Visual revision 14 - stable symmetric pitch

The pitch was accepted on Switch and is now the latest stable baseline. The
installable package is in `local-debug/visual-v14-stable-20260901/install/` and
combines the accepted v14 PAK with the last stable v9/v1.98 runtime NRO.

V14 keeps the accepted broad v10 cadence from midfield to the penalty-box
front. A single local band per goal is re-anchored to the keeper-box line, so
the left boundaries are `331, 494, 671, 848, 1024`; the right side is its exact
mirror. The corrected `331..494` and `530..693` bands are 163 texture pixels;
all other complete bands remain 176/177 pixels. Dark and light bands are not
given different global widths.

The combined Low/Standard texture is generated directly from those same left
and right phases at half density. Its samples adjacent to midfield are
light-left/dark-right, eliminating the thin extra phase seen in the rejected
unequal-width experiment.

The accompanying experimental Native Pad Lab NRO was rejected on hardware.
It reached a one-player match, but Joy-Con input did not control the player and
the accepted Player Cursor/helper presentation regressed. It remains archived
under `local-debug/visual-v14-native-pad-lab-20260901/` only for diagnosis and
must not be distributed as the stable runtime.

See the [stable README](local-debug/visual-v14-stable-20260901/README.md) for
the exact two files, destinations, hashes, and runtime split.
