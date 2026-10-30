#include "gameplan_layout.h"
/* Exact shared FootballNX presentation primitives; no extra GL program/assets. */
#include "manager_league_client.h"
#include "manager_league_hub.h"
#include <time.h>
static void md_ui_right_text(MasterLeagueRender *ui,const char *text,float right,float cy,
    float height,GLfloat *verts,int *quads) {
  float width=fminf(.22f,measure_efootball_line_mode(text,(int)strlen(text),height*screen_height,EFOOTBALL_FONT_BOLD,0)/screen_width);
  fd_text(ui,text,right-width,fd_cap_top(cy,height),width+.001f,height,-1,verts,quads);
}
static void md_ui_chrome(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  ml_ui_image(ui,gl.master_league_pearl_tex,0,0,0,1,1,verts,quads);
  ml_ui_art(ui,0,.03f,.03f,.94f,.133f,verts,quads);
  const float tx=v->badge ? .119f : .057f;
  if(v->badge)ml_ui_image(ui,gl.badge_tex,v->badge,.050f,.052f,.051f,.091f,verts,quads);
  ml_ui_text(ui,v->online_test?"ONLINEDEV - TEST":"MANAGER LEAGUE",tx,.049f,.57f,.0472f,1,-1,0,1,verts,quads);
  ml_ui_text(ui,v->caption[0] ? v->caption : v->subtitle,tx,.114f,.61f,.0278f,2,-1,0,1,verts,quads);
  if(!v->online || v->online_cash_available){
    md_ui_right_text(ui,"NX CASH",.950f,.066f,.0222f,verts,quads);
    char cash[24];snprintf(cash,sizeof(cash),"%llu",(unsigned long long)(v->online?v->online_cash:v->balance));
    md_ui_right_text(ui,cash,.950f,.115f,.0389f,verts,quads);
  }
}
static void md_ui_circle(MasterLeagueRender *ui,float x,float y,float h,
    float r,float g,float b,GLfloat *verts,int *quads) {
  const float w=h*screen_height/screen_width;
  fd_rect(ui,x-w*.5f,y-h*.5f,w,h,r,g,b,verts,quads);
  if(ui->draw_count)ui->draws[ui->draw_count-1].round.radius=h*screen_height*.5f;
}
static void md_ui_pitch(MasterLeagueRender *ui,const MdView *v,float x,float y,
    float w,float h,int moving,GLfloat *verts,int *quads) {
  fd_rect(ui,x,y,w,h,.055f,.23f,.15f,verts,quads);
  for(uint32_t i=0;i<10;i+=2)fd_rect(ui,x+w*i/10,y,w/10,h,.065f,.25f,.17f,verts,quads);
  const float tx=.0015f,ty=.0026f;
  fd_rect(ui,x+.008f,y+.014f,w-.016f,ty,.72f,.83f,.75f,verts,quads);
  fd_rect(ui,x+.008f,y+h-.017f,w-.016f,ty,.72f,.83f,.75f,verts,quads);
  fd_rect(ui,x+.008f,y+.014f,tx,h-.028f,.72f,.83f,.75f,verts,quads);
  fd_rect(ui,x+w-.010f,y+.014f,tx,h-.028f,.72f,.83f,.75f,verts,quads);
  fd_rect(ui,x+w*.5f,y+.014f,tx,h-.028f,.72f,.83f,.75f,verts,quads);
  md_ui_circle(ui,x+w*.5f,y+h*.5f,h*.21f,.72f,.83f,.75f,verts,quads);
  md_ui_circle(ui,x+w*.5f,y+h*.5f,h*.20f,.055f,.23f,.15f,verts,quads);
  md_ui_circle(ui,x+w*.5f,y+h*.5f,.006f,.85f,.90f,.86f,verts,quads);
  for(uint32_t side=0;side<2;side++) {
    float bx=side ? x+w-.008f-w*.15f : x+.008f;
    fd_rect(ui,bx,y+h*.24f,w*.15f,ty,.72f,.83f,.75f,verts,quads);
    fd_rect(ui,bx,y+h*.76f,w*.15f,ty,.72f,.83f,.75f,verts,quads);
    fd_rect(ui,side ? bx : bx+w*.15f,y+h*.24f,tx,h*.52f,.72f,.83f,.75f,verts,quads);
  }
  for(uint32_t i=0;i<(moving ? 23u : 11u);i++) {
    const uint32_t side=moving ? v->dots[i].side : 0;
    const float px=moving ? v->dots[i].x : i==0 ? .08f : i<5 ? .28f : i<8 ? .50f : .75f;
    const float py=moving ? v->dots[i].y : i==0 ? .5f : i<5 ? .17f+(i-1)*.22f : i<8 ? .23f+(i-5)*.27f : .23f+(i-8)*.27f;
    const float cx=x+.018f+px*(w-.036f),cy=y+.025f+py*(h-.05f),size=moving ? .025f : .033f;
    if(moving && i==22) {
      float pulse=.033f+.009f*sinf(v->elapsed_ms*.009f);
      md_ui_circle(ui,cx,cy,pulse,.47f,.65f,.45f,verts,quads);
    }
    md_ui_circle(ui,cx,cy,size+.005f,.98f,.99f,1,verts,quads);
    md_ui_circle(ui,cx,cy,size,side==0 ? .04f : side==1 ? .91f : .99f,
        side==0 ? .33f : side==1 ? .14f : .95f,side==0 ? .87f : side==1 ? .21f : .40f,verts,quads);
    if(side<2) {char number[8];snprintf(number,sizeof(number),"%u",moving ? v->dots[i].number : i+1);
      fd_center_text(ui,number,cx-.016f,cy,.032f,moving ? .018f : .022f,-1,verts,quads);}
  }
  if(moving && v->event_age_ms<2400 && v->event_kind!=MD_PASS) {
    static const char *const labels[]={"","SHOT WIDE","GOAL!","FOUL","YELLOW CARD","SUBSTITUTION","OFFSIDE","CORNER","GREAT SAVE","HALF TIME"};
    const int goal=v->event_kind==MD_GOAL,card=v->event_kind==MD_YELLOW;
    float pop=sinf(fminf(v->event_age_ms/260.f,1.f)*1.5707963f);
    float bw=w*(.62f+.025f*pop),bx=x+(w-bw)*.5f,by=y+h*.13f;
    fd_card(ui,bx,by,bw,.117f,1,0,verts,quads);
    fd_rect(ui,bx+.007f,by+.014f,.004f,.088f,card ? 1.f : goal ? .97f : .12f,card ? .85f : .14f,card ? .05f : .32f,verts,quads);
    fd_center_text(ui,labels[v->event_kind],bx+.014f,by+.034f,bw-.028f,goal ? .042f : .030f,-1,verts,quads);
    char detail[80];
    if(v->event_kind==MD_SUB)snprintf(detail,sizeof(detail),"#%u OFF   >   #%u ON",v->event_player,v->event_other);
    else if(v->event_kind==MD_HALF)snprintf(detail,sizeof(detail),"45 MINUTES - %s",v->score);
    else snprintf(detail,sizeof(detail),"%.34s - #%u",v->event_side ? v->away : v->home,v->event_player);
    fd_center_text(ui,detail,bx+.014f,by+.083f,bw-.028f,.023f,-1,verts,quads);
  }
}
/* Online cards use only published API data. Do not populate the legacy
 * local league table, feed or opponent previews with synthetic values. */
