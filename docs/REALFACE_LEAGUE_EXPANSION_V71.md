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
The latest verified gameplay set is now the eight-file v73 candidate documented
in `ATMOSPHERE_CORNER_V73.md`; the v71 gameplay path above is historical.
