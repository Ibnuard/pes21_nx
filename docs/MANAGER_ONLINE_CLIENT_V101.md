# Manager League HTTPS client — v101 integration

## Current client v112 — 29 October 2026

LEAGUE has four cards: W1/W2 Ranking History, monthly League Ranking, Logout,
and League Guide. Monthly ranking has Current Season (all entries) and Past
Season (one champion per completed month), five display rows and 50-row server
pages with stable snapshots. A new capability gate prevents legacy RP from
being shown as monthly PTS. Reset uses calendar months in WIB. The profile
accepts the new nullable monthly_ranking object and hides stale season totals.

The HOME phase tile shows a red LIVE badge when the current Match Day has a
live broadcast. Background schedule refresh is bounded; kickoff/end and cache
freshness guard the badge. Registration text no longer includes A TO JOIN.
TODAY is aligned as a separate badge. Player Feed has separate goal, assist and
OVR columns, and Club Feed opens directly onto activity cards.

See [MANAGER_HUB_V112.md](MANAGER_HUB_V112.md) for exact DTOs, additive 500 entry
and 2,000/1,500/1,000 podium points, MySQL ledger, reset/concurrency rules and
acceptance. DEV OFFLINE keeps a local monthly projection from existing archives;
it never uploads points. This revision uses host tests and renderer previews;
it does not claim a live API retest or device acceptance.

## Current hub v111 — 29 October 2026

The hub now has HOME, MY TEAM and LEAGUE tabs. The first tile shows a phase
countdown and registration status. A requests registration confirmation only
when eligible and not joined; registered/preparation states show an OK message.
Match Day and League End open Match Centre. Schedule is a seven-day WIB calendar.

Club Feed uses large activity cards. Player Feed supports the new
`player_feed_v1` capability and `/league/player-feed` contract. The latter needs
backend implementation before enabling it. Exact routing, DTOs, MySQL guidance,
publication rules and acceptance are in [MANAGER_HUB_V111.md](MANAGER_HUB_V111.md).
The current-cycle and full recording findings in the v110 review remain open.
No new live backend retest is implied by this UI revision.


## Current client v110 — 29 October 2026

The own-club Game Plan is now an editable local draft. XI/bench swaps, position
changes, formation, four tactics and captain/set-piece assignments do not make
network requests. A dirty leave sends one full-plan PUT with expected_revision;
GET confirms the saved plan. An uncertain save keeps its draft, original body
and UUID for retry/check. Explicit reload discards only after a valid GET.
Opponent Game Plan has no edit actions and one last-saved-data caption.

Online hub restores real top-three standings, fixture previews and club crests.
Schedule/watch/opponent/table use presentation_team_id for local atlas lookup,
while club_id remains the server navigation identity. The competition page has
distinct rewards, champions, own history, overall ranking and guide entries.
Schedule shows kickoff dates in WIB; an unpublished table has an explanatory
empty state. The timeline reads registration/fixture/reward timestamps when
available. Conflicting membership is reported; published current-window fixtures
prevent an erroneous second JOIN prompt.

Portraits remain bound to canonical player_key through the paired local catalog.
All slots have a procedural fallback; the GPU queue rotates so a missing asset
cannot starve later slots. Audit of the current 18 TEST starters found 6 photos,
8 neutral silhouette assets and 4 missing bindings. This supersedes the earlier
assumption that every nonzero binding represented a real photo.

Recorded playback caches 22 chunks. It loads chunk 0 even at watermark 0 and bridges
frame gaps across chunk/half-time boundaries. A frozen TEST watermark is surfaced
after 15 seconds and network errors permit Retry/Back. Full-recording playback is
implemented behind bootstrap.capabilities.match_recording_bundle: one GET
/matches/{id}/playback returns all 22 chunks and all events, max 4 MiB decompressed.
LIVE uses the server kickoff offset, replay starts at 0, and future event/score data
stays hidden until the playback cursor reaches it. That new endpoint/capability
is **not yet available on the retested deployment**; legacy reads remain supported.
See [the current backend contract](BACKEND-REVIEW.md) before enabling the flag.

