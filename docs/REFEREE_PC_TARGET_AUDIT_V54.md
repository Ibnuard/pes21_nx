# FL26 referee target audit

This follow-up to [the animation audit](REFEREE_FL26_AUDIT_V53.md) inspects
the owned PC executable to establish which movement rules can be translated.
The PC game was not started. These are bounded static/parser observations,
not a device trace or REA runtime Evidence. The previously established native
provider limitation remains; no disassembler provider was installed.

## Target and active configuration

The local `FL_2026.exe` is a 458,910,720-byte x86-64 PE, SHA-256
`7c27ecb303b71331e36f9ccd8ac879f0f0d8c56c754bd4d0d2e9c8353464f847`.
Its image base is `0x140000000`. Addresses below are RVAs. The active
`SiderAddons/sider.ini` identifies that executable. It enables the referee kit
module, with one live CPK root; the enabled referee Lua module contains kit
selection and file redirection. It supplies no movement controller.

The `Data/dt18_all.cpk` TOC has ten members, including match/player/stadium
constant archives and position data. Their presence does not identify a
standalone referee movement configuration. No copying of those archives is
needed for the narrow target constraints below.

## Actual PC controller

PE RTTI and complete-object-locator references identify these vtables:

| Native class | Vtable RVA |
|---|---:|
| `match::referee::Referee` | `0x2641e78` |
| `match::referee::RefereeChief` | `0x26420f0` |
| `match::referee::RefereeLinesman` | `0x2642348` |
| `match::referee::RefereeActionBasePosition` | `0x2642558` |
| `match::referee::RefereeActionOutofPlay` | `0x2642738` |

The Chief override at `0xa383a0` calls the live target routine `0xa37910`
when MatchInfo's phase field at `+0x116c` is 1. A separate dispatcher at
`0xa38c40` uses restart kind `+0x1554` to select restart-specific routines.
This is concrete evidence of separate live and restart positioning.

The live target routine is 2,632 bytes, with dependencies on ball history,
player action state/timing, team direction, field geometry and trajectory
helpers. It includes angular avoidance/projection paths. Its entire behavior
cannot be replaced by a ball follower or established by the motion bank.
Several restart routines redirect into obfuscated executable regions; those
branches were not fully recovered in this bounded audit.

## Translated constraints

Two self-contained constraints can be translated without PC pointers or ABI
assumptions. `source/referee_pc_policy.h` implements their arithmetic using
semantic field inputs:

1. At `0xa37de6..0xa37e21`, limit the target X magnitude to
   `FieldInfo[0x18] - 3`.
2. After the subsequent target-Z selection, at `0xa382a0..0xa38302`, compute
   `diagonalZ = FieldInfo[0x1c] -
   ((FieldInfo[0x18] + targetX) * FieldInfo[0x1c] / FieldInfo[0x18])`.
   Limit target Z to `diagonalZ +/- FieldInfo[0x04]`.

The second calculation uses the already bounded target X. The source keeps
the observed operation order rather than reducing it algebraically. It
constrains a target around a diagonal; it does not force the referee onto the
center of that diagonal. Movement speed, acceleration, turn rate, smoothing,
player separation and the complex trajectory branches are separate behavior.

The immediately preceding Z-selection block at `0xa37e21..0xa37e93` starts
with the base Z position. If its magnitude exceeds `0.4 * FieldInfo[0x04]`,
it shifts 15 metres toward the centre. Otherwise it shifts 15 metres toward
the side on which the current referee is standing relative to that base
position (a zero difference chooses the positive side). A negative action
angle then skips the trajectory/projection blocks and goes directly to the
final diagonal constraint. A nonnegative action angle takes additional
branches. The wrapper has no verified equivalent of that PC action-angle
selection; the narrow target helper therefore does not apply the Z-selection
block as if it covered every live action.

Field offsets must not be mistaken for pitch half-length/half-width. The
compatible Mobile `match::registry::FieldInfo` constructor at `0x6802264`
copies 72 bytes from RVA `0x81cae90`. Its observed defaults include:

| Offset | Value (metres) | Geometric interpretation |
|---|---:|---|
| `+0x00` | 52.56 | Pitch half-length |
| `+0x04` | 34.06 | Pitch half-width |
| `+0x10` | 47.06 | Goal-area X line |
| `+0x14` | 9.16 | Goal-area half-width |
| `+0x18` | 36.14 | Penalty-area X line |
| `+0x1c` | 20.12 | Penalty-area half-width |

The interpretations follow the geometry and are corroborated by the native
penalty-position helpers. These are **Mobile defaults**, not observed PC live
values. PC geometry defaults were not established. The translated function
therefore accepts a validated live geometry snapshot and embeds no guessed PC
dimensions. Invalid inputs leave the caller's target unchanged.

The PC kickoff-specific target routine `0xa38a00`, selected for restart kind
1, uses `(-5 * direction, 0, -10 * direction)`. The signed direction is read
from TeamInfo `+0x254` for the restart team `MatchInfo+0x1558`. This formula
is documented for further integration; translating it requires independently
verified Mobile direction ownership and is not implied by the target helper.

## Coverage and verification

The translated helper is a partial PC movement rule. It does not establish
identical PC AI, collision behavior, card behavior or foul decisions. Those
claims require further call-site/state mapping and device comparisons.

The synthetic host test covers midfield stability, movement away from both
goal ends, diagonal symmetry, alternate geometry, repeat application and
invalid/missing snapshots. Run it with:

```powershell
python -B -m pytest tests/test_referee_pc_policy.py -q
```

Only project-authored source, tests and this concise finding ledger belong in
the public tree. The local executable, CPK metadata reports and native
disassembly remain ignored under `local-debug/referee-pc-v54/`.