static void md_ui_online_hub(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  static const char *const tabs[]={"HOME","MY TEAM","LEAGUE"};
  md_ui_chrome(ui,v,verts,quads);
  for(uint32_t i=0;i<3;i++) {
    const float x=.10f+i*.275f;fd_card(ui,x,.199f,.25f,.048f,v->tab==i,0,verts,quads);
    fd_text(ui,tabs[i],x+.018f,.211f,.224f,.025f,v->tab==i ? -1 : -2,verts,quads);
  }
  for(uint32_t i=0;i<(v->tab?4u:5u);i++) {
    const MdRow *r=&v->rows[i];const float gap=24.f/screen_width,small=(.92f-2.f*gap)/3.f;const float x=i<2 ? .04f+i*(.92f+gap)*.5f : .04f+(i-2)*(small+gap);
    const float top_h=v->tab?(.833f-.280f-24.f/screen_height)*.5f:.219f;
    const float y=i<2 ? .280f : .280f+top_h+24.f/screen_height,w=i<2 ? (.92f-gap)*.5f : small,h=i<2 ? top_h : .833f-y;
    const int selected=v->focus==i;
    if(v->tab&&i>=2){
      float bx=.04f+(i-2)*(.92f+gap)*.5f;
      uint32_t icon=v->tab==1?(i==2?ML_HEADER_FINANCE:ML_HEADER_TRANSFER):(i==2?ML_HEADER_MANAGER:ML_HEADER_CALENDAR);
      const char *label=v->tab==1?(i==2?"CLUB PACKS":"UPCOMING"):(i==2?"SIGN OUT":"HOW TO PLAY");
      ml_ui_panel(ui,r->label,icon,bx,y,(.92f-gap)*.5f,h,selected,verts,quads);
      float tw=(.92f-gap)*.5f;
      ml_ui_art(ui,v->tab==1?(i==2?2:3):(i==2?3:2),bx+.010f,y+.088f,tw-.020f,h-.105f,verts,quads);
      fd_text(ui,label,bx+.027f,y+.115f,tw-.054f,.034f,-1,verts,quads);
      if(v->tab==1&&i==2)fd_text(ui,"LITE   MEDIUM   JUMBO",bx+.027f,y+.203f,tw-.054f,.024f,-1,verts,quads);
      continue;
    }
    if(i<2){
      ml_ui_frame(ui,x,y,w,h,selected,verts,quads);fd_card(ui,x,y,w,h,0,0,verts,quads);
      ml_ui_art(ui,i==1 ? 1 : 0,x,y,w,h,verts,quads);
      int live=!v->tab&&!i&&v->hub_phase==MH_MATCH&&v->hub_live;
      fd_text(ui,r->label,x+.020f,y+.024f,w-(live?.128f:.040f),.0333f,-1,verts,quads);
      if(live){
        fd_rect(ui,x+w-.095f,y+.022f,.075f,.040f,.91f,.05f,.18f,verts,quads);
        fd_center_text(ui,"LIVE",x+w-.095f,y+.042f,.075f,.0236f,-1,verts,quads);
      }
      if(i==1&&!v->tab&&v->news_preview_count){
        fd_text(ui,v->news_preview.label,x+.020f,y+.075f,w-.040f,.030f,-1,verts,quads);
        fd_text(ui,v->news_preview.detail,x+.020f,y+.123f,w-.040f,.0236f,-1,verts,quads);
      }else fd_text(ui,r->detail,x+.020f,y+.095f,w-.040f,!v->tab&&!i?.036f:.026f,-1,verts,quads);
      if(strcmp(r->value,"OPEN"))fd_text(ui,r->value,x+.020f,y+h-.041f,w-.040f,.0236f,-1,verts,quads);
    }else {
      static const uint32_t icons[3]={ML_HEADER_CALENDAR,ML_HEADER_RANKING,ML_HEADER_SAVE};
      ml_ui_panel(ui,r->label,icons[i-2],x,y,w,h,selected,verts,quads);
      if(i==3&&!v->tab){
        for(uint32_t n=0;n<v->table_preview_count;n++){
          const MdRow *item=&v->table_preview[n];float yy=y+.086f+n*.065f;
          fd_card(ui,x+.010f,yy,w-.020f,.059f,0,0,verts,quads);
          char rank[8];snprintf(rank,sizeof(rank),"%u",n+1);fd_text(ui,rank,x+.019f,yy+.017f,.022f,.024f,-2,verts,quads);
          if(item->badge)ml_ui_image(ui,gl.badge_tex,item->badge,x+.043f,yy+.007f,.026f,.046f,verts,quads);
          const char *name=strstr(item->label,". ");name=name?name+2:item->label;
          fd_text(ui,name,x+.077f,yy+.016f,w-.148f,.0236f,-2,verts,quads);
          fd_text(ui,item->value,x+w-.062f,yy+.017f,.053f,.0236f,-2,verts,quads);
        }
        if(!v->table_preview_count){fd_text(ui,"AWAITING THE LEAGUE TABLE",x+.017f,y+.120f,w-.034f,.025f,-2,verts,quads);}
      }else if(i==2&&!v->tab){
        const char *days[]={"M","T","W","T","F","S","S"};float cw=(w-.034f)/7.f;
        for(unsigned d=0;d<7;d++){float xx=x+.017f+d*cw;int today=v->history_week==d;
          fd_rect(ui,xx,y+.104f,cw-.003f,.054f,today?.03f:.89f,today?.34f:.95f,today?.72f:.99f,verts,quads);
          fd_center_text(ui,days[d],xx,y+.130f,cw-.003f,.024f,today?-1:-2,verts,quads);
          fd_rect(ui,xx,y+.164f,cw-.003f,.006f,d<3?.03f:d<6?.87f:.16f,d<3?.34f:d<6?.15f:.61f,.59f,verts,quads);
        }
        fd_text(ui,"W1",x+.017f,y+.190f,w*.25f,.026f,-2,verts,quads);
        fd_text(ui,"W2",x+.017f+cw*3,y+.190f,w*.25f,.026f,-2,verts,quads);
        fd_text(ui,"TODAY",x+.017f,y+.244f,.070f,.022f,-2,verts,quads);
        const char *phases[]={"","REGISTRATION","PREPARATION","MATCH DAY","LEAGUE END"};
        fd_text(ui,phases[v->hub_phase<5?v->hub_phase:0],x+.090f,y+.240f,w-.107f,.027f,-2,verts,quads);
      }else if(i==4&&!v->tab){
        if(v->badge)ml_ui_image(ui,gl.badge_tex,v->badge,x+.020f,y+.094f,.050f,.089f,verts,quads);
        fd_text(ui,v->name,x+.083f,y+.103f,w-.100f,.027f,-2,verts,quads);
        char detail[64];snprintf(detail,sizeof(detail),"%u PLAYERS",v->roster_size);fd_text(ui,detail,x+.083f,y+.147f,w-.100f,.025f,-2,verts,quads);
        snprintf(detail,sizeof(detail),"%u LEAGUE POINTS",v->league_points);fd_text(ui,detail,x+.020f,y+.202f,w-.040f,.032f,-2,verts,quads);
        
      }
    }
  }
  ml_ui_image(ui,switch_button_texture("L"),0,.056f,.204f,.020f,.035f,verts,quads);
  ml_ui_image(ui,switch_button_texture("R"),0,.924f,.204f,.020f,.035f,verts,quads);
  ml_ui_pills_count(ui,v->tab,3,.872f,verts,quads);
}
/* Bind read-only dummy data to the exact production Master League hub. */
static void md_ui_master_hub(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  if(v->online||v->hub_revised){md_ui_online_hub(ui,v,verts,quads);return;}
  MlView *hub=&ui->view;hub->page=ML_PAGE_HUB;hub->badge=v->badge;
  hub->section=v->tab==2u ? 3u : v->tab;hub->section_count=3;hub->selected=v->focus;hub->count=hub->total=5;
  hub->next_title_size=.0347f;
  hub->squad_size=v->roster_size;hub->board_target=1;hub->rank=v->rank;
  snprintf(hub->title,sizeof(hub->title),"MANAGER LEAGUE");
  snprintf(hub->caption,sizeof(hub->caption),"%s",v->caption);
  snprintf(hub->club_name,sizeof(hub->club_name),"%s",v->name);
  snprintf(hub->balance,sizeof(hub->balance),"%u LEAGUE POINT",v->league_points);
  snprintf(hub->season_summary,sizeof(hub->season_summary),"%u REGISTERED PLAYERS",v->roster_size);
  for(uint32_t i=0;i<5;i++) {
    snprintf(hub->rows[i].label,sizeof(hub->rows[i].label),"%s",v->rows[i].label);
    snprintf(hub->rows[i].detail,sizeof(hub->rows[i].detail),"%s",v->rows[i].detail);
    snprintf(hub->rows[i].value,sizeof(hub->rows[i].value),"%s",v->rows[i].value);
    hub->rows[i].enabled=1;
  }
  snprintf(hub->rows[4].value,sizeof(hub->rows[4].value),"OPEN CLUB PROFILE");
  snprintf(hub->next.home,sizeof(hub->next.home),"%s",v->home);snprintf(hub->next.away,sizeof(hub->next.away),"%s",v->away);
  /* Reuse the production generic feature for preparation and final results.
   * Match Day alone presents the next fixture as a broadcast card. */
  if(v->week.state!=MD_MATCH_DAY)hub->next.home[0]=0;
  hub->next.home_badge=v->home_badge;hub->next.away_badge=v->away_badge;
  snprintf(hub->next.day,sizeof(hub->next.day),"LEAGUE %02u",v->week_id);snprintf(hub->next.competition,sizeof(hub->next.competition),"%s",v->phase_label);
  hub->fixture_count=hub->ranking_count=hub->squad_count=3;
  for(uint32_t i=0;i<3;i++) {
    const MdRow *r=&v->table_preview[i];
    snprintf(hub->ranking[i].label,sizeof(hub->ranking[i].label),"%s",r->label+3);
    snprintf(hub->ranking[i].detail,sizeof(hub->ranking[i].detail),"%u",i+1);
    const char *pts=strrchr(r->value,' ');
    if(v->tab==2)snprintf(hub->ranking[i].value,sizeof(hub->ranking[i].value),"%u",(unsigned)strtoul(r->value,NULL,10));
    else snprintf(hub->ranking[i].value,sizeof(hub->ranking[i].value),"%s",pts ? pts+1 : r->value);
    hub->ranking[i].badge=r->badge;
    snprintf(hub->fixtures[i].label,sizeof(hub->fixtures[i].label),"%s",v->fixture_preview[i].label);
    snprintf(hub->fixtures[i].detail,sizeof(hub->fixtures[i].detail),"%s",v->fixture_preview[i].value);
    snprintf(hub->squad[i].label,sizeof(hub->squad[i].label),"%s",v->squad_preview[i].label);
    snprintf(hub->squad[i].detail,sizeof(hub->squad[i].detail),"REGISTERED PLAYER");
    snprintf(hub->squad[i].value,sizeof(hub->squad[i].value),"%s",v->squad_preview[i].value);
    hub->squad[i].portrait=v->squad_preview[i].portrait;

  }
  hub->feed_index=(uint32_t)(v->now_ms/5000u)%4u;hub->feed_progress=(v->now_ms%5000u)/5000.f;hub->feed_opacity=1;
  MlStoryView *story=&hub->story;story->club_badge=v->badge;
  snprintf(story->headline,sizeof(story->headline),"%.63s",v->headline);
  snprintf(story->summary,sizeof(story->summary),"%s",v->summary);
  if(!hub->feed_index && v->news_preview.label[0]) {
    story->club_badge=v->news_preview.badge;
    snprintf(story->headline,sizeof(story->headline),"%s",v->news_preview.label);
    snprintf(story->summary,sizeof(story->summary),"%s",v->news_preview.detail);
  }
  snprintf(story->stat_value[0],sizeof(story->stat_value[0]),"1");snprintf(story->stat_value[1],sizeof(story->stat_value[1]),"1");
  if(hub->feed_index==2) {
    snprintf(story->headline,sizeof(story->headline),"%s",v->week.state==MD_RESULT ? "THE FINAL LEAGUE TABLE" : "THE LEAGUE TITLE RACE");
    snprintf(story->summary,sizeof(story->summary),"%s",v->summary);
    snprintf(story->stat_value[0],sizeof(story->stat_value[0]),"%u",hub->rank);
  } else if(hub->feed_index==3) {
    snprintf(story->headline,sizeof(story->headline),"BUILD YOUR SQUAD");
    snprintf(story->summary,sizeof(story->summary),"%u NX Cash available in the player shop.",v->balance);
    snprintf(story->stat_value[0],sizeof(story->stat_value[0]),"%s",v->shop_locked ? "CLOSED" : "OPEN");
    snprintf(story->stat_value[1],sizeof(story->stat_value[1]),"%u",v->roster_size>18?v->roster_size-18:0);
  }
  story->has_result=v->last_complete;story->home_goals=v->last_hg;story->away_goals=v->last_ag;
  story->home_badge=v->last_home_badge;story->away_badge=v->last_away_badge;
  snprintf(story->home,sizeof(story->home),"%s",v->last_home);snprintf(story->away,sizeof(story->away),"%s",v->last_away);
  snprintf(story->result,sizeof(story->result),"FULL TIME");snprintf(story->competition,sizeof(story->competition),"MANAGER LEAGUE");
  static MlUiMotion motion;
  md_ui_chrome(ui,v,verts,quads);
  ml_ui_hub(ui,hub,ml_ui_navigation_slide(&motion,v->navigation_serial,v->slide_direction),verts,quads);
  /* Embed the same production shoulder sprites for this self-contained overlay. */
  ml_ui_image(ui,switch_button_texture("L"),0,.066f-.035f*.5625f*.5f,.222f-.0175f,.035f*.5625f,.035f,verts,quads);
  ml_ui_image(ui,switch_button_texture("R"),0,.934f-.035f*.5625f*.5f,.222f-.0175f,.035f*.5625f,.035f,verts,quads);
}
#include "manager_league_watch_overlay.inc"


