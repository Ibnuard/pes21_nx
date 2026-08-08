# Contributing

Contributions to the compatibility wrapper are welcome, especially fixes for
the final GLES compose path, input mapping, shim correctness, and reproducible
diagnostics.

## Repository rules

Never submit or attach:

- APK/OBB files or extracted game assets
- native game `.so` files or PAK/CPK archives
- offline response payloads, cryptographic keys, or decrypted private data
- save data, logs containing personal identifiers, or emulator firmware/keys
- compiled NRO/ELF/NACP artifacts or third-party emulator binaries

References to filenames, symbols, offsets, and observed behavior may be used
when necessary to explain wrapper compatibility work. Keep test material in a
private local runtime directory and reduce bug reports to logs or code snippets
that do not reproduce copyrighted content.

## Before opening a pull request

1. Build the wrapper with `make` or `.\build-wsl.ps1`.
2. Verify, then remove the local NRO/ELF/NACP and other build output.
3. Run `.\scripts\check-public-tree.ps1` from PowerShell.
4. Confirm the public tree contains no runtime or build artifacts.
5. Describe the tested environment and the observable before/after behavior.
6. Keep new platform shims narrowly scoped and document non-obvious behavior.

By contributing, you agree that your changes are provided under the repository
MIT license and that you have the right to submit them.
