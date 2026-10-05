#include "master_league_catalog.h"
#include "fl26_league_catalog_generated.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

int main(void) {
  MasterLeague *c=malloc(sizeof(*c));assert(c);
  uint32_t eligible=0u;
  for(uint32_t league=0;league<FL26_LEAGUE_CUSTOM_INDEX;league++) {
    const Fl26LeagueCatalogEntry *entry=&fl26_league_catalog[league];
    int valid=1;
    for(uint32_t i=0;i<entry->pool_count;i++)valid &= ml_catalog_has_team(entry->team_ids[i]);
    if(!valid)continue;
    const MlSettings settings={entry->competition_id,entry->team_ids[0],3u,10u,5u,1u,5u,0u};
    assert(ml_init(c,ml_catalog_content_id(),&settings,"Local Audit",1u,999u));
    assert(ml_catalog_import(c));
    assert(ml_start_season(c,entry->team_ids,entry->pool_count,NULL,0u));
    assert(ml_valid(c));
    MlEvent event;uint32_t events=0u;
    while(ml_next_event(c,&event) && event.kind!=ML_EVENT_SEASON_END) {
      assert(ml_simulate_event(c,&event));assert(ml_valid(c));
      assert(++events<=62u);
    }
    assert(ml_next_season(c) && ml_valid(c));eligible++;
  }
  assert(eligible==FL26_LEAGUE_CUSTOM_INDEX);
  printf("local catalog: %u clubs, %u players, %u leagues simulated and rolled over\n",c->club_count,c->player_count,eligible);
  free(c);return 0;
}