static void md_ui_copy_row(MlViewRow *out,const MdRow *in) {
  snprintf(out->label,sizeof(out->label),"%s",in->label);snprintf(out->detail,sizeof(out->detail),"%s",in->detail);
  snprintf(out->value,sizeof(out->value),"%s",in->value);out->enabled=in->enabled;
  out->badge=in->badge;out->portrait=in->portrait;out->rating=in->rating;out->role=in->role;out->league_logo=in->league_logo;
}
static void md_ui_project(MasterLeagueRender *ui,const MdView *v) {
  MlView *m=&ui->view;m->page=ML_PAGE_CLUBS;m->selected=v->focus;m->first=v->first;m->count=v->count;m->total=v->total;
  m->badge=v->badge;snprintf(m->title,sizeof(m->title),"MANAGER LEAGUE");
  snprintf(m->caption,sizeof(m->caption),"%.95s",v->caption[0] ? v->caption : v->subtitle);
  snprintf(m->left_title,sizeof(m->left_title),"%.63s",v->headline);
  for(uint32_t i=0;i<v->count;i++){md_ui_copy_row(&m->rows[i],&v->rows[i]);if(v->online&&(v->page==MD_PAYMENT_RECOVERY||v->page==MD_ONLINEDEV||v->page==MD_PROMOTION||v->page==MD_PLAN_SETTINGS))m->rows[i].detail[0]=0;}
  if(v->page==MD_TEAM_INFO||v->page==MD_PLAN_RESERVES||v->page==MD_PURCHASE_HISTORY)m->page=ML_PAGE_MARKET_PLAYERS;
  if(v->page==MD_NAME || v->page==MD_LOGIN || v->page==MD_SECURE || v->page==MD_MIGRATE)m->page=ML_PAGE_MANAGER;
  if(v->page==MD_TABLE){m->page=ML_PAGE_TABLE;m->table_count=v->count;
    for(uint32_t i=0;i<v->count;i++){MlTableRow *r=&m->table[i];const MdRow *src=&v->rows[i];
      const char *name=strstr(src->label,". ");snprintf(r->name,sizeof(r->name),"%s",name?name+2:src->label);r->badge=src->badge;r->rank=v->first+i+1;r->own=v->online?src->selected:!src->team_id;r->stats=src->stats;}}
  if(v->page==MD_CALENDAR){m->page=ML_PAGE_CALENDAR;m->calendar_count=42;memcpy(m->calendar,v->calendar,sizeof(v->calendar));
    snprintf(m->calendar_month,sizeof(m->calendar_month),"%.47s",v->headline);snprintf(m->calendar_detail,sizeof(m->calendar_detail),"%s",v->caption);}

}
/* Adapt registration data to the existing Master League settings drawer.
 * Keep its row geometry, badge treatment, selection frame and scroll bar. */
