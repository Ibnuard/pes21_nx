# Barca/MU source-detail experiments

The user narrowed the next face work to Barcelona and Manchester United and
withdrew the previous fixed 2,000-triangle ceiling. The objective is a measured
balance between appearance and runtime cost. A larger offline count is neither
an FPS result nor permission to ship broken eyes, necks or hair.

## Scope and existing regression

The identity-verified roster has 59 players across team IDs 100 and 108.
There are 51 verified source heads; eight lack a verified source/identity:
Jesse Bisiwu, Shea Lacey, Tyler Fletcher, Eder Aller, Xavi Espart,
Hamza Abdelkarim, Jordi Pesquer and Brian Fariñas. Native fallback is retained
for unresolved identities; donor faces are not assigned by numeric slot alone.

The received v40 PAK exactly matches the recorded release hash. Its 8,885
staged files were checked and all 740 face diffuse mip chains are opaque.
Resolved mesh/material import declarations have no missing required name.
UE FName numeric suffixes must be decoded: `face_162114` may be serialized as
`face` plus number 162115, not a literal name-table string.

Ninety-one hair textures contain entirely discarded small mips, including
seven fully transparent placeholders. In the selected Barca/MU roster this
affects Karl Darlow, Eric García and Manuel Ugarte; Yamal is not among them.
Empty placeholders can be deliberate. This evidence does not explain the
reported widespread disappearing faces, dents or Yamal hair, and does not
justify filling every alpha channel or patching shared shader IDs.

All 617 assets in the earlier 51-head v37 Barca/MU package match their v40
counterparts byte-for-byte. That smaller package is therefore a useful
unchanged control for whole-catalog versus team-only mounting. It is not a
newly repaired face package or proof that the older assets cannot be faulty.

## Controlled geometry trials

`tools/realface_budget_experiment.py` uses source identities and pinned inputs
from the existing PC-to-Mobile pipeline. A separate Blender worker exposes
explicit 3,000 / 4,500 / 6,000 complete-head limits without changing legacy
production recipes. Both the outer budget and the former inner 2k clamp are
accounted for. Each trial preserves:

- one opaque face/eye section and one native masked hair section;
- 256px opaque face colour, 128px hair colour and the native rig;
- source eye surface, neck seam handling and transferred shading normals;
- face UV/normal/anatomy checks and 13-view hair coverage checks;
- recorded source, tool, recipe and prepared/cooked hashes.

The allowance is mostly spent on facial anatomy. Hair reduction removes
hidden sheets and simplifies retained source sheets. It does not generate a
generic dark dome. Hair gaps or an increased layer workload hold a candidate;
the ceiling is never met by ignoring its quality failure.

Initial prepared sample results:

| Player | Audited PC-derived head | 3k trial | 4.5k trial | 6k trial |
| --- | ---: | --- | --- | --- |
| Anthony Gordon | 26,332 | 2,978; geometry pass | 4,476; geometry pass | 5,977; geometry pass |
| Bruno Fernandes | 20,424 | held: hair gaps | 4,296; geometry pass | 5,802; geometry pass |
| Lamine Yamal | 26,748 | held: hair silhouette | held: hair gaps | 5,970; geometry pass |

These counts cover face plus hair. The initial 6k sample uses two sections,
versus four in each corresponding dense imported source. The offline hair
raster fragment count drops by about 56% for Bruno and Yamal and 17% for
Gordon. Those are fixed-view overlap measurements, not measured GPU savings.
All three 6k preparations pass the unchanged hair coverage gates. Visual and
independent cooked checks remain separate steps.

The full team preparation produces 50 candidates from the 51 verified
sources, at 4,315–5,980 triangles each. Alejandro Balde and Ayden Heaven pass
with 3,000 skin triangles and the remaining allowance assigned to hair.
Jules Koundé still fails hair coverage after both bounded reallocations and
is held. Together with the eight unresolved identities, this leaves nine
native fallbacks before cooked validation; none is silently filled with a
previously damaged head.

## Automation and measurement

Use a local config with the pinned input/tool paths. Every cache/output below
is on D:. Successful cached work and deterministic failures are reused.

`tools/run_realface_budget_trial.py` chains these phases serially, including
four-angle cooked-texture previews for Yamal, Gordon and Bruno. It uses one
worker and can resume with `--from-phase recover` after preparation has completed.
It records `RUN-STATUS.json`; a ready test package still requires image review
and hardware testing. It is an ordinary local CLI job, not a recurring task.
The scoped cook helper accepts `--import-chunk-size` through the runner
(1–16, default 8). Larger chunks avoid repeatedly loading the editor while
still running one editor at a time; they do not alter the game assets' budget.
The current host uses chunks of 12, with a single validation/render worker.

The first full 6k cook independently verifies all 50 prepared candidates.
Front review of the complete cohort and four-angle pilot review remain
separate evidence. The source comparison for Bruno exposes a limitation of
silhouette-only hair acceptance: a permissive collapse can turn adjacent
beard cards into a broad cheek/jaw fin while retaining the overall outline.
The optional `face_locked_cards` experiment locks forward facial-hair
vertices below 170 cm (Y > 5 cm, |X| < 9 cm), uses 0.45 cm hair simplifier
error and UV weight 0.5. All existing surface, rig, coverage and complete-head
gates remain. Bruno's prepared repair totals 5,995 triangles and removes the
visible fin in front and side review with the same cooked colour textures.

