# v13 diagnostic candidate

Save single-controller mode at MatchSetup. Live editor must not depend on the
prematch session-active flag; vs COM closes on human ready without P2 input.
Real 2P retains the existing two-ready handshake.

Restore native squad Load for both sides before refresh. v11 removed it while
the stall was still unidentified; v12 identified portrait IO as the blocker.
GetSquadPlayer(index) returns a dummy when its vector is empty/out of range,
so the vector must be populated before reading identities.

Read live player identity directly from SquadPlayer::GetTmpdbPlayer(NORMAL),
whose ABI was inspected (offset 0x80, parameter stride 0x120). SquadData lookup
can return a dummy entry when PlayerId cannot resolve. Hardware verification of
names/IDs is still required; do not rewrite live substitution IDs from names.

Keep 64 bounded portrait copies from successful pre-match reads. Live editor
uses these cached PNGs without synchronous asset IO. Uncached portraits still
use placeholders: this does not yet provide all live portraits on a cold cache.
Opening the custom pre-match Game Plan populates its portraits for reuse.

Existing OBB, fullscreen Pause and loading handoff unchanged.
