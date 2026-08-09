# PES 2021 NX

PES 2021 NX is an experimental Android arm64 compatibility wrapper for
Nintendo Switch homebrew. It maps the original Android ELF objects into the
homebrew process, resolves their Bionic/Android imports through native shims,
and starts the game as a simulated Android `NativeActivity` without running
Android itself.

This repository contains wrapper source code, a safe runtime-directory
template, and build tooling only. It does **not** contain an APK, OBB, native
game libraries, PAK/CPK archives, extracted game assets, saved data, generated
network-response payloads, private keys, or game artwork. You must supply a
legally obtained compatible copy of the game and prepare its runtime files
yourself. Do not open issues asking for copyrighted files, download links,
private keys, or piracy support.

This is an independent compatibility project. It is not affiliated with,
authorized, sponsored, or endorsed by Konami. All product names, trademarks,
and copyrighted game content belong to their respective owners.

## Compatibility target

The currently supported and tested target is **PES 2021 Mobile v5.3.0**
(`versionCode 305030001`, package `jp.nyan2021.pesam`), specifically the
**Nyan Mod Offline** edition. Other game revisions or packages are not expected
to work without source changes.

The Nyan Mod files are not included, maintained, or distributed by this
repository. Credit goes to **Nyan Mod** for creating the offline modification
used as the compatibility target during development.

## What is included

- Android arm64 ELF loading, relocation, and symbol resolution
- Bionic libc, pthread, JNI, asset-manager, and Android activity shims
- EGL/GLES2, input, audio, filesystem, and networking compatibility glue
- UE4-specific runtime hooks and diagnostic instrumentation
- A synthetic silent audio fixture and a project-authored numeric FPS font
- A placeholder-only runtime tree and a reproducible offline-response builder
- A one-folder Windows preparer for the APK, two OBBs, and release NRO
- devkitPro/libnx Makefile and a WSL build helper

## Current status

Wrapper version `0.1.93` boots through the splash screen and menus on the
tested v5.3.0 game revision. Touch input, offline HTTP bootstrap,
login/registration flow, PAK/CPK mounting, the render loop, UI/HUD, and the 3D
gameplay scene are operational in the tested Ryujinx setup.

The offline bootstrap can now treat the supplied club data as an existing
account and bypass the otherwise-blocking mobile onboarding wizard. The JNI
shim also implements the title's software-keyboard contract for profile text
input still requested by the game.

The former gameplay black screen is fixed by a GLES 3 fullscreen fallback
compositor. The original mobile final pass produces no covered fragments on
the tested Switch Mesa path; the fallback samples the completed offscreen scene
texture, performs the linear-to-sRGB conversion, and corrects the vertical
orientation before presentation.

Controller gameplay now uses a custom multi-touch handler because the original
PES Mobile match layer does not consume native gamepad input. In the tested
Ryujinx Classic-control setup, the left analog moves the player, B passes, X
performs a through pass, Y shoots, A performs a Cross while attacking or a
Sliding gesture while defending, and R1 holds Dash. Multiple synthetic contacts
can run together, so movement, sprint, and an action can overlap while the
physical touchscreen remains available. See [DEVELOPMENT.md](DEVELOPMENT.md)
for implementation and testing details.

The eFootball tile now provides a local Exhibition proof of concept. It uses
the title's own master club/player data instead of the incomplete myClub squad
fixture, currently selecting FC Barcelona against Madrid Chamartin B, then
continues through Strategy into a normal CPU match. Runtime testing reached
active gameplay with valid player models and no immediate 3-0 forfeit.

## Build

Required packages:

- devkitPro with `devkitA64` and `libnx`
- `switch-mesa` and `switch-libdrm_nouveau`
- `switch-sdl2`, `switch-openal-soft`, `switch-zlib`, and `switch-mpg123`
- WSL Ubuntu when using the supplied PowerShell helper

The helper expects devkitPro at `/opt/devkitpro`. From PowerShell:

```powershell
.\build-wsl.ps1
```

On a configured Linux/devkitPro environment, run `make`. The resulting NRO,
ELF, NACP, map, and build directory are intentionally ignored and rejected by
the public-tree audit; publish source from this tree, not local build output.

## Automated releases

The `Build and release NRO` GitHub Actions workflow provides a manual,
source-only release process. Before running it:

