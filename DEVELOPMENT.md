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

## Wrapper version 0.1.65

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

## Open rendering issue

Gameplay is reached and UI/HUD rendering remains visible, but the main 3D scene
is black. Instrumentation has established that:

- draw calls continue and the renderer does not crash;
- vertex/geometry output is present;
- shader compilation and program linking succeed;
- offscreen FBO 8, backed by texture 85, contains valid rendered RGB output;
- the failure occurs after offscreen rendering, during the path that samples or
  composes that texture onto the default backbuffer.

The next investigation should trace the final fullscreen pass: framebuffer and
texture bindings, active texture unit, sampler uniform, viewport/scissor,
blend/color masks, texture completeness, and any format/swizzle behavior that
differs between Android Mesa expectations and Horizon Mesa.

The experimental shader-cache Mesa patch used during private diagnostics is
not required to describe or build the current public wrapper and is not
included here. It did not explain the black 3D compose result.

## Testing notes

- Use full-memory title override on hardware.
- Keep emulator-only patches and emulator build artifacts outside this repo.
- Re-run `scripts/check-public-tree.ps1` after every runtime-copy or diagnostic
  session before committing.
- A successful source build does not prove that a locally prepared runtime is
  complete; boot validation and hardware testing remain separate checks.
