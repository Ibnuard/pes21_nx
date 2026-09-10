# Pause v10 diagnostic candidate

Includes the v9 lifecycle changes, plus the requested console-style layout.
Not a stable checkpoint; test manually on hardware, no emulator verification.

- Native Pause window surface alpha is zeroed after native Update, not before.
  Its separate team/score header remains native and retains the actual score.
- GuiBarWindow post-update hides Back via alpha during custom Pause/live Game
  Plan, and restores it after leaving. No native events are disabled.
- Team-info duplicates move outward; their teamName children move inward/up;
  userName (Special Team) is hidden. Coordinates derive from the native team-card
  separation, with a range guard. Diagnostic logs report layout hook installation
  and whether the header could be repositioned.
- The opaque lower-screen cover is removed. Stats use a rounded box at 26.5%
  screen height, 46.5% height and 76% opacity. Three horizontal buttons and the
  controller helper remain below it. No extra dimming is added over the header.

Use the existing scoreboard-square-v2 OBB unchanged. Check Pause appearance,
navigation, Camera and Back restoration, live custom Game Plan for P1/2P, and
prematch visibility. If any native elements remain, send debug.log and a picture.
`pause-v9:` logs trace editor/loading; `pause-v10:` logs trace layout hooks.
