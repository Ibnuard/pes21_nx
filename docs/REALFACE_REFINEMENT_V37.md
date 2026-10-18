# Realface v37: visible facial detail and compact hair

The user reports that v36 corrected some heads, but Anthony Gordon still
shows severe triangular mouth corners. The strict **2,000 triangles per
complete head** remains required. They also requested compact, joined hair
where reducing individual strands leaves apparent bald patches.

## Diagnosis and policy

The isolated neutral normal material from v36 remains necessary and unchanged.
Gordon has a separate geometric problem: the skin simplifier can stretch the
mouth texture across a sparse triangle even when nearest-surface distance is
small. Its old recipe locked 345 neck vertices and assigned little importance
to UVs. Only 49 of those neck vertices are true attachment boundaries. Protect
that boundary, retain the original positions/UVs/bone weights of surviving
vertices, and spend more of the unchanged triangle budget on visible features.

`realface_surface_quality.py` projects source and candidate skin from identical
front and ±25-degree cameras. It measures visible UV displacement at the actual
92x124 skin tile, plus depth error. This detects distortion that positional
distance alone misses. A p95 above 1.3 texels around the mouth or 1.35 across
the face selects a head for refinement; these are screening thresholds, not
a universal guarantee of perceptual quality.

The repair increases UV importance, preserves up to 128 source-derived visible
mouth crease anchors, and preserves source smooth normals. Original face,
eye and lower-neck distance limits remain in force. A candidate must improve
both projection errors and pass the strict total-head ceiling before cooking.
The eye atlas must remain byte-identical; the original cooked skin colour
textures are retained in the release.

Hair with more than 12% missing projected coverage and the legacy strand-card
recipe is selected for a compact radial surface. Interior strand gaps are
filled behind the source hairline, without extending that hairline. Scalp and
beard have separate origins; a frontal jaw region welded to scalp cards must
still be classified as facial hair so the fill cannot bridge over the face.
The original 13-view silhouette and projected-layer workload gates remain
active. Hair stays one masked section with a 128x128 colour texture.

If filling the complete scalp envelope crosses the silhouette limit, the
automation retries a single compact surface with bounded gap closing instead.
This still replaces strand layers with one surface, but avoids bridging large
gaps between scalp and facial hair. Both alternatives use the same triangle
and silhouette limits; a failed bounded retry remains held.
Visual review can also select this conservative envelope through the local
`bounded_hair_base_ids` configuration. These are BaseIds in the independently
verified baseline, not donor slot substitutions. Automated projection scores
do not catch every hair/forehead intersection, so preview review is required.

## Reproduce locally

Extend the existing mobile factory configuration with:

```json
{
  "work_dir": "<repo>/local-debug/realface-surface-v37/refine",
  "cache_dir": "<repo>/local-inputs/realface-mobile-cache-v1",
  "baseline_pak": "<v36-release>/update/PesMobile/Content/Paks/<v36>.pak",
  "baseline_verification": "<v36-release>/VERIFICATION.json",
  "baseline_identity_report": "<v35-work>/verify-report.json",
  "release_label": "v37"
}
```

Keep the existing local tool, rig, source-profile and identity-state paths.
Run in order:

```powershell
python tools/realface_refine.py --config <local-config.json> prepare
python tools/realface_refine.py --config <local-config.json> cook
python tools/realface_refine.py --config <local-config.json> verify
python tools/realface_refine.py --config <local-config.json> preview
python tools/realface_refine.py --config <local-config.json> package
```

The audit covers the complete baseline roster; only selected repairs are
rebuilt. Source/code fingerprints and prepared/cooked cache hashes prevent
stale reuse. Blender prepares the selected heads in one process; the existing
UE importer/cooker and independent cooked-buffer validator check geometry,
normals, UVs, weights and triangle counts. Failed repairs remain held and
block packaging. No API, model call or per-frame runtime work is introduced.

