# Selected-team publication v64

Device follow-up: [v65 native match team keys](EXHIBITION_MATCH_KEYS_V65.md)
corrects this candidate's invalid comparison of match-local and master Team IDs.
V64 is superseded: its new identity guard deterministically rejects valid teams.

The v63 Switch log had a complete custom squad (`XI=11/11`) followed by
`snapshot rejected stage=4 side=0`. Stage 4 reads the actual Match Team member
count, before examining any player. The user subsequently reproduced the
failure with every selected P1 team: two tiny HOME players and immediate full
time, while AWAY was complete. Valid SquadData in the hub was not proof of a
valid Match payload.

V63 incorrectly allowed that structural failure through its optional commentary
fallback. V64 supersedes that behavior. Missing Match/Team, an invalid count,
an incompatible player-record address or a mismatched carrier blocks Play.
Only failure of the optional commentary selection policy, after those
structural checks, may use the existing native/canary fallback.

## Native writer and final publication

The compatible local v5.3.0 ELF's Training `ActDatasync` (RVA `0x6a8e968`)
calls `UtilityQuick::SetTeamDataInTmpdbMatch` twice, including a team from the
offline MyClub session. SearchWindow's matching records can already exist
before this import. The new v62 early hub conversion therefore left two
representations: the prepared, editable SquadData and a subsequently replaced
Match. `exhibition_plan_ready` prevented the former selected-team refresh from
reimporting Match. The old void save skipped a failed HOME synchronization but
still published AWAY and continued.

V64 explicitly rebuilds Match through the existing selected-team native
importer before the initial Kick Off commentary snapshot. It then imports that
Match into matchPlan Data and saves both **existing edited** SquadData owners.
It never reloads SquadEdit in this operation. Both selected team IDs, roster
counts, player identities, inline records and AdditionalData bindings must
agree. The complete player records and order permutation retain the selected
reserve's appearance, parameters and identity; no placeholder actor or scale
correction is manufactured.

Both sides must synchronize before any native save. The native save's boolean
result is checked, its previous MySide is restored on failure, and a refused
save is not published. Initial Play retains setup on failure. An accepted audio
reload resumes the already frozen transaction without another team import.
After stock Strategy has run, the final MatchSetup boundary restores the deep
squad snapshots and repeats the selected-team publication before native player
parameter loading. If that final publication is impossible, it raises an
explicit error instead of constructing a malformed match.

The investigation used bounded static ELF/symbol/Capstone inspection of the
legally obtained local input. In particular, native Setup reads the Team count
at `0x39e + 8`, confirming the existing `0x3a6` field; it is not an offset fix.
No PC/mobile binary or raw disassembly is added to the public tree. Static
inspection establishes the native writer and layout, not the exact timing of
every device callback.

## Verification and device checks

Host regression tests replay a late HOME overwrite after a complete hub, then
execute the actual rebase, two-sided synchronization and save functions. They
check full record bytes, stable carriers across final publication, both sides'
lineup edits, a starter from outside the registered 18, wrong source team or
identity, importer refusal, a native save failure and exclusion of live
substitutions. Commentary tests now distinguish structural refusal from an
optional policy failure, including drain and cancellation. Host tests and a
normal isolated build do not establish Switch gameplay success.

The candidate keeps the v63 consolidated FootballNX.assets, commentary catalog,
Yamal/Raphinha audio, referee animation/token, scoreboard, pitch and render
policies byte-identical. Active dist, OBB/CPK/face PAKs and saves are unchanged.
If v62/v63 assets are installed, only the NRO needs replacing.

On Switch, test Barcelona–Real Madrid and a different P1 club, initially using
direct hub Kick Off. Then swap a starter with an unregistered reserve in Game
Plan, play, finish, Rematch, and Select Team to a new pair. Check eleven normal
size players per side and that the match stays live. The journal starts with
`FootballNX scene v64 session`; successful publications say `v64 selected teams
rebound; both edited squads committed`. A refusal identifies structural Match
failure separately from optional commentary policy. Keep the journal if any
step fails. No device playback, FPS or Rematch acceptance is claimed here.
