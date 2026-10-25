# Expanded realface body-palette correction

The user reports dark/light discontinuities between the new French/Italian
heads and their native bodies. The accepted mesh batch did not synchronize
body palettes. A native skin selector is separate from a realface's albedo;
correct head identity/triangles do not establish matching body colour.

`tools/realface_skin_batch.py audit|status --config <local-config>` processes
validated expansion heads serially, with one immutable-input binding and one
checkpoint per player. It compares three opaque neck swatches with the six
native body palettes in Lab space. The same player's final prepared profile,
validated head and canonical BaseId/native ID/fingerprint must agree. Null
BaseId FL-only identities do not select assets. Duplicate native owners fail.
Previous 907 heads and explicit accepted skin policies are preserved.

The audit is measurement only. Consistent swatches and a meaningful distance
improvement create a review candidate, never an automatic patch. Inconsistent
swatches, native default selectors and missing appearance rows are reported
separately. Image/lighting differences and unknown default resolution require
further evidence; do not infer skin from nationality, a name, a donor slot, or
API fields that do not exist. Inspect the actual selected texture/neck material
and a bounded comparison sheet before admitting each policy group. An empty or
wrong UV swatch cannot stand in for a skin decision.

The ignored work root is `local-debug/realface-skin-v76/`; its config pins the
latest v75 dt200, source/verified reports, canonical identity state and native
swatches. `AUDIT.json`, `RUN-STATUS.json`, `HANDOFF.json` and per-player caches
are distinct from a staged/verified correction. Check a real owner's process,
creation time and log before resuming a live CLI. Do not recook the head batch,
rerun deterministic holds unchanged, or mutate a pinned config during a run.

Use `patch_player_skin` and `stage_skin_profile_update` for reviewed existing
appearance rows. Only byte 37 bits 0..2 in the player's 60-byte appearance row
may change. Missing rows need a separately audited native representation; do
not create donor rows or bypass fixed-count/version rules. Preserve physique,
identity, stats, face ownership, all 1,638 head payloads and every unrelated CPK
member. Check exact row hashes, allowed bits, idempotence and archive roundtrip.

Compose the result with the CURRENT cinematic-compatible manifest using
`tools/compose_loose_cpk.py`, refresh the trophy marker from measured hashes,
and verify all 24 CPKs through overlays plus the actual native C validator.
Never reuse the pre-cinematic skin/physique manifest that caused dt220 startup
failure. Keep the current NRO, commentary, weather, scoreboard and adboard
payloads. All candidates/temp/cache/logs remain on D, without OBB duplication
or active runtime installs. Deliver a verified ready-copy folder/ZIP with
audited/corrected/held counts and explicit device-evidence limits.

The requested hourly in-chat automation continues this correction and stays
quiet during healthy pending work. It stops after the verified correction
candidate is actually handed over, rather than after measurement alone.

## Released-texture provenance follow-up

`tools/realface_skin_provenance.py --config <local-config>` independently
binds each audited BaseId, native ID and fingerprint to its final validated
profile and released texture. It verifies the prepared profile/atlas hashes,
import profile and own material report, cooked completion hashes, released
texture hashes and resolved material import declarations. It decodes the
actual cooked texture and compares the same opaque neck regions with their
source samples. A changed nearest palette or more than four Lab units of
source/cooked difference prevents reuse of the source recommendation.
Per-player receipts and the final aggregate remain separate from a skin patch.
Material import declarations are static evidence; they do not establish that
the Switch selected that package during a match.

The exact compatible native body consumer distinguishes default selectors:
zero resolves to body palette one, while seven clamps to body palette six.
The face-montage consumer has a different clamp and must not be substituted
for the body route. The ignored evidence binds the native file digest,
appearance-to-character-config path, body-texture filename consumer and eight
isolated compiled clamp cases. This is static analysis and bounded instruction
emulation, rather than game execution or hardware appearance acceptance.

For the 37 absent rows, canonical owners and final validated head identities
agree, but neither their exact native IDs nor the actual native lookup keys
resolve to an appearance row. A BaseId appearance row is absent as well.
Thirteen native lookup keys differ under the native mask; a numerical match
elsewhere in Player.bin can belong to another person and cannot supply a
donor appearance. These cases are schema holds for the existing-row-only
patcher. Creating records or overriding the runtime fallback would require a
separate, fully validated representation change.

The reviewed-update continuation waits for the exact provenance process
creation identity and a complete 731-player result before staging. Its frozen
inputs, own-row policy, current runtime binding and finite failure state prevent
an incomplete audit, changed recipe or historical PID from starting a duplicate
job. A partial candidate never ends the remaining scope or its automation.
Final packaging must use the latest verified runtime override in the handoff,
including the v77 NRO/assets and canonical Camp Nou PAK, rather than the
historical v75 runtime path pinned for the original measurement audit.

## Complete-scope continuation

`tools/realface_skin_scope.py` joins the immutable 731-player audit, completed
released-texture proofs, native schema diagnosis and already reviewed policy.
It resolves the actual body defaults before comparing cooked neck colours.
Its output distinguishes an existing accepted correction, an effective nearest
palette, a bounded colour difference, an absent native row and a new cooked
review. It never stages a patch or treats an original measurement label as a
terminal reason. Source/profile/fingerprint and exact scope mismatches fail.

The continuation diagnoses 121 effective-nearest rows and 136 rows whose
measured gain from another native palette is below four Lab units. It retains
these rows and one protected policy. Those are colour-based retention
decisions, not proof of identical face/body shading on hardware. The 37 absent
rows retain their individual canonical/native-mask lookup evidence and remain
unfixed schema holds; adding or rekeying appearance records is outside the
existing-row patcher.

An additional 155 corrections were reviewed against actual cooked swatches
and own source atlases, including adjacent-palette cases that cannot reuse
the earlier source-only recommendation. One lower-neck sample intersected a
visible shirt graphic. Its separately bound anatomical upper-neck regions
exclude that graphic: source and cooked both select palette one, with a
maximum source/cooked distance below 1.59 Lab units. The four-unit provenance
bound remains unchanged; neither image payload nor mesh was modified.

The final v78 policy contains 436 corrections, including all 281 earlier
staged corrections. Every one of the 731 identities has a correction,
documented retention, or specific native-schema hold: 436 corrected, 258
retained and 37 held. Full scope diagnosis does not mean every mismatch is
fixed. Packaging compares the original and partial appearance tables, checks
exactly 436 permitted byte changes and 155 additional changes, and preserves
all other CPK members and every old-head appearance row. The complete face
PAK and ten protected v77 runtime files stay byte-identical. The other three
runtime files are the patched dt200, composed current manifest and measured
trophy marker. Twenty-four CPK overlay/native-validator checks and ZIP
CRC/member hashes remain separate from Switch boot, appearance or FPS tests.
