# Remaining pacing after v43 device feedback

On 16 October 2026 the user reports **no whole-player blinking in either v43
cache mode**. That is device feedback for these runs, not proof that cache
suppression caused or cured the previous disappearance. Preserve v41-7k face
detail and the Barcelona/Manchester United pilot.

The supplied normal-cache log records Konami, DAY/FINE, season 0, quality 2,
teams 108/100, native Dynamic Wide (camera 5), 1024x576. Its whole-play report
contains 4,503 intervals, mean 18.176 ms and 609 intervals above 20 ms. The
single worst interval is 164.050 ms. Region timings are:

| Region | Frames | Mean interval | Presentations/s | Above 20 ms |
| --- | ---: | ---: | ---: | ---: |
| Centre/middle | 1,254 | 17.708 ms | 56.47 | 8.37% |
| Centre/right | 489 | 17.998 ms | 55.56 | 10.43% |
| Near/middle | 2,255 | 18.408 ms | 54.32 | 16.63% |
| Near/right | 407 | 18.849 ms | 53.05 | 18.43% |

At near/middle, timed draw calls consume 2.574 ms and buffer uploads 1.605 ms
per frame; first-draw-to-swap span is 14.811 ms. Sampled GPU stream span is
4.925 ms over 75 samples. These overlapping observations are not additive CPU/
GPU utilization or proof of the dominant bottleneck. In particular, the
unclassified part of the CPU frame must not be labelled skinning without a
measurement. The mean interval needs about 1.74 ms less work/wait to reach a
16.667 ms frame budget in this region.

All 25 load records have resolved nonempty face/hair meshes and one available
LOD, including Gerard Martín and Senne Lammens. The records include three
native-ID-zero referee loads. Across all recorded regions, 188,166 map and
188,166 unmap calls report no failure. GL error checks are **zero**, so the zero
error count does not certify error-free rendering. These are observations on
the presenting thread, not every loading context.

The supplied **bypassed log has load records but no presentation windows**.
Its performance cannot be compared with the normal-cache run. The analyser's
new opt-in `--allow-partial` preserves its load data and records timings as
unavailable; strict mode still rejects missing measurements. No zero timings
or FPS values are invented.

## Quality-preserving wrapper change

The compatibility clock and pthread TLS get/set shims unconditionally updated
global trace counters even when `debugPrintf` was compiled to a no-op. Every
successful TLS read therefore still executed a sequentially consistent global
read/modify/write; multiple engine threads shared that cache line. v44 compiles
those three logging counters and updates only under `DEBUG_LOG`. Clock values,
Android key validation, thread-row lookup, isolation, identity, scheduling and
game synchronization are unchanged. Debug builds retain their original logs.

The focused C tests execute the production functions. They verify no release
trace RMW over 100,000 TLS reads and 10,000 clock queries, preserved clock/error
semantics, null/delete behavior, table exhaustion, Android identity changes,
four concurrent colliding thread identities and retained debug logging.

`tools/benchmark_compat_tls.py` reuses the authored shim block. On this host,
three trials of eight million lookups across four threads give median aggregate
cost 24.86 ns/lookup before and 13.56 ns after. Single-thread median is 44.53 ns
before and 42.88 ns after. This is synthetic host throughput, **not Switch FPS**
or a prediction of how much of the game's frame budget will be recovered.

## Candidate and acceptance

The primary `update` NRO is an ordinary build with per-draw/GPU diagnostic
probes absent and normal GL caching enabled. It ignores the v43 diagnostic
control file. A separate diagnostic NRO/control is provided only for a detailed
follow-up. Keep the exact same face PAK and game settings for device comparison.
Pause before preserving the runtime log; its header identifies v44.

`tools/package_pacing_runtime_candidate.py` validates both NROs against their
ELFs/runtime pair, hashes package files and emits an ignored local ZIP. No face,
hair, material, texture, triangle, stadium, OBB, CPK, roster or save is changed.
The package records stable 60 FPS as **unverified** until measured on Switch.

## Verification and local output

Production and diagnostic devkitA64 builds succeeded serially with the same
runtime pair `e861c583ec78e9ae` and 53,248-byte dummy OBB requirement. Both
ELF/NRO segment comparisons and FNX icon checks passed. The focused suite
passed **31 tests and 41 subtests**; the public-tree audit passed 1,092 files.
ZIP CRC and all recorded package hashes passed independent readback.

The compiled wrapper confirms the intended change: the clock and TLS getter
each lose their exclusive load/store pair; the setter retains its legitimate
cold row-claim pair and loses only the extra logging pair. Both TLS trace
counter symbols disappear from the ordinary ELF. No game-library patch is used.

- ZIP: `local-debug/face-pacing-v44/FootballNX-Pacing-v44-TEST.zip`,
  89,256,806 bytes, SHA-256
  `e13e24e03ddcd351d4723587472b59638d998fe75398d310f96eb0df478ff72b`.
- Ordinary NRO SHA-256:
  `e37bef496d7ac4cfeeb884897eed92d15ec1739535d57b25327351ff5f7e2b05`.
- Diagnostic NRO SHA-256:
  `381ae81eaa547625ac8d1b884e9d7bee1b1b5f46fc12f518df6ca799e7b7f8ca`.

The active prepared runtime, supplied logs and v41 face PAK remain untouched.
