# Near-camera pacing candidate v32

The user reports the same lower-middle/near-camera slowdown in DAY and NIGHT,
including **Konami Stadium**, and with `referee-probe.txt` removed. The latest
locally supplied device journal is still v26; it cannot establish the v31
bottleneck. Imported stadium geometry and roof shading are therefore not
sufficient explanations. No claim of a complete hardware fix is made here.

## Corrected upload submission budget

`gl_load_drain` submitted after every 512 buffer/texture allocations using a
thread-lifetime counter. It was intended to bound large unswapped world loads,
but continued to trigger during matches after successful presentations. The
counter now resets after a successful swap of that context's current surface.
It remains separate for each context, preserves the loading threshold, and
does not reset on failure or another context's presentation.

This removes avoidable mid-frame submissions. `glFlush` submits work; it does
not establish a GPU completion wait. The change is consistent with the
[EGL specification's implicit flush on presentation](https://registry.khronos.org/EGL/specs/eglspec.1.5.pdf).
Its contribution to the reported device slowdown remains unmeasured.

The host reproduction submits 120 uploads per presented frame for 600 frames:
the previous counter triggers 140 additional flushes; the corrected counter
triggers none. A separate unswapped run still submits four times in 2,048
uploads. This is a policy test, **not a Switch performance benchmark**.

## Lean diagnostic variant

The default `update` NRO has tracing disabled. The optional `diagnostic` NRO
uses `NEAR_CAMERA_TRACE=1`, independently of `DIAGNOSTICS` and `PERF_TRACE`,
both disabled in both variants. The trace stores
bounded counters in thread-local RAM and reports only after leaving live play
(pause, replay, or menu). It requires no referee marker.

The existing camera callback publishes a scalar snapshot. Rendering is grouped
into far/centre/near and left/middle/right zones using the **camera target**,
not an assumed ball pointer. A stale or invalid camera is `unknown`; a mirrored
camera reverses the depth classification. The snapshot is captured before swap
so the next simulation update cannot relabel the frame during the swap wait.
Transitions between zones, settings, sessions, and failed swaps are excluded.

Each `near-camera:` journal row includes:

- Presentation interval, worst interval, and counts above 20/30 ms.
- Swap/overlay CPU duration and first-draw-to-swap span.
- Driver draw-call duration and submitted indices/vertices (including instances).
- Buffer upload/map/unmap call duration, buffer bytes and forced loading flushes.
- Session, stadium, time, weather, season, quality, camera and final viewport.
  Home/away IDs describe the Exhibition selector; they are not authoritative
  competition team identities.

These are CPU timings and submitted-element counts, not GPU time, unique
triangles, or shader-category timings. Map counts include map and unmap calls;
buffer byte counts do not include texture uploads. No shader dumps, GPU
readbacks, `glFinish`, synchronous query polling, filesystem writes, allocations,
or locks are introduced per draw. Existing static and resolved draw routes keep
their original rendering behavior. The trace still has small CPU timing overhead.

## Device check

Install `update/pes21_nx.nro` over the installed v31 runtime. Stadium PAKs,
realface PAKs, player physique data, lighting and camera composition are unchanged.
Test this variant first; it has no new per-draw timing instrumentation. If the
slowdown remains, replace it with `diagnostic/pes21_nx.nro` from the same package.
Use the same teams and camera in Konami: pass for about 15 seconds on the far
side, then the lower middle, then pause. Repeat in NIGHT and DAY. Copy the new
`scene-runtime.log` before restarting; it must start with `FootballNX scene v32`.
The diagnostic trace starts automatically and writes its summary at the break.
The default variant retains only the previous whole-play presentation summary.

If the slowdown remains, the per-zone rows will establish whether submitted
work, driver/upload stalls, or presentation latency changes with the camera.
Stable counts alone cannot rule out GPU fill cost or game-thread work.
The prior v31 NRO remains the rollback; device acceptance is still required.

## Verification

Focused host checks cover loading/live-frame budgets, context isolation,
failed swaps, context reuse, table exhaustion, mirrored and stale cameras,
quiet live recording, state/zone transitions, exact resolved driver arguments,
and a trace-disabled translation unit. The package records actual test and
NRO/ELF/icon verification results with `hardware_tested: false`.
