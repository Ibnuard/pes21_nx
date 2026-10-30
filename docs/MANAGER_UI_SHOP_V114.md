# Manager League v114 — UI and shop corrections

30 October 2026. Supersedes the seven-row-at-once weekly schedule in v112.

- Weekly Schedule is one scrollable column, four days visible out of seven.
  Analog/D-pad changes focus and follows the viewport. Dates, W1/W2, short
  descriptions and TODAY remain visible, with a 1–4 / 4–7 range indicator.
- Online own/opponent Game Plan enters the existing offline Game Plan render
  branch in overlay.c through manager_gameplan_render_adapter.inc. Native
  pitch/bench, names, portraits, role/rating plates and action components are
  reused, centered as one panel. Input remains the online controller and saves
  its draft once on leaving via API; rendering cannot mutate engine squads.
  Actions are SUBSTITUTE, FORMATION, TACTIC, POSITIONS. Opponent replaces the
  action area with LATEST SAVED TEAM DATA and has no editing focus.
  Missing portraits are queued through the existing asynchronous loader even
  on direct Game Plan entry; a rotating five-image batch avoids starvation.
  A silhouette stays visible until the real portrait is available.
- Hub lower tiles use 24 physical pixels between columns and rows; League's
  lower two tiles fill their row. Club lists use matching top/bottom insets.
- ZL INFO opens contextual help locally with an OK popup. Generic explanatory
  footnotes, repeated OPEN labels and ranking-rule footers move there. Essential
  countdown, registration status, price, points and player statistics remain.
- Known no-charge errors PACK_POOL_UNAVAILABLE / OFFER_ALREADY_PURCHASED clear
  an unpaid purchase intent and return to Shop. Unknown payment outcomes keep
  their original UUID/body for recovery. SaveData is not deleted or reset.

Backend findings and deployment/data-repair commands:
[V114-SHOP-SIMULATION.md](https://github.com/BlekjekSudo/fnx_server/blob/main/docs/V114-SHOP-SIMULATION.md) in the
separate backend checkout. Public client review: [BACKEND-REVIEW.md](BACKEND-REVIEW.md).

Host rendering and controller tests are not Switch hardware acceptance. The
Game Plan now uses the offline production renderer; older standalone dummy
Game Plan previews do not represent this new production path.

## Verification result

104 host tests and 144 subtests passed. The portrait queue regression was rerun after the final render change. Go race tests, vet and server build passed at backend commit 58c99167ea82c418999fb64d9f8f5f991a6a90ce. The new synthetic full tape passed the C parser at 661 playback times. Client public-tree audit passed (1,548 files).

NRO 86786975 bytes; SHA-256 81c616286f1e5e5e71c4f789b3cc751bce7a89f8fc1c4d2b4b1d644582b38ad9. All 241 pinned source/build inputs and three ELF load segments match; launcher icon is exact. Runtime pair e861c583ec78e9ae, dummy OBB 53,248 bytes. The delivery contains only the NRO and two public verification/install files.

Live shop success is pending backend deployment and TEST catalog inspection/repair; no live acceptance or Switch hardware acceptance is claimed.
