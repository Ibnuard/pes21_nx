# Changelog

All notable changes to the public PES 2021 NX wrapper are recorded here.
Game files and changes made by the compatibility target are outside the scope
of this changelog.

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
