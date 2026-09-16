# Stable kit/logo migration checkpoint

## Verified release

User hardware confirmation: `native-license-v7-madrid-preserve-order` is stable.
Recovery v6 was also confirmed to have the latest Barcelona kit, working goal
celebration and pause. The subsequent Madrid candidate was confirmed stable.
This is user hardware evidence, not an automated emulator test.

Production binaries promoted unchanged to `dist/pes21_nx/`:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| pes21_nx.nro | 46715085 | af5887f8b3a24e5b0eae1685dc0b9e42af6d64c1db6a2830a13e3b4b0e6698e0 |
| patch.305030001.jp.nyan2021.pesam.obb | 1393788928 | 206720b6c6378dad462d9aa5de2e2e9207992826f70158948175106282b92904 |

Local source: `local-debug/native-license-v7-madrid-preserve-order/`.
Previous dist backup: `local-debug/stable-promotion-before-madrid-v7/`.
Dist and proprietary runtime archives remain git-ignored; Git stores tools,
documentation and metadata, not the OBB/NRO payloads. Never force-add them.
The exact tested NRO is authoritative; subsequent diagnostic source edits are
not evidence that a freshly rebuilt NRO has been hardware verified.

## Why earlier candidates regressed

Do not equate a successful Python dictionary lookup with native loader compatibility.
The failing packages could contain every asset and pass byte-level validation,
yet still fail at boot or render kits incorrectly and stall goal/pause sequences.
Sorting whole CPK TOCs fixed boot in v3 but regressed other behavior. The exact
native mechanism is not proven; a universal case-insensitive sorting rule is
NOT established by these experiments.

The successful Madrid candidate retains original TOC row order and IDs, appends
Madrid descriptor rows, and sets `Sorted=0` on dt120/dt200. Existing texture
payloads remain unchanged. This is the tested contract for these archives, not
a claim that every CRI archive supports the same layout.

`AAsset ... MISSING` is an Android loose-file probe. It alone does not prove the
file is absent from CPK or explain a stall. Binder `result=0` likewise does not
prove all subsequent reads completed.

## Migration workflow

1. Start from an explicitly selected, hardware-tested OBB/NRO pair. Preserve a
   backup and record hashes. Never use an untested canary as a stable baseline.
2. Map logical club IDs to physical slots. Preserve Player.bin, assignments,
   tactics, names and unrelated Team.bin fields. Do not replace a whole old
   Team.bin merely to change licensing flags.
3. Inventory existing texture and descriptor names before deciding replace/add.
   Barcelona 108 has native realUni descriptors. Madrid 109 needed three realUni
   additions. Do not overwrite a 96-byte generic descriptor with a 120-byte realUni.
4. Convert Football Life FTEX to the verified mobile format using
   `tools/build_barca_real_madrid_mobile_kit_canary.py` and its manifest. For this
   template, body atlases are 256x384, backs 320x40; do not directly transplant
   PC FTEX. Validate home, away, GK and font references independently. This
   converter currently enforces the 108/109 canary; extend its manifest validation
   and tests before using it for other clubs.
5. Preserve working Barcelona descriptors/textures from recovery. Do not swap
   all descriptors to PC versions as an incidental part of another club's import.
6. Use `tools/build_madrid_preserve_order.py` for the tested integration method.
   It checks converted texture provenance, changes only Madrid's Team.bin kit
   flag, adds the three descriptors, and restores original row order with Sorted=0.
   Its intermediate generic packer may sort; only the final original-order CPK
   files are approved inputs to the outer OBB.
7. Patch existing outer slots with `patch_cpk_slots.py` when capacity permits.
   Reject overflow rather than overwriting adjacent data. If repacking becomes
   necessary, treat the result as a new untested candidate. If OBB size changes,
   update the explicit size allowance in source/main.c and build a matching NRO.
8. Validate member sets, all unrelated payloads, original row order/IDs, flags,
   offsets and hashes. Then test on hardware: boot, selector, native prematch,
   both clubs' kits, Game Plan, goal celebration, skip, pause/resume and restart.
   Only promote after the complete affected flow works.

Reproduce this candidate with local input assets present (fresh output required):

```powershell
python tools/build_madrid_preserve_order.py --base-obb local-debug/native-license-v6-kit-regression-recovery/patch.305030001.jp.nyan2021.pesam.obb --kit-pack local-debug/pesdb-famous-teams-candidate-v6-barca-madrid --output local-debug/madrid-new-candidate
```

## Logos have two separate consumers

- Custom selector/Game Plan: `data/exhibition_team_catalog.json`, generated
  `source/exhibition_teams_generated.inc`, and badge atlas compiled into NRO.
  `tools/integrate_club_licenses.py` stages names/Football Life crests;
  `scripts/generate_badge_atlas.py` builds the atlas. Rebuilding the catalog from
  raw EF10 sources can erase staged license overrides: reapply them deliberately.
- Native prematch/goal/pause surfaces: crest PNG members inside dt240. Updating
  the NRO atlas does not update these. Keep native dimensions and transparency.
  Changing Madrid to licensed uniforms required both `_f` and `_r` crest aliases,
  including `_l` and `_s` sizes. A missing crest is not automatically a PNG error.

For other teams, audit their requested variants rather than guessing filenames.
The current name manifest covers 39 existing native clubs; Sunderland 396 still
needs coordinated team/roster/slot integration. Do not claim all 40 slots exist.

## Scope limits

This checkpoint is not a complete EF10 face transfer. Portraits and 3D faces are
different resources. Do not infer Ronaldo's runtime identity merely because a
mapping contains `4522:4522`; verify his actual active assignment before claiming
the correct model/commentary. The single missing-portrait guard is not a general
solution for every possible missing portrait.
