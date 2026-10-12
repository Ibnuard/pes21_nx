# Selected stadiums and near-camera rendering, v27

## Scope and device evidence

The selectable additions are Etihad Stadium, San Siro, Santiago Bernabeu,
Signal Iduna Park, Stamford Bridge and Old Trafford. Konami and the previously
accepted Anfield remain. Historical IDs 3, 4, 5, 10 and 11 are retained as
tombstones but are not offered, even if their old PAKs remain installed.
Old Trafford uses ID 12; its owned FL26 source is st007 inside dt30_g4.cpk.

The supplied v26 device log has slower presentation intervals in DAY and
NIGHT. For example, the short Ramon NIGHT sample averages 19,789 microseconds
at 1024x576, with 49 of 150 intervals above 20 ms. San Siro DAY samples average
19,517 and 18,674 microseconds. These intervals are neither GPU timings nor
simulation FPS and do not isolate one bottleneck. The near-touchline screenshots
also show that a roof-only explanation is insufficient.

## Rendering changes

- The native roof shader selects its roof height before projection and uses
  that single projection for derivatives and visibility. Previously imported
  stadiums and Anfield calculated a second projection. The rounded roof shapes,
  soft borders, weather response and player-height response are preserved.
- Imported static shells bake their existing hemisphere light into vertex
  colours. Their unlit materials no longer calculate that normal-based light
  per pixel. This affects stadium surfaces only; players and pitch retain
  runtime lighting and the roof's dark/light transitions.
- Source opaque/cutout and one/two-sided flags survive material merging.
  Opaque concrete no longer inherits a cutout mask merely because it shares a
  texture with glass or a fence. One-sided surfaces reject their back faces.
- Conservative camera culling moves fully hidden clusters to degenerate
  triangles in the ES3.1 vertex stage. A padded world box must fit completely
  inside the existing lens-clearance sphere. Partially visible triangles keep
  the exact existing pixel cutaway, including celebration clearance. ES2
  compiles out this optional vertex path because it supports fewer UV sets.
  It is enabled for Old Trafford, Signal Iduna and Stamford Bridge. Etihad,
  San Siro and Bernabeu omit its extra UVs and vertex work because the sampled
  benefit was small or absent; they still receive the lighting/surface fixes.
- Bounds occupy UV2–4, while an unused UV1 component separates clusters during
  UE's vertex weld. Actual cooked bounds must be constant within each triangle
  and enclose its vertices after half-float quantization. A failed shader
  connection or unsafe cooked bound fails packaging/verification.

The shell budget remains 35,000 triangles per stadium. An experiment splitting
long foreground triangles was rejected: it added too many vertices for its
measured reduction in sampled hidden fragments. Camera culling benefit varies
by venue and view. Offline intersection counts are not a GPU/FPS benchmark.
There are no additional dynamic lights, shadow maps, per-frame actor spawns,
viewport reductions or CPU crowd animation.

## Surface repairs

Fox triangle winding is converted to the destination convention before
enabling one-sided materials. The previous two-sided material had concealed
the mismatch. Pitch clearance now clips crossing low triangles and retains
their outside apron pieces, instead of dropping the entire source triangle.
Source UVs/normals are interpolated at each cut.

Etihad's two missing common camera/TV-prop textures are resolved by exact name
from the owned FL26 common texture library. Signal Iduna Park still lacks the
source's st051_sgbd009 sign texture in the locally available inputs; its small
sign surface uses the explicit neutral fallback. This is not a claim that an
unknown screenshot's venue has been identified.

Old Trafford has an asymmetric roof opening. Its separately measured inner and
outer centres use previously unused uniform components; the fit overlaps the
sampled opening/outer footprint by 89.04%/95.69%. Other accepted roof profiles
remain unchanged. Its audience uses the same native 16-frame sheet at 8 fps.

## Reproduction and verification

Use `data/stadiums/fl26_selected_v27.json` with the stadium preparation tools.
`extract_fl26_stadium.py` can read a single nested CPK member through a bounded
file window and extract only the requested stadium shell, audience and textures.
All proprietary inputs/intermediates remain local and ignored.

