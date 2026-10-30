/* Owned players must be directly reachable through the native bench list. */
static void owned_plan_v118(void){
  v117_setup();open_squad(1);idle();MdView v;manager_online_view(&v);
  assert(v.plan_count==26&&online.plan_count==26&&online.plan_focus==MO_PLAYERS);
  for(unsigned i=0;i<26;i++){
    assert(v.plan_players[i].label[0]);
    for(unsigned j=0;j<i;j++)assert(online.plan_roster[i]!=online.plan_roster[j]);
  }
  assert(!strcmp(v.plan_players[18].label,"Player 19")&&!strcmp(v.plan_players[25].label,"Player 26"));
  unsigned before=http_calls;manager_online_pad(A);
  for(unsigned i=0;i<11&&online.plan_focus<11;i++)manager_online_pad(RIGHT);
  assert(online.plan_focus==11);
  for(unsigned i=0;i<7;i++)manager_online_pad(DOWN);
  assert(online.plan_focus==18&&online.plan_bench_focus==7);
  manager_online_view(&v);assert(!strcmp(v.helper_label[0],"SWAP"));
  manager_online_pad(A);manager_online_pad(LEFT);
  unsigned field=online.plan_focus;assert(field>0&&field<11);
  uint64_t previous=online.plan.ids[field];manager_online_pad(A);
  assert(online.plan.ids[field]==119&&online.plan_roster[18]==previous&&online.plan_dirty);
  /* The preserved bench cursor returns to the reserve we just swapped. */
  for(unsigned i=0;i<11&&online.plan_focus<11;i++)manager_online_pad(RIGHT);
  assert(online.plan_focus==18);manager_online_pad(DOWN);manager_online_pad(A);
  for(unsigned i=0;i<7;i++)manager_online_pad(UP);
  assert(online.plan_focus==12);manager_online_pad(A);
  assert(online.plan.ids[12]==120&&online.plan_count==26&&http_calls==before);
  manager_online_pad(B);assert(online.plan_focus==MO_PLAYERS&&http_calls==before);
  manager_online_pad(B);idle();assert(plan_puts==1&&http_calls==before+1&&!online.plan_dirty);
  /* Reload from server snapshots, not only the in-memory draft. */
  read_cache_clear();open_squad(1);idle();manager_online_view(&v);
  assert(online.plan.ids[field]==119&&online.plan.ids[12]==120&&v.plan_count==26);
  unsigned owned=0;for(unsigned i=0;i<26;i++){
    assert(v.plan_players[i].label[0]);owned+=online.plan_roster[i]==previous;
    for(unsigned j=0;j<i;j++)assert(online.plan_roster[i]!=online.plan_roster[j]);
  }
  assert(owned==1);manager_online_pad(B);assert(plan_puts==1);
}
static void owned_plan_boundary_v118(void){
  v117_setup();open_squad(1);idle();
  for(unsigned i=26;i<MO_PLAYERS;i++){
    MoPlayer *p=&online.players[i];p->instance=101+i;snprintf(p->key,sizeof(p->key),"ef:%u",i+1);
    snprintf(p->row.label,sizeof(p->row.label),"Owned %u",i+1);p->row.role=1;p->row.rating=70;
  }
  online.player_count=MO_PLAYERS;plan_display();assert(online.plan_count==MO_PLAYERS);
  manager_online_pad(A);for(unsigned i=0;i<11&&online.plan_focus<11;i++)manager_online_pad(RIGHT);
  assert(online.plan_focus==11);unsigned before=http_calls;
  manager_online_pad(UP);assert(online.plan_focus==MO_PLAYERS-1);
  MdView v;manager_online_view(&v);assert(!strcmp(v.plan_players[MO_PLAYERS-1].label,"Owned 128"));
  manager_online_pad(A);assert(online.plan_pick==MO_PLAYERS-1);
  manager_online_pad(LEFT);assert(online.plan_focus<11);manager_online_pad(A);
  assert(online.plan.ids[online.plan_focus]==228&&http_calls==before);
  manager_online_pad(B);assert(online.plan_focus==MO_PLAYERS);
  manager_online_pad(RIGHT);assert(online.plan_focus==MO_PLAYERS+1);
  manager_online_pad(A);assert(online.page==MD_PLAN_SETTINGS&&online.plan_menu==1);
}
