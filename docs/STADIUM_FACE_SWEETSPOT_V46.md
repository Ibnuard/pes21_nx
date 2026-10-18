# Residual Stadium pacing: wrapper and balanced-head candidate v46

The 17 October 2026 supplied journal identifies v45 and Konami at 1024x576.
The user reports a large improvement, with residual pacing particularly in
native STADIUM. The log is an ordinary build: no camera IDs, lineups, quality,
draw/upload breakdowns or GPU samples were recorded. Do not attribute its
individual windows to a particular camera or treat it as a matched v43/v44 A/B.

| Time | Recorded intervals | Weighted mean | Presentations/s | Above 20 ms |
| --- | ---: | ---: | ---: | ---: |
| DAY/FINE | 5,331 | 17.607 ms | 56.80 | 9.323% |
| NIGHT/FINE | 17,406 | 17.524 ms | 57.07 | 8.417% |

The mean needs about 0.9 ms less work/wait to reach 16.667 ms, but these logs
do not identify its dominant contributor. The native entrance reveal callback
ran in both sessions; this event alone is not proof of displayed preview pixels.
The original log and its SHA-256 analysis are preserved in ignored output on D:.

## Further wrapper overhead

`glBlendFuncSeparate_c` previously always called the driver and invalidated the
two-factor blend cache. v46 suppresses consecutive identical four-factor
requests in native thread-local context state. RGB and alpha are compared
separately. The two-factor setter invalidates the new cache; the four-factor
setter invalidates the old one. Real context changes and every swap retain
the existing complete reset, covering the wrapper overlay's direct GL calls.

Only common GLES factors are eligible. Constants, unknown/extension factors
and invalid saturate destinations remain native calls, including repeated
invalid requests. Imported and dynamically resolved setters share one route.
Texture and program binds still execute, preserving shared-context acquisition.
No shader, visibility, animation, draw count, resolution or face asset changes
are part of the wrapper candidate. Earlier accepted v44/v45 fixes remain.

The optional diagnostic adds RAM-only `blend_requests` / `blend_skipped`
counts to the existing per-camera/per-region report. They count separate-factor
requests only, are summed as absolute counts, and are written outside live
play. Production omits these counters. No synchronous GL query or GPU wait is
added. Call suppression is established by executable host tests; device
milliseconds recovered remain unmeasured.

## Measured-quality geometry preparation

The v41-7k test contains 50 heads at 4,315–6,932 triangles (mean 5,795.28).
The next experiment targets 5,000 complete-head triangles, retaining the same
identities, two sections, opaque 256px face/eye atlas, 128px masked hair, rig,
eye handling, neck locks and existing geometry/UV/normal/hair coverage gates.
The legacy global 2k recipe is not used.

`realface_budget_sweep.py` tries skin allocations of 3,000, 2,800 and 2,600
triangles within the same complete-head budget. A face/UV surface failure is
held immediately. Budget or hair-coverage failures can retry distribution,
without relaxing thresholds. The accepted baseline's per-player facial-hair
lock policy is retained: applying this lock to every scalp unnecessarily
overconstrains Yamal and is not equivalent to the accepted v41 policy.

Preparation yields 46 heads within 5,000; four of those already met the target
and reuse their accepted cooked bytes. Four difficult reductions are held and
retain their exact verified v41 originals to keep the comparison's real-face
coverage constant:

| Retained original | Triangles | Reduction hold |
| --- | ---: | --- |
| Joshua Zirkzee | 6,932 | Protected hair cannot reach the target |
| Alejandro Balde | 5,962 | Hair coverage misses the unchanged quality gate |
| Leny Yoro | 6,462 | Protected hair cannot reach the target |
| Ayden Heaven | 6,132 | Protected hair cannot reach the target |

The 50-head preparation totals 248,021 triangles, **14.41% fewer** than v41,
mean 4,960.42. Its actual maximum remains 6,932. This is a **balanced 5k target
with four explicit retained originals**, not a strict 5k maximum or proof of
an FPS gain. Koundé and eight unresolved identities retain the same nine
native fallbacks as v41; no new native fallback substitutes for a heavy head.

Retained originals require the pinned baseline verification hash, identical
identity/preparation/cooked keys, original cooked folder and exact triangle
count. Newly reduced heads must pass the ordinary target ceiling. The original
failed attempts remain in `reduction-report.json`; exceptions are listed in
`retained-originals.json` and release verification/CSV. No new over-budget
geometry is approved by a retained-original entry.

