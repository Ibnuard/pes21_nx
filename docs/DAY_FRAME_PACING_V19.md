# Day frame pacing candidate v19

The user reports that all players stutter near midfield in DAY at both Anfield
and Konami, with every weather/season setting. NIGHT is smooth. They clarified
that this is motion cadence, not jagged edges, and that the earlier Day shadows
were already running well. These observations supersede the previous assumption
that enabling the referee was sufficient to explain the problem.

There is no new device capture with reliable Day/Night labels yet. The v17 log
does not label match time, so it cannot establish a Day versus Night comparison.
Neither a particular GPU bottleneck nor a guaranteed FPS improvement is proven.

## Changes

- Weather/season factors for direct light, ambient light, rain tint, turf detail,
  dampness and sheen are calculated when a program's climate/time settings
  change. Three cached vectors replace the repeated climate calculations in
  fragment shaders. Colour equations and their Day/quality gates are retained.
- The uniform cache previously had one entry per program hash bucket. Alternating
  programs with the same bucket discarded each other's locations and values,
  repeating every location query and upload. Four entries per bucket retain those
  programs. Storage and lookup work are bounded, with no per-draw allocation.
  Real native program binds still run; cross-context relink/delete and context
  changes still invalidate the cache. Texture binding behaviour is unchanged.
- The existing break-only presentation log now includes DAY/NIGHT, stadium
  profile and the Day lighting gate. It records the last live cascade observation
  from the existing game-thread CVar check, rather than querying UE or GL during
  rendering. `csm=-1` means not observed/unavailable; `-2` means the native CVar
  type did not match. A zero value is a native count observation, not a GPU timer.
  Native weather setup also records DAY/NIGHT.

The analytic roof shape, projection, soft edges, season position and shading
strength are unchanged. The existing native cascade policy is unchanged.
Wet/snow pitch patches, particle removal, scene colour choices, native gameplay
and the v18 referee candidate are retained. No new texture, draw pass, light
actor or graphical quality reduction is introduced.

## Verification and device comparison

Host checks compare the new uploaded factors with the previous equations for
every Day/Night, weather, season, turf and surface setting, across multiple
colours and shadow visibility values. Cache checks exercise colliding program
IDs, eviction, unchanged settings, Day/Night changes, optimized-away uniforms
and shared-program invalidation. Presentation checks ensure live observations
are not relabelled by the settings visible after returning to a menu.

This is an NRO-only candidate for the existing runtime pair
`e861c583ec78e9ae`, with a 53,248-byte patch OBB. Keep the previously installed
NRO for rollback. Test the same teams, camera and quality at midfield, first
DAY/Fine/Summer and then NIGHT with the same settings. Keep the referee state
the same between comparisons. Follow with Rainy/Summer and Rainy/Winter to
check the retained surface and lighting appearance.

Play for at least 20-30 seconds, then pause or let the ball go out so the buffered
summary is written. Save `scene-runtime.log` before restarting the application.
The new header is `FootballNX scene v19 session`. The log records presentation
intervals, not simulation FPS or GPU time. Switch acceptance remains pending.

The final focused run passes 51 tests and 1,060 subtests, including the local
native ABI fixtures. All 706 audited shader variants compile in both clip-space
modes, before and after transformation: 2,824 successful compilations. These
checks retain shader inputs in memory and do not create extracted shader files.
The production build has diagnostics/performance trace disabled; its NRO
segments match the AArch64 ELF and its migration ID matches the runtime above.
The compiled source copies match the working source, and the icon is verified
byte-for-byte. The public-tree audit passes for 779 files; whitespace checks pass.

Delivery: `local-debug/day-pacing-v19/release/FootballNX-Day-Pacing-v19.zip`.
NRO size: 83,805,087 bytes. SHA-256:
`c1aa66b164523638ed25dd07307540c4ffeb284de9449c980a39a3d5abff793b`.
The package includes installation instructions and verification/checksum records.
These changes are preserved in the subsequently accepted v20 checkpoint,
`checkpoint-roof-shadow-v20-2026-10-11`. The earlier requested v17 checkpoint
remains available at `checkpoint-review-v17-2026-10-11`.

Device follow-up: the user reports reduced stutter with v19, but play inside
the roof shadow still stutters while the open area feels like 60 FPS. This is
a user observation, without a new instrumented capture. The follow-up candidate
is documented in [Roof shadow v20](ROOF_SHADOW_COST_V20.md).
