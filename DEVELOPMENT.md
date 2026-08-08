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

## Wrapper version 0.1.79

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
- direct entry to the main myClub menu from a preconfigured offline account
- title-specific software-keyboard JNI calls used by profile text input
- main PAK and patch/locale CPK discovery and mounting
- splash screens, menus, UI, HUD, and transition into gameplay
- visible, correctly oriented 3D gameplay through the fallback compositor
- custom Switch-HID-to-mobile-touch controls in the tested Ryujinx Classic
  layout, including simultaneous movement, Dash, and action input

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

## Custom controller handler

Ryujinx exposes a connected Bluetooth controller as Switch HID, but PES Mobile
does not route generic Android or native-pad events into its match-action
ThinkUnits. Version 0.1.78 therefore translates Switch HID into the same
multi-touch protocol consumed by the Classic mobile controls:

- left analog controls the virtual movement stick with a radial deadzone;
- Switch B holds/releases the Pass surface;
- Switch X holds/releases the Through surface;
- Switch Y holds/releases the Shoot or contextual Clear surface;
- Switch A performs a Pass-surface Cross swipe in offense mode and a dedicated
  Sliding swipe in defense mode;
- Switch R1 holds the Dash surface.

The fake Android motion event stores a complete immutable pointer snapshot.
It emits Android `DOWN`, indexed `POINTER_DOWN`, `MOVE`, indexed `POINTER_UP`,
and `UP` transitions, so the stick, Dash, an action button, and the physical
touchscreen can coexist. Synthetic pointer IDs stay within the game's accepted
0-9 range, and queue-full handling commits state only after the event has been
accepted to avoid stuck contacts.

A narrow UE4 hook records the current mobile offense/defense control mode. The
input shim requires a fresh, known gameplay mode before generating controller
touches, preventing stale contacts in menus, pauses, and mode transitions. The
older native Cobra pad bridge remains inert because enabling it changes the
mobile cursor route without feeding match gameplay.

Ryujinx runtime traces confirm left-stick movement, B, X, Y, offense A Cross,
R1 Dash, and simultaneous multi-pointer input. Defensive A Sliding is
implemented with a larger threshold-safe swipe but still needs broader runtime
and hardware coverage. Advanced controls and user-relocated mobile button
layouts are not supported by this coordinate-based handler yet.

## Testing notes

- Use full-memory title override on hardware.
- Keep emulator-only patches and emulator build artifacts outside this repo.
- Re-run `scripts/check-public-tree.ps1` after every runtime-copy or diagnostic
  session before committing.
- A successful source build does not prove that a locally prepared runtime is
  complete; boot validation and hardware testing remain separate checks.
