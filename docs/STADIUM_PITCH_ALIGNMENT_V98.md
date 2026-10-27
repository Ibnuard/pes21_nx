# Signal Iduna and Camp Nou paint alignment v98

Signal Iduna's previous twelve equal-width stripes met the nominal goal and
halfway lines but crossed the retained native goal-area front. Its imported
shell keeps the same native pitch mesh and diffuse paint as the other venues.
The v96 barycentric UV audit therefore supplies the relevant native fronts:
penalty area 36.220 m, goal area 47.257 m and goal line 52.552 m from midfield.
The regulation dimensions differ enough to produce a visible edge mismatch.

Signal Iduna now has eighteen stripes, with nine per half. Six central stripes
are 6.037 m wide, two box stripes are 5.519 m and the outer stripe is 5.295 m.
Every front above is a mowing edge contained in both halves' white paint.
The widest-to-narrowest ratio is below 1.141; there is no cropped thin strip at
the goal line. The cadence continues beyond that line. The two midfield sides
have opposite shades. Old Trafford keeps its twenty-stripe arrangement;
Stamford Bridge keeps twenty-two.

Camp Nou now has a small 3.004 m central disc. Its second mowing edge is at
9.012 m, meeting the actual native painted center circle; the later edges
continue at 6.008 m intervals. The retained paint's measured circle center is
only 1.443 cm along X and 0.962 cm along Y from the kickoff origin. Using this
center avoids shifting the mowing edge to one side of the native white line.
The grass remains circular, without a camera-dependent transform.

This radius comes from read-only barycentric interpolation of the retained
`st029_pitch_2` mesh and the accepted L/R diffuse paint. A fit to 1,404 white
texel centers gives 9.01214 m. Sampling the authored edge at every degree puts
all 360 points on retained native white paint. A 9.15 m regulation-radius
comparison hits only the two halfway-line intersections. These are local
fixture measurements, not observations of a Switch frame. Native payloads and
the detailed input hashes remain ignored in
`local-debug/manager-review-v98/pitch/native-circle-audit.json`.

The change is confined to profile IDs 8 and 13 in the existing shader helper.
There are no new samples, uniforms, textures, geometry or draw passes. Camp
Nou keeps the existing single distance operation. White paint, native fine
detail, alpha, lighting, weather and the shared grass/wear remain untouched.

## Verification

The thirteen focused mowing tests pass, including both halves' retained paint
bounds, the actual profile branches, near-uniform complete Signal stripes,
Camp Nou's first/second/following edges, every-degree native circle mapping,
paint preservation, minification and all 58 accepted native shader rewrite
routes. The supporting math/weather/lighting checks pass fifteen tests and
250 subtests. An independent 3,266-point comparison per profile against the
checkpoint keeps IDs 0, 1, 2, 9 and 12 byte-identical in host math output.

Public-data-only previews execute the emitted shader math:

```powershell
python tools/preview_pitch_mowing.py --stadium 8 --output local-debug/manager-review-v98/pitch/signal-iduna.png
python tools/preview_pitch_mowing.py --stadium 13 --output local-debug/manager-review-v98/pitch/camp-nou.png
```

These diagnostic top views omit actual native lighting and fine detail.
They are not device screenshots. Day/Night, both goals, distant and replay
cameras, and frame pacing still need Switch acceptance. The separate missing
Signal Iduna stand/apron report is outside this mowing-only change.
