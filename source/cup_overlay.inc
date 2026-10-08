/* Cup editorial UI. Uses the exact Master League card, button, typography,
 * icon and indicator primitives. All tournament access below is read-only. */
static void cup_ui_art(MasterLeagueRender *ui,uint32_t sprite,float x,float y,float w,float h,
    GLfloat *verts,int *quads) {
  MlDraw *d=ml_ui_draw(ui,*quads,2);if(!d)return;
  d->texture=gl.cup_news_tex;
  const float aspect=w*screen_width/(h*screen_height),source=16.f/9.f;
  const float uw=aspect<source ? .494f*aspect/source : .494f;
  const float vh=aspect>source ? .494f*source/aspect : .494f;
  const float u=(sprite%2u)*.5f+.003f+(.494f-uw)*.5f;
  const float v=(sprite/2u)*.5f+.003f+(.494f-vh)*.5f;
  d->uv[0]=u;d->uv[1]=v;d->uv[2]=uw;d->uv[3]=vh;
  d->round=(RoundedRectStyle){w*screen_width,h*screen_height,9.f};
  *quads+=emit_image_rect_uv(x*screen_width,y*screen_height,w*screen_width,h*screen_height,
      u,v,u+uw,v+vh,verts+*quads*24);
}
static void cup_ui_text(MasterLeagueRender *ui,const char *text,float x,float y,float w,float h,
    int ink,GLfloat *verts,int *quads) {
  ml_ui_text(ui,text,x,y,w,h,0,ink,0,1,verts,quads);
}
static void cup_ui_helper(MasterLeagueRender *ui,const char *key,const char *label,GLfloat *verts,int *quads) {
  MlView *v=&ui->view;const uint32_t i=v->helper_count;
  if(i>=4u)return;
  v->helper_key[i]=key;v->helper_label[i]=label;
  float x=.047f;
  if(i) x=ui->helper_centers[i-1]+.068f+measure_efootball_line_mode(v->helper_label[i-1],
      (int)strlen(v->helper_label[i-1]),22.f,EFOOTBALL_FONT_BOLD,0)/screen_width;
  ui->helper_centers[i]=x;v->helper_count++;
  cup_ui_text(ui,label,x+.021f,.9625f-11.f/screen_height,.35f,22.f/screen_height,-1,verts,quads);
}
static void cup_ui_badge(MasterLeagueRender *ui,uint32_t team,float x,float y,float h,GLfloat *verts,int *quads) {
  const uint32_t badge=team ? exhibition_team_catalog_badge(team) : 0u;
  if(badge)ml_ui_image(ui,gl.badge_tex,badge,x,y,h*screen_height/screen_width,h,verts,quads);
  else ml_ui_icon(ui,3,x,y,h,verts,quads);
}
static const char *cup_ui_team(uint32_t team) {
  return team ? exhibition_team_catalog_name(team) : "TO BE DECIDED";
}
/* Codes belong to opening-round positions, not teams. Resolve through the
 * draft map so cups with byes use the same fixture numbers as the bracket. */
static uint32_t cup_ui_slot_code(const CompetitionEntryDraft *draft,uint32_t slot,char *code,size_t size) {
  uint32_t fixture=0,side=0;
  if(!competition_draft_slot_fixture(draft,slot,&fixture,&side)) {
    snprintf(code,size,"--");return UINT32_MAX;
  }
  snprintf(code,size,"%02u%c",fixture+1u,side ? 'B' : 'A');return fixture;
}
static void cup_ui_fixture_badge(MasterLeagueRender *ui,uint32_t fixture,const char *label,
    float x,float y,float w,float h,GLfloat *verts,int *quads) {
  static const float colors[][3]={
    {.04f,.40f,.37f},{.43f,.28f,.61f},{.61f,.32f,.12f},{.57f,.24f,.40f},
    {.24f,.34f,.57f},{.37f,.42f,.14f},{.42f,.29f,.23f},{.29f,.36f,.39f}};
  const float *color=colors[fixture%8u];
  ml_ui_rect(ui,x,y,w,h,color[0],color[1],color[2],1,-1,0,1,verts,quads);
  ml_ui_center_text(ui,label,x,y,w,h,.0208f,0,-1,verts,quads);
}
/* Use draft ownership for unassigned participants too: team ID zero is not
 * enough to distinguish P1/P2 from COM before the lineup is complete. */