`tools/realface_budget_hair_repair.py` retries baseline heads having at least
20 source triangles touching that region. It preserves each head's original
face allocation, including earlier bounded reallocations, records every
attempt and merges only identity-matched results. A held repair remains a
native fallback. Unchanged heads retain explicit prior cooked provenance.
Five locked-hair preparations exceed 6k while preserving the face allocation:
Gordon, Zirkzee, Amad, Yoro and Heaven. A separate, explicit 7k ceiling allows
these bounded exceptions. Successful 6k repairs are reused; only the five
held heads are prepared again. This allocation follows observed geometry
needs and is still awaiting the same device performance comparison.

Seven first-cook hair textures have entirely discarded 1–2 pixel mips:
Karl Darlow, Marcus Rashford, Lisandro Martínez, Eric García, Amad Diallo,
Manuel Ugarte and Carlos Baleba. `tools/realface_hair_mips.py` scales only
the alpha of those tiny, nonzero mips until their maximum reaches 86/255.
It preserves RGB, payload sizes, mip zero, visible mips and empty source
placeholders. Larger or zero-alpha unexplained losses are held. The packager
records every changed mip and reopens its same-sized payloads for validation.
This is bounded distant-hair protection; it does not establish the cause of
the reported Yamal/runtime disappearance, because his mips were visible.

For 6k hair coverage holds only, a recovery phase tries allocating 3,000 or
2,600 skin triangles and giving the remainder to hair. The complete-head
ceiling, eye allocation and all anatomy/UV/normal/coverage thresholds stay
unchanged. Successful original preparations are retained; failed reallocation
attempts are cached and reported. This changes allocation, not acceptance gates.

```powershell
. D:\PESNX-Cache\use-cache.ps1
python tools/run_realface_budget_trial.py --config <local-config> --output local-debug/<trial> --cap 6000 --import-chunk-size 12 --baseline-stage <verified-stage> --baseline-verification <v40-verification>
python tools/realface_budget_hair_repair.py --baseline-config local-debug/<trial>/6000/config.local.json --output local-debug/<repair> --repair-cap 7000 --reuse-prepared-repairs <6k-hair-repair-report>
python tools/run_realface_budget_trial.py --config local-debug/<repair>/7000/config.local.json --output local-debug/<repair> --cap 7000 --from-phase cook --import-chunk-size 12 --baseline-stage <verified-stage> --baseline-verification <v40-verification>
```

The test packager requires the complete selected preparation and verification
reports, rechecks identity/cache hashes and cooked counts, excludes held heads,
preserves the private neutral material dependencies, checks texture mips and
resolved imports, and independently unpacks/hashes the result. Its per-player
status includes unresolved and held native fallbacks. It never installs the
PAK or marks device appearance/FPS as accepted.

The completed local `v41-7k TEST` cook contains 50 independently verified
heads: 45 at or below 6,000 triangles and five bounded exceptions. Counts are
4,315–6,932, averaging 5,795.28 (289,764 total), with two sections per head.
This is 0.90% more total geometry than the first 50-head 6k preparation,
after protecting facial-hair cards. The five exceptions are:

| Player | Complete head triangles |
| --- | ---: |
| Anthony Gordon | 6,075 |
| Joshua Zirkzee | 6,932 |
| Amad Diallo | 6,261 |
| Leny Yoro | 6,462 |
| Ayden Heaven | 6,132 |

Koundé and the eight unresolved identities remain explicit native fallbacks.
The PAK contains 605 whitelisted files, is 9,463,540 bytes and passes an
UnrealPak integrity test plus independent unpack/hash comparison. All face
mips remain opaque. Thirteen tiny mips across the seven listed hair textures
are repaired; no nonempty hair texture retains a fully discarded mip.
The local ZIP is 9,440,384 bytes. Neither these checks nor the image review
are hardware FPS or animation acceptance.

Offline review covers all 50 fronts plus front/left/right/above views of nine
selected heads. Faces and necks retain their surfaces in these rest previews.
Broad hair cards remain apparent in close-ups of Cunha and Mbeumo's facial
hair and Zirkzee's scalp hair. These are recorded as visual follow-up rather
than granting final style approval. The local `PLAYER-REVIEW.csv` and
`VISUAL-REVIEW.json` distinguish a candidate ready for device performance
testing from approved runtime appearance; the package remains a TEST build.

- PAK SHA-256: `29ece9f16d68292e8217cba1165474f51b13d4acd3589287a388ef85b147faac`
- ZIP SHA-256: `e84cce1a8cf5f0857762a7aa42d588915f2be760900339ce0f5dd184c2f250f4`

Compare the no-additional-face baseline, unchanged team-only control, and
candidate using the same NRO, lineup, camera, settings and play sequence.
See [the diagnostic workflow](MATCH_PACING_BASELINE_V41.md). Geometry,
section/layer counts and texture bytes complement measured presentation
intervals; none can select a universal triangle sweet spot alone.
