# v83: Cup-final team keys and added-time padding

The supplied v82 trophy journal confirms package validation and both runtime
hook installations. At full time its listener reaches readiness (state 16,
flags 1/0/1), but snapshot capture rejects `current-team-mismatch`. No trophy
candidate is created and the result UI follows its normal overview route.
The static `revision=v60` feature label is not an executing-NRO version.

The snapshot adapter compared the complete stats team key against a master key
with zero storage bits. Native `SetExhibitionTeamId` preserves the physical
identity in the upper 18 bits and sets the lower 14 bits to HOME `0x3ffd` or
AWAY `0x3ffe`, as established by the v65 owned-ELF oracle. A correct current
match key therefore fails the old comparison. The earlier trophy host fixture
incorrectly used master keys and missed this defect.

The corrected adapter uses the existing `exhibition_match_team_identity`
predicate: require both the expected physical identity and the exact side
locator. It does not simply mask away the low bits or accept either team.
Mismatch diagnostics now include side, logical ID, actual key, master key and
expected key. All borrowed-record locks, live-final checks, END-phase checks,
fresh scores, winner-side policy, one-shot success, prop readiness, ownership,
Skip, timeout, fallback and overview ordering remain intact.

The host fixture now carries native match keys. Before the correction this
fixture fails at trophy creation; after correction the real C adapter admits
the candidate and holds the overview. Tests cover the device's readiness state
16 and reject master keys, opposite-side locators, different physical teams,
invalid locators, logical IDs and zero for either side. The existing lifecycle
tests continue through success, failure, shootout, Skip, teardown and reentry.

An additional optional bounded Capstone probe reads the pinned owned ELF.
`Record::UpdateStatsMatchStatus` copies TeamAIInfo's complete word at `0xa278`
to StatsTeamInfo `+0x28`; `StatsMatchInfo::GetTeamId` returns that raw field.
The four-instruction copy and the v65 conversion are checked over synthetic
values without executing the game. The device log did not include numeric
team keys, so those exact device values remain unobserved. These probes prove
the native storage contract, not successful trophy rendering on Switch.
REA native decompilation was unavailable on this host (unconfigured provider);
the findings above use local source, Capstone and the existing owned-ELF tests,
not decompiler evidence. No analysis engine was installed or reconfigured.

The generic FootballNX27 League/Cup added-time plate increases from 48×24 to
60×32. The native glyph/font size remains the same; its content is shifted up
2.65px and right 6px to provide balanced padding. The 4×28 team strips and the
main 404×48 scoreboard remain exact. Added-time visibility/fades still belong
to the native conditional clip. Licensed scoreboards remain unchanged.

Packaging starts from the complete verified v82 runtime. Only NRO and the two
generic scoreboard members inside FootballNX.assets change. All other archive
members, all 1,638 heads, 436 body-selector corrections, old 907 heads, cinematic
CPK/manifest/marker pair, trophy props, weather, stadiums, adboards, commentary
and referee remain exact. Host/native parser, 24-CPK, hash and ZIP checks do not
establish device playback.

Device check: win an actual standalone Cup championship final, allow its ending
to proceed, then retain the new scene/trophy journals. Admission should reach
`factory-snapshot ... accepted=1`, the UI hold, and candidate creation; a later
prop/cut failure must remain distinguishable from a team-key rejection. Also
check halftime, a non-final match, Skip, ordinary overview and the next match.
