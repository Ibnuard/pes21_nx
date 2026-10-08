static uint32_t national_selected;
static int ml_national_offers_page(void) {
  return page==ML_PAGE_NATIONAL_OFFERS || (page==ML_PAGE_NATIONAL && !career.world.national_team);
}
static void ml_national_back(void) {
  if(page==ML_PAGE_NATIONAL_OFFERS && career.world.national_team) {
    ml_page(ML_PAGE_NATIONAL);focus=4u;
  }else {
    ml_page(national_parent);focus=national_parent_focus;
  }
}
static const char *ml_national_reply_label(uint32_t status) {
  return status==ML_OFFER_WAITING ? "AWAITING REPLY" : status==ML_OFFER_ACCEPTED ? "APPOINTMENT ACCEPTED" :
    status==ML_OFFER_REJECTED ? "OFFER DECLINED" : status==ML_OFFER_CANCELLED ? "WITHDRAWN - ROLE FILLED" : "OFFER EXPIRED";
}
static int ml_world_pad(uint32_t pressed) {
  if(drawer_kind==ML_DRAWER_NATIONAL_JOB) {
    if(pressed&ML_B){ml_drawer_close();return 1;}
    if(ml_national_offer_status(&career,national_selected)!=ML_OFFER_WAITING || career.office.dismissed)return 1;
    ml_scroll(pressed,2u,&drawer_focus,1u);
    if(pressed&ML_A) {
      const int accept=drawer_focus==0u;
      const char *error=accept ? ml_accept_national_job(&career,national_selected) : ml_reject_national_job(&career,national_selected);
      if(*error)ml_message(error);
      else {
        ml_drawer_close();if(accept)ml_page(ML_PAGE_NATIONAL);
        if(ml_autosave())ml_toast(accept ? "National appointment accepted" : "National offer declined");
      }
    }
    return 1;
  }
  if(drawer_kind)return 0;
  if(page==ML_PAGE_COMPETITIONS) {
    if(pressed&ML_B){ml_page(ML_PAGE_HUB);return 1;}
    ml_scroll(pressed,3u,&focus,1u);
    if(pressed&ML_A) {
      if(focus==2u){ml_page(ML_PAGE_NATIONAL);return 1;}
      cup_kind=focus ? ML_EVENT_CONTINENTAL : ML_EVENT_CUP;
      if(!ml_view_cup()->team_count){ml_toast("Competition available from the next eligible season");return 1;}
      cup_page=0u;ml_page(ML_PAGE_CUP);
    }
    return 1;
  }
  if(ml_national_offers_page()) {
    if(pressed&ML_B){ml_national_back();return 1;}
    ml_scroll(pressed,career.world.national_count,&focus,1u);
    if((pressed&ML_A) && focus<career.world.national_count) {
      national_selected=focus;
      const int unread=ml_national_offer_unread(&career,focus);
      if(unread)ml_national_offer_mark_read(&career,focus);
      ml_drawer_open(ML_DRAWER_NATIONAL_JOB,0u);
      if(unread)ml_autosave();
    }
    return 1;
  }
  if(page==ML_PAGE_NATIONAL) {
    if(pressed&ML_B){ml_national_back();return 1;}
    ml_scroll(pressed,5u,&focus,1u);
    if(pressed&ML_A) {
      if(focus==4u)ml_page(ML_PAGE_NATIONAL_OFFERS);
      else if(focus==0u)ml_page(ML_PAGE_INTERNATIONAL_SCHEDULE);
      else if(focus==1u)ml_page(ML_PAGE_QUALIFIERS);
      else {
        cup_kind=focus==2u ? ML_EVENT_REGIONAL : ML_EVENT_WORLD_CUP;
        if(ml_view_cup()->team_count){cup_page=0u;ml_page(ML_PAGE_CUP);}
        else ml_toast(career.world.finals_started ? "World Cup qualification was not achieved" : "Finish qualifiers to earn a World Cup place");
      }
    }
    return 1;
  }
  if(page==ML_PAGE_QUALIFIERS || page==ML_PAGE_INTERNATIONAL_SCHEDULE) {
    if(pressed&ML_B)ml_page(ML_PAGE_NATIONAL);
    return 1;
  }
  return 0;
}
static void ml_world_calendar(MlView *v) {
  uint32_t y,m,d;ml_calendar_date(calendar_day,&y,&m,&d);
  const uint32_t first=calendar_day-d+1u;
  for(uint32_t i=0;i<42u;i++) {
    MlCalendarCell *cell=&v->calendar[i];if(!cell->day)continue;
    const uint32_t day=first+cell->day-1u;
    uint32_t home=0u,away=0u,hg=0u,ag=0u,done=0u,kind=0u;
    for(uint32_t k=ML_EVENT_CONTINENTAL;k<=ML_EVENT_WORLD_CUP;k++) {
      const CupTournament *cup=ml_event_cup(&career,k);
      const uint32_t team=ml_event_manager_team(&career,k);
      if(!cup || !team)continue;
      for(uint32_t r=0;r<cup->round_count;r++)if(ml_world_day(&career,k,r)==day)
        for(uint32_t j=0;j<cup_tournament_fixture_count(cup,r);j++) {
          const CupFixture *f=&cup->fixtures[r][j];
          if(f->home==team || f->away==team){home=f->home;away=f->away;hg=f->home_goals;ag=f->away_goals;done=f->complete;kind=k;}
        }
    }
    if(career.world.national_team) {
      const LeagueTournament *q=&career.world.qualifiers;
      for(uint32_t r=0;r<q->matchday_count;r++)if(ml_world_day(&career,ML_EVENT_QUALIFIER,r)==day)
        for(uint32_t j=0;j<q->matchday_fixture_count[r];j++) {
          const LeagueFixture *f=&q->fixtures[q->matchday_first[r]+j];
          if(f->home==career.world.national_team || f->away==career.world.national_team)
            {home=f->home;away=f->away;hg=f->home_goals;ag=f->away_goals;done=f->complete;kind=ML_EVENT_QUALIFIER;}
        }
      for(uint32_t j=0;j<2u;j++)if(ml_world_day(&career,ML_EVENT_FRIENDLY,j)==day) {
        const LeagueFixture *f=&career.world.friendlies[j];home=f->home;away=f->away;hg=f->home_goals;ag=f->away_goals;done=f->complete;kind=ML_EVENT_FRIENDLY;
      }
    }
    if(!kind || !home || !away)continue;
    const int own_home=home==ml_event_manager_team(&career,kind);const uint32_t other=own_home ? away : home;
    cell->kind=kind;cell->badge=exhibition_team_catalog_badge(other);
    snprintf(cell->label,16,"%.15s",exhibition_team_catalog_name(other));
    if(done)snprintf(cell->detail,24,"%s %u-%u",own_home ? "H" : "A",own_home ? hg : ag,own_home ? ag : hg);
    else snprintf(cell->detail,24,"%s / %s",own_home ? "HOME" : "AWAY",ml_event_is_national(kind) ? "INTL" : "CUP");
    if(cell->selected)snprintf(v->calendar_detail,112,"%s / %.42s / %s",ml_world_name(&career,kind),exhibition_team_catalog_name(other),cell->detail);
  }
}
static void ml_world_view(MlView *v) {
  if(!session_ready)return;
  int national_context=page==ML_PAGE_NATIONAL || page==ML_PAGE_NATIONAL_OFFERS || page==ML_PAGE_QUALIFIERS || page==ML_PAGE_INTERNATIONAL_SCHEDULE ||
      (page==ML_PAGE_CUP && ml_event_is_national(cup_kind));
  if(page==ML_PAGE_HUB && hub_section==0u) {
    MlEvent next;
    if(ml_next_event(&career,&next) && ml_event_is_national(next.kind))national_context=1;
  }
  if((page==ML_PAGE_NEXT || page==ML_PAGE_ADVANCE) && ml_event_is_national(pending.kind))national_context=1;
  const uint32_t header_team=national_context ? career.world.national_team : career.settings.club;
  v->badge=header_team ? exhibition_team_catalog_badge(header_team) : 0u;
  snprintf(v->caption,96,"%s / SEASON %u / DAY %u",header_team ? exhibition_team_catalog_name(header_team) : "FEDERATION INVITATIONS",
    career.season,(page==ML_PAGE_ADVANCE ? calendar_day : career.day)+1u);
  if(national_context) {
    v->annual_budget[0]=v->transfer_budget[0]=0;
  }
  if(page==ML_PAGE_CALENDAR || page==ML_PAGE_ADVANCE)ml_world_calendar(v);
  if(page==ML_PAGE_HUB && hub_section==3u) {
    snprintf(v->rows[2].label,64,"CUP COMPETITIONS");
    snprintf(v->rows[2].detail,96,"Domestic, continental and international competitions");
  }
  if(page==ML_PAGE_CUP && !ml_view_cup()->team_count) {
    v->count=v->total=0u;snprintf(v->empty,96,"Competition Starts Next Eligible Season");
  }
  if(page==ML_PAGE_COMPETITIONS || page==ML_PAGE_NATIONAL || page==ML_PAGE_NATIONAL_OFFERS || page==ML_PAGE_INTERNATIONAL_SCHEDULE || page==ML_PAGE_QUALIFIERS) {
    memset(v->rows,0,sizeof(v->rows));memset(v->info,0,sizeof(v->info));v->count=v->total=0u;
    v->first=0u;v->selected=focus;v->action_count=0u;v->helper_count=2u;
    v->helper_key[0]="A";v->helper_key[1]="B";v->helper_label[0]="SELECT";v->helper_label[1]="BACK";
    snprintf(v->title,64,"%s",page==ML_PAGE_COMPETITIONS ? "CUP COMPETITIONS" : page==ML_PAGE_QUALIFIERS ? "WORLD CUP QUALIFIERS" :
      ml_national_offers_page() ? "NATIONAL OFFERS" : "NATIONAL TEAM");
    snprintf(v->left_title,64,"%s",page==ML_PAGE_QUALIFIERS ? "QUALIFYING GROUP / TOP 2 ADVANCE" : v->title);
    if(page==ML_PAGE_COMPETITIONS) {
      v->count=v->total=3u;
      for(uint32_t i=0;i<3u;i++) {
        MlViewRow *r=&v->rows[i];r->enabled=1;r->emblem=i==2u ? 2u : 1u;
        snprintf(r->label,64,"%s",i==0u ? ml_cup_name() : i==1u ? ml_world_name(&career,ML_EVENT_CONTINENTAL) : "INTERNATIONAL MANAGEMENT");
        snprintf(r->detail,96,"%s",i==0u ? (career.cup_enabled ? "Domestic knockout bracket" : "No supported domestic pool") :
          i==1u ? (career.world.continental.human_count ? "Qualified / compact career knockout format" : "Top 4 qualify / compact career format") : "Club and country on one calendar");
      }
    }else if(ml_national_offers_page()) {
      v->count=v->total=career.world.national_count;
      for(uint32_t i=0;i<v->count;i++) {
        const MlNationalOffer *o=&career.world.national_offers[i];MlViewRow *r=&v->rows[i];
        const uint32_t status=ml_national_offer_status(&career,i);
        r->enabled=1;r->unread=ml_national_offer_unread(&career,i);
        r->badge=exhibition_team_catalog_badge(o->team);
        snprintf(r->label,64,"%s",exhibition_team_catalog_name(o->team));
        snprintf(r->detail,96,"%s / REPLY BY DAY %u",ml_national_reply_label(status),o->expiry+1u);
      }
      if(!v->count)snprintf(v->empty,96,"No National Offers Yet");
    }else if(page==ML_PAGE_NATIONAL) {
        snprintf(v->left_title,64,"%s",exhibition_team_catalog_name(career.world.national_team));
        const char *labels[]={"INTERNATIONAL FRIENDLIES","WORLD CUP QUALIFIERS",ml_world_name(&career,ML_EVENT_REGIONAL),"WORLD CUP FINALS","FEDERATION OFFERS"};
        const char *details[]={"National roster / no transfer or wage budget","Four-team group / six matches / top two advance","Regional knockout tournament","Eight-team career finals after qualification","Review your appointment decisions"};
        v->count=v->total=5u;
        for(uint32_t i=0;i<5u;i++) {
          MlViewRow *r=&v->rows[i];r->enabled=1;r->emblem=i<2u ? 2u : 1u;
          snprintf(r->label,64,"%s",labels[i]);snprintf(r->detail,96,"%s",details[i]);
        }
        v->rows[4].emblem=3u;
    }else if(page==ML_PAGE_QUALIFIERS) {
      const LeagueTournament *q=&career.world.qualifiers;uint8_t ranked[LEAGUE_MAX_TEAMS];league_tournament_ranked_slots(q,ranked);
      int8_t changes[LEAGUE_MAX_TEAMS];league_tournament_rank_changes(q,changes);
      v->total=q->team_count;
      for(uint32_t i=0;i<q->team_count;i++) {
        MlTableRow *r=&v->table[v->table_count++];r->stats=q->standings[ranked[i]];r->rank=i+1u;
        r->rank_change=changes[ranked[i]];
        r->badge=exhibition_team_catalog_badge(r->stats.team);r->own=r->stats.team==career.world.national_team;
        snprintf(r->name,64,"%s",exhibition_team_catalog_name(r->stats.team));
      }
    }else {
      v->count=v->total=2u;
      for(uint32_t i=0;i<2u;i++) {
        const LeagueFixture *f=&career.world.friendlies[i];MlViewRow *r=&v->rows[i];r->enabled=1;
        const uint32_t other=f->home==career.world.national_team ? f->away : f->home;
        r->badge=exhibition_team_catalog_badge(other);snprintf(r->label,64,"%s",exhibition_team_catalog_name(other));
        snprintf(r->detail,96,"DAY %u / %s / FRIENDLY",ml_world_day(&career,ML_EVENT_FRIENDLY,i)+1u,f->home==career.world.national_team ? "HOME" : "AWAY");
        if(f->complete)snprintf(r->value,48,"%u - %u",f->home_goals,f->away_goals);
        else snprintf(r->value,48,"UPCOMING");
      }
    }
  }
  if(page==ML_PAGE_JOBS)for(uint32_t i=0;i<v->count;i++)v->rows[i].emblem=3u;
  if(page==ML_PAGE_MANAGER_OFFICE && v->count==3u)
    for(uint32_t i=0;i<career.world.national_count;i++)v->rows[2].unread+=ml_national_offer_unread(&career,i);
  if(drawer_kind==ML_DRAWER_NATIONAL_JOB) {
    MlDrawerView *d=&v->drawer;memset(d,0,sizeof(*d));d->open=1;d->serial=drawer_serial;d->modal=2;d->confirm=2;
    const MlNationalOffer *o=&career.world.national_offers[national_selected];
    const uint32_t status=ml_national_offer_status(&career,national_selected);
    d->badge=exhibition_team_catalog_badge(o->team);
    snprintf(d->title,64,"%s",status==ML_OFFER_WAITING ? "NATIONAL APPOINTMENT" : ml_national_reply_label(status));
    snprintf(d->subtitle,96,"%s",exhibition_team_catalog_name(o->team));
    snprintf(d->detail,96,"YOUR CLUB CAREER CONTINUES");
    snprintf(d->body,256,"One club + one country. No national transfers or wages. Accept closes other offers; Decline keeps them open. Fictional career calendar.");
    if(status==ML_OFFER_WAITING && !career.office.dismissed) {
      d->count=d->total=2u;d->selected=drawer_focus;
      for(uint32_t i=0;i<2u;i++){d->rows[i].enabled=1;snprintf(d->rows[i].label,64,"%s",i ? "DECLINE OFFER" : "ACCEPT NATIONAL ROLE");}
    }
  }
}
