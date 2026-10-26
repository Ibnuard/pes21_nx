# Match review v94

The supplied v93 journals identify two runtime failures: all three game2dPes
resource attempts retain native UI while the separate wave texture succeeds,
and trophy music reports `music-wave-pool allocation-rejected`. The two-team
Home Away Cup also completes after its first match because the core deliberately
treated every final as single-leg. The current user request replaces that rule
for standalone Cups and, following the additional review, standalone League
knockout finals with Home Away enabled.

## Cup championship return leg

Standalone Cup sets `CUP_TWO_LEG_FINAL` in the final fixture's existing reserved
flags. The fixture and save payload sizes stay unchanged. The shared core's
two-leg query now drives result recording, extra-time/penalty eligibility, native
aggregate seeding, next-match captions and trophy admission. Standalone League
uses the same explicit final flag; third place stays single-leg.

Leg 1 records prior goals without a winner, history completion or champion. The
hub retains the return fixture through save/continue. Only the deciding final
leg supplies a live trophy context. Its first-leg goals are copied into current
native HOME/AWAY order. The ceremony policy selects the aggregate winner, with
current shootout evidence required only when the aggregate is level. A return-leg
loss or draw can therefore still produce the correct championship presentation.

Cup save header version 5 retains the same payload. Older pending Home Away
finals gain the return-leg policy on read. Already completed saves preserve their
recorded outcome; an awarded old Cup is not silently reopened or rescored.

## League and automatic Master League schedules

Standalone League applies Home Away to every knockout round, including the
final. The hub, bracket status, extra time/penalties and scoreboard aggregate
read the shared two-leg query. A two-team season needs both table fixtures
before entering knockout, then both final legs before completion. Table
fixtures count independently towards standings; only knockout ties use an
aggregate. League save v6 keeps the payload unchanged, upgrades pending v1-v5
Home Away knockout finals on read, and preserves already awarded titles.

Master League selects its rules separately: the domestic league and national
qualifying group automatically use a double round robin with reversed return
fixtures; current domestic, continental, regional and World Cup knockouts all
use single legs. These compact career rules are existing project policies,
not a recreation of official competition regulations. The standalone final
flag is not injected into career saves. Full-season tests cover two clubs,
odd-team byes and larger fields, refuse season rollover before the return
fixtures finish, and save/continue halfway through. The national qualifier
test retains all six matchdays and cannot begin World Cup finals after only
the first three. The custom on-field trophy bridge remains scoped to a live
standalone Cup final; League and career fixtures cannot inherit that context.

## White rounded banner admission

The sealed v93 archive contains white RGB, the original rounded alpha, smaller
competition title and the intended aggregate layout. Its 23 score packets have
a corrupted TXP2 size field: atlas growth on a bare TXP2 writes the big-endian
length, then overwrites the same location as if it were an outer little-endian
AFP header. The runtime correctly rejects those packets. The separate wave
packet is valid, explaining the mixed native plate and branded ribbons.

`afp_texture_patch.replace_atlas` now writes the outer size only when an outer
header exists. A detached, exact-source repair tool fixes the 23 sealed packets,
removes only trailing zero alignment and refreshes their target sizes/checksums.
Source identities, image pixels, scripts, rounding, aggregate placements and all
other archive members remain exact. The real C packet parser accepts every
repaired theme. Public tests also exercise growth on synthetic raw TXP2 and AFP
containers, so this check requires no proprietary fixture.

## Stamford Bridge pitch

Loaded stadium ID 9 receives narrower vertical mowing, stronger contrast
and deterministic worn-grass patches through the existing diffuse helper.
Other stadiums keep their previous pattern. Paint/outside-pitch rejection,
native detail, weather and shader texture/alpha operations retain their
existing paths. Exact host math and optional native fixtures pass the focused
pitch, lighting, weather and roof tests. See `STADIUM_PITCH_MOWING_V62.md` for
the v94 parameters and the public-data-only diagnostic preview command.

## Custom trophy music on the existing native pool

The recording is the user's complete reviewed `WEARETHECHAMPION.mp3` clip,
retaining the v90 PCM source's -12 dB attenuation, stereo 44.1 kHz and all 688,128
samples. It is staged as highest-quality plaintext HCA, compatible with existing
native HCA voices. Playback no longer allocates a new WAVE pool. The cue retains
the accepted native sequence/category/bus route and ceremony-owned start/stop.
Cipher bypass requires the mounted owned bank and the entire exact HCA header;
other voices retain their existing admission.

The detached bank is 694,940 bytes, SHA-256
`5a5a06c711b27940f8109b43cfb32c422b0b4fa5231579c10984ca09b891a506`.
Independent full decoding has zero clipped/non-finite samples, peak 0.236976,
RMS -25.7668 dBFS and 38.609 dB polarity-aligned signal-to-error ratio. VGAudio
and FFmpeg use opposite global HCA polarity; only the comparison accounts for
this convention, without changing the encoded recording. This is lossy HCA,
not the previous lossless WAVE candidate. The native original header and all
673 packet reads are checked separately. Host decoding and queue ownership do
not establish audible Switch playback or final mixing quality.

REA bound the exact compatible ELF, but no native decompilation provider was
available on this Windows session. The additional instruction inspection used
the existing local Capstone/ELF and bounded Unicorn tooling; it is not presented
as REA decompilation evidence. Game inputs, journals, encoded music, native
inspection output and detached asset candidates remain ignored.

No Switch build, installation or delivery is implied by these source and host
checks. The user requested a further review checkpoint before the next build.
