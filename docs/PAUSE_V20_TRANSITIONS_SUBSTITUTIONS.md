# Pause v20: compact stats, transition cover, pending substitutions

The stats panel now spans 64% of the screen with closer value columns. Pause
handoffs use the custom full-screen background, an animated spinner and an
opening/returning/resuming label. The editor publishes its ready state before
the cover is released. Resume waits for a gameplay/demo callback after Pause
has gone away, with a timeout to prevent a permanently covered screen.

Within Game Plan, the displayed incoming member is resolved back to its native
pending reservation. Selecting the outgoing player cancels that reservation;
selecting another substitute replaces it. A rejected replacement restores the
previous pending pair. Native eligibility and substitution limits remain in
effect. Back from the root of Game Plan confirms both ready human sides (only
HOME against COM), and outgoing members are greyed and blocked on later visits.
Already-applied native reservations also mark outgoing members unavailable.
Locks are per side and reset at the next MatchSetup.

Native ABI audited in the local library: GetChangeReservedInfo returns a
four-byte record (in, out, reason, alreadyChanged); there are six records.
SetChangeReserveCancel clears one pending record. The native starting order
is not changed by a pending reservation, so the v19 display projection remains.

Host validation: 22 pause tests, 12 Game Plan editor tests and 4 live Game Plan
tests pass. New executable C cases cover cancel, replacement at the limit,
rejection rollback, confirmation locks, separate sides, applied records and
transition lifetime. Visual timing and actual match substitutions need Switch
verification.

Build: `build-wsl.ps1 -OutputDirectory local-debug/pause-console-v20-diagnostic -Diagnostics -Jobs 8`.
Use the existing OBB. Test Pause -> Game Plan -> Pause -> Resume, then test
starter A -> reserve B -> A (cancel), A -> B -> C (replace), and reopen after
Back to check the outgoing player's grey/locked row. Also check 2P readiness.
