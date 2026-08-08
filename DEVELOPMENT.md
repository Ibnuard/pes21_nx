# Development progress

## Architecture

PES 2021 NX is a native compatibility wrapper, not an Android emulator. The
NRO reserves a region for the original arm64 ELF objects, maps and relocates
them, resolves Android/Bionic imports against libnx-backed shims, installs the
small set of title-specific hooks, creates a fake JNI/NativeActivity runtime,
and then transfers control to the original initialization path.

The public repository deliberately stops at that compatibility boundary. Game
binaries, data archives, extracted assets, offline response payloads, keys,
and local reverse-engineering output stay outside the repository.

## Wrapper version 0.1.77

The current compatibility target is the Nyan Mod Offline edition of PES 2021
Mobile v5.3.0 (`versionCode 305030001`, package `jp.nyan2021.pesam`). The
wrapper currently validates files from that specific revision and should not
be assumed compatible with other releases.

Working in the currently tested revision:

- devkitPro/libnx build on WSL Ubuntu
- ordered loading of the two support libraries and the UE4 library
- static import resolution for all three loaded ELF objects
- Bionic TLS, libc, pthread, filesystem, JNI, and NativeActivity shims
- EGL/GLES2 context creation and continuous swap/render loop
- touchscreen input in emulator and on hardware
- offline HTTP bootstrap, login, and registration flow
- main PAK and patch/locale CPK discovery and mounting
- splash screens, menus, UI, HUD, and transition into gameplay
- visible, correctly oriented 3D gameplay through the fallback compositor

## Runtime packaging findings

- The approximately 400 MB main OBB is a ZIP with one main PAK. The PAK is
  extracted into `PesMobile/Content/Paks/`; retaining the original main OBB is
  unnecessary for this wrapper.
- The approximately 1.5 GB patch OBB is a live CPK container. It must keep its
  original `.obb` filename and remain available to the runtime.
- Only the ten small locale CPK archives used by the tested build need to be
  present loose under `Download/`.
- Runtime validation currently checks the expected file set before executing
  the game libraries, making incomplete SD-card copies fail early.

These findings describe compatibility behavior only; none of the mentioned
archives are included in the source repository.

## Rendering fix

The gameplay scene was always rendered successfully into the offscreen color
target. The black output was isolated to the first fullscreen draw that should
compose that target onto the default framebuffer:

- framebuffer completeness, scene RGB data, shader compilation, and program
  linking were valid;
- a sentinel clear and immediate readback proved that the original compose
  draw generated zero covered fragments;
- the original fullscreen vertex/index state was therefore unsuitable on the
  tested runtime even though the fragment program and source texture were
  otherwise usable.

Version 0.1.77 detects that scene-compose transition and draws a replacement
fullscreen triangle from `gl_VertexID`. Its fragment path samples the captured
scene texture, applies linear-to-sRGB conversion, and flips the vertical UV to
match the default framebuffer orientation. The wrapper saves and restores the
affected GLES state so later UI rendering remains game-owned.

The experimental shader-cache Mesa patch used during earlier diagnostics is
not required and is not included in this repository.

## Controller investigation

Ryujinx exposes a connected Bluetooth controller as Switch HID, and the wrapper
observes both left-stick values and face-button transitions. Version 0.1.77
adds a radial-deadzone normalizer and publishes a coherent input snapshot on
the game thread. The requested positional PES mapping is:

- Switch B: short pass
- Switch X: through pass
- Switch Y: shoot
- Switch A: cross while attacking / sliding while defending

The snapshot is injected into `cobra::game::Pad`, including its normal
clicked/released/repeat generation. Diagnostics also found that the mobile
initializer marks the player cursor as having no real pad and disables real
pad slot 0, so narrow experimental hooks reopen those two gates when Switch HID
is connected.

Those changes prove the complete Ryujinx-to-native-pad path, but the mobile
match logic still does not reliably act on it. The remaining work is below the
generic Cobra/UE input layer: PES Mobile's touch-oriented movement/action
consumer must be bridged directly. Until that path is complete, controller
support remains experimental.

## Testing notes

- Use full-memory title override on hardware.
- Keep emulator-only patches and emulator build artifacts outside this repo.
- Re-run `scripts/check-public-tree.ps1` after every runtime-copy or diagnostic
  session before committing.
- A successful source build does not prove that a locally prepared runtime is
  complete; boot validation and hardware testing remain separate checks.
