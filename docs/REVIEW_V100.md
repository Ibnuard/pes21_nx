# Random environment, navigation and production assets v100

This source review follows the user's v99 Switch feedback. No NRO build or
active-runtime installation is part of this review.

## Match preferences

Match Time (Day/Night), Weather and Season each append Random and default to
Random. Match Time here means lighting, not the separate match-duration rule.
Concrete options remain available. UI preferences are separate from the native
values: a random choice resolves once for a fresh pre-match session and stays
fixed across repeated MatchSetup, Strategy and native snapshot handoffs.
Rematch and the next Cup/League fixture start a fresh resolution. Getters used
by pitch/weather rendering still expose concrete native values. Random enum
sentinels never enter the native match record. Stadium, grass length and pitch
condition retain their existing choices and precipitation/wet-ground policy.

## Analog navigation and rewards

The Cobra menu bridge now translates P1's left stick to competition navigation.
It uses a 16,000-axis threshold, the dominant axis, a 350 ms initial repeat delay
and 110 ms subsequent repeat. D-pad input has priority; face buttons never repeat.
Gameplay/P2 axes and native match commands are unchanged.

Touchline has a visible focused event and a sliding five-row viewport, so moving
one row is visible immediately. L/R still moves five events. Only elapsed
events are shown. League Rewards now handles Up/Down, clamps to its five rows,
and exposes the same left-stick helper. Neither navigation grants money.

## Loading popup for a future online client

`loading_popup.h` exposes begin/update/finish and a copied render snapshot.
The request token prevents an older worker from updating or closing a newer
request. The render thread owns an animated twelve-dot indicator using existing
UI primitives, with a dimmed full-screen backdrop. Existing menu input is
blocked, including underlying native axes, while the operation is active.
Pre-match input requires release after closing the popup.

This is a reusable UI/ownership interface, not a network implementation. The
preview explicitly opens a sample Connecting popup; ordinary local operations
do not pretend to contact a server or add an artificial delay. A future online
owner must finish its token on success, failure, cancellation and timeout, then
display any result/error through the existing message popup.

## One production archive

The detached `FootballNX.assets` contains 1,838 verified members. All 1,834
protected members of the sealed v99 archive, including the referee animation,
are unchanged. The obsolete referee enable-token is removed. Added members:

- `Audio/manager-league-pcm-v96.acb`: identical reviewed 13-recording PCM bank.
- `Audio/trophy-user-hca-v100.acb`: current trophy recording.
- `ManagerLeague/unknown-club.png`: identical existing placeholder.
- `Runtime/trophy.cfg`: production configuration with the existing paired
  native ELF, cinematic CPK, manifest and trophy PAK identities.

Production readers prefer these consolidated members. Legacy loose installations
remain readable during an upgrade; staging never extracts archive members or
deletes source folders. A future v100 update should carry the consolidated
archive and NRO, without the loose Audio, ManagerLeague or Animations directories
or the old trophy-canary file. Old SD folders are not automatically deleted.

The referee installs through its existing ABI and validated-motion checks,
without an experimental opt-in token. Its old status file is diagnostic-build
only. Trophy bootstrap reads production metadata from the archive and retains
all four actual file-hash checks and native ABI preflights. The legacy marker
parser remains solely for old installations; the new archive needs no marker.
No compatibility gate is bypassed and no native animation/CPK/PAK is recooked.

## Trophy volume

The custom recording is encoded once from the exact original decoded PCM at
0 dB baked attenuation, another 3 dB above v99. It is not amplified from an
earlier lossy HCA. The measured change is 2.999960 dB; decoded peak is 0.940728,
with zero clipped samples and all 688,128 stereo frames preserved. Native cue
routing, global music volume and commentary volume are unchanged. The recording
and archive are detached local assets. Speaker balance still needs Switch
listening; host decode/headroom checks do not establish final mixer headroom.

Local receipts and real-renderer previews live under
`local-debug/manager-review-v100/`. Any later build must freeze current sources,
use the new trophy catalog and consolidated archive, and rebuild the native
loose-runtime validator against the current configuration header. Reusing the
v93 validator's old header-binding receipt is invalid after this change.
