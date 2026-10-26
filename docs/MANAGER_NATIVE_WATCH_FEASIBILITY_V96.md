# Manager League: native 3D watch feasibility v96

Genuine COM versus COM is a plausible next prototype, but this audit does not
establish a working spectator launch. The existing scheduled data broadcast
must remain the production path until native team ownership is demonstrated on
Switch. No experimental control, match-mode or replay hook is enabled here.

## What is established

The source already boots genuine 3D PES matches through
`main_menu_start_exhibition_match()` in `source/ue4_hooks.c`. Its
`MyClub/TutorialMatch` bootstrap supports selected teams, wrapper match settings,
native AI difficulty and native results. `main_menu_activate_league_fixture()`
shows the fixture-to-match-to-hub lifecycle. Manager Game Plan already supplies
account-scoped roster and strategy overrides, although those overrides currently
belong to the editor and need an explicit spectator owner before reuse.

`pes_cursor_set_pad_no()` binds HOME to physical pad 0 and leaves AWAY at -1 in
one-player matches. The adjacent `pes_set_real_pad_is_enable()` deliberately
keeps port 0 enabled outside the two-player mode. Merely hiding HUD helpers or
suppressing Joy-Con actions does not change either ownership rule. Leaving a
human cursor motionless is not a COM versus COM implementation.

The read-only native inspection used the locally supplied ARM64 `libUE4.so`,
SHA-256 `a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
No library was executed or modified. REA's existing target had no compatible
Windows ARM64 ELF analysis provider, so these follow-up observations come from
the repository's ELF/Capstone inspection tools, not a new REA decompilation or
device trace. Local symbol/call metadata is retained under the ignored
`local-debug/manager-review-v96/native-watch/` directory.

| Evidence | Observation | Limit |
| --- | --- | --- |
| `CursorData::SetPadNo`, 0x067fe8d4 | The stock setter stores 0 for pad 0 and -1 for other requests. The wrapper replaces this for accepted P1/P2 routes. | No proof that changing HOME alone selects every required AI consumer. |
| `input::TeamParameter::SetCoachMode` / `GetCoachMode`, 0x066b20e8 / 0x066b2a64; `onlinemode::UtilityCoach::IsCoachMode`, 0x06a9f1f0 | Native coach-mode accessors exist. | Their names are candidate entry points, not proof of an offline watch mode. |
| `MatchInfo::SetIsAutoMove` / `GetIsAutoMove`, 0x068081b8 / 0x0680895c | These small functions write/read one boolean at offset 0x1769. | Auto-move may be assistance/tutorial behavior; it is not an established full-team AI switch. |
| `TaskMatchSearchingWatching::ActConnecting`, 0x06a8dae4 | Static direct calls create an online match session and populate its observer users. | This native watch path requires additional session behavior; an isolated debug flag is insufficient evidence. |
| `TaskMatchSearchingWatching::ActDatasync`, 0x06a8df14 | Static direct calls create `TaskSyncManager` and set both native match user IDs. | No local fixture-to-stream replacement exists in the wrapper. |
| `TaskMatchWatchingManager::Action`, 0x06a93290 | Static direct calls register multiplayer commentary/player-selection receivers and receive a match-menu update. | This is an online session consumer, not a proven standalone recording player. |
| `RecordReplay`, `ReplayData`, `PlaybackController::InitPlayRecordPoint`, 0x07c9f85c | Native match recording/playback machinery exists. | Serialization, complete-match retention and arbitrary seeking are unproven. |
| `IsReplayRecordAllDebug`, 0x0680196c | Stock function returns false. | Ordinary goal replay cannot be assumed to contain a full ten-minute match. |
| `replaycnf::GetReplayDataFrame` / `GetReplayCnfSaveReplayTime`, 0x0683ccfc / 0x0683cd14 | Stock default values are 240 frames and 4 respectively. | The second value's call-site units and total buffer policy need further tracing; do not extrapolate full-match storage. |
| `math::Random::SetSeed`, 0x06842b68 | Writes one selected RNG stream seed. | A seed setter does not demonstrate deterministic AI/physics, all streams, loading state or timestep scheduling. |

## Bounded prototype route

1. Add a separate, opt-in native watch experiment using one fixed offline
   fixture. Reuse the accepted bootstrap and exact ABI guards; do not overload
   Exhibition or two-player state. Start at kickoff, at normal speed, without
   altering a saved season result.
2. Trace the native coach-mode conversion and AI/control setup, then establish
   both teams as CPU-owned before kickoff. Validate cursor membership, pad
   ownership and native command consumers together. Controller input remains
   available only for camera, pause and exit. If ownership cannot be established,
   abort to the hub rather than run an unresponsive human side.
3. Extend the Manager fixture adapter to stage immutable HOME/AWAY roster and
   strategy snapshots for this dedicated owner. Keep identity/portrait policy,
   per-account presets and engine player-count checks. Native substitutions and
   discipline must update the match snapshot, not silently mutate a different
   fixture or the active editable profile.
4. Confirm one complete match, both halves, goals, set pieces, substitutions,
   penalties where allowed, native audio and return to the correct Manager hub.
   Probe whether native AI works without an attached gameplay controller. Restore
   all input/audio/mode owners on every failure, exit and subsequent ordinary match.
5. Only then investigate full-match capture and seekable playback. First prove
   recording capacity, lifecycle, memory bounds and replay audio rules. Do not
   enlarge native replay buffers based on one constant or publish fabricated
   scores to reconcile different runs.

This route could produce a genuine 3D match to watch on one Switch. It does not
yet satisfy a precomputed, shared online fixture with late entry and full replay.

## Scheduled Live, precomputed results and replay

The current broadcast can reconstruct any timestamp from its saved tape. A
native match started from kickoff at 19:01 would initially be a minute behind a
19:00 fixture. A native clock write alone cannot reconstruct all 22 player
states, ball physics, fatigue, cards, substitutions, animations and RNG state.

Re-running COM versus COM separately on every client is not an acceptable
authoritative league result. Matching roster, settings and a seed has not been
shown to produce identical native outcomes. Writing the backend's score over a
different native match would also leave goals and events inconsistent.

The promising production direction is to run the authoritative match once and
distribute its validated native recording, or a supported complete state/event
stream with periodic snapshots. The client would play that captured match at
the scheduled timestamp. The native playback format and its portability must
be established first. Existing short goal replays do not prove this capability.
Recorded video is another architectural option for consistent images and late
entry, but it would need separate playback/bandwidth work and would not provide
interactive native camera control.

A VPS can own accounts, schedules, economy, sealed roster snapshots and results.
The current Switch/libnx wrapper is not a demonstrated headless VPS match
runner. A compatible native simulation worker or recording service is a
separate dependency. Increasing the data broadcast to two five-minute halves
does not establish that dependency.

During genuine native 3D play, the engine would become the audio owner; the
custom data-broadcast cues must stop. Live commentary audibility still requires
device verification. For replay, commentary must remain disabled while crowd
and ball sounds follow playback speed/seek policy. Neither native playback
symbols nor successful audio requests establish that all these behaviors work.

## Completion boundary

Answered: current wrapper ownership, useful native candidate paths, why native
online watching is not a one-flag offline unlock, and the required separation
between live simulation and authoritative captured playback.

Unresolved: a tested two-CPU launch, coach-mode consumers, full-match recording
format/capacity, deterministic native simulation, snapshot restoration, fast
seek, compatible VPS execution and device audio. No claim of production 3D
watching or full audit coverage is made.
