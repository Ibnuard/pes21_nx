# France, Italy and two additional clubs

23 October 2026. The user explicitly selected Ligue 1 France, Serie A Italy,
Al Nassr and Inter Miami and reaffirmed the existing release criteria:
complete-head target 4,500–5,000 triangles, unique hairstyles at most 7,000.
Do not inflate smaller valid heads, add cosmetic review loops or rebuild the
previous English/Spanish cohort. Identity, valid rig/sections and actual cooked
triangle counts remain necessary to avoid broken or incorrectly owned players.

The active catalog contains 18 French and 19 Italian clubs plus the two named
clubs: 39 teams, 1,144 unique roster identities. Initial local inventory has
743 source candidates, 199 missing sources, 201 unresolved source identities
and one ambiguous source identity. These statuses are not global unavailability.
Of the 743 candidates, 699 have the original BaseId/name/biography evidence.
The remaining 44 now have an explicit own-source biography supplement: 41
direct BaseIds with disclosed height/foot metadata differences and three
documented source aliases. Full name, country, age and goalkeeper class agree;
aliases additionally require matching foot and height within 3 cm. The
supplement binds the canonical fingerprint, inventory, source player-table and
row hashes. This admits source identity only, not cooking or visual acceptance.
Never use a numeric slot as a donor.

Local state is under `local-debug/realface-france-italy-v71/`. Check actual
process identity/creation time, children and moving logs before resuming.
`BATCH-RUN-LATEST.json` pins the serial dense owner; `DENSE-STAGE-STATUS.json`
is distinct from final budget/cook acceptance. Dense conversion failures such
as the Ronaldo collar-support refusal require a changed, scoped recipe or a
documented hold. Do not rerun deterministic failures unchanged.

An interrupted owner left 401 checkpointed rows (391 prepared, ten conversion
holds). Windows recorded resource exhaustion at the interruption; the precise
termination cause is unproven. Resume from the cache after the isolated v71
gameplay build, rather than running the two heavy stages together. Check current
receipts for newer progress before acting on these historical counts.

After dense conversion finishes, initialize once:

```powershell
python -B tools/realface_league_expansion.py `
  --dense-config local-debug/realface-france-italy-v71/dense/config.local.json `
  --accepted-config local-debug/realface-leagues-balanced-v55/config.local.json `
  --output local-debug/realface-france-italy-v71/budget
python -B tools/realface_league_balanced.py run `
  --config local-debug/realface-france-italy-v71/budget/config.local.json
```

The explicit `identity-bound-dense-v1` admission binds the inventory row,
BaseId/native ID/fingerprint, original source biography and dense cache/profile/
FBX/texture hashes. It does not label dense preparation as independent cooking.
The historical accepted-source path remains strict by default. A single serial
budget worker and shared engine cook/validator continue the existing CLI/cache
pipeline. The previous 907 cooked heads are preloaded into verification and
must remain exact; only new owners are reduced/cooked. Source/identity holds
are emitted separately. Cosmetic observations do not block release.

Package the independently validated bounded new heads together with the exact
existing face assets and latest verified gameplay/FootballNX.assets candidate.
The current gameplay work is `local-debug/review-v71/`; never replace it with
the old v54 NRO merely because historical configuration pins that candidate.
Verify PAK allowlist/unpack, ZIP CRC/payload hashes and preserved head hashes.
No device playback, FPS, full coverage or visual acceptance may be inferred
from dense preparation, numeric checks or desktop cooking.

The first budget run stopped at Eric Dier (47431): his dense hair carries an
opaque skin material, which the current reduction recipe explicitly refuses.
The league runner now records that owner as a source/material hold and continues
the other heads. It does not bypass the trial guard or turn this into a
successful preparation. Pinned-input changes and native-owner mismatches remain
fatal. Existing prepared and cooked rows are resumed from their checkpoints.
The first budget cohort is terminal: 703 new heads passed independent cooking,
31 remain geometry holds and three require a scoped source/material recipe.
The 907 earlier heads remain intact. Bounded recovery runs in a separate work
directory, carrying every successful preparation and cooked proof. Source
invisibility requires the same player's raw material/geometry proof; an empty
raster alone is insufficient. The exceptional ceiling includes exactly 7,000.

For this explicit human budget-priority release, the bound review records
identity, rig, two sections, integrity and cooked counts without claiming new
image inspection or visual acceptance. Held sources remain native fallbacks.
The packager's default remains strict visual review. Expanded packages pin the
latest runtime explicitly and compare all 907 previously released head payloads,
including textures, byte for byte.

Legacy exporters can silently omit dependencies when deeply nested recovery
paths exceed the Windows path limit, producing `dummy_material_0` even though
the cooked material exists. The validation-only alias must resolve to the same
canonical work root and retain every relative asset path. Existing cooked bytes
can then be independently revalidated without cooking them again. An alias to
another directory or an input outside the bound root is rejected; material,
rig, normal, triangle and section checks are unchanged.

The latest verified gameplay is the ten-payload v75 set documented in
`WEATHER_WORLD_ANCHOR_V75.md`. The earlier v71/v73 paths above are historical;
never let their NRO/CPK pins replace the current runtime. The serial combined
pipeline and its dependency receipts are under the ignored expansion work root.

The final host-verified candidate contains 731 new heads from the 1,144 audited
expansion identities, together with all 907 previous heads byte-identical:
1,638 heads across the combined 78-team, 2,266-identity scope. Of 743 source
candidates, 738 reached dense preparation and 731 passed bounded reduction and
independent cooking. Five dense and seven material/UV/source-slot holds remain.
The other expansion fallbacks are 199 locally absent sources, 201 unresolved
source identities and one ambiguous identity; these are not global absence.

The combined package has 1,534 heads at or below 5,000 triangles and 104 explicit
exceptions, with an actual maximum of 6,996. All ten v75 runtime payloads remain
exact. PAK allowlist/Test, independent extraction, all 907 prior head hashes,
ZIP CRC/member hashes and the native C loose-CPK/marker validator passed, along
with 89 focused tests and the 1,319-file public-tree check. Fifty-one cooked hair
mip chains retain advisory warnings without forced alpha. These results do not
claim new visual acceptance, full roster coverage or device frame-time proof.
