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
