/* Projection/input for asynchronous transfers, board mail and competition views. */
static uint32_t market_groups[EXHIBITION_TEAM_CATEGORY_COUNT],market_group_count;
static uint32_t market_teams[ML_MAX_CLUBS],market_team_count,market_group;
static uint32_t offer_indices[ML_MAX_OFFERS],offer_rows,offers_incoming;
static uint32_t current_offer,offer_fee,offer_wage,cup_page;
static uint32_t ml_term_rate(void) {
  return career.options.currency==1u ? 85u : career.options.currency==2u ? 110u : 100u;
}
static void ml_term_money(char *out,size_t size,uint32_t amount,int wage) {
  const uint32_t quantum=wage ? 100u : 100000u;
  const uint32_t tenths=(uint32_t)(((uint64_t)amount*ml_term_rate()+quantum*50u)/(quantum*100u));
  snprintf(out,size,"%s %u.%u %s",ml_currencies[career.options.currency],tenths/10u,tenths%10u,wage ? "K" : "M");
}
static uint32_t ml_term_round(uint32_t amount,uint32_t quantum,uint32_t limit) {
  /* Round a NEW draft quote up to the displayed precision. Existing cash and
   * contracts never change when switching currency or opening this popup. */
  const uint32_t rate=ml_term_rate();
  uint64_t shown=((uint64_t)amount*rate+99u)/100u;
  shown=(shown+quantum-1u)/quantum*quantum;
  const uint64_t value=(shown*100u+rate-1u)/rate;
  return (uint32_t)(value>limit ? limit : value);
}
static void ml_term_step(uint32_t *amount,int plus,int wage) {
  const uint32_t rate=ml_term_rate(),quantum=wage ? 100u : 100000u;
  const uint32_t step=wage ? 1000u : 100000u,minimum=wage ? 1000u : 0u,maximum=wage ? 1000000u : 1000000000u;
  int64_t shown=(int64_t)(((uint64_t)*amount*rate+quantum*50u)/(quantum*100u))*quantum;
  shown+=plus ? (int64_t)step : -(int64_t)step;
  int64_t value=shown>0 ? (shown*100+rate-1u)/rate : 0;
  *amount=value<minimum ? minimum : value>maximum ? maximum : (uint32_t)value;
}
static const char *ml_offer_status(uint32_t status) {
  static const char *names[]={"","WAITING RESPONSE","TERMS ACCEPTED","COUNTEROFFER",
    "REJECTED","COMPLETED","CANCELLED","OFFER EXPIRED"};
  return status<8u ? names[status] : "UNAVAILABLE";
}
static void ml_offer_list(uint32_t incoming) {
  offer_rows=0u;offers_incoming=incoming;
  for(uint32_t i=career.office.offer_count;i>0u;i--)
    if(career.office.offers[i-1u].incoming==incoming)offer_indices[offer_rows++]=i-1u;
}
static MlOffer *ml_selected_offer(void) {
  for(uint32_t i=0;i<career.office.offer_count;i++)if(career.office.offers[i].id==current_offer)return &career.office.offers[i];
  return NULL;
}
static uint32_t ml_offer_action_count(const MlOffer *o) {
  if(!o || career.office.dismissed)return 0u;
  if(o->status==ML_OFFER_ACCEPTED || o->status==ML_OFFER_COUNTER)return 3u;
  if(o->status==ML_OFFER_WAITING)return 1u;
  if(o->incoming && o->status==ML_OFFER_EXPIRED && career.players[o->player].club==career.settings.club)return 1u;
  return 0u;
}
static void ml_offer_open(uint32_t index,uint32_t id) {
  if(!ml_window_open(&career)){ml_toast("Transfer window closed");return;}
  if(career.office.dismissed){ml_message("MANAGER DISMISSED");return;}
  if(!id && career.players[index].club==career.settings.club){ml_message("REVIEW BUYER OFFERS IN MY TEAMS");return;}
  current_offer=id;transaction_player=index;years=3u;
  const MlPlayer *p=&career.players[index];
  const uint32_t rating=p->overall>40u ? p->overall-40u : 1u;
  offer_fee=ml_transfer_fee(&career,p);offer_wage=1000u+rating*rating*15u;
  MlOffer *o=ml_selected_offer();if(o){years=o->years;offer_fee=o->fee;offer_wage=o->wage;}
  offer_fee=ml_term_round(offer_fee,100000u,1000000000u);
  offer_wage=ml_term_round(offer_wage,100u,1000000u);
  ml_drawer_open(ML_DRAWER_OFFER,0u);
}
static void ml_market_categories(void) {
  market_group_count=0u;
  for(uint32_t i=0;i<EXHIBITION_TEAM_CATEGORY_COUNT;i++) {
    const ExhibitionTeamCategory *cat=&exhibition_team_categories[i];
    int found=0;for(uint32_t j=0;j<cat->team_count;j++)found|=ml_find_club(&career,cat->teams[j])!=NULL;
    if(found)market_groups[market_group_count++]=i;
  }
}
static void ml_market_team_list(uint32_t index) {
  market_group=index;market_team_count=0u;
  const ExhibitionTeamCategory *cat=&exhibition_team_categories[market_groups[index]];
  for(uint32_t i=0;i<cat->team_count;i++)if(ml_find_club(&career,cat->teams[i]))market_teams[market_team_count++]=cat->teams[i];
}
static void ml_recommend_players(void) {
  const uint32_t role=ml_weak_position(&career);player_rows=0u;market_club=0u;
  /* A bounded ranked shortlist, exact weak starting role first. No invented
   * season statistics: this recommendation uses the registered XI strength. */
  for(uint32_t i=0;i<career.player_count;i++) {
    const MlPlayer *p=&career.players[i];
    if(p->club==career.settings.club || p->position!=role)continue;
    uint32_t at=0u;while(at<player_rows && career.players[row_players[at]].overall>=p->overall)at++;
    if(at>=30u)continue;
    if(player_rows<30u)player_rows++;
    for(uint32_t j=player_rows-1u;j>at;j--)row_players[j]=row_players[j-1u];
    row_players[at]=i;
  }
}
static void ml_scroll(uint32_t pressed,uint32_t count,uint32_t *position,uint32_t step) {
  if(!count){*position=0u;return;}
  if(pressed&(ML_UP|ML_L))*position=*position>=step ? *position-step : 0u;
  if(pressed&(ML_DOWN|ML_R))*position=*position+step<count ? *position+step : count-1u;
}
static int ml_office_pad(uint32_t pressed) {
  if(drawer_kind>=ML_DRAWER_MARKET_LEAGUE) {
    if(pressed&ML_B) {
      if(drawer_kind==ML_DRAWER_MARKET_TEAM)ml_drawer_open(ML_DRAWER_MARKET_LEAGUE,market_group);
      else ml_drawer_close();
      return 1;
    }
    uint32_t count=drawer_kind==ML_DRAWER_MARKET_LEAGUE ? market_group_count+1u :
      drawer_kind==ML_DRAWER_MARKET_TEAM ? market_team_count : drawer_kind==ML_DRAWER_OFFER ? 4u :
      drawer_kind==ML_DRAWER_OFFER_ACTIONS ? ml_offer_action_count(ml_selected_offer()) : drawer_kind==ML_DRAWER_MY_PLAYER ? 2u : 1u;
    ml_scroll(pressed,count,&drawer_focus,pressed&(ML_L|ML_R) ? 5u : 1u);
    if(drawer_focus<drawer_first)drawer_first=drawer_focus;
    if(drawer_focus>=drawer_first+5u)drawer_first=drawer_focus-4u;
    if(drawer_kind==ML_DRAWER_OFFER && (pressed&(ML_LEFT|ML_RIGHT))) {
      const int plus=(pressed&ML_RIGHT)!=0u;
      if(drawer_focus==0u)years=plus ? (years<5u ? years+1u : 1u) : (years>1u ? years-1u : 5u);
      else if(drawer_focus==1u)ml_term_step(&offer_wage,plus,1);
      else if(drawer_focus==2u)ml_term_step(&offer_fee,plus,0);
    }
    if(!(pressed&ML_A))return 1;
    if(drawer_kind==ML_DRAWER_MARKET_LEAGUE) {
      if(drawer_focus==market_group_count){market_club=0u;ml_refresh_players(0u);ml_drawer_close();ml_page(ML_PAGE_MARKET_PLAYERS);}
      else {ml_market_team_list(drawer_focus);ml_drawer_open(ML_DRAWER_MARKET_TEAM,0u);}
    } else if(drawer_kind==ML_DRAWER_MARKET_TEAM && count) {
      market_club=market_teams[drawer_focus];ml_refresh_players(market_club);ml_drawer_close();ml_page(ML_PAGE_MARKET_PLAYERS);
    } else if(drawer_kind==ML_DRAWER_OFFER && drawer_focus<3u) {
      drawer_focus++;
    } else if(drawer_kind==ML_DRAWER_OFFER && drawer_focus==3u) {
      const char *error=ml_offer_submit(&career,transaction_player,offer_fee,offer_wage,years,current_offer);
      if(*error)ml_message(error);
      else {ml_drawer_close();ml_offer_list(offers_incoming);if(ml_autosave())ml_toast("Offer sent - waiting for response");}
    } else if(drawer_kind==ML_DRAWER_OFFER_ACTIONS) {
      MlOffer *o=ml_selected_offer();if(!o)return 1;
      if(!count)return 1;
      if(o->status==ML_OFFER_EXPIRED){ml_renew_open(o->player);return 1;}
      if(drawer_focus==2u) {
        if(o->status==ML_OFFER_ACCEPTED || o->status==ML_OFFER_COUNTER)ml_offer_open(o->player,o->id);
        return 1;
      }
      const int accept=drawer_focus==0u && o->status!=ML_OFFER_WAITING;
      const char *error=accept ? ml_offer_accept(&career,o->id) : ml_offer_reject(&career,o->id);
      if(*error)ml_message(error);
      else {ml_drawer_close();ml_offer_list(offers_incoming);if(ml_autosave())ml_toast(accept ? "Transfer completed" : "Offer declined");}
    } else if(drawer_kind==ML_DRAWER_MY_PLAYER) {
      if(!drawer_focus)ml_renew_open(transaction_player);
      else {ml_drawer_close();ml_open_confirmation(6u);}
    } else if(drawer_kind==ML_DRAWER_JOB) {
      const char *error=ml_accept_job(&career);
      if(*error)ml_message(error);
      else {ml_drawer_close();ml_page(ML_PAGE_HUB);if(ml_autosave())ml_toast("Welcome to your new club");}
    }
    return 1;
  }
  if(drawer_kind)return 0;
  if(page==ML_PAGE_MARKET_CLUBS) {
    if(pressed&ML_B){ml_page(ML_PAGE_HUB);return 1;}
    ml_scroll(pressed,4u,&focus,1u);
    if(pressed&ML_A) {
      if(focus==0u)ml_page(ML_PAGE_MY_TEAM);
      else if(focus==1u){ml_offer_list(0u);ml_page(ML_PAGE_OFFERS);}
      else if(focus==2u){ml_recommend_players();ml_page(ML_PAGE_MARKET_PLAYERS);}
      else {ml_market_categories();ml_drawer_open(ML_DRAWER_MARKET_LEAGUE,0u);}
    }return 1;
  }
  if(page==ML_PAGE_MY_TEAM) {
    if(pressed&ML_B){ml_page(ML_PAGE_MARKET_CLUBS);return 1;}
    ml_scroll(pressed,2u,&focus,1u);
    if(pressed&ML_A) {
      if(!focus){ml_offer_list(1u);ml_page(ML_PAGE_OFFERS);}
      else {ml_refresh_players(career.settings.club);ml_page(ML_PAGE_MY_PLAYERS);}
    }return 1;
  }
  if(page==ML_PAGE_MY_PLAYERS) {
    if(pressed&ML_B){ml_page(ML_PAGE_MY_TEAM);focus=1u;return 1;}
    ml_scroll(pressed,player_rows,&focus,pressed&(ML_L|ML_R) ? 5u : 1u);
    if((pressed&ML_A) && focus<player_rows) {
      transaction_player=row_players[focus];ml_drawer_open(ML_DRAWER_MY_PLAYER,0u);
    }return 1;
  }
  if(page==ML_PAGE_OFFERS || page==ML_PAGE_MANAGER_OFFICE || page==ML_PAGE_MESSAGES || page==ML_PAGE_JOBS) {
    if(pressed&ML_B){ml_page(page==ML_PAGE_OFFERS ? (offers_incoming ? ML_PAGE_MY_TEAM : ML_PAGE_MARKET_CLUBS) : page==ML_PAGE_MANAGER_OFFICE ? ML_PAGE_HUB : ML_PAGE_MANAGER_OFFICE);return 1;}
    const uint32_t count=page==ML_PAGE_OFFERS ? offer_rows : page==ML_PAGE_MANAGER_OFFICE ? 3u :
      page==ML_PAGE_MESSAGES ? career.office.notice_count : career.office.job_team && career.day<=career.office.job_expiry ? 1u : 0u;
    ml_scroll(pressed,count,&focus,pressed&(ML_L|ML_R) ? 5u : 1u);
    if((pressed&ML_A) && count) {
      if(page==ML_PAGE_OFFERS){
        const uint32_t index=offer_indices[focus];
        current_offer=career.office.offers[index].id;ml_drawer_open(ML_DRAWER_OFFER_ACTIONS,0u);
        if(ml_offer_unread(&career,index)){ml_offer_mark_read(&career,index);ml_autosave();}
      }
      else if(page==ML_PAGE_MANAGER_OFFICE)ml_page(focus==2u ? ML_PAGE_NATIONAL : focus ? ML_PAGE_MESSAGES : ML_PAGE_JOBS);
      else if(page==ML_PAGE_MESSAGES)ml_drawer_open(ML_DRAWER_NOTICE,0u);
      else ml_drawer_open(ML_DRAWER_JOB,0u);
    }return 1;
  }
  if(page==ML_PAGE_NEXT && (career.office.dismissed || (pending.kind>=ML_EVENT_WINDOW && !ml_event_is_match(pending.kind)))) {
    if(pressed&ML_B){ml_page(ML_PAGE_HUB);return 1;}
    if((pressed&ML_A) && !career.office.dismissed) {
      const uint32_t from=career.day;
      if(ml_process_office_event(&career,&pending)) {
        const int response=pending.kind==ML_EVENT_RESPONSE;
        ml_begin_advance(from,response ? "Transfer response received" : "Calendar advanced");
      }else ml_message("EVENT CHANGED - RETURN TO THE HUB");
    }return 1;
  }
  if(page==ML_PAGE_TABLE && !table_scorers) {
    if(pressed&ML_B){ml_page(ML_PAGE_HUB);return 1;}
    if(pressed&ML_Y){table_scorers=1u;focus=0u;return 1;}
    ml_scroll(pressed,career.league.team_count,&focus,pressed&(ML_L|ML_R) ? 8u : 1u);return 1;
  }
  if(page==ML_PAGE_CUP) {
    const CupTournament *cup=ml_view_cup();
    if(pressed&ML_B){ml_page(ml_event_is_national(cup_kind) ? ML_PAGE_NATIONAL : ML_PAGE_COMPETITIONS);return 1;}
    if((pressed&(ML_LEFT|ML_L)) && focus){focus--;cup_page=0u;}
    if((pressed&(ML_RIGHT|ML_R)) && focus+1u<cup->round_count){focus++;cup_page=0u;}
    const uint32_t count=cup_tournament_fixture_count(cup,focus),pages=(count+3u)/4u;
    if((pressed&ML_UP) && cup_page)cup_page--;
    if((pressed&ML_DOWN) && cup_page+1u<pages)cup_page++;
    return 1;
  }
  return 0;
}
static void ml_player_row(MlViewRow *r,const MlPlayer *p) {
  r->rating=p->overall;r->role=p->position;r->portrait=p->portrait_id;
  snprintf(r->label,sizeof(r->label),"%s",p->name);
  snprintf(r->detail,sizeof(r->detail),"%s",ml_role(p->position));r->value[0]=0;r->enabled=1;
}
static void ml_office_drawer(MlView *v) {
  if(drawer_kind<ML_DRAWER_MARKET_LEAGUE)return;
  MlDrawerView *d=&v->drawer;memset(d,0,sizeof(*d));d->open=1;d->serial=drawer_serial;d->first=drawer_first;d->selected=drawer_focus;
  if(drawer_kind==ML_DRAWER_MARKET_LEAGUE || drawer_kind==ML_DRAWER_MARKET_TEAM) {
    d->total=drawer_kind==ML_DRAWER_MARKET_LEAGUE ? market_group_count+1u : market_team_count;
    snprintf(d->title,64,"SELECT %s",drawer_kind==ML_DRAWER_MARKET_LEAGUE ? "LEAGUE" : "TEAM");
    for(uint32_t i=0;i<5u && d->first+i<d->total;i++) {
      const uint32_t at=d->first+i;MlViewRow *r=&d->rows[d->count++];r->enabled=1;
      if(drawer_kind==ML_DRAWER_MARKET_TEAM) {
        snprintf(r->label,64,"%s",exhibition_team_catalog_name(market_teams[at]));r->badge=exhibition_team_catalog_badge(market_teams[at]);
      }else if(at==market_group_count)snprintf(r->label,64,"FREE AGENTS");
      else {const ExhibitionTeamCategory *cat=&exhibition_team_categories[market_groups[at]];
        snprintf(r->label,64,"%s",cat->label);r->badge=cat->badge_slot;
        for(uint32_t j=0;j<FL26_LEAGUE_CATALOG_COUNT;j++)if(fl26_league_catalog[j].category_index==market_groups[at]) {
          snprintf(r->label,64,"%s",fl26_league_catalog[j].name);r->league_logo=j+1u;break;
        }
      }
    }
  }else if(drawer_kind==ML_DRAWER_OFFER) {
    snprintf(d->title,64,"PROPOSE TERMS");snprintf(d->subtitle,96,"%s",career.players[transaction_player].name);
    d->count=3u;d->total=4u;d->first=0u;d->confirm=1;d->confirm_selected=drawer_focus==3u;
    d->modal=1;
    snprintf(d->confirm_label,32,"SEND OFFER");
    const char *labels[]={"CONTRACT","WEEKLY WAGE","TRANSFER FEE"};
    for(uint32_t i=0;i<3u;i++){snprintf(d->rows[i].label,64,"%s",labels[i]);d->rows[i].enabled=1;d->rows[i].adjustable=2;}
    snprintf(d->rows[0].value,48,"%u %s",years,years==1u ? "YEAR" : "YEARS");
    ml_term_money(d->rows[1].value,48,offer_wage,1);ml_term_money(d->rows[2].value,48,offer_fee,0);
  }else if(drawer_kind==ML_DRAWER_OFFER_ACTIONS) {
    MlOffer *o=ml_selected_offer();if(!o)return;
    snprintf(d->title,64,"%s",ml_offer_status(o->status));snprintf(d->subtitle,96,"%s",career.players[o->player].name);
    char fee[32],wage[32];ml_term_money(fee,sizeof(fee),o->fee,0);ml_term_money(wage,sizeof(wage),o->wage,1);
    snprintf(d->detail,96,"%u YEARS / WAGE %s",o->years,wage);snprintf(d->value,96,"FEE %s",fee);
    d->count=d->total=ml_offer_action_count(o);d->first=0u;d->confirm=2;d->modal=2;
    d->badge=exhibition_team_catalog_badge(o->incoming ? o->to : o->from);
    snprintf(d->body,sizeof(d->body),"%s",o->status==ML_OFFER_EXPIRED ? "Only this transfer offer expired. Your player's contract is separate." :
      o->status==ML_OFFER_COMPLETED ? "Transfer completed. The player has joined their new club." :
      o->status==ML_OFFER_REJECTED ? "The club rejected these terms. This negotiation is closed." :
      o->status==ML_OFFER_CANCELLED ? "This offer has been closed. No further action is required." :
      o->status==ML_OFFER_WAITING ? "Awaiting the other club's reply. Advance the calendar for an update." : "Review the agreed terms before completing the transfer.");
    const char *labels[]={"ACCEPT TERMS","REJECT TERMS","NEGOTIATE"};
    for(uint32_t i=0;i<d->count;i++){snprintf(d->rows[i].label,64,"%s",o->status==ML_OFFER_EXPIRED ? "RENEW PLAYER CONTRACT" : o->status==ML_OFFER_WAITING ? "CANCEL OFFER" : labels[i]);d->rows[i].enabled=1;}
  }else if(drawer_kind==ML_DRAWER_MY_PLAYER) {
    const MlPlayer *p=&career.players[transaction_player];char fee[32];ml_money(fee,sizeof(fee),ml_release_value(&career,transaction_player));
    snprintf(d->title,64,"PLAYER CONTRACT");snprintf(d->subtitle,96,"%s",p->name);d->badge=exhibition_team_catalog_badge(p->club);
    snprintf(d->detail,96,"%s / CONTRACT UNTIL SEASON %u",ml_role(p->position),p->contract_end);
    snprintf(d->value,96,"RELEASE COMPENSATION %s",fee);
    snprintf(d->body,sizeof(d->body),"%s",p->contract_end<=career.season ? "Contract expires this season. Renew to keep this player." :
      "Renew the player's contract or release them into the free-agent pool.");
    d->modal=2;d->confirm=2;d->count=d->total=2u;
    snprintf(d->rows[0].label,64,"RENEW CONTRACT");snprintf(d->rows[1].label,64,"RELEASE PLAYER");
    d->rows[0].enabled=d->rows[1].enabled=!career.office.dismissed;
  }else {
    snprintf(d->title,64,"%s",drawer_kind==ML_DRAWER_NOTICE ? "PRESIDENT MESSAGE" : "MANAGER CONTRACT");
    if(drawer_kind==ML_DRAWER_NOTICE) {
      const MlNotice *n=&career.office.notices[career.office.notice_count-1u-focus];
      snprintf(d->body,sizeof(d->body),"%s",n->text);
    }else {
      snprintf(d->body,sizeof(d->body),"Join %s? Your current club and its budgets stay behind. Fixtures and results remain unchanged.",exhibition_team_catalog_name(career.office.job_team));
      d->modal=2;d->confirm=2;d->count=d->total=1u;d->rows[0].enabled=1;
      d->badge=exhibition_team_catalog_badge(career.office.job_team);
      snprintf(d->subtitle,96,"%s",exhibition_team_catalog_name(career.office.job_team));
      snprintf(d->detail,96,"FRESH SQUAD, BUDGET AND BOARD TARGET");
      snprintf(d->rows[0].label,64,"ACCEPT JOB");
    }
  }
  v->helper_count=2u;v->helper_key[0]="A";v->helper_key[1]="B";v->helper_label[0]="CONFIRM";v->helper_label[1]="CLOSE";
  if(drawer_kind==ML_DRAWER_OFFER)v->helper_label[0]=drawer_focus==3u ? "SEND OFFER" : "NEXT FIELD";
  if(drawer_kind==ML_DRAWER_OFFER_ACTIONS && !d->count) {
    v->helper_count=1u;v->helper_key[0]="B";v->helper_label[0]="CLOSE";
  }
  if(drawer_kind==ML_DRAWER_MARKET_TEAM || drawer_kind==ML_DRAWER_MARKET_LEAGUE) {
    v->helper_count=4u;v->helper_key[2]="L";v->helper_label[2]="PREV PAGE";v->helper_key[3]="R";v->helper_label[3]="NEXT PAGE";
  }
}
static const char *ml_round_title(uint32_t r) {
  const uint32_t remaining=ml_view_cup()->round_count-r;
  return remaining==1u ? "FINAL" : remaining==2u ? "SEMI FINAL" : remaining==3u ? "QUARTER FINAL" : remaining==4u ? "ROUND OF 16" : "ROUND OF 32";
}
static void ml_office_view(MlView *v) {
  uint32_t incoming_unread=0u,outgoing_unread=0u;
  if(session_ready)for(uint32_t i=0;i<career.office.offer_count;i++)if(ml_offer_unread(&career,i)) {
    if(career.office.offers[i].incoming)incoming_unread++;else outgoing_unread++;
  }
  v->transfer_unread=incoming_unread+outgoing_unread;
  if(page==ML_PAGE_HUB && hub_section==2u)v->rows[0].unread=v->transfer_unread;
  if(page==ML_PAGE_HUB && hub_section==1u)v->rows[2].unread=v->transfer_unread;
  v->toast_serial=toast_serial;snprintf(v->toast,sizeof(v->toast),"%s",toast);
  if(page==ML_PAGE_MY_TEAM) {
    memset(v->rows,0,sizeof(v->rows));v->first=0u;v->count=v->total=2u;v->selected=focus;v->action_count=0u;
    snprintf(v->title,64,"MY TEAMS");snprintf(v->left_title,64,"SQUAD MANAGEMENT");
    snprintf(v->rows[0].label,64,"CLUB OFFERS");snprintf(v->rows[0].detail,96,"Review bids from other clubs");v->rows[0].unread=incoming_unread;
    snprintf(v->rows[1].label,64,"MY PLAYERS");snprintf(v->rows[1].detail,96,"Renew contracts or release players to free agency");
    v->rows[0].enabled=v->rows[1].enabled=1;v->helper_count=2u;
  }
  if(page==ML_PAGE_MY_PLAYERS) {
    memset(v->rows,0,sizeof(v->rows));v->first=focus/5u*5u;v->count=0u;v->total=player_rows;v->selected=focus;v->action_count=0u;
    snprintf(v->title,64,"MY PLAYERS");snprintf(v->left_title,64,"PLAYER CONTRACTS");
    for(uint32_t i=0;i<5u && v->first+i<player_rows;i++) {
      MlViewRow *r=&v->rows[v->count++];const MlPlayer *p=&career.players[row_players[v->first+i]];
      ml_player_row(r,p);
      if(p->contract_end<=career.season)snprintf(r->value,48,"EXPIRING / RENEW CONTRACT");
      else snprintf(r->value,48,"Contract until season %u",p->contract_end);
    }
    v->helper_count=4u;v->helper_key[0]="A";v->helper_label[0]="PLAYER OPTIONS";v->helper_key[1]="B";v->helper_label[1]="BACK";
    v->helper_key[2]="L";v->helper_label[2]="PREV PAGE";v->helper_key[3]="R";v->helper_label[3]="NEXT PAGE";
  }
  if(page==ML_PAGE_HUB && hub_section==0u) {
    MlEvent event={0};ml_next_event(&career,&event);
    if(event.kind>=ML_EVENT_WINDOW && !ml_event_is_match(event.kind)) {
      snprintf(v->rows[0].label,64,"NEXT EVENT");snprintf(v->rows[0].detail,96,"%s",ml_event_label(&career,&event));
    }
    if(career.office.dismissed){snprintf(v->rows[0].label,64,"CAREER OVER");snprintf(v->rows[0].detail,96,"Your manager contract has been terminated");}
  }
  if(page==ML_PAGE_TABLE && !table_scorers) {
    v->count=0u;v->first=focus/8u*8u;v->total=career.league.team_count;
    uint8_t order[LEAGUE_MAX_TEAMS];league_tournament_ranked_slots(&career.league,order);
    for(uint32_t i=0;i<8u && v->first+i<v->total;i++) {
      MlTableRow *r=&v->table[v->table_count++];r->stats=career.league.standings[order[v->first+i]];
      r->rank=v->first+i+1u;r->own=r->stats.team==career.settings.club;r->badge=exhibition_team_catalog_badge(r->stats.team);
      snprintf(r->name,sizeof(r->name),"%s",exhibition_team_catalog_name(r->stats.team));
    }
    v->helper_count=4u;v->helper_key[0]="L";v->helper_label[0]="PREV PAGE";
    v->helper_key[3]="R";v->helper_label[3]="NEXT PAGE";
  }else if(page==ML_PAGE_TABLE && table_scorers && !v->count)snprintf(v->empty,sizeof(v->empty),"No Matches Played Yet");
  if(page==ML_PAGE_CUP && ml_view_cup()->team_count) {
    const CupTournament *cup=ml_view_cup();
    snprintf(v->title,64,"%s",cup_kind==ML_EVENT_CUP ? ml_cup_name() : ml_world_name(&career,cup_kind));
    v->count=0u;v->bracket_round=focus;v->bracket_page=cup_page;
    v->bracket_pages=(cup_tournament_fixture_count(cup,focus)+3u)/4u;
    const uint32_t page_index=cup_page<v->bracket_pages ? cup_page : 0u;
    for(uint32_t col=0;col<3u && focus+col<cup->round_count;col++) {
      snprintf(v->bracket_titles[col],32,"%s",ml_round_title(focus+col));
      uint32_t start=(page_index*4u)>>col,limit=4u>>col;
      for(uint32_t i=0;i<limit && start+i<cup_tournament_fixture_count(cup,focus+col);i++) {
        const CupFixture *f=cup_tournament_fixture(cup,focus+col,start+i);
        MlBracketMatch *m=&v->bracket[v->bracket_count++];m->round=col;m->index=i;
        snprintf(m->home,64,"%s",f->home ? exhibition_team_catalog_name(f->home) : "TO BE DECIDED");
        snprintf(m->away,64,"%s",f->away ? exhibition_team_catalog_name(f->away) : (f->home && f->complete ? "BYE" : "TO BE DECIDED"));
        m->home_badge=exhibition_team_catalog_badge(f->home);m->away_badge=exhibition_team_catalog_badge(f->away);
        m->hg=f->home_goals;m->ag=f->away_goals;m->complete=f->complete;
        const uint32_t team=ml_event_manager_team(&career,cup_kind);
        m->own=f->home==team || f->away==team;
      }
    }
    v->helper_count=3u;v->helper_key[0]="L";v->helper_label[0]="PREV ROUND";v->helper_key[2]="R";v->helper_label[2]="NEXT ROUND";
  }
  if(page==ML_PAGE_NEXT && ((pending.kind>=ML_EVENT_WINDOW && !ml_event_is_match(pending.kind)) || career.office.dismissed)) {
    memset(v->rows,0,sizeof(v->rows));v->count=career.office.dismissed ? 0u : 1u;v->total=v->count;v->first=v->selected=0u;
    snprintf(v->title,64,"%s",career.office.dismissed ? "CAREER OVER" : "NEXT EVENT");
    snprintf(v->left_title,64,"%s",career.office.dismissed ? "MANAGER CONTRACT" : ml_event_label(&career,&pending));
    snprintf(v->rows[0].label,64,"ADVANCE CALENDAR");snprintf(v->rows[0].detail,96,"Continue to season day %u",pending.day+1u);v->rows[0].enabled=1;
    if(career.office.dismissed)snprintf(v->empty,96,"%s",career.office.dismissed==1u ? "Dismissed: six consecutive losses" : "Dismissed: 14 days of negative balance");
  }
  if(page==ML_PAGE_MARKET_CLUBS) {
    const char *labels[]={"MY TEAMS","TRANSFER RESPONSE","WEAK POSITION","BROWSE TEAM"};
    const char *details[]={"Review offers from clubs for your players","Track your bids, replies and counteroffers","Strengthen the weakest role in your starting XI","Find players by league, then team"};
    memset(v->rows,0,sizeof(v->rows));v->count=v->total=4u;v->first=0u;v->selected=focus;
    for(uint32_t i=0;i<4u;i++){snprintf(v->rows[i].label,64,"%s",labels[i]);snprintf(v->rows[i].detail,96,"%s",details[i]);v->rows[i].enabled=1;}
    v->rows[0].unread=incoming_unread;v->rows[1].unread=outgoing_unread;
  }
  if(page==ML_PAGE_MARKET_PLAYERS || page==ML_PAGE_CONTRACTS) {
    for(uint32_t i=0;i<v->count;i++) {
      const MlPlayer *p=&career.players[row_players[v->first+i]];ml_player_row(&v->rows[i],p);
      if(page==ML_PAGE_CONTRACTS)snprintf(v->rows[i].value,48,"Contract until season %u",p->contract_end);
      else snprintf(v->rows[i].value,48,"%.47s",p->club ? exhibition_team_catalog_name(p->club) : "Free agent");
    }
    if(!v->count)snprintf(v->empty,96,"No Players Available");
    if(page==ML_PAGE_MARKET_PLAYERS && market_club)snprintf(v->left_title,64,"%s",exhibition_team_catalog_name(market_club));
    else if(page==ML_PAGE_MARKET_PLAYERS && player_rows && career.players[row_players[0]].club)
      snprintf(v->left_title,64,"WEAK POSITION / %s",ml_role(ml_weak_position(&career)));
  }
  if(page==ML_PAGE_OFFERS || page==ML_PAGE_MANAGER_OFFICE || page==ML_PAGE_MESSAGES || page==ML_PAGE_JOBS) {
    memset(v->rows,0,sizeof(v->rows));v->count=0u;v->first=focus/5u*5u;v->selected=focus;v->action_count=0u;
    snprintf(v->title,64,"%s",page==ML_PAGE_OFFERS ? (offers_incoming ? "CLUB OFFERS" : "TRANSFER RESPONSE") :
      page==ML_PAGE_MANAGER_OFFICE ? "MANAGER" : page==ML_PAGE_MESSAGES ? "PRESIDENT MESSAGES" : "JOB OFFERS");
    snprintf(v->left_title,64,"%s",v->title);
    v->total=page==ML_PAGE_OFFERS ? offer_rows : page==ML_PAGE_MANAGER_OFFICE ? 3u : page==ML_PAGE_MESSAGES ? career.office.notice_count :
      career.office.job_team && career.day<=career.office.job_expiry && !career.office.dismissed ? 1u : 0u;
    for(uint32_t i=0;i<5u && v->first+i<v->total;i++) {
      const uint32_t index=v->first+i;MlViewRow *r=&v->rows[v->count++];r->enabled=1;
      if(page==ML_PAGE_OFFERS) {
        const MlOffer *o=&career.office.offers[offer_indices[index]];
        r->unread=ml_offer_unread(&career,offer_indices[index]);
        r->badge=exhibition_team_catalog_badge(offers_incoming ? o->to : o->from);
        snprintf(r->label,64,"%s",career.players[o->player].name);
        snprintf(r->detail,96,"%s / DAY %u / %.42s",ml_offer_status(o->status),o->status==ML_OFFER_WAITING ? o->due+1u : o->updated+1u,
          exhibition_team_catalog_name(offers_incoming ? o->to : o->from));
        ml_money(r->value,48,o->fee);r->portrait=career.players[o->player].portrait_id;
      }else if(page==ML_PAGE_MANAGER_OFFICE) {
        snprintf(r->label,64,"%s",index==2u ? "NATIONAL TEAM" : index ? "PRESIDENT MESSAGES" : "JOB OFFERS");
        snprintf(r->detail,96,"%s",index==2u ? "International appointment alongside your club" : index ? "Board feedback, warnings and club notifications" : "Review opportunities within your league");
        r->emblem=index==2u ? 2u : index ? 4u : 3u;
      }else if(page==ML_PAGE_MESSAGES) {
        const MlNotice *n=&career.office.notices[career.office.notice_count-1u-index];
        snprintf(r->label,64,"SEASON %u / DAY %u",n->season,n->day+1u);snprintf(r->detail,96,"%s",n->text);
      }else {
        snprintf(r->label,64,"%s",exhibition_team_catalog_name(career.office.job_team));r->badge=exhibition_team_catalog_badge(career.office.job_team);
        snprintf(r->detail,96,"Manager offer / reply by day %u",career.office.job_expiry+1u);
      }
    }
    if(!v->count)snprintf(v->empty,96,"%s",page==ML_PAGE_OFFERS ? "No Transfer Offers Yet" : page==ML_PAGE_MESSAGES ? "No Messages Yet" : "No Job Offers Yet");
    if(v->total<=5u)v->helper_count=2u;
  }
  if(v->empty[0]){memset(v->info,0,sizeof(v->info));snprintf(v->left_title,64,"%s",v->title);}
  ml_office_drawer(v);
}
