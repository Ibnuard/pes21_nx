# Pause v11 diagnostic candidate

User hardware confirmed v10 loading release is correct; that path is unchanged.
The supplied log confirms Pause-origin editor entry, but not squad refresh
completion. Reentrant matchplan Load was removed from this path; existing native
live squads are read instead. Additional initialization boundary logs identify
any remaining stall. This is a candidate fix, not a hardware-verified resolution.

Pause is now a full-screen custom page using the existing team-selection
background. Native UI is covered rather than relying on alpha propagation.
Custom header uses selected team names/badges and actual native GetScore(half5)
snapshots; unavailable scores display --. No fabricated scores. Stats remain
rounded; three horizontal actions and helper remain. The unsuccessful native
header reposition hook is disabled. OBB and loading behavior are unchanged.

Manual checks: Pause appearance at nonzero score; Game Plan opens custom editor;
P1/2P controls and return; Camera/Top Menu confirmations; loading regression.
Build is diagnostic; retain debug.log when reproducing problems.
