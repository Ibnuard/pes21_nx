# Runtime face regression and controlled budget trials

The v40 report from the device describes disappearing/blinking face textures,
missing Yamal hair and dented faces. Offline geometry acceptance does not
establish correct native material selection, animation or GPU behaviour. No
device appearance fix or measured frame-rate sweet spot is claimed here.

## Verified baseline

- The supplied v40 PAK matches the released test PAK, SHA-256
  `b639c86357631ab5fbed419fc0c41311c7ab29da9354393210ef7d11b93f7a24`.
- Its stage contains 740 heads and 8,885 hash-verified assets. Every face colour
  mip is opaque. Hair is BGRA8; face colour is ETC1.
- Yamal (BaseId/native ID 162114) has 1,810 face triangles and 167 hair triangles.
  His twelve packaged files are unchanged from the inherited accepted release.
  His eight hair mips retain alpha above the native mask threshold; the final
  mip is opaque. Disappearing tiny hair mips do not explain his reported loss.
- There are 91 catalogue hair textures with at least one fully discarded mip,
  including seven entirely transparent textures. Empty native hair placeholders
  must be distinguished from a damaged hairstyle before changing alpha.
  Among the 51 packaged Barca/MU heads the tiny-mip cases are Karl Darlow,
  Eric García and Manuel Ugarte. This is a separate bounded follow-up, not an
  explanation for widespread face damage.
- Yamal's serialized face and hair bounds are broad rather than an obvious
  too-small box. Both have one LOD and the expected 29-bone embedded rig.
  Existing ForceLOD host checks clamp to available LODs.
- The neutral face parent retains compiled native shader bytes. UE4.22 resolves
  texture uniform expressions by index against each material's own referenced
  textures. A shared shader-map identifier alone is not evidence that materials
  share the wrong diffuse texture; no speculative GUID edit was made.

`tools/audit_realface_runtime_assets.py` checks every staged hash and every
decoded mip, including small mips, and resolves imported FNames with their
numeric suffix. UE stores `face_162114` as `face` plus number 162115; checking
the raw name table alone incorrectly reports a missing dependency.

Ignored local evidence is under
`local-debug/face-runtime-audit-20261016/full-audit/asset-audit.json`. Paths under
`local-debug/` are optional inputs, not repository guarantees. The report
explicitly records `device_appearance_pass=false` and `hardware_profiled=false`.

## Barca/MU experiment

The revised user scope is teams 100 and 108, not another league-wide rebuild.
The verified roster has 59 identities, of which 51 have accepted source heads.
All 51 v40 heads are inherited v37 assets. Their total is 100,950 triangles
(1,929–1,995 each); all colour mip payloads total 4,074,852 bytes across the
catalogue, not the resident size of one match. The corresponding accepted PC
source conversions total 649,019 triangles (5,560–33,470 each; median 10,936).

The isolated `tools/realface_budget_experiment.py` compares 3,000, 4,500 and
6,000 complete-head ceilings. The initial cohort is Yamal, Anthony Gordon and
Bruno Fernandes. It uses identity/fingerprint-verified fitted sources, original
eye surfaces, source normals and UV checks, the same visible-hair policy, a
256-pixel opaque face atlas, 128-pixel hair texture and two material sections.
Only skin/hair geometry allowances vary. The user no longer requires 2,000 as
an immutable limit; the production recipe is nevertheless left unchanged.

The production Blender worker contains its own additional 2,000 clamp. A
separate explicitly guarded experimental worker reuses its face/hair audits
without silently lifting the production cap. Failed silhouette, coverage,
normal, UV, identity or cooked-rig checks remain held. There is no automatic
fallback to a generic face or a more permissive visual gate.

Preparation outputs and per-cap reports live in an isolated directory. Cook
and independent verification can reuse the existing factory, but this tool has
no package or install phase. A trial must still receive visual and device
review before release. Hardware measurement must compare identical teams,
camera, weather, near-camera ball path and instrumentation; budget counts alone
cannot select the frame-rate sweet spot.

Example with available local inputs:

```powershell
. D:/PESNX-Cache/use-cache.ps1
python tools/realface_budget_experiment.py prepare `
  --config local-debug/realface-leagues-v38/seam-recovery/config.local.json `
  --output local-debug/face-budget-experiment-v41 `
  --team 100 --team 108 `
  --scope-verification local-debug/realface-native-hair-v40/test-packages/57528f6953a9ea47/release/VERIFICATION.json `
  --player 162114 --player 119835 --player 60512 --workers 1
```

Use `--cap 4500` to select one explicitly reviewed allowance and omit `--player`
to cover the available Barca/MU sources. The scope report retains unresolved
identities instead of substituting donor faces. `cook`, `verify` and `status`
use the same arguments and isolated output directory. `comparison.json`
distinguishes requested ceilings, actual triangles and held reasons.

The follow-up serial runner, bounded hair reallocation and explicit TEST
packager are documented in [the budget trial workflow](REALFACE_BUDGET_V41.md).
They retain independent cooked verification and never install or approve a
candidate automatically.
