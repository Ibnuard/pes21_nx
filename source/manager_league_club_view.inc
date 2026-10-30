/* Read-only club projections. Opponent rosters are the saved local league
 * entries, never the original club's full real-world roster. */
static void club_summary(MdView *v) {
  if(!profile_ready)return;
  MdRow league[MD_TEAMS],overall[MD_TEAMS];table_rows(league);overall_rows(overall);
  for(uint32_t i=0;i<MD_TEAMS;i++) {
    if(!league[i].team_id)v->league_points=league[i].stats.points;
    if(league[i].team_id==team_choice)v->club_rank=i+1;
    if(overall[i].team_id==team_choice){v->rank=i+1;v->club_reputation=(uint32_t)strtoul(overall[i].value,NULL,10);}
  }
  v->club_team=team_choice;
  for(uint32_t n=0;n<11;n++)if(squad[team_choice][n])v->club_power+=squad[team_choice][n]->overall;
  v->club_rating=(v->club_power+5u)/11u;
}
static void club_profile_view(MdView *v) {
  static const char *const labels[]={"REGISTERED SQUAD","LEAGUE STANDINGS","MATCH HISTORY","LEAGUE RANKING","GAME PLAN","LEAGUE REWARDS"};
  static const char *const details[]={"Players, positions and attributes","Position and points in this league","Your club's scheduled games and replays","Current month and past season champions","Formation and starting eleven","Entry bonus and finishing rewards"};
  copy(v->headline,sizeof(v->headline),team_name(team_choice));
  copy(v->caption,sizeof(v->caption),team_choice ? "LEAGUE CLUB PROFILE" : "YOUR CLUB PROFILE");
  copy(v->club,sizeof(v->club),exhibition_team_catalog_name(profile.clubs[team_choice]));
  v->badge=badge(team_choice);v->total=6;v->first=focus>3 ? 1u : 0u;v->count=5;
  for(uint32_t i=0;i<v->count;i++) {
    uint32_t at=v->first+i;char value[40]="OPEN";
    if(at==1)snprintf(value,sizeof(value),"POSITION %u",v->club_rank);
    if(at==3)snprintf(value,sizeof(value),"RANK %u",v->rank);
    if(at==4)copy(value,sizeof(value),team_choice ? "OPEN" : "EDIT");
    row(v,i,labels[at],details[at],value,0);
  }
  helper(v,"LS","SCROLL");helper(v,"A","OPEN");
}
static void club_plan_view(MdView *v) {
  copy(v->headline,sizeof(v->headline),team_name(team_choice));
  copy(v->caption,sizeof(v->caption),"GAME PLAN");v->badge=badge(team_choice);
  copy(v->summary,sizeof(v->summary),"4-3-3");
  /* Local opponent entries currently use their registered default 4-3-3.
   * API snapshots will supply their saved formation when online is connected. */
  for(uint32_t n=0;n<18;n++) {
    const MlCatalogPlayer *p=squad[team_choice][n];if(!p)continue;
    MdPlanPlayer *r=&v->plan_players[n];copy(r->label,sizeof(r->label),p->name);
    r->portrait=p->portrait_id;r->rating=p->overall;r->role=p->position;r->identity=p->identity;
  }
}
static void club_rewards_view(MdView *v) {
  copy(v->headline,sizeof(v->headline),"LEAGUE REWARDS");
  copy(v->caption,sizeof(v->caption),"Participation bonus plus finishing rewards - NX Cash");
  v->count=5;
  row(v,0,"STARTING WALLET","Once when you create your manager account","5,000 NX CASH",0);
  row(v,1,"LEAGUE PARTICIPATION","Every league you join, including your first","1,500 NX CASH",0);
  row(v,2,"CHAMPION","Added after the league's final broadcast","5,000 NX CASH",0);
  row(v,3,"SECOND PLACE","Added after the league's final broadcast","4,000 NX CASH",0);
  row(v,4,"THIRD PLACE","Added after the league's final broadcast","3,000 NX CASH",0);
  helper(v,"LS","SCROLL");
}