## Reusable serial workflow

All proprietary inputs are optional ignored local files. Reuse the legally
supplied canonical inputs and pin the accepted v41 report; do not copy OBBs.

```powershell
. D:/PESNX-Cache/use-cache.ps1
python -B tools/realface_budget_sweep.py --baseline-config <v41-config> --output local-debug/<trial> --cap 5000
python -B tools/realface_budget_sweep.py --baseline-config <v41-config> --output local-debug/<trial> --cap 5000 --retain-accepted-holds
python -B tools/run_realface_budget_trial.py --config local-debug/<trial>/5000/config.local.json --output local-debug/<trial> --cap 5000 --from-phase cook --import-chunk-size 12 --baseline-stage <pinned-material-stage> --baseline-verification <pinned-scope-verification>
```

Preparation, editor imports/cook, independent validation and previews run
serially. Successful hashes and deterministic failed attempts are cached.
The same sweep supports an explicit 4,500 target, but 5,000 is the first device
comparison. A global 4,500 release has not been selected from these logs.

Compare the v46 ordinary NRO with the unchanged v41-7k PAK first. Then change
only the face PAK to the balanced target using the same NRO and lineup. Test
native STADIUM near/far in DAY and NIGHT separately; Pause and preserve a log
per run. Diagnostic camera 6 identifies native STADIUM and adds draw/upload,
GPU stream-span and actual blend savings counts. Diagnostic timings must not
be treated as ordinary-build performance. The accepted v45 NRO and v41 PAK
remain rollback controls. Stable 60 FPS and runtime visual acceptance require
Switch testing before selecting a sweet spot.

## Local face-package verification

All 50 heads pass independent cooked validation (42 new, eight reused).
The 605-file payload passes UnrealPak testing and independent unpack/hash
comparison. An additional readback checks the ZIP CRC, every packaged file,
all 50 identities and identical v41 bytes for the eight reused heads. The
59-row status CSV includes the same nine native fallbacks; the 50-row budget
CSV records face/hair triangles, vertices, sections and retained originals.
Pilot front/left/right/above previews use prepared meshes with decoded cooked
textures; they are offline appearance evidence, not runtime captures.

- Face release: `local-debug/face-balanced-v46/5000/test-packages/f82ce06cef07fed7/release`.
- Face ZIP: `FootballNX-Barca-MU-v46-balanced-5000-TEST.zip`, SHA-256
  `8f4ed3bc8fa2ff9049c74e9509ab1aaea3e227ba1d32a6ec7115eae2c27fc1c0`.
- PAK: 8,868,422 bytes, SHA-256
  `30d2df2b41f0acef190d0b41764a60bfd52dbcfde98d91dbc500d711c9675eb1`.
- Focused source/tool validation: **75 tests passed**.

The recipe is a device-test candidate. A smaller archive and successful
offline verification do not establish a 60 FPS lock or runtime appearance.

The 50 front previews and all 12 pilot views were reviewed. No missing face,
eye, neck or texture surface was seen in these offline views; minor facial
detail differences and the existing card-style hair remain. The side-by-side
pilot image and hashed `VISUAL-REVIEW.json` stay beside the ignored experiment.
These findings do not approve native animation, gameplay visibility or FPS.

Both v46 devkitA64 builds succeeded with the same runtime pair
`e861c583ec78e9ae` and existing 53,248-byte dummy OBB requirement. FNX icon,
ELF/NRO segment comparison, ZIP CRC and package-file hash readback passed.
The ordinary binary omits the new diagnostic count fields; the diagnostic
binary includes them. The public-tree audit checked **1,100 files**. The
active prepared runtime and original v41 PAK were not modified.

- Wrapper ZIP: `local-debug/face-pacing-v46/FootballNX-Pacing-v46-TEST.zip`,
  89,258,366 bytes, SHA-256
  `d9df8ae9e6dc43d771f82c35fd8b264483405deeda5ba067a8c3dba77f1ae775`.
- Ordinary NRO SHA-256:
  `02ead0a5e89e81d28ea9ac3b58077bfddf114c39a3d294fc8ee6457f78e01983`.
- Diagnostic NRO SHA-256:
  `a41811a675299bc441f941c423b2f2256b00f7e18ae6103073b3c5166563eb72`.

`local-debug/face-pacing-v46/TEST-MATRIX.txt` records the controlled A/B/C order
and the original NRO/PAK rollback. 4.5k remains an available explicit sweep,
not the selected production policy; assess the 5k-target/device comparison first.
