# Native aggregate score presentation v90

Second-leg Cup and League knockout fixtures now display their existing native
aggregate score in a separate 144×32 `AGG` plate below the main scoreboard.
All 22 competition themes and the c0 fallback use the same clear plate. The
current match score remains in its existing cells. The first leg, a single-leg
final, group/table matches, Exhibition, completed fixtures and invalid contexts
do not acquire an aggregate score. Current Master League domestic cups are
single-leg; a normal home-and-away league calendar is not a two-leg tie.

## Original native score ordering

The frontend resolves first-leg goals into the current match's HOME/AWAY team
order. The original `tmpdb::Match::Set1stLegScore` stores previous-leg HOME/AWAY
bytes; `SetTmpdbMatchToRegistryMatchEnv` copies them unchanged. The original
`match2D::Screen::Manager::UpdateTimeScoreInfo` adds current HOME goals to the
stored previous AWAY score, and current AWAY goals to previous HOME. The small
`nx_native_first_leg_score` policy therefore reverses the frontend pair exactly
once when seeding a second-leg native Match. Result/frontend aggregate math is
unchanged, and native away-goal regular/extra-time flags remain disabled.

This is backed by execution of the original hash-pinned functions with owned
fake records and named dependency stubs, not by a guessed field orientation.
For first-leg current-order goals 3–1 and current goals 2–0, the old seed
produces an incorrect 3–3; previous-leg storage ordering produces 5–1. Reversed
teams and a 12–13 two-digit aggregate are also exercised. The manager requests
native `HalfKind 5` combined regular/extra-time goals; shootout goals are not
added. Native display execution separately proves show/off labels, distinct
live 2–1 fields, one/two-digit labels and the existing 99 display clamp.

The optional native test reads the compatible ignored library at runtime. It
pins the whole ELF SHA256 and six function RVAs, sizes and digests. Public code
contains no copied game instructions or raw disassembly. Missing local ELF or
probe dependencies make this an unavailable integration test.

## Narrow asset changes

`tools/refine_scoreboard_aggregate_v90.py` accepts the verified v90 lower-banner
archive and all 23 corresponding packets, then writes a new directory. It
patches only:

- The aggregate outer placement and its two number-cell translations.
- The aggregate's dedicated image import dimensions and one atlas mapping.
- One authored plate in unused atlas rows 464–495.
- The redundant second square background's X translation, moved offscreen.

Native labels, bytecode, names, frame counts, alpha tracks, entry/exit motion
and native one/two-digit child transforms remain exact. Shared clock glyphs,
current score, names, kit strips, cards and all other atlas pixels/mappings
remain exact. Spain and France reserve the lower left for added time; their
aggregate sits alongside it with an eight-pixel gap. Other themes place it
below the whole main plate and clock tab.

The composition retains the parallel v90 lower-banner title refinement and
native rounded alpha exactly. Its movie SHA256 is
`eb96ed25e3f9fda9fb3b632dd7aefa1301d0b156f6baf49bd7f96de7caf56955`;
half-plate alpha SHA256 is
`6e74130d78cf3d83cd82716709f8b080345a8a54dab15d76824890b46ebc5ecf`.
All 1,812 other archive members, including shared wave textures, are compared
byte for byte after archive roundtrip.

Focused tests cover actual production frontend contexts with real Cup/League
types and the real tournament fixture resolver; all 23 movie field allowlists;
packet source/target checksums; atlas pixels and mappings; protected movies;
and the composed archive's exact member delta.

## Local candidate evidence

Ignored evidence lives under `local-debug/presentation-v90/aggregate-01`:
`NATIVE-PROOF-02.json`, `candidate/ASSET-REPORT.json`, and `previews-03`.
The combined banner/aggregate `FootballNX.assets` is 29,982,722 bytes, SHA256
`ce9978da072e1ddf79c9378aa7f4ceec861497c442a04a6958724ef4119f3fe3`.
The previews use actual plate and aggregate digit atlas pixels, with sample
native UIR text proxies. They establish host layout only. Switch visibility,
native font appearance, scoring updates, extra time and shootout transitions
still require device evidence.

## Default theme for rejected placeholder plates

User review rejected the generic `GER` and `INT` wordmark plates. Selection
keys39 and1002 now use the complete current FootballNX27 default packet from
key1000, including its white, blue and red main plate, native score/clock
bindings, rounded lower banner and AGG panel. The competition's selection key
and fixture name remain unchanged. `DEFAULT_THEME_ALIASES` makes that choice
part of future builds rather than a runtime hook or a change to team identity.

The incremental `aggregate-02` stage reuses the independently validated
aggregate cohort and replaces only `scoreboards/c39.nxsb` and
`scoreboards/c1002.nxsb`. Both must be byte-identical to `c1000.nxsb`; every
other archive member remains exact. This external UI change does not require
another NRO build. The older `aggregate-01` evidence remains immutable.