static void cup_ui_player_badge(MasterLeagueRender *ui,uint32_t player,float x,float y,float w,float h,
    GLfloat *verts,int *quads) {
  char label[16];snprintf(label,sizeof(label),player ? "P%u" : "COM",player);
  ml_ui_rect(ui,x,y,w,h,.03f,player ? .42f : .27f,player ? .70f : .44f,1,-1,0,1,verts,quads);
  ml_ui_center_text(ui,label,x,y,w,h,.0208f,0,-1,verts,quads);
}
static void cup_ui_logo(MasterLeagueRender *ui,float x,float y,float w,float h,GLfloat *verts,int *quads) {
  const GLuint texture=current_cup_logo_texture();
  const uint32_t index=competition_frontend_cup_catalog_index();
  const float aspect=texture && index<FL26_CUP_CATALOG_COUNT
      ? (gl.cup_logo_aspect[index]>0.f ? gl.cup_logo_aspect[index] : 1.f) : 1120.f/424.f;
  /* Contain the complete emblem; different cup PNGs need not be square. */
  const float box_aspect=w*screen_width/(h*screen_height);
  const float iw=aspect<box_aspect ? h*screen_height*aspect/screen_width : w;
  const float ih=aspect>box_aspect ? w*screen_width/aspect/screen_height : h;
  ml_ui_image(ui,texture ? texture : gl.main_menu_brand_tex,0,x+(w-iw)*.5f,y+(h-ih)*.5f,iw,ih,verts,quads);
}
static void cup_ui_landing(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const uint32_t focus=competition_frontend_focus();
  cup_ui_art(ui,0,.04f,.190f,.522f,.690f,verts,quads);
  ml_ui_rect(ui,.04f,.626f,.522f,.254f,.015f,.09f,.27f,.94f,-1,0,1,verts,quads);
  cup_ui_text(ui,"THE ROAD TO THE TROPHY",.066f,.658f,.468f,.040f,-1,verts,quads);
  ml_ui_text(ui,"One tournament. Every player has a story.",.066f,.731f,.468f,.028f,2,-1,0,1,verts,quads);
  cup_ui_text(ui,"1-8 PLAYERS  /  KNOCKOUT FOOTBALL",.066f,.817f,.468f,.0222f,-1,verts,quads);
  const char *titles[]={"NEW CUP","CONTINUE"};
  const char *details[]={"Choose a cup. Set the rules. Bring your rivals.","Pick up your tournament from a saved slot."};
  for(uint32_t i=0;i<2u;i++) {
    const float y=.190f+i*.360f;
    ml_ui_panel(ui,titles[i],i ? ML_HEADER_SAVE : ML_HEADER_TROPHY,.59f,y,.37f,.330f,focus==i,verts,quads);
    ml_ui_text(ui,details[i],.607f,y+.123f,.334f,.025f,2,-3,0,1,verts,quads);
    cup_ui_text(ui,i ? "3 SAVE SLOTS" : "LOCAL MULTIPLAYER",.608f,y+.183f,.331f,.0222f,-2,verts,quads);
    ml_ui_button(ui,.608f,y+.247f,.331f,.064f,focus==i,1,verts,quads);
    ml_ui_center_text(ui,i ? "LOAD CUP" : "CREATE CUP",.608f,y+.247f,.331f,.064f,.029f,0,-1,verts,quads);
  }
}
static void cup_ui_settings(MasterLeagueRender *ui,int general,GLfloat *verts,int *quads) {
  const uint32_t focus=general ? competition_frontend_cup_general_focus() : competition_frontend_focus();
  const uint32_t count=general ? competition_frontend_cup_general_count() : competition_frontend_cup_setting_count();
  const uint32_t start=general ? (focus/5u)*5u : 0u;
  char info[96];
  ml_ui_panel(ui,general ? "MATCH RULES" : "YOUR TOURNAMENT",ML_HEADER_TROPHY,.04f,.190f,.318f,.690f,0,verts,quads);
  ml_ui_art(ui,0,.051f,.287f,.296f,.280f,verts,quads);
  cup_ui_logo(ui,.065f,.300f,.268f,.254f,verts,quads);
  cup_ui_text(ui,competition_frontend_cup_name(),.061f,.603f,.276f,.0333f,-2,verts,quads);
  snprintf(info,sizeof(info),"%u TEAMS   /   %u PLAYERS",competition_frontend_cup_team_count(),competition_frontend_cup_player_count());
  cup_ui_text(ui,info,.061f,.661f,.276f,.025f,-3,verts,quads);
  cup_ui_text(ui,competition_frontend_cup_home_away() ? "HOME & AWAY LEGS" : "SINGLE MATCH KNOCKOUT",.061f,.718f,.276f,.025f,-2,verts,quads);
  ml_ui_text(ui,general ? "Changes apply to the next match." : "Choose your teams in the Cup Hub.",.061f,.817f,.276f,.024f,2,-3,0,1,verts,quads);
  ml_ui_panel(ui,general ? "GENERAL SETTINGS" : "CUP SETTINGS",ML_HEADER_SETTINGS,.383f,.190f,.577f,.690f,0,verts,quads);
  for(uint32_t i=start;i<count && i<start+5u;i++) {
    const uint32_t index=general ? i : competition_frontend_cup_setting_row(i);
    MlViewRow row={0};row.enabled=1;row.adjustable=1;
    static const char *labels[]={"CUP TYPE","PLAYERS","TEAMS","HOME & AWAY","THIRD PLACE MATCH"};
    snprintf(row.label,sizeof(row.label),"%s",general ? competition_frontend_cup_general_label(index) : labels[index]);
    snprintf(row.value,sizeof(row.value),"%s",general ? competition_frontend_cup_general_value(index) : competition_frontend_item_value(index));
    ml_ui_row(ui,&row,.400f,.298f+(i-start)*.093f,.543f,.078f,focus==index,0,verts,quads);
  }
  if(!general) {
    ml_ui_button(ui,.706f,.792f,.236f,.064f,focus==5u,1,verts,quads);
    ml_ui_center_text(ui,"CREATE CUP",.706f,.792f,.236f,.064f,.0278f,0,-1,verts,quads);
  } else {
    snprintf(info,sizeof(info),"%u / %u",start/5u+1u,(count+4u)/5u);
    cup_ui_text(ui,info,.879f,.820f,.06f,.025f,-3,verts,quads);
    cup_ui_text(ui,"UP / DOWN TO BROWSE",.403f,.823f,.40f,.0222f,-3,verts,quads);
  }
}
static void cup_ui_slots(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const int saving=competition_frontend_cup_slots_saving();
  cup_ui_art(ui,3,.04f,.190f,.318f,.690f,verts,quads);
  ml_ui_rect(ui,.04f,.626f,.318f,.254f,.015f,.09f,.27f,.94f,-1,0,1,verts,quads);
  cup_ui_text(ui,saving ? "KEEP THE STORY" : "BACK TO THE CUP",.061f,.665f,.275f,.0333f,-1,verts,quads);
  ml_ui_text(ui,saving ? "Save the draw and every result." : "Your participants. Your progress.",.061f,.731f,.275f,.025f,2,-1,0,1,verts,quads);
  for(uint32_t i=0;i<3u;i++) {
    const float y=.190f+i*.237f;char label[24];snprintf(label,sizeof(label),"SLOT %02u",i+1u);
    const char *name=competition_frontend_slot_competition(i);
    const int used=competition_frontend_cup_slot_valid(i);const int selected=competition_frontend_focus()==i;
    ml_ui_panel(ui,label,ML_HEADER_SAVE,.383f,y,.577f,.216f,selected,verts,quads);
    cup_ui_text(ui,used ? name : "EMPTY SLOT",.402f,y+.105f,.336f,.0306f,-2,verts,quads);
    ml_ui_text(ui,used ? competition_frontend_slot_progress(i) : saving ? "Ready for a new tournament" : "Create a new Cup to get started",.402f,y+.159f,.336f,.024f,2,-3,0,1,verts,quads);
    ml_ui_button(ui,.785f,y+.119f,.153f,.070f,selected,saving || used,verts,quads);
    ml_ui_center_text(ui,saving ? (used ? "OVERWRITE" : "SAVE") : "LOAD",.785f,y+.119f,.153f,.070f,.025f,0,-1,verts,quads);
  }
}
static void cup_ui_news(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const CupTournament *cup=competition_frontend_cup_tournament();
  const CompetitionEntryDraft *draft=competition_frontend_cup_draft();
  const uint32_t story=competition_frontend_cup_news_index();
  const uint32_t assigned=competition_draft_assigned_count(draft);
  char headline[112],detail[112],tag[64];
  snprintf(tag,sizeof(tag),"TOURNAMENT BRIEF");
  snprintf(headline,sizeof(headline),assigned==draft->team_count ? "THE STAGE IS SET" : "THE DRAW STARTS WITH YOU");
  snprintf(detail,sizeof(detail),"%u / %u teams assigned. %u players in the Cup.",assigned,draft->team_count,draft->player_count);
  if(story==1u) {
    uint32_t round=0,index=0;snprintf(tag,sizeof(tag),"MATCHDAY WATCH");
    if(competition_frontend_cup_next_fixture(&round,&index)) {
      const CupFixture *f=cup_tournament_fixture(cup,round,index);
      snprintf(headline,sizeof(headline),"%s",competition_frontend_cup_round_name(round));
      snprintf(detail,sizeof(detail),"%s vs %s",cup_ui_team(f->home),cup_ui_team(f->away));
    } else {
      snprintf(headline,sizeof(headline),cup->champion ? "THE FINAL WHISTLE" : "WAITING FOR THE LINE-UP");
      snprintf(detail,sizeof(detail),cup->champion ? "Every result is in Match Centre." : "Assign teams to reveal the opening fixtures.");
    }
  } else if(story==2u) {
    snprintf(tag,sizeof(tag),"RESULTS DESK");
    snprintf(headline,sizeof(headline),"EVERY MATCH WRITES HISTORY");
    snprintf(detail,sizeof(detail),"Results appear here after the matches are played.");
    if(cup->history_count) {
      const uint32_t last=cup->history_count-1u;
      const CupFixture *f=cup_tournament_fixture(cup,cup->history_round[last],cup->history_index[last]);
      if(f) {
        snprintf(headline,sizeof(headline),"%s  %u - %u  %s",cup_ui_team(f->home),f->home_goals,f->away_goals,cup_ui_team(f->away));
        snprintf(detail,sizeof(detail),"%s / %s",competition_frontend_cup_round_name(cup->history_round[last]),f->simulated ? "COM result" : "Full time");
      }
    }
  } else if(story==3u) {
    snprintf(tag,sizeof(tag),cup->champion ? "CUP CHAMPION" : "ROAD TO THE FINAL");
    snprintf(headline,sizeof(headline),"%s",cup->champion ? cup_ui_team(cup->champion) : "ONE TROPHY. EVERY CONTENDER.");
    snprintf(detail,sizeof(detail),cup->champion ? "The Cup is complete. Relive the journey in Match Centre." : "%u teams. Follow their path on the bracket page.",draft->team_count);
  }
  ml_ui_frame(ui,.04f,.190f,.57f,.445f,competition_frontend_focus()==5u,verts,quads);
  cup_ui_art(ui,story,.04f,.190f,.57f,.445f,verts,quads);
  ml_ui_rect(ui,.04f,.441f,.57f,.194f,.015f,.07f,.22f,.94f,-1,0,1,verts,quads);
  cup_ui_text(ui,"CUP NEWS",.061f,.216f,.40f,.0306f,-1,verts,quads);
  cup_ui_text(ui,tag,.061f,.462f,.523f,.021f,-1,verts,quads);
  cup_ui_text(ui,headline,.061f,.504f,.523f,.0375f,-1,verts,quads);
  ml_ui_text(ui,detail,.061f,.568f,.523f,.025f,2,-1,0,1,verts,quads);
  const float progress=competition_frontend_cup_news_progress();
  if(progress>0.f)ml_ui_rect(ui,.061f,.617f,.523f*progress,.003f,.07f,.77f,.90f,1,-1,0,1,verts,quads);
  /* Same pill geometry/palette as ML, centred below this carousel. */
  const uint32_t first=*quads;ml_ui_pills(ui,story,.658f,verts,quads);
  for(int q=(int)first;q<*quads;q++)for(int v=0;v<6;v++)verts[q*24+v*4]-=.35f;
}
static void cup_ui_next(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const CupTournament *cup=competition_frontend_cup_tournament();
  uint32_t round=0,index=0;const int available=competition_frontend_cup_next_fixture(&round,&index);
  const CupFixture *fixture=available ? cup_tournament_fixture(cup,round,index) : NULL;
  const int selected=competition_frontend_focus()==1u;
  ml_ui_panel(ui,cup->champion ? "CUP CHAMPION" : "NEXT MATCH",cup->champion ? ML_HEADER_TROPHY : ML_HEADER_MATCH,.635f,.190f,.325f,.445f,selected,verts,quads);
  if(fixture) {
    char stage[64];snprintf(stage,sizeof(stage),"%s%s",round+1u==cup->round_count && index==CUP_THIRD_PLACE_INDEX ? "THIRD PLACE" : competition_frontend_cup_round_name(round),
        cup->home_away && round+1u<cup->round_count ? (fixture->first_leg_complete ? " / LEG 2" : " / LEG 1") : "");
    cup_ui_text(ui,stage,.652f,.289f,.288f,.0222f,-3,verts,quads);
    for(uint32_t side=0;side<2u;side++) {
      const uint32_t team=side ? fixture->away : fixture->home;const float y=.333f+side*.147f;
      ml_ui_rect(ui,.650f,y,.295f,.134f,.93f,.96f,.99f,1,-1,0,1,verts,quads);
      cup_ui_badge(ui,team,.660f,y+.017f,.100f,verts,quads);
      cup_ui_text(ui,cup_ui_team(team),.729f,y+.022f,.199f,.029f,-2,verts,quads);
      cup_ui_player_badge(ui,competition_frontend_cup_player_slot(team),.729f,y+.077f,.055f,.035f,verts,quads);
    }
  } else if(cup->champion) {
    cup_ui_badge(ui,cup->champion,.7469f,.301f,.180f,verts,quads);
    ml_ui_center_text(ui,cup_ui_team(cup->champion),.650f,.507f,.295f,.048f,.032f,0,-2,verts,quads);
    ml_ui_center_text(ui,"TOURNAMENT COMPLETE",.650f,.582f,.295f,.027f,.0222f,0,-3,verts,quads);
  } else {
    cup_ui_text(ui,"BUILD THE LINE-UP",.653f,.353f,.29f,.031f,-2,verts,quads);
    ml_ui_text(ui,"Assign participants in Teams.",.653f,.429f,.29f,.025f,2,-3,0,1,verts,quads);
    ml_ui_text(ui,"Then the road to the final begins.",.653f,.478f,.29f,.025f,2,-3,0,1,verts,quads);
  }
}
static void cup_ui_home(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  cup_ui_news(ui,verts,quads);cup_ui_next(ui,verts,quads);
  static const uint32_t ids[]={0,4,2,3};
  static const uint32_t icons[]={ML_HEADER_SQUAD,ML_HEADER_TROPHY,ML_HEADER_SETTINGS,ML_HEADER_SAVE};
  static const char *titles[]={"TEAMS","BRACKET","SETTINGS","SAVE CUP"};
  const CompetitionEntryDraft *draft=competition_frontend_cup_draft();
  char assigned[48];snprintf(assigned,sizeof(assigned),"%u / %u ASSIGNED",competition_draft_assigned_count(draft),draft->team_count);
  const char *details[]={competition_frontend_cup_bracket_editable() ? assigned : "LINE-UP LOCKED","ROAD TO THE FINAL","MATCH RULES","3 SAVE SLOTS"};
  for(uint32_t i=0;i<4u;i++) {
    const float x=.04f+i*.2375f;
    ml_ui_panel(ui,titles[i],icons[i],x,.704f,.2075f,.176f,competition_frontend_focus()==ids[i],verts,quads);
    cup_ui_text(ui,details[i],x+.015f,.816f,.18f,.0222f,-3,verts,quads);
  }
}
/* A fixture occupies its own readable card. Future participants are display-only
 * schedule projections; byes and two-leg aggregates remain owned by the core. */