Live API verification: client-encoded Game Plan saved and read back successfully,
then original content restored (revision 1→2→3). Fixture 55's 22 chunks and 470 events
passed the C parser; all 661 one-second cursor positions rendered, including the
half-time boundary. The original recording hash stayed unchanged by the plan
edit. Event actor/recipient names are now populated; v109's missing-name finding
is closed. Calendar membership and advancing TEST live time remain backend work.

Validation: 59 host tests and 131 subtests pass. Fifteen pages were rendered with
the production C functions and captured deployment payloads. The Switch NRO is
built with `build-wsl.ps1`; hardware acceptance remains pending.

The following sections describe earlier releases and historical limitations;
their read-only online-editor restriction is superseded by v110.

## Previous client v109

Client update **v109**, 29 October 2026: online portrait requests now use the
active provider and include all 18 Game Plan slots. Existing canonical IDs and
the local paired catalog remain authoritative for portraits; no backend image
URL or donor face is accepted. Four of the tested 18 starters have no portrait
binding in this catalog; the other 14 can now reach the existing GPU loader.

Frontend ticks now run before the loading input gate, so TEST clock receipts,
polling and the 60-second recovery timeout can progress while the cover is shown.
Input remains blocked during the operation. The network worker still has its
20-second HTTP timeout; an unanswered mutation retains its original request ID.

Payment recovery reads the existing account/realm journal UUID and original
body. Shop can check `/shop/operations/{key}` or retry that same purchase without
generating a fresh payment ID. A local journal write failure sends no POST and
does not mark a new payment uncertain; leaving and reopening Shop remains usable.
Corrupt or unverifiable records are retained and block a new payment. A verified
paid pack still requires player selection before leaving. The old journal format
remains readable. Do not delete SaveData to work around a payment popup.

Club Profile now shares the offline crest layout with six online submenus:
registered squad, standings, own match history, overall rank, saved Game Plan,
and rewards. Server rank, league points and RP are shown; missing ranks do not
become position zero. Back restores the profile submenu focus. The hub caption
shows the calendar phase separately from membership; an unpublished calendar is
shown explicitly. The font draws underscores at baseline, preserving displayed
User IDs such as `fnx_dev` without changing authentication input.

Backend v109 retest: recorded TEST matches now pass the client C parser,
including all 22 chunks and 470 events of one match. Current-window rotation
still returns the last SETTLED W2 on the next Monday. See the
[latest backend review](BACKEND-REVIEW.md) for evidence and remaining contracts.
Hardware/filesystem acceptance is still required on the user's Switch.

Validation for v109: **50 host tests passed** (33 online controller/recovery,
14 Game Plan/font, three competition flows) and 30 deployed payload parser
checks passed. Host renders of the shared profile layout and underscore text
were inspected. Native devkitPro/Makefile build, O3/LTO1, retains runtime pair
`e861c583ec78e9ae`; the previously unavailable WSL setup was not retried.
Build ID `f834e528bc67b0d5363d605d2647a46094312573`;
NRO SHA256 `8c702bf8d0f2db8eaf8646348f9366c509f8bc094925a17f224fd8ca6ceeea06`.
Install only the NRO update over the existing paired runtime. Preserve SaveData.

Backend-only retest **v108**,28 October2026: close/autofill to4, six fixtures,
finished standings and Sunday5000 payout now work in the tested1-human group;
replay does not double credit. Remaining server blockers: TEST recording header
stays SCHEDULED/watermark0 and chunks say MATCH_NOT_STARTED even after report/
schedule end; W2/current phase and next-Monday registration do not rotate
correctly. See [current review](BACKEND-REVIEW.md). No source or NRO changed on
v108; v107 remains the current client build, with its guards intact.

