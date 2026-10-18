# Realface follow-up: Barcelona versus Manchester United

The user's device test rejects v34 as a performance solution: Barcelona
versus Manchester United still stutters, while removing the realface PAK
returns smooth 60 FPS by their observation. They explicitly confirmed that
only the Lite v34 face PAK was mounted; older face packages were absent.
This is device feedback, not a new captured GPU/CPU profile. The locally
available scene-runtime.log is still v26 and cannot diagnose this test.

## Verified remaining differences

`tools/audit_realface_match_budget.py` reads the existing verified player
counts and native cooked inventory. It needs no conversion or paid API.
The selected roster is 51 optimized identities across team IDs 100 and 108,
including substitutes. It does not imply 51 players are rendered together.

| Complete head | Native inventory | v34 Barcelona/MU roster |
| --- | ---: | ---: |
| Minimum triangles | 1,132 | 2,195 |
| Median triangles | 1,358 | 2,439 |
| Maximum triangles | 1,924 | 9,583 |
| Material sections | 2 | 3 |

All 51 exceed 2,000 triangles; eight exceed 4,000. The maximum belongs to
Roony Bardghji. The adaptive v34 quality allocation preserved more geometry
when a smaller candidate failed the surface checks. Thus its 76% aggregate
reduction did not make every head as cheap as a native mobile head.

Only 23 of these 51 storage slots have a complete native face/hair pair in
the base PAK. Removing the patch therefore mixes original real faces and
fallback heads; it is not a controlled comparison with 51 native real faces.
That does not invalidate the reported package-on/package-off result.

A focused Pedri cooked-asset comparison also found:

- Native face: 1,156 triangles, 688 vertices, one section; native hair:
  133 triangles, 399 vertices, one section.
- v34 face: 1,480 triangles, 885 vertices, separate eye and skin sections;
  v34 hair: 800 triangles, 1,332 vertices, one section.
- Both native and Lite section flags enable shadow casting and disable
  tangent recomputation. No newly enabled shadow flag was found in this
  sample. Native hair has one bone influence; Lite hair has up to three,
  both within the usual four-influence vertex layout. This is not a measured
  skinning-time comparison.
- Native hair texture is 128x128 BGRA8; Lite is 128x64 BGRA8. This sample
  does not support blaming a larger hair texture. It is not an inventory of
  every texture's residency or bandwidth.

These observations come from local UE Viewer/UAssetAPI assets and the UE4.22
headers. Section decoding was cross-checked against the
[UE Viewer serializer](https://github.com/gildor2/UEViewer/blob/master/Unreal/UnrealMesh/UnMesh4.cpp).
REA's deep native provider is not configured on this host; no REA runtime
observation or GPU measurement is claimed.

## Implementation direction

Do not start another 897-player conversion merely with a smaller decimation
ratio. First validate a mobile head recipe on the two affected rosters:

1. Use a strict gameplay budget around 1,300–1,800 triangles, with a 2,000
   ceiling and no automatic jump to 10,000. Keep face identity and neck
   attachment checks. Hold failures for a different topology instead of
   silently accepting a heavier mesh or another player's donor.
2. Combine the eye and skin textures in an explicit per-player atlas and
   merge their compatible opaque sections. Keep masked hair separate:
   target two material sections per complete head, matching the native
   reference. Verify eye UVs, iris appearance and the actual cooked slots.
3. Replace layered PC hair with a compact silhouette mesh and a limited
   number of fringe cards. Reducing triangles inside the same layers does
   not directly budget pixel overdraw. Measure projected layers/alpha
   coverage and inspect the silhouette, rather than only triangle count.
4. Compare that small candidate against v34 and no patch with identical
   teams, lineup, stadium, camera, quality and DAY/NIGHT settings. If the
   frame-time difference remains, capture draw/upload/presentation counters
   before choosing a shader or runtime change. Do not infer GPU time from
   static counts or CPU submission counters.

Keep the existing v34 assets as the close-up source. A second LOD can preserve
detail for replay/celebration later, but adding LOD1 alone is not evidence
that this game's loader/master-pose route selects it. Verify that route
before claiming automatic gameplay/close-up switching. A single mobile head
LOD is the simpler first test and adds no per-frame camera/player polling.

The subsequent [Mobile v35 canary](REALFACE_MOBILE_CANARY_V35.md) implements
this direction for 51 Barcelona/MU identities and records its host validation.
Device acceptance remains pending. Texture downsizing, disabling
all player shadows, and lowering global image quality are not established
fixes. Layer overdraw and submission costs remain hypotheses until device
evidence separates them.

## Reproduce the roster audit

```powershell
python tools/audit_realface_match_budget.py `
  --verification <lite-release/VERIFICATION.json> `
  --status <lite-release/PLAYER-STATUS.json> `
  --native-metrics <native-mesh-metrics.json> `
  --team 100 --team 108 --output local-debug/<audit>/barca-mu-budget.json
```

The output records source hashes, all selected names, triangle/vertex/section
counts, native-slot availability and coverage gaps. Five synthetic tests cover
shared identities, absent hair pairs, duplicate/mismatched IDs, incomplete
coverage and held meshes.
