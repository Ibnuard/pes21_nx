# Referee kickoff publication v62

The v61 device report still showed the optional referee outside the requested
centre-circle position after an opponent goal, then moving during the whistle.
The source reproduced a premature release of the kickoff stance: a completed
native warp armed placement, but its next draw could still read the old
goal-end ball. The previous code treated warp acknowledgement as though a
centre-ball snapshot had already been observed. That distant sample released
the stance and could select the ordinary return-from-replay destination.
This is a source-confirmed failure path consistent with the report; it is not
a new trace of the Switch event sequence.

## Native evidence and contract

The inspected compatible Mobile ELF is the ignored local
`dist/pes21_nx/libUE4.so`, SHA-256
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
REA reported that its Ghidra provider was not configured. The following are
bounded local ELF/symbol/Capstone observations, without native execution or
REA decompiler Evidence. Temporary inspection output used ignored
`local-debug/match-recovery-v62/referee/` and was removed after the findings
and repeatable optional checks were recorded here.

- `Flow::InitHalfStartFlow` at `0x62017d8` and `InitKickOffFlow` at `0x620233c`
  set FlowKind 2 and 3 respectively. `ExecTask` calls `ExecPositionWarp` through
  the existing hooked PLT. `ExecPositionWarp` at `0x61fb150` waits for the
  native acknowledgement at `MatchInfo+0x1194` to equal 20. It does not clear
  FlowKind, so reading the kind after its successful return was not the bug.
- `GlobalRegistry::OpenRead` at `0x67e2a8c` borrows the MatchInfo read snapshot
  into registry `+0x4f0`. `ExecWaitInPlay` reads its status at `+0x116c` and
  restart kind at `+0x1514`.
- `GetMatchStatusString` and its table identify 0 as NONE, 1 as IN_PLAY, 2 as
  OUT_OF_PLAY and 3 as SET_PLAY. `ToInPlay` at `0x62004cc` tests restart kind
  1, KICK_OFF, before setting status 1. The out-of-play reason table identifies
  3 as GOAL. Native warp acknowledgement and the subsequent borrowed ball
  snapshot therefore must not be treated as the same observation.

The optional reader validates eight relevant instructions in writable ELF
backing before executable mapping. It retains no MatchInfo or registry
pointer. A missing owner, unknown status/restart value or layout mismatch
leaves the established ball-based fallback available.

## Placement and release

An acknowledged kickoff request remains pending through replay, pause and
interval presentation owners. The first live publisher consumes it, clears
the prior movement/animation clocks and consumes the current OutOfPlay event
serial. It publishes the full pose and transform at `(0, 0, 9.15)` before
showing the optional actor. This remains the user's presentation position,
independent of which side scored or which goal end was used.

While native status is OUT_OF_PLAY or SET_PLAY with restart KICK_OFF, an old
goal-end ball sample cannot release the stance. Native IN_PLAY allows the
existing ball-departure release, including a fast pass for which no centre
sample was drawn. The native motion bank's measured mouth-contact interval
still keeps a contemporaneous whistle planted. Native audio is forwarded once.
No elapsed-time teleport, extra native hook or additional actor is introduced.

The approved native v4 animation bank and its payload remain unchanged. The
two translated FL26 live-target constraints and the ordinary movement policy
also remain unchanged. This correction does not establish complete PC AI.

## Assistant referee status

The earlier [presentation note](REFEREE_PRESENTATION_V57.md) correctly treats
assistant implementation as an integration gap, not missing appearance data.
This bounded recheck confirms:

| Evidence | What it establishes | Remaining work |
|---|---|---|
| `FixDemoManager::HumanList::AddReferee` at `0x7b808bc` | Native demo requests allocate official indices starting at `0x100` and carry referee-kind data. | Map live slots and ownership without borrowing a demo or player actor. |
| `FixDemoManager::CreateHumanReferee` at `0x7b86d7c` | Demo officials use `CreateLoadId` and native HumanKind Referee (2). | Establish live loading, uniforms, own bone buffers and scene teardown for two additional renderers. |
| `draw::Human::SetAssistantRefereeProp` at `0x7b23ed4` | The setter stores a property byte at `+0x60` and dispatches a virtual update. | Verify the flag model, attachment, visibility and animation contract through the renderer/resource path; the setter alone does not establish them. |
| `LinesmanMove` and `LinesmanAction` Execute/UpdateAnimeInfo | All four inspected exports consist of a single return instruction. | Supply and validate live positioning, side/direction, offside/ball-out signals and motion selection. |
| PC `RefereeLinesman` class from the [FL26 audit](REFEREE_PC_TARGET_AUDIT_V54.md) | PC has a distinct assistant controller. | Recover its relevant behavior and independently map Mobile inputs and lifetime; a vtable is not a working Mobile controller. |

Two live assistants are not implemented or enabled by this change. Their
device rendering cost and visual behavior also remain unmeasured.

## Verification and remaining device check

The focused run passes **14 tests and 89 subtests**:

```powershell
python -B -m pytest tests/test_referee_kickoff_v62.py `
  tests/test_scene_canaries.py tests/test_referee_native_contract.py `
  tests/test_referee_pc_policy.py tests/test_referee_presentation_policy.py `
  tests/test_referee_offside_presentation.py tests/test_referee_projection.py -q
```

The new tests execute the actual include and publisher against the bounded
native-model fixture. They cover both scoring sides, both goal ends, both
stopped native statuses, warp before model load, stale goal-ball publication,
replay/pause/interval before consumption, replay and unavailable registry
after consumption, repeated upload callbacks, event serial consumption,
whistle contact, native IN_PLAY release without any centre sample, fallback
for missing/invalid status, unchanged players and reused actor lifetime. Each
new instruction guard is rejected independently when changed or missing; an
optional local ELF check verifies the actual instructions, status names and
four assistant stubs.

The source correction and assistant evidence questions are answered within
that boundary. Switch verification remains open: repeat initial kickoff,
goals by both teams at both ends, goal replay/skip, halftime, rematch and a
fast first pass. Confirm the requested point and planted whistle against the
device image. Host checks do not establish successful device presentation or
frame-rate acceptance. No build, package or active runtime replacement was
performed by this scoped investigation.
