# Roof shadow v20 — accepted checkpoint

**Accepted on device, 2026-10-11.** After testing the delivered v20 NRO, the
user reported "nah ringan nih" and requested a commit, push and checkpoint.
This records the user's improved-smoothness assessment; no numerical hardware
FPS measurement was supplied. Preserve this build as the comparison baseline.

After testing v19, the user reports improved frame pacing but continued stutter
when players play under the roof shadow. Passing in the open area feels like
60 FPS. They request cheaper roof shading while retaining players' light/dark
response. A GPU capture or a new v19 device log is not available, so this does
not establish which GPU stage causes the remaining delay.

## Change

The Day roof receiver now has shorter paths for spatially uniform regions:

- Straight sides and the rectangular interior use the exact scalar distance.
  Only rounded corners calculate a vector length (square root).
- Fully open and exterior points return as soon as their boundary is known.
- Solid shade skips boundary smoothing. Konami skylight and beam calculations
  run only within a skylight band; its two bands cannot overlap at the current
  8-120 cm edge widths. Anfield uses its own simpler roof ring.

The projected roof plane, rounded corners, openings, beam positions and shadow
strength stay the same. The shared world-space receiver still uses each
fragment's height, so skin, kit, hair and pitch respond to the same roof. Fully
shaded direct light retains 12% and ambient light retains 56% of the lit values.
Season direction and cloudy/rain softness are preserved. Screen derivatives
are evaluated before any spatial early return, keeping the soft-edge footprint
defined across fragment groups.

No runtime sampler, texture, draw pass, light actor, mesh, resolution or player
update rate is added or reduced. Existing native Day cascade suppression and
Night/quality gates remain unchanged. The v19 uniform cache and climate factors,
v18 referee changes and the installed surface patches are retained.

An audit of the 706 locally available, eligible native shader variants finds
300 positive-depth PCF conditions: all 284 in Day-capable variants have the
existing Day bypass; the remaining 16 belong to the two Night-only pitch
families and retain their native shadow path. No missing Day bypass was found
in these fixtures. This is source coverage evidence, not proof of the currently
selected on-device shader or cascade state.

## Verification

The new regression harness executes the emitted helper code and compares it
with the frozen pre-v20 equations. It covers both stadiums, rounded corners,
off-pitch camera regions, skylights, beam edges, exact branch boundaries,
weather/season combinations, receiver heights and different edge footprints.
Visibility differences must remain below 0.0002 on the 0-1 scale.

Host operation counters check representative solid-shade points: the old
Anfield path executes two vector lengths and two smoothsteps, while the new
path executes neither. The equivalent Konami solid-shade check goes from two
vector lengths and seven smoothsteps to neither. Soft boundaries still blend
and curved corners still calculate their distance. These counts describe the
source execution paths; they are not GPU timings or a promised FPS increase.

The final focused suite passes 54 tests and 1,060 subtests. All 706 eligible
native shader variants compile before and after rewriting under both clip-space
definitions (2,824 successful compilations). The production NRO's loadable
segments match its AArch64 ELF, its compiled runtime identity is correct, and
the embedded icon matches the project icon. The public-tree audit passes for
781 files; whitespace checks pass. The wider legacy suite is not rerun here.

## Device comparison

This is an NRO-only update for runtime pair `e861c583ec78e9ae` and its 53,248-byte
patch OBB. Keep the previously installed NRO for comparison/rollback. Use the
same graphics quality, teams, camera and referee setting in each comparison.

1. DAY / Fine / Summer: pass the ball entirely inside the roof shadow for
   20-30 seconds, then pause so the buffered presentation summary is written.
2. Resume and repeat in the open area, then pause again. Check that players
   still darken/lighten smoothly while crossing the boundary.
3. Repeat at both Anfield and Konami, then check Rainy/Summer, Rainy/Winter and
   NIGHT for appearance and pacing regressions.
4. Save `scene-runtime.log` before restarting. The header is
   `FootballNX scene v20 session`. Presentation lines retain DAY/NIGHT,
   stadium, Day lighting gate and native CSM observation labels.

The log records presentation intervals, not GPU time or simulation FPS. The
same scene is required for useful future comparisons against this accepted
build. Referee opt-in remains `PESNX_REFEREE_PROBE_V1` if in use.

Delivery: `local-debug/roof-shadow-v20/release/FootballNX-Roof-Shadow-v20.zip`.
NRO size: 83,809,183 bytes. SHA-256:
`067f930d8bfe4853a2004f1b7e44bed5e3f4c54551ebf8f14cc680a51beecbae`.
Checkpoint tag: `checkpoint-roof-shadow-v20-2026-10-11` on `cupleague`.
It includes the accumulated v18 referee and v19 climate/cache changes used in
the tested NRO. The earlier v17 checkpoint remains available. Binary payloads
stay local; the Git checkpoint contains authored source, tests and documentation.
