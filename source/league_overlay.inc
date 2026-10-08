/* League broadcast UI. Read-only rendering; season simulation and all input
 * stay in competition_frontend.c. Shared controls are the ML/Cup primitives. */
static void league_ui_art(MasterLeagueRender *ui,uint32_t sprite,float x,float y,float w,float h,
    GLfloat *verts,int *quads) {
  const uint32_t first=ui->draw_count;
  cup_ui_art(ui,sprite,x,y,w,h,verts,quads);
  if(ui->draw_count>first)ui->draws[first].texture=gl.league_news_tex;
}
static void league_ui_logo(MasterLeagueRender *ui,float x,float y,float w,float h,GLfloat *verts,int *quads) {
  const GLuint texture=current_league_logo_texture();
  const uint32_t index=competition_frontend_league_catalog_index();
  const float aspect=texture && index<FL26_LEAGUE_CATALOG_COUNT && gl.league_logo_aspect[index]>0.f
      ? gl.league_logo_aspect[index] : texture ? 1.f : 1120.f/424.f;
  const float box=w*screen_width/(h*screen_height);
  const float iw=aspect<box ? h*screen_height*aspect/screen_width : w;
  const float ih=aspect>box ? w*screen_width/aspect/screen_height : h;
  ml_ui_image(ui,texture ? texture : gl.main_menu_brand_tex,0,x+(w-iw)*.5f,y+(h-ih)*.5f,iw,ih,verts,quads);
}
static uint32_t league_ui_owner(uint32_t team) {
  const CompetitionEntryDraft *d=competition_frontend_league_draft();
  if(d && team)for(uint32_t i=0;i<d->team_count;i++)if(d->teams[i]==team)return d->owners[i];
  return 0u;
}
static uint32_t league_ui_champion(void) {
  const LeagueTournament *l=competition_frontend_league_tournament();
  if(!l || l->phase!=LEAGUE_PHASE_COMPLETE)return 0u;
  if(l->reserved[0]==LEAGUE_SYSTEM_KNOCKOUT)return l->knockout.champion;
  uint8_t slots[LEAGUE_MAX_TEAMS];league_tournament_ranked_slots(l,slots);
  return l->team_count ? l->standings[slots[0]].team : 0u;
}
static const char *league_ui_round(uint32_t round) {
  const LeagueTournament *l=competition_frontend_league_tournament();
  const uint32_t count=l ? l->knockout.round_count : 0u;
  return round+1u==count ? "FINAL" : round+2u==count ? "SEMI FINAL" : "QUARTER FINAL";
}
static int league_ui_next_teams(uint32_t *home,uint32_t *away) {
  const LeagueTournament *l=competition_frontend_league_tournament();
  uint32_t fixture=0,round=0,index=0;*home=*away=0;
  if(!l || !league_tournament_next_human(l,&fixture,&round,&index))return 0;
  if(l->phase==LEAGUE_PHASE_TABLE) {
    *home=l->fixtures[fixture].home;*away=l->fixtures[fixture].away;
  } else {
    const CupFixture *f=cup_tournament_fixture(&l->knockout,round,index);
    if(!f)return 0;
    *home=f->home;*away=f->away;
  }
  return 1;
}
static void league_ui_header(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  MlDraw *d=ml_ui_draw(ui,*quads,2);if(!d)return;
  d->texture=gl.league_header_tex;
  const float vh=3.f/(.94f*screen_width/(.133f*screen_height)),v=(1.f-vh)*.5f;
  d->uv[0]=0;d->uv[1]=v;d->uv[2]=1;d->uv[3]=vh;
  d->round=(RoundedRectStyle){.94f*screen_width,.133f*screen_height,9.f};
  *quads+=emit_image_rect_uv(.03f*screen_width,.03f*screen_height,.94f*screen_width,.133f*screen_height,
      0,v,1,v+vh,verts+*quads*24);
}
static void league_ui_landing(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  league_ui_art(ui,0,.04f,.190f,.522f,.710f,verts,quads);
  ml_ui_rect(ui,.04f,.657f,.522f,.243f,.012f,.085f,.18f,.94f,-1,0,1,verts,quads);
  cup_ui_text(ui,"EVERY MATCHDAY MATTERS",.065f,.692f,.470f,.042f,-1,verts,quads);
  ml_ui_text(ui,"Build the league. Write the season.",.065f,.763f,.470f,.029f,2,-1,0,1,verts,quads);
  cup_ui_text(ui,"1-8 PLAYERS   /   ONE TITLE RACE",.065f,.850f,.470f,.025f,-1,verts,quads);
  const uint32_t focus=competition_frontend_focus();
  for(uint32_t i=0;i<2u;i++) {
    const float y=.190f+i*.365f;
    ml_ui_panel(ui,i ? "CONTINUE" : "NEW LEAGUE",i ? ML_HEADER_SAVE : ML_HEADER_RANKING,
        .59f,y,.37f,.345f,focus==i,verts,quads);
    competition_ui_pattern(ui,i ? 3u : 0u,.59f,y+.075f,.37f,.270f,verts,quads);
    cup_ui_text(ui,i ? "YOUR SEASON, SAVED" : "SET THE STAGE",.611f,y+.122f,.325f,.031f,-2,verts,quads);
    ml_ui_text(ui,i ? "Resume the title race." : "Build your league.",.611f,y+.182f,.325f,.026f,2,-3,0,1,verts,quads);
    ml_ui_button(ui,.609f,y+.259f,.332f,.065f,focus==i,1,verts,quads);
    ml_ui_center_text(ui,i ? "LOAD LEAGUE" : "CREATE LEAGUE",.609f,y+.259f,.332f,.065f,.030f,0,-1,verts,quads);
  }
}
static void league_ui_settings(MasterLeagueRender *ui,int general,GLfloat *verts,int *quads) {
  const uint32_t focus=general ? competition_frontend_cup_general_focus() : competition_frontend_focus();
  const uint32_t count=general ? competition_frontend_cup_general_count() : 5u;
  const uint32_t start=general ? focus/5u*5u : 0u;
  char info[96];
  ml_ui_panel(ui,"YOUR LEAGUE",ML_HEADER_RANKING,.04f,.190f,.318f,.710f,0,verts,quads);
  league_ui_art(ui,2,.051f,.287f,.296f,.305f,verts,quads);
  league_ui_logo(ui,.073f,.311f,.252f,.254f,verts,quads);
  cup_ui_text(ui,competition_frontend_league_name(),.061f,.632f,.276f,.0333f,-2,verts,quads);
  snprintf(info,sizeof(info),"%u TEAMS   /   %u PLAYERS",competition_frontend_league_team_count(),competition_frontend_league_player_count());
  cup_ui_text(ui,info,.061f,.691f,.276f,.027f,-3,verts,quads);
  cup_ui_text(ui,competition_frontend_league_system()==LEAGUE_SYSTEM_STANDINGS ? "CHAMPION BY STANDINGS" : "LEAGUE + KNOCKOUT",.061f,.751f,.276f,.026f,-2,verts,quads);
  cup_ui_text(ui,competition_frontend_league_home_away() ? "HOME & AWAY" : "SINGLE ROUND ROBIN",.061f,.831f,.276f,.025f,-3,verts,quads);
  ml_ui_panel(ui,general ? "GENERAL SETTINGS" : "LEAGUE SETTINGS",ML_HEADER_SETTINGS,.383f,.190f,.577f,.710f,0,verts,quads);
  if(general)competition_ui_pattern(ui,2u,.383f,.790f,.577f,.110f,verts,quads);
  for(uint32_t i=start;i<count && i<start+5u;i++) {
    MlViewRow row={0};row.enabled=1;
    row.adjustable=general || i!=2u || competition_frontend_league_catalog_index()==FL26_LEAGUE_CUSTOM_INDEX ? 1u : ML_VALUE_FIXED;
    static const char *labels[]={"LEAGUE TYPE","PLAYERS","TEAMS","HOME & AWAY","LEAGUE SYSTEM"};
    snprintf(row.label,sizeof(row.label),"%s",general ? competition_frontend_cup_general_label(i) : labels[i]);
    snprintf(row.value,sizeof(row.value),"%s",general ? competition_frontend_cup_general_value(i) : competition_frontend_item_value(i));
    ml_ui_row(ui,&row,.400f,.298f+(i-start)*.093f,.543f,.078f,focus==i,0,verts,quads);
  }
  if(general) {
    snprintf(info,sizeof(info),"PAGE %u / %u",start/5u+1u,(count+4u)/5u);
    cup_ui_text(ui,info,.404f,.839f,.29f,.025f,-3,verts,quads);
  } else {
    ml_ui_button(ui,.706f,.812f,.236f,.065f,focus==5u,1,verts,quads);
    ml_ui_center_text(ui,"CREATE LEAGUE",.706f,.812f,.236f,.065f,.028f,0,-1,verts,quads);
  }
}
static void league_ui_slots(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const int saving=competition_frontend_league_slots_saving();
  league_ui_art(ui,0,.04f,.190f,.318f,.710f,verts,quads);
  ml_ui_rect(ui,.04f,.668f,.318f,.232f,.012f,.085f,.18f,.94f,-1,0,1,verts,quads);
  cup_ui_text(ui,saving ? "KEEP THE SEASON" : "BACK TO THE LEAGUE",.061f,.709f,.276f,.0333f,-1,verts,quads);
  ml_ui_text(ui,"Every team. Every matchday.",.061f,.787f,.276f,.027f,2,-1,0,1,verts,quads);
  for(uint32_t i=0;i<3u;i++) {
    const float y=.190f+i*.245f;char title[32];snprintf(title,sizeof(title),"SLOT %02u",i+1u);
    const int used=competition_frontend_league_slot_valid(i),selected=competition_frontend_focus()==i;
    ml_ui_panel(ui,title,ML_HEADER_SAVE,.383f,y,.577f,.220f,selected,verts,quads);
    cup_ui_text(ui,used ? competition_frontend_slot_competition(i) : "EMPTY SLOT",.402f,y+.104f,.357f,.031f,-2,verts,quads);
    cup_ui_text(ui,used ? competition_frontend_slot_progress(i) : "NO SEASON SAVED",.402f,y+.166f,.350f,.025f,-3,verts,quads);
    ml_ui_button(ui,.785f,y+.126f,.153f,.069f,selected,saving || used,verts,quads);
    ml_ui_center_text(ui,saving ? used ? "OVERWRITE" : "SAVE" : "LOAD",.785f,y+.126f,.153f,.069f,.025f,0,-1,verts,quads);
  }
}
static void league_ui_news(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const LeagueTournament *l=competition_frontend_league_tournament();
  const CompetitionEntryDraft *d=competition_frontend_league_draft();
  const uint32_t story=competition_frontend_league_news_index(),champion=league_ui_champion();
  char tag[48]="SEASON OVERVIEW",headline[112]="THE SEASON STARTS WITH YOU",detail[112];
  snprintf(detail,sizeof(detail),"%u / %u teams assigned. %u players in the league.",competition_draft_assigned_count(d),d->team_count,d->player_count);
  if(story==1u) {
    uint32_t home=0,away=0;snprintf(tag,sizeof(tag),"MATCHDAY WATCH");
    if(league_ui_next_teams(&home,&away)) {
      if(l->phase==LEAGUE_PHASE_TABLE)snprintf(headline,sizeof(headline),"MATCHDAY %u",l->active_matchday+1u);
      else snprintf(headline,sizeof(headline),"%s",league_ui_round(l->knockout.active_round));
      snprintf(detail,sizeof(detail),"%s vs %s",cup_ui_team(home),cup_ui_team(away));
    } else {
      const int ready=competition_draft_ready(d);
      snprintf(headline,sizeof(headline),champion ? "THE FINAL WHISTLE" : ready ? "THE SEASON MOVES ON" : "BUILD YOUR LINE-UP");
      snprintf(detail,sizeof(detail),champion ? "The complete season is in Match Centre." : ready ? "Advance to resolve the remaining fixtures." : "Assign the teams to reveal your opening matchday.");
    }
  } else if(story==2u) {
    snprintf(tag,sizeof(tag),"TABLE WATCH");
    snprintf(headline,sizeof(headline),"THE RACE FOR FIRST PLACE");
    snprintf(detail,sizeof(detail),"Every win earns 3 points. Every draw earns 1.");
    if(l->team_count && l->first_match_started) {
      uint8_t slots[LEAGUE_MAX_TEAMS];league_tournament_ranked_slots(l,slots);
      const LeagueStanding *leader=&l->standings[slots[0]];
      snprintf(headline,sizeof(headline),"%s",cup_ui_team(leader->team));
      snprintf(detail,sizeof(detail),"%u POINTS   /   %u PLAYED   /   %+d GOAL DIFFERENCE",leader->points,leader->played,(int)leader->goals_for-(int)leader->goals_against);
    }
  } else if(story==3u) {
    snprintf(tag,sizeof(tag),champion ? "LEAGUE CHAMPIONS" : "THE TITLE RACE");
    snprintf(headline,sizeof(headline),"%s",champion ? cup_ui_team(champion) : "ONE LEAGUE. EVERY CONTENDER.");
    if(champion)snprintf(detail,sizeof(detail),"Season complete. Revisit the table and every result.");
    else if(competition_frontend_league_system()==LEAGUE_SYSTEM_KNOCKOUT)
      snprintf(detail,sizeof(detail),"The top %u teams qualify for the knockout stage.",league_tournament_qualifier_count(d->team_count));
    else snprintf(detail,sizeof(detail),"The team at the top after the final matchday wins.");
  }
  ml_ui_frame(ui,.04f,.190f,.57f,.480f,competition_frontend_focus()==5u,verts,quads);
  league_ui_art(ui,story,.04f,.190f,.57f,.480f,verts,quads);
  cup_ui_text(ui,"LEAGUE NEWS",.062f,.215f,.39f,.031f,-1,verts,quads);
  if(story==3u && champion)cup_ui_badge(ui,champion,.104f,.269f,.153f,verts,quads);
  ml_ui_rect(ui,.04f,.441f,.57f,.229f,.012f,.07f,.18f,.95f,-1,0,1,verts,quads);
  cup_ui_text(ui,tag,.062f,.462f,.522f,.022f,-1,verts,quads);
  cup_ui_text(ui,headline,.062f,.503f,.522f,.0375f,-1,verts,quads);
  ml_ui_text(ui,detail,.062f,.563f,.522f,.025f,2,-1,0,1,verts,quads);
  const float progress=competition_frontend_league_news_progress();
  if(progress>0)ml_ui_rect(ui,.062f,.610f,.522f*progress,.003f,.07f,.77f,.90f,1,-1,0,1,verts,quads);
  const uint32_t first=*quads;ml_ui_pills(ui,story,.640f,verts,quads);
  for(int q=(int)first;q<*quads;q++)for(int v=0;v<6;v++)verts[q*24+v*4]-=.35f;
}
static void league_ui_next(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const LeagueTournament *l=competition_frontend_league_tournament();
  const uint32_t champion=league_ui_champion();uint32_t home=0,away=0;
  const int next=league_ui_next_teams(&home,&away);
  ml_ui_panel(ui,champion ? "CHAMPIONS" : "NEXT MATCH",champion ? ML_HEADER_TROPHY : ML_HEADER_MATCH,
      .635f,.190f,.325f,.480f,competition_frontend_focus()==2u,verts,quads);
  if(champion) {
    league_ui_art(ui,3,.649f,.285f,.297f,.293f,verts,quads);
    cup_ui_badge(ui,champion,.664f,.317f,.185f,verts,quads);
    ml_ui_center_text(ui,cup_ui_team(champion),.65f,.601f,.295f,.044f,.031f,0,-2,verts,quads);
  } else if(next) {
    char label[64];snprintf(label,sizeof(label),"MATCHDAY %u / %u",l->active_matchday+1u,l->matchday_count);
    if(l->phase==LEAGUE_PHASE_KNOCKOUT) {
      uint32_t round=0,index=0;league_tournament_next_human(l,NULL,&round,&index);
      const CupFixture *f=cup_tournament_fixture(&l->knockout,round,index);
      snprintf(label,sizeof(label),"%s%s",league_ui_round(round),l->knockout.home_away && round+1u<l->knockout.round_count
          ? f && f->first_leg_complete ? " / LEG 2" : " / LEG 1" : "");
    }
    cup_ui_text(ui,label,.653f,.292f,.288f,.024f,-3,verts,quads);
    for(uint32_t side=0;side<2u;side++) {
      const float y=.338f+side*.156f;const uint32_t team=side ? away : home;
      ml_ui_rect(ui,.650f,y,.295f,.143f,.93f,.96f,.99f,1,-1,0,1,verts,quads);
      cup_ui_badge(ui,team,.660f,y+.019f,.105f,verts,quads);
      cup_ui_text(ui,cup_ui_team(team),.730f,y+.026f,.202f,.030f,-2,verts,quads);
      cup_ui_player_badge(ui,league_ui_owner(team),.730f,y+.085f,.059f,.037f,verts,quads);
    }
  } else {
    const int ready=competition_draft_ready(competition_frontend_league_draft());
    league_ui_art(ui,1,.649f,.285f,.297f,.234f,verts,quads);
    cup_ui_text(ui,ready ? "ADVANCE THE SEASON" : "BUILD THE LINE-UP",.653f,.554f,.287f,.030f,-2,verts,quads);
    cup_ui_text(ui,ready ? "RESOLVE REMAINING FIXTURES" : "ASSIGN YOUR PARTICIPANTS",.653f,.616f,.287f,.024f,-3,verts,quads);
  }
}
static void league_ui_home(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  league_ui_news(ui,verts,quads);league_ui_next(ui,verts,quads);
  static const uint32_t ids[]={0u,4u,1u,3u};
  static const uint32_t icons[]={ML_HEADER_SQUAD,ML_HEADER_RANKING,ML_HEADER_SETTINGS,ML_HEADER_SAVE};
  static const char *titles[]={"TEAMS","STANDINGS","SETTINGS","SAVE LEAGUE"};
  const CompetitionEntryDraft *d=competition_frontend_league_draft();
  const LeagueTournament *l=competition_frontend_league_tournament();
  char assigned[48];snprintf(assigned,sizeof(assigned),"%u / %u ASSIGNED",competition_draft_assigned_count(d),d->team_count);
  const char *details[]={l->first_match_started ? "PARTICIPANTS" : assigned,l->knockout.round_count ? "TABLE & KNOCKOUT" : "THE TITLE RACE","MATCH RULES","3 SAVE SLOTS"};
  for(uint32_t i=0;i<4u;i++) {
    const float x=.04f+i*.2375f;
    ml_ui_panel(ui,titles[i],icons[i],x,.695f,.2075f,.205f,competition_frontend_focus()==ids[i],verts,quads);
    competition_ui_pattern(ui,i,x,.770f,.2075f,.130f,verts,quads);
    cup_ui_text(ui,details[i],x+.015f,.825f,.181f,.022f,-3,verts,quads);
  }
}
static void league_ui_teams(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const CompetitionEntryDraft *d=competition_frontend_league_draft();
  const uint32_t focus=competition_frontend_league_team_slot_focus(),start=focus/8u*8u;
  char title[80];snprintf(title,sizeof(title),"PARTICIPANTS    /    %u OF %u",start/8u+1u,(d->team_count+7u)/8u);
  ml_ui_panel(ui,title,ML_HEADER_SQUAD,.04f,.190f,.92f,.710f,0,verts,quads);
  const uint32_t rows=d->team_count-start<4u ? d->team_count-start : 4u;
  const float step=.556f/(rows ? rows : 1u),rh=step-.019f,bh=fminf(.128f,rh-.036f);
  for(uint32_t i=start;i<d->team_count && i<start+8u;i++) {
    const float x=.06f+(i-start)/4u*.452f,y=.298f+(i-start)%4u*step,name_x=.026f+bh*screen_height/screen_width;
    ml_ui_frame(ui,x,y,.425f,rh,focus==i,verts,quads);
    ml_ui_rect(ui,x,y,.425f,rh,.93f,.96f,.99f,1,-1,0,1,verts,quads);
    cup_ui_badge(ui,d->teams[i],x+.012f,y+(rh-bh)*.5f,bh,verts,quads);
    cup_ui_text(ui,d->teams[i] ? cup_ui_team(d->teams[i]) : "SELECT TEAM",x+name_x,y+(rh-.030f)*.5f,.343f-name_x,.030f,-2,verts,quads);
    cup_ui_player_badge(ui,d->owners[i],x+.350f,y+(rh-.038f)*.5f,.060f,.038f,verts,quads);
  }
  if(d->team_count-start<=4u)league_ui_art(ui,0,.512f,.298f,.425f,.537f,verts,quads);
  snprintf(title,sizeof(title),"%u / %u TEAMS ASSIGNED%s",competition_draft_assigned_count(d),d->team_count,
      competition_frontend_league_teams_editing() ? "" : "    /    LINE-UP LOCKED");
  cup_ui_text(ui,title,.061f,.861f,.87f,.025f,-3,verts,quads);
}
static void league_ui_table(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const LeagueTournament *l=competition_frontend_league_tournament();
  const CompetitionEntryDraft *d=competition_frontend_league_draft();
  const uint32_t page=competition_frontend_league_table_page(),start=page*ML_TABLE_PAGE_ROWS;
  char label[80];snprintf(label,sizeof(label),"STANDINGS    /    PAGE %u OF %u",page+1u,(d->team_count+ML_TABLE_PAGE_ROWS-1u)/ML_TABLE_PAGE_ROWS);
  ml_ui_panel(ui,label,ML_HEADER_RANKING,.04f,.190f,.92f,.710f,0,verts,quads);
  static const char *cols[]={"P","W","D","L","GF","GA","GD","PTS"};
  static const float cx[]={.468f,.522f,.576f,.630f,.684f,.738f,.792f,.866f};
  cup_ui_text(ui,"POS",.068f,.306f,.041f,.025f,-3,verts,quads);
  cup_ui_text(ui,"CLUB",.170f,.306f,.21f,.025f,-3,verts,quads);
  for(uint32_t c=0;c<8u;c++)ml_ui_center_text(ui,cols[c],cx[c],.303f,.055f,.032f,.025f,0,-3,verts,quads);
  uint8_t slots[LEAGUE_MAX_TEAMS]={0};if(l->team_count)league_tournament_ranked_slots(l,slots);
  int8_t changes[LEAGUE_MAX_TEAMS];league_tournament_rank_changes(l,changes);
  const uint32_t champion=league_ui_champion();
  const uint32_t qualifiers=competition_frontend_league_system()==LEAGUE_SYSTEM_KNOCKOUT ? league_tournament_qualifier_count(d->team_count) : 0u;
  const float step=.080f,rh=.075f,bh=.069f;
  for(uint32_t rank=start;rank<d->team_count && rank<start+ML_TABLE_PAGE_ROWS;rank++) {
    const LeagueStanding empty={0},*r=l->team_count ? &l->standings[slots[rank]] : &empty;
    const uint32_t team=l->team_count ? r->team : d->teams[rank];const float y=.355f+(rank-start)*step;
    const uint32_t owner=team ? league_ui_owner(team) : 0u;
    const int won=team && team==champion;
    ml_ui_rect(ui,.059f,y,.882f,rh,won ? .98f : owner ? .83f : rank%2u ? 1.f : .94f,
        won ? .96f : owner ? .94f : rank%2u ? 1.f : .97f,won ? .78f : 1.f,1,-1,0,1,verts,quads);
    if(rank<qualifiers)ml_ui_rect(ui,.059f,y,.004f,rh,.02f,.49f,.40f,1,-1,0,1,verts,quads);
    snprintf(label,sizeof(label),"%02u",rank+1u);ml_ui_center_text(ui,label,.065f,y,.030f,rh,.0306f,0,-2,verts,quads);
    ml_ui_rank_change(ui,l->team_count ? changes[slots[rank]] : 0,.098f,y+rh*.5f,0,verts,quads);
    cup_ui_badge(ui,team,.119f,y+(rh-bh)*.5f,bh,verts,quads);
    cup_ui_text(ui,team ? cup_ui_team(team) : "UNASSIGNED",.170f,y+(rh-.0333f)*.5f,.231f,.0333f,-2,verts,quads);
    if(owner)cup_ui_player_badge(ui,owner,.409f,y+(rh-.034f)*.5f,.046f,.034f,verts,quads);
    const int values[]={r->played,r->wins,r->draws,r->losses,r->goals_for,r->goals_against,(int)r->goals_for-(int)r->goals_against,r->points};
    for(uint32_t c=0;c<8u;c++) {
      snprintf(label,sizeof(label),c==6u ? "%+d" : "%d",values[c]);
      ml_ui_center_text(ui,label,cx[c],y,.055f,rh,.0306f,c==7u ? 0 : 2,-2,verts,quads);
    }
  }
  if(qualifiers)snprintf(label,sizeof(label),"TOP %u QUALIFY FOR KNOCKOUT",qualifiers);
  else snprintf(label,sizeof(label),champion ? "FINAL LEAGUE TABLE" : "3 POINTS FOR A WIN   /   1 FOR A DRAW");
  cup_ui_text(ui,label,.062f,.861f,.75f,.025f,-3,verts,quads);
}
static void league_ui_fixture_card(MasterLeagueRender *ui,uint32_t number,const char *stage,const char *status,
    uint32_t home,uint32_t away,int scored,uint32_t hg,uint32_t ag,
    float x,float y,float w,float h,GLfloat *verts,int *quads) {
  ml_ui_rect(ui,x,y,w,h,.93f,.96f,.99f,1,-1,0,1,verts,quads);
  char label[24];snprintf(label,sizeof(label),"%02u",number);
  cup_ui_fixture_badge(ui,number-1u,label,x+.014f,y+.016f,.047f,.038f,verts,quads);
  const float status_w=measure_efootball_line_mode(status,(int)strlen(status),.023f*screen_height,EFOOTBALL_FONT_BOLD,0)/screen_width;
  cup_ui_text(ui,stage,x+.075f,y+.022f,w-.103f-status_w,.025f,-3,verts,quads);
  cup_ui_text(ui,status,x+w-.014f-status_w,y+.023f,status_w+.001f,.023f,-3,verts,quads);
  for(uint32_t side=0;side<2u;side++) {
    const float step=(h-.092f)*.5f,bh=fminf(.120f,step-.012f),yy=y+.070f+side*step+(step-bh)*.5f;
    const uint32_t team=side ? away : home;const float name_x=.026f+bh*screen_height/screen_width;
    cup_ui_badge(ui,team,x+.014f,yy,bh,verts,quads);
    cup_ui_text(ui,cup_ui_team(team),x+name_x,yy+(bh-.028f)*.5f,w-.115f-name_x,.028f,-2,verts,quads);
    if(team)cup_ui_player_badge(ui,league_ui_owner(team),x+w-.104f,yy+(bh-.034f)*.5f,.050f,.034f,verts,quads);
    snprintf(label,sizeof(label),scored ? "%u" : "-",side ? ag : hg);
    ml_ui_center_text(ui,label,x+w-.039f,yy+(bh-.038f)*.5f,.026f,.038f,.030f,0,-2,verts,quads);
  }
}
static void league_ui_matches(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const LeagueTournament *l=competition_frontend_league_tournament();
  const uint32_t day=competition_frontend_league_view_matchday(),page=competition_frontend_league_schedule_page();
  const uint32_t count=day<l->matchday_count ? l->matchday_fixture_count[day] : 0u;
  char label[80];snprintf(label,sizeof(label),"MATCH CENTRE    /    MATCHDAY %u",count ? day+1u : 1u);
  ml_ui_panel(ui,label,ML_HEADER_CALENDAR,.04f,.190f,.92f,.710f,0,verts,quads);
  snprintf(label,sizeof(label),"FIXTURES    /    PAGE %u OF %u",page+1u,count ? (count+3u)/4u : 1u);
  cup_ui_text(ui,label,.061f,.299f,.87f,.026f,-3,verts,quads);
  for(uint32_t i=0;i<4u && page*4u+i<count;i++) {
    const LeagueFixture *f=league_tournament_matchday_fixture(l,day,page*4u+i);
    snprintf(label,sizeof(label),"MATCHDAY %u",day+1u);
    league_ui_fixture_card(ui,page*4u+i+1u,label,f->complete ? "FULL TIME" : "UPCOMING",f->home,f->away,f->complete,f->home_goals,f->away_goals,
        .06f+(i/2u)*.452f,.352f+(i%2u)*.264f,.425f,count-page*4u==1u ? .509f : .245f,verts,quads);
  }
  if(count<=page*4u+2u) {
    league_ui_art(ui,1,.512f,.352f,.425f,.509f,verts,quads);
    if(!count) {
      cup_ui_text(ui,"THE FIXTURES START HERE",.073f,.444f,.405f,.036f,-2,verts,quads);
      ml_ui_text(ui,"Assign all teams in Participants.",.073f,.526f,.405f,.028f,2,-3,0,1,verts,quads);
    }
  }
}
static void league_ui_scorers(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const LeagueTournament *l=competition_frontend_league_tournament();uint16_t slots[4];
  const uint32_t count=league_tournament_top_scorers(l,slots);
  ml_ui_panel(ui,"TOP SCORERS",ML_HEADER_STATISTICS,.04f,.190f,.92f,.710f,0,verts,quads);
  cup_ui_text(ui,"THE GOLDEN BOOT RACE",.061f,.299f,.87f,.027f,-3,verts,quads);
  if(!count) {
    league_ui_art(ui,1,.06f,.352f,.425f,.525f,verts,quads);
    cup_ui_text(ui,"THE RACE IS ABOUT TO BEGIN",.525f,.474f,.402f,.034f,-2,verts,quads);
    ml_ui_text(ui,"Player goals appear after matches are played.",.525f,.555f,.402f,.026f,2,-3,0,1,verts,quads);
  }
  for(uint32_t i=0;i<count;i++) {
    const LeagueScorer *r=&l->scorers[slots[i]];const float x=.06f+(i/2u)*.452f,y=.352f+(i%2u)*.272f;
    ml_ui_rect(ui,x,y,.425f,.253f,.93f,.96f,.99f,1,-1,0,1,verts,quads);
    const GLuint portrait=gameplan_portrait_texture(r->portrait_id);
    if(portrait)ml_ui_image(ui,portrait,0,x+.014f,y+.040f,.0844f,.150f,verts,quads);
    else cup_ui_badge(ui,r->team,x+.014f,y+.047f,.142f,verts,quads);
    ui->view.rows[i].portrait=r->portrait_id;ui->view.count=i+1u;
    char label[32];snprintf(label,sizeof(label),"RANK %02u",i+1u);
    cup_ui_text(ui,label,x+.116f,y+.023f,.232f,.023f,-3,verts,quads);
    cup_ui_text(ui,r->name,x+.116f,y+.077f,.243f,.030f,-2,verts,quads);
    ml_ui_text(ui,cup_ui_team(r->team),x+.116f,y+.140f,.243f,.024f,2,-3,0,1,verts,quads);
    snprintf(label,sizeof(label),"%u",r->goals);ml_ui_center_text(ui,label,x+.363f,y+.067f,.049f,.086f,.048f,0,-2,verts,quads);
    cup_ui_text(ui,"GOALS",x+.363f,y+.175f,.050f,.022f,-3,verts,quads);
  }
}
static void league_ui_knockout_card(MasterLeagueRender *ui,uint32_t round,uint32_t index,
    float x,float y,float w,float h,GLfloat *verts,int *quads) {
  const CupTournament *cup=&competition_frontend_league_tournament()->knockout;
  const CupFixture *f=cup_tournament_fixture(cup,round,index);if(!f)return;
  uint32_t home=0,away=0;cup_tournament_schedule_teams(cup,round,index,&home,&away);
  const int two_leg=cup->home_away && round+1u<cup->round_count;
  const char *status=f->complete ? (two_leg ? "AGGREGATE" : "FULL TIME")
      : two_leg ? (f->first_leg_complete ? "LEG 1 DONE" : "LEG 1 NEXT") : "UPCOMING";
  league_ui_fixture_card(ui,index+1u,league_ui_round(round),status,home,away,f->complete || f->first_leg_complete,
      f->complete ? f->home_goals : f->first_leg_home_goals,f->complete ? f->away_goals : f->first_leg_away_goals,x,y,w,h,verts,quads);
}
static void league_ui_bracket(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const CupTournament *cup=&competition_frontend_league_tournament()->knockout;
  const uint32_t round=competition_frontend_league_bracket_round(),first=competition_frontend_league_bracket_page()*2u;
  const uint32_t count=cup_tournament_fixture_count(cup,round);char title[96];
  snprintf(title,sizeof(title),"KNOCKOUT    /    %s",league_ui_round(round));
  ml_ui_panel(ui,title,ML_HEADER_TROPHY,.04f,.190f,.92f,.710f,0,verts,quads);
  snprintf(title,sizeof(title),"ROUND %u / %u    -    PAGE %u / %u",round+1u,cup->round_count,first/2u+1u,(count+1u)/2u);
  cup_ui_text(ui,title,.061f,.299f,.87f,.025f,-3,verts,quads);
  if(round+1u==cup->round_count) {
    league_ui_knockout_card(ui,round,0,.06f,.352f,.425f,.290f,verts,quads);
    league_ui_art(ui,3,.512f,.352f,.425f,.525f,verts,quads);
    if(cup->champion)cup_ui_badge(ui,cup->champion,.555f,.393f,.220f,verts,quads);
    ml_ui_rect(ui,.512f,.711f,.425f,.166f,.012f,.07f,.18f,.95f,-1,0,1,verts,quads);
    cup_ui_text(ui,cup->champion ? "CHAMPIONS" : "THE TITLE AWAITS",.532f,.741f,.383f,.025f,-1,verts,quads);
    cup_ui_text(ui,cup->champion ? cup_ui_team(cup->champion) : "ONE FINAL. ONE WINNER.",.532f,.807f,.383f,.033f,-1,verts,quads);
    league_ui_art(ui,2,.060f,.663f,.425f,.214f,verts,quads);
    ml_ui_rect(ui,.060f,.663f,.425f,.214f,.012f,.07f,.18f,.50f,-1,0,1,verts,quads);
    cup_ui_text(ui,"THE FINAL CHAPTER",.080f,.701f,.385f,.033f,-1,verts,quads);
    cup_ui_text(ui,cup->champion ? "SEASON COMPLETE" : "ONE MATCH FOR THE TITLE",.080f,.814f,.385f,.025f,-1,verts,quads);
  } else {
    for(uint32_t i=0;i<2u && first+i<count;i++)league_ui_knockout_card(ui,round,first+i,.06f,.352f+i*.277f,.425f,.248f,verts,quads);
    const float edge=.485f,spine=.499f,mid=.476f;
    ml_ui_rect(ui,edge,mid,spine-edge,.003f,.16f,.51f,.48f,1,-1,0,1,verts,quads);
    ml_ui_rect(ui,edge,mid+.277f,spine-edge,.003f,.16f,.51f,.48f,1,-1,0,1,verts,quads);
    ml_ui_rect(ui,spine,mid,.002f,.280f,.16f,.51f,.48f,1,-1,0,1,verts,quads);
    league_ui_art(ui,2,.512f,.352f,.425f,.525f,verts,quads);
    cup_ui_text(ui,"WINNERS ADVANCE",.532f,.387f,.385f,.032f,-1,verts,quads);
    ml_ui_rect(ui,spine,mid+.1385f,.026f,.003f,.16f,.51f,.48f,1,-1,0,1,verts,quads);
    league_ui_knockout_card(ui,round+1u,first/2u,.525f,.4905f,.399f,.248f,verts,quads);
  }
}
static void league_news_emit(MasterLeagueRender *ui,CompetitionFrontendState state,GLfloat *verts,int *quads) {
  memset(ui,0,sizeof(*ui));
  const int hub=state==COMPETITION_FRONTEND_LEAGUE_HUB,general=hub && competition_frontend_cup_general_open();
  const LeagueFrontendPage page=competition_frontend_league_page();
  const int selected=hub || state==COMPETITION_FRONTEND_LEAGUE_SETTINGS || (state==COMPETITION_FRONTEND_LEAGUE_SLOTS && competition_frontend_league_slots_saving());
  const char *title=state==COMPETITION_FRONTEND_LEAGUE_LANDING ? "LEAGUE" : state==COMPETITION_FRONTEND_LEAGUE_SLOTS ? competition_frontend_league_slots_saving() ? "SAVE LEAGUE" : "CONTINUE LEAGUE"
      : state==COMPETITION_FRONTEND_LEAGUE_SETTINGS ? "LEAGUE SETTINGS" : general ? "GENERAL SETTINGS" : page==LEAGUE_PAGE_TABLE ? "LEAGUE STANDINGS" : page==LEAGUE_PAGE_MATCHES ? "MATCH CENTRE"
      : page==LEAGUE_PAGE_SCORERS ? "TOP SCORERS" : page==LEAGUE_PAGE_TEAMS ? "LEAGUE PARTICIPANTS" : page==LEAGUE_PAGE_BRACKET ? "LEAGUE KNOCKOUT" : "LEAGUE HUB";
  ml_ui_image(ui,gl.league_pearl_tex,0,0,0,1,1,verts,quads);
  league_ui_header(ui,verts,quads);
  ml_ui_header_icon(ui,ML_HEADER_RANKING,.049f,.053f,.085f,verts,quads);
  if(selected)league_ui_logo(ui,.847f,.043f,.103f,.108f,verts,quads);
  ml_ui_text(ui,title,.113f,.049f,.62f,.0472f,1,-1,0,1,verts,quads);
  ml_ui_text(ui,selected ? competition_frontend_league_name() : "ONE SEASON. EVERY CONTENDER.",.113f,.114f,.61f,.0278f,2,-1,0,1,verts,quads);
  if(state==COMPETITION_FRONTEND_LEAGUE_LANDING)league_ui_landing(ui,verts,quads);
  else if(state==COMPETITION_FRONTEND_LEAGUE_SETTINGS || general)league_ui_settings(ui,general,verts,quads);
  else if(state==COMPETITION_FRONTEND_LEAGUE_SLOTS)league_ui_slots(ui,verts,quads);
  else if(page==LEAGUE_PAGE_TEAMS)league_ui_teams(ui,verts,quads);
  else if(page==LEAGUE_PAGE_TABLE)league_ui_table(ui,verts,quads);
  else if(page==LEAGUE_PAGE_MATCHES)league_ui_matches(ui,verts,quads);
  else if(page==LEAGUE_PAGE_SCORERS)league_ui_scorers(ui,verts,quads);
  else if(page==LEAGUE_PAGE_BRACKET)league_ui_bracket(ui,verts,quads);
  else league_ui_home(ui,verts,quads);
  ml_ui_rect(ui,0,.925f,1,.075f,.025f,.10f,.28f,1,-1,0,1,verts,quads);ui->draws[ui->draw_count-1u].round.radius=0.f;
  if(hub && !general && page!=LEAGUE_PAGE_HOME) {
    if(page==LEAGUE_PAGE_TEAMS && competition_frontend_league_teams_editing())cup_ui_helper(ui,"A","SELECT TEAM",verts,quads);
    cup_ui_helper(ui,"B","LEAGUE HUB",verts,quads);
    if(page==LEAGUE_PAGE_TEAMS) {
      if(competition_frontend_league_teams_editing())cup_ui_helper(ui,"X","AUTO FILL",verts,quads);
      cup_ui_helper(ui,"Y","NEXT PAGE",verts,quads);
    } else if(page==LEAGUE_PAGE_SCORERS)cup_ui_helper(ui,"X","FIXTURES",verts,quads);
    else {
      cup_ui_helper(ui,"L",page==LEAGUE_PAGE_MATCHES ? "PREV DAY" : page==LEAGUE_PAGE_BRACKET ? "PREV ROUND" : "PREV PAGE",verts,quads);
      cup_ui_helper(ui,"R",page==LEAGUE_PAGE_MATCHES ? "NEXT DAY" : page==LEAGUE_PAGE_BRACKET ? "NEXT ROUND" : "NEXT PAGE",verts,quads);
      if(page!=LEAGUE_PAGE_TABLE)cup_ui_helper(ui,"Y","NEXT PAGE",verts,quads);
      else if(competition_frontend_league_tournament()->knockout.round_count)cup_ui_helper(ui,"Y","KNOCKOUT",verts,quads);
      if(page==LEAGUE_PAGE_MATCHES)cup_ui_helper(ui,"X","TOP SCORERS",verts,quads);
      if(page==LEAGUE_PAGE_BRACKET)cup_ui_helper(ui,"X","STANDINGS",verts,quads);
    }
  } else {
    const int next=hub && !general && competition_frontend_focus()==2u;
    uint32_t home=0,away=0;
    cup_ui_helper(ui,"A",next ? league_ui_champion() ? "SEASON RESULTS" : league_ui_next_teams(&home,&away) ? "PLAY MATCH" : "ADVANCE" : general || (state==COMPETITION_FRONTEND_LEAGUE_SETTINGS && competition_frontend_focus()!=5u) ? "CHANGE" : "SELECT",verts,quads);
    cup_ui_helper(ui,"B",general ? "LEAGUE HUB" : "BACK",verts,quads);
    if(hub && !general) {
      cup_ui_helper(ui,"L","PREV NEWS",verts,quads);cup_ui_helper(ui,"R","NEXT NEWS",verts,quads);
    }
  }
  cup_ui_toast(ui,0,verts,quads);
}
