# Online review v117

The authenticated TEST read found 20 owned players, including two PACK players,
but only 18 registered players. Purchases were present; the client had no way
to insert collection reserves into Game Plan.

## Controls and ownership

- Online drag uses the same normalized HID screen coordinates as Exhibition.
  Physical up is negative screen Y. Explicit navigation directions take priority
  over an inconsistent native axis sign; horizontal movement is preserved.
- Game Plan loads the complete owned collection. In Substitute, focus a starter
  or bench player, press X (Reserves), then A to replace that slot. The displaced
  player remains owned. Goalkeeper checks and set-piece assignments are preserved.
  B leaves the picker; changes are submitted only on Save & Back.
- Backend saves Game Plan and its registered eighteen in one transaction, under
  the existing revision lock. It returns the committed plan in the acknowledgement.
  The client verifies this response directly; older servers use the GET fallback.
  Existing published fixtures/recordings are not rewritten.

## Shop and promotion

- Pack detail has an explicit BUY action, independent of the last footer helper.
  Explanatory footnotes are available through ZL Info.
- Pool selection/deselection is local. Confirm sends one POST with all selected
  keys to the existing grant endpoint. No per-player selection PUT or status GET.
  An uncertain confirmation retains its key and choices for an exact retry.
- Y in Shop and the pool opens Purchased Players. It uses owned collection
  metadata (origin PACK and acquisition time), newest first, five per page,
  with L/R pagination. Back preserves the unfinished pool and cursor.
- Promotion entry shows no reward amount. A validated receipt reveals the actual
  NX Cash amount; it is no longer required to equal 5,000. Other reward types
  require a future API contract. Backend redemption recovery uses its recorded
  amount. This patch does not change the current minting policy.

## Read policy

Session memory holds at most 16 read responses, bounded to 128 KiB each. Caches
are cleared on logout, account/realm/cycle/phase changes and successful grants. Plan
saves invalidate plan, squad and profile. Explicit refresh bypasses the cache.

| Data | Maximum reuse | Refresh trigger |
| --- | --- | --- |
| Collection, squad, Game Plan | 120 seconds | Ownership/plan mutation or expiry |
| Pack offers | 60 seconds | Payment/grant or expiry |
| Profile, standings, feed, schedule, opponent | 30 seconds | Scope change or expiry |
| Auth, payments, grant, receipts, promotion | Never cached | Explicit operation/recovery |

Cached reads never reset the server-clock anchor. Current background schedule
responses refresh the same schedule cache. Hub preview requests no longer open
successive modal loading popups. Writes still wait for authoritative confirmation.
Purchase receipts already contain the wallet revision/balance; the client uses
that snapshot and fetches bootstrap only as a compatibility fallback. A grant
does not refetch bootstrap because it does not change the wallet.

## Verification

Host tests exercise the production controller and renderer adapters: local
selection request counts, history return/pagination, reserves and goalkeeper
validation, one-request save acknowledgements, cache expiry/scope/clock guards,
non-5,000 promotion receipts, physical stick normalization and drag directions.
PostgreSQL tests cover direct grant without selection autosave, immutable grant
retries, Game Plan/squad atomicity and rollback, and promotion receipt recovery.
Visual previews use the C renderer with synthetic players; they are not Switch
captures. Final build/test hashes are recorded in the local v117 verification.

Deploy the companion backend patch described in fnx_server/docs/CLIENT_V117.md
before testing reserve changes on Switch. No save deletion or catalog reset.