Source/build candidate **v107**,28 October2026. Real DEV login returns TEST;
normal QA returns PRODUCTION; TEST CDK grants exactly5000 once with replay/lookup
verified, and cross-realm redemption is rejected. Four new routes are deployed.
**Backend blocker:** clock advance/Finish Week returns SUCCEEDED while W1 stays
REGISTRATION with1human,0BOT, no fixtures even at Sunday. See
[current backend review](BACKEND-REVIEW.md); no client-generated results hide it.
Client now fetches league/status for an unjoined null-league bootstrap, accepts
authorized raw chunk arrays in TEST, and validates realm before clearing journals
on error.28 host tests cover these cases and existing flows. Build is a test
candidate, not hardware or complete server-calendar acceptance.

V107 NRO built with the installed Windows devkitPro SDK/Makefile after canonical
build-wsl.ps1 failed during WSL mount/systemd startup. Jobs1/LTO1, O3 and paired
catalog/runtime inputs retained. Build ID `ae25d88650f6cf5484f240ea2985575e305bdcbf`;
SHA256 `315c1be0352e46c522e4c83835686b8173efaea607ad8cc364afaa1183d43986`.
Update only the NRO over the existing v100/v101 runtime pair; this does not
replace game assets or save files. No automatic device installation was made.

Source update **v106**,28 October2026: account-authorized ONLINEDEV and CDK
consumers added. Login/refresh/bootstrap environment TEST enables ONLINEDEV;
production and legacy responses never gain demo-time privilege by User ID alone.
Hub TEST Y opens Next Milestone / Finish Week; Shop X opens Promotion Code input
when server capability is enabled. API jobs, receipts, durable retry journals,
realm assertions and monotonic auth TTL are implemented. DEV OFFLINE is retained.
See the [exact new API and storage contract](MANAGER_ONLINEDEV_CDK_V106.md).
The deployed41-operation OpenAPI still lacks these additions; real TEST/CDK
acceptance awaits backend implementation and a provisioned DEV account.
**24 async host tests pass** (14new+10regressions). This source change does not
update the old v101 NRO or prove Switch hardware/internet acceptance.

28 October 2026. This is an integration candidate, not Switch hardware acceptance
or confirmation that every backend product feature is ready.

Latest backend retest v105, 28 October: forged canonical keys and tactic enums
are rejected, schedule/header state and time agree, and all22 recording chunks
including halftime pass the actual C parser. Game Plan guards, Save replay/CAS,
payment replay, minimum-four group and schedule/standings semantics also pass
the focused probes. See [current review](BACKEND-REVIEW.md) for evidence and limits.
Source accepts minimum four from the earlier fix; v105 makes no source/NRO
changes. Ten async host tests pass. The delivered v101 NRO needs a later build;
online editor/draft wiring, recovery lookup and other UI integration remain.

New editor contract: changes stay in a local draft; send one full-plan save
when leaving a dirty editor, zero writes for a clean leave or internal submenu.
Keep draft on timeout/conflict and use revision/idempotency guards. This is
documented behavior for implementation; it does not enable the online editor.

## Entry points and provider boundary

The normal Main Menu Online League entry opens `manager_league_online.*` through
`manager_league_client.*`. It checks the deployed compatibility endpoint before
allowing account requests. The source retains the existing frontend enum name
`COMPETITION_FRONTEND_MANAGER_DUMMY` for ABI/call-site stability; that name no
longer selects the local provider.

At the idle Main Menu, hold **ZL + ZR + Y together for two seconds** to open
DEV OFFLINE. Release before opening it again. The shortcut is unavailable in
matches, other frontends, loading, keyboard and Main Menu popup flows. Offline
DEV retains the existing local saves, fixture simulation, account and clock
controls. Offline DEV never changes online clock/wallet. ONLINEDEV is a separate,
server-authorized TEST account mode on the normal online provider; it may advance
only TEST domain time through the new job API. Production has no demo clock.

`manager_league_client.*` dispatches input, view DTOs, keyboard actions, ticks
and the existing commentary/audio event boundary. The online provider does
not invoke the local simulator or use local cash/results as server authority.

