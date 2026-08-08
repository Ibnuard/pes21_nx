# PES 2021 NX

PES 2021 NX is an experimental Android arm64 compatibility wrapper for
Nintendo Switch homebrew. It maps the original Android ELF objects into the
homebrew process, resolves their Bionic/Android imports through native shims,
and starts the game as a simulated Android `NativeActivity` without running
Android itself.

This repository contains wrapper source code and build tooling only. It does
**not** contain an APK, OBB, native game libraries, PAK/CPK archives, extracted
assets, saved data, network-response payloads, encryption keys, or game
artwork. You must supply a legally obtained compatible copy of the game and
prepare its runtime files yourself. Do not open issues asking for copyrighted
files, download links, keys, or piracy support.

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
- devkitPro/libnx Makefile and a WSL build helper

## Current status

Wrapper version `0.1.77` boots through the splash screen and menus on the
tested v5.3.0 game revision. Touch input, offline HTTP bootstrap,
login/registration flow, PAK/CPK mounting, the render loop, UI/HUD, and the 3D
gameplay scene are operational in the tested Ryujinx setup.

The former gameplay black screen is fixed by a GLES 3 fullscreen fallback
compositor. The original mobile final pass produces no covered fragments on
the tested Switch Mesa path; the fallback samples the completed offscreen scene
texture, performs the linear-to-sRGB conversion, and corrects the vertical
orientation before presentation.

Switch HID polling and a custom bridge into the game's native pad state are
present, but controller gameplay is still experimental. Input is visible in
diagnostic logs, while the PES Mobile match-action layer does not yet respond
reliably. Controller support is therefore **not** listed as working yet. See
[DEVELOPMENT.md](DEVELOPMENT.md) for the evidence and current next step.

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
   and enter a tag such as `v0.1.77`.

The workflow validates that the tag matches `APP_VERSION`, builds in the
official `devkitpro/devkita64` container, uploads the NRO and SHA-256 checksum
as a CI artifact, creates the Git tag and GitHub Release, and generates release
notes from the changelog and development-progress documents.

The repository must allow GitHub Actions read/write workflow permissions so
the provided `GITHUB_TOKEN` can create tags and releases. Release assets contain
only the wrapper NRO and checksum; users still supply all game files themselves.

## Runtime layout

The following is documentation only. None of these proprietary runtime files
may be committed to this repository:

```text
sdmc:/switch/pes21_nx/
|-- pes21_nx.nro
|-- libavs2-core.so
|-- libafp-core.so
|-- libUE4.so
|-- PesMobile/Content/Paks/PesMobile-Android_ETC1.pak
|-- patch.305030001.jp.nyan2021.pesam.obb
|-- Download/dt530_mobile_*_all.cpk
`-- assets/responses/*.bin
```

For the tested revision, the main OBB is a ZIP containing the main PAK. Extract
that PAK into the loose `PesMobile/.../Paks/` path; the main OBB itself is not
needed afterward. The patch OBB is an active CPK container rather than a ZIP,
so it remains mounted under its original filename. Ten small locale CPK files
are also required loose under `Download/`.

The current offline bootstrap additionally expects locally prepared response
payloads under `assets/responses/`. Those payloads and the private preparation
tooling are deliberately not distributed here, so this source tree is not a
plug-and-play game package.

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
