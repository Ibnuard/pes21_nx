# New-fixture Game Plan lifecycle v66

Subsequent device feedback confirmed the bench failure still occurs after
v66. The lifecycle correction below is retained, but is not a resolved-device
claim. See [the later bench-edit boundary](BENCH_EDIT_BOUNDARY_V67.md).

The reported failure is a starter/bench replacement from the new Exhibition
hub after Rematch or Select Team. Moving positions still works, and the user
has demonstrated a working goalkeeper replacement on a fresh match.

The custom hub loaded squads into reused native owners without reproducing
the native pre-match initialization. The compatible owned ELF establishes:

- `MyClubFlowMatchMenu::Main` resolves the local side, calls
  `UtilityMyClubSquadEdit::SetSquadMode(11, side)`, then loads squads. That
  utility calls `SquadEdit::Init`, sets the mode and sets the owner. Init
  clears the reused squads and obsolete native move/overlap selection state.
- `Data::SetupDataFromTmpdbMatch` populates the existing plan. It can retain
  earlier `PlayerDataInfo` eligibility and leaving flags, and does not clear
  substitution history. `LoadSquadDataFromMatchPlanData` transfers that
  history into the reconstructed squads.
- `AdditionalDataInfo::Init` alone does not initialize either its six change
  records or its forty player-info records. Its constructor initializes both
  inline arrays before calling Init. These records contain inline metadata
  and borrowed player references, without an owning allocation to release.
- `Data::ResetDataForRematch` restores formation/settings data; it does not
  replace this complete new-fixture initialization.

V66 initializes both `CommonDataInfo` values and reconstructs both
`AdditionalDataInfo` values through their native methods before the first
setup/load of a fixture. It uses the native pre-match mode utility with HOME,
whose local user binding remains checked immediately before conversion.
This runs only while `exhibition_plan_ready` is false. Reopening the prepared
Game Plan and rebasing an edited plan retain their state. The live Pause
loader, reservation limits, consumed substitutions and player identity
hydration are unchanged. A live editor owner refuses new-fixture reset.

Starter/bench replacement still uses native replacement followed by the
existing full-record identity/permutation checks and rollback. New release
journal stages distinguish missing swap bindings, invalid registration and
a native replacement that failed to change the requested orders. The v65
native team-key conversion and two-sided publication gates remain in force.
There is no CanReserved/CanSwap override.

The new host regression reuses dirty plan and editor objects through three
fixtures. Its setup model deliberately preserves existing eligibility and
history like the inspected native setup, rather than returning clean state.
It executes production initialization, preparation, starter/reserve and
goalkeeper replacements, complete record transfers and identity gates. It
also verifies no reset on a prepared-plan reopen, refusal during live editing
and refusal when a native initializer binding is unavailable.

The optional owned-ELF oracle pins SHA-256
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
It decodes the actual pre-match mode route and the constructor's complete
six-change/forty-player argument sequence, then interprets the real leaf
initializer instructions on dirty synthetic memory. It retains no game
bytes. Missing local ELF/Capstone dependencies produce explicit skips.
REA's native decompiler providers were unavailable; symbol, segment and
Capstone inspection supplied the static evidence. Private receipts are under
ignored `local-debug/match-review-v66/bench/`.

Static native evidence proves the omitted lifecycle and retained state. Host
regressions prove the wrapper now initializes it and preserves its existing
publication policy. Neither proves which retained field caused the observed
device failure, or that the complete Switch sequence now succeeds.

Device acceptance remains: fresh Exhibition -> pre-match bench replacement
-> complete match -> Rematch -> new pre-match replacement -> complete match
-> Select Team -> another fixture -> pre-match replacement. Reopen the same
Game Plan to check edits persist, start the match to check actor identity,
then verify Pause substitution reservation/limits and undo still work. Both
controller modes need coverage. Retain the scene journal if a swap fails;
the new-fixture marker begins `v66 new fixture`, and rejection notes identify
the registration, native replacement or full publication stage.