## Implemented online paths

- Compatibility/version/catalog/pair check, update/maintenance messages.
- Register and Login using User ID plus a controller-only four-digit PIN;
  leading zeros survive JSON encoding. Registration displays the recovery code
  returned by the server. The client does not currently expose PIN recovery or
  recovery-code re-claim endpoints for existing accounts.
- Refresh-token session resume, proactive refresh, one refresh/retry for an
  expired read request, and local logout even when remote revocation cannot
  be confirmed. Unsafe POSTs are not automatically repeated after a disconnect.
- Server-confirmed wallet, club profile, registered squad, collection and
  latest saved Game Plan, including the server's assigned roles/coordinates.
- Offer pages, explicit price/version consent, payment, opening animation,
  mandatory player selection, selection autosave, grant and pending-pack resume.
- Schedule sections LIVE / SCHEDULED / MATCH ENDED, current standings, news,
  overall ranking and champions reads. Empty responses show empty states.
- Header/chunk/events playback, bounded gzip decoding, frame interpolation,
  released-event touchline and event-driven commentary publication. Late join
  uses server kickoff offset; replay supports pause and 30-second seeking.
- Existing loading popup and informational/error popup presentation. Online
  hub cards do not populate local synthetic league standings or news.

Schedule navigation: left/right selects a column, up/down selects a row;
L/R changes status section. Live status polling is non-modal and cannot reopen
a watch page the user already closed. Unknown shirt numbers remain unlabelled;
instance IDs/array indexes are not displayed as invented shirt numbers.

## Transport and response limits

Base URL: `https://wedreamku.my.id/footballnx/api/v1`, as observed on deployment.
Online version `1.0.0`, API schema `1`, catalog content SHA256
`2ffab2858daa681400e89445d75c28c0d8ac951bd36b0ec4af35ff08020f1222`,
runtime pair `e861c583ec78e9ae`. An unpaired local build cannot pass the gate.

One pthread worker owns a request at a time. Network calls never run in the
render/game thread. Responses from a closed provider generation are discarded.
Worker-owned loading tokens finish independently of the input/render loop.

