# Wrapper overhead and native stadium preview v45

On 16 October 2026 the user reports a large improvement from v44, with residual
pacing most visible in native STADIUM when many objects are on screen. This is
device feedback, not a new measured v44 frame-time log. Keep the accepted v44
clock/TLS logging fix and the unchanged Barcelona/MU v41-7k face package.

## Changes with a source-level cost argument

`gettid_fake()` previously called `svcGetThreadId` on every request, including
`syscall(GETTID)` and the existing compatibility `GETCPU` route. A successful
Horizon current-thread ID is constant for that native thread. It is now cached
in native TLS. Failures and zero IDs still return the existing fallback and are
retried; successful IDs retain the exact original 31-bit conversion, including
a possible zero after masking. New native threads receive fresh TLS storage.
This removes repeated kernel transitions, without changing thread scheduling.
The game’s actual call frequency and milliseconds recovered are not measured.

The authored Nouveau buffer pool searched free ranges to find the first fit,
then searched the chosen list again to recover its link. Free insertion also
walked from the head a second time to rediscover the predecessor. Both now
retain the already discovered pointer while holding the same mutex. Selection
order, alignment, splitting/coalescing, range/handle ABI, BO references,
fence-deferred free callbacks and the one-warm-slab policy are unchanged. This
removes duplicate list traversal; it does not establish that the allocator is
the dominant STADIUM bottleneck. No GPU synchronization is removed or bypassed.

The normal gameplay callback also used an atomic exchange to clear the already
zero loading-cover flag on every update. An acquire check now avoids the write
when unarmed; the exchange remains for the actual one-time reveal transition.

## Restore visibility of the native pre-match preview

The custom VS loading cover waited for `DemoMatchCard::NeedDisp`, a demo-skip
unit, or the live ScreenTap callback. There was no reveal on the native entrance
start callback, so an earlier stadium-preview portion could remain covered.
The v45 candidate observes `FixDemoEntrance::StartDemoEvent`: it calls the
original exactly once, then releases the armed VS cover. The existing later
card/gameplay reveal paths remain fallback paths.

Installation requires the audited 32-byte method fingerprint and the expected
native vtable slot. A mismatch makes no writes. Installation is idempotent, and
is separate from the suspended FL26 entrance canary. It does not select a scene,
patch Start/End FPS behavior, skip a cinematic, or change native cameras.
STADIUM-V2 remains suspended. Use the already restored native dt220 baseline;
this NRO-only package cannot restore a different cinematic archive on the SD.

The ordinary journal records `native prematch: entrance started; VS cover
released` when the callback sees an armed cover. An absent record requires
checking native scene selection/loading and the installed assets. Neither
static inspection nor the host lifecycle test proves that preview pixels were
displayed on Switch.

## Verification and device acceptance

The thread-ID C harness executes the real shim and syscall dispatch. Twelve
concurrent/sequential native test threads each exercise failed/zero queries,
200,000 successful requests and the GETCPU route, with exactly one successful
kernel query per thread. It includes high-bit IDs, a zero masked result,
thread reuse and isolated main-thread storage.

The pool harness covers first-fit reuse through 512 separated holes,
left/right coalescing, split ranges, allocation failures, retained BO lifetime,
bounded memory retention and competing threads. The entrance harness covers
every installation gate, native-first execution, idempotence, unrelated UI,
fallback reveal and 100,000 inactive reveal calls without an atomic write.
The native method fingerprint also matches the compatible local Mobile ELF.

`tools/package_pacing_runtime_candidate.py --version 45` verifies both build
variants, native ELF/NRO segments, runtime identity and required version
markers before packaging. It retains v44 packaging support. The primary update
uses the ordinary build; optional diagnostics stay separate. No face, hair,
texture, geometry, stadium, shader or roster quality is changed.

On Switch, keep the same assets/settings and compare with the accepted v44:
custom loading -> native stadium preview -> kickoff, without pressing Skip;
then Barça/MU, native STADIUM, near/middle and far-side play. Pause before
preserving `scene-runtime.log`. Use the diagnostic build only if finer timing
is needed. Stable 60 FPS and preview restoration remain device acceptance
items, not claims made by host tests.

## Built candidate

Both devkitA64 build variants succeeded; ELF/NRO segment equality and embedded
FNX icon checks passed. Focused validation passed **33 tests and 6 subtests**;
the public-tree audit checked 1,096 files. Compiled `gettid_fake` in both v45
variants has a cache-hit return before `svcGetThreadId`; v44 always entered
that kernel call. This machine-code check is not a device performance sample.
The unchanged v41-7k PAK SHA-256 was verified against its original release.

- Local ZIP: `local-debug/face-pacing-v45/FootballNX-Pacing-v45-TEST.zip`,
  89,258,180 bytes, SHA-256
  `62db73c8ee66afd9a4668dcaa2e8cc93bb8d90b1df2d86097056a87fdbd2319c`.
- Ordinary NRO SHA-256:
  `1ae8999baaabe7b76c54797edafce704a76647d1da06f0706cda4253d7718cdc`.
- Diagnostic NRO SHA-256:
  `191785b5f9d1aff0a45d8687e51814f70f4dd4228e58e510634a940ed02672c2`.
- Runtime pair: `e861c583ec78e9ae`, existing 53,248-byte dummy OBB requirement.

The active prepared runtime is not replaced. Keep the accepted v44 NRO for the
same-scene comparison and rollback.
