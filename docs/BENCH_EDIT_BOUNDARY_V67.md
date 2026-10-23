# Bench confirmation boundary v67

The device report after v66 is unchanged: following Rematch or Select Team,
a reserve can be highlighted but A does not replace the selected starter.
The user also recalled an earlier permanent Master League Game Plan issue.
No new Switch journal was available during this investigation.

V66's new-fixture initialization corrected a missing native lifecycle, but
did not close a later publication boundary. A pre-match editor can still own
valid selected SquadData after native Training data-sync overwrites the raw
Match. The v64/v65 rebuild protects Play and final MatchSetup. It did not run
before the earlier bench edit. Native replacement could therefore succeed,
then `exhibition_sync_prematch_lineup` would reject the unrelated raw Match
and the rollback would make A appear to do nothing.

This is a source-confirmed failure path, reproduced by a new test which sends
the actual substitute-page A action through the actual swap, replacement,
rebuild and full-record validation functions. The model imports selected
native values, admits valid squads, then corrupts HOME or AWAY Match values
as a late callback can do. On unchanged v66 both overwrite cases reject the
swap. After the change, both commit the complete selected player data.
This does not establish that a device trace observed that exact ordering.

V67 synchronously rebuilds and rebinds the selected Match before changing the
keys for an ordinary pre-match bench edit. It keeps both existing edited
SquadData objects, formations and current registered/reserve choices. It
never reloads SquadEdit at this boundary. Identity, exact native side keys,
roster counts, player records, info bindings, native save results and rollback
checks remain enforced. A refused source import retains the selection.

The ownership branches remain explicit:

- A live Pause editor continues to use native CanReserved/reservation rules;
  it never rebuilds the Match or immediately replaces its roster.
- A Master League office editor continues to validate its career roster
  without a playable Match, and only its existing save path persists the plan.
- An ordinary Exhibition pre-match edit uses the selected Match publication
  path and does not acquire career persistence.

The source does not establish a stale Master League editor flag as the cause
of this report. The new regression covers the career path with unavailable
Match data, as well as a fresh/repeated ordinary edit, a reserve outside the
registered eighteen, refused import, and live reservation rejection. The
older Pause fixture has been brought up to the current preset-header and
pre-match replacement API so its existing live-reservation checks can run.

The release journal now records a bounded `v67 bench confirmation` entry with
side, live/office owner and order numbers, plus rebuild refusal or accepted
refresh. Existing structural rejection stages remain available. It records
no raw pointers or player payloads and performs no per-frame logging.

The native static investigation reused the compatible owned ELF and retained
v64/v65 timing evidence. Bounded additional symbol/Capstone inspection of
Match lookup and native replacement found no new reason to bypass eligibility
or identity gates. REA's native providers remained unavailable; no native
game execution or decompiler-provider result is claimed.

The candidate preserves every FootballNX.assets member from v66, including
the accepted audio, referee animation/token and four compact scoreboards.
Only a replacement NRO is needed if those v66 assets are already installed.
Device acceptance remains open: complete a match, choose Rematch or Select
Team, select a starter and reserve, confirm the swap and check that it survives
reopening Game Plan and kickoff. Retain the scene journal if it still fails.