1. Update `APP_VERSION` in `Makefile`.
2. Add the matching version section to [CHANGELOG.md](CHANGELOG.md).
3. Update the matching wrapper section and current progress in
   [DEVELOPMENT.md](DEVELOPMENT.md).
4. Push the changes, open **Actions > Build and release NRO > Run workflow**,
   and enter a tag such as `v0.1.93`.

The workflow validates that the tag matches `APP_VERSION`, builds in the
official `devkitpro/devkita64` container, uploads the NRO and SHA-256 checksum
as a CI artifact, creates the Git tag and GitHub Release, and generates release
notes from the changelog and development-progress documents.

The repository must allow GitHub Actions read/write workflow permissions so
the provided `GITHUB_TOKEN` can create tags and releases. Release assets contain
the wrapper NRO, checksums, and the standalone Windows preparer bundle; users
still supply the compatible APK and both OBB files themselves.

## Runtime layout

The repository includes the empty [runtime-template](runtime-template/) tree.
Its `.DONOTDELETE` files preserve the tested folder structure; none of the
proprietary files shown below may be committed:

```text
sdmc:/switch/pes21_nx/
|-- pes21_nx.nro
|-- libavs2-core.so
|-- libafp-core.so
|-- libUE4.so
|-- PesMobile/Content/Paks/PesMobile-Android_ETC1.pak
|-- patch.305030001.jp.nyan2021.pesam.obb
|-- Download/dt530_mobile_*_all.cpk
|-- assets/responses/*.bin
|-- SaveData/                         (generated locally)
`-- UE4Game/PesMobile/PesMobile/Content/Paks/ (optional mirror)
```

For the tested revision, the main OBB is a ZIP containing the main PAK. Extract
that PAK into the loose `PesMobile/.../Paks/` path; the main OBB itself is not
needed afterward. The patch OBB is an active CPK container rather than a ZIP,
so it remains mounted under its original filename. Ten small locale CPK files
are also required loose under `Download/`.

The offline response files are used directly: `jni_fake.c` maps each requested
PHP command to `assets/responses/<name>.bin`, applies seven compatibility
aliases, and falls back to `generic.bin` for an unknown command. They are not
embedded into the NRO and the stale JSON files sometimes used during local
debugging are not read by the game.

The public builder extracts the 48 original response documents from a
user-supplied APK, changes only `CmdLogin` and `CmdGetMyclubEntryInfo` so both
describe one existing account, and emits byte-for-byte reproducible encrypted
payloads. The APK's VS-COM response remains unmodified; the new Exhibition path
does not use its incomplete myClub roster and instead binds valid master teams
inside the native flow. See [runtime-template/README.md](runtime-template/README.md)
for the exact command and provenance of every runtime directory.

Release bundles include `PES21NX-Prepare.exe` beside the NRO. Put the compatible
APK and both OBBs in that same directory, launch the preparer, and select that
one directory. It detects all four inputs and creates a ready-to-copy
`switch/pes21_nx/` below them. The preparer validates exact input hashes,
extracts the three libraries and main PAK, parses the patch CPK directly to
extract ten locale archives, generates all offline responses, validates and
hashes 64 required runtime files, and publishes the output atomically. It does
not depend on CriPakTools or overwrite SaveData.

For an already-created offline account, `coach_list` and `squad_list` contain
the owned club data while `default_coach_list` is empty. The game interprets a
non-empty default list as the choices for a new-account manager wizard; mixing
those two meanings reopens onboarding even when a complete squad is present.

Launch through a full-memory title override, not Album applet mode. The loader
needs code-memory syscalls and more heap than applet mode provides.

## Public-tree safety check

Run this before every commit or release:

```powershell
.\scripts\check-public-tree.ps1
```

The same check runs in GitHub Actions and rejects game archives, extracted
runtime binaries, build output, logs, keys, suspicious private-key material,
and unexpectedly large files.

## License

Wrapper code is distributed under the MIT license; see [LICENSE](LICENSE) and
[NOTICE.md](NOTICE.md). No license is granted for any separately obtained game
content.

## Credits

Porting concepts and ideas that helped shape this project were inspired by
work shared by [NaGaa95](https://github.com/NaGaa95).

Credit also goes to **Nyan Mod** for the PES 2021 Mobile v5.3.0 offline
modification used as this project's compatibility target.
