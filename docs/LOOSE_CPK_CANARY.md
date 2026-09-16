# Loose CPK canary

## Scope

Stage 1 redirects only `/Expansion/dt200_mobile_all.cpk` and
`/Expansion/dt241_mobile_all.cpk` to files beside the NRO in `LooseCpk/`.
The original OBB remains required for all other packs and native existence
checks. A small dummy OBB is NOT supported at this stage.

The canary uses the approved player-migration snapshot `81f096d278e1225b`.
No global player migration is activated by this change.

## Install and rollback

From `local-debug/loose-cpk-canary`, copy the new `pes21_nx.nro` and the entire
`LooseCpk` directory into the existing runtime directory on the SD card.
Keep the existing OBB, Download directory, and approved canary SaveData.
Do not copy the ELF, NACP, or host provenance JSON. Fully restart the game.

Remove or rename `LooseCpk/manifest.txt` to return this NRO to the original
OBB route. The approved original NRO and OBB remain unchanged in
`local-debug/pes21-player-migration-canary`.

## Validation and routing

The manifest pins the compiled migration ID, parent OBB size, and the size
and SHA-256 of both loose packs. Boot validates both packs before enabling
either redirect. Invalid or incomplete manifests/packs stop boot; they do
not silently fall back to another player database. An absent manifest
intentionally selects the legacy OBB path.

The runtime hashes the two loose packs, not the entire parent OBB. Host-side
`loose-cpk-source.json` records the original OBB hash and extraction provenance.
That JSON describes the initial extraction; the manifest is authoritative
after partial updates. Hashing approximately 188 MiB adds startup I/O.

At the CRI BindCpk call, exact matching nested paths are redirected to
`./LooseCpk/<name>` with a null source binder. Destination binder, work buffer,
native priority, ordering, and unbind lifecycle are preserved. Other mounts
are untouched. Diagnostic logs report each redirected bind and its result.

## Host commands

Run from the repository root:

```powershell
python tools/prepare_loose_cpk.py extract --obb local-debug/pes21-player-migration-canary/patch.305030001.jp.nyan2021.pesam.obb --output local-debug/loose-cpk-canary --build-id 81f096d278e1225b
python tools/prepare_loose_cpk.py verify --root local-debug/loose-cpk-canary --obb local-debug/pes21-player-migration-canary/patch.305030001.jp.nyan2021.pesam.obb
python tools/prepare_loose_cpk.py update --root local-debug/loose-cpk-canary --member dt200_mobile_all.cpk --file PATH_TO_REPLACEMENT_CPK
```

Extraction refuses an existing LooseCpk directory. Update validates the
existing package and replacement, publishes the replacement pack, then the
manifest. Install only while the game is closed; copy changed packs first
and the manifest last. An interrupted installation must be completed before
boot. Keep the previous changed pack and manifest together for rollback.

Partial updates operate at CPK granularity, not individual member granularity.
Player/roster changes that alter compiled NRO data still require a matching
NRO. This mechanism does not make incompatible databases interchangeable.

Build the diagnostic canary:

```powershell
.\build-wsl.ps1 -OutputDirectory local-debug/loose-cpk-canary -PlayerMigrationCanary -ExpectedPatchObbSize 1412450304 -Diagnostics -Jobs 8
python -m unittest discover -s tests -p test_loose_cpk.py -v
```

## Hardware gate (pending)

- Confirm logs show verified loose canary mode and successful redirects for both packs.
- Test Inter Miami, Al Nassr, and Barcelona: hub, pre-match Game Plan, portraits,
  starting eleven, kickoff identities, faces, commentary, and pause Game Plan.
- Check branding, kits, logos, and several consecutive matches.
- Test manifest removal: the same NRO must boot the unchanged original OBB.
- Only after this gate should additional pack extraction or global player
  migration proceed. A tiny OBB requires a separate audit of every remaining
  mount and native archive/existence dependency.

Host tests cover extraction, partial replacement, unchanged-pack preservation,
manifest activation, exact routing, and rejection of wrong IDs, missing,
truncated, and hash-corrupted files. They do not prove native hardware I/O.

## Initial artifact hashes

- NRO: `90b3efbaa037d7e8961318a1fc21fe05b858e68c05129b578c86878453d59313`
- Parent OBB (1,412,450,304 bytes): `f9d6e370bcf5963d131bc1711fecc44c1e58c8c7e5e673e0d714c6435abbde0c`
- dt200 (10,964,992 bytes): `728216780263d6ab6cdc85fd43cf66700a1668fcae983e58fa78734a0c76ffc1`
- dt241 (186,464,256 bytes): `1abda618f28d386fbacdcf477883fecee460766bb6253ef55a244eff37b5657d`
