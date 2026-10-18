# Shared-object visibility and mixed model quality v47

The user reports smoother play with the balanced 4–5k face target, but
intermittent missing/blinking players, ball, goals and stadium. Some objects
recover after an out-of-play/cinematic transition; stadium problems can
persist. Keep the tested face PAK while repairing shared rendering.

The supplied ordinary v46 journal records Konami, DAY/FINE, 1024x576 and
11,235 presentation intervals. Its weighted mean is 17.640 ms (56.69
presentations/s), 9.13% exceed 20 ms and the worst is 30.127 ms. Camera,
quality, exact lineup/PAK set, GL outcomes and visibility are absent. These
measurements cannot identify the blinking cause or establish a matched
performance improvement over an earlier run. The immutable log and analysis
are preserved under ignored local-debug/render-stability-v47/.

## Reproduced wrapper defect

overlay_render previously called glVertexAttribPointer while the engine's
vertex array was still bound. Its restore block restored attribute enables
and the global array-buffer binding, but not the per-attribute buffer, pointer,
format, integer interpretation or stride. Binding the old array buffer does
not restore those captured attribute fields. A native RHI that reuses its
cached input layout can therefore submit subsequent objects using the HUD
vertex buffer/layout. A later layout rebind can repair the state. This is a
source-level defect consistent with the reported transition recovery; the
ordinary device log does not prove it caused every missing object.

v47 creates a private overlay VAO per EGL context. It configures its position
and UV attributes once and restores the complete engine VAO after every
overlay branch, including early jumps to the common restore block. The
engine's element-buffer binding, integer attributes, divisors and all other
enabled attributes remain untouched. Successful context destruction removes
the private context key, including destruction on a different thread, so a
recycled EGL handle receives a fresh object.

Overlay draws now change only the draw framebuffer. The existing kit-preview
capture changes only the read framebuffer and restores its actual previous
read binding. These operations no longer collapse distinct read/draw targets.
The wrapper state cache is invalidated before and after the overlay boundary.
Existing v44–v46 clock, TLS, allocator and repeated blend-state improvements
remain enabled. There is no new GPU wait, readback or live-play file logging.
The kit-preview readback already existed and remains outside normal gameplay.

The host replay leaves an engine layout cached over 1,000 HUD passes and
checks all vertex formats/buffers, integer modes, pointers, strides, divisors
and the index buffer. It also covers separate contexts, reused EGL handles,
core/OES entry points and allocation/unavailable-driver failures. This proves
state preservation in the replay, not device visibility or recovered FPS.

## Exact requested quality mapping

| Setting | Player model | Stadium model |
| --- | --- | --- |
| Low | Low | Low |
| Standard | Standard | Standard |
| High | Standard | High |

The native UI values are Low=0, Standard=1, High=2. The engine class names are
APlayerActorLowest, APlayerActorLow, APlayerActorHigh respectively;
internal quality 3 also selects Lowest. Standard therefore means the class
named Low internally, not the UI Low setting.

A single checked branch in UEPlayerModel::LoadImpl redirects only the High
class factory to the same factory used by native Standard. Low, Standard and
internal mode 3 retain their exact branches. The native body-mesh decision
already treats quality 1 and 2 identically, so no second patch is required.
The shared quality getter, saved profile, stadium loader, animation, FPS mode
and global graphics/scalability settings remain native. No global skeletal
LOD override or new 2k reduction is applied. The existing face PAK is unchanged;
the appearance and cost of the Standard actor still need device review.

The patch checks all 16 bytes around the call before changing one word. A
missing symbol or mismatch applies no patch and journals a native fallback.
Installation precedes engine threads and the existing RX cache publication.
Optional local tests compare against the compatible ignored ELF, decode the
old/new branch targets, then replay the actual bounded AArch64 chooser with
stubbed external calls for modes 0/1/2/3. No proprietary bytes or disassembly
are redistributed.

REA session inventory confirmed no configured Ghidra/IDA provider and no
Hopper support on this Windows host. The native findings above come from the
repository's local ELF/Capstone reader and bounded Unicorn tests; they are not
claimed as REA decompilation or observed Switch execution.

## Device acceptance

Install the v47 ordinary NRO with the same balanced-5000 PAK, fully restart
and begin with High, Barca/MU and native STADIUM. Check ball, both goals,
players and stadium from kickoff, near-camera passes, an out-of-play event
and celebration. Test DAY/NIGHT separately and include a custom stadium.
Pause and preserve a log per run. Check Low and Standard in fresh matches.
The model quality journal row must show the mapping above, not fallback.

Use the diagnostic build only if more evidence is needed; keep diagnostic
and ordinary performance comparisons separate. The v46 NRO remains rollback.
The package includes no PAK/CPK/OBB/save update and does not modify the active
prepared runtime. Blinking across all stadiums and stable 60 FPS require
hardware confirmation.

## Local validation

The focused and adjacent rendering/UI checks passed 74 tests and 378
subtests after adapting one existing lifecycle assertion to the extended
context-destruction block. An additional pre-existing menu test fails because
it expects eight settings while the header contains nine; both conflicting
values were independently confirmed in HEAD. That unrelated mismatch is
left unchanged. The native quality tests include all four mode branches and
fingerprint failures, not only source-text assertions.

Both single-job devkitA64 builds completed with runtime pair
e861c583ec78e9ae and the existing 53,248-byte dummy OBB requirement. FNX icon
and NRO/ELF load-segment verification passed. The public-tree audit checked
1,105 files. The active prepared runtime, balanced face PAK and v46 rollback
remain unchanged.

Local test package:
local-debug/render-stability-v47/FootballNX-Render-Stability-v47-TEST.zip
(89,260,540 bytes). The ordinary NRO is under update/; diagnostic files are
optional. SHA-256 digests:

- ZIP: fdd0d4a3b13aa2dc7ebb5ceb42d01e3d6809435a759115f24ba59eaa7127f629
- Ordinary NRO: 28f0ab8a56642e7181f7fdaa16a38668e644c7483a4ec280e26e488a5b8bd9fd
- Diagnostic NRO: 02c5e3316d93f0e212f6a90ef34e6320c87cc8650a5b42d96a02c597d35af4bb
