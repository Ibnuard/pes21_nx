# Changelog

All notable changes to the public PES 2021 NX wrapper are recorded here.
Game files and changes made by the compatibility target are outside the scope
of this changelog.

## [0.1.94] - 2026-08-09

### Fixed

- Seeded the offline account consistently across Login, GetEntry, and SetEntry,
  pre-accepted the supported agreement flags, and bypassed only the obsolete
  season-change branch that reopened User Profile and legacy onboarding.
- Kept the mobile VirtualPad active for synthetic Switch-controller input while
  tinting its persistent stick and action clips to 2% alpha; added a compact
  attack/defense mapping legend that does not intercept gameplay touches.
- Replaced the title's unintended 5 FPS gameplay tick-rate request with a
  narrowly validated 30 FPS floor while preserving normal unlimited and
  already-valid frame-rate requests.
- Moved render-state tracking to native thread-local storage and enabled the
  release GLES state cache, reducing redundant wrapper calls and improving
  gameplay pacing, replay stability, and player-name flicker in Ryujinx.
- Made the Classic-control gamepad mapping possession-aware without changing
  the confirmed attacking controls. Defense now maps B to Press, A to Tackle,
  L1 to Switch, and R1 to Dash.
- Added a synthetic touch binding from Switch Plus to the in-match Pause
  button because the original mobile title has no usable native gamepad pause
  route.

### Added

- Added optional low-overhead timing instrumentation for swap, looper, sleep,
  and selected runtime paths. It is disabled in release builds and can be
  enabled explicitly for performance diagnostics.

### Verified

- Match gameplay no longer remains at the former fixed 5 FPS in the tested
  Ryujinx setup, and replay sequences can remain near 29-30 FPS.
- The latest release configuration reduces slow-motion and HUD/player-name
  flicker compared with the previous build.

### Known issues

- Active gameplay is improved but is not yet locked to 30 FPS in Ryujinx;
  camera load can still lower frame rate and produce some slow-motion or text
  flicker. Native Switch performance still requires hardware validation.
- The revised defense and Plus mappings are testable in this release but need
  a complete match validation before being marked hardware-verified.

## [0.1.93] - 2026-08-09

### Added

- Routed the eFootball main-menu action into a local Exhibition proof of
  concept using the title's normal matchmaking, Strategy, and match flows.
- Bound FC Barcelona and Madrid Chamartin B from the game's own master data,
  producing valid players, managers, kits, formations, and a playable CPU
  match instead of an empty myClub squad or immediate 3-0 forfeit.
- Added a public `runtime-template/` with `.DONOTDELETE` placeholders for all
  required, optional-mirror, and runtime-generated directories.
- Added a deterministic offline-response builder. It extracts the original
  fixtures from a user-supplied APK, applies the two existing-account
  overrides, generates all 48 encrypted payloads, and validates their sizes.
- Added a one-folder runtime preparer that automatically discovers the APK,
  both OBBs, and release NRO, then validates and atomically publishes a complete
  `switch/pes21_nx` SD-card directory with an install report.
- Added a project-owned minimal CRI UTF/CPK reader, removing the runtime
  preparation dependency on the unlicensed third-party CriPakTools binary.

### Verified

- A clean Ryujinx run entered Barcelona vs Madrid gameplay through eFootball,
  with visible 3D player models and the custom multi-touch controller handler.
- All generated offline payloads are byte-identical to the files used by the
  tested live runtime; proprietary APK/OBB/PAK/CPK data remains uncommitted.
- A fresh full preparation generated and hashed 64 required files; the ten
  extracted locale CPK archives matched the working runtime byte-for-byte.

## [0.1.79] - 2026-08-09

### Fixed

- Implemented the `jp/konami/SoftwareKeyboard` JNI contract used by profile
  text input, including class loading, show/completion state, and text return.
- Updated runtime response validation for the tested preconfigured-account
  payloads.
- Documented the offline entry-data distinction that prevents the client from
  reopening the User Profile, Team Select, and Signable Managers onboarding
  loop when a club and squad already exist.

