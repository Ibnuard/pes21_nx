#ifndef PESNX_MANAGER_LEAGUE_HUB_H
#define PESNX_MANAGER_LEAGUE_HUB_H
#include "manager_league_dummy.h"
#include "competition_hub_navigation.h"
#include "manager_league_season.h"
#include <stdio.h>
#include <string.h>
#include <time.h>

enum { MH_UNKNOWN, MH_REGISTRATION, MH_PREPARATION, MH_MATCH, MH_END };
enum { MH_RULE_COUNT=12 };
static inline uint32_t md_hub_phase(const char *state) {
  if(!strcmp(state,"REGISTRATION"))return MH_REGISTRATION;
  if(!strcmp(state,"PREPARATION"))return MH_PREPARATION;
  if(strstr(state,"MATCH")||strstr(state,"COMPETITION"))return MH_MATCH;
  if(strstr(state,"RESULT")||strstr(state,"CLOSED")||!strcmp(state,"SETTLED")||!strcmp(state,"LEAGUE_END"))return MH_END;
  return MH_UNKNOWN;
}
static inline const char *md_hub_phase_name(uint32_t phase) {
  static const char *const names[]={"CALENDAR PENDING","REGISTRATION DAY","PREPARATION DAY","MATCH DAY","LEAGUE END"};
  return names[phase<=MH_END?phase:0];
}
static inline const char *md_hub_phase_help(uint32_t phase) {
  static const char *const help[]={
    "The league calendar has not been published yet. Refresh to check for an update.",
    "Register today, then prepare your squad and Game Plan. Registration closes tonight. Each league entry grants 1,500 NX Cash once.",
    "Registration is closed. Prepare your squad and Game Plan before Match Day. W1 plays Wednesday; W2 plays Saturday.",
    "Follow LIVE matches, upcoming kickoffs and completed replays in Match Centre.",
    "All matches in this league have ended. Review results and replays. Podium rewards are settled on Sunday."};
  return help[phase<=MH_END?phase:0];
}
static inline uint32_t md_hub_weekday(uint64_t now) {
  return (uint32_t)(((now/86400000u+(now%86400000u+25200000u)/86400000u)+3u)%7u); /* Mon=0, WIB */
}
static inline uint64_t md_hub_midnight(uint64_t now) {
  uint64_t day=now/86400000u+(now%86400000u+25200000u)/86400000u;
  return day?day*UINT64_C(86400000)-25200000u:0;
}
static inline void md_hub_countdown(char *out,size_t size,uint64_t now,uint64_t end) {
  if(!end)snprintf(out,size,"TIME TO BE CONFIRMED");
  else if(end<=now)snprintf(out,size,"UPDATING PHASE...");
  else {uint64_t minutes=(end-now+59999u)/60000u;snprintf(out,size,"ENDS IN %lluH %02lluM",(unsigned long long)(minutes/60),(unsigned long long)(minutes%60));}
}
/* HOME has five tiles; MY TEAM and LEAGUE use two-by-two grids. */
static inline void md_hub_navigate(uint32_t key,uint32_t *tab,uint32_t *focus) {
  if(*tab){
    if(*focus>3)*focus=3;
    if(key&(1u<<10)){if(*focus>=2)*focus-=2;}
    else if(key&(1u<<11)){if(*focus<2)*focus+=2;}
    else if(key&(1u<<4)){(*tab)--;*focus=*focus>=2?2:0;}
    else if(key&(1u<<7)){if(*tab<2){(*tab)++;*focus=*focus>=2?2:0;}}
    else if(key&(1u<<12)){if(*focus%2)(*focus)--;else{(*tab)--;*focus=*focus>=2?(*tab?3:4):1;}}
    else if(key&(1u<<13)){if(!(*focus%2))(*focus)++;else if(*tab<2){(*tab)++;*focus=*focus>=2?2:0;}}
  }else fnx_hub_navigate_count(key,tab,focus,3);
  if(*tab&&*focus>3)*focus=3;
}
static inline void md_hub_fill(MdView *v,uint32_t phase,uint64_t now,uint64_t end,const char *week) {
  static const char *const names[3][5]={
    {"","CLUB FEED","SCHEDULE","LEAGUE STANDINGS","CLUB PROFILE"},
    {"GAME PLAN","PLAYER FEED","SHOP","TRADE HISTORY",""},
    {"LEAGUE RANKING HISTORY","LEAGUE RANKING","LOGOUT","LEAGUE GUIDE",""}};
  static const char *const details[3][5]={
    {"","Latest club activity","Seven days. Two league weeks.","The top three in your league","Your club, squad and records"},
    {"Set your formation, eleven and tactics","Top scorers and Rising Stars","Choose players with NX Cash","Player trading is coming in a future update",""},
    {"Previous W1 and W2 league champions","Monthly points and past season champions","Your progress stays saved","Points, daily schedule and rewards",""}};
  uint32_t tab=v->tab<3?v->tab:0;v->hub_revised=1;v->hub_phase=phase;v->history_week=md_hub_weekday(now);v->count=tab?4:5;
  for(uint32_t i=0;i<v->count;i++){
    MdRow *r=&v->rows[i];memset(r,0,sizeof(*r));r->enabled=1;
    snprintf(r->label,sizeof(r->label),"%s",names[tab][i]);snprintf(r->detail,sizeof(r->detail),"%s",details[tab][i]);snprintf(r->value,sizeof(r->value),"OPEN");
  }
  if(!tab){
    snprintf(v->rows[0].label,sizeof(v->rows[0].label),"%s%s%s",md_hub_phase_name(phase),week&&week[0]?" ":"",week?week:"");
    md_hub_countdown(v->rows[0].detail,sizeof(v->rows[0].detail),now,end);
    snprintf(v->rows[0].value,sizeof(v->rows[0].value),"%s",phase==MH_UNKNOWN?"REGISTRATION STATUS PENDING":v->joined?"REGISTERED":"NOT REGISTERED");
    snprintf(v->rows[2].value,sizeof(v->rows[2].value),"W1 MON-WED / W2 THU-SAT");
  }else if(tab==1){
    snprintf(v->rows[1].value,sizeof(v->rows[1].value),"%s",phase>=MH_MATCH?"OPEN":"OPENS ON MATCH DAY");
    snprintf(v->rows[3].value,sizeof(v->rows[3].value),"UPCOMING");
  }
}
static inline void md_hub_calendar(MdView *v,uint64_t now) {
  static const char *const days[]={"MONDAY","TUESDAY","WEDNESDAY","THURSDAY","FRIDAY","SATURDAY","SUNDAY"};
  static const char *const descriptions[]={"Registration & preparation","Preparation - finalise your Game Plan","Match Day - follow the broadcasts","Registration & preparation","Preparation - finalise your Game Plan","Match Day - follow the broadcasts","Results overview & podium rewards"};
  uint32_t today=md_hub_weekday(now);uint64_t midnight=md_hub_midnight(now),offset=today*UINT64_C(86400000);
  uint64_t monday=midnight>=offset?midnight-offset:0;
  snprintf(v->headline,sizeof(v->headline),"WEEKLY SCHEDULE");snprintf(v->summary,sizeof(v->summary),"ALL TIMES WIB (UTC+7) - TWO LEAGUES PER REAL WEEK");v->count=v->total=7;v->first=0;
  for(uint32_t i=0;i<7;i++){
    MdRow *r=&v->rows[i];memset(r,0,sizeof(*r));time_t stamp=(time_t)((monday+i*UINT64_C(86400000))/1000+25200);struct tm day;
    char date[24]="";if(gmtime_r(&stamp,&day))strftime(date,sizeof(date),"%d %b %Y",&day);
    snprintf(r->label,sizeof(r->label),"%s - %s",days[i],date);snprintf(r->detail,sizeof(r->detail),"%s",descriptions[i]);
    snprintf(r->value,sizeof(r->value),"%s",i<3?"LEAGUE W1":i<6?"LEAGUE W2":"W1 + W2");r->selected=i==today;r->enabled=1;
  }
}
static inline void md_hub_rules(MdView *v,uint32_t focus) {
  static const char *const titles[]={"TWO LEAGUES PER REAL WEEK","MONDAY / THURSDAY","TUESDAY / FRIDAY","WEDNESDAY / SATURDAY","SUNDAY","MATCH POINTS","FOUR TEAMS MINIMUM","NX CASH","CASH PODIUM REWARDS","MONTHLY LEAGUE RANKING","RANKING PODIUM BONUS","PAST SEASONS"};
  static const char *const details[]={"W1: Monday-Wednesday. W2: Thursday-Saturday. Times WIB.","Register and prepare. Entries close at midnight.","Preparation only. Finalise your squad and Game Plan.","Match Day. LIVE, Scheduled and Ended in Match Centre.","Results overview and cash rewards for both league weeks.","Win 3, draw 1, loss 0. Then goal difference and goals scored.","1-3 human entries are filled to four with BOT clubs.","5,000 starting wallet. +1,500 once per league joined.","1st: 5,000. 2nd: 4,000. 3rd: 3,000 NX Cash.","+500 PTS per league joined. Resets on the 1st, 00:00 WIB.","Added to participation: 1st +2,000; 2nd +1,500; 3rd +1,000 PTS.","One champion per completed month. W1/W2 honours stay in Ranking History."};
  snprintf(v->headline,sizeof(v->headline),"LEAGUE GUIDE & RULES");v->total=MH_RULE_COUNT;v->first=focus/5*5;v->count=MH_RULE_COUNT-v->first;if(v->count>5)v->count=5;
  for(uint32_t i=0;i<v->count;i++){MdRow *r=&v->rows[i];memset(r,0,sizeof(*r));r->enabled=1;snprintf(r->label,sizeof(r->label),"%s",titles[v->first+i]);snprintf(r->detail,sizeof(r->detail),"%s",details[v->first+i]);}
}
#endif
