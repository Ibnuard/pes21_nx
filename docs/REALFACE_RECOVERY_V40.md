# Incremental league face recovery, v40

## Device regression report: held for investigation

The subsequent device test reports widespread damaged/missing/blinking head
textures and missing Yamal hair. The user-supplied v40 PAK SHA-256 matches the
published candidate. Yamal's 12 per-player assets are byte-identical to the
inherited v37 head, so the report cannot be explained as a new v40 Yamal
decimation alone. Earlier per-head approval states are historical evidence,
not acceptance of this combined package in the current runtime.

Do not promote v40 or extend the same recipe on the strength of the offline
screen/cook passes below. The user has also replaced the strict 2,000-triangle
requirement with a request for measured quality/performance tradeoffs. Old
package ceilings remain factual descriptions, not a budget for all future
recipes. See [the controlled baseline procedure](MATCH_PACING_BASELINE_V41.md).

This continues the 623-head v39 TEST package across the same 1,122 unique
roster identities in 39 playable teams (19 English, 20 Spanish). Sunderland
is absent from this native catalogue. It does not imply complete coverage of
every present-day league club. The full-head ceiling remains 2,000 triangles
and two existing material sections. Switch performance and full appearance
approval remain pending; v35's hardware result is not a measurement of v40.

## Completed recovery pass

| Outcome | Unique players |
| --- | ---: |
| Included in the v40 TEST candidate | 740 |
| Byte-identical inherited v39 heads | 623 |
| New screened and independently cooked heads | 117 |
| Missing/unverified source identity or assets | 215 |
| Remaining visual holds | 153 |
| Remaining geometry holds | 14 |

All 499 identities excluded from v39 were accounted for. Ten recovered
sources plus the 274 earlier technical/visual holds produced 284 processing
targets. Every one has a final source, geometry, appearance or cooked outcome.
The 260 already-prepared heads and ten new sources received front screening.
All 163 rejected hairstyles received a joined-scalp attempt, with 71 exported
geometry passes screened again. The 14 earlier geometry failures were retried
under the same strict limits and remain held.

All 123 selected cook attempts passed independent validation; six were
excluded after visual review (one front-view refinement and five defects
visible from oblique/top angles). The final 117 additions have 1,426–1,996
triangles and two sections. The complete package retains the 2,000 maximum.
Only the inherited 51 v37 heads retain their earlier accepted state; all
other 689 are TEST heads, not a new hardware acceptance.

The exact current local result is recorded in
`local-debug/realface-native-hair-v40/latest-test.json`. Its release folder
contains `PLAYER-STATUS.csv`, `TEAM-COVERAGE.csv`, `VERIFICATION.json`, install
instructions and the full replacement ZIP. Do not add the binary package on
top of another real-face PAK.

Validation completed: 71 focused tests, public-tree audit (1,047 files),
8,885 PAK entries checked, independent unpack hashes, ZIP CRC and embedded
PAK hash. The ZIP is 68,589,448 bytes; SHA-256
`3e0154e97abdadfcf3471b2dfa2fe48de4ac382dde01929bfe827bbde5cedede`.
The PAK SHA-256 is
`b639c86357631ab5fbed419fc0c41311c7ab29da9354393210ef7d11b93f7a24`.

Optional deletion of this pass's verified temporary `stage` and `roundtrip`
trees was rejected by automatic approval review ("blocked by policy"). They
remain local on D:; cleanup was not retried through a different mechanism.

## Source recovery

The source audit checked the 12 configured FL26 archives, plus the 48 base
Data CPKs and the additional unlock archive. The extra archives provided no
additional numeric face sources. The local Extra1..5 files were placeholders.

Ten explicit aliases increased identity-verified source coverage from 897 to
907. Each alias requires the same BaseId, current canonical fingerprint,
allowlisted source/canonical names, height/age bounds, foot, and goalkeeper
class. A nationality difference requires that alias's documented exact pair.
Runtime identities and storage slots are unchanged.

The evidence and primary club/league/federation links are recorded in
[`data/realface-source-aliases-v1.json`](../data/realface-source-aliases-v1.json).
The recovered names are Iván Cuéllar, Jean-Ricner Bellegarde, George
Tsitaishvili, Carlos Protesoni, Arnaud Kalimuendo, Urko González de Zárate,
Pablo, Will Osula, Jair Cunha and Youssef Enríquez. Source recovery does not
mean the converted head passed visual selection. The remaining 215 source
holds cannot be solved by increasing the triangle allowance or guessing a
donor identity. The Benoît Aimée/Nicolas Jackson conflict and the conflicting
foot evidence for Jean-Mattéo Bahoya remain unresolved.

