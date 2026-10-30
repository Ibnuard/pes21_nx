# Manager League API deployment: integration review v1

Initial contract review: 28 October 2026. The sections below preserve the
read-only discovery stage. An authorized single-account QA pass and client
adapter have since been added; see [BACKEND-REVIEW.md](BACKEND-REVIEW.md) for
current authenticated findings and [client implementation](MANAGER_ONLINE_CLIENT_V101.md).
This is not a source/database security audit or a Switch hardware acceptance test.

Latest retest v105 on 28 October: the remaining v104 key/tactic validation,
schedule/header disagreement and null halftime chunks now pass focused tests.
Game Plan guards, Save replay/CAS and financial replay regressions also pass.
All22 recording chunks decode with the actual C parser; response schemas for
schedule/standings validate. See BACKEND-REVIEW for evidence, integration work
and untested acceptance areas. Findings below describe the original deployment.

Later product amendment: minimum four total teams, with 1–3 human entrants
filled to four using BOTs at registration close. This replaces the old
eight-human/carry policy discussed in this historical review. The current
BACKEND-REVIEW and handoff §7 define the required implementation and tests.

API documentation: [deployed OpenAPI](https://wedreamku.my.id/footballnx/openapi.yaml).
Specification snapshot SHA256:
`51ffdf80bc23606835a1c687795bcf6fa94fbf5f4a76822e47292e7a25ac4f1f`.
Local diagnostic receipts: `local-debug/manager-online-api-v1/` (ignored).
Product requirements remain in [backend handoff](MANAGER_BACKEND_HANDOFF_V1.md).

## Verified without changing server data

| Read-only request | Observed response |
| --- | --- |
| GET `/footballnx/api/v1/compatibility` | 200, online1.0.0, API schema1, maintenance=false |
| GET `/footballnx/api/v1/health/ready` | 200 READY; confirms the published readiness response, not an independent DB audit |
| GET `/footballnx/api/v1/me/bootstrap`, client online0.9.0 | 426 CLIENT_UPDATE_REQUIRED |
| Same protected GET with missing online version | 426 CLIENT_UPDATE_REQUIRED |
| Same protected GET with online1.0.0 and wrong catalog hash | 409 CATALOG_SYNC_REQUIRED |
| Same protected GET with current version/catalog and no token | 401 UNAUTHORIZED |
| GET `/api/v1/compatibility` at domain root | 404 |

The catalog hash advertised by compatibility matches our exported SQLite:
`2ffab2858daa681400e89445d75c28c0d8ac951bd36b0ec4af35ff08020f1222`.
The advertised runtime pair is `e861c583ec78e9ae`. This verifies the announced
values, not the rows in the private server database. At this initial read-only stage no account was created or authenticated.
The later authorized QA pack/refresh and Join evidence is recorded in
BACKEND-REVIEW.md. No production clock was changed; calendar carry and
settlement remain unverified.

## Fix before relying on the online client contract

### Public base URL

The specification's server URL resolves to the domain root, while the deployed
service is under a prefix. Set the public OpenAPI server URL to:

```yaml
servers:
  - url: https://wedreamku.my.id/footballnx/api/v1
```

The NRO adapter must use that observed HTTPS base. Do not switch to HTTP, disable
certificate verification or redirect authenticated requests to an unrelated host.

### Participation is a credit, not an entry fee

The published Join description and insufficient-funds response imply a fee.
Our confirmed product rule is **+1500 NX Cash**, once per logical league entry.
There must be no wallet-minimum requirement for receiving that participation
bonus. Determine whether this is documentation drift or implementation behavior
using an authenticated backend integration test; the read-only probes cannot
establish the money flow.

Required backend test: create a synthetic test account in a test database,
capture wallet/ledger, Join once, retry with the same and a different idempotency
key, and carry an under-eight cohort into the next registration window.
Assert one ledger credit of +1500, the same entry across carry, and no second
credit. Do not perform these tests on real user wallets.

### Wire schemas and mutation rules

The snapshot contains 38 operations, with no typed success-response schemas;
three have success examples. Presence in OpenAPI does not prove behavior.
Complete the response/request schemas before generating or freezing a C adapter:

- Envelopes, error codes, ID types, nullability and pagination/cursors.
- Token lifetime/session fields, refresh retry behavior and recovery payloads.
- Bootstrap capabilities, pending purchase and all versions/revisions.
- Owned instance IDs versus canonical `player_key` versus native asset bindings.
- Exact Game Plan tactic enums, XI/bench item fields, position coordinates,
  preset/roster references and optimistic revision checks.
- Offer version/price consent, pending receipt/pool, selection revision and
  granted instance IDs. Paying an offer must require explicit accepted price
  and version; the client must not infer these from a later offer fetch.
- Required idempotency keys on mutation routes that change persistent state,
  and the same-key/different-body conflict rule. The schema currently exposes
  optional idempotency headers on only purchase and Join; this does not prove
  backend deduplication is absent, but its public contract is incomplete.
- League windows/carry-over, roster lock, confirmed match day and Sunday payout
  status. An announced final result is distinct from a paid entitlement.

Use one JSON ID convention consistently. Our handoff uses decimal strings for
database IDs; the current examples mix string IDs and integer IDs. If a deliberate
wire change is retained, specify integer bounds and update client fixtures and
the contract version coherently rather than guessing from examples.

### Recording payload and anti-spoiler rules

Document the recording header, compression/content type, frame/event payload,
actor-slot/ownership mapping, coordinate units, chunk bounds, watermark, half-time
pause, event cursor and replay-expiry behavior. The description mentions 22
chunks for a 660-second broadcast, whereas the handoff proposes two-second
chunks. Twenty-two uniform chunks would imply thirty seconds each; actual chunk
length and release semantics have not been observed with an authenticated match.
Do not hardcode either interpretation in the renderer.

Whole-chunk release after its end can create a lag equal to its length; release
before its end can reveal future events. Pick and test a documented design with
a bounded live lag and no future score leakage through schedule, news, standings,
rewards or reports. All viewers use server kickoff time and the same stored tape.
Opening the watch page must not create a new match clock or simulation.

The user additionally proposed preparing every match-day recording in advance.
The deployed worker's compute/lock timing is not established by the OpenAPI.
If adopting full-day precomputation, freeze the day's Game Plans before that
batch and document the cutoff; do not promise both immutable precomputed results
and later plan edits that affect those already-computed matches.

## Feature coverage to document or complete

The following capabilities are required by the agreed client UX but are not
fully represented in this OpenAPI snapshot. They may exist privately; check
backend code/tests before declaring them missing from the server:

| Capability | Required clarification or addition |
| --- | --- |
| Register players from collection into the squad | A squad mutation with ownership, size and revision validation; changing Game Plan alone is not a substitute for collection registration |
| Multiple formations/presets | Legal formations, three saved presets and apply behavior; retain supported client choices or explicitly version the reduction |
| Club name/presentation editing | Authorized profile mutation and revision check |
| Opponent profile/history/Game Plan | Public club IDs, last-published snapshot/as_of, read-only squad and match history without exposing wallet or draft plan |
| Previous league navigation | Cycle/group parameters or history routes; a current-only schedule cannot implement previous-week browsing |
| Rewards and pending Sunday payouts | Rules, entitlement, payout time, pending/settled/delayed status, both W1/W2 results |
| Historical ranking/champion details | Period/group IDs, immutable original presentation and final standings |
| Wallet reconciliation/history | Ledger proof/tests; an authenticated wallet/history route if the UI needs it |
| Runtime/build compatibility | Required build policy is advertised, but approved build IDs and request-header behavior are not specified |
| Group sizes | Confirm fixed eight versus the proposed range8..16 and how leftover entrants are handled; never silently start a group below eight |

## Route names can be adapted

These path changes need not block integration if their schemas/semantics match:

| Handoff logical function | Deployed documentation path |
| --- | --- |
| Team roster | `/catalog/teams/{id}/roster` |
| Own club/collection/squad/Game Plan | `/club/profile`, `/club/collection`, `/club/squad`, `/club/gameplan` |
| Pending paid pack | `/shop/pending` |
| Save selection / grant | `/shop/purchases/{id}/selection`, `/shop/purchases/{id}/grant` |
| Current league / Join / schedule / standings | `/league/status`, `/league/join`, `/league/schedule`, `/league/standings` |
| Playback header / chunk | `/matches/{id}/recording/header`, `/matches/{id}/recording/chunks/{chunk}` |
| Overall Rank / honours | `/ranking/overall`, `/ranking/champions` |

Normalize these behind the client domain interface. Avoid exposing HTTP route
names to UI code or reshaping the offline UI around unfinished server responses.

## Client integration boundary (updated)

The source now dispatches Main Menu Online League to a separate asynchronous
HTTPS provider. The legacy local provider remains behind the hidden offline
DEV shortcut. Supported account, wallet, pack and recording DTOs were checked
against the authorized QA responses, rather than frozen from absent schemas.
See [client implementation](MANAGER_ONLINE_CLIENT_V101.md).

This does not establish that the full online product is ready. Join is held
for the documented fee/credit conflict; online squad/Game Plan editing and
opponent/reward/history menus await complete contracts. Unknown payment results
without a pending receipt remain blocked until the server can reconcile them.
The full review and backend acceptance tasks are in
[BACKEND-REVIEW.md](BACKEND-REVIEW.md).