The batch cooker serializes the offline ETC1 cook by default. A parallel
UE4.22 cook stalled in the bundled Qonvert DLL's shared format registry;
serial execution avoids that initialization race without changing texture
format or quality. This build-machine issue is separate from Switch frame
pacing. Texture imports record their source SHA256 on the UE asset, so later
mesh/material rebuilds reuse unchanged textures and their compression cache.
For baked lighting, reimports also update the mesh's saved vertex-colour
import mode to Replace. UE can reuse that saved setting rather than the new
task's FbxImportUI; Ignore remaps old colours by position and loses distinct
corner values after a topology change. The cooked lighting audit rejects this.

Prepare the source surface policies with `convert_fl26_stadium.py` and
`stadium_shell_fbx.py`, then run:

```text
python tools/optimize_stadium_batch.py --config <local-config> --source <prepared-source> --work <new-work> --manifest data/stadiums/fl26_selected_v27.json --vertex-camera-cull
python tools/cook_stadium_batch.py --config <cook-config> --work <new-work> --keys EtihadStadium SanSiro SantiagoBernabeu SignalIdunaPark StamfordBridge OldTrafford
python tools/audit_stadium_optimization.py --config <cook-config> --work <new-work> --output <fresh-audit-directory>
```

The cooked audit checks sections, triangles, native crowd coverage, atlas IDs,
quantized bounds, vertex light, ETC1 encoding and cutout coverage. Geometry
sampling checks near/far camera cutaways; offline renders inspect the bowl and
both camera positions. Those renders do not substitute for Switch captures.

### Verified candidate, 2026-10-12

- Native build and NRO/ELF runtime identity checks passed. The NRO is
  83,813,279 bytes, SHA256
  `74f46da39aecb72fa8f362be44ba3d11c7c1a1386e055b221a9ab080bfa5ce2f`.
- Focused verification passed 60 tests and 919 subtests. A subsequent focused
  run passed all 15 asset, atlas, camera-culling and packaging tests after the
  final selective-culling changes.
- Native GLSL verification passed 706 variants / 2,824 compiler invocations.
  The final cooked material audit passed 41 live materials / 574 shader
  records, covering 4,592 clip/HDR variants with 192 unique compiles.
- All six actual cooked meshes passed the geometry/material audit. They total
  257,380 triangles including native crowds. Static cutout coverage matched
  exactly; crowd cutout mismatch was 0.5502%. Maximum baked-light error was
  below 0.005215 on a normalized colour scale. Quantized camera bounds retain
  at least 23.21 cm of margin at every tested vertex.
- Camera-clearance checks passed 181,440 geometry rays across all six venues.
  The separate sampled near/far overdraw audit removed no visible surfaces.
- All six PAKs passed independent UnrealPak integrity tests and byte-for-byte
  unpack verification for all 274 members. The final ZIP passed CRC and
  extracted-content comparisons.

The local delivery is
`local-debug/stadium-camera-v27/release/FootballNX-Stadiums-v27.zip`
(70,528,463 bytes), SHA256
`e7e524671aa68fb13ccde4bd143c8a8e8860a4f27f90b824299f4af266d96c8f`.
It includes the paired NRO and six PAKs, installation instructions, per-file
hashes and `VERIFICATION.json`. It is an ignored local candidate, not a public
asset or a hardware-accepted checkpoint. Loading time, frame pacing and native
camera appearance still require the Switch acceptance run below.

## Installation and acceptance

Install the matching NRO and six replacement/additional stadium PAKs together.
The accepted Anfield PAK, realfaces, physique CPKs, OBBs and saves remain in use.
Runtime identity remains e861c583ec78e9ae with the 53,248-byte patch OBB.
The scene log header is `FootballNX scene v27 session`.

Compare identical teams/settings in DAY and NIGHT: pass along the near
touchline and midfield, then the far side; cross the roof boundary and inspect
all celebration corners. Pause after each segment to flush the existing
presentation summary. Frame pacing and visual acceptance on Switch remain
pending; this candidate is not a verified 60 FPS fix.
