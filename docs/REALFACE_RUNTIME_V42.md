# Real-face runtime isolation v42

The user confirms **v41-7k**, with disappearing Gerard Martín and a Manchester
United goalkeeper, plus pacing under native Stadium in DAY and NIGHT. This is
device feedback, not a captured v42 performance profile. Keep the accepted
face detail: **do not restore the old global 2,000-triangle policy**. The pilot
remains Barcelona and Manchester United. No new face PAK is produced here.

## Verified offline evidence

Gerard Martín is BaseId **138183**, native storage key **34493**, with 5,620
complete-head triangles and 3,763 cooked vertices. Senne Lammens is
BaseId/native **134931**, 5,980 triangles and 4,785 vertices. Neither requires
one of v41's >6,000 exceptions. Karl Darlow and Tom Heaton are also included in
the targeted goalkeeper audit; the report does not assume which keeper was
selected on the device.

All 605 staged v41 assets still match their release hashes. The four targeted
heads have no missing dependency declarations, transparent face mips or fully
discarded hair mips. This is packaged-byte evidence, not observed texture
binding on the device.

The existing cooked rig/UV/weight proof and the new native-reference-pose
audit have finite, nonempty face/hair geometry for these four players. For
Gerard the posed face Z range is 138.53–182.47 cm; Lammens is 139.36–182.99 cm.
Raw cooked bind-space bounds can look misplaced because the import compensates
different rest rigs. Do not delete apparently distant vertices without first
applying the weighted native/cooked bind transform.

`tools/audit_realface_pose_bounds.py` reads existing verification profiles and
glTF exports without starting Blender or UE. It hashes inputs and reports
counts, influences and posed bounds, retaining no vertex payload in the report.
This does **not** establish runtime animation, material binding or visibility.

The matching Mobile ELF was inspected locally with bounded Capstone/ELF
queries. REA's deep providers remain unavailable; no new REA decompilation
evidence is claimed. The native child mesh uses fixed whole-player bounds;
native LOD setters clamp to available LODs as already established in the
earlier audit. No speculative culling/LOD/bone change is installed.

## Runtime changes

`experimental_features.h` suspends Stadium V2 and the entrance canary hooks.
The picker exposes six native cameras plus FootballNX. All three V2 motion
patches and its per-update begin/end adapter are disabled. Native Stadium and
the shared native camera update remain available.

Disabling the entrance trace alone cannot remove its assets. The local package
therefore includes a hash-verified native `dt220` baseline. The installer
accepts only that baseline or an independently checked entrance-only canary.
It replaces the NRO, `dt220`, and **only the corresponding row of the installed
manifest**, preserving other manifest rows, physique data, other CPKs, PAKs,
OBB and saves. Unknown cinematic changes are rejected before writing. The
three replaced files and trace marker are backed up on D: for rollback. This
retires the FL26 entrance experiment; it does not bypass native match/demo
teardown or native FPS restoration.

## Bounded diagnostic build

The separate diagnostic NRO adds:

- A native `LoadRealFace` wrapper for High/Low/Lowest actor classes. Up to 128
  RAM-only snapshots record the requested native key, load duration, resolved
  face/hair mesh and available LOD count. Originals run exactly once. Records
  are written only outside live play. These snapshots distinguish a failed
  load from later disappearance; they are not proof that a loaded head stays
  visible or uses the correct material.
- Optional GPU timestamp pairs, sampled once per 30 rendered frames. Support
  is checked per context. Both availability flags must pass before reading
  results; a full queue skips samples. Disjoint clocks and context/session
  changes discard pending measurements. No GPU wait, readback, flush or shader
  replacement is added. Unsupported drivers report unavailable GPU samples.
- Existing CPU draw/upload counters and presentation timing by camera region.
  GPU stream spans include idle gaps between submitted commands, so they are
  **not a pure GPU busy counter**. Compare them with CPU submission/upload
  durations and the same scene without the face PAK before selecting a remedy.

Production omits the GPU and face-load probes. Face geometry/materials and
texture detail remain the v41-7k bytes supplied separately. There is no new
forced-low actor quality, FPS clamp or triangle reduction.

`analyze_match_pacing.py` now aggregates GPU samples by their own sample counts,
keeps missing GPU data unknown and lists unresolved face/hair loads separately.
Old CPU-only logs remain supported. Exact lineups, asset/NRO hashes and repeated
play must still match; a single number cannot establish a frame-rate sweet spot.

## Device acceptance still required

Use the same diagnostic NRO for two NIGHT cases: no extra face PAK and the
unchanged v41-7k PAK, Barca/MU, Konami, native STADIUM, identical lineup,
quality and resolution. Spend at least 20 seconds passing near the camera and
20 seconds at the far side, then Pause to write the summaries. Save each
`scene-runtime.log` before restarting. DAY can be compared afterward.

First resolve a failed native load if one is observed. If meshes load but
disappear later, inspect runtime visibility/material/streaming evidence. If
the render workload dominates, consider screen-size LOD that preserves the
current close-up mesh and hairstyle, or redundant hair-layer/index/vertex
work. If CPU uploads/submission dominate, fix that path first. None of these
conditional diagnoses is claimed proven by the current offline checks.

**Missing heads are not yet fixed and stable 60 FPS is not verified.** This
candidate supplies the suspended-feature baseline and the measurements needed
for a targeted performance fix without another blind quality reduction.

## Local artifacts and checks

Both devkitA64 builds succeeded and their NRO load segments match their ELF;
the FNX icon passed byte verification. Production omits GPU/load-probe strings
and both builds omit the suspended V2/entrance installer signatures. Focused
validation passed **56 tests and 2 subtests**. The public-tree audit passed
**1,082 files**. A real baseline install preflight completed without writes;
synthetic installer tests cover unrelated manifest rows, backup, tampering
and rejection of unrelated cinematic changes.

The ignored local package is
`local-debug/face-runtime-v42/FootballNX-FaceRuntime-v42-TEST.zip`, 112,990,160
bytes, SHA-256
`f14eb9fa822b40a00b5dc70c8cb2f951629c16b5df18a7ec09445fe02cc61f3c`.
Runtime pair remains `e861c583ec78e9ae`, dummy OBB 53,248 bytes. Production NRO
SHA-256 is `9db627e37e5926e49810d54ffe57fd0970cd0c197146945fa0e1a919988fd1a5`;
diagnostic is `d956acf3422c54b5393af5706a09dad5b3484afc23c5236ce5a46fd91a953e1c`.
No active prepared runtime, immutable face PAK, OBB or save was modified.
