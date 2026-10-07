/* Career office simulation. All decisions run on explicit actions/date events,
 * never during projection/rendering; saves retain the rolled response date. */
static const uint32_t ml_window_days[]={0u,15u,30u,184u,199u,214u};
static void ml_notice(MasterLeague *c,uint32_t kind,const char *text) {
  MlOfficeState *o=&c->office;
  if(o->notice_count==ML_MAX_MESSAGES) {
    memmove(o->notices,o->notices+1,(ML_MAX_MESSAGES-1u)*sizeof(o->notices[0]));
    o->notice_count--;
  }
  MlNotice *n=&o->notices[o->notice_count++];memset(n,0,sizeof(*n));
  n->kind=kind;n->day=c->day;n->season=c->season;
  snprintf(n->text,sizeof(n->text),"%s",text);
}
static MlOffer *ml_offer_find(MasterLeague *c,uint32_t id) {
  for(uint32_t i=0;i<c->office.offer_count;i++)if(c->office.offers[i].id==id)return &c->office.offers[i];
  return NULL;
}
static int ml_offer_live(const MlOffer *o) {return o->status>=ML_OFFER_WAITING && o->status<=ML_OFFER_COUNTER;}
int ml_offer_unread(const MasterLeague *c,uint32_t index) {
  if(!c || index>=c->office.offer_count)return 0;
  const MlOffer *o=&c->office.offers[index];
  const int update=o->status==ML_OFFER_ACCEPTED || o->status==ML_OFFER_COUNTER ||
      o->status==ML_OFFER_REJECTED || o->status==ML_OFFER_EXPIRED;
  return update && c->offer_seen[index]!=((o->rounds<<8)|o->status);
}
void ml_offer_mark_read(MasterLeague *c,uint32_t index) {
  if(!c || index>=c->office.offer_count)return;
  const MlOffer *o=&c->office.offers[index];
  c->offer_seen[index]=(o->rounds<<8)|o->status;
}
static uint32_t ml_window_end(const MasterLeague *c) {return c->day<31u ? 30u : 214u;}
static MlOffer *ml_offer_allocate(MasterLeague *c) {
  MlOfficeState *s=&c->office;
  if(s->next_id==UINT32_MAX)return NULL;
  if(s->offer_count==ML_MAX_OFFERS) {
    uint32_t i=0u;while(i<s->offer_count && ml_offer_live(&s->offers[i]))i++;
    if(i==s->offer_count)return NULL;
    memmove(&s->offers[i],&s->offers[i+1u],(s->offer_count-i-1u)*sizeof(s->offers[0]));
    memmove(&c->offer_seen[i],&c->offer_seen[i+1u],(s->offer_count-i-1u)*sizeof(c->offer_seen[0]));s->offer_count--;
  }
  c->offer_seen[s->offer_count]=0u;
  MlOffer *o=&s->offers[s->offer_count++];memset(o,0,sizeof(*o));o->id=++s->next_id;return o;
}
const char *ml_offer_submit(MasterLeague *c,uint32_t player,uint32_t fee,uint32_t wage,uint32_t years,uint32_t id) {
  if(!c || c->office.dismissed || player>=c->player_count)return "INVALID NEGOTIATION";
  if(!ml_window_open(c))return "TRANSFER WINDOW CLOSED";
  if(c->day==ml_window_end(c))return "DEADLINE DAY - RESOLVE EXISTING TERMS";
  if(years<1u || years>5u || !wage || wage>1000000u || fee>1000000000u)return "INVALID TERMS";
  MlPlayer *p=&c->players[player];MlOffer *o=id ? ml_offer_find(c,id) : NULL;
  if(id && (!o || o->player!=player || !ml_offer_live(o) || o->status==ML_OFFER_WAITING || o->from!=p->club))return "OFFER IS NOT NEGOTIABLE";
  if(!id && p->club==c->settings.club)return "USE MY TEAMS TO REVIEW BUYER OFFERS";
  if(!id)for(uint32_t i=0;i<c->office.offer_count;i++)
    if(c->office.offers[i].player==player) {
      const MlOffer *old=&c->office.offers[i];
      if(ml_offer_live(old))return "A NEGOTIATION IS ALREADY OPEN";
      if(!old->incoming && old->status==ML_OFFER_REJECTED && old->season==c->season &&
          old->created/184u==c->day/184u)return "NEGOTIATION CLOSED UNTIL THE NEXT WINDOW";
    }
  const uint32_t to=o ? o->to : c->settings.club;
  const MlClub *buyer=ml_find_club(c,to);
  if(!buyer || buyer->cash<fee)return "INSUFFICIENT TRANSFER BUDGET";
  if(buyer->count>=ML_SQUAD_SIZE)return "DESTINATION SQUAD IS FULL";
  if((uint64_t)ml_weekly_wage(c,to)+wage>buyer->wage_budget)return "WAGE BUDGET EXCEEDED";
  if(!o) {
    o=ml_offer_allocate(c);if(!o)return "NEGOTIATION INBOX FULL";
    o->player=player;o->from=p->club;o->to=to;o->season=c->season;o->created=c->day;
  }
  uint32_t roll=c->seed ^ o->id*2654435761u ^ o->rounds*97u ^ c->day;
  o->due=c->day+1u+ml_random(&roll)%3u;
  if(o->due>ml_window_end(c))o->due=ml_window_end(c);
  o->fee=fee;o->wage=wage;o->years=years;o->rounds++;o->updated=c->day;o->status=ML_OFFER_WAITING;
  c->transaction_sequence++;return "";
}
const char *ml_offer_accept(MasterLeague *c,uint32_t id) {
  if(!c || c->office.dismissed)return "MANAGER DISMISSED";
  MlOffer *o=ml_offer_find(c,id);
  if(!o || (o->status!=ML_OFFER_ACCEPTED && o->status!=ML_OFFER_COUNTER))return "TERMS ARE NOT AVAILABLE";
  if(o->season!=c->season || c->players[o->player].club!=o->from)return "PLAYER OWNERSHIP HAS CHANGED";
  const char *error=ml_transfer_terms(c,o->player,o->to,o->years,o->fee,o->wage);
  if(*error)return error;
  o->status=ML_OFFER_COMPLETED;o->updated=c->day;
  for(uint32_t i=0;i<c->office.offer_count;i++) {
    MlOffer *other=&c->office.offers[i];
    if(other!=o && other->player==o->player && ml_offer_live(other))other->status=ML_OFFER_CANCELLED;
  }
  char line[96];snprintf(line,sizeof(line),"Transfer completed: %.47s",c->players[o->player].name);
  ml_notice(c,ML_NOTICE_TRANSFER,line);return "";
}
const char *ml_offer_reject(MasterLeague *c,uint32_t id) {
  if(!c || c->office.dismissed)return "MANAGER DISMISSED";
  MlOffer *o=ml_offer_find(c,id);if(!o || !ml_offer_live(o))return "OFFER ALREADY CLOSED";
  o->status=ML_OFFER_CANCELLED;o->updated=c->day;c->transaction_sequence++;return "";
}
uint32_t ml_release_value(const MasterLeague *c,uint32_t index) {
  if(!c || index>=c->player_count || c->players[index].club!=c->settings.club ||
      (c->players[index].reserved&ML_PLAYER_RELEASE_PAID))return 0u;
  /* Fictional release compensation, paid at most once per player identity.
   * Re-signing a free agent must not create an infinite release/cash loop. */
  return ml_transfer_value(&c->players[index])/4u;
}
const char *ml_release(MasterLeague *c,uint32_t index) {
  if(!c || index>=c->player_count || c->office.dismissed ||
      c->players[index].club!=c->settings.club)return "ONLY YOUR OWN PLAYER CAN BE RELEASED";
  MlPlayer *p=&c->players[index];MlClub *club=ml_club(c,p->club);
  if(!club || club->count<=18u)return "KEEP AT LEAST 18 PLAYERS";
  uint32_t slot=0u;while(slot<club->count && club->players[slot]!=index)slot++;
  if(slot==club->count)return "ROSTER IDENTITY MISMATCH";
  if(!ml_has_keeper(c,club,index))return "CANNOT RELEASE THE LAST GOALKEEPER";
  if(slot<11u) {
    int replacement=0;
    for(uint32_t i=11u;i<club->count;i++)replacement|=(c->players[club->players[i]].position==0u)==(p->position==0u);
    if(!replacement)return "NO SUITABLE STARTER REPLACEMENT";
  }
  const uint32_t value=ml_release_value(c,index);
  if(club->cash>INT64_C(1000000000000)-(int64_t)value)return "TRANSFER BALANCE LIMIT";
  /* All validation above is read-only. These writes commit the release once. */
  ml_remove_member(c,club,slot);club->cash+=value;
  p->club=p->wage=p->contract_end=0u;p->reserved|=ML_PLAYER_RELEASE_PAID;
  memset(&c->current_plan,0,sizeof(c->current_plan));
  for(uint32_t i=0;i<c->office.offer_count;i++) {
    MlOffer *o=&c->office.offers[i];
    if(o->player==index && ml_offer_live(o)){o->status=ML_OFFER_CANCELLED;o->updated=c->day;}
  }
  if(club->cash>=0)c->office.negative_since=0u;
  c->transaction_sequence++;
  char line[96];snprintf(line,sizeof(line),"Released to free agency: %.47s",p->name);ml_notice(c,ML_NOTICE_TRANSFER,line);
  return "";
}
static void ml_offer_resolve(MasterLeague *c,MlOffer *o) {
  const MlPlayer *p=&c->players[o->player];
  uint32_t fee=ml_transfer_fee(c,p),wage=ml_wage_for(p);
  o->updated=c->day;
  if(p->club!=o->from){o->status=ML_OFFER_CANCELLED;return;}
  /* The interest roll is stable for this player/club/window, not offer ID.
   * Reloading or resubmitting cannot reroll a star's willingness to leave. */
  int unwilling=0;
  if(!o->incoming && c->options.transfer_difficulty!=1u) {
    const uint32_t elite=p->overall>84u ? p->overall-84u : 0u;
    const int step_down=(int)ml_strength(c,o->from)-(int)ml_strength(c,o->to);
    const MlClub *seller=ml_find_club(c,o->from);
    uint32_t starter=0u;
    if(seller)for(uint32_t i=0;i<11u && i<seller->count;i++)starter|=seller->players[i]==o->player;
    const uint32_t remaining=p->contract_end>c->season ? p->contract_end-c->season : 0u;
    const uint32_t premium=elite*6u+(elite && starter ? 20u : 0u)+(elite && remaining>1u ? 15u : 0u);
    fee=(uint32_t)((uint64_t)fee*(100u+premium)/100u);
    wage=(uint32_t)((uint64_t)wage*(100u+elite*3u+(step_down>4 ? 15u : 0u))/100u);
    uint32_t roll=c->seed^p->identity*2654435761u^o->to*97u^c->season*193u^(o->created/184u);
    const uint32_t resistance=elite*3u+(elite && step_down>4 ? 18u : 0u)+
        (c->options.transfer_difficulty==2u ? 15u : 0u);
    unwilling=elite && ml_random(&roll)%100u<(resistance>80u ? 80u : resistance);
  }
  int acceptable=o->incoming ? o->fee<=(uint64_t)fee*110u/100u : o->fee>=fee;
  if(unwilling)o->status=ML_OFFER_REJECTED;
  else if(acceptable && o->wage>=wage)o->status=ML_OFFER_ACCEPTED;
  else if(o->rounds>=3u || (!o->incoming && (uint64_t)o->fee*100u<(uint64_t)ml_transfer_fee(c,p)*60u) ||
          (o->incoming && o->fee>(uint64_t)fee*150u/100u))o->status=ML_OFFER_REJECTED;
  else {o->status=ML_OFFER_COUNTER;o->fee=fee;o->wage=wage;}
  char line[96];snprintf(line,sizeof(line),"%.47s: %s",p->name,o->status==ML_OFFER_ACCEPTED ? "terms accepted" :
      o->status==ML_OFFER_COUNTER ? "counteroffer received" : "offer rejected");
  ml_notice(c,ML_NOTICE_RESPONSE,line);
}
static void ml_incoming_offer(MasterLeague *c) {
  const MlClub *own=ml_find_club(c,c->settings.club);
  if(!own || own->count<=18u)return;
  uint32_t roll=c->seed ^ c->day ^ c->season*173u;
  const uint32_t start=ml_random(&roll)%own->count;
  for(uint32_t k=0;k<own->count;k++) {
    const uint32_t index=own->players[(start+k)%own->count];const MlPlayer *p=&c->players[index];
    if(p->position==0u)continue;
    int active=0;for(uint32_t i=0;i<c->office.offer_count;i++)active|=c->office.offers[i].player==index && ml_offer_live(&c->office.offers[i]);
    if(active)continue;
    for(uint32_t j=0;j<c->club_count;j++) {
      const MlClub *buyer=&c->clubs[(j+start)%c->club_count];
      const uint32_t fee=ml_transfer_fee(c,p),wage=ml_wage_for(p);
      if(buyer->team==own->team || buyer->count>=ML_SQUAD_SIZE || buyer->cash<fee ||
         (uint64_t)ml_weekly_wage(c,buyer->team)+wage>buyer->wage_budget)continue;
      MlOffer *o=ml_offer_allocate(c);if(!o)return;
      o->player=index;o->from=own->team;o->to=buyer->team;o->season=c->season;
      o->created=o->due=o->updated=c->day;o->status=ML_OFFER_ACCEPTED;
      o->fee=fee;o->wage=wage;o->years=3u;o->incoming=1u;
      ml_notice(c,ML_NOTICE_RESPONSE,"A club has submitted terms for one of your players. Review My Teams.");return;
    }
  }
}
static int ml_milestone_enabled(const MasterLeague *c,uint32_t i) {
  return !(i<3u && c->season==1u && c->options.skip_first_window);
}
static void ml_office_schedule(const MasterLeague *c,MlEvent *event) {
  for(uint32_t i=0;i<6u;i++)if(ml_milestone_enabled(c,i) && !(c->office.milestone_mask&(1u<<i)) &&
      ml_window_days[i]>=c->day && ml_window_days[i]<=event->day)
    *event=(MlEvent){ML_EVENT_WINDOW,ml_window_days[i],i,0u,0u,0u};
  /* Incoming response wins a tie with a deadline so terms can be reviewed. */
  for(uint32_t i=0;i<c->office.offer_count;i++) {
    const MlOffer *o=&c->office.offers[i];
    if(o->status==ML_OFFER_WAITING && o->due>=c->day && o->due<=event->day)
      *event=(MlEvent){ML_EVENT_RESPONSE,o->due,o->id,0u,0u,0u};
  }
  if(!c->world.version && !c->office.job_checked && c->day<=183u && event->day>183u)
    *event=(MlEvent){ML_EVENT_BOARD,183u,0u,0u,0u,0u};
  ml_world_office_schedule(c,event);
  const MlClub *club=ml_find_club(c,c->settings.club);
  if(club && club->cash<0) {
    uint32_t due=c->office.negative_since ? c->office.negative_since-1u+14u : c->day;
    if(due<c->day)due=c->day;
    if(due<=event->day)*event=(MlEvent){ML_EVENT_BOARD,due,1u,0u,0u,0u};
  }
}
static void ml_board_result(MasterLeague *c,uint32_t h,uint32_t a,uint32_t hg,uint32_t ag) {
  if(h!=c->settings.club && a!=c->settings.club)return;
  if(c->day<183u)return; /* Consecutive losses count from mid-season. */
  if((h==c->settings.club && hg<ag) || (a==c->settings.club && ag<hg))c->office.losses++;
  else c->office.losses=0u;
  if(c->office.losses==3u)ml_notice(c,ML_NOTICE_WARNING,"President: results must improve. Six consecutive mid-season losses end your contract.");
}
static void ml_board_check(MasterLeague *c) {
  MlOfficeState *o=&c->office;const MlClub *club=ml_find_club(c,c->settings.club);
  if(o->dismissed || !club)return;
  if(club->cash>=0)o->negative_since=0u;
  else if(!o->negative_since) {
    o->negative_since=c->day+1u;
    ml_notice(c,ML_NOTICE_WARNING,"President: transfer balance is negative. Restore it within 14 days to keep your job.");
  }
  if(o->losses>=6u)o->dismissed=1u;
  if(o->negative_since && c->day>=o->negative_since-1u+14u)o->dismissed=2u;
  if(o->dismissed) {
    ml_notice(c,ML_NOTICE_DISMISSED,o->dismissed==1u ? "Contract terminated: six consecutive losses. Career over." :
      "Contract terminated: 14 days in negative balance. Career over.");return;
  }
  if(c->world.version) {ml_world_board_check(c);return;}
  if(c->day>=183u && !o->job_checked) {
    o->job_checked=1u;
    if(ml_rank(c)<=c->target_rank)for(uint32_t i=0;i<c->league.team_count;i++) {
      const uint32_t team=c->league.standings[i].team;
      if(team==c->settings.club || ml_find_club(c,team)->cash<0)continue;
      int eligible=!c->cup_enabled;
      for(uint32_t j=0;c->cup_enabled && j<cup_tournament_fixture_count(&c->cup,0u);j++)
        eligible|=c->cup.fixtures[0][j].home==team || c->cup.fixtures[0][j].away==team;
      if(!eligible)continue;
      o->job_team=team;o->job_expiry=c->day+14u;
      ml_notice(c,ML_NOTICE_JOB,"A club in your league has offered you the manager position. Reply within 14 days.");break;
    }
  }
}
const char *ml_accept_job(MasterLeague *c) {
  if(!c || c->office.dismissed || !c->office.job_team || c->day>c->office.job_expiry)return "JOB OFFER UNAVAILABLE";
  const uint32_t team=c->office.job_team;
  int eligible=0;
  for(uint32_t i=0;i<c->league.team_count;i++)eligible|=c->league.standings[i].team==team;
  if(!eligible || !ml_find_club(c,team))return "JOB OFFER UNAVAILABLE";
  if(c->cup_enabled) {
    eligible=0;for(uint32_t i=0;i<cup_tournament_fixture_count(&c->cup,0u);i++)
      eligible|=c->cup.fixtures[0][i].home==team || c->cup.fixtures[0][i].away==team;
    if(!eligible)return "JOB OFFER UNAVAILABLE";
  }
  c->settings.club=team;c->league.human_teams[0]=team;
  if(c->cup_enabled)c->cup.human_teams[0]=team;
  if(c->world.continental.team_count) {
    CupTournament *cup=&c->world.continental;cup->human_count=0u;cup->human_teams[0]=team;
    for(uint32_t i=0;i<cup_tournament_fixture_count(cup,0u);i++)
      cup->human_count|=cup->fixtures[0][i].home==team || cup->fixtures[0][i].away==team;
  }
  for(uint32_t i=0;i<c->office.offer_count;i++)if(ml_offer_live(&c->office.offers[i]))c->office.offers[i].status=ML_OFFER_CANCELLED;
  c->office.losses=c->office.negative_since=c->office.job_team=0u;
  memset(&c->current_plan,0,sizeof(c->current_plan));memset(c->presets,0,sizeof(c->presets));
  c->wages_paid=c->match_income=c->prize_income=0;
  uint32_t stronger=0u;for(uint32_t i=0;i<c->league.team_count;i++)stronger+=ml_strength(c,c->league.standings[i].team)>ml_strength(c,team);
  c->target_rank=stronger+3u<c->league.team_count ? stronger+3u : c->league.team_count;
  c->transaction_sequence++;ml_notice(c,ML_NOTICE_JOB,"Welcome to your new club. Existing fixtures and results are preserved.");return "";
}
int ml_process_office_event(MasterLeague *c,const MlEvent *event) {
  if(!event || event->kind<ML_EVENT_WINDOW || event->kind>ML_EVENT_BOARD || !ml_event_matches(c,event) || !ml_advance_date(c,event))return 0;
  if(event->kind==ML_EVENT_WINDOW) {
    c->office.milestone_mask|=1u<<event->index;
    ml_notice(c,ML_NOTICE_WINDOW,ml_event_label(c,event));
    if(event->index%3u!=2u)ml_incoming_offer(c);
  }
  if(event->kind==ML_EVENT_RESPONSE)for(uint32_t i=0;i<c->office.offer_count;i++)
    if(c->office.offers[i].status==ML_OFFER_WAITING && c->office.offers[i].due<=c->day)ml_offer_resolve(c,&c->office.offers[i]);
  for(uint32_t i=0;i<c->office.offer_count;i++)if(ml_offer_live(&c->office.offers[i]) && !ml_window_open(c))c->office.offers[i].status=ML_OFFER_EXPIRED;
  ml_board_check(c);c->transaction_sequence++;return 1;
}
const char *ml_event_label(const MasterLeague *c,const MlEvent *event) {
  if(!event)return "NEXT EVENT";
  if(event->kind>=ML_EVENT_CONTINENTAL)return ml_world_name(c,event->kind);
  if(event->kind==ML_EVENT_WINDOW)return event->index%3u==0u ? "TRANSFER WINDOW OPENS" : event->index%3u==1u ? "MID-WINDOW REVIEW" : "TRANSFER DEADLINE DAY";
  if(event->kind==ML_EVENT_RESPONSE)return "TRANSFER RESPONSE";
  if(event->kind==ML_EVENT_BOARD)return "PRESIDENT REVIEW";
  if(event->kind==ML_EVENT_SEASON_END)return "SEASON REVIEW";
  return event->home && event->away ? "NEXT MATCH" : "REST DAY";
}
uint32_t ml_calendar_transfer(const MasterLeague *c,uint32_t day) {
  uint32_t marker=0u;
  for(uint32_t i=0;i<6u;i++)if(ml_window_days[i]==day && ml_milestone_enabled(c,i))marker=i%3u+1u;
  for(uint32_t i=0;i<c->office.offer_count;i++) {
    const MlOffer *o=&c->office.offers[i];
    if(!marker && o->season==c->season && (o->due==day || o->updated==day))marker=4u;
  }
  return marker;
}
uint32_t ml_weak_position(const MasterLeague *c) {
  const MlClub *club=ml_find_club(c,c->settings.club);uint32_t role=0u,lowest=100u;
  if(club)for(uint32_t i=0;i<11u && i<club->count;i++) {
    const MlPlayer *p=&c->players[club->players[i]];
    if(p->overall<lowest){lowest=p->overall;role=p->position;}
  }
  return role;
}
static int ml_office_valid(const MasterLeague *c) {
  const MlOfficeState *s=&c->office;
  if(s->offer_count>ML_MAX_OFFERS || s->notice_count>ML_MAX_MESSAGES || s->milestone_mask>63u ||
     s->losses>1000u || s->negative_since>366u || s->dismissed>2u || s->job_checked>1u || s->job_expiry>365u)return 0;
  if(s->job_team) {
    int found=0;for(uint32_t i=0;i<c->league.team_count;i++)found|=c->league.standings[i].team==s->job_team;
    if(!found || s->job_team==c->settings.club)return 0;
  }
  for(uint32_t i=0;i<s->offer_count;i++) {
    const MlOffer *o=&s->offers[i];
    if(c->offer_seen[i] && ((c->offer_seen[i]>>8)>1000u ||
       !(c->offer_seen[i]&255u) || (c->offer_seen[i]&255u)>ML_OFFER_EXPIRED))return 0;
    if(!o->id || o->id>s->next_id || o->player>=c->player_count || o->incoming>1u ||
       !o->season || o->season>c->season || o->created>365u || o->due<o->created || o->due>365u ||
       o->updated>365u || o->rounds>1000u || o->status<ML_OFFER_WAITING || o->status>ML_OFFER_EXPIRED ||
       o->from==o->to || !ml_find_club(c,o->to) || (o->from && !ml_find_club(c,o->from)) ||
       !o->years || o->years>5u || !o->wage || o->wage>1000000u || o->fee>1000000000u)return 0;
    for(uint32_t j=0;j<i;j++)if(o->id==s->offers[j].id)return 0;
    if(ml_offer_live(o) && (o->season!=c->season || c->players[o->player].club!=o->from ||
       (o->incoming ? o->from!=c->settings.club : o->to!=c->settings.club)))return 0;
  }
  for(uint32_t i=0;i<s->notice_count;i++) {
    const MlNotice *n=&s->notices[i];
    if(n->kind<ML_NOTICE_WINDOW || n->kind>ML_NOTICE_TRANSFER || !n->season || n->season>c->season || n->day>365u || !memchr(n->text,0,sizeof(n->text)))return 0;
  }
  return 1;
}
