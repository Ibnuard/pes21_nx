# Referee performance candidate v15

On 11 October 2026 the user reported smooth play after removing the referee
probe, and uneven frames with it enabled. This narrows the regression to the
optional referee path; it does not yet distinguish its CPU updates, native queue
publication, model rendering, or contention. Weather v14 is left unchanged.

## Bounded optimizations

- Sample the 22 avoidance-neighbour positions at 15 Hz instead of once per
  native write frame. Cache scalar positions only; no registry pointers survive
  a callback. Reset the cache on pause, replay, unavailable registry and stadium
  teardown. Ball tracking, movement, animation and bone/transform publication
  retain their native frame cadence. At 60 Hz the neighbour reads fall from
  1,320 to approximately 330 per second. Avoidance positions can be up to about
  67 ms old; this is a visual follower, not native player collision or rules.
- Reject distant avoidance neighbours using squared distance before taking a
  square root. Keep close-obstacle separation, bounds and movement limits.
- Calculate the substep tracking coefficient once per movement update rather
  than repeating the same exponential for every substep.

The existing duplicate-frame guard and edge-triggered visibility remain. No
extra model loads, pose throttling, renderer queue bypass, LOD guess, texture
mutation or global GL observer is introduced.

## Measurement

Accumulate elapsed CPU time separately for follow, pose evaluation/copy, native
bone publication, and native transform/visibility publication. The v15
`referee perf` summary is written only on suspension/teardown, never every live
frame. It records average microseconds per stage, worst total sampled callback
time and player reads. Timing excludes the original native object-list draw,
GPU execution and asynchronous work after publication. It cannot rule out GPU
or native queue contention if the measured CPU work is small.

Existing frame-pacing summaries now carry the v15 header. Compare identical
stadium, weather, teams, camera and console mode with/without the probe. Play
20–30 seconds with fast passes then pause and save each log before relaunch.
With the probe enabled, verify gestures, close-player avoidance, pause/replay
resume and repeated matches. No new assets or probe token are required.

## Verification

The focused host suite passed 12 tests and 23 subtests: synthetic independent
animation clocks/gestures, installer guards, scene lifecycle and native-state
preservation. A 300-frame 30 Hz scenario retains all 300 publications while
halving neighbour reads. A 120-frame 60 Hz scenario retains all 120 bone and
transform publications while reducing neighbour reads to 30 snapshots. Duplicate
callbacks do not advance animation or republish. Suspension invalidates the
snapshot and flushes timing. This is a candidate optimization with instrumentation,
not a confirmed 60 FPS fix. Console performance acceptance remains pending.
