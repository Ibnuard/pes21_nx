# Native PES21 referee candidate v54

The optional visual referee now accepts an offline bake of the owned FL26
PES21 motions. It keeps the native Mobile `HumanKindReferee`, its own 19-slot
bone buffer, the existing Low renderer policy, and native match-event timing.
This is a device-test candidate. Animation compatibility does not establish
complete PC referee AI parity or a frame-rate improvement.

## Motion conversion

`tools/convert_pes21_referee.py` reads bounded members of an owned
`Data/dt13_all.cpk`. It pins the compatible Mobile decoder and the native
animation skeleton, render skeleton and rig identities documented in
[the v53 audit](REFEREE_FL26_AUDIT_V53.md). No EF skeleton is used. The decoder
runs offline in the existing sealed animation-math evaluator; no PC executable
or game process is started.

The converter evaluates all eight clips and all 355 frames twice. The two
bakes must be byte-identical. It preserves solved world positions, removes
horizontal root travel, maps by native bone names and applies render bind
rotations. The renderer omits `sk_root_hip`; its first slot is `dsk_hip`.
It does not rebuild limbs from a different skeleton or repair invalid poses.
Native bone-length and hierarchy residuals must remain within 2 mm; this
candidate's worst measured residual is below 0.16 mm.

NXREF version 4 keeps eight clips and 19 bones. The whistle entry additionally
stores a finite, bounded wrist/head proximity interval. This candidate's
interval is 0.500–1.333 seconds, measured from the decoded motion. Native sound
requests use that interval instead of the earlier EF bake's timing. This is a
geometric proxy for the hand near the face, not an audio marker from the PC.
All payloads and timing metadata are checksum-protected and validated once at
load. Invalid or absent banks leave the optional referee disabled.

Native walk/run clips have no horizontal root travel, so their velocities
cannot be recovered from root displacement. The existing explicit playback
knots of 1.4, 3.2 and 5.8 m/s remain wrapper parameters, not recovered PC AI
constants. Legacy v2/v3 banks remain supported and identify themselves as
legacy in the log.

## PC movement constraints and Mobile ownership

[The PC controller audit](REFEREE_PC_TARGET_AUDIT_V54.md) identifies the actual
FL26 `RefereeChief` live-target routine. v54 translates its penalty-line X
limit and final diagonal Z corridor. These rules use the current Mobile
`FieldInfo` dimensions, not hardcoded PC defaults. The native v4 bank enables
them during active play; restart targets remain the existing wrapper policy.
Target selection, trajectory prediction, avoidance, movement integration,
acceleration and turn rate have not been replaced by the complete PC AI.

The compatible Mobile `GlobalRegistry::OpenRead` registers a `FieldInfo`
pointer at `+0x49e0` and supplies its read-lock pointer at `+0x4a10`. Installation
checks the actual load/destination instructions before patching. The follower
copies three scalar dimensions from that read pointer alongside its existing
15 Hz player snapshot. No field pointer survives the callback. Missing or
invalid geometry clears the copied bounds and leaves the existing target
policy available. Host tests cover those transitions and reject mismatched
layout instructions before any optional hook is installed.

Foul decisions, cards, restart selection and whistle audio still belong to
the Mobile match engine. No PC executable or DLL is loaded into the Switch
process. The existing native demo transform remains authoritative when it
provides the center referee's position. One owned Low-detail renderer and
the previous asynchronous lifetime safeguards remain in use. No live-frame
file writes or additional model spawns are added.

## Reproduction

Use D for temporary files and caches. Generated motion data is proprietary and
must remain ignored. The compatible prepared Mobile ELF is an optional local
input, not a public repository fixture.

```powershell
. D:/PESNX-Cache/use-cache.ps1
python -B tools/convert_pes21_referee.py --help
python -B tools/convert_pes21_referee.py --cpk '<owned-FL26>/Data/dt13_all.cpk' `
  --native-lib dist/pes21_nx/libUE4.so `
  --output local-debug/referee-native-v54/Animations/referee.nxra
python -B -m pytest tests/test_pes21_referee_conversion.py `
  tests/test_referee_conversion.py tests/test_referee_native_contract.py `
  tests/test_referee_projection.py tests/test_scene_canaries.py `
  tests/test_fl26_referee_audit.py -q
```

Synthetic tests cover native pose preservation, bind rotations, full motion
identities, table bounds, deterministic encoding and production C playback.
The optional native contracts verify actual Mobile hook layouts. These are
host checks; appearance and presentation timing still require a Switch test.

## Build and device handoff

The serial isolated production build retains the v53 private catalog/roster
and full-loose runtime pair `e861c583ec78e9ae`, with a 53,248-byte patch OBB.
Diagnostics and performance trace are disabled. The active prepared runtime
is not overwritten. Temporary WSL storage is backed by `D:/WSL/Ubuntu` and
Windows temporary files use `D:/PESNX-Cache`.

The selected regression run passes **105 tests and 89 subtests**, covering
referee behavior/lifetime/layouts, native bake playback, model quality,
shader/blend caches, commentary and session logging. The native model-quality
emulator also passes separately (three tests). Public-tree verification checks
1,154 files successfully. The entire optional-fixture suite was not rerun.

Build ID: `79cf4f629bf5992fc6e878d96f15f7ff29a32c19`. The NRO is
83,903,391 bytes, SHA-256
`f6afd36d8f70b8f14f9cab17fce3a79798f9a63691a6afe81cee8ab76991e554`.
Its executable segments match the linked AArch64 ELF. Source/build-input
identities, the compiled build ID and the existing commentary header allowlist
were checked against the delivered files.

The ignored local handoff is
`local-debug/referee-native-v54/FootballNX-v54-WASIT-SIAP-COPY`, with a ZIP
beside it. It supplies `switch/pes21_nx/` containing the NRO,
`Animations/referee.nxra`, the activation token `referee-probe.txt`, and the
unchanged v53 two-player commentary delta. No OBB, stadium or real-face PAK is
copied. The ZIP's CRC and every payload hash were read back and verified.
Generated artifacts remain optional local outputs and are not public inputs.

Close the game, back up the previous NRO/animation override, then merge the
package's `switch` folder into the SD root. Keep the existing installed game
and intro assets. Test Exhibition with both ordinary and STADIUM cameras,
fast changes of play, both ends, ball out, foul/free kick, goal to kickoff,
rematch and another match. Check body/foot alignment, signal transitions,
duplicate actors and presentation pacing. Save `scene-runtime.log`; the native
bank reports `Referee v54 native PES21 motions armed`.

For the performance comparison, close the game and rename the activation
token before reopening; re-enable it for the matching scene. The new motion
bank does not remove the extra actor's native rendering/GPU cost. Device
appearance and 60 FPS acceptance are still pending. Trophy lifting remains
the separate unresolved device task.
