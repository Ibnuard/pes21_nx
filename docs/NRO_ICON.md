# FNX launcher artwork

The canonical build input is root `icon.jpg`: an opaque, baseline 256x256 RGB
JPEG. Its master and generation prompt live in `art/nro/`. Both direct Makefile
and WSL builds use that input. Changing the JPEG triggers NRO repackaging even
when no source code changes.

`build-wsl.ps1` validates dimensions/format before compilation and compares the
embedded ASET icon byte-for-byte after compilation, before promotion to `dist`.
The checker uses Windows System.Drawing, with no additional Python dependency:

```powershell
.\scripts\check-nro-icon.ps1 -IconPath icon.jpg -NroPath PATH_TO_BUILT_NRO
```

The legacy APK/OBB preparer now copies the supplied release NRO unchanged by
default, preserving its icon, executable, NACP and RomFS. `--apk-icon` explicitly
opts into the former APK-artwork conversion. This does not make that legacy
preparer a full-loose-CPK installer.

Keep the established full-loose build flags when producing this user's runtime:

```powershell
.\build-wsl.ps1 `
  -OutputDirectory local-debug/fnx-icon-build `
  -PlayerMigrationCanary -LooseCpkFull -ExpectedPatchObbSize 53248 `
  -BadgeAtlas local-debug/full-mobile-kit-migration-v1/league-branding/badge_atlas.bin `
  -MigrationTeamInclude local-debug/full-mobile-kit-migration-v1/league-branding/exhibition_teams_migration_generated.inc `
  -Jobs 8
```

Do not replace this with a bare build command for a full-loose installation.
Do not distribute the unrelated legacy runtime contents in `dist` as a complete
full-loose package.

## NSP forwarder feasibility

A separate homebrew NSP forwarder can launch
`sdmc:/switch/pes21_nx/pes21_nx.nro` and use this same JPEG. It is a launcher, not
a conversion of the game/runtime into a standalone NSP; all SD assets remain
required. Updating the target NRO does not require regenerating the forwarder
unless its path or installed metadata/icon changes.

[NTON's upstream documentation](https://github.com/rlaphoenix/nton) describes
extracting title metadata and artwork directly from an NRO, custom icons, and an
explicit SD path. Its workflow requires locally supplied console keys and an
unused title ID. Never commit keys or proprietary payloads. Upstream warns of
console-ban risk from installed forwarders; compatibility with this wrapper's
memory/application-mode requirements still needs hardware testing.

No NSP or console installation is produced by the NRO build script.

### Local FootballNX 26 v2.0.0 candidate

The 2026-09-20 local build used `APP_TITLE=FootballNX 26`,
`APP_AUTHOR=Androswitch Project`, and `APP_VERSION=2.0.0` with the full-loose
flags above. Its NRO is `local-debug/fnx-v2-forwarder/pes21_nx.nro`. NTON 3.0.1
then built a forwarder targeting `sdmc:/switch/pes21_nx/pes21_nx.nro`, using
the same `icon.jpg`. The locally generated title ID is `01867db209672000`.
The NSP is `local-debug/fnx-v2-forwarder/FootballNX26-v2.0.0-forwarder.nsp`.

Both binaries and console keys remain ignored/local. The NRO retains the
existing player migration build ID `1852ec648d2ebd75`, which matches the
accepted V17 skin4 full-loose manifest. NTON validated the NRO and built the
NSP; booting the forwarder on a Switch is still pending user testing.
