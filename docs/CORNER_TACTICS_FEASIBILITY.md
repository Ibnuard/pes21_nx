# Native corner tactics feasibility

Read-only investigation on 23 October 2026. The user asked whether FL26-style
corner attack/defence presets could be enabled in the compatible Mobile runtime.
No gameplay source, NRO, prepared runtime or assets archive was changed by
that read-only pass. The subsequently authorized implementation is documented
in [Corner presets v69](CORNER_TACTICS_V69.md).

## What the compatible Mobile ELF contains

Bounded ELF symbol/Capstone inspection follows actual function bodies and
their annotated PLT calls, rather than treating matching names as execution.
The inspected `libUE4.so` is the existing compatible local runtime, SHA-256
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.

| Native path | Static observation |
| --- | --- |
| `ThinkUnitCornerKickTactics::Main` | 600-byte input handler at `0x66a99c4`; reads native pad press/click state, has four normal and four short-corner choice branches, writes option and returns commands `0x6e`/`0x71`. |
| `Team::UpdateCornerKickTactics` | 824 bytes at `0x62a2358`; consumes those commands and converts their options into team corner/short-corner state. |
| `TeamFormation::AdjustCornerkickTactics` | Dispatches to actual Train, CrowdGK, LineGoalArea, Far and other formation-adjustment functions. |
| `ThinkUnitCornerKickDefenceType::Main` | 508 bytes at `0x66a9c2c`; three selection branches and command `0x6f`, with native camera-direction and input-timing handling. |
| `Team::UpdateCornerKickDefenceType` | 408 bytes at `0x62a2690`; checks match/local team ownership, consumes `0x6f`, calls `ConvertOption2DefenceType` and updates the team defence state. |
| `ThinkUnitFreeKickTactics::Main` | Separate 364-byte native input handler; free-kick routines are another plausible activation target. |

These are meaningful input-to-AI paths. They support a strong feasibility
finding, not a claim that every PC label, enum, movement and timing has already
been mapped or observed on Switch. Pressure during ordinary defending must
not automatically be identified with a corner-marking preset.

The current wrapper already identifies corner unit kind 70 and preserves it
when present in the native set-play list. Existing host routing fixtures cover
that preservation. The old September V1 report saying it was not scheduled is
historical; it must not be presented as the complete current diagnosis. The
corner Main wrapper presently publishes set-play context, while there is no
equivalent explicit defence-type UI bridge. A route debug bit alone does not
establish a working visible preset selector.

## Selected local FL26 UI comparison

The bounded owned `dt11_x64.cpk` member
`common/menu/general/game2d.bin` decodes to 623,318 bytes, SHA-256
`912a647bd428ded0b8fa6173373c2a7425069622e8e51547b3e0bb081cc994d3`.
It contains set-play display, separate left/right tactics/attack-defence-level
movies and quick member-change movies. A selected historical compatible
Mobile general-UI member instead has action-button/advantage/pause-slider UI;
only pause and radar movie names are common between these two inspected inputs.
This is a bounded resource comparison, not a complete current runtime UI audit.
An equal engine family does not make whole PC UI containers interchangeable.

The official PC manual provides useful target categories: four normal corners,
four short corners and three defensive marking presets. Its names include
Dash, 6-yard box, Train, Far Post and Mixed/Man-to-Man/Zonal. The accessible
reference is the [PES 2019 PC manual](https://dds.konami.com/games/manual/pes2019/PC/en/control_set.html);
this reference is not proof of exact FL26/PES21 option-to-label mapping.

## Implementation boundary

Use the existing Mobile command and team-AI paths, with FL26 as the presentation
reference. First validate exact choice mappings and native preconditions, then
expose a small context-owned selector for attack, short corner and defence.
Selection must belong to the correct HOME/AWAY controller and match generation,
preserve kick/aim/camera/taker controls, support camera/goal direction changes,
and reset on the actual restart end. Do not patch team memory directly merely
to make the displayed label change. Test selection against resulting native
team state and player movement for both single-player and local two-player.

Other evidenced candidates are free-kick routines, attack/defence level and
switching existing tactics presets: the Mobile input handlers and corresponding
PC UI resources are present. Their full feature activation remains separate.

Private static receipts, selected function hashes and resource comparisons are
under ignored `local-debug/corner-tactics-audit-v69/`. No REA native execution or
decompiler-provider result is claimed; prior provider limitations were retained.
No activation, PC behavioural parity, Switch playback or performance acceptance
has been established by this feasibility pass.
