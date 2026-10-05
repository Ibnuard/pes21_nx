# Pregame lineup / Hub regression (2026-10-05)

## Root cause

The reported Inter Miami substitution is a useful reproducer: the active local
roster places Yannick Bright at index 7 and Lionel Messi at index 21 (zero-based).
Native SquadData registers **18 member keys**, but its player vector can contain
up to 40 players. Unregistered reserves report `0xff` for both member and order.
Replacing a registered player with one of these reserves reuses the outgoing
member key; this is not an ordinary two-member order swap.

The previous wrapper commit synchronized an order swap only. The native squad
save helper copies formations/settings/reservations, not roster identities or
the order map. `UpdateTmpdbMatchTeamData` publishes coach/tactics data, not player
records. Consequently SquadData and the captured custom HUD identity could say
Messi while MatchSetup still imported Bright's complete native player payload.
This is independent of the default Day/Night stadium setting.

## Commit contract

- Before native match initialization, resolve each registered SquadData key to
  its player in the **same side's** Match roster, checking unique IDs, team
  membership, AdditionalData pointers, counts and one-to-one mappings.
- Permute the complete inline native `Match::PlayerData` values, not only the
  name/ID or the first Player copy. Preserve base/increased parameters, condition,
  appearance and per-member metadata together. Retain displaced reserves.
- Apply the same permutation to Team member IDs/shirt numbers and AdditionalData
  flags, rebinding each PlayerDataInfo pointer to its destination Match record.
- Publish the SquadData order map and initial match-order snapshot, then let the
  native save helper publish formations/settings. Repeat commits are idempotent.
- Validate/stage before writing. On a failed substitution commit, restore
  SquadData with its native deep-copy lifecycle, rather than accepting a UI-only
  edit. Never mutate CommonWork or another side, even for same-team matchups.
- Live substitutions retain the native reservation path; the pregame record
  permutation is explicitly disabled while that editor is active.

ABI scope is the supported Mobile v5.3.0 runtime. Native getters and exports were
inspected locally. Match PlayerData is an inline 0x380-byte value with no owning
pointers. These offsets are not a compatibility promise for other runtimes.
No proprietary binary/disassembly is included in this document or the tests.

Reopening Kits now reuses the prepared Game Plan. Late native Hub refreshes also
preserve it; changing a selected team already invalidates the prepared plan.
Preset files assign distinct file-only reserve orders above 17 and apply only
the native registered lineup, using the same validated replacement path.

## Hub rendering

Hub buttons were emitted frame/fill/gloss per button, but drawn as contiguous
frame, fill and gloss groups. This misapplied focus colors to neighboring buttons.
Emission now matches the draw ranges; each layer uses the same focus index.
The obsolete second red-label draw is removed; the shared button text theme owns
the only action-label draw.

## Verification

Host tests execute the production synchronization/replacement/save functions with
a synthetic 26-player, 18-member model. They cover outside-18 and registered-bench
swaps, reverse/multiple swaps, idempotence, full-payload/metadata preservation,
same-team side isolation, invalid identity/allocation rollback, and live exclusion.
Hub tests execute actual geometry/draw ranges for every focus in four/five-button
layouts at 720p and 1080p. Native export tests require the ignored local library.
No game or emulator is run by these checks.

Validation: 59 focused host tests passed, 2 optional local-fixture tests skipped.
The separate native export check passed for all 8 editor/commit bindings. The
diagnostic build used the installed Windows devkitPro toolchain after WSL's
source-copy operation stalled; no WSL restart or release-runtime replacement was
performed. Compilation succeeded with existing unused-helper warnings. The
native fallback uses the same full-loose flags and candidate asset overrides.

On 2026-10-05, the user confirmed that the diagnostic build fixed the reported
pregame substitution / Hub regression on Switch. This confirms the reported
reproducer, not every combination below. Retain the following regression matrix
for broader on-device coverage:

1. Inter Miami: Bright -> Messi before kickoff. Hub, Game Plan, native overhead
   name, actual actor and bottom HUD must agree.
2. Reopen Game Plan, Kits and General Settings, then kickoff. Repeat the swap and
   reverse it; test a reserve within the registered bench too.
3. Test HOME and AWAY independently (including same-team matchups), Exhibition,
   Cup and League. Check in-match substitutions remain native and functional.
4. Move across every Hub action: exactly one selected button, with matching frame,
   fill, gloss and dark label on yellow.

Diagnostic output is `local-debug/prematch-roster-sync-v3/pes21_nx.nro`, paired with
the existing full-loose manifest `e01100ff077bb275`. Only the NRO changes; CPKs,
dummy OBB and save files are not rebuilt or replaced. Keep the last working NRO
for recovery while broader on-device coverage continues.
