# Stadium acquisition correction v57

The user reports the selected native Stadium camera leaving a keeper with the
ball, moving towards a goal on a turnover, and failing to frame a backpass to
the keeper. V57 changes the live Stadium target acquisition boundary. It is a
device-test candidate, with no claim that all three reports are resolved.

## Evidence and scope

The owned Mobile ELF SHA-256 is
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
Local static inspection identifies `GetBallPositionBroadcast` at `0x665bfe4`:
it reads keeper/last-touch state, team/player positions, screen projection and
future-ball data before returning an acquired target. `ShotBroadcastBallActive`
can then substitute another player position. Consequently its target need not
be the current physical ball.

At `ShotBroadcastBallActive + 0x6d0`, the engine has completed those selections
and already sampled `BallInfo::GetTrans`. The existing audited trampoline has
the acquired target at stack offset `0x130`, the sampled ball in `x26`, and the
camera in `x21`. It preserves the live integer/SIMD registers, NZCV and FPSR,
then replays four displaced loads. The exact instruction guard is retained.
V57 shares that acquisition boundary with the suspended V2 implementation;
the V2 preset, custom trace and custom interpolation remain disabled.

Only a normal Stadium update (live ID 6, tmpdb type 12) with a current gameplay
HUD, no player-follow and no V2 flag admits the correction. Match phase 1 is
checked at the target callback, after native Update acquires its current
MatchInfo registry copy. The callback copies just the three target floats
from the sampled physical ball. It retains no pointer, velocity or history.
Invalid inputs fall back to the unmodified target. The thread-local scope is
cleared before and after every Update; other camera owners, replay, demo,
pause, result and set-piece phases remain native.

Native height shaping, projection, bounds, screen margins, tracing, smoothing,
zoom, transition counters and final eye/look construction still run. V57
does not place the ball at the screen centre or directly write a final pose.
Native future movement passed into the downstream tracer is also retained;
the patch does not claim to remove every predictive part of the camera.
No per-frame allocation, file I/O, registry lookup for a second ball sample,
GPU synchronization or gameplay mutation is added.

## FL26 comparison and limits

The owned `FL_2026.exe` SHA-256 is
`7c27ecb303b71331e36f9ccd8ac879f0f0d8c56c754bd4d0d2e9c8353464f847`.
The prior [v33 table audit](FL26_NATIVE_CAMERAS_V33.md) establishes equality of
the 440-byte Stadium table. A bounded local Capstone/PE-unwind-table inspection
also identifies PC `ShotBroadcast` at RVA `0x8a57f0`, its active-ball routine at
`0x8a5b60`, and contextual target selection at `0x8a4730`. The PC routine also
uses keep/last-touch, team direction and event state. These observations do not
establish that the reported behavior exists only on Mobile, or that these PC
branches execute identically in every match.

REA opened and identified the same PC executable, but native procedure analysis
is unavailable because no supported native provider is configured on this host.
The focused assembly observations are local static evidence, not REA native
decompilation or observed PC execution. No provider was installed and no PC
game process was started. Raw instructions remain in ignored
`local-debug/stadium-camera-v57/`. V57 is an authored target policy, not a full
FL26 camera transplant or a new port of PC executable code.

## Validation and device procedure

Host policy tests cover both keeper ends, backpasses, turnovers and aerial
balls, all other IDs/presets, stale/replay HUD admission, non-live phases,
invalid samples, owner mismatch, in-place copying and scope cleanup. Adapter
tests check that MatchInfo is read after the original Update acquires it,
native Update runs once and all output outside the target remains native.
The existing AArch64 trampoline oracle checks full register/stack preservation
and optional no-op equivalence with the owned Mobile bytes.

The eight focused camera files pass **19 tests** with the local native fixture
available. The strengthened callback/Update test also passes after adding
invalid-ball, null-input and unavailable-original cleanup cases. These are host
checks; no Switch recording has been inspected for this revision.

```powershell
python -B -m pytest tests/test_stadium_camera_policy.py tests/test_stadium_camera_runtime.py tests/test_stadium_v2_hook.py tests/test_stadium_camera_anticipation.py tests/test_stadium_v2_camera.py tests/test_stadium_v2_native.py tests/test_camera_choice_policy.py tests/test_stadium_diagnostics.py -q
```

On Switch select **STADIUM**, and test keeper catches at both ends, backpasses,
rapid possession changes, passes along both touchlines and high balls. Repeat
in single-player and local two-player, then check pause/resume, goal/replay,
goal kick and rematch. Check that native zoom and smooth pan remain present;
record any remaining goalward lead separately. These host checks do not prove
subjective camera behavior or Switch FPS.