## Bounded conversion and selection

- Preserve all 623 prior PAK heads byte-for-byte, including the 51 accepted
  v37 heads and the neutral face material. Preserve their approval states.
- Reconsider the 260 remaining previously prepared heads. Preserve their
  verified facial mesh/UVs, rather than repeating expensive preparation.
- Screen every exported candidate. Route fragmented hair, beard plates,
  bald gaps and swollen caps through source-derived joined scalp recovery.
- The joined route spends only the unused portion of the 2,000-triangle
  budget on scalp. Source facial hair is projected onto the existing atlas;
  no extra runtime light, normal texture or material section is introduced.
- Require the existing 13-view geometry bounds and actual FBX reimport.
  Geometry scores do not override a visibly bad hairline or forehead patch.
- Retry the 14 earlier geometry holds with bounded allocations and the same
  facial surface/neck/eye checks. Failed attempts remain explicit holds.
- Cook only exact-key screened candidates, then independently inspect cooked
  meshes, skeletons, buffers and materials. Front screening is not four-angle,
  animation or device approval.
- Repack a full replacement TEST PAK. Check every inherited byte, perform
  UnrealPak's integrity test, independently unpack/hash the result, and check
  ZIP CRC plus the embedded PAK hash.

The full player CSV records both included and excluded identities; team
totals count actual PAK membership. All raw assets, source indices, images,
reports, PAKs and archives remain ignored and local. Only authored automation,
tests and evidence policies belong in the public repository.

## Repeat locally

The inputs below are optional local fixtures, not files to commit. Use a
fresh ignored folder for changed recipes. A completed cache with changed
bytes is an error, not something the factory silently overwrites.

```powershell
. D:\PESNX-Cache\use-cache.ps1

# A missing source index is built once from the configured local CPKs.
python tools/realface_source_recovery.py --config <source-config> --inventory <inventory> --index <ignored-index.json> --aliases data/realface-source-aliases-v1.json --work-dir <source-recovery-dir>

# Prepare recovered verified sources through the existing batch preparer,
# then retain the same seam/normal/surface checks for the mobile head.
python tools/realface_recovered_sources_mobile.py --config <mobile-config> --inventory <recovered-inventory> --prepared <source-prepare-report> --work-dir <mobile-recovery-dir>

python tools/realface_joined_recovery.py --config <mobile-config> --face-report <prepared-report> --baseline <v39-verification> --mode preserved_surface --work-dir <preserved-dir>
python tools/realface_native_hair_screen.py --config <mobile-config> --report <immutable-candidate-snapshot> --work-dir <screen-dir>
python tools/realface_native_hair_screen_review.py --report <immutable-candidate-snapshot> --screen-dir <screen-dir> --reject-file <rejects.json> --page 1 --reject "<BaseId>=<observed defect>"

# For rejected hair only; no inherited v39 head can be replaced.
python tools/realface_joined_recovery.py --config <mobile-config> --face-report <prepared-report> --baseline <v39-verification> --mode joined_scalp --player <BaseId> --work-dir <joined-dir>

# --reviews contains [{"report": "...", "screen_dir": "..."}].
# Use a short cook directory for legacy Windows exporter path limits.
python tools/realface_incremental_validate.py --config <mobile-config> --report <screened-candidates.json> --reviews <reviews.json> --baseline <v39-verification> --work-dir local-debug/j40-cook --workers 1
python tools/realface_incremental_coverage.py --specification <coverage-inputs.json> --work-dir <recovery-dir>
python tools/realface_incremental_candidate.py --config <mobile-config> --verified <recovery-dir>/selected-verified.json --reviews <reviews.json> --baseline <v39-verification> --baseline-pak <v39-pak> --status <recovery-dir>/coverage.json --work-dir <recovery-dir>
```

`coverage-inputs.json` names `baseline`, `inventory`, and lists of `reports`,
`rejects`, and `verified`. Reports include every attempted identity, not only
successful cooks. Exact-key rejection is retained across reconciliation.
An immutable baseline plus cached per-head recipes makes later recovery
incremental; large Blender/tool binaries are hashed once per batch and their
file metadata is checked during it. These commands do not install or publish
the candidate. Use only one face PAK when testing; no new NRO, CPK or OBB is
required by this asset-only recovery.
