# PES21 NX open issues and design notes

Last reviewed: 2026-08-23, against the working tree after the controller
coverage pass following `775c77c`.

This file records confirmed runtime problems and design decisions that still
need implementation or hardware testing. It is not a claim that an item is
fixed merely because a hook or overlay already exists.

## Confirmed input and menu issues

- Half time is now treated as two native pages. `MatchResultTeamStats` owns the
  first statistics/Next preview and `MatchResultMainMenuHalfTime` owns the
  following tile menu. Both publish independent cursor heartbeats; A targets
  the native bottom-right Next footer. Every match phase still needs a manual
  Ryujinx/hardware pass.
- Pre-match and Pause Game Plan now use `MyClubSquadEdit` natively. Its real
  `UpdatePostControlWindow` vtable method owns the Game Plan cursor heartbeat,
  so the cursor follows either entry route and expires after the native page
  closes. The previous custom substitution/formation frontend is inactive.
- Goal celebration is detected before Replay from
  `GoalDemo::UpdateGoalDemo2DInfo`, with ownership supplied by native
  `GoalDemo::IsCpuGoal`. Player goals expose A Celebrate/B Skip; CPU goals
  expose only B Skip. Replay retains its separate any-button skip route. An
  opponent-goal runtime test remains required.
- Extra-time and penalty settings are reapplied at the final native
  `MatchSetupDataTmpdb` conversion and kept resident during gameplay, including
  half/extra-time tmpdb rebuilds. A full ET2 -> penalties test is still required.
- Goal-kick and corner contexts now observe the original native ThinkUnit
  vtable methods without replacing their return values. Goal Kick maps X Team
  Up/Y Camera; Corner maps Minus Kicker/Y Camera/X Short Corner. Helpers now
  use the native vertical button positions, and Left/Right emits the native
  kicker-selection swipe. A runtime corner stress test is still required.
- Foul/offside fixed-demo flow now enables the native skip gate and consumes a
  controller press through `FixDemoManager::Skip`; tutorial set-piece guides
  expose the native Play footer through the virtual cursor. Both need a match
  pass to confirm each game mode's timing.
- Gameplay -> GoalDemo/Goal Kick/Corner transitions now change the synthetic
  input generation. The first poll releases all old gameplay fingers before a
  contextual action can begin. This specifically contains the stale-pointer
  risk seen when the ball crossed the line for a corner, but the random freeze
  is not considered resolved until a repeated corner stress test passes.

## Requested simplified match UI

- The Exhibition -> Matchmaking -> Game Plan hand-off has returned to the
  complete native editor, including the game's own squad, formation and kit
  flows. A moves through native cursor clicks, B targets the native Back footer,
  and ZL/ZR remain alternate cursor-click buttons.
- Pause has returned to the native full-screen frontend. The AddIcon calls for
  Controls List, General Settings and Sound are disabled, leaving native Game
  Plan, Camera and Top Menu tiles. B calls `MatchPause::PadEventBack`; A clicks
  the virtual cursor.
- Camera selection maps Left/Right to the native
  `MatchPauseTouchCameraSetting::PadEventSwipeEnd`, so each change uses the
  original save and live registry-update path; B returns to Pause. A six-page
  fallback prevents the first swipe from being discarded while the registry
  vector is still being populated.
- The custom post-match overlay is disabled. Full-result tiles are removed;
  half-time's second page keeps only native Game Plan. B dispatches the native
  Top Menu event and A remains on the native Next footer. Final-result and
  half-time transitions still require a runtime pass.
- The custom Game Plan intentionally remains a frontend only. Native matchPlan
  owns squad data, substitution validation, formation/tactics data and commits.

## Newer eFootball asset research

- The file named `EFOOTBAL2024.xapk` is actually eFootball 11.0.0
  (`versionCode 311000001`) according to its embedded manifest.
- Its packaged data has been inventoried without importing anything. See
  `EFOOTBALL11_ASSET_AUDIT.md` for the concrete CPK/IoStore contents,
  compatibility findings and recommended experiments.

## Stadium camera tracking

- Stadium/Broadcast now preserves the native composition but corrects it to the
  live `BallInfo` position only when the ball is moving quickly and the stock
  group target trails by at least 12 field units. This is deliberately
  conservative and needs tests for keeper throws, rapid backwards switches and
  normal slow possession.

## Native controller route

- A native gameplay controller route really exists in the binary:
  `cobra::game::Pad`, `match::registry::PadInput`,
  `PadInput::SetRealPadKeyConfig`, `match::registry::KeyConfig`, and the native
  offense/defense command readers.
- PES21 NX already injects Switch HID into `cobra::game::Pad`, reconnects the
  mobile cursor to pad 0, and keeps real-pad slot 0 enabled for menu use.
- The earlier native gameplay experiment proved that HID reached Cobra pad
  state, but PES Mobile's match-action layer did not react reliably. Gameplay
  was therefore moved to calibrated synthetic touch.
- The remaining promising gap is the match-side KeyConfig/pad assignment and
  command-consumer state. Before replacing synthetic touch, build a diagnostic
  proof that pad 0 reaches `PadInputUnit::Update` and produces the expected
  offense/defense command output. Keep touch mapping as the fallback until
  movement, simultaneous actions, contextual defense, replay and pause all pass.
