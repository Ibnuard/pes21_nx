# Online review v116

Three Switch regressions reported after v115:

- Shop opens a club-pack selector, then that club's sizes, then the existing
  price confirmation. Offers are grouped by server team ID even if interleaved.
  Back retains the chosen club/size. Refresh and paid-pack recovery remain
  idempotent; an unknown payment keeps its original request and blocks a new one.
- Online Game Plan exposes the same native bottom-right cursor, blue corner
  selection and Hold to Move context as Exhibition. The frontend now forwards
  held/released samples and raw stick axes. Tap A selects/swaps; hold for 220 ms
  and move the stick/d-pad to drag, release to drop; B ends a drag. X no longer
  starts movement. Native and online editors share drag speed, keeper limit and
  role zones in gameplan_gesture.h. Y changes the role; R toggles condition view.
- Backend simulator v1.3.0 adjusts supporting runs against the defensive line
  and ball, and recycles possession instead of targeting an already offside
  attacker. The referee still judges offside at release. Existing recordings
  remain immutable; the fix applies to newly simulated fixtures.

## Server data and deployment

A fresh authenticated TEST read returned 30 offers with zero eligible players;
Manchester United and Barcelona rosters were empty, with CATALOG_NOT_READY.
The exact local paired catalog has 30 and 29 memberships respectively. This is
independent of Switch save files. Do not delete payment journals to fix it.

The companion fnx_server patch checks/restores incomplete TEST memberships on
API/all startup using its existing paired catalog file locations (overridable
via FNX_TEST_CATALOG_SQLITE and FNX_TEST_CATALOG_MANIFEST). Repair verifies the
SQLite hash, size, active content hash and runtime pair before its transaction.
It preserves accounts, wallets, ownership, purchases and match results.
See backend docs/CLIENT_V116.md. Deployment and live post-repair purchase remain
separate from local verification; a client build cannot repair the server DB.

## Verification

Host checks exercise the real async controller, native editor and render
adapter, including A hold/release/cancel and team-before-size navigation.
Backend tests use disposable PostgreSQL databases and test full 90-minute
recordings across all ten editor shapes, three defensive lines and trap on/off.
These are host/synthetic checks, not on-device acceptance.

Final local checks: 148 client tests and 147 subtests passed. The complete
PostgreSQL suite passed with the race detector; go vet was clean. The production
C parser accepted the new backend tape at 661 playback positions. Public-tree
scanning of the backend still reports four pre-existing absolute deployment-path
findings (main, RUNBOOK, config, routes); no proprietary payload or credentials
are added by this patch. Live deployment/repair and Switch acceptance are pending.