The release starts from the verified v36 PAK and permits only selected face
mesh pairs, selected hair mesh pairs and their hair colour textures to change.
The private neutral normal texture, compiled material, material instances,
skin colour textures and all unaffected players must remain byte-identical.
Every output is checked by UnrealPak, independent repak roundtrip hashes and
ZIP CRC/embedded-PAK checks. `PLAYER-STATUS.csv` lists changes for every player;
`OUTSIDE-CANDIDATE.json` carries forward uncovered source identities.

The preview phase renders all selected faces from the front and changed hair
from an additional oblique view, using independently verified prepared meshes
and decoded cooked colour textures. It requires current prepared/cooked cache
keys and labels its provenance as an offline preview, never a device capture.

Previews are offline Blender renders, not Switch captures. The earlier user
report of 60 FPS applies to v35. Appearance and performance of the new PAK
still require a device comparison with the same Barca/MU lineup, camera,
stadium, DAY/NIGHT and near-camera passing sequence.

## Verified host result — 14 October 2026

All 51 baseline heads were audited. Eight facial surfaces and five hairstyles
were selected, covering 12 unique players. Every selected repair passed
prepared and independent cooked-buffer validation. The final package retains
the other 39 heads, the v36 normal correction and all skin colour textures.

| Player | Face refined | Compact hair | Complete head triangles |
| --- | --- | --- | ---: |
| Gabriel Jesus | Yes | Retained | 1,986 |
| Frenkie de Jong | Yes | Retained | 1,972 |
| Marcus Rashford | Yes | Retained | 1,994 |
| Mason Mount | Yes | Retained | 1,971 |
| Anthony Gordon | Yes | Yes | 1,988 |
| Noussair Mazraoui | Retained | Yes | 1,974 |
| Senne Lammens | Retained | Yes | 1,985 |
| Joan García | Retained | Yes | 1,974 |
| Benjamin Šeško | Yes | Retained | 1,985 |
| Carlos Baleba | Yes | Retained | 1,987 |
| Dermot Mee | Retained | Yes | 1,973 |
| Marc Bernal | Yes | Retained | 1,985 |

Gordon's worst-view mouth UV p95 falls from 1.837 to 0.917 skin-tile texels.
His new hair uses the same 260 triangles and retains a 0.921 minimum silhouette
IoU. The five hair repairs reduce projected triangle-layer fragments by
60–88% relative to their dense source models. This is an offline work proxy,
not a measured FPS improvement over v35/v36.

Mazraoui uses the automatic bounded-envelope retry. Visual review found a
forehead intersection in Lammens' initially passing solid-envelope preview;
the explicit `bounded_hair_base_ids: [134931]` policy chooses his conservative
joined surface. Seventeen final front/oblique previews use decoded cooked
colour textures; the corrected Lammens preview removes the intersecting fringe.

The 51-head range is **1,929 minimum / 1,985 median / 1,995 maximum**, totaling
100,950 triangles, with two sections per head. All 617 assets passed UnrealPak
integrity and independent repak hash comparison. Exactly 41 approved files
changed; the remaining 576 are byte-identical to v36. ZIP CRC and embedded PAK
hash checks passed, and rerunning packaging returned `verified_cached`.
Thirty-three focused tests passed; the 12 real cooked repairs also passed the
available local Blender/cooked-asset integration validator. The public-tree
audit passed with 909 files. No device run is claimed.

- PAK: `PesMobile-Barca-MU-Faces-Mobile-v37-Android_ETC1_P.pak`, 4,811,017 bytes.
- PAK SHA-256: `cd7263c1736badeaa13a9ae4b4bdc4bd6eda8dffa4a1ae9c5c4cf0d23994c497`.
- ZIP: `FootballNX-Mobile-v37-Barca-MU.zip`, 4,855,601 bytes.
- ZIP SHA-256: `8cff70c500d958126946c25d0af8f3af486922eb0bff6885a9a887b70ca6ebb4`.

The same eight roster identities remain outside the candidate because they
lack verified source faces. This release remains scoped to Barca/MU rather
than all previously imported league players. The active installation, NRO,
CPK and stadium packages were not changed.
