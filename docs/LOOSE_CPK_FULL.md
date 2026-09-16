# Full loose CPK runtime

Status: stable. The full package completed hardware boot and gameplay testing
without mount errors or visible regressions. Git release marker:
`loose-cpk-full-v1-stable`.

## Result

The full package extracts every one of the 24 stored CPK members from the
approved 1,412,450,304-byte player-migration OBB. The runtime keeps the same
mount names and order, but redirects each nested `/Expansion/*.cpk` bind to
`./LooseCpk/*.cpk`.

The replacement OBB is a valid 53,248-byte CRI archive containing the same 24
paths in the same order. Each member is a four-byte placeholder. The native
existence checks therefore succeed before the low-level bind hook redirects
the actual read. The placeholder is never used as game data.

This changes packaging, not game content. The extracted bytes of every CPK
match the approved source OBB exactly.

## Build package

```powershell
python tools/prepare_loose_cpk.py extract-full `
  --obb local-debug/pes21-player-migration-canary/patch.305030001.jp.nyan2021.pesam.obb `
  --output local-debug/loose-cpk-full-v1 `
  --build-id 81f096d278e1225b

.\build-wsl.ps1 `
  -OutputDirectory local-debug/loose-cpk-full-v1 `
  -PlayerMigrationCanary `
  -LooseCpkFull `
  -ExpectedPatchObbSize 53248 `
  -Diagnostics -Jobs 8
```

`-LooseCpkFull` deliberately requires `-PlayerMigrationCanary`; the manifest
and NRO must share the same migration build ID. The full NRO refuses a missing
manifest, the old large OBB, an unexpected dummy OBB, and incomplete packages.

## Install for hardware validation

Close the game completely. Preserve the approved large OBB and previous NRO
outside the SD runtime for rollback. From `local-debug/loose-cpk-full-v1`, copy:

- `pes21_nx.nro` to `sdmc:/switch/pes21_nx/pes21_nx.nro`;
- the 53,248-byte `patch.305030001.jp.nyan2021.pesam.obb` to the runtime root,
  replacing the large OBB on the SD card;
- the entire `LooseCpk/` directory to `sdmc:/switch/pes21_nx/LooseCpk/`.

There must be 24 `.cpk` files and `manifest.txt`. Do not copy the ELF, NACP,
or provenance JSON. Leave `Download/`, `PesMobile/`, `SaveData/`, libraries,
and response assets unchanged. A legacy `LooseCpk/verified-v2.txt` may remain;
the fast-validation runtime ignores it.

Copy CPKs first and `manifest.txt` last. Never install while the game is open.

## Fast boot validation

Runtime boot does not hash the 1.4 GB package. It validates the manifest/build
ID, dummy OBB size, all 24 required filenames and exact sizes, and the `CPK `
signature of every archive. Full SHA-256 validation remains mandatory in the
PC-side extract, update, verify, and packaging tools. Copy CPKs first and the
manifest last so an interrupted partial update fails the runtime size checks.

Legacy `LooseCpk/verified-v2.txt` files are ignored and may be left in place;
new runtime builds do not create or depend on a verification cache.

## Partial updates

```powershell
python tools/prepare_loose_cpk.py update `
  --root local-debug/loose-cpk-full-v1 `
  --member dt200_mobile_all.cpk `
  --file PATH_TO_NEW_DT200.cpk

python tools/prepare_loose_cpk.py verify `
  --root local-debug/loose-cpk-full-v1
```

Distribute only the changed CPK and the new manifest. The receiver closes the
game, copies the CPK first, then the manifest. NRO updates remain necessary
when code, compiled team catalogs, generated rosters, or migration build IDs
change. Loose CPK packaging does not remove that compatibility contract.

## Hardware validation

- First boot reaches the game without reading all CPK payloads and reports
  fast-validated full mode.
- The log records successful loose redirects for every CPK mounted by the
  selected language; no nested bind may use a placeholder.
- Inter Miami, Al Nassr, Barcelona, kits, crests, portraits, faces,
  commentary, pre-match Game Plan, pause Game Plan, and repeated matches are
  unchanged from the approved canary.
- Repeated cold boots and the first boot after a partial update remain fast.
- Changing commentary language mounts the corresponding loose dt530 CPK.

The default runtime hardware gate passed. The large OBB is retired from the SD
runtime, but remains the local rollback/source artifact. Language-specific
dt530 mounts remain covered by the same strict manifest and routing table.

Stable artifact hashes:

- NRO: `23abf0718d295d209fec26bf7be64066ac31aa61854b833d88f7b1dd9c19d0fc`
- dummy OBB: `3fe37e8175c8b20d7248e25810c5ffced19962bae21f3f2725168fde9ed1f92f`
- manifest: `fc4b91a3ef339d68789c1ecdba64bc4123b5d82d1a1b08c62ec3b6f04b437248`

## Rollback

Restore the previous checkpoint NRO and the approved 1,412,450,304-byte OBB
together. Remove or rename the V2 `LooseCpk/manifest.txt`; the old canary NRO
does not accept a V2 manifest. Restore both components as one matched pair.
