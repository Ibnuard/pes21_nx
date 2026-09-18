# PES21 NX open issues and design notes

Last reviewed: 2026-09-18, against the V12 native Stadium-target candidate
after the full mobile kit migration.

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
- Goal celebration uses the stable `ThinkUnitInteractiveGoalDemo::Main` and
  `ButtonGoalPerformance` heartbeats; the crash-prone
  `GoalDemo::UpdateGoalDemo2DInfo` trampoline remains disabled. Ownership comes
  from native `GoalSide`, with a separate own-goal latch. Player goals expose A
  Celebrate/B Skip; CPU and own goals expose only B Skip. Replay retains its
  separate any-button skip route. All ownership cases still need a hardware
  pass.
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
- ButtonSetplay visibility is now gated by the native `NeedDisp` result rather
  than a half-second owner grace. This removes the stale goal-kick helper flash
  after the keeper enters the kick animation. Ordinary long free kicks expose
  only Set Piece Taker; offside restarts are identified from native `FoulKind`
  and intentionally expose no helper. Both restart variants need hardware
  confirmation. V11 additionally suppresses all gameplay helper families
  during pause/loading ownership and prioritizes a fresh free-kick heartbeat
  over ambiguous PositionShift bits. Goal-kick -> pause submenu transitions
  still need hardware verification.

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

- V12 removes Stadium's post-target soft clamp and selects the calculator's
  existing live-ball branch before group/predicted-receive composition. Scope
  remains selected Stadium (tmpdb 12), live CAMERA_ID 6, same native Update and
  movement readiness. Final pose and downstream tracing remain native; the
  ball-only branch supplies its own native zoom input instead of group framing.
  Shared future-vector/speed-cap and trace routines remain untouched. Keeper
  throw/counter-pass/midfield stopping behavior still needs device validation.
- V11 restores fixed `FOOTBALLNX CAM`, without sliders, alongside Dynamic Wide
  (default), Stadium, Medium, Long and Wide. It retains Wide's native smoothed
  target. V11's eagle-eye framing was rejected; V12 reduces the eye to roughly
  native Stadium height and tightens field coverage, retaining continuous lens
  compensation for the near touchline. This is not a pixel-identical Stadium pose;
  far/near framing and tracking need hardware acceptance. The selected allowed
  preset survives rematch bootstrap.
- The user confirms stable Day 60 FPS with V11, but rejects its shadow shape.
  V12 retains roof always OFF/no toggle and zero Day CSM cascades, replacing
  the forced Night board with each time's own native low-quality ShadowBoard.
  Real Day lighting and custom pitch remain unchanged. Native CVar originals
  are restored for Night/Top Menu. Shadow appearance and performance of this
  revised combination remain unverified; no Night-only fallback is forced.
- The user narrowed frame glitching to **Game Speed** changes. V7 removes the
  wrapper's immediate and per-frame simulation-FPS forcing, leaving the
  native MatchMain timing handoff. Before-kickoff, resume and all five speeds
  need hardware validation; not every General Settings action is implicated.
- V7 synchronizes both tmpdb's timezone rule and the renderer InitParam copy,
  and retains Hub COM/rules across bootstrap. Night/Legend -> Top Menu -> new
  match needs verification. See `STADIUM_ROOF_CAMERA.md` for the current V12
  shadow policy, historical evidence and hardware test steps.
- Radar now starts `OFF` in each exhibition match, matching the mobile screen's
  actual initial state. It can still be enabled from General Settings.
- V8 hides the bugged native stamina gauges unconditionally and removes SHOW
  STAMINA from General Settings; stamina gameplay is unchanged. A new Night
  capture still identifies V6, with about 41 FPS across two matches, including
  slow gameplay before the first pause. It cannot isolate the cost of a stamina
  toggle and does not validate V7's speed-ownership fix. V8 adds action-level
  `[SETTINGS]` events for the next performance comparison; hardware pending.

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
