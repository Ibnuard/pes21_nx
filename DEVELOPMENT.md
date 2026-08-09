# Development progress

## Architecture

PES 2021 NX is a native compatibility wrapper, not an Android emulator. The
NRO reserves a region for the original arm64 ELF objects, maps and relocates
them, resolves Android/Bionic imports against libnx-backed shims, installs the
small set of title-specific hooks, creates a fake JNI/NativeActivity runtime,
and then transfers control to the original initialization path.

The public repository deliberately stops at that compatibility boundary. Game
binaries, data archives, extracted assets, generated offline response
payloads, private keys, and local reverse-engineering output stay outside the
repository. Project-authored response transformations and an empty runtime
directory template are included so a legally supplied target can be prepared
reproducibly.

## Wrapper version 0.1.93

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
- eFootball-to-Exhibition routing with master-data FC Barcelona and Madrid
  squads, a valid Strategy screen, and a playable local CPU match
- reproducible generation of the exact 48 offline HTTP payloads from a
  user-supplied compatible APK
- a one-folder runtime preparer that discovers the APK, both OBBs, and release
  NRO, with an independently implemented minimal CPK table reader for the ten
  required locale archives

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
- `runtime-template/` mirrors the required and runtime-generated directories
  with `.DONOTDELETE` placeholders. It contains no game payloads.

These findings describe compatibility behavior only; none of the mentioned
archives are included in the source repository.

## Offline response pipeline

The Android-mod server data is not compiled into the wrapper. The JNI HTTP
shim reads encrypted payloads from `assets/responses/` on each emulated HTTP
request. Seven endpoint names use compatibility aliases; direct-name lookup is
next, followed by `generic.bin`.

The tested APK contains 48 JSON response documents. Forty-six are retained
semantically unchanged. The public builder makes `CmdLogin` and
`CmdGetMyclubEntryInfo` share the corrected 30-player existing-account entry,
clears the default-manager onboarding list, repairs duplicated serials, and
adds the fixed-size neutral formation required by the native parser. It then
MessagePacks, GZIPs, and encrypts every response exactly as the client expects.
All generated sizes and all 48 byte streams were checked against the live
Ryujinx runtime used for the successful Exhibition match.

The nearby `.json` files used in private diagnostic runs are not runtime input.
Only `.bin` files are opened by `jni_fake.c`. The Exhibition hook separately
loads player, shirt, formation, and manager records from the game's master data
already present in the user's OBB/PAK; those records are not copied into this
repository or into the response fixtures.

## Runtime preparer

`tools/prepare_runtime.py` discovers the exact supported APK, main OBB, patch
OBB, and one release NRO in a selected directory. It validates the proprietary
inputs' complete SHA-256 hashes before creating a staging directory. It then
extracts the arm64 libraries, main PAK, and ten locale CPKs, generates the
response payloads, copies the release NRO, and hashes all 64 required runtime
files. Only a fully validated staging directory is renamed to
`<selected>/switch/pes21_nx`; existing output is rejected to protect user
SaveData. Explicit file-path arguments remain available for development.

The patch OBB extractor is implemented in this repository. It decrypts and
parses the CRI UTF CPK header and TOC, bounds-checks each requested member, and
accepts only the expected uncompressed locale entries. Testing produced ten of
ten CPK files byte-identical to the live runtime without invoking the local
third-party CriPakTools binary.

The GitHub release workflow packages this source as a standalone Windows
`PES21NX-Prepare.exe` with its Python dependencies. When launched without
arguments it uses one native directory picker. Release users extract the bundle,
put the APK and both OBBs beside its included NRO, select that directory, and
receive a complete `switch/pes21_nx` tree inside it.

### Local development workspace

A locally complete source checkout may use the following ignored directories:

- `local-inputs/` for the compatible APK, both OBBs, and a development NRO;
- `dist/pes21_nx/` for the validated runtime launched by Ryujinx or copied to
  Switch;
- `local-debug/offline-responses/` for optional decrypted JSON and generated
  response payloads used during diagnostics;
- `logs/` for local traces, dumps, and screenshots.

These paths are deliberately excluded by `.gitignore` and the public-tree
audit. They may contain user-owned proprietary data and must never be staged or
published. Populate the runtime from the ignored inputs with:

```powershell
python -B tools/prepare_runtime.py `
  --input-dir local-inputs `
  --output dist/pes21_nx
```

The preparer refuses to overwrite an existing runtime so it cannot silently
destroy `SaveData`. Use a separate output for experiments, or explicitly move
the old local runtime aside before rebuilding it.

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
