# Online Manager League review v115

The v115 review addresses the user's Switch captures from the v114 client.

- Profile navigation remembers the originating page and selected row. Back from
  a profile child returns to that profile; Back from the profile returns to the
  standings or club list that opened it. Failed reloads retain the return path.
- Club Match History uses its own list, newest first across all league cycles,
  five rows per page with L/R pagination and A for replay. It does not overwrite
  the current schedule cache or expose future results.
- Online Game Plan starts at the four root actions. A enters Substitute;
  directional input then selects pitch/bench players. B cancels a selection,
  returns to the root actions, and finally saves the draft on exit. Formation
  shares the ten native shapes, with the native shape-picker and player-role
  panel renderer. Offside trap, automatic substitutions and nine role assignments
  persist through the backend. Tactic replaces Preset for online plans.
- The Schedule tile shows a seven-day strip, W1/W2 bands and today's phase.
  Lower MY TEAM and LEAGUE tiles regain artwork and meaningful labels. General
  explanations remain in ZL Info. MY TEAM now has four tiles in a 2x2 grid:
  Game Plan, Player Feed, Shop and Trade History (upcoming). Opponent profiles
  are accessed through League Standings, removing the duplicate hub shortcut.
- Shop reads per-club offer availability before entering checkout. Missing
  canonical memberships are reported as an unavailable catalog, not an uncertain
  payment. Existing idempotent purchase recovery remains in place.
- Online saves count as a shot on target for the opposing team. Touchline event
  labels use spaces; blocked shots are no longer labeled as wide shots.

## Backend dependency

Deploy the accompanying `fnx_server` patch before installing this client. It adds
`GET /api/v1/clubs/{id}/matches`, Game Plan settings, offer readiness and simulator
`v1.2.0`. See that repository's `docs/CLIENT_V115.md` for the contract and the
required TEST membership repair. A read-only live probe found empty rosters for
teams 100 and 108. No production data was changed during this review.

## Verification boundaries

Host tests execute the production online controller against synthetic HTTP,
the offline editor with native callbacks stubbed, and actual rendering
primitives. Backend integration tests use temporary PostgreSQL databases.
Preview images demonstrate host rendering, not Switch acceptance. The new
backend recording is also passed through the real C playback parser at each
second. Build artifacts and verification logs stay in ignored
`local-debug/manager-v115/`; proprietary runtime assets remain local.

The live catalog repair and on-device acceptance still require verification
after deployment. Do not delete payment recovery saves to fix missing server
catalog rows.

Final checks: 147 host tests and 147 subtests passed, the backend's complete
PostgreSQL suite passed with the race detector, and `go vet ./...` was clean.
The C parser accepted the new recording at 661 playback positions. The paired
Switch build succeeded; its NRO/ELF, embedded icon and source pins are checked
again during packaging.
