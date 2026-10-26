#ifndef PES21_MASTER_LEAGUE_CATALOG_H
#define PES21_MASTER_LEAGUE_CATALOG_H
#include "master_league.h"

/* Immutable metadata from the exact locally paired runtime. identity is the
 * canonical BaseId when available; high-bit identities are local-only players
 * and must not be treated as eFootball BaseIds. Native and portrait IDs are
 * storage/asset keys, never a replacement for canonical identity. All fields
 * are bound to ml_catalog_content_id() and ml_catalog_pair_id(). */
typedef struct {
  uint32_t identity, native_id, portrait_id, club;
  uint8_t overall, position, shirt;
  const char *name;
} MlCatalogPlayer;

const char *ml_catalog_content_id(void);
const char *ml_catalog_pair_id(void);
/* Manager League binds the unchanged player metadata to current native
 * fingerprints. Returns "unpaired" unless the compiled career catalog matches
 * the audited source pins in manager_league_catalog_binding.h. */
const char *ml_catalog_manager_binding_id(void);
/* Manager-only eligibility: canonical BaseId has an audited native portrait
 * distinct from the exact generic silhouette. Unknown, unscanned and unpaired
 * identities return zero. Does not change career or original club pack policy. */
int ml_catalog_has_real_portrait(uint32_t identity);
uint32_t ml_catalog_player_count(void);
/* Index enumeration is O(1), preserves native club/roster order, and returns
 * NULL out of bounds. Returned entries remain valid for the process lifetime. */
const MlCatalogPlayer *ml_catalog_player_at(uint32_t index);
/* Returns NULL for zero/unknown identities. Consumers drawing repeated player
 * profiles should retain player_at() pointers in their own roster cache. */
const MlCatalogPlayer *ml_catalog_find_identity(uint32_t identity);
int ml_catalog_import(MasterLeague *career);
int ml_catalog_has_team(uint32_t team);
#endif
