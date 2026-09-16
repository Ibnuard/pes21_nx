# Game Plan v3 — positional roles and Reset Default

User confirmed this version and requested commit/push after manual testing.
Production NRO: 46723277 bytes, SHA-256
`9e77ec1b453fc2eb2e86abdea3512a2f49c2f49dc6b1e9db39a38a386de31863`.
This records user acceptance, not an exhaustive hardware/controller test matrix.

NRO production: `local-debug/gameplan-zones-v3-production/pes21_nx.nro`.
Use the working 1401395200-byte England/Spain OBB unchanged. Keep checkpoint
Game Plan v2 as recovery. User acceptance is recorded above.

## Positional rules

Native coordinates run from own goal y=0 to opponent goal y=48; width x=0..105.
These are explicit custom-editor boundaries, not a claim of exact console rules.

| Zone | Bounds | Central roles | Additional wide roles |
| --- | --- | --- | --- |
| Defence | y 0–17 | CB | LB on left / RB on right |
| Midfield | y 18–35 | DMF, CMF, AMF | LMF on left / RMF on right |
| Attack | y 36–48 | SS, CF | LWF on left / RWF on right |

Left means x<30; right means x>75. A central attacker cannot cycle to CB, DMF
or a wing role with Y. Y keeps coordinates fixed. When dragging, a valid current
role is retained; an invalid role changes to a suitable role in the new zone.
The standard AMF preset at y=34 remains in midfield. GK stays GK and its drag is
bounded to the defensive zone. Outfield players never become GK.

Role and coordinates are stored in native formation data. Moving/changing a
role updates the live shape label to `CUSTOM D-M-F`. Preset selection clears
the custom flag for that tactic. The other tactics and opponent are independent.

## Reset Default

The final row in the shape popup is `RESET DEFAULT`. A applies it; B cancels.
It restores the complete initial native Formation for the current side/tactic,
captured before editing when that match's Game Plan first loads. It does not
replace the lineup, reset kits, change the opponent or reset the other tactic.
Starting a new Game Plan session after selecting teams captures a fresh baseline.
It is not a global roster reset or an undo of substitutions.

## Verification

The host editor suite tests each role against central/wide zones, exact 17/18
and 35/36 boundaries, AMF dragged into attack followed by release/refresh,
SS/CF cycling, custom shape, Reset Default and tactics/opponent isolation.
Existing drag, clamp, controller, preset, text and rating cases also run.

```powershell
python -m unittest discover -s tests -p test_gameplan_editor.py
.\build-wsl.ps1 -OutputDirectory local-debug/gameplan-zones-v3-production -Jobs 8
```

Manual test: drag an AMF forward to central attack, release and press Y several
times (only SS/CF). Drag back into midfield and defence, then test left/right
flanks. Check the CUSTOM shape after re-entering Game Plan, apply Reset Default,
and verify the other tactics/side plus substitutions are unchanged. Finish with
kickoff, pause and goal celebration using the existing OBB.
