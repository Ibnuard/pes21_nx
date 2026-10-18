# Trophy ceremony: readiness and test handoff

## Status on 2026-10-18

The user reports that the **current entrance/intro works**. Retain that runtime
as the baseline. This does not identify or approve the separate FL26 walkout
candidate from 2026-10-15. The accepted v48 rendering NRO is also a baseline,
not a trophy-enabled NRO.

The ceremony work has working asset preparation, rigid-prop cooking, native
compatibility probes, a read-only live Cup-final query and a pure result policy.
**There is still no playable trophy update.** The prop backend is probe-only;
the runtime does not include it or redirect the result factory. Finishing a
Cup with the current NRO is not a test of the new trophy assets.

| Part | Evidence | What remains |
| --- | --- | --- |
| Trophy scene/motions | Detached `dt220` stage; native entrance and unrelated members retained; 69 sampled poses recorded | Actual scene playback, camera and parenting |
| Cup and podium | Cooked static meshes and scoped PAK; retained oriented geometry/UV audit | Appearance, mesh completion and real renderer lifecycle |
| Cup-final eligibility | Host tests exercise the real frontend, including native HOME/AWAY swap | Capture fresh native phase/teams/scores at the final-result call |
| Winner policy | Host tests cover normal goals, separate shootout scores, rejection and one-shot acknowledgement | Invocation-scoped registry access and a live monotonic match token |
| Prop backend | Bounded native ABI/ownership probes; defaults inactive | Serialized mesh-completion observer, timeout and cleanup |
| Native ceremony | Not connected | Factory handoff, failure fallback, Skip/destructor and FPS restoration |

The detailed source evidence and conversion limits are in
[FL26 cinematics](FL26_CINEMATICS_CANARY.md). Native ABI probes with simulated
callbacks do not establish engine thread ownership or running-scene behavior.

The 2026-10-18 local audit passed both asset checks: 28 authored trophy
payloads, 2,471 unrelated CPK members byte-identical, and all 14 PAK members
matched after a fresh integrity test and unpack. The retained cook audit
describes a 19,664-triangle cup and 331-triangle podium. These are props for
the ceremony, not replacements for player heads. Device cost is unmeasured.
The resulting status is `assets_verified_runtime_pending`, not playable.

## Repeatable offline audit

All generated files stay under the ignored `local-debug/` on D. No OBB is
duplicated, no save is edited and no runtime is installed. Use the host's
existing cache setup before the commands:

```powershell
. D:/PESNX-Cache/use-cache.ps1
python -B tools/audit_trophy_candidate.py `
  --trophy-report local-debug/trophy-assets-20261015-v1/trophy-report.json `
  --package-report local-debug/cinematic-props-cook-20261015-v3/package.local.json `
  --cooked-audit local-debug/cinematic-props-cook-20261015-v3/cooked-audit/cooked-audit.local.json `
  --repak C:/Users/Administrator/.cargo/bin/repak.exe `
  --unrealpak D:/UE_4.22/Engine/Binaries/Win64/UnrealPak.exe `
  --output local-debug/trophy-readiness-new-run
```

These local fixture/tool paths are optional inputs, not files supplied by the
repository. Use a **new** output directory on each run. The audit rechecks:

1. The full V2 baseline, detached CPK/manifest pair, all unchanged CPK members,
   IDs/order and the entrance table. It reconstructs the authored ending and
   retained motion dependency plan from the same owned donor archive.
2. Prepared source hashes, retained geometry measurements, current cooked
   hashes, both shader versions, exact PAK membership, `UnrealPak -Test` and
   every unpacked payload hash. Retained measurements remain distinguished
   from a fresh geometry export or hardware observation.
3. The explicit missing runtime steps. Successful assets never set
   `ready_for_switch_trophy_test` or `production_ready` to true.

Exit codes: `0` means **offline assets pass**, `1` means an asset/input check
failed. Add `--require-playable` for an integration pipeline: it returns `2`
when assets pass but playable integration is still pending. Consult
`readiness-report.json`; a green asset check is not an install instruction.

For fresh geometry measurements, run `validate_cinematic_props_cooked.py` with
the same preparation and cooked roots, an owned local UModel executable and a
new output directory. Pass its resulting report to the readiness audit.
The staging tool also now returns failure if an explicitly requested
`--sample-native-elf` decoder check fails; asset staging alone cannot mask it.

Run focused regression tests without any game input:

```powershell
python -B -m pytest tests/test_audit_trophy_candidate.py tests/test_fixdemo_ceremony_policy.py tests/test_fixdemo_prop_bridge.py tests/test_fixdemo_prop_backend.py tests/test_cup_frontend_flow.py tests/test_stage_trophy_ceremony.py tests/test_stage_entrance_walkout.py tests/test_cinematic_props_fbx.py tests/test_cook_cinematic_props.py tests/test_prepare_cinematic_props.py tests/test_validate_cinematic_props_cooked.py -q
```

