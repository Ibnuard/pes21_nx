# Camera motion and measured face budgets

The current device report has two distinct outcomes: Stadium-V2 continuously
chases the ball and feels uncomfortable; the v40 face package has visible
runtime regressions despite offline checks. The user no longer requires an
arbitrary 2,000-triangle ceiling. Future head budgets must be chosen from
controlled device measurements and appearance, preserving the face and hair
shape rather than accepting damage to reach a number.

## Evidence available

The supplied `scene-runtime.log` records Konami, DAY/FINE, season 0, 1024x576.
Across its two presentation windows (4,950 intervals), the weighted mean is
17.743 ms, approximately 56.36 presentations/s, and 9.01% exceed 20 ms. The
log lacks per-region draw/upload timings and exact camera/lineup/package
identity. It establishes pacing variation in that run; it cannot attribute
the cost to faces, stadiums, shadows, the referee or camera code.

The supplied `cinematic-trace.log` records entrance selection and Start entry/
return for scene 65537. There is no End callback record or asset/actor playback
observation. Returning from Start is not successful entrance playback. The
parallel entrance implementation is preserved; this camera update does not
claim to repair or validate it.

## Camera implementation

`source/stadium_v2_camera.h` now holds the shot inside a screen-space margin,
reframes smoothly towards an off-centre composition, and eases native zoom.
See [Stadium V2](STADIUM_V2_CAMERA.md) for policy and native hook scope. This
targets perceived camera jerk. A smoother shot is not proof of higher FPS.

The ordinary production NRO has per-draw tracing disabled. The diagnostic
variant adds the existing `NEAR_CAMERA_TRACE` counters, independently of full
debug/performance tracing. `build-wsl.ps1 -NearCameraTrace` now propagates that
option into the build and reproducible build identity. It restores the caller's
environment when complete. Both variants use the same source and runtime pair.
Temporary build storage uses the configured Ubuntu instance on D:, and the
PowerShell cache environment comes from `D:/PESNX-Cache/use-cache.ps1`.

The diagnostic collects fixed-size interval histograms in memory, then writes
on leaving play. `p50_upper_us`, `p95_upper_us` and `p99_upper_us` are histogram
bucket upper bounds, not exact percentiles. Draw/upload counters are CPU call
durations and submitted elements, not GPU elapsed time or unique triangles.
There are no new per-draw file writes, allocations, readbacks or GPU waits.
Diagnostic camera ID 134 identifies Stadium-V2; native Stadium remains ID 6.
Zone describes camera target, which may intentionally be away from the ball.

## Controlled sequence

1. Keep the same diagnostic NRO, teams, starting XI, quality, resolution,
   stadium, season, weather, camera and repeatable play sequence. Start with
   Konami at NIGHT, then repeat DAY separately. Record active PAK filenames.
2. Measure no additional face PAK, then v40 for diagnosis. Pass on the far
   side, at midfield and near the camera for at least 15 seconds each; pause
   to flush the report. Preserve each log before restarting. Repeat runs.
3. Check the ordinary NRO too: diagnostic CPU timing overhead must not be
   mistaken for production cost. Keep camera motion comparison separate from
   the face-package A/B comparison.
4. After the missing-texture/model regression is resolved, compare a small
   common roster at several face/hair allocations. Example test points are
   3,000, 4,500 and 6,000 complete-head triangles, plus an unchanged dense
   reference. These are experiment points, not a selected budget. Keep shader,
   sections, textures, alpha policy, rig and identity constant where possible;
   explicitly record any unavoidable differences.
5. Prefer the lowest measured workload that preserves eyes, mouth, neck and
   hairstyle. Measure hair layers/alpha coverage, sections, influences, texture
   residency, draw/upload stalls and frame-time tails alongside triangles.
   If the no-patch baseline is slow, investigate that workload before reducing
   the faces again. No new global quality reduction is justified by this log.

## Reusable log analysis

```powershell
. D:\PESNX-Cache\use-cache.ps1
python tools/analyze_match_pacing.py --case native=<baseline.log> --case face=<face.log> --output local-debug/<experiment>/comparison.json
```

The analyser hashes its inputs, avoids double counting overlapping whole-play
and per-zone reports, keeps settings/cameras/zones apart, and calculates weighted
intervals and threshold rates. Missing metrics stay unknown. Percentiles are
never averaged: combined summaries report the largest window bound. Matching
contexts with at least 600 frames are flagged for comparison; exact lineup,
NRO/PAK identity and repeated play must still be established separately. The
tool cannot select a polygon budget from a single uncontrolled log.

No new face PAK is approved by this camera/performance work. Keep immutable
v40 evidence for comparison; a new asset candidate needs independent runtime
appearance and timing checks before replacing the league-wide package.

## Built camera artifacts

Both devkitA64 builds completed. Their NRO load segments match their ELF,
the expected camera-hook symbols and runtime-pair string are present, and the
production build omits the diagnostic accumulator. Runtime pair is
`e861c583ec78e9ae`, with the existing 53,248-byte dummy patch OBB requirement.
The active prepared runtime was not replaced.

- Production NRO: 83,858,335 bytes, SHA-256
  `fbaa1f6451e35d01c5146c6348d0c33a8b1017b6fc9e497b8952ad8845f7a3fe`.
- Diagnostic NRO: 83,862,431 bytes, SHA-256
  `037c87ab75ed195180ab59a1fc1f1bc029322faace79ae885e98b988de4286ef`.
- Local ZIP: `local-debug/stadium-v2-frame-hold-v41/FootballNX-StadiumV2-FrameHold-v41.zip`,
  SHA-256 `8d67deaef80d4514f0defb0a649c54316bb65d29955b2b385b175e5c93c54c4a`.

The package includes separate ordinary and diagnostic NROs, installation
instructions and verification. It contains no face payload. Camera comfort,
GPU cost and entrance playback remain unverified on the device.
