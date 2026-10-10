# Competition scoreboards and native weather audit

Audit date: 2026-10-10. Scope: read-only investigation of the current wrapper,
locally supplied PES Mobile runtime, installed FL26, and local UE4.22 sources.
No NRO, asset archive, PAK, OBB, or installed runtime was changed. Findings
describe the working tree at this date, including its uncommitted stadium work.

The native library inspected has SHA-256
`a27939569d6013502873076b517e8bc0d9f63cabacd17d944d88a8b1dcc8d187`.
Binary offsets and conclusions must be revalidated for any other build.
Proprietary inputs and raw inspection output remain local and ignored.

## Results

| Request | Evidence and feasibility |
| --- | --- |
| Scoreboard selected by competition | Feasible through native UI resource selection. FL26 uses competition-to-folder routing; the wrapper has competition catalogs but no equivalent scoreboard resolver. |
| Grass length and pitch condition affecting the ball | Native surface-state selection and movement coefficients survive. Settings delivery needs verification; several menu combinations intentionally select the same native state. |
| Winter affecting physics | No direct season input was found in the inspected ball surface selector. Winter appearance does not establish snow or frozen-ground physics. |
| Actual rain affecting play | Native rainy-state ball physics and weather-transition logic survive, but Mobile match initialization explicitly resets rain and changing weather to off. |
| Rain/snow inside the Unreal scene | Native particle components and emitter spawning remain implemented. A compatible weather asset and scene integration are still needed; several game-specific wet/splash functions are empty. |

## Scoreboards: what FL26 actually does

The installed Sider configuration enables `common/scoreboards.lua`. Its
competition map routes resource requests to a skin folder using live-CPK
callbacks. It also supports optional variants and an Exhibition fallback that
checks whether both clubs belong to the same league. This is resource routing,
not a gameplay feature that becomes available by enabling Unreal.

Our League/Cup catalogs already have competition IDs. League, Cup and Master
League context should select the theme before loading the native match UI.
These modes reuse the native Exhibition launch route, so its default native
competition value alone is not a reliable theme key. A Cup fixture must use the
Cup theme even if both clubs belong to one league. Exhibition can optionally
use a shared-league theme, with a generic fallback for mixed leagues.

Mobile's `match2D::LocalSkin::SetupType` initializes the skin type to zero and
leaves it at zero on all inspected branches. Changing a competition ID alone
will therefore not expose a collection of PC skins.

Both platforms use the TXP2/AP2 UI container family. The existing
`tools/build_efootball10_scoreboard_v2.py` and
`tools/build_scoreboard_square.py` already adapt the Mobile atlas/timeline while
preserving native score, clock and animation bindings. Local inspection also
parsed the PC `game2d_score` movie from
`Data/dt11_x64.cpk` / `common/menu/licence/game2dPes.bin`.

That shared format is useful, but it does not establish drop-in compatibility:

- The inspected FL26 ENG1 `common/menu/general/game2d.bin` contains 18 general
  UI movies and no `game2d_score` movie. Mobile's general container has five,
  including touch/action controls. Replacing this entire PC file would touch
  unrelated UI and would not by itself establish a scorebar port.
- Mobile's licence container has eight movies; the inspected PC equivalent
  has nine. Node names, bindings, texture formats and timelines need individual
  conversion and validation. The complete precedence of every FL skin override
  has not been audited.
- Sider's Lua/file hooks and the Windows executable cannot be used directly
  by the ARM64 Mobile wrapper.

Recommended implementation: an authored competition-to-theme manifest, a
Mobile-compatible resource package per theme, and selection before UI creation.
Keep the native score/clock/event bindings, retain one active theme plus a
fallback, and release old resources between matches. `FootballNX.assets` can
store theme packages, but native UI loading still needs a resource bridge to
read them; the archive alone does not provide that integration.

Relevant code: `source/competition_frontend.c`,
`source/fl26_league_catalog_generated.h`,
`source/fl26_cup_catalog_generated.h`, `source/master_league.h`, and the
scoreboard tools above. See also [the existing scoreboard notes](SCOREBOARD_SQUARE_V1.md).

## Weather settings: confirmed delivery defect

`exhibition_apply_match_settings` in `source/ue4_hooks.c` currently writes
season at `InitParam + 0x08` and weather at `+ 0x0c`. Inspection of native
`tmpdb::util::SetStadiumInitParam` establishes the opposite layout:

| Offset in `common::InitParam` | Native field |
| --- | --- |
| `0x00` | Stadium ID |
| `0x04` | Time zone |
| `0x08` | Weather |
| `0x0c` | Season |
| `0x78` | Turf length |
| `0x7c` | Pitch condition |

The weather/season stores are reversed. An isolated execution of the native
ARM64 store block with distinct sentinel values confirmed this layout.
The separate `tmpdb::Match` rule setters update separate fields; they do not
automatically repair the prebuilt stadium snapshot.

The wrapper currently exposes Fine/Cloudy and maps those choices to native
values 0/2. The exact Mobile weather-enum semantics must be verified before
adding Rain/Snow; FL's numeric labels should not be assumed to match Mobile.
`MatchListener::MatchParam` caches the stadium snapshot for subsequent setup,
so fixing only the menu label or applying setters after that copy is insufficient.

