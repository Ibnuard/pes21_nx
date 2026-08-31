# Visual revision 14 - symmetric goal-area correction + 1P native pad lab

Candidate files are in
`local-debug/visual-v14-native-pad-lab-20260901/install/`. Stable rollback is
still the v10 pitch PAK and v9 runtime NRO.

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

The accompanying NRO turns the old 2P tile into an isolated one-controller
native-input proof. It immediately seeds Barcelona vs PSG, with PSG controlled
by CPU. It does not poll controller 2 or assign a second human. Native Cobra
input is emitted only during live offense/defense and only into pad ID 0;
ordinary Exhibition retains the existing synthetic-touch implementation.

See the [candidate README](local-debug/visual-v14-native-pad-lab-20260901/README.md)
for copy order, hashes, expected behavior and rollback.
