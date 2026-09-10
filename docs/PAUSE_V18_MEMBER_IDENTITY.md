# Pause Game Plan v18 — identity handoff

Status: diagnostic build; requires Switch hardware validation. Not a stable
checkpoint and not a replacement for the main `dist` package.

## Evidence and cause addressed

The supplied `local-debug/pause-console-v16-diagnostic/debug.log` shows both
selected squads hydrated before kickoff (Barcelona 108 and Madrid 109, 30/30
players each). Their portraits were successfully read, including HOME 141038
and AWAY 44383. After native Pause loading, HOME becomes `PLAYER 1` while AWAY
becomes `C. TRUSSARDI`; those are not the selected players.

Before-match uses `exhibition_refresh_squad_side_player_stats` to populate BOTH
NORMAL and INCREASED copies through native `UpdateMemberTmpdbPlayer`. Pause
reconstructs those copies through `LoadSquadDataFromMatchPlanData`, but previously
did not hydrate them again. The legacy name fallback just recycled synthetic
`PLAYER n` labels. Not resetting the custom UI was insufficient: refresh replaces
each UI entry from the reconstructed native squad anyway.

## Changes

- Capture authenticated `common::PlayerId` values and names by **side + MemberId**
  at MatchSetup, after restoring the final pre-Strategy squad and before disposing
  that deep copy. The separate identity map survives UI reset and is replaced for
  every new fixture. Reject incomplete/ambiguous sides and changed team IDs.
- Load the current live squad once (the native loader already loops both sides),
  then resolve each captured player through CommonWork and the existing native
  player-copy setter. Validate the returned ID before writing. Do not map by
  pitch order or vector index, and do not restore pre-match formations, stamina,
  eligibility, or substitution reservations.
- Remove the legacy fallback to synthetic UI names. Reset disposable custom UI
  state normally on entry; keep only the independent identity and PNG caches.
- PNG cache holds 80 distinct IDs, updates duplicate IDs in place, and evicts the
  least recently used identity when the fixture changes. Pause still
  cannot issue synchronous portrait file reads. Missing assets remain blank,
  rather than blocking the native UI thread.
- Arm the full-screen Pause cover before hiding Game Plan on Back. Ignore late
  updates of the closing native child until a fresh Game Plan request. On entry, publish
  custom Game Plan visibility before clearing the transition cover.
- No change to the working prematch loading reveal, OBB, kits, or scoreboard.

## Build and test

```powershell
.\build-wsl.ps1 -OutputDirectory local-debug/pause-console-v18-diagnostic -Diagnostics -Jobs 8
python -m unittest discover -s tests -p 'test_live_gameplan*.py' -v
python -m unittest discover -s tests -p 'test_pause*.py' -v
python -m unittest discover -s tests -p 'test_gameplan_editor.py' -v
python -m unittest discover -s tests -p 'test_runtime_obb_size_contract.py' -v
```

The host C harness executes the production capture/restore routines, including
two sides, 30-to-18-player native rebuild, reordered vectors, changed MemberId
after substitution, preservation of live-state sentinels, invalid members,
changed fixture, incomplete capture, duplicate members, and repeated PNG cache
refreshes. Native symbols/ABI were inspected in the existing local `libUE4.so`.
These checks do not substitute for running the NRO on Switch.

## Hardware handoff

Use `local-debug/pause-console-v18-diagnostic/pes21_nx.nro`, renamed as usual to
`pes21_nx.nro` on the SD card. Keep the current OBB (1,401,395,200 bytes); no asset
update is required. Fully restart the game so MatchSetup captures the identity
map; replacing the file while the previous process runs cannot populate it.

1. Start Barcelona vs Madrid (COM), then Pause → Game Plan. Check both sides'
   names, face images, and COM readiness.
2. Change formation/position and reserve a substitution. Back to Pause, resume,
   and reopen Game Plan. Check the same players stay attached to the correct
   slots and the native transition does not flash through.
3. Test a second fixture and two-human mode: no previous-fixture identities and
   independent controls/readiness. Do not promote to stable until these pass.

Useful diagnostic markers:

- `pause-v18: captured identity ... members=...` at kickoff;
- `pause-v18: identity ... member=... unique=... name=...` during Pause hydration;
- `pause-v18: restored identity ... members=.../... captured=...`;
- `pause-v18: ready ... players=... cachedFaces=... first=... portrait=...`.

Capture zero means the source snapshot/member mapping failed; restored zero with
successful capture means the live member mapping or CommonWork lookup failed.
Correct names/IDs with `cachedFaces=0` isolates the remaining problem to the
portrait handoff. A smaller live count than pre-match is not itself a failure:
the stock in-match squad can expose only its active/reserve match list.
