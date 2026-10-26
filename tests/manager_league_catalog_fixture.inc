/* Host fixture only: invented identities/portraits, never shipped in a runtime. */
#include "master_league_catalog.h"
#include "exhibition_team_catalog.h"
#include <stdio.h>
#include <string.h>
static MlCatalogPlayer fixture_players[256];
static char fixture_names[256][48];
static void fixture_catalog(void) {
  if(fixture_players[0].identity)return;
  const uint32_t clubs[8]={100,101,102,103,108,109,119,121};
  for(uint32_t i=0;i<256;i++) {
    snprintf(fixture_names[i],48,"Fixture Player %03u",i+1);
    fixture_players[i]=(MlCatalogPlayer){10000+i,20000+i,30000+i,clubs[i/32],(uint8_t)(60+i%10),(uint8_t)(i%13),(uint8_t)(i%32+1),fixture_names[i]};
  }
}
const char *ml_catalog_content_id(void){return "1111111111111111111111111111111111111111111111111111111111111111";}
const char *ml_catalog_manager_binding_id(void){return ml_catalog_content_id();}
const char *ml_catalog_pair_id(void){return "1234567890abcdef";}
uint32_t ml_catalog_player_count(void){fixture_catalog();return 256;}
const MlCatalogPlayer *ml_catalog_player_at(uint32_t i){fixture_catalog();return i<256 ? &fixture_players[i] : NULL;}
const MlCatalogPlayer *ml_catalog_find_identity(uint32_t id){fixture_catalog();return id>=10000 && id<10256 ? &fixture_players[id-10000] : NULL;}
int ml_catalog_has_real_portrait(uint32_t id){return ml_catalog_find_identity(id)!=NULL;}
int ml_catalog_has_team(uint32_t team){return exhibition_team_catalog_find(team)!=NULL;}