The same suite has explicitly optional native-ELF/Blender checks. Missing
fixtures must be reported as skips, never recreated in the public tree.
Set `PESNX_TEST_BLENDER` to the existing Blender executable to exercise its
synthetic split-normal/UV regression.

## Implementation gates before a Switch trophy test

Complete these in order. The production activation gate remains disabled
until the implementation and its device tests establish the missing behavior.

1. **Mesh completion and lifetime:** observe the native serialized load/bind
   boundary. Check the exact cup/platform name, actual component-bound mesh,
   owner, load key and current scene token. Actor existence and the native
   `IsReady` flag alone are insufficient. Bound waiting by both frames and
   elapsed time; keep failures hidden, release only the still-owned object,
   invalidate before teardown, and reject late completion after replacement.
2. **Final-result capture:** use the audited full-time caller, actual END
   phase and an invocation-scoped native registry lifetime. Check current
   logical-to-physical team mappings, fresh match goals and separate shootout
   goals against the live standalone Cup championship final. Exclude halftime,
   third place, simulations, already recorded results and other game modes.
3. **Native ownership/fallback:** create one candidate with the real winning
   captain assignment and native root/parent transforms. A failed candidate
   restores FPS and releases its own resources before the original result
   factory is used once. Do not consume the success latch on allocation alone.
   Preserve native virtual execution, deletion, Skip and the next-match path.
4. **One installation pair:** create one CPK/manifest package against the
   accepted installed baseline, including its actual entrance. The detached
   entrance and trophy candidates both replace `dt220` and its manifest;
   independently copying one over the other silently loses the other change.
   Pin NRO/CPK/manifest/PAK hashes and ship rollback instructions together.

None of these steps requires lowering face quality, changing the graphics
mapping or modifying tournament/save formats. There should be no additional
per-frame prop observer work outside an explicitly active ceremony candidate.

## Device test sequence once an integrated candidate exists

This is the future acceptance procedure, **not a test that the current
asset-only PAK can pass**. Keep the accepted installation/save as a recoverable
baseline and use a disposable Cup save. Start in Konami Stadium with the same
graphics, faces and camera as the accepted 60 FPS setup.

1. **Control:** play an Exhibition with the integrated candidate; check the
   working intro, gameplay and ordinary result page. No trophy should appear.
   Also observe halftime; it must use the ordinary scene.
2. **Shortest final:** create a Custom Cup with two teams (Barcelona and MU),
   one human slot and one leg. Its only fixture is the championship final.
   Use the shortest exposed match duration and win in normal time. The real
   winning captain should lift the visible cup over the podium once; the
   teammates, camera, kit and winner must match. Let it finish naturally.
3. **Opposite result:** repeat with the human losing. The COM winner still
   receives the trophy. Repeat a human-vs-human final to cover established
   native HOME/AWAY reordering; selecting the correct winner must not depend
   on starter index zero or the on-screen HOME label alone.
4. **Shootout:** draw with penalties enabled, then determine a winner in the
   shootout. The ceremony must use shootout-only goals to break the match tie,
   and the saved bracket/result must remain correct after return.
5. **Skip and cleanup:** repeat a final and Skip during the ceremony. Reach
   the same result/bracket flow, then start another match. Check cameras, HUD,
   ball, player visibility and the restored gameplay frame rate. Repeat with
   natural completion so both teardown routes are covered.
6. **Negative selection:** in a four-team Cup, verify semifinals and third
   place have no trophy. Simulated/COM-only fixtures and returning to an
   already completed Cup must not replay the ceremony. League, Master League
   and Exhibition behavior must remain unchanged.
7. **Failed load canary:** only a future diagnostic candidate with an explicit
   fault-injection option should test delayed/missing mesh, timeout, owner
   replacement and scene cancellation. Each must recover through the ordinary
   result path without a floating/invisible cup, hang, duplicate owner or
   retained FPS change. Do not simulate this by corrupting the active PAK.

After these pass, repeat natural completion and Skip with Low/Standard/High,
different teams/kits, and two consecutive matches. Record full package hashes,
Cup type/team ownership, final score plus separate shootout score, graphics,
completion/Skip, winner/captain, and before/after frame pacing with each clip
and log. The current `cinematic-trace.log` observes entrance callbacks only;
it cannot prove a trophy loaded or completed. An integrated candidate needs
bounded trophy lifecycle events before those log-based assertions can pass.

## Checkpoint scope

This source checkpoint preserves the conversion/staging automation, tests and
documentation, plus their minimal frontend/policy/bridge source dependencies.
Those helpers do not install runtime hooks. No trophy PAK/CPK, donor payload,
raw disassembly, save or generated NRO is committed or deployed by this audit.

Validation on 2026-10-18: **257 focused tests passed**, including the synthetic
Blender check, optional native ABI/bounded probes, Cup/League flows and Master
League transition/adapter regressions. This is not the full repository suite
or a Switch test. The public-tree audit passed. The accepted v48 NRO remains
byte-identical (SHA-256
`b6419c1e45f7e58ee49ba5aae66eea845096628875a74effb8c069e337ee35b5`);
no new runtime NRO is needed to use these offline tools.