static void md_ui_registration_picker(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  MlView *m=&ui->view;
  MlDrawerView *d=&m->drawer;
  d->open=1;d->serial=0x80000000u | (uint32_t)v->page;
  d->count=m->count;d->total=m->total;d->first=m->first;d->selected=m->selected;
  snprintf(d->title,sizeof(d->title),"%.63s",v->headline);
  for(uint32_t i=0;i<d->count;i++){d->rows[i]=m->rows[i];d->rows[i].detail[0]=0;d->rows[i].value[0]=0;}
  m->page=ML_PAGE_SETTINGS;m->count=m->total=2;m->first=0;m->selected=v->page==MD_CLUB;
  snprintf(m->left_title,sizeof(m->left_title),"YOUR CLUB");
  memset(m->rows,0,sizeof(m->rows));
  const ExhibitionTeamCategory *c=v->picker_category<EXHIBITION_TEAM_CATEGORY_COUNT ? &exhibition_team_categories[v->picker_category] : NULL;
  snprintf(m->rows[0].label,sizeof(m->rows[0].label),"LEAGUE");
  snprintf(m->rows[0].detail,sizeof(m->rows[0].detail),"%s",c ? c->label : "CHOOSE LEAGUE");
  m->rows[0].badge=c ? c->badge_slot : 0;m->rows[0].enabled=1;
  snprintf(m->rows[1].label,sizeof(m->rows[1].label),"CLUB");
  const MdRow *selected=v->page==MD_CLUB && v->focus>=v->first && v->focus-v->first<v->count ? &v->rows[v->focus-v->first] : NULL;
  snprintf(m->rows[1].detail,sizeof(m->rows[1].detail),"%s",selected ? selected->label : "CHOOSE CLUB");
  m->rows[1].badge=selected ? selected->badge : 0;m->rows[1].enabled=1;
  ml_ui_primary(ui,verts,quads);
}
static void md_ui_moving_art(MasterLeagueRender *ui,uint32_t sprite,float x,float y,float w,float h,float phase,GLfloat *verts,int *quads) {
  const int first=*quads;ml_ui_art(ui,sprite,x,y,w,h,verts,quads);
  MlDraw *d=&ui->draws[ui->draw_count-1];const float u=d->uv[0],v=d->uv[1],uw=d->uv[2],vh=d->uv[3],zoom=.86f;
  const float du=uw*(1-zoom)*(.5f+.5f*sinf(phase)),dv=vh*(1-zoom)*(.5f+.5f*cosf(phase*.73f));
  for(int q=first;q<*quads;q++)for(uint32_t n=0;n<6;n++){float *p=verts+q*24+n*4;p[2]=u+(p[2]-u)*zoom+du;p[3]=v+(p[3]-v)*zoom+dv;}
  d->uv[0]=u+du;d->uv[1]=v+dv;d->uv[2]=uw*zoom;d->uv[3]=vh*zoom;
}
static void md_ui_shop(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  for(uint32_t i=0;i<v->count && i<3;i++) {
    const MdRow *r=&v->rows[i];const float x=.080f+i*.285f,w=.265f;const int chosen=v->focus==i;
    ml_ui_frame(ui,x,.238f,w,.618f,chosen,verts,quads);
    fd_card(ui,x,.238f,w,.618f,0,0,verts,quads);
    const float phase=(float)(armTicksToNs(armGetSystemTick())%14000000000ULL)/14000000000.f*6.2831853f;
    if(chosen)md_ui_moving_art(ui,i==1 ? 1 : 0,x+.012f,.256f,w-.024f,.391f,phase,verts,quads);
    else ml_ui_art(ui,i==1 ? 1 : 0,x+.012f,.256f,w-.024f,.391f,verts,quads);
    /* Layered club foil uses the established blue/red FootballNX artwork. */
    fd_rect(ui,x+.038f,.293f,w-.076f,.304f,1,1,1,verts,quads);
    if(chosen)md_ui_moving_art(ui,i==1 ? 1 : 0,x+.042f,.300f,w-.084f,.289f,phase+.4f,verts,quads);
    else ml_ui_art(ui,i==1 ? 1 : 0,x+.042f,.300f,w-.084f,.289f,verts,quads);
    ml_ui_image(ui,gl.badge_tex,r->badge,x+.089f,.330f,.087f,.155f,verts,quads);
    fd_center_text(ui,r->label,x+.036f,.540f,w-.072f,.033f,-1,verts,quads);
    fd_center_text(ui,exhibition_team_catalog_name(r->team_id),x+.014f,.689f,w-.028f,.025f,-2,verts,quads);
    fd_center_text(ui,r->detail,x+.014f,.731f,w-.028f,.021f,-3,verts,quads);
    fd_card(ui,x+.018f,.776f,w-.036f,.058f,chosen,0,verts,quads);
    fd_center_text(ui,r->value,x+.025f,.805f,w-.050f,.027f,chosen ? -1 : -2,verts,quads);
  }
}
static void md_ui_pack(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  const int revealing=v->page==MD_PACK_OPENING,selecting=v->page==MD_PACK_SELECT || revealing;
  if(v->page==MD_PACK || v->page==MD_PACK_BUY) {
    fd_card(ui,.18f,.225f,.64f,.655f,0,0,verts,quads);
    const float phase=v->now_ms*.0005f;
    md_ui_moving_art(ui,0,.216f,.258f,.255f,.535f,phase,verts,quads);
    if(v->badge)ml_ui_image(ui,gl.badge_tex,v->badge,.289f,.358f,.110f,.1956f,verts,quads);
    fd_center_text(ui,"CLUB SELECTION",.230f,.663f,.227f,.030f,-1,verts,quads);
    fd_text(ui,v->headline,.502f,.320f,.280f,.033f,-2,verts,quads);
    char terms[64];snprintf(terms,sizeof(terms),"SELECT %u FROM %u",v->pack_draw,v->pack_pool);
    fd_text(ui,terms,.502f,.405f,.280f,.030f,-2,verts,quads);
    snprintf(terms,sizeof(terms),"%u NX CASH",v->pack_price);
    fd_text(ui,terms,.502f,.553f,.280f,.030f,-2,verts,quads);
    fd_card(ui,.502f,.654f,.275f,.077f,1,0,verts,quads);
    fd_center_text(ui,"BUY",.512f,.6925f,.255f,.031f,-1,verts,quads);
    return;
  }
  fd_card(ui,.045f,.225f,.910f,selecting ? .575f : .653f,0,0,verts,quads);
  char title[96];
  if(revealing)snprintf(title,sizeof(title),"YOUR CLUB SELECTION");
  else if(selecting)snprintf(title,sizeof(title),"SELECT %u FROM %u",v->pack_draw,v->pack_pool);
  else if(v->page==MD_PACK_RESULT)snprintf(title,sizeof(title),"%u PLAYERS CONFIRMED",v->pack_draw);
  else snprintf(title,sizeof(title),"%u PLAYERS FROM %u  -  %u NX CASH",v->pack_draw,v->pack_pool,v->pack_price);
  fd_center_text(ui,title,.075f,.263f,.85f,.032f,-2,verts,quads);
  if(selecting && !revealing){char count[48];snprintf(count,sizeof(count),"%u OF %u SELECTED",v->pack_selection_count,v->pack_draw);
    fd_center_text(ui,count,.075f,.296f,.85f,.021f,-3,verts,quads);}
  for(uint32_t i=0;i<v->pack_count;i++) {
    const MdRow *r=&v->pack_players[i];uint32_t col=i%4,row=i/4;
    const float raw=revealing ? fmaxf(0.f,fminf(1.f,((float)v->pack_opening_ms-MD_PACK_UNSEAL_MS-i*70.f)/400.f)) : 1.f;
    const float ease=raw*raw*(3.f-2.f*raw);
    float x=(!selecting && v->pack_count<=4 ? .5f-v->pack_count*.215f*.5f+.015f : .085f)+col*.215f;
    const float y=(selecting ? .330f : .314f)+row*(selecting ? .232f : .255f);
    const int vertex_first=*quads;
    const uint32_t draw_first=ui->draw_count;
    const int chosen=selecting && !revealing && v->focus==i,checked=selecting && (v->pack_selected&(1u<<i));
    if(chosen)ml_ui_frame(ui,x,y,.185f,.216f,1,verts,quads);
    fd_card(ui,x,y,.185f,.216f,0,0,verts,quads);ml_ui_art(ui,col%2,x,y,.185f,.144f,verts,quads);
    if(raw>=.65f) {
      GLuint portrait=r->portrait?gameplan_portrait_texture(r->portrait):0;
      if(portrait)ml_ui_image(ui,portrait,0,x+.054f,y+.007f,.077f,.137f,verts,quads);
      else {md_ui_circle(ui,x+.0925f,y+.044f,.040f,.60f,.66f,.70f,verts,quads);fd_rect(ui,x+.068f,y+.068f,.049f,.066f,.53f,.60f,.66f,verts,quads);}
      char rating[16];snprintf(rating,sizeof(rating),"%u",r->rating);fd_text(ui,rating,x+.012f,y+.018f,.045f,.031f,-1,verts,quads);
      static const char *const roles[]={"GK","CB","LB","RB","DMF","CMF","LMF","RMF","AMF","LWF","RWF","SS","CF"};
      fd_rect(ui,x+.010f,y+.105f,.047f,.028f,r->role==0 ? .91f : r->role<4 ? .10f : r->role<9 ? .05f : .83f,r->role==0 ? .55f : r->role<4 ? .36f : r->role<9 ? .58f : .10f,r->role==0 ? .08f : r->role<4 ? .80f : r->role<9 ? .32f : .20f,verts,quads);
      fd_center_text(ui,r->role<13 ? roles[r->role] : "?",x+.010f,y+.119f,.047f,.019f,-1,verts,quads);
      fd_center_text(ui,r->label,x+.007f,y+.174f,.171f,.0236f,-2,verts,quads);
    } else if(v->badge)ml_ui_image(ui,gl.badge_tex,v->badge,x+.064f,y+.035f,.057f,.1013f,verts,quads);
    if(checked){
      const float cx=x+.168f,cy=y+.026f;
      md_ui_circle(ui,cx,cy,.033f,1,1,1,verts,quads);
      md_ui_circle(ui,cx,cy,.028f,.035f,.28f,.76f,verts,quads);
      md_watch_line(ui,cx-.0055f,cy,cx-.0010f,cy+.005f,.0020f,1,1,1,1,verts,quads);
      md_watch_line(ui,cx-.0010f,cy+.005f,cx+.0060f,cy-.006f,.0020f,1,1,1,1,verts,quads);
    }
    if(revealing && raw<.65f) {
      const float source_x=.5f+((float)i-(v->pack_pool-1)*.5f)*.074f;
      const float cx=source_x+(x+.0925f-source_x)*ease,cy=.495f+(y+.108f-.495f)*ease;
      const float sx=(.58f+.42f*ease)*fmaxf(.018f,cosf(raw/.65f*1.5707963f));
      for(int q=vertex_first;q<*quads;q++)for(uint32_t n=0;n<6;n++) {
        float *p=verts+q*24+n*4;
        const float px=(p[0]+1.f)*.5f,py=(1.f-p[1])*.5f;
        p[0]=2.f*(cx+(px-x-.0925f)*sx)-1.f;
        p[1]=1.f-2.f*(cy+(py-y-.108f)*(1.3f-.3f*ease));
      }
    } else if(revealing && raw<1.f) {
      /* Portraits and text are never horizontally scaled. Reveal the complete
       * front at its final aspect only after the card back has folded away. */
      const float alpha=fminf(1.f,(raw-.65f)/.35f);
      for(uint32_t d=draw_first;d<ui->draw_count;d++)ui->draws[d].color[3]*=alpha;
    }
  }
  if(selecting && !revealing){const int ready=v->pack_selection_count==v->pack_draw;
    fd_card(ui,.295f,.833f,.410f,.065f,v->focus==v->pack_pool && ready,0,verts,quads);
    fd_center_text(ui,ready ? "CONFIRM" : "COMPLETE YOUR SELECTION",.310f,.865f,.380f,.029f,v->focus==v->pack_pool && ready ? -1 : ready ? -2 : -3,verts,quads);
  } else if(revealing)fd_center_text(ui,"REVEALING YOUR PLAYERS",.080f,.851f,.84f,.028f,-2,verts,quads);
}
static void md_ui_pack_opening(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  if(v->pack_opening_ms>=MD_PACK_UNSEAL_MS){md_ui_pack(ui,v,verts,quads);return;}
  const float t=fminf(1.f,v->pack_opening_ms/(float)MD_PACK_UNSEAL_MS);
  const float entrance=fminf(1.f,t/.23f),u=entrance-1;
  const float arrive=1.f+2.7f*u*u*u+1.7f*u*u;
  const float charge=fmaxf(0.f,fminf(1.f,(t-.25f)/.37f));
  const float burst=fmaxf(0.f,fminf(1.f,(t-.66f)/.34f));
  /* Arrival, foil sweep, unseal and fan-out: every phase derives from the
   * opening clock, so pause/seek and host captures render the same image. */
  const float squeeze=sinf(charge*3.1415926f);
  const float w=.235f-.018f*squeeze+.045f*burst,h=.495f+.025f*squeeze;
  const float x=.5f-w*.5f,y=.275f+.19f*(1-arrive)-.025f*charge;
  for(uint32_t i=0;i<v->pack_pool;i++) {
    const float spread=((float)i-(v->pack_pool-1)*.5f)*.074f*(1-powf(1-burst,3));
    const float yy=.355f+.025f*fabsf(spread*8.f);
    fd_card(ui,.5f+spread-.057f,yy,.114f,.294f,0,0,verts,quads);
    md_ui_moving_art(ui,i%2,.5f+spread-.053f,yy+.007f,.106f,.280f,t*4.f+i*.1f,verts,quads);
  }
  const int cover_first=*quads;
  const uint32_t face=ui->draw_count;
  fd_card(ui,x-.006f,y-.010f,w+.012f,h+.020f,0,0,verts,quads);
  md_ui_moving_art(ui,0,x,y,w,h,t*5.f,verts,quads);
  if(v->badge)ml_ui_image(ui,gl.badge_tex,v->badge,.448f,y+.098f,.104f,.185f,verts,quads);
  fd_center_text(ui,"CLUB SELECTION",x+.010f,y+.382f,w-.020f,.028f,-1,verts,quads);
  for(uint32_t d=face;d<ui->draw_count;d++)ui->draws[d].color[3]*=1.f-burst;
  if(charge>0 && burst<1) {
    const uint32_t sheen=ui->draw_count;
    const float sy=y+h*(1-charge),sh=.028f+.02f*sinf(charge*3.1415926f);
    fd_rect(ui,x,sy,w,sh,1,1,1,verts,quads);
    ui->draws[sheen].color[3]=.28f*(1-burst);
  }
  /* Anticipation shakes the sealed foil, then releases into a short upward
   * punch. Rotation uses pixel aspect so the pack retains its proportions. */
  const float angle=sinf(charge*35.f)*.027f*squeeze;
  const float cx=.5f,cy=y+h*.5f,aspect=screen_width/(float)screen_height;
  for(int q=cover_first;q<*quads;q++)for(uint32_t n=0;n<6;n++) {
    float *p=verts+q*24+n*4;const float dx=((p[0]+1.f)*.5f-cx)*aspect,dy=(1.f-p[1])*.5f-cy;
    p[0]=2.f*(cx+(dx*cosf(angle)-dy*sinf(angle))/aspect)-1.f;
    p[1]=1.f-2.f*(cy+dx*sinf(angle)+dy*cosf(angle));
  }
  if(burst>0.f) {
    const float pop=sinf(fminf(1.f,burst*3.f)*3.1415926f);
    const uint32_t flash=ui->draw_count;
    fd_rect(ui,.065f,.200f,.870f,.680f,1,1,1,verts,quads);
    ui->draws[flash].color[3]=.34f*pop;
    for(uint32_t i=0;i<28;i++) {
      const float a=i*2.399963f,rad=.045f+.31f*burst;
      const float px=.5f+cosf(a)*rad*.76f,py=.485f+sinf(a)*rad+.12f*burst*burst;
      const float tilt=a+burst*(i%2 ? 5.f : -5.f),length=.006f+.005f*(i%3);
      const uint32_t before=ui->draw_count;
      md_watch_line(ui,px,py,px+cosf(tilt)*length,py+sinf(tilt)*length,.0025f,
          i%3==0 ? .96f : .04f,i%3==0 ? .10f : .34f,i%3==0 ? .22f : .92f,1.f-burst,verts,quads);
      if(ui->draw_count>before)ui->draws[before].color[3]*=fminf(1.f,burst*8.f);
    }
  }
  fd_center_text(ui,burst>0 ? "YOUR SELECTION AWAITS" : "OPENING CLUB PACK",.25f,.84f,.5f,.030f,-2,verts,quads);
}
static void md_ui_match_history(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads){
  ml_ui_panel(ui,"MATCH HISTORY",ML_HEADER_MATCH,.055f,.205f,.890f,.675f,0,verts,quads);
  for(unsigned i=0;i<v->count;i++){
    const MdRow *r=&v->rows[i];float x=.073f,y=.300f+i*.102f,w=.854f;int ink=v->focus==v->first+i?-1:-2;
    MlViewRow surface={0};surface.enabled=1;ml_ui_row(ui,&surface,x,y,w,.090f,ink==-1,0,verts,quads);
    if(r->badge)ml_ui_image(ui,gl.badge_tex,r->badge,x+.015f,y+.014f,.034f,.060f,verts,quads);
    if(r->away_badge)ml_ui_image(ui,gl.badge_tex,r->away_badge,x+w-.049f,y+.014f,.034f,.060f,verts,quads);
    fd_text(ui,r->label,x+.070f,y+.012f,w-.220f,.029f,ink,verts,quads);
    fd_text(ui,r->detail,x+.070f,y+.053f,w-.220f,.022f,ink,verts,quads);
    fd_center_text(ui,r->value,x+w-.150f,y+.044f,.085f,.033f,ink,verts,quads);
  }
  if(!v->count)fd_center_text(ui,"NO COMPLETED MATCHES YET",.12f,.53f,.76f,.031f,-2,verts,quads);
  char label[64];snprintf(label,sizeof(label),"%u-%u OF %u",v->count?v->first+1:0,v->first+v->count,v->total);
  fd_center_text(ui,label,.2f,.848f,.6f,.024f,-2,verts,quads);
}
static void md_ui_match_centre(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  ml_ui_panel(ui,v->page==MD_TEAM_HISTORY ? "CLUB MATCH HISTORY" : "MATCH CENTRE",ML_HEADER_MATCH,.055f,.205f,.890f,.675f,0,verts,quads);
  static const char *const groups[]={"LIVE","SCHEDULED","MATCH ENDED"};
  for(uint32_t g=0;g<3;g++) {
    float x=.073f+g*.290f;char label[40];snprintf(label,sizeof(label),"%s  %u",groups[g],v->match_groups[g]);
    fd_card(ui,x,.294f,.274f,.045f,v->match_group==g,0,verts,quads);
    fd_center_text(ui,label,x+.007f,.3165f,.260f,.024f,v->match_group==g ? -1 : -2,verts,quads);
  }
  for(uint32_t i=0;i<v->count;i++) {
    const MdRow *r=&v->rows[i];const float x=.073f+(i%2)*.435f,y=.359f+(i/2)*.158f,w=.419f;
    const int chosen=v->first+i==v->focus,ink=chosen ? -1 : -2;
    MlViewRow surface={0};surface.enabled=1;ml_ui_row(ui,&surface,x,y,w,.142f,chosen,0,verts,quads);
    if(r->badge)ml_ui_image(ui,gl.badge_tex,r->badge,x+.012f,y+.033f,.034f,.0604f,verts,quads);
    if(r->away_badge)ml_ui_image(ui,gl.badge_tex,r->away_badge,x+w-.047f,y+.033f,.034f,.0604f,verts,quads);
    fd_center_text(ui,r->label,x+.052f,y+.031f,w-.104f,.024f,ink,verts,quads);
    fd_center_text(ui,r->value,x+.068f,y+.072f,w-.136f,.032f,ink,verts,quads);
    fd_center_text(ui,r->detail,x+.012f,y+.119f,w-.024f,.0195f,chosen ? -1 : -3,verts,quads);
    if(r->phase==1) {
      fd_rect(ui,x+w-.067f,y+.008f,.054f,.025f,.91f,.08f,.20f,verts,quads);
      fd_center_text(ui,"LIVE",x+w-.067f,y+.0205f,.054f,.018f,-1,verts,quads);
    }
  }
  if(!v->count)fd_center_text(ui,v->match_group==0 ? "NO MATCH IS LIVE RIGHT NOW" : v->match_group==1 ? "NO UPCOMING MATCHES" : "NO COMPLETED MATCHES YET",.10f,.552f,.80f,.0306f,-3,verts,quads);
  char range[48];snprintf(range,sizeof(range),"%u-%u OF %u",v->count ? v->first+1 : 0,v->first+v->count,v->total);
  fd_text(ui,range,.077f,.852f,.81f,.019f,-3,verts,quads);
}
static void md_ui_week_schedule(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  char title[40];snprintf(title,sizeof(title),"WEEKLY SCHEDULE");
  ml_ui_panel(ui,title,ML_HEADER_CALENDAR,.04f,.205f,.92f,.675f,0,verts,quads);
  char range[40];snprintf(range,sizeof(range),"DAYS %u-%u OF %u",v->first+1u,v->first+v->count,v->total);
  fd_text(ui,range,.755f,.232f,.150f,.024f,-1,verts,quads);
  for(uint32_t i=0;i<v->count;i++) {
    const MdRow *day=&v->rows[i];const MdScheduleDay *tile=&v->schedule[i];
    const float x=.057f,y=.298f+i*.190f,w=.870f,h=.174f;
    const int selected=v->focus==v->first+i,ink=selected ? -1 : -2;
    MlViewRow surface;memset(&surface,0,sizeof(surface));surface.enabled=day->enabled;
    ml_ui_row(ui,&surface,x,y,w,h,selected,0,verts,quads);
    fd_text(ui,day->label,x+.017f,y+.014f,.580f,.0306f,ink,verts,quads);
    fd_text(ui,day->value,x+w-.177f,y+.016f,.160f,.0278f,ink,verts,quads);
    ml_ui_rect(ui,x+.017f,y+.054f,w-.034f,.0014f,selected ? 1.f : .72f,selected ? 1.f : .80f,selected ? 1.f : .89f,.45f,-1,0,1,verts,quads);
    if(tile->match_count) {
      const float step=tile->match_count>3 ? .025f : .034f;
      const float text_size=tile->match_count>3 ? .0236f : .0278f;
      for(uint32_t n=0;n<tile->match_count;n++) {
        const MdRow *match=&tile->matches[n];const float yy=y+.064f+n*step;
        fd_text(ui,match->value,x+.017f,yy,.082f,text_size,ink,verts,quads);
        if(match->badge)ml_ui_image(ui,gl.badge_tex,match->badge,x+.108f,yy-.002f,step*.5625f,step,verts,quads);
        fd_text(ui,match->label,x+.140f,yy,.490f,text_size,ink,verts,quads);
        if(match->phase==1) {
          fd_rect(ui,x+w-.157f,yy-.001f,.063f,.023f,.91f,.08f,.20f,verts,quads);
          fd_center_text(ui,"LIVE",x+w-.157f,yy+.0105f,.063f,.017f,-1,verts,quads);
        }
        fd_text(ui,match->detail,x+w-.077f,yy+.001f,.060f,.0208f,ink,verts,quads);
      }
    } else {
      fd_text(ui,tile->period,x+.017f,y+.071f,w-.034f,.0333f,ink,verts,quads);
      fd_text(ui,day->detail,x+.017f,y+.124f,w-.034f,.0278f,selected ? -1 : -3,verts,quads);
    }
  }
  const float track_y=.298f,track_h=.554f,thumb_h=track_h*v->count/v->total;
  const float thumb_y=track_y+(track_h-thumb_h)*v->first/(v->total-v->count);
  fd_rect(ui,.944f,track_y,.004f,track_h,.83f,.88f,.94f,verts,quads);
  fd_rect(ui,.944f,thumb_y,.004f,thumb_h,.04f,.35f,.77f,verts,quads);
}
static void md_ui_pin(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  ml_ui_rect(ui,0,0,1,.925f,.015f,.035f,.09f,.68f,-1,0,1,verts,quads);
  ml_ui_panel(ui,v->pin_confirming ? "CONFIRM YOUR PIN" : v->pin_creating ? "CREATE YOUR PIN" : "ENTER YOUR PIN",ML_HEADER_MANAGER,.285f,.165f,.430f,.698f,0,verts,quads);
  fd_center_text(ui,v->pin_confirming ? "Enter the same four digits again" : v->pin_creating ? "Choose your four-digit login code" : "Your club is one code away",.310f,.274f,.380f,.0236f,-3,verts,quads);
  for(uint32_t i=0;i<4;i++) {
    const float x=.362f+i*.070f;
    fd_card(ui,x,.307f,.056f,.067f,0,0,verts,quads);
    if(i<v->pin_length)md_ui_circle(ui,x+.028f,.3405f,.018f,.035f,.20f,.46f,verts,quads);
    else fd_rect(ui,x+.019f,.340f,.018f,.0025f,.66f,.73f,.82f,verts,quads);
  }
  for(uint32_t i=0;i<12;i++) {
    const float x=.322f+(i%3)*.122f,y=.405f+(i/3)*.085f,w=.112f,h=.072f;
    const int ready=i!=11 || v->pin_length==4,chosen=v->pin_cursor==i && ready;
    fd_card(ui,x,y,w,h,chosen,0,verts,quads);
    char digit[2]={(char)('1'+i),0};
    const char *label=i==9 ? "DELETE" : i==10 ? "0" : i==11 ? "CONFIRM" : digit;
    fd_center_text(ui,label,x+.006f,y+h*.5f,w-.012f,i==9 || i==11 ? .0236f : .032f,chosen ? -1 : ready ? -2 : -3,verts,quads);
  }
  fd_center_text(ui,v->pin_confirming ? "2 OF 2 - CONFIRM" : v->pin_creating ? "1 OF 2 - CREATE" : "USER ID + PIN",.310f,.786f,.380f,.021f,-3,verts,quads);
}
static void md_ui_club_profile(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  ml_ui_panel(ui,"CLUB PROFILE",ML_HEADER_MANAGER,.055f,.205f,.890f,.675f,0,verts,quads);
  if(v->badge)ml_ui_image(ui,gl.badge_tex,v->badge,.160f,.310f,.090f,.160f,verts,quads);
  fd_center_text(ui,v->headline,.075f,.510f,.265f,.0333f,-2,verts,quads);
  fd_center_text(ui,v->club,.075f,.561f,.265f,.0222f,-3,verts,quads);
  char text[64];
  if(v->online)snprintf(text,sizeof(text),"%u REGISTERED PLAYERS",v->roster_size);
  else snprintf(text,sizeof(text),"POWER %u  -  OVR %u",v->club_power,v->club_rating);
  fd_center_text(ui,text,.075f,.639f,.265f,.025f,-2,verts,quads);
  if(v->online&&!v->club_rank)snprintf(text,sizeof(text),"LEAGUE - NOT RANKED");
  else snprintf(text,sizeof(text),"LEAGUE POSITION %u",v->club_rank);
  fd_center_text(ui,text,.075f,.697f,.265f,.025f,-2,verts,quads);
  snprintf(text,sizeof(text),"%u LEAGUE POINTS",v->league_points);
  fd_center_text(ui,text,.075f,.750f,.265f,.025f,-2,verts,quads);
  if(v->page==MD_OPPONENT_PROFILE)snprintf(text,sizeof(text),"TEAM OVR %u",v->club_rating);
  else if(v->online&&!v->season_label[0])snprintf(text,sizeof(text),"MONTHLY RANKING NOT PUBLISHED");
  else snprintf(text,sizeof(text),"%u PTS - CURRENT MONTH",v->club_reputation);
  fd_center_text(ui,text,.075f,.798f,.265f,.021f,-3,verts,quads);
  for(uint32_t i=0;i<v->count;i++) {
    MlViewRow r={0};md_ui_copy_row(&r,&v->rows[i]);
    ml_ui_row(ui,&r,.366f,.300f+i*.103f,.552f,.091f,v->focus==v->first+i,0,verts,quads);
  }
  char range[32];snprintf(range,sizeof(range),"%u-%u OF %u",v->first+1,v->first+v->count,v->total);
  fd_text(ui,range,.376f,.846f,.51f,.0208f,-3,verts,quads);
}
static void md_ui_club_plan(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  const float gx=(1.f-GP_GROUP_W)*.5f;
  const float x=gx+GP_PITCH_DX,y=GP_PITCH_Y,w=GP_PITCH_W,h=GP_PITCH_H;
  ml_ui_image(ui,gl.master_league_pearl_tex,0,0,0,1,1,verts,quads);
  ml_ui_art(ui,0,gx,.025f,GP_GROUP_W,.120f,verts,quads);
  if(v->badge)ml_ui_image(ui,gl.badge_tex,v->badge,gx+.012f,.044f,.045f,.080f,verts,quads);
  fd_text(ui,v->plan_editable?"YOUR GAME PLAN":v->headline,gx+.066f,.048f,GP_GROUP_W-.080f,.030f,-1,verts,quads);
  fd_text(ui,v->plan_formation,gx+.066f,.102f,.20f,.026f,-1,verts,quads);
  fd_rect(ui,x,y,w,h,.055f,.23f,.15f,verts,quads);
  for(uint32_t i=0;i<10;i+=2)fd_rect(ui,x,y+h*i/10,w,h/10,.065f,.25f,.17f,verts,quads);
  const float left=x+.008f,right=x+w-.008f,top=y+.014f,bottom=y+h-.014f,tx=.0015f,ty=.0026f;
  fd_rect(ui,left,top,right-left,ty,.72f,.83f,.75f,verts,quads);
  fd_rect(ui,left,bottom-ty,right-left,ty,.72f,.83f,.75f,verts,quads);
  fd_rect(ui,left,top,tx,bottom-top,.72f,.83f,.75f,verts,quads);
  fd_rect(ui,right-tx,top,tx,bottom-top,.72f,.83f,.75f,verts,quads);
  fd_rect(ui,left,y+h*.5f,right-left,ty,.72f,.83f,.75f,verts,quads);
  md_ui_circle(ui,x+w*.5f,y+h*.5f,h*.21f,.72f,.83f,.75f,verts,quads);
  md_ui_circle(ui,x+w*.5f,y+h*.5f,h*.20f,.055f,.23f,.15f,verts,quads);
  for(uint32_t end=0;end<2;end++)for(uint32_t box=0;box<2;box++) {
    const float bw=w*(box ? .24f : .56f),bh=h*(box ? .06f : .16f);
    const float bx=x+(w-bw)*.5f,by=end ? bottom-bh : top;
    fd_rect(ui,bx,by,tx,bh,.72f,.83f,.75f,verts,quads);
    fd_rect(ui,bx+bw-tx,by,tx,bh,.72f,.83f,.75f,verts,quads);
    fd_rect(ui,bx,end ? by : by+bh-ty,bw,ty,.72f,.83f,.75f,verts,quads);
  }
  static const float px[11]={.5f,.14f,.38f,.62f,.86f,.23f,.5f,.77f,.18f,.5f,.82f};
  static const float py[11]={.84f,.64f,.64f,.64f,.64f,.43f,.43f,.43f,.17f,.17f,.17f};
  static const char *const roles[]={"GK","CB","LB","RB","DMF","CMF","LMF","RMF","AMF","LWF","RWF","SS","CF"};
  for(uint32_t i=0;i<11;i++) {
    const MdPlanPlayer *p=&v->plan_players[i];
    const float nx=v->online?v->plan_dots[i].x:px[i],ny=v->online?v->plan_dots[i].y:py[i];
    const float xx=x+nx*(w-GP_PLAYER_W),yy=y+ny*(h-GP_PLAYER_H),cx=xx+GP_PLAYER_W*.5f;
    const int chosen=v->plan_editable&&(v->focus==i||v->plan_pick==i);
    GLuint tex=p->portrait?gameplan_portrait_texture(p->portrait):0;
    if(tex)ml_ui_image(ui,tex,0,cx-.015f,yy,.030f,.0533f,verts,quads);
    else {md_ui_circle(ui,cx,yy+.014f,.021f,.60f,.66f,.70f,verts,quads);fd_rect(ui,cx-.012f,yy+.025f,.024f,.029f,.53f,.60f,.66f,verts,quads);}
    if(chosen)ml_ui_frame(ui,xx-.002f,yy-.003f,GP_PLAYER_W+.004f,GP_PLAYER_H+.006f,1,verts,quads);
    fd_rect(ui,xx+GP_PLAYER_W*.04f,yy+.051f,GP_PLAYER_W*.92f,.022f,.02f,.07f,.05f,verts,quads);
    char label[24];snprintf(label,sizeof(label),"%s %u",p->role<13?roles[p->role]:"",p->rating);
    fd_center_text(ui,label,xx,yy+.062f,GP_PLAYER_W,.0192f,-1,verts,quads);
    fd_text(ui,p->label,xx-GP_PLAYER_W*.11f,yy+.074f,GP_PLAYER_W*1.22f,.0278f,-1,verts,quads);
  }
  unsigned plan_count=v->plan_count>=18&&v->plan_count<=MD_PLAN_PLAYERS?v->plan_count:18;
  unsigned bench_count=plan_count-11,bench_focus=v->focus>=11&&v->focus<plan_count?v->focus-11:v->plan_bench_focus;
  unsigned bench_start=bench_focus>3?bench_focus-3:0;if(bench_start+7>bench_count)bench_start=bench_count-7;
  for(uint32_t n=0;n<7;n++) {
    uint32_t i=11+bench_start+n;
    const MdPlanPlayer *p=&v->plan_players[i];MlViewRow r={0};
    snprintf(r.label,sizeof(r.label),"%s",p->label);r.portrait=p->portrait;r.rating=p->rating;r.role=p->role;
    snprintf(r.detail,sizeof(r.detail),"%s",p->role<13 ? roles[p->role] : "");r.enabled=1;
    ml_ui_row(ui,&r,gx+GP_BENCH_DX,GP_PITCH_Y+n*(GP_PITCH_H/7.f),GP_BENCH_W,GP_PITCH_H/7.f-.009f,v->plan_editable&&(v->focus==i||v->plan_pick==i),0,verts,quads);
  }
  if(bench_count>7){float sx=gx+GP_BENCH_DX+GP_BENCH_W+.003f;fd_rect(ui,sx,GP_PITCH_Y,.003f,GP_PITCH_H,.76f,.84f,.89f,verts,quads);fd_rect(ui,sx,GP_PITCH_Y+GP_PITCH_H*bench_start/bench_count,.003f,GP_PITCH_H*7/bench_count,.02f,.34f,.76f,verts,quads);}
  if(v->plan_editable){
    static const char *const labels[]={"SUBSTITUTE","FORMATION","TACTIC","POSITIONS"};
    const float bw=(GP_GROUP_W-3.f*GP_ACTION_GAP)/4.f;
    unsigned root=v->online?MD_PLAN_PLAYERS:18;
    for(unsigned i=0;i<4;i++){float bx=gx+i*(bw+GP_ACTION_GAP);fd_card(ui,bx,GP_ACTION_Y,bw,GP_ACTION_H,v->focus==root+i,0,verts,quads);fd_center_text(ui,labels[i],bx+.003f,GP_ACTION_Y+GP_ACTION_H*.5f,bw-.006f,.024f,v->focus==root+i?-1:-2,verts,quads);}
  }else {
    fd_card(ui,gx,GP_ACTION_Y,GP_GROUP_W,GP_ACTION_H,0,0,verts,quads);
    fd_center_text(ui,"LATEST SAVED TEAM DATA",gx+.012f,GP_ACTION_Y+GP_ACTION_H*.5f,GP_GROUP_W-.024f,.026f,-2,verts,quads);
  }
}
static void md_ui_league_clubs(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  ml_ui_panel(ui,v->headline,ML_HEADER_SQUAD,.13f,.205f,.74f,.670f,0,verts,quads);
  const float top=.280f+24.f/screen_height,bottom=.875f-24.f/screen_height,gap=12.f/screen_height;
  const float rh=v->count?(bottom-top-gap*(v->count-1))/v->count:0;
  for(unsigned i=0;i<v->count;i++){MlViewRow r={0};md_ui_copy_row(&r,&v->rows[i]);
    ml_ui_row(ui,&r,.13f+24.f/screen_width,top+i*(rh+gap),.74f-48.f/screen_width,rh,v->focus==v->first+i,0,verts,quads);}
}
static void md_ui_seven_days(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  ml_ui_panel(ui,v->headline,ML_HEADER_CALENDAR,.09f,.205f,.82f,.685f,0,verts,quads);
  const unsigned first=v->focus>2?v->focus-2:0,start=first>3?3:first;
  const float gap=12.f/screen_height,top=.280f+24.f/screen_height,bottom=.835f,rh=(bottom-top-3.f*gap)/4.f;
  for(unsigned n=0;n<4;n++){
    unsigned i=start+n;const MdRow *r=&v->rows[i];float y=top+n*(rh+gap);
    if(v->focus==i)ml_ui_frame(ui,.108f,y,.784f,rh,1,verts,quads);
    fd_card(ui,.108f,y,.784f,rh,0,0,verts,quads);
    if(r->selected){fd_rect(ui,.108f,y,.784f,rh,.84f,.95f,1.f,verts,quads);fd_rect(ui,.108f,y,.005f,rh,.02f,.55f,.78f,verts,quads);}
    fd_text(ui,r->label,.125f,y+.020f,.48f,.028f,-2,verts,quads);
    fd_text(ui,r->detail,.125f,y+.065f,.54f,.026f,-2,verts,quads);
    fd_center_text(ui,r->value,.686f,y+rh*.5f,.114f,.025f,-2,verts,quads);
    if(r->selected){fd_rect(ui,.810f,y+rh*.5f-.018f,.067f,.036f,.035f,.27f,.55f,verts,quads);fd_center_text(ui,"TODAY",.810f,y+rh*.5f,.067f,.022f,-1,verts,quads);}
  }
  char range[32];snprintf(range,sizeof(range),"%u-%u OF 7 DAYS",start+1,start+4);fd_center_text(ui,range,.1f,.867f,.8f,.0236f,-2,verts,quads);

}
static void md_ui_activity(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  int players=v->page==MD_PLAYER_FEED;
  ml_ui_panel(ui,v->headline,players?ML_HEADER_RANKING:ML_HEADER_NEWS,.07f,.205f,.86f,.685f,0,verts,quads);
  if(players){
    static const char *const labels[]={"TOP SCORERS","RISING STARS"};
    for(uint32_t i=0;i<2;i++){float x=.088f+i*.416f;fd_card(ui,x,.301f,.408f,.042f,v->feed_section==i,0,verts,quads);fd_center_text(ui,labels[i],x,.322f,.408f,.0236f,v->feed_section==i?-1:-2,verts,quads);}
  }
  for(uint32_t i=0;i<v->count&&i<3;i++){
    const MdFeedItem *f=&v->feed[i];const MdRow *r=&f->row;float y=players?.371f+i*.153f:.308f+i*.172f,h=players?.140f:.151f;
    if(v->focus==v->first+i)ml_ui_frame(ui,.088f,y,.824f,h,1,verts,quads);
    fd_card(ui,.088f,y,.824f,h,0,0,verts,quads);
    if(r->identity||r->portrait){GLuint tex=r->portrait?gameplan_portrait_texture(r->portrait):0;
      if(tex)ml_ui_image(ui,tex,0,.102f,y+.014f,.052f,.092f,verts,quads);
      else {md_ui_circle(ui,.128f,y+.039f,.035f,.53f,.60f,.66f,verts,quads);fd_rect(ui,.111f,y+.056f,.034f,.043f,.53f,.60f,.66f,verts,quads);}
      if(r->badge)ml_ui_image(ui,gl.badge_tex,r->badge,.136f,y+.083f,.025f,.044f,verts,quads);
    }else if(r->badge)ml_ui_image(ui,gl.badge_tex,r->badge,.104f,y+.030f,.050f,.089f,verts,quads);
    else if(gl.manager_unknown_club_tex)ml_ui_image(ui,gl.manager_unknown_club_tex,0,.104f,y+.030f,.050f,.089f,verts,quads);
    if(r->away_badge)ml_ui_image(ui,gl.badge_tex,r->away_badge,.855f,y+.026f,.040f,.071f,verts,quads);
    fd_text(ui,r->label,.177f,y+.019f,players?.40f:.66f,.028f,-2,verts,quads);
    if(players){
      fd_text(ui,f->body,.177f,y+.055f,.40f,.026f,-2,verts,quads);
      static const char *const labels[]={"GOALS","ASSISTS","MATCH OVR"};
      for(unsigned j=0;j<3;j++){
        float x=.598f+j*.098f;char number[16];
        if(j==1&&!f->assists_known)snprintf(number,sizeof(number),"--");
        else snprintf(number,sizeof(number),"%u",j==0?f->goals:j==1?f->assists:r->rating);
        fd_center_text(ui,labels[j],x,y+.038f,.091f,.0185f,-3,verts,quads);
        fd_center_text(ui,number,x,y+.084f,.091f,.032f,-2,verts,quads);
      }
    }else ml_ui_paragraph(ui,f->body,.177f,y+.052f,r->away_badge?.66f:.71f,.026f,2u,-2,verts,quads);
    fd_text(ui,f->context,.177f,y+(players?.110f:.120f),players?.40f:.71f,.021f,-3,verts,quads);
  }
  if(!v->count)fd_center_text(ui,v->empty_detail,.10f,.53f,.80f,.029f,-3,verts,quads);
  char range[64];if(v->count)snprintf(range,sizeof(range),"%u-%u OF %u",v->first+1,v->first+v->count,v->total);else snprintf(range,sizeof(range),"NO PUBLISHED RECORDS");
  fd_center_text(ui,range,.1f,.852f,.80f,.021f,-3,verts,quads);
  
}
static void md_ui_monthly_ranking(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads) {
  ml_ui_panel(ui,"LEAGUE RANKING",ML_HEADER_RANKING,.07f,.205f,.86f,.685f,0,verts,quads);
  static const char *const tabs[]={"CURRENT SEASON","PAST SEASON"};
  for(unsigned i=0;i<2;i++){float x=.088f+i*.416f;fd_card(ui,x,.301f,.408f,.042f,v->ranking_section==i,0,verts,quads);fd_center_text(ui,tabs[i],x,.322f,.408f,.0236f,v->ranking_section==i?-1:-2,verts,quads);}
  char caption[112];
  if(v->ranking_section)snprintf(caption,sizeof(caption),"CHAMPIONS FROM ALL COMPLETED SEASONS");
  else {time_t seconds=(time_t)(v->rank_reset_ms/1000u+25200u);struct tm date;char reset[24]="";
    if(v->rank_reset_ms&&gmtime_r(&seconds,&date))strftime(reset,sizeof(reset),"%d %b %Y",&date);
    snprintf(caption,sizeof(caption),"%s - RESETS %s 00:00 WIB",v->season_label,reset);
  }
  fd_center_text(ui,caption,.09f,.373f,.82f,.022f,-3,verts,quads);
  for(unsigned i=0;i<v->count&&i<5;i++){
    const MdRow *r=&v->rows[i];float y=.410f+i*.079f;
    if(v->focus==v->first+i)ml_ui_frame(ui,.088f,y,.824f,.068f,1,verts,quads);
    fd_card(ui,.088f,y,.824f,.068f,0,0,verts,quads);
    if(r->badge)ml_ui_image(ui,gl.badge_tex,r->badge,.101f,y+.010f,.028f,.050f,verts,quads);
    else if(gl.manager_unknown_club_tex)ml_ui_image(ui,gl.manager_unknown_club_tex,0,.101f,y+.010f,.028f,.050f,verts,quads);
    fd_text(ui,r->label,.144f,y+.008f,.60f,.025f,-2,verts,quads);
    fd_text(ui,r->detail,.144f,y+.041f,.60f,.019f,-3,verts,quads);
    fd_center_text(ui,r->value,.755f,y+.034f,.143f,.026f,-2,verts,quads);
  }
  if(!v->count)fd_center_text(ui,v->empty_detail,.10f,.56f,.80f,.028f,-3,verts,quads);
  char range[48];snprintf(range,sizeof(range),"%u-%u OF %u",v->count?v->ranking_offset+v->first+1:0,v->ranking_offset+v->first+v->count,v->total);
  fd_center_text(ui,range,.1f,.818f,.8f,.020f,-3,verts,quads);

}
static void md_ui_owned_players(MasterLeagueRender *ui,const MdView *v,GLfloat *verts,int *quads){
  static const char *const roles[]={"GK","CB","LB","RB","DMF","CMF","LMF","RMF","AMF","LWF","RWF","SS","CF"};
  ml_ui_panel(ui,v->headline,ML_HEADER_TRANSFER,.13f,.205f,.74f,.675f,0,verts,quads);
  for(unsigned i=0;i<v->count;i++){
    const MdRow *p=&v->rows[i];MlViewRow r={0};md_ui_copy_row(&r,p);
    snprintf(r.detail,sizeof(r.detail),"%s",p->role<13?roles[p->role]:"");
    float y=.300f+i*.103f;int selected=v->focus==v->first+i;
    ml_ui_row(ui,&r,.148f,y,.704f,.091f,selected,0,verts,quads);
    if(v->page==MD_PURCHASE_HISTORY)fd_text(ui,p->detail,.600f,y+.057f,.205f,.024f,selected?-1:-2,verts,quads);
  }
  if(v->total){char range[40];snprintf(range,sizeof(range),"%u-%u OF %u",v->first+1,v->first+v->count,v->total);fd_center_text(ui,range,.15f,.842f,.70f,.024f,-2,verts,quads);}
  else fd_center_text(ui,v->summary,.16f,.505f,.68f,.028f,-2,verts,quads);
}
static void manager_dummy_emit(MasterLeagueRender *ui,GLfloat *verts,int *quads) {
  MdView v;manager_client_view(&v);memset(ui,0,sizeof(*ui));
  if(v.page==MD_DASHBOARD || v.page==MD_LOGOUT || v.page==MD_NEXT_WEEK)md_ui_master_hub(ui,&v,verts,quads);
  else if(v.page==MD_WATCH)md_watch_emit(ui,&v,verts,quads);
  else {
    md_ui_project(ui,&v);if(v.page!=MD_CLUB_PLAN)md_ui_chrome(ui,&v,verts,quads);
    if(v.page==MD_REGISTER) {
      fd_card(ui,.075f,.245f,.850f,.590f,0,0,verts,quads);
      ml_ui_art(ui,0,.075f,.245f,.850f,.175f,verts,quads);
      fd_text(ui,"BUILD YOUR CLUB",.112f,.302f,.74f,.048f,-1,verts,quads);
      if(gl.manager_unknown_club_tex)ml_ui_image(ui,gl.manager_unknown_club_tex,0,.133f,.473f,.104f,.185f,verts,quads);
      fd_text(ui,"YOUR CLUB",.282f,.477f,.56f,.042f,-2,verts,quads);
      fd_text(ui,"Choose a club. Create your profile. Join the league.",.282f,.548f,.56f,.027f,-3,verts,quads);
      for(uint32_t i=0;i<2;i++) {
        const float x=.282f+i*.286f,w=.274f;const int selected=v.focus==i;
        fd_card(ui,x,.658f,w,.096f,selected,0,verts,quads);
        fd_action_content(ui,i ? "REGISTER" : "LOGIN",ML_HEADER_MANAGER,x,.658f,w,.096f,.031f,selected ? -1 : -2,verts,quads);
      }
    } else if(v.page==MD_LEAGUES||v.page==MD_CLUB)md_ui_registration_picker(ui,&v,verts,quads);
    else if((v.page==MD_SHOP||v.page==MD_SHOP_CLUBS))md_ui_shop(ui,&v,verts,quads);
    else if(v.page==MD_PACK_OPENING)md_ui_pack_opening(ui,&v,verts,quads);
    else if(v.page==MD_PACK || v.page==MD_PACK_BUY || v.page==MD_PACK_RESULT || v.page==MD_PACK_SELECT)md_ui_pack(ui,&v,verts,quads);
    else if(v.page==MD_TABLE){
      if(v.online&&!v.count){ml_ui_panel(ui,"LEAGUE STANDINGS",ML_HEADER_RANKING,.04f,.205f,.92f,.675f,0,verts,quads);fd_center_text(ui,"AWAITING THE LEAGUE TABLE",.08f,.45f,.84f,.032f,-2,verts,quads);fd_center_text(ui,v.summary,.08f,.53f,.84f,.026f,-3,verts,quads);fd_center_text(ui,v.empty_detail,.08f,.60f,.84f,.0236f,-3,verts,quads);}
      else ml_ui_table(ui,verts,quads);
    }
    else if(v.page==MD_TEAM_HISTORY && v.online)md_ui_match_history(ui,&v,verts,quads);
    else if(v.page==MD_SCHEDULE || v.page==MD_TEAM_HISTORY)md_ui_match_centre(ui,&v,verts,quads);
    else if(v.page==MD_CALENDAR)md_ui_week_schedule(ui,&v,verts,quads);
    else if(v.page==MD_WEEK_SCHEDULE)md_ui_seven_days(ui,&v,verts,quads);
    else if(v.page==MD_NEWS||v.page==MD_PLAYER_FEED)md_ui_activity(ui,&v,verts,quads);
    else if(v.page==MD_OVERALL)md_ui_monthly_ranking(ui,&v,verts,quads);
    else if(v.page==MD_CLUB_PROFILE || v.page==MD_OPPONENT_PROFILE)md_ui_club_profile(ui,&v,verts,quads);
    else if(v.page==MD_CLUB_PLAN)md_ui_club_plan(ui,&v,verts,quads);
    else if(v.page==MD_TEAMS_PAGE)md_ui_league_clubs(ui,&v,verts,quads);
    else if(v.page==MD_PURCHASE_HISTORY||v.page==MD_PLAN_RESERVES)md_ui_owned_players(ui,&v,verts,quads);
    else ml_ui_primary(ui,verts,quads);
  }
  fd_rect(ui,0,.925f,1,.075f,.025f,.10f,.28f,verts,quads);ui->draws[ui->draw_count-1].round.radius=0;
  float hx=.035f;for(uint32_t i=0;i<v.helper_count;i++)fd_helper_at(ui,v.helper_key[i],v.helper_label[i],.9625f,&hx,verts,quads);
  if(v.pin_open)md_ui_pin(ui,&v,verts,quads);
  if(v.touchline_open)md_watch_touchline(ui,&v,verts,quads);
  if(v.page==MD_CHAMPIONS && !v.count)fd_center_text(ui,v.summary,.075f,.865f,.850f,.0222f,-3,verts,quads);
  if(v.modal.open){ui->view.modal=v.modal;ml_ui_confirmation(ui,verts,quads);}
}
