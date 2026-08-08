# Changelog

All notable changes to the public PES 2021 NX wrapper are recorded here.
Game files and changes made by the compatibility target are outside the scope
of this changelog.

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
