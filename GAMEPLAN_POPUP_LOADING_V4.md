# Game Plan popup / kickoff loading v4

## Scope

- Rounded Auto Line Up, formation and position-picker popup backgrounds.
- Formation title and current-shape subtitle centered; five visible rows.
- Up/down (or left/right) moves focus and scrolls the window. All ten presets
  and Reset Default remain reachable. The applied preset is blue independently
  of keyboard focus; a custom shape does not falsely highlight a preset.
- VS loading now includes the animated bottom-right spinner.
- MatchSetup no longer dismisses the VS cover. An enabled native DemoSkip unit
  reveals the cinematic; a live offense/defense ScreenTap callback is the
  fallback when entrance cinematics are absent. No timer, asset replacement,
  match rules, celebration or pause-menu logic is changed.

## Build / manual acceptance

Build production with `build-wsl.ps1 -OutputDirectory
local-debug/gameplan-popup-loading-v4-production -Jobs 8` (no Diagnostics flag).
Use the existing stable eng-spa-all-kits-v3 OBB, unchanged.

Host tests cover editor behavior, scroll bounds and applied-versus-focused
selection. They cannot establish the timing of native callbacks on hardware.
Before marking stable, manually verify:

1. Both sides: rounded Auto Line Up and centered, compact formation popup.
2. Scroll through every preset to Reset Default and wrap back; blue text tracks
   the applied shape, not focus. Apply/reset and reopen the popup.
3. Kick Off: VS/spinner covers the native tips and clears for the entrance.
4. Repeat a match and try skipping the entrance: no retained loading cover.
5. Gameplay, goal celebration and pause remain normal.

Custom pause and result layouts are feasible via existing native pause/result
hooks, but are deliberately outside this change. Preserve native state/actions
and expose only validated score/stat fields when implementing their overlays.
