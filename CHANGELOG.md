# Changelog

All notable changes to the public PES 2021 NX wrapper are recorded here.
Game files and changes made by the compatibility target are outside the scope
of this changelog.

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
