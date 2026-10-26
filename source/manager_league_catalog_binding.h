/* Project-authored hashes only. No native player records or game assets.
 * Audited against the accepted v93 runtime on 2026-10-26. Recompute these pins
 * whenever the Manager League source catalog or native identity state changes.
 * The career catalog hash intentionally remains unchanged for career saves.
 * Packaging must verify source file hashes; this is build-time provenance,
 * not runtime verification that an installed CPK has these contents. */
#ifndef PES21_MANAGER_LEAGUE_CATALOG_BINDING_H
#define PES21_MANAGER_LEAGUE_CATALOG_BINDING_H

#define ML_MANAGER_CATALOG_BINDING_ID \
  "74073ef84b98e515b2d6102185eabc6e3517a8d46990d85e0251f50d2fb7668f"
#define ML_MANAGER_SOURCE_PAIR_ID "e861c583ec78e9ae"
#define ML_MANAGER_SOURCE_CATALOG_CONTENT_ID \
  "97e84d7f8c21ba930bb0e13793ac46c91a60836a33902d40100d36aa5801a59f"
#define ML_MANAGER_SOURCE_CATALOG_FILE_SHA256 \
  "8cbd0cb123dc86ae2f00c28462fd8415e907187e1df2f3550a65499f2585b7fc"
#define ML_MANAGER_IDENTITY_STATE_SHA256 \
  "438a0dc547bf3bbfce7452284b7c9e457754e42045b9f2e5014dac5f59cee40d"
#define ML_MANAGER_PLAYER_CPK_SHA256 \
  "5a677a002255cd39668e0394651efb2475a500951c2018aec99e1ab183f0baf6"

#endif
