# Custom Game Plan / club stars — v2

## Checkpoint — 2026-09-09

User confirmed this build with "mantaps" and requested a checkpoint, commit,
and push. Recorded as `gameplan-editor-v2-user-confirmed`; this does not imply
every club/controller configuration was exhaustively tested.

Production NRO: 46719181 bytes, SHA-256
`5299ee3f52e6cb7a4abcc6584dcec473946b14b1058bff3508113ba03a1ff04d`.
Checkpoint metadata: `data/checkpoints/gameplan-editor-v2.json`.
The binary remains at its local output path; dist/recovery is not overwritten.

## Scope

Production NRO output: `local-debug/gameplan-editor-v2-production/pes21_nx.nro`.
Use the existing working England/Spain kits OBB (1401395200 bytes). No OBB,
kit, logo, player rating, or roster data is changed by this revision.
User acceptance is recorded above; host tests do not emulate the complete game.

## Drag persistence: verified native cause

The previous editor called `tmpdb::SquadData::SetFormation`, then updated local
preview coordinates. In the user-owned runtime:

- `SquadData::SetFormation` at `0x06d2f9ac` forwards to SquadGameplan.
- `SquadGameplan::SetFormation` at `0x06d2f1e0` copies **roles only**, not positions.
- `SquadData::GetFormation` at `0x06d2f91c` copies the base Formation at
  `squad + 0x1cc + tactics * 0x90`, then overlays SquadGameplan roles.
- `SaveSquadDataToMatchPlanData` at `0x07d796e0` calls GetFormation for both
  tactics and writes those complete values to match-plan data.

Therefore a release/save/refresh read the old coordinates. The v2 store helper
uses native `Formation::operator=` to update the owning base Formation and
then calls the role setter. Drag, presets, role changes and field swaps share
this helper. The write is per squad side and tactics; it does not replace a
global team/coach formation, including when both opponents use the same club.

This offset is specific to the audited PES21 library, not a portable tmpdb ABI.
Re-audit GetFormation and the 144-byte Formation size before changing runtime
libraries. Local disassemblies: `local-debug/gameplan-position-api.txt` and
`local-debug/gameplan-fix-native-audit.txt`.

The host stub previously modeled SetFormation as a full copy, concealing this
bug. It now models the roles-only setter and the separate base-formation store.

## UI and rating changes

- Shape Preset: A opens a 10-option list; directional input selects; A applies;
  B cancels without changing the current formation. Left/right quick cycling on
  the settings row is retained. HOME/COM picker state is independent.
- Names: fixed integer-pixel font height, 20px at 720p instead of 15px. Focused
  long names retain the clipped scrolling behavior; names never shrink to fit.
- Helper text: contrast panel below the actions, inset alignment, larger primary
  hint, and a separate move/release/role hint on the field-edit page.
- Stars: use a custom monotonic curve for the rounded mean of visible FW/MF/DF,
  not the native curve intended for its own full-squad overall. This changes only
  the displayed stars, not FW/MF/DF values or player abilities.

| Visible mean | Stars |
| --- | --- |
| below 52 | 1 |
| 52–56 | 1.5 |
| 57–61 | 2 |
| 62–66 | 2.5 |
| 67–72 | 3 |
| 73–79 | 3.5 |
| 80–82 | 4 |
| 83–87 | 4.5 |
| 88+ | 5 |

Screenshot examples: Rayo 70/68/65 and Girona 74/66/67 become 3 stars;
Oviedo 64/64/63 becomes 2.5; Manchester United 84/83/81 remains 4.5.
This is an explicit UI calibration, not a claim about official PES console grades.

## Verification and manual acceptance

```powershell
python -m unittest discover -s tests -p test_gameplan_editor.py
python -m unittest discover -s tests -p test_gameplan_native_symbols.py
.\build-wsl.ps1 -OutputDirectory local-debug/gameplan-editor-v2-production -Jobs 8
```

Host tests cover drag/release/re-read, tactics/opponent isolation, clamping,
edge-trigger input, player-role edits, all 10 presets, picker cancel/apply,
horizontal Joy-Con mapping, text clipping and monotonic rating thresholds.
Native-export test checks the actual library's defined symbols.

On hardware: move a player, release A, enter/exit another page, then reopen Game
Plan; check the saved position. Switch attacking/defensive and test the other
side. Open preset list, cancel, then apply a different shape; verify kickoff
uses it. Check text on handheld and the example stars above. Keep the previously
working NRO as recovery until these flows have been exercised.
