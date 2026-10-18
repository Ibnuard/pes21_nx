# Whole-player blinking: device evidence and render control v43

The user now confirms that **whole bodies disappear/reappear with the face
PAK active**, rather than only a face texture or hair. Preserve the accepted
v41-7k face detail and the Barcelona/Manchester United pilot. The report shifts
the next isolation to shared player rendering, visibility and buffer handling;
it does not by itself establish which of those paths is faulty.

## Supplied logs

The two files are preserved in the ignored v41 release tree. Both record the
v42 diagnostic NRO, Konami, DAY/FINE, season 0, quality 2, teams 108/100,
camera 5 (native Dynamic Wide), 1024x576. They are not the requested NIGHT/
native Stadium run, but their recorded contexts agree with each other.

| Camera region | Filename `no-paks` | Filename `with-paks` |
| --- | --- | --- |
| Centre/middle | 1,189 frames; 26.731 ms; 37.41 presentations/s | 1,290 frames; 17.350 ms; 57.64 presentations/s |
| Near/middle | 249 frames; 28.457 ms; 35.14 presentations/s | 3,476 frames; 18.129 ms; 55.16 presentations/s |

The labelled PAK run submits more geometry but records shorter CPU draw/upload
durations and sampled GPU stream spans. These logs therefore do **not** prove
that triangle count alone caused the timing regression. They also do not prove
that the PAK improves performance: exact active assets, lineup, clock/power
state and the contribution of disappearing bodies are not captured. GPU stream
spans include submission gaps and are not a pure GPU busy measurement.

All native face/hair load snapshots report resolved assets, including Gerard
Martín (native 34493) and Senne Lammens (134931). This describes load completion,
not later visible pixels. The `face_mesh=0`/`hair_mesh=0` values in **both** v42
logs are invalid evidence: the probe read only the optional override pointer.
Native `SetSkeletalMesh` writes the regular pointer at component +0x5a0; native
`GetNumLODs` first checks +0x6c0 and falls back to +0x5a0. The v43 probe follows
that order. Its C harness covers both paths and override precedence; the local
native setter test now executes both paths too.

The analyser also previously let prose `zone=camera target` overwrite the
measured region. It now parses only the measurement prefix. A regression test
uses the actual explanatory suffix and keeps centre/near measurements apart.

## Driver audit and remaining uncertainty

Bounded local ELF/object inspection used the compatible Mobile library and
the installed devkitPro `libEGL.a`, without publishing their contents. REA's
deep providers remain unavailable, so no REA decompilation success is claimed.
The installed Nouveau allocator matches the wrapper's cache/handle ABI. Its
buffer destruction and transfer paths schedule `nouveau_mm_free_work` through
the native fence-work queue; that callback receives the original allocation
handle and delegates to `nouveau_mm_free`. No premature-free fault was established
in that inspected path. The allocator is left unchanged.

v42 counted unmap calls as maps but did not cover all EXT/OES map routes.
`mapped_bytes=0` therefore cannot establish failed mapping. v43 measures core,
EXT range and OES whole-buffer mapping separately from unmap outcomes. Each
entry point retains its own driver pointer and exact arguments/return value.
Whole-buffer mapped size stays unknown instead of adding a driver size query.
Native `glGetError` returns are observed without adding or consuming extra
queries. Missing older metrics stay unknown in the analyser; new failure
counts are summed rather than averaged over frames.
Per-region outcomes cover the presenting render thread; an absence of those
faults does not establish that every asynchronous loading context is safe.

## Controlled isolation, without another face recook

The diagnostic reads `render-control.txt` **once before engine threads start**.
Only the exact `PESNX_GL_CACHE_BYPASS_V1` token disables the wrapper's redundant
state-call suppression. Missing, malformed or default control files retain
normal caching. Production builds do not read this file. Both modes retain
the same face PAK, textures, geometry, shaders, culling and animation policies.

Use the packaged normal-cache NRO/control first, then fully exit and replace
only the control file with the bypass version. Keep the PAK installed for both
runs and preserve the two logs after pausing. Record whether entire players
still blink. The header identifies the selected mode. This comparison tests
cache suppression as a cause; it does not assume that turning it off fixes
rendering, and bypass overhead must not become the new performance target.

There are no new GPU waits, readbacks, forced LOD/visibility changes or live file
writes. GPU timestamps retain v42's bounded asynchronous sampling. Outcome
counters stay in RAM and are reported outside live play. A zero GL error count
without native error checks is inconclusive.

`tools/package_render_control_probe.py` verifies the NRO against its ELF and
runtime pair, checks required v43 probe markers, hashes package contents and
creates an ignored NRO-only ZIP. It never installs files, recooks faces or
duplicates an OBB. The package explicitly records that blinking and stable
60 FPS are **not yet hardware-verified as fixed**.

## Built local candidate

The single-job devkitA64 diagnostic build succeeded, including byte-for-byte
FNX icon and ELF/NRO load-segment checks. Focused host validation passed **25
tests and 41 subtests**, including both native LOD mesh-pointer paths and the
existing pooled-buffer lifecycle checks. ZIP CRC and every recorded file hash
passed independent readback.

- Package: `local-debug/face-blink-v43/FootballNX-Render-Control-v43-TEST.zip`,
  44,633,150 bytes, SHA-256
  `0632fab051491478bed0e3f67550c5b0fe718ba285a9b5ec30137aec740ce648`.
- Diagnostic NRO: 83,862,431 bytes, SHA-256
  `8f8efa9885701f075efb8c92a593575696f09474c82dd6352ababea9ac729832`.
- Runtime pair: `e861c583ec78e9ae`, existing dummy OBB 53,248 bytes.

The active prepared runtime and immutable v41/v42 evidence were not modified.
