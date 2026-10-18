# Native Stadium and Pitch Side camera candidate v33

The user asked to try FL26 Stadium/Pitch Side because the wrapper's Stadium
view still behaves poorly, and to avoid an additional ball-tracking layer.
The previous v32 near-camera pacing candidate has not been tested on Switch.
V33 is a camera candidate, not a confirmed frame-pacing fix.

Follow-up: [STADIUM-V2](STADIUM_V2_CAMERA.md) adds separately selected custom
tracking inside the native Stadium framing pipeline. Its scoped target/trace
hooks differ from the removed v32 implementation. The original Stadium/Pitch
Side behavior documented here remains selectable and passes through unchanged.

## Local FL26 audit

The installed FL26 Sider configuration enables `camera.lua` 3.1, which adjusts
Dynamic Wide/Fan View. It does not include an active `StadiumCam` or `CommonCam`
override. The native PC executable therefore provides the Stadium/Pitch Side
reference. The compatibility locators from
[nesa24/juce's camera modules](https://mapote.com/pes/nesa24-cameras-3.3.zip)
identify the corresponding native PC tables; the downloaded reference remains
local and is not incorporated into the wrapper.

The read-only audit found exact byte equality with the supported Mobile ELF:

| Native parameter family | Compared data | SHA-256 in both inputs |
| --- | --- | --- |
| Common / Pitch Side | 90 floats, 360 bytes | `43621fff867d25bd3b44239fcf6b47756b94dc87a06eef12d3160aa46efcf1c5` |
| Broadcast / Stadium | 110 floats, 440 bytes | `11c0eca6753180c08371778f60f49cc2584b55ae4a134202b202a1cff6148d25` |

Consequently the implementation exposes/restores the matching Mobile native
presets. It does not copy an x86 executable, inject Lua, or approximate PC camera
motion with another per-frame target calculation. Parameter equality does **not**
prove that every PC/Mobile gameplay branch, interpolation, or rendered frame is
identical. A full PC behavior transplant is not claimed.

Reproduce against legally supplied, ignored inputs:

```powershell
python tools/audit_fl26_cameras.py --pc-exe <owned-FL26.exe> --mobile-elf <owned-libUE4.so> --output local-debug/fl26-camera-v33/parameter-audit.json
```

The tool validates locators and native routing, refuses ambiguous signatures,
and emits input hashes, parameter hashes and counts. It never writes extracted
tables, game instructions or modifications to either input.

## Runtime changes

- Add **PITCH SIDE** to the existing camera picker, after Stadium. It uses tmpdb
  type 3, registry type 2 and live camera ID 1: the native horizontal/common
  pipeline, distinct from Stadium's live camera ID 6.
- Restore **STADIUM** to native conversion (distance 2, height 3, angle 6).
  Remove the wrapper's forced height 6. Pitch Side retains native 2/2/0.
  The original converter owns active, Normal and BL registry copies.
- Remove both installed `GetBallPositionBroadcast` patches, their AArch64
  trampolines, duplicate ball sampling, motion-readiness state and per-update
  scope clearing. Native ball/group selection, speed limits, interpolation and
  camera lifecycle now run without those corrections. This also restores native
  anticipation; its visual behavior still needs user acceptance.
- Retain the original default Dynamic Wide and the explicitly selected
  FootballNX custom composition. Other native choices pass through unchanged.
  Camera selection persists through pause and rematch within the app session.
- Replay, celebration, kickoff and set-piece cameras retain their own native
  owners. Gameplay helpers that use BallInfo are separate and remain intact.

This removes added camera work; it is not evidence that the removed work caused
the reported lower-middle slowdown. Native cameras still track the action.
The v32 upload-budget correction, v31 stadiums, roof/pitch shaders, and existing
gameplay features are unchanged. Production builds disable DEBUG_LOG,
PERF_TRACE and NEAR_CAMERA_TRACE. The regular scene journal identifies v33.

## Verification and device check

Host tests execute the actual compatible AArch64 preset converter for six
presets across seven resident modes, verify all three registry copies and mode
restoration, and check Pitch Side/Stadium's separate native dispatch paths.
Controller tests cover the seven-entry cycle, labels, pause restore and rematch.
Wrapper tests check byte-preserving native camera output and removal of the
additional sampling/branch hooks. These checks are not hardware visual tests.

The focused camera/settings, pause/result, render-budget, referee and lighting
regressions pass: **81 tests and 89 subtests**. Both local native-ABI tests also
pass through the standalone unittest runner. The production devkitA64 build
succeeds; existing unused-function warnings remain. Release verification checks
the NRO/ELF segments, accepted runtime identity and launcher icon, the seven
compiled camera presets, and absence of the removed camera-hook symbols.

The release contains one production `pes21_nx.nro` and installation/audit notes;
no PAK, CPK or OBB update is necessary. Keep the previous NRO for comparison.

1. Install the NRO; open Pause > Camera Settings > Camera Type > **PITCH SIDE**.
2. In Konami Stadium, compare far-side play with passes near the lower middle.
   Repeat on DAY and NIGHT with the same teams/quality.
3. Select **STADIUM** and compare kickoff, loose balls, aerial passes, receiving
   a pass, switching possession and both touchlines.
4. Check pause/resume, a rematch, replay/celebration, free kick and goal kick.

If pacing persists, do not infer the root cause from a camera change alone.
V32's separate diagnostic measures the previous camera implementation; its
results must not be described as measurements of V33 or the new Pitch Side
choice. See `NEAR_CAMERA_PACING_V32.md` for that earlier baseline procedure.
