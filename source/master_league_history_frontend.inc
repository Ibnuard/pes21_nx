/* Read-only season archive; no cached projection or additional ownership data. */
static uint32_t history_selected;
static uint32_t ml_honour_count(uint32_t mask) {
  uint32_t count=0u;
  for(;mask;mask>>=1u)count+=mask&1u;
  return count;
}
static int ml_history_pad(uint32_t pressed) {
  if(page!=ML_PAGE_HISTORY && page!=ML_PAGE_SEASON_DETAIL && page!=ML_PAGE_CAREER_STATS)return 0;
  if(pressed&ML_B) {
    if(page==ML_PAGE_HISTORY){ml_page(ML_PAGE_MANAGER_OFFICE);focus=3u;}
    else {ml_page(ML_PAGE_HISTORY);focus=history_selected;}
    return 1;
  }
  uint32_t count=page==ML_PAGE_HISTORY ? career.history.count+1u : page==ML_PAGE_CAREER_STATS ? 5u :
      8u+career.history.seasons[career.history.count-history_selected].scorer_count;
  ml_scroll(pressed,count,&focus,pressed&(ML_L|ML_R) ? 5u : 1u);
  if(page==ML_PAGE_HISTORY && (pressed&ML_A)) {
    history_selected=focus;
    ml_page(focus ? ML_PAGE_SEASON_DETAIL : ML_PAGE_CAREER_STATS);
  }
  return 1;
}
static void ml_history_view(MlView *v) {
  if(page!=ML_PAGE_HISTORY && page!=ML_PAGE_SEASON_DETAIL && page!=ML_PAGE_CAREER_STATS)return;
  memset(v->rows,0,sizeof(v->rows));memset(v->info,0,sizeof(v->info));
  v->count=v->action_count=0u;v->first=focus/5u*5u;v->selected=focus;
  const char *title=page==ML_PAGE_HISTORY ? "CAREER ARCHIVE" : page==ML_PAGE_CAREER_STATS ? "ARCHIVED SEASON TOTALS" : "SEASON REVIEW";
  snprintf(v->title,64,"%s",title);snprintf(v->left_title,64,"%s",title);
  snprintf(v->caption,96,"%s",career.history.count ?
      "Season-end club records - only archived seasons are included" :
      "Finish a season and start the next to create your first archive");
  if(page==ML_PAGE_HISTORY) {
    v->total=career.history.count+1u;
    for(uint32_t i=v->first;i<v->total && v->count<5u;i++) {
      MlViewRow *r=&v->rows[v->count++];r->enabled=1;
      if(!i) {
        snprintf(r->label,64,"TOTALS & TROPHIES");
        snprintf(r->detail,96,"Recorded club seasons, goals and honours");
        snprintf(r->value,48,"%u %s",career.history.count,career.history.count==1u ? "SEASON" : "SEASONS");
        r->emblem=3u;
      } else {
        const MlSeasonRecord *s=&career.history.seasons[career.history.count-i];
        snprintf(r->label,64,"SEASON %u OF %u TROPHIES",s->season,ml_honour_count(s->honours));
        snprintf(r->detail,96,"%s",exhibition_team_catalog_name(s->club));
        snprintf(r->value,48,"RANK %u OF %u",s->rank,s->team_count);
        r->badge=exhibition_team_catalog_badge(s->club);
      }
    }
  } else if(page==ML_PAGE_CAREER_STATS) {
    uint32_t played=0,wins=0,draws=0,losses=0,gf=0,ga=0,trophies=0,league=0,cup=0,other=0;
    int64_t income=0,expenses=0;
    for(uint32_t i=0;i<career.history.count;i++) {
      const MlSeasonRecord *s=&career.history.seasons[i];
      played+=s->standing.played;wins+=s->standing.wins;draws+=s->standing.draws;losses+=s->standing.losses;
      gf+=s->standing.goals_for;ga+=s->standing.goals_against;
      trophies+=ml_honour_count(s->honours);league+=(s->honours&ML_HONOUR_LEAGUE)!=0;
      cup+=(s->honours&ML_HONOUR_CUP)!=0;other+=ml_honour_count(s->honours&~3u);
      income+=s->match_income+s->prize_income;expenses+=s->wages_paid;
    }
    const char *labels[]={"ARCHIVE COVERAGE","TROPHIES","LEAGUE RECORD","LEAGUE GOALS","SEASON OPERATING TOTALS"};
    v->count=v->total=5u;v->first=0u;
    for(uint32_t i=0;i<5u;i++){snprintf(v->rows[i].label,64,"%s",labels[i]);v->rows[i].enabled=1;}
    if(career.history.count)snprintf(v->rows[0].detail,96,"SEASONS %u - %u OF %u RECORDS",career.history.seasons[0].season,
        career.history.seasons[career.history.count-1u].season,career.history.count);
    else snprintf(v->rows[0].detail,96,"No earlier results are inferred from legacy saves");
    snprintf(v->rows[1].value,48,"%u",trophies);
    snprintf(v->rows[1].detail,96,"LEAGUE %u - CUP %u - CONTINENTAL + NATIONAL %u",league,cup,other);
    snprintf(v->rows[2].detail,96,"P %u   W %u   D %u   L %u",played,wins,draws,losses);
    snprintf(v->rows[3].detail,96,"FOR %u - AGAINST %u - GD %+d",gf,ga,(int)gf-(int)ga);
    char earned[32],paid[32];ml_money(earned,sizeof(earned),income);ml_money(paid,sizeof(paid),expenses);
    snprintf(v->rows[4].detail,96,"MATCH + PRIZE %s - WAGES %s",earned,paid);
  } else {
    const MlSeasonRecord *s=&career.history.seasons[career.history.count-history_selected];
    snprintf(v->left_title,64,"SEASON %u OF %u TROPHIES",s->season,ml_honour_count(s->honours));
    snprintf(v->caption,96,"%s - season-end club record",exhibition_team_catalog_name(s->club));
    v->total=8u+s->scorer_count;
    for(uint32_t i=v->first;i<v->total && v->count<5u;i++) {
      MlViewRow *r=&v->rows[v->count++];r->enabled=1;
      if(!i) {
        snprintf(r->label,64,"LEAGUE RECORD");snprintf(r->value,48,"RANK %u OF %u",s->rank,s->team_count);
        snprintf(r->detail,96,"P %u W %u D %u L %u - GF %u GA %u OF %u PTS",s->standing.played,s->standing.wins,
            s->standing.draws,s->standing.losses,s->standing.goals_for,s->standing.goals_against,s->standing.points);
      } else if(i<6u) {
        const char *labels[]={"LEAGUE CHAMPION","DOMESTIC CUP CHAMPION","CONTINENTAL CHAMPION","REGIONAL CHAMPION","WORLD CUP CHAMPION"};
        const uint32_t teams[]={s->league_champion,s->cup_champion,s->continental_champion,s->regional_champion,s->world_champion};
        snprintf(r->label,64,"%s",labels[i-1u]);
        snprintf(r->detail,96,"%s",teams[i-1u] ? exhibition_team_catalog_name(teams[i-1u]) : "NOT HELD - NO RECORDED WINNER");
        r->badge=teams[i-1u] ? exhibition_team_catalog_badge(teams[i-1u]) : 0u;
      } else if(i<6u+s->scorer_count) {
        const LeagueScorer *p=&s->scorers[i-6u];
        snprintf(r->label,64,"TOP SCORER %u - %.38s",i-5u,p->name);
        snprintf(r->detail,96,"%s",p->team ? exhibition_team_catalog_name(p->team) : "MULTIPLE CLUBS - COMBINED SEASON TOTAL");
        snprintf(r->value,48,"%u GOALS",p->goals);r->portrait=p->portrait_id;
      } else if(i==6u+s->scorer_count) {
        snprintf(r->label,64,"CLOSING CASH");ml_money(r->value,48,s->closing_cash);
        snprintf(r->detail,96,"Before the next season operating grant");
      } else {
        char earned[32],paid[32];ml_money(earned,sizeof(earned),s->match_income+s->prize_income);ml_money(paid,sizeof(paid),s->wages_paid);
        snprintf(r->label,64,"SEASON OPERATING TOTALS");snprintf(r->detail,96,"MATCH + PRIZE %s - WAGES %s",earned,paid);
      }
    }
  }
  v->helper_count=page==ML_PAGE_HISTORY ? 4u : 3u;
  if(page==ML_PAGE_HISTORY){v->helper_key[0]="A";v->helper_label[0]="OPEN";}
  const uint32_t k=page==ML_PAGE_HISTORY ? 1u : 0u;
  v->helper_key[k]="B";v->helper_label[k]="BACK";
  v->helper_key[k+1u]="L";v->helper_label[k+1u]="PREV PAGE";
  v->helper_key[k+2u]="R";v->helper_label[k+2u]="NEXT PAGE";
  if(v->total<=5u)v->helper_count=k+1u;
}
