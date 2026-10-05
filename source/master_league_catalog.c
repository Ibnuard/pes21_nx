#include "master_league_catalog.h"

typedef struct {
  uint32_t identity, native_id, portrait_id, club;
  uint8_t overall, position, shirt;
  const char *name;
} MlCatalogPlayer;
#ifndef ML_CATALOG_INCLUDE
#define ML_CATALOG_INCLUDE "master_league_catalog_generated.inc"
#endif
#include ML_CATALOG_INCLUDE

const char *ml_catalog_content_id(void) { return ML_CATALOG_CONTENT_ID; }
const char *ml_catalog_pair_id(void) { return ML_CATALOG_PAIR_ID; }
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
