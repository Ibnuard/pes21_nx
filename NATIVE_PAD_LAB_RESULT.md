# Native Pad Lab device result

Status: **rejected on Switch, 1 September 2026**.

The experimental tile reached a one-player match, but Joy-Con input produced
no player response. The same experimental NRO also regressed the accepted
runtime presentation: the `Player Cursor` setting was no longer reachable,
native set-piece action buttons were visible again, and custom helper colors
were absent.

The device result proves that the v14 path is incomplete, not which individual
gate failed. Subsequent inspection found that ThinkUnitList selects MobileShoot,
MobilePass, MobileDribble and MobileFreeMove. Those remain mobile consumers even
when the real-pad history is populated. Pad::Update already connects the main
pad automatically; a missing IsConnected override was not established as the
cause.

The missing visual features have a separate, confirmed packaging cause:
prepare_visual_runtime_build.py copied an older v1.98 snapshot and applied bare
`git diff`, omitting changes already committed. Staging now requires both an
explicit snapshot and a Git delta base. A regression test covers committed
plus uncommitted changes.

## V2 device result / Native Mapping Baseline V1 - 1 September 2026

Package: `local-debug/native-pad-lab-v2-20260901/install/pes21_nx.nro`.
The exact binary was device-verified for native live-play and promoted without
a rebuild to `local-debug/native-pad-v1-baseline-20260901/`. It is the initial
native mapping baseline, not yet a complete native set-play implementation.

- Built from the accepted visual-v9 runtime snapshot, not the failed v14 NRO.
- Lab-only PLT wrapper changes the selected mobile actions to existing native
  actions, using their own objects and native input history. Original context
  scheduling and command dispatch remain in control.
- Requires the local home player and cursor pad 0; away CPU and Exhibition pass
  through unchanged. Runtime vtable checks reject an incompatible layout.
- Native sampling is observed, not fabricated. The old synthetic FriendPress
  adapter is disabled only in Lab so Y cannot give a false native-input result.
- On-screen Lab-only milestones: HID / PAD / OWNER / ROUTE. These diagnose the
  path but do not by themselves prove that a player responded.
- Device-confirmed combinations include R2 controlled/finesse shoot, L1+X
  match-up and L1+Triangle lofted through ball. Defensive second-player
  pressure is routed but still awaiting a device test.
- The shoot power indicator, goal kick, corner and throw-in are confirmed route
  gaps. Set-play still selects mobile swipe consumers while Lab touch fallback
  is disabled. Native CornerKickTactics exists but is not scheduled by V1.
- No new second-controller support; penalties and right stick remain outside
  this initial native live-play baseline.
- Build is release (`DIAGNOSTICS=0`, `PERF_TRACE=0`); no per-frame log/file I/O.

Validation: 28 Python tests, host C routing tests (also UBSan), visual policy
and FriendPress tests passed. Owned-ELF audit verified 24 unit types, two PLT
entries and native key mapping. Staged-runtime audit checked retained camera,
cursor, opacity and helper code; config/render/allocator/data files are unchanged
from the stable snapshot. V14 pitch hash is unchanged.

See [test instructions](local-debug/native-pad-lab-v2-20260901/README.md).
See [accepted V1 scope](NATIVE_MAPPING_BASELINE_V1.md).

Stable production combination:

- runtime: visual v9 / release v1.98 NRO;
- pitch: visual v14 PAK;
- package: `local-debug/visual-v14-stable-20260901/install/`.

## Kandidat Native Setplay V3 - goal kick

Iterasi berikutnya sudah dibangun terpisah di
`local-debug/native-setplay-v3-20260901/`. Route goal kick stock dideteksi dari
MobileSetplayKick + GoalkickPassSupport, lalu unit mobile kick/camera diganti
dengan SetplayGuide, ShortPass, LongPass, dan Shoot native; support native
dipertahankan. Overlay mencatat tombol live, PadInput history, event ThinkUnit,
dan command return agar hasil Switch dapat dilokalisasi tanpa tebakan.

Kandidat ini belum stable dan belum mengubah corner, throw-in, free kick,
power-gauge visual, maupun 2P. Detail: [NATIVE_SETPLAY_V3_TEST.md](NATIVE_SETPLAY_V3_TEST.md).

## Kandidat Native Setplay V4 - LS aim + RS camera

V4 menggantikan V3 sebagai kandidat aktif di
`local-debug/native-setplay-v4-20260901/`. Input Right Stick sekarang ditulis ke
axis 2/3 `cobra::game::Pad` dan teramati sebagai StickKind 1 pada history
`PadInput`; Left Stick tetap memakai axis 0/1 untuk `SetplayGuide`. Route yang
sama diterapkan secara kontekstual pada goal kick, corner, dan free kick.

V4 sudah lolos 30 tes Python, host routing C, audit 32 unit ABI, audit layout
dual-stick, dan build NRO release. Kamera aktual masih memerlukan tes Switch;
nilai overlay `RPOW` membuktikan apakah RS sudah sampai engine sebelum menilai
consumer kamera. Detail: [NATIVE_SETPLAY_V4_TEST.md](NATIVE_SETPLAY_V4_TEST.md).
