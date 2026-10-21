# Native match team keys v65

V64's device log admits XI 11/11 but refuses every selected squad commit.
Its new selected-team identity guard compares the Match Team's complete ID
with the master ID. That guard is incorrect for this native runtime.

The compatible native `SetExhibitionTeam` calls `SetExhibitionTeamId` after
copying the selected master team. The latter preserves the physical team
identity in bits 14..31 and changes the low 14 storage bits to `0x3ffd` for
HOME or `0x3ffe` for AWAY. It likewise changes player carriers' low 16 bits
to `0xfffd` or `0xfffe`, preserving their player identity. Consequently a
correctly imported Match Team cannot equal its zero-locator master ID.
This is a deterministic v64 regression, introduced by the new guard.

V65 requires the exact expected physical identity **and** the correct native
side locator. It rejects the other side, another physical team, a malformed
master key and an unconverted master ID. It retains the two-sided squad
publication, full player-record permutation, native save return checks and
structural Match barrier. Commentary identities and buffers are unchanged.

The synthetic importer in the previous host test did not perform this native
ID conversion. That test now returns match-local team keys. A separate optional
owned-ELF oracle decodes and interprets two bounded integer/load/store blocks
from the real `SetExhibitionTeamId` at RVA `0x6d85158`, over synthetic memory.
It proves the ID/carrier transformations for both sides and several roster
sizes. It does not execute the entire function, its dependencies or the game.
The input SHA-256 is pinned; game bytes are not committed or retained by the
test. Missing local ELF/Capstone fixtures produce explicit skips.

An initial attempt using the installed Windows Unicorn engine crashed in its
memory-mapping API before executing target instructions. It supplied no target
execution evidence. The bounded interpreter above replaces that engine path;
no software installation or native game execution is required.

The earlier Training/MyClub timing explanation for v63's invalid raw HOME
remains an inference from static native writes and the device's stage-4
failure. V65 does not claim that a live callback trace established that timing.
The native selected-team reimport from v64 remains in place.

Every refused publication now adds a bounded release journal entry with its
stage, side, member index and numeric actual/expected values. Stages distinguish
team keys, squad/plan/Team counts, player identity, record address compatibility,
AdditionalData binding, member/order registration, allocation and native save.
It logs no raw pointers or payloads. A missing pre-match squad binding also
has a specific stage. No invalid Match may fall through the optional audio
policy fallback introduced in v63.

The NRO candidate preserves v64's commentary source/catalog and the exact
consolidated FootballNX.assets from v62/v63/v64, including accepted canary audio,
referee motions, scoreboard and other assets. Render policy, pitch, camera,
active dist, input archives, face PAKs and saves are unchanged. If those assets
are installed, only the NRO needs replacing.

Focused host checks: 79 tests passed, followed by 17 checks of the final save
binding guard and rebase code, including one new missing-binding case (80
unique tests). This is not a whole-repository or Switch acceptance claim.

Device sequence: direct hub Kick Off with Barcelona–Madrid and another P1;
starter/reserve swap before kickoff; finish then Rematch; finish then Select
Team and a new fixture. Check eleven normal-sized players per side and a match
that stays live. The journal begins `FootballNX scene v65 session`. Successful
publication says `v65 native HOME/AWAY team keys verified; both edited squads
committed`; if refused, retain the immediately preceding `stage=...` line.