### Working

- A clean Ryujinx boot reaches the main myClub menu without the unauthorized
  activity dialog or the initial-manager wizard.
- Squad Management opens the supplied 4-2-3-1 squad, and confirming it returns
  to the Match menu without a crash.

### Known issues

- Offline player cards and calculated squad values still depend on compatible
  locally supplied master data; incomplete data can show placeholder cards and
  zero Team Spirit or Team Strength.

## [0.1.78] - 2026-08-08

### Added

- Added a custom Android multi-touch controller handler for PES Mobile's
  touch-oriented match input instead of relying on unsupported native gamepad
  events.
- Added simultaneous synthetic touch contacts for the left stick, action
  buttons, and Dash while preserving the physical touchscreen contact.
- Added a narrow gameplay-context hook that enables synthetic contacts only in
  active offense or defense control modes.

### Controller mapping

- Left analog: player movement
- Switch B: short pass
- Switch X: through pass
- Switch Y: shoot / contextual clear action
- Switch A: Cross swipe while attacking / Sliding swipe while defending
- Switch R1: Dash / sprint

### Working

- Left-stick movement and simultaneous movement plus action/Dash input are
  confirmed in Ryujinx with a Bluetooth controller exposed as Switch HID.
- B, X, Y, offense A Cross, and R1 produce the expected independent Android
  pointer sequences in the tested Classic-control layout.
- Physical touchscreen input remains available alongside the synthetic
  controller contacts.

### Known issues

- The defensive A Sliding path is mode-aware and implemented, but still needs
  broader match testing across teams, camera/control settings, and hardware.
- Controller coordinates target the tested Classic mobile-control layout;
  Advanced controls and modified button layouts are not supported yet.
- The project remains tied to PES 2021 Mobile v5.3.0, version code
  `305030001`, and is not expected to support other revisions unchanged.

## [0.1.77] - 2026-08-08

### Fixed

- Replaced the failing mobile final compose draw with a GLES 3 fullscreen
  fallback that presents the completed offscreen gameplay scene.
- Applied linear-to-sRGB conversion in the fallback compositor and corrected
  the vertically inverted output.
- Kept the fallback isolated to the detected gameplay compose path while
  restoring the original GLES state after presentation.

### Added

- Focused framebuffer, shader, uniform-buffer, vertex/index-state, coverage,
  and pixel-readback diagnostics used to isolate the zero-fragment final pass.
- Switch HID polling with radial analog deadzone and positional face-button
  mapping for the requested PES controls.
- A game-thread bridge into `cobra::game::Pad` plus experimental mobile cursor
  and real-pad routing hooks.

### Working

- The 3D gameplay scene is visible and correctly oriented in the tested
  Ryujinx setup, alongside the existing UI/HUD and touch overlay.

### Known issues

- Controller events reach Switch HID and the native Cobra pad state, but PES
  Mobile's match-action layer still does not reliably react. Gamepad gameplay
  remains work in progress and is not advertised as supported.
- The project remains tied to PES 2021 Mobile v5.3.0, version code
  `305030001`, and is not expected to support other revisions unchanged.

## [0.1.65] - 2026-08-08

### Added

- Android arm64 ELF loading, relocation, and static import resolution
- Bionic, pthread, JNI, NativeActivity, filesystem, and asset-manager shims
- EGL/GLES2, OpenAL, touchscreen, networking, and runtime compatibility glue
- Early validation for the required locally supplied runtime file set
- WSL/devkitPro build helper and source-only public-tree audit
- GitHub Actions workflow for reproducible NRO releases

### Working

- Splash screens, menus, login/registration flow, UI, and HUD
- Offline HTTP bootstrap used by the tested Nyan Mod Offline v5.3.0 target
- Main PAK, patch OBB, and loose locale CPK mounting
- Transition from the menus into gameplay

### Known issues

- The gameplay 3D scene remains black during the final compose pass.
- The project is currently tied to PES 2021 Mobile v5.3.0, version code
  `305030001`, and is not expected to support other revisions unchanged.