Existing `nxStadiumClimate` presets independently alter Day/High lighting,
roof contrast, grass detail and sheen. They can look different even when native
match state is wrong. `tests/test_stadium_environment.py` checks this appearance
math, not the ABI layout or native ball response. Accepted Night appearance is
deliberately excluded from those presets.

## Ball physics and the disabled rain path

`match::Ball::Init` calls `UpdateBallPitchState`. The selector reads native
`MatchEnv` and chooses a surface state. Isolated native execution verified all
18 combinations of three turf lengths, three pitch conditions and rain on/off.
With rain off, the state IDs are:

| Pitch condition / turf | Short | Normal | Long |
| --- | --- | --- | --- |
| Dry | 2 | 1 | 1 |
| Normal | 2 | 1 | 0 |
| Wet | 1 | 0 | 0 |

These are opaque state IDs, **not friction multipliers or a speed ranking**.
Different menu combinations can select the same state. With `IsNowRainy` set,
all nine combinations select state 3.

The selector writes live and future ball-movement state. The inspected
`match::UpdateBallTransition` indexes `constant::BallBase` coefficient arrays
using that state; this is a native movement path, not just a visual flag.
Exact stopping distances, bounce changes and coefficient magnitudes have not
been measured. No direct season input occurs in this selector, so a Winter
selection alone does not prove snow/ice physics.

`MatchListener::SetGeneralInfoFromTmpdb` consumes turf and condition from the
cached stadium snapshot, then explicitly sets both `ChangeWeatherType` and
`IsNowRainy` to zero. The subsequent rule-copy helper does not restore them.
The surviving `Flow::ThinkRainy` path needs an enabled weather-change mode,
appropriate weather, live-match timing and other conditions. Resetting the
change mode to zero blocks that normal transition path.

Future implementation must deliver validated settings before ball
initialization, then verify the effective `MatchEnv`, rain flag and selected
surface state. A mid-match transition also needs to update live ball state,
prediction and the native weather-change/recording path consistently. Creating
a separate Unreal-physics ball would leave PES movement prediction and AI
using different rules and is not the proposed solution.

## Native Unreal precipitation

`UParticleSystemComponent::SetTemplate`, `ActivateSystem`, particle emitter
spawning, and `UGameplayStatics::SpawnEmitterAtLocation` have implemented bodies
in this Mobile library. The local UE4.22 toolchain therefore provides a plausible
route to cooked, world-space Cascade rain/snow inside the stadium scene.

However, `match::Player::UpdateWetEffect` and
`match::Ball::UpdateSplashEffect` are return-only stubs in this build. Visible
rain, splashes and wet-player materials cannot be promised by toggling one
native flag. The main PAK filename inventory did not identify a ready rain/snow
weather system; that search is not proof that no indirectly named asset exists.

The inspected Android Low profile selects EffectsQuality 0. Local UE4.22
scalability sets emitter spawn-rate scale to 0.125 at that tier, rather than
globally disabling all particles. Effective runtime quality and material/shader
compatibility still require validation.

A candidate should use a bounded emitter volume around the camera in world
coordinates, scene depth for occlusion, explicit roof exclusion where needed,
and a controlled particle/overdraw budget. Avoid stadium-wide per-particle
physics collisions. Creation, pause, replay and destruction must follow the
native world lifetime, including repeated matches. This would render through
Unreal, without drawing rainfall as a Switch overlay. Its visual state should
follow the same authoritative native weather used for the ball.

The installed FL26 `WeatherConditions.lua` distinguishes season, weather and
falling-weather effects, but is not enabled in the inspected `sider.ini`.
Its structure is a reference; this audit does not attribute active FL weather
behavior to that unused module.

## Proposed sequence and verification limits

The subsequent authorized implementation is documented in
[Native weather and competition scoreboards](NATIVE_WEATHER_SCOREBOARDS.md).
The observations below describe the audit baseline before that implementation.

1. Correct and test the snapshot layout and explicit Mobile enum mappings.
   Log effective settings after native setup, rather than only menu choices.
2. Validate native dry/wet/rain physics and weather transitions using identical
   kicks; compare live movement, prediction, replay and consecutive matches.
3. Add one bounded native Unreal rain emitter with compatible cooked materials;
   measure load time, frame time and memory. Extend to snow only with an explicit
   surface policy; a Winter lighting preset is not that policy.
4. Add the competition theme resolver and one Mobile-compatible scoreboard;
   validate league/cup precedence, Exhibition fallback, injury time, goals,
   penalties, pause/replay and switching themes across matches.

Verification completed: source and native control-flow inspection, parsing of
local PC/Mobile UI containers, native field-store probe, and 18 isolated native
surface-selector cases. Optional probe scripts/results are under ignored
`local-debug/environment-score-audit/`; the installed runtime was only read.
No full match, new particle system, theme switch or performance measurement was
executed on Switch. No build or full regression suite was warranted for this
documentation-only audit. The pending referee/device validation is unchanged.
