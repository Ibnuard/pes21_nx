#include "master_league_catalog.h"
#include "manager_league_catalog_binding.h"
#include "manager_league_portrait_eligibility.h"
#include <stddef.h>
#include <string.h>

#ifndef ML_CATALOG_INCLUDE
#define ML_CATALOG_INCLUDE "master_league_catalog_generated.inc"
#endif
#include ML_CATALOG_INCLUDE

const char *ml_catalog_content_id(void) { return ML_CATALOG_CONTENT_ID; }
const char *ml_catalog_pair_id(void) { return ML_CATALOG_PAIR_ID; }
const char *ml_catalog_manager_binding_id(void) {
  return !strcmp(ML_CATALOG_CONTENT_ID, ML_MANAGER_SOURCE_CATALOG_CONTENT_ID) &&
         !strcmp(ML_CATALOG_PAIR_ID, ML_MANAGER_SOURCE_PAIR_ID)
             ? ML_MANAGER_CATALOG_BINDING_ID : "unpaired";
}
int ml_catalog_has_real_portrait(uint32_t identity) {
  if (!identity || (identity & 0x80000000u) ||
      strcmp(ml_catalog_manager_binding_id(), ML_MANAGER_PORTRAIT_BINDING_ID))
    return 0;
  uint32_t low=0u, high=ML_MANAGER_REAL_PORTRAIT_ID_COUNT;
  while (low<high) {
    const uint32_t mid=low+(high-low)/2u;
    if (ml_manager_real_portrait_baseids[mid]<identity) low=mid+1u;
    else high=mid;
  }
  return low<ML_MANAGER_REAL_PORTRAIT_ID_COUNT &&
         ml_manager_real_portrait_baseids[low]==identity;
}
uint32_t ml_catalog_player_count(void) { return ML_CATALOG_PLAYER_COUNT; }
const MlCatalogPlayer *ml_catalog_player_at(uint32_t index) {
  const uint32_t total=ML_CATALOG_PLAYER_COUNT;
  return index < total ? &ml_catalog_players[index] : NULL;
}
const MlCatalogPlayer *ml_catalog_find_identity(uint32_t identity) {
  if (identity) {
    const uint32_t total=ML_CATALOG_PLAYER_COUNT;
    for (uint32_t i=0; i<total; i++)
      if (ml_catalog_players[i].identity == identity) return &ml_catalog_players[i];
  }
  return NULL;
}
int ml_catalog_has_team(uint32_t team) {
  uint32_t count=0u;
  const uint32_t total=ML_CATALOG_PLAYER_COUNT;
  for (uint32_t i=0; i<total; i++)
    count += ml_catalog_players[i].club == team;
  return count >= 11u && count <= ML_SQUAD_SIZE;
}
int ml_catalog_import(MasterLeague *career) {
  const uint32_t total=ML_CATALOG_PLAYER_COUNT;
  for (uint32_t i=0; i<total; i++) {
    const MlCatalogPlayer *entry=&ml_catalog_players[i];
    MlPlayer p={0};
    p.identity=entry->identity; p.native_id=entry->native_id;
    p.portrait_id=entry->portrait_id; p.overall=entry->overall;
    p.position=entry->position; p.shirt=entry->shirt;
    uint32_t n=0u;
    while (entry->name[n] && n+1u<sizeof(p.name)) { p.name[n]=entry->name[n]; n++; }
    if (!ml_add_player(career,entry->club,&p)) return 0;
  }
  return career && career->player_count != 0u;
}
