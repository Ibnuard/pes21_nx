# Online hub Back v119

Pressing B on the authenticated Online League hub previously entered the page
breadcrumb handler. An empty breadcrumb returned to the hub again, so the
visible Back helper did nothing on all three tabs.

The hub now emits `MD_ACTION_EXIT`, using the existing competition frontend
close transition to return to the native main menu. Closing clears in-memory
authentication but preserves the saved refresh session. Reopening Online
League resumes that session; Back does not call logout or remove saves.

B also exits while advisory hub previews are loading. The close operation
invalidates their generation, so a late response cannot reopen the mode,
publish stale data or continue the preview request chain. Modal API operations
retain their existing guard. Information and registration popups consume B
before the hub; child pages still return through their normal breadcrumbs.

Regression coverage checks every hub tab, saved-session bytes, automatic
session resume, background reads and late responses, popup dismissal, modal
requests and child-page navigation. The existing Game Plan, roster, purchase,
native editor and frontend flow suites remain part of verification.

Verification result: 87 focused tests and 135 subtests passed, plus three
frontend/axis regression tests. The new cases reproduced the missing exit
before the correction and now pass through exit and session resume.

This is a client-only change. It uses the same runtime assets and backend
contract as v118; no backend deployment or save reset is required. Host
verification and a Switch build are separate from physical-device acceptance.

## Player database check, 30 October 2026

The active curated selector contains 394 teams: 306 clubs and 88 national
teams. A fresh collection was started against the public eFootballDB team API
for that exact scope. The first 68 completed team requests all returned HTTP
522, with no usable roster. Collection was stopped after the repeated endpoint
failure; the remaining 326 teams have no completed response in this capture.

No transfer conclusion or runtime data update can be made from this incomplete
capture. The older 5 October snapshot is not presented as current information.
The capture, complete team checklist and failure evidence are kept under
ignored `local-inputs/efootballdb-updates/2026-10-30-v119/` and
`local-debug/manager-v119/roster-audit/`. A new complete capture is required
before comparing BaseIds and verified identities or applying any transfers.
