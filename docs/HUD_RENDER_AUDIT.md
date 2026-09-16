# HUD render candidate — 2026-09-16

Status: **failed hardware experiment, removed from current source**. This file
records why it must not be repeated. No OBB/CPK or roster changes were involved.

## Stamina

The current source no longer contains the old height/scale experiments. Native
`ModelStaminaGauge` supplies active fills in slots 0/1, plus full-power dark
tracks in slots 2/3 (`GetColor`: RGB 17/17/17). Native `Primitive::DrawBuff`
also submits each stamina model as two separate triangle items: a textured
plate and a vertex-colored fill using `GWhiteTexture`.

This establishes multiple overlapping draws; it does **not** prove from static
analysis whether the hardware symptom is batch ordering, sampling, or clipping.
The failed candidate attempted to remove those ambiguities locally:

- It suppressed the duplicate dark-track slots after its hook installed.
- It deferred the plate submission and replaced the stamina fill with one
  white-texture triangle item containing a dark track followed by the fill.
- It obtained bounds, remaining-power width and fill color from the native
  items in that same call. No saved world positions or delayed overlay snapshot.
- It preserved the outer rectangle and targeted an 80%-height fill.
  a 10% inset at each edge; no fixed 720p coordinates or height multiplier.
- It used centered white-texture UVs and an ordinary canvas batch.
  custom texture sampler/stencil parameters. Other UI batches are untouched.
- It used stack-only scratch geometry without readback or heap allocation.
  per-frame logging, synchronization, or new heap allocation in the wrapper.
  On hardware, however, stamina disappeared completely. The ABI guards were
  insufficient evidence that the reconstructed item state was valid.

Frozen libUE4 ABI:

- `FCanvasUVTri`: 0x60 bytes, three XY/UV/RGBA float vertices.
- `FCanvasTriangleItem`: texture at +0x38, parameters at +0x48, triangle array
  at +0x50. Its native Draw method copies vertices into `FBatchedElements`.
- `Primitive::DrawBuff` (0x03f0d064) +0x2c0c: defer plate `DrawItem`.
- +0x30d8: guarded four-instruction trampoline, resume +0x30e8. The first
  item's copied vertex array remains alive at this point.
- Shared `UCanvas::DrawItem` entry and PLT are **not** hooked.
- Unknown instruction layout leaves the original stamina renderer enabled.

## Camera

The checked-in camera correction is an 80% planar ball-target bias, not the
older ten-unit threshold. Further along, `gcViewTraceBroadcast` quantizes X/Z
through `FCVTZS`/`SCVTF` pairs at +0x84/+0x88 and +0xa4/+0xa8. Its grid cell
depends on the native trace parameters and current scale. Crossing a cell can
therefore make a continuous target jump before interpolation.

The failed candidate bypassed both snaps. Hardware testing made frame glitching
worse and visible across every camera mode. Therefore this shared trace routine
cannot be treated as broadcast-exclusive despite its symbol name. The patch was
removed; it must not be revived without a verified runtime camera-owner gate.

## Small eFootball text

Switching the existing 48px atlas to trilinear mipmaps produced no visible
improvement on hardware and was reverted. The next attempt must change the
source rasterization/atlas strategy, not only the texture filter.

## Hardware result

1. Stamina: not drawn at all.
2. Camera/HUD: worse frame glitching across all camera modes.
3. Small eFootball text: still visibly rough.

## Follow-up candidate

The next candidate avoids all three failed mechanisms:

- Stamina keeps the native four models and native canvas path. Three guarded
  instruction changes swap slot semantics so full dark tracks draw first in
  slots 0/1 and live colored power draws afterward in slots 2/3. There is no
  draw hook, reconstructed canvas item, scale or height override.
- Camera correction remains inside the single-caller Broadcast ball-position
  calculator. A ten-unit deadzone blocks physics micro-motion, with a smooth
  eight-unit ramp to a capped 35% correction. The shared trace routine is not
  modified.
- Small eFootball text uses dedicated 20x24 hinted glyphs stored in separate
  atlas rows, selected at 21 screen pixels and below. Large glyph rows and
  texture filtering remain unchanged.

## Lesson from local verification

- Failed build: `local-debug/hud-render-v1/install/pes21_nx.nro`.
- SHA-256: `2fee72bd5487ebf71b4d0162a3d7a804438a9a3c01271be59a98e2a6348a44b6`.
- All 13 guarded instruction words matched the supplied ARM64 `libUE4.so`.
- Linked trampoline disassembly checked against the native stack offsets,
  replayed instructions and resume address.
- 83 source/host regressions passed, yet hardware behavior failed in all three
  target areas. These tests were structural and cannot be treated as visual or
  frame-pacing validation.