static void cup_ui_fixture(MasterLeagueRender *ui,uint32_t round,uint32_t index,
    float x,float y,float w,float h,GLfloat *verts,int *quads) {
  const CupTournament *cup=competition_frontend_cup_tournament();
  const CupFixture *f=cup_tournament_fixture(cup,round,index);if(!f)return;
  const int bye=f->complete && (!f->home || !f->away);
  const int two_leg=cup->home_away && round+1u<cup->round_count;
  uint32_t teams[2]={0};cup_tournament_schedule_teams(cup,round,index,&teams[0],&teams[1]);
  ml_ui_rect(ui,x,y,w,h,.93f,.96f,.99f,1,-1,0,1,verts,quads);
  const int third=round+1u==cup->round_count && index==CUP_THIRD_PLACE_INDEX;
  char code[16];snprintf(code,sizeof(code),"%02u",index+1u);
  if(third)snprintf(code,sizeof(code),"3RD");
  if(round==0u && !third) {
    cup_ui_fixture_badge(ui,index,code,x+.014f,y+.015f,.046f,.038f,verts,quads);
  } else {
    ml_ui_rect(ui,x+.014f,y+.015f,.046f,.038f,.03f,.27f,.44f,1,-1,0,1,verts,quads);
    ml_ui_center_text(ui,code,x+.014f,y+.015f,.046f,.038f,.0208f,0,-1,verts,quads);
  }
  cup_ui_text(ui,third ? "THIRD PLACE" : competition_frontend_cup_round_name(round),x+.073f,y+.022f,w-.087f,.0236f,-3,verts,quads);
  for(uint32_t side=0;side<2u;side++) {
    const float yy=y+.071f+side*.080f;
    cup_ui_badge(ui,teams[side],x+.014f,yy,.064f,verts,quads);
    const int empty_bye=round==0u && competition_draft_fixture_slot(competition_frontend_cup_draft(),index,side)==UINT32_MAX;
    cup_ui_text(ui,teams[side] ? cup_ui_team(teams[side]) : round==0u ? (empty_bye ? "BYE" : "UNASSIGNED") : "TO BE DECIDED",x+.064f,yy+.018f,w-.178f,.0278f,-2,verts,quads);
    char score[16];snprintf(score,sizeof(score),"%u",side ? f->away_goals : f->home_goals);
    if(!f->complete && f->first_leg_complete)snprintf(score,sizeof(score),"%u",side ? f->first_leg_away_goals : f->first_leg_home_goals);
    if(bye || (!f->complete && !f->first_leg_complete))snprintf(score,sizeof(score),"-");
    ml_ui_center_text(ui,score,x+w-.041f,yy+.015f,.030f,.034f,.0278f,0,-2,verts,quads);
    if(teams[side])cup_ui_player_badge(ui,competition_frontend_cup_player_slot(teams[side]),x+w-.104f,yy+.016f,.050f,.032f,verts,quads);
  }
  cup_ui_text(ui,bye ? "BYE / AUTOMATIC ADVANCE" : f->complete ? (two_leg ? "AGGREGATE / FULL TIME" : "FULL TIME") : f->first_leg_complete ? "FIRST LEG / RETURN TO PLAY" : "UPCOMING",x+.014f,y+h-.034f,w-.028f,.0208f,-3,verts,quads);
}
static void cup_ui_bracket(MasterLeagueRender *ui,int matches,GLfloat *verts,int *quads) {
  const CupTournament *cup=competition_frontend_cup_tournament();
  const uint32_t stage=competition_frontend_cup_view_round();
  const uint32_t round=stage<cup->round_count ? stage : 0u;
  const uint32_t first=competition_frontend_cup_view_first_fixture();
  const uint32_t count=cup_tournament_fixture_count(cup,round);
  char heading[80];snprintf(heading,sizeof(heading),"%s  /  %s",matches ? "MATCH CENTRE" : "BRACKET",competition_frontend_cup_round_name(round));
  ml_ui_panel(ui,heading,matches ? ML_HEADER_CALENDAR : ML_HEADER_TROPHY,.04f,.190f,.92f,.690f,0,verts,quads);
  const float left=.057f,top=.291f,card_w=.424f,card_h=.267f,row_step=.299f;
  const float right=.532f,right_w=.411f;
  if(round+1u==cup->round_count) {
    cup_ui_fixture(ui,round,0,left,top,card_w,card_h,verts,quads);
    if(cup->third_place_enabled)cup_ui_fixture(ui,round,CUP_THIRD_PLACE_INDEX,left,top+row_step,card_w,card_h,verts,quads);
    cup_ui_art(ui,3,right,top,right_w,row_step+card_h,verts,quads);
    if(cup->champion)cup_ui_badge(ui,cup->champion,right+.058f,top+.074f,.250f,verts,quads);
    ml_ui_rect(ui,right,.689f,right_w,.168f,.015f,.09f,.27f,.93f,-1,0,1,verts,quads);
    cup_ui_text(ui,cup->champion ? "CHAMPIONS" : "THE TROPHY AWAITS",.550f,.718f,.375f,.024f,-1,verts,quads);
    cup_ui_text(ui,cup->champion ? cup_ui_team(cup->champion) : "ONE FINAL. ONE WINNER.",.550f,.774f,.375f,.0333f,-1,verts,quads);
  } else {
    for(uint32_t i=0;i<2u && first+i<count;i++)
      cup_ui_fixture(ui,round,first+i,left,top+i*row_step,card_w,card_h,verts,quads);
    if(matches) {
      cup_ui_text(ui,"ROUND OVERVIEW",.55f,.369f,.36f,.036f,-2,verts,quads);
      char info[64];snprintf(info,sizeof(info),"%u FIXTURES IN THIS ROUND",count);
      cup_ui_text(ui,info,.55f,.441f,.36f,.0278f,-3,verts,quads);
      cup_ui_text(ui,"ALL PARTICIPANTS",.55f,.528f,.36f,.024f,-2,verts,quads);
      ml_ui_text(ui,"Player and COM matches share one Cup.",.55f,.577f,.36f,.025f,2,-3,0,1,verts,quads);
      ml_ui_text(ui,"Use L / R to browse every round.",.55f,.622f,.36f,.025f,2,-3,0,1,verts,quads);
      ml_ui_text(ui,"Results update after matches finish.",.55f,.667f,.36f,.025f,2,-3,0,1,verts,quads);
    } else {
      const float edge=left+card_w,spine=.506f,mid_y=top+card_h*.5f;
      ml_ui_rect(ui,edge,mid_y,spine-edge,.003f,.2f,.48f,.67f,1,-1,0,1,verts,quads);
      ml_ui_rect(ui,edge,mid_y+row_step,spine-edge,.003f,.2f,.48f,.67f,1,-1,0,1,verts,quads);
      ml_ui_rect(ui,spine,mid_y,.002f,row_step+.003f,.2f,.48f,.67f,1,-1,0,1,verts,quads);
      ml_ui_rect(ui,spine,mid_y+row_step*.5f,right-spine,.003f,.2f,.48f,.67f,1,-1,0,1,verts,quads);
      cup_ui_fixture(ui,round+1u,first/2u,right,top+row_step*.5f,right_w,card_h,verts,quads);
      cup_ui_text(ui,"WINNERS ADVANCE",right+.014f,.743f,right_w-.028f,.0222f,-3,verts,quads);
      /* Semis, final and third-place remain inspectable on the Final page. */
    }
  }
  snprintf(heading,sizeof(heading),"ROUND %u / %u    -    PAGE %u / %u",round+1u,cup->round_count,
      competition_frontend_cup_view_page_index()+1u,competition_frontend_cup_view_page_count());
  cup_ui_text(ui,heading,.057f,.895f,.886f,.021f,-3,verts,quads);
}
static void cup_ui_teams(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  const CompetitionEntryDraft *draft=competition_frontend_cup_draft();
  const uint32_t focus=competition_frontend_cup_bracket_slot_focus(),start=focus/8u*8u;
  ml_ui_panel(ui,"PARTICIPANTS",ML_HEADER_SQUAD,.04f,.190f,.92f,.690f,0,verts,quads);
  for(uint32_t i=start;i<draft->team_count && i<start+8u;i++) {
    const float x=.06f+((i-start)/4u)*.452f,y=.292f+((i-start)%4u)*.144f;
    ml_ui_frame(ui,x,y,.425f,.122f,focus==i,verts,quads);
    const int moving=i==competition_frontend_cup_bracket_swap_source();
    ml_ui_rect(ui,x,y,.425f,.122f,moving ? .81f : .93f,moving ? .93f : .96f,.99f,1,-1,0,1,verts,quads);
    cup_ui_badge(ui,draft->teams[i],x+.010f,y+.021f,.080f,verts,quads);
    cup_ui_text(ui,draft->teams[i] ? cup_ui_team(draft->teams[i]) : "SELECT TEAM",x+.068f,y+.0465f,.205f,.029f,-2,verts,quads);
    char code[16];const uint32_t fixture=cup_ui_slot_code(draft,i,code,sizeof(code));
    cup_ui_fixture_badge(ui,fixture,code,x+.286f,y+.042f,.052f,.038f,verts,quads);
    cup_ui_player_badge(ui,draft->owners[i],x+.350f,y+.042f,.060f,.038f,verts,quads);
  }
  char info[80];snprintf(info,sizeof(info),"PAGE %u / %u   -   %u / %u TEAMS ASSIGNED",start/8u+1u,(draft->team_count+7u)/8u,competition_draft_assigned_count(draft),draft->team_count);
  cup_ui_text(ui,info,.061f,.895f,.87f,.021f,-3,verts,quads);
}
static void cup_ui_toast(MasterLeagueRender *ui,int moving,GLfloat *verts,int *quads) {
  static uint32_t serial;static uint64_t began;static char previous[96];
  const char *status=competition_frontend_status();
  const uint32_t current=competition_frontend_status_serial();
  if(serial!=current || strcmp(previous,status)) {
    serial=current;began=armGetSystemTick();snprintf(previous,sizeof(previous),"%s",status);
  }
  /* Assignment counts already live in the Teams card and participant footer. */
  if(!status[0] || !strncmp(status,"ASSIGN TEAMS  ",14) || competition_frontend_cup_opening_rule_popup())return;
  char move_status[64];
  const int move_hint=moving && !strcmp(status,"CHOOSE TARGET SLOT AND PRESS A");
  if(move_hint) {
    char from[16],to[16];
    cup_ui_slot_code(competition_frontend_cup_draft(),competition_frontend_cup_bracket_swap_source(),from,sizeof(from));
    cup_ui_slot_code(competition_frontend_cup_draft(),competition_frontend_cup_bracket_slot_focus(),to,sizeof(to));
    snprintf(move_status,sizeof(move_status),"MOVE %s  TO  %s",from,to);status=move_status;
  }
  const float ms=(float)armTicksToNs(armGetSystemTick()-began)/1000000.f;
  if(!move_hint && ms>=3000.f)return;
  const float enter=fminf(1.f,ms/180.f),leave=move_hint ? 0.f : fmaxf(0.f,(ms-2750.f)/250.f);
  ml_ui_toast_card(ui,status,(1.f-enter)*(1.f-enter)+leave*leave,verts,quads);
}
static void cup_news_emit(MasterLeagueRender *ui,CompetitionFrontendState state,GLfloat *verts,int *quads) {
  memset(ui,0,sizeof(*ui));
  const int hub=state==COMPETITION_FRONTEND_CUP_BRACKET;
  const int general=hub && competition_frontend_cup_general_open();
  const CupFrontendPage page=competition_frontend_cup_page();
  const int moving=hub && !general && page==CUP_PAGE_TEAMS &&
      competition_frontend_cup_bracket_swap_source()!=UINT32_MAX;
  const int selected_cup=hub || state==COMPETITION_FRONTEND_CUP_SETTINGS ||
      (state==COMPETITION_FRONTEND_CUP_SLOTS && competition_frontend_cup_slots_saving());
  const char *title=state==COMPETITION_FRONTEND_CUP_LANDING ? "CUP" : state==COMPETITION_FRONTEND_CUP_SLOTS ? (competition_frontend_cup_slots_saving() ? "SAVE CUP" : "CONTINUE CUP") : state==COMPETITION_FRONTEND_CUP_SETTINGS ? "CUP SETTINGS" : general ? "GENERAL SETTINGS" : page==CUP_PAGE_TEAMS ? "CUP PARTICIPANTS" : page==CUP_PAGE_BRACKET ? "CUP BRACKET" : page==CUP_PAGE_MATCHES ? "MATCH CENTRE" : "CUP HUB";
  ml_ui_image(ui,gl.cup_pearl_tex,0,0,0,1,1,verts,quads);
  ml_ui_rect(ui,0,0,1,1,1,1,1,.22f,-1,0,1,verts,quads);
  ml_ui_art(ui,0,.03f,.03f,.94f,.133f,verts,quads);
  ml_ui_header_icon(ui,ML_HEADER_TROPHY,.049f,.053f,.085f,verts,quads);
  if(selected_cup)cup_ui_logo(ui,.854f,.043f,.096f,.108f,verts,quads);
  ml_ui_text(ui,title,.113f,.049f,.56f,.0472f,1,-1,0,1,verts,quads);
  ml_ui_text(ui,selected_cup ? competition_frontend_cup_name() : "ONE CUP. EVERY PLAYER.",.113f,.114f,.59f,.0278f,2,-1,0,1,verts,quads);
  if(state==COMPETITION_FRONTEND_CUP_LANDING)cup_ui_landing(ui,verts,quads);
  else if(state==COMPETITION_FRONTEND_CUP_SETTINGS || general)cup_ui_settings(ui,general,verts,quads);
  else if(state==COMPETITION_FRONTEND_CUP_SLOTS)cup_ui_slots(ui,verts,quads);
  else if(page==CUP_PAGE_TEAMS)cup_ui_teams(ui,verts,quads);
  else if(page==CUP_PAGE_BRACKET || page==CUP_PAGE_MATCHES)cup_ui_bracket(ui,page==CUP_PAGE_MATCHES,verts,quads);
  else cup_ui_home(ui,verts,quads);
  ml_ui_rect(ui,0,.925f,1,.075f,.025f,.10f,.28f,1,-1,0,1,verts,quads);
  ui->draws[ui->draw_count-1u].round.radius=0.f;
  if(hub && !general && (page==CUP_PAGE_BRACKET || page==CUP_PAGE_MATCHES)) {
    cup_ui_helper(ui,"B","CUP HUB",verts,quads);cup_ui_helper(ui,"L","PREV ROUND",verts,quads);
    cup_ui_helper(ui,"R","NEXT ROUND",verts,quads);cup_ui_helper(ui,"Y","NEXT PAGE",verts,quads);
  } else {
    const int next_match=hub && !general && page==CUP_PAGE_HOME && competition_frontend_focus()==1u && competition_frontend_item_enabled(1u);
    cup_ui_helper(ui,"A",moving ? "SWAP" : next_match ? (competition_frontend_cup_tournament()->champion ? "TOP MENU" : "PLAY MATCH") : general || (state==COMPETITION_FRONTEND_CUP_SETTINGS && competition_frontend_focus()!=5u) ? "CHANGE" : "SELECT",verts,quads);
    cup_ui_helper(ui,"B",moving ? "CANCEL MOVE" : hub && (general || page==CUP_PAGE_TEAMS) ? "CUP HUB" : "BACK",verts,quads);
    if(hub && !general && page==CUP_PAGE_TEAMS) {
      cup_ui_helper(ui,"X","AUTO FILL",verts,quads);cup_ui_helper(ui,"Y","MOVE SLOT",verts,quads);
    } else if(hub && !general) {
      cup_ui_helper(ui,"L","PREV NEWS",verts,quads);cup_ui_helper(ui,"R","NEXT NEWS",verts,quads);
    }
  }
  cup_ui_toast(ui,moving,verts,quads);
  if(competition_frontend_cup_opening_rule_popup()) {
    const uint32_t first=ui->draw_count;
    ml_ui_rect(ui,0,0,1,1,.0f,.025f,.08f,.74f,-1,0,1,verts,quads);
    ml_ui_panel(ui,"OPENING ROUND",ML_HEADER_MATCH,.21f,.30f,.58f,.35f,0,verts,quads);
    cup_ui_text(ui,"At least one player must play in the first round.",.238f,.415f,.524f,.028f,-2,verts,quads);
    cup_ui_text(ui,"Move a player into an opening fixture to continue.",.238f,.467f,.524f,.025f,-3,verts,quads);
    ml_ui_button(ui,.411f,.548f,.178f,.065f,1,1,verts,quads);
    ml_ui_center_text(ui,"OK",.411f,.548f,.178f,.065f,.0306f,0,-1,verts,quads);
    for(uint32_t i=first;i<ui->draw_count;i++)ui->draws[i].layer=1;
  }
}