libcurl uses HTTPS only, verified peer certificate and hostname, TLS 1.2 minimum,
no redirects, 6-second connect timeout and 20-second request timeout. It does not
log bodies, PINs or tokens. HTTP gzip and the deployment's gzip JSON-array chunk
format are decoded with an output bound. The installed Switch portlib curl is
linked before zlib/libnx. See curl's
[peer verification](https://curl.se/libcurl/c/CURLOPT_SSL_VERIFYPEER.html),
[hostname verification](https://curl.se/libcurl/c/CURLOPT_SSL_VERIFYHOST.html)
and [content decoding](https://curl.se/libcurl/c/CURLOPT_ACCEPT_ENCODING.html).

Current bounds are 512 KiB response/decoded payload, 32,768 JSON tokens,
32 nesting levels, 128 collection players/offers, 256 schedule/list rows,
512 events, 128 frames per chunk and a two-chunk cache. Oversized or invalid
payloads fail visibly; the client does not truncate them into financial actions.
Backend pagination/cursors are required before accounts/catalogs exceed those
bounds. These are client bounds, not product inventory limits.

## Session and payment recovery files

All paths below are relative to the prepared runtime working directory:

- `SaveData/manager-online-session-v2.dat`: origin/realm-bound refresh token and
  User ID, with temporary/backup rotation. Old v1 caches require a fresh login;
  logout removes both versions. No PIN, access token or recovery code.
  This is a plaintext SD-card session cache, not encrypted secure storage;
  anyone who can read it must be treated as able to use that refresh token.
- `SaveData/manager-online-pay-<account-id>.dat`: idempotency key and payment
  request intent written before the financial POST. It contains no credentials.
  Account IDs in paths are validated decimal digits.
- TEST payment recovery uses `manager-online-pay-TEST-<account-id>.dat` so the
  same numeric production account ID cannot load it. Clock and CDK intents use
  `manager-online-{clock|promotion}-{TEST|PRODUCTION}-<account-id>.dat`, with
  origin/realm/account validation inside each record. They survive logout until
  a final server outcome resolves them. An unresolved CDK intent temporarily
  contains its code; keep it private and never publish or log it.

After an ambiguous payment, Shop retrieves server pending state rather than
issuing another payment. A valid paid receipt resumes the same pool and saved
selection. If pending is null without proof of the previous payment's outcome,
the intent survives restart and further purchases stay blocked. The backend
receipt lookup added in the backend retest still needs client integration and
a documented retention/legacy contract for automatic resolution;
deleting the local journal is not a safe reconciliation strategy.

Online logout removes only the online session cache. A payment intent remains
bound to its account so switching accounts does not erase an unresolved payment.
Existing local DEV account, wallet, player and fixture files are untouched.

## Remaining integration and acceptance work

The integration does not silently substitute offline features for missing APIs:

| Feature | Current restriction |
| --- | --- |
| Join | v101 gate remains disabled; +1,500 credit previously verified, minimum-four/BOT snapshot and current schedule now pass; client activation and full calendar acceptance remain |
| Squad registration / Game Plan editing | Backend ownership/revision/Save probes now pass; client editor and local draft/Save-on-leave wiring remain |
| Opponent submenus / reward entitlements / history navigation | Require published profile/snapshot/history/settlement schemas |
| Ambiguous payment with no pending pack | New backend operation lookup requires client integration and durable retention/legacy rules |
| Natural movement and scorer identity | Uses actual frames/events; cannot repair static formations or absent actor bindings by inventing data |
| 3D COM vs COM / video | Deferred by the user; no 3D stream or engine execution is added |

V105 schedule/header public state and kickoff now agree for all six fixtures:
fixture29 ENDED with score, five future fixtures SCHEDULED on Saturday with null
scores. Names/IDs/timestamps and standings semantics parse correctly. Fixture29
was regenerated with a new hash; all22 chunks, including halftime10/11, are
nonempty arrays accepted by the C decoder. This is wire/decoder verification,
not Switch rendering/audio or multi-viewer LIVE acceptance.
Actual multi-viewer LIVE
watermarks, schedule payloads for a joined account, calendar/BOT autofill/settlement,
Switch TLS/certificate compatibility and audible commentary on hardware still
require acceptance tests. The source has bounded parsing for observed DTOs;
untested schedule field aliases are not a substitute for a typed API contract.

## Verification and follow-up

`tests/test_manager_online_client.py` compiles the real async controller with
synthetic in-process HTTP replies, not a copy of its implementation. Tests cover
PIN preservation, server gate, paid selection/grant, restart recovery, ambiguous
payment blocking, session refresh/logout, same kickoff offset, future-event
filtering, stale watch replies, malformed coordinates/chunks, JSON bounds and
the DEV shortcut. No test creates production accounts or embeds QA credentials.

The authorized QA parser audit additionally exercised production response
bodies for bootstrap, offers, squad, legal Game Plan, pending pack, old ENDED
header, frame chunk and events through the actual C parser; all eight pass
after the minimum-four source fix. V105 additionally accepts all14 positive
payload probes and all22 recording chunks. One SCHEDULED header is intentionally
rejected by the LIVE/ENDED watch parser; the schedule UI already shows the
scheduled-broadcast popup rather than opening watch for that phase. This is
expected guard behavior, not an outstanding server decoding failure.
Those proprietary/credential-bearing diagnostics remain ignored locally.

Builds use the already accepted v100 runtime pair and `build-wsl.ps1`, with
output under ignored `local-debug/manager-online-api-v1/`. No prepared runtime,
asset archive or user's SaveData is replaced automatically. Host checks and
SDK linking are not a device or internet gameplay test.

Backend fixes and required acceptance tests:
[BACKEND-REVIEW.md](BACKEND-REVIEW.md).
