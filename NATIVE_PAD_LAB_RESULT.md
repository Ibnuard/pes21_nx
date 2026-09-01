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

## V2 candidate - 1 September 2026

Package: `local-debug/native-pad-lab-v2-20260901/install/pes21_nx.nro`.
This is **not device-verified or a new stable release**.

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
- No new second-controller support; special set pieces, penalties and right
  stick are outside this initial native live-play acceptance test.
- Build is release (`DIAGNOSTICS=0`, `PERF_TRACE=0`); no per-frame log/file I/O.

Validation: 28 Python tests, host C routing tests (also UBSan), visual policy
and FriendPress tests passed. Owned-ELF audit verified 24 unit types, two PLT
entries and native key mapping. Staged-runtime audit checked retained camera,
cursor, opacity and helper code; config/render/allocator/data files are unchanged
from the stable snapshot. V14 pitch hash is unchanged.

See [test instructions](local-debug/native-pad-lab-v2-20260901/README.md).

Stable production combination:

- runtime: visual v9 / release v1.98 NRO;
- pitch: visual v14 PAK;
- package: `local-debug/visual-v14-stable-20260901/install/`.
