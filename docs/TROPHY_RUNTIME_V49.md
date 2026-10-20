# Trophy runtime v49 canary

**Hardware follow-up: do not use this package to preserve the FL26 walkout.**
The 2026-10-18 device test confirmed that its hashes and hooks loaded, but the
working player walkout reverted to the stock intro and no trophy appeared
after a completed Cup final. The package used the stock entrance CPK as its
baseline. Its result adapter also missed the normal full-time ending factory.
These are integration defects; successful offline validation did not prove
the user's installed entrance was retained or that regular finals reached the
adapter. A combined walkout/trophy package and the normal ending boundary are
being corrected in v50. The notes below record the v49 build, not acceptance.

This opt-in candidate connects the previously audited trophy assets to the
Mobile runtime. Its baseline is the user-accepted v48 rendering build. The
current native entrance, player quality policy, face assets, renderer fixes,
roster identity and save formats are retained. Hardware playback and the
appearance of the winning captain, cup and podium still require a Switch test.

## Activation and ownership

`trophy-canary.txt` enables the candidate only with the reviewed Mobile library,
trophy CPK and cinematic-prop PAK. Startup measures those files and the selected
manifest once per startup. The marker is exact, ordered, LF-only text; it cannot approve an
arbitrary CPK or PAK. All native ABI and hook-slot checks for both adapters pass
before either adapter writes a patch. Without the marker, trophy hooks are not
installed.

The result adapter captures the borrowed Registry during the native
`match::FixDemo::CreateFixDemo` invocation. Only the audited full-time result
caller, actual END phase, fresh team identities and scores, and a live standalone
Cup championship final qualify. Normal goals and shootout-only goals are read
separately. A dedicated monotonic match token prevents replaying an accepted
ceremony. Half-time, semifinals, third place, simulations, completed Cups,
Exhibition, League and Master League do not qualify.

The native manager retains player selection, captain parenting, animation,
camera, Skip and deletion. Creation alone does not count as success. The first
cut waits for both cooked static meshes to be bound to their actual native
components. The PES and UE callbacks exchange only bounded identity metadata;
readiness is not inferred from actor existence. Waiting is bounded by elapsed
time and callback counts. Failed loading returns through the ordinary result
factory after the candidate's native destructor releases its resources.

The native ceremony frame-rate request and its restoration remain native.
Accepted 60 FPS gameplay does not imply a 60 FPS cinematic. No new per-frame
mesh scanning runs during ordinary gameplay. Lifecycle diagnostics go to the
bounded `trophy-runtime.log` in the runtime directory.

## Reproducible package

Use `build-wsl.ps1` with the same full-loose roster/catalog inputs as the accepted
v48 NRO and a separate output directory. Keep diagnostics, performance trace and
near-camera trace off. The local build arguments are recorded alongside the
candidate; ignored inputs are not repository guarantees.

`tools/build_trophy_test_package.py` builds a detached update. It re-audits the
trophy CPK and cooked PAK, verifies the complete current baseline by streaming
hashes, retains all unrelated manifest rows, and matches the NRO's executable
segments to its linked ELF. It requires the integrated capability and the
reviewed asset hashes in that NRO. It does not duplicate an OBB or copy saves.

The native-club baseline can be composed with the current physique CPK overlay
by supplying `--baseline-manifest` and `--baseline-cpk-root`. An unknown entrance
CPK is rejected: independently overlaying the older experimental FL26 walkout
package would discard either its entrance or this trophy change.

The generated package contains `Apply-Update.ps1`, `INSTALL.txt`,
`VERIFICATION.json` and five update files:

- `pes21_nx.nro`
- `LooseCpk/dt220_mobile_all.cpk`
- `LooseCpk/manifest.txt`
- `PesMobile/Content/Paks/PesMobile-CinematicProps-Android_ETC1_P.pak`
- `trophy-canary.txt`

Run the installer against the folder containing the accepted NRO, first with
`-CheckOnly`, then without that switch. Its default rollback storage is on D.
It validates the installed NRO and full CPK baseline, backs up only these five
paths, installs the marker last, and restores originals if an installation
fails. A later unrelated update is never overwritten by rollback. Keep the
reported rollback directory until device testing is complete.

```powershell
.\Apply-Update.ps1 -RuntimeRoot 'E:\switch\pes21_nx' -CheckOnly
.\Apply-Update.ps1 -RuntimeRoot 'E:\switch\pes21_nx'
# Restore using the exact directory printed by the installer:
.\Apply-Update.ps1 -RuntimeRoot 'E:\switch\pes21_nx' `
  -RollbackDirectory 'D:\PESNX-Cache\RuntimeRollback\trophy-<printed-id>'
```

Replace the example SD drive and runtime path with the actual mounted folder.
An installer mismatch needs investigation, not a manual overwrite of `update/`.

## Local verification (2026-10-18)

The integrated AArch64 build completed with the accepted v48 inputs and runtime
pair `e861c583ec78e9ae`. Focused tests passed for activation parsing, ceremony
eligibility, native result/prop ABI probes, lifecycle races, installer/rollback,
and the retained entrance and rendering policies. The last lifecycle regression
forces an old completion to resume after a new match has failed; the new failure
must stay latched.

The detached package is
`local-debug/trophy-runtime-v49/FootballNX-Trophy-Canary-v49-TEST.zip`.
Its fresh audit verified all 24 baseline CPKs, the 28 trophy payloads, 2,471
unchanged unrelated CPK members, and all 14 cooked PAK members. The three NRO
load segments match the linked ELF. ZIP CRCs and every packaged runtime file's
SHA-256 were checked after packaging; all 13 recorded runtime source files
still match the build inputs.

- NRO SHA-256: `3bba60b4af5f2e5d50bbf709095875b31b010833c9bdf098d2246d0bc129a634`
- ZIP SHA-256: `6f070e67545a558c8c7bccb4c5939da2eaa91086d7b0b93d313e6c80f26f49a2`

The accepted v48 NRO and active runtime were not changed. This verifies a
reproducible test package; Switch playback and gameplay regression acceptance
remain pending. The asset audit's `scene_enabled: false` describes the CPK-only
audit: runtime activation additionally requires this NRO, the marker and both
adapter preflights.

## First Switch test

1. Play an Exhibition with the same faces, graphics and camera used for v48.
   Confirm the existing intro, normal half-time/result and gameplay pacing.
2. Create a disposable **Custom Cup with two teams**, Barcelona and MU, one
   human slot and one leg. Its only fixture is the final. Choose the shortest
   exposed match duration and win in normal time.
3. Let the ceremony finish once. Check the correct winner and captain, visible
   cup/podium, camera, return to results/bracket and the following match.
4. Repeat with a COM win, a penalty-shootout win and Skip during the ceremony.
   Verify the saved winner and the return to the accepted gameplay frame rate.

Do not corrupt an installed PAK to simulate a failed load. Offline tests cover
timeout, stale completion, owner replacement and fallback; controlled hardware
fault injection would be a separate diagnostic candidate.

Keep a short clip plus `trophy-runtime.log`, `scene-runtime.log` and
`VERIFICATION.json`. If the trophy does not appear, the lifecycle log separates
package/ABI rejection, ineligible result, missing mesh and native scene start.
The broader acceptance matrix remains in
[the ceremony test plan](TROPHY_CEREMONY_TEST_PLAN.md).
