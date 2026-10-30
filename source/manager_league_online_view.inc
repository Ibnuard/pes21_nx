static void helper(MdView *v,const char *key,const char *label){if(v->helper_count<6){v->helper_key[v->helper_count]=key;v->helper_label[v->helper_count++]=label;}}
static void row(MdView *v,uint32_t i,const char *label,const char *detail,const char *value,uint32_t badge){
  MdRow *r=&v->rows[i];memset(r,0,sizeof(*r));copy(r->label,sizeof(r->label),label);copy(r->detail,sizeof(r->detail),detail);copy(r->value,sizeof(r->value),value);r->badge=badge;r->enabled=1;
}
static void history_open(uint32_t page,int reset){
  if(reset)online.history_snapshot=0;
  online.history=1;online.history_request=page;char path[192];
  snprintf(path,sizeof(path),"/clubs/%llu/matches?page=%u&page_size=5&snapshot_id=%llu",(unsigned long long)(online.opponent?online.opponent_id:strtoull(online.club_id,NULL,10)),page,(unsigned long long)online.history_snapshot);get(J_HISTORY,path);
}
static void route_back(void){
  if(!online.route_count){online.profile_child=0;online.opponent=0;change_page(MD_DASHBOARD);online.focus=online.hub_focus;return;}
  MoRoute route=online.routes[online.route_count-1];online.route_origin=(MoRoute){online.page,online.focus,online.opponent,online.opponent_id};online.route_restore=1;online.route_focus=route.focus;
  online.profile_child=0;online.opponent=route.page==MD_OPPONENT_PROFILE?1:route.opponent;online.opponent_id=route.opponent_id;
  if(route.page==MD_TABLE||route.page==MD_TEAMS_PAGE){online.opponent=0;online.want_teams=route.page==MD_TEAMS_PAGE;get(J_STANDINGS,"/league/standings");}
  else if(route.page==MD_CLUB_PROFILE){online.opponent=0;get(J_PROFILE,"/club/profile");}
  else if(route.page==MD_OPPONENT_PROFILE){char path[128];snprintf(path,sizeof(path),"/club/opponents/%llu",(unsigned long long)route.opponent_id);get(J_OPPONENT,path);}
  else if(route.page==MD_TEAM_HISTORY)history_open(online.history_page,0);
  else if(route.page==MD_TEAM_INFO||route.page==MD_COLLECTION_PAGE)get(route.page==MD_TEAM_INFO?J_SQUAD:J_COLLECTION,route.page==MD_TEAM_INFO?"/club/squad":"/club/collection");
  else change_page(route.page);
}
static int offer_ready(const MoOffer *offer){
  if(offer->available)return 1;
  message("PACK UNAVAILABLE",!strcmp(offer->unavailable,"CATALOG_NOT_READY")?"This club's player catalog is being updated. Choose another club pack. Your NX Cash has not been charged.":!strcmp(offer->unavailable,"OFFER_ALREADY_PURCHASED")?"You have already claimed this offer. Choose a different pack.":"This pack has too few players outside your collection. Choose another club or pack size. Your NX Cash has not been charged.");return 0;
}
static void open_shop(void){online.shop_sizes=0;get(J_OFFERS,"/shop/offers");}
static void open_squad(int plan){online.opponent=0;online.want_plan=plan;get(plan?J_COLLECTION:J_SQUAD,plan?"/club/collection":"/club/squad");}
static void purchases_open(void){
  online.purchases_return=online.page;online.purchases_focus=online.focus;online.want_plan=2;get(J_COLLECTION,"/club/collection");
}
static void open_schedule(void){online.match_group=0;online.history=0;online.schedule_auto=1;get(J_SCHEDULE,"/league/schedule");}
static uint32_t hub_phase(void){
  if(online.calendar_conflict){uint64_t now=server_now();return now<online.match_day_start?MH_PREPARATION:now<online.match_day_end?MH_MATCH:MH_END;}
  uint32_t phase=online.league_known?md_hub_phase(online.phase):MH_UNKNOWN;
  /* Some deployments retain PREPARATION after kickoff. Official broadcast
   * boundaries still let the user open the matches, without inventing a cycle
   * or enabling registration from a stale state label. */
  uint64_t now=server_now();
  if((phase==MH_REGISTRATION||phase==MH_PREPARATION)&&online.match_day_start&&
      online.match_day_end>online.match_day_start&&now>=online.match_day_start&&
      online.next_registration>online.match_day_end&&now<online.next_registration)
    return now<online.match_day_end?MH_MATCH:MH_END;
  return phase;
}
static uint64_t hub_phase_end(void){
  uint32_t phase=hub_phase();
  if(online.phase_ends&&!online.calendar_conflict&&phase==md_hub_phase(online.phase))return online.phase_ends;
  return phase==MH_REGISTRATION?online.registration_close:phase==MH_PREPARATION?online.match_day_start:phase==MH_MATCH?online.match_day_end:phase==MH_END?online.next_registration:0;
}
static uint32_t hub_live_count(void){
  if(hub_phase()!=MH_MATCH||online.match_cycle!=online.cycle||online.mono<online.schedule_seen||online.mono-online.schedule_seen>=90000)return 0;
  uint32_t count=0;uint64_t now=server_now();
  for(unsigned i=0;i<online.match_count;i++){
    const MoMatch *m=&online.matches[i];
    if(m->phase==1&&(!m->kickoff||now>=m->kickoff)&&(!m->ends||now<m->ends))count++;
  }
  return count;
}
static void open_standings(void){
  uint32_t phase=hub_phase();
  if(phase==MH_REGISTRATION)message("LEAGUE STANDINGS","The league's teams are not final yet. Standings open during Preparation, after registration closes.");
  else if(phase==MH_UNKNOWN)message("LEAGUE STANDINGS","The league calendar has not been published yet. Refresh to check again.");
  else get(J_STANDINGS,"/league/standings");
}
static void home_action(void){
  online.profile_child=0;online.hub_focus=online.focus;
  uint32_t f=online.focus;
  if(online.tab==0){
    if(f==0){uint32_t phase=hub_phase();
      if(phase==MH_REGISTRATION&&!online.joined&&!online.calendar_conflict){
        if(hub_phase_end()&&server_now()>=hub_phase_end()){refresh_bootstrap();}
        else {online.join_confirm=1;online.join_choice=1;online.join_cycle=online.cycle;}
      }else if(phase>=MH_MATCH)open_schedule();
      else message(md_hub_phase_name(phase),md_hub_phase_help(phase));}
    else if(f==1)get(J_NEWS,"/news");else if(f==2){change_page(MD_WEEK_SCHEDULE);online.focus=md_hub_weekday(server_now());}else if(f==3)open_standings();else get(J_PROFILE,"/club/profile");
  }else if(online.tab==1){
    if(f==0)open_squad(1);
    else if(f==1){if(hub_phase()<MH_MATCH)message("PLAYER FEED","Top Scorers and Rising Stars open from Match Day until League End.");
      else if(!online.player_feed_capable)message("PLAYER FEED","Player performance data has not been published by the server yet.");
      else get(J_PLAYER_FEED,"/league/player-feed");}
    else if(f==2)open_shop();
    else message("TRADE HISTORY - UPCOMING","Player trading and its transaction history are planned for a future update.");
  }else{if(f==0)get(J_CHAMPIONS,"/ranking/champions");else if(f==1)monthly_open(0,1,0);else if(f==3)change_page(MD_RULES);else{change_page(MD_LOGOUT);online.focus=1;}}
}
static uint32_t group_matches(uint32_t out[MO_MATCHES]){
  uint32_t count=0;for(uint32_t i=0;i<online.match_count;i++){
    uint64_t club=online.opponent?online.opponent_id:strtoull(online.club_id,NULL,10);
    if(online.history&&online.matches[i].home_club!=club&&online.matches[i].away_club!=club)continue;
    unsigned group=online.matches[i].phase==1?0:online.matches[i].phase==0?1:2;if(group==online.match_group)out[count++]=i;
  }return count;
}
static void watch_open(const MoMatch *match){
  online.fixture=match->id;online.kickoff=match->kickoff;online.replay=match->phase==2;online.ended=online.replay;
  online.paused=online.play_ms=online.touchline=online.event_count=online.watermark=0;online.recording_hash[0]=0;
  online.last_events=0;online.timeline_serial++;
  online.bundle_ready=online.watch_fail=online.watch_stalled=0;online.watch_wait=online.watermark_changed=online.mono;
  online.next_watch_request=0;online.home_badge=match->row.badge;online.away_badge=match->row.away_badge;
  memset(online.chunks,0,sizeof(online.chunks));memset(online.score,0,sizeof(online.score));memset(online.shots,0,sizeof(online.shots));memset(online.on_target,0,sizeof(online.on_target));
  copy(online.home,sizeof(online.home),"HOME CLUB");copy(online.away,sizeof(online.away),"AWAY CLUB");
  const char *sep=strstr(match->row.label," Vs ");if(sep){size_t n=(size_t)(sep-match->row.label);if(n>=sizeof(online.home))n=sizeof(online.home)-1;memcpy(online.home,match->row.label,n);online.home[n]=0;copy(online.away,sizeof(online.away),sep+4);}
  if(match->home[0])copy(online.home,sizeof(online.home),match->home);
  if(match->away[0])copy(online.away,sizeof(online.away),match->away);
  if(online.bundle_capable){char path[160];snprintf(path,sizeof(path),"/matches/%llu/playback",(unsigned long long)online.fixture);get(J_RECORDING,path);}else queue_watch_header();
}
static uint32_t visible_events(void){
  uint32_t count=0;while(count<online.event_count&&online.events[count].at<=online.play_ms)count++;
  return count;
}
static void manager_online_input(uint32_t key,uint32_t buttons,int32_t ax,int32_t ay,int raw){
  pthread_mutex_lock(&ui_mutex);
  online.force_read=(key&Y)&&online.page!=MD_SHOP&&online.page!=MD_SHOP_CLUBS&&online.page!=MD_PACK_SELECT;
  if(raw&&(online.notice[0]||online.busy||online.clock_active||online.opponent||online.page!=MD_CLUB_PLAN)){online.plan_move=0;online.plan_buttons=buttons;}
  /* Leaving the hub must not wait for its advisory preview reads. The host
   * closes the mode and invalidates their generation; writes stay modal. */
  int hub_back=(key&B)&&online.page==MD_DASHBOARD&&!online.modal_busy&&
    (online.busy_kind==J_HUB_TABLE||online.busy_kind==J_HUB_SCHEDULE||
     online.busy_kind==J_HUB_NEWS||online.busy_kind==J_HUB_RANKING);
  if(!online.active||online.clock_active||(online.busy&&online.busy_kind!=J_HUB_LIVE&&!hub_back&&(online.modal_busy||online.page!=MD_WATCH)))goto done;
  if(online.notice[0]){if(key&(A|B)){mo_wipe(online.notice,sizeof(online.notice));online.notice_title[0]=0;}goto done;}
  if(key&32u){message("INFO",online.page==MD_CLUB_PLAN&&online.opponent?"This Game Plan uses the latest team data saved by this club.":manager_league_page_info(online.page));goto done;}
  if(online.join_confirm){
    if(key&B)online.join_confirm=0;
    else if(key&(LEFT|RIGHT|UP|DOWN))online.join_choice^=1;
    else if(key&A){online.join_confirm=0;
      if(!online.join_choice){
        if(hub_phase()!=MH_REGISTRATION||online.joined||online.calendar_conflict||online.cycle!=online.join_cycle||(hub_phase_end()&&server_now()>=hub_phase_end()))refresh_bootstrap();
        else request(J_JOIN,"POST","/league/join","{}",1);
      }
    }goto done;
  }
  if(pin_active){pin_pad(key);if(notice[0]){message("PIN",notice);notice[0]=0;}goto done;}
  if(!online.opponent&&(online.page==MD_CLUB_PLAN||online.page==MD_PLAN_SETTINGS||online.page==MD_PLAN_RESERVES)){if(raw)key=plan_sample(buttons,key,ax,ay);plan_pad(key);goto done;}
  if(online.clock_confirm){
    if(key&B)online.clock_confirm=0;
    else if(key&(LEFT|RIGHT|UP|DOWN))online.clock_choice^=1;
    else if(key&A){uint32_t action=online.clock_confirm-1;online.clock_confirm=0;if(!online.clock_choice)clock_submit(action);}
    goto done;
  }
  if(online.touchline){
    uint32_t count=visible_events();
    if(key&B)online.touchline=0;
    else if((key&UP)&&online.touchline_focus)online.touchline_focus--;
    else if((key&DOWN)&&online.touchline_focus+1<count)online.touchline_focus++;
    else if(key&L)online.touchline_focus=online.touchline_focus>5?online.touchline_focus-5:0;
    else if(key&R){uint32_t next=online.touchline_focus+5;online.touchline_focus=next<count?next:count?count-1:0;}
    goto done;
  }
  if(online.page==MD_PACK_BUY||online.page==MD_LOGOUT){
    if(key&B){int logout=online.page==MD_LOGOUT;change_page(logout?MD_DASHBOARD:MD_PACK);if(logout)online.focus=online.hub_focus;goto done;}
    if(key&(LEFT|RIGHT|UP|DOWN))online.focus^=1;
    if(key&A){if(online.focus){int logout=online.page==MD_LOGOUT;change_page(logout?MD_DASHBOARD:MD_PACK);if(logout)online.focus=online.hub_focus;goto done;}
      if(online.page==MD_LOGOUT){request(J_LOGOUT,"POST","/auth/logout","{}",1);goto done;}
      if(online.offer_focus>=online.offer_count)goto done;
      const MoOffer *offer=&online.offers[online.offer_focus];char body[256];
      snprintf(body,sizeof(body),"{\"offer_id\":%llu,\"offer_version\":%u,\"accepted_price_nx_cash\":%u}",(unsigned long long)offer->id,offer->version,offer->price);
      if(request(J_PAY,"POST","/shop/purchases",body,1))online.pay_uncertain=1;
    }goto done;
  }
  if(online.page==MD_PACK_OPENING)goto done;
  if(online.page==MD_PACK_RESULT&&(key&A)){open_shop();goto done;}
  if(online.page==MD_PACK_SELECT){
    uint32_t count=online.pool_count;
    if(key&Y){purchases_open();goto done;}
    if(key&LEFT){if(online.focus<count&&online.focus%4)online.focus--;}
    else if(key&RIGHT){if(online.focus<count&&online.focus%4<3&&online.focus+1<count)online.focus++;}
    else if(key&UP){if(online.focus==count)online.focus=count>4?4:0;else if(online.focus>=4)online.focus-=4;}
    else if(key&DOWN){if(online.focus<count){if(online.focus+4<count)online.focus+=4;else if(online.focus<4&&count>4)online.focus=count-1;else if(selected_count()==online.draw)online.focus=count;}}
    else if(key&A){if(online.focus==count){if(selected_count()==online.draw)selection_submit();}
      else if(online.grant_uncertain){online.focus=count;message("CONFIRM SELECTION","The previous confirmation is unresolved. Confirm again to recover the same players; this does not charge NX Cash again.");}
      else {uint32_t bit=1u<<online.focus;if(online.selected&bit)online.selected&=~bit;else if(selected_count()<online.draw)online.selected|=bit;else message("YOUR SELECTION","Deselect a player before choosing another.");}}
    goto done;
  }
  if(online.page==MD_PURCHASE_HISTORY){
    if(key&B){change_page(online.purchases_return);online.focus=online.purchases_focus;}
    else if((key&UP)&&online.focus)online.focus--;
    else if((key&DOWN)&&online.focus+1<online.purchases_count)online.focus++;
    else if((key&L)&&online.focus>=5)online.focus=(online.focus/5-1)*5;
    else if((key&R)&&(online.focus/5+1)*5<online.purchases_count)online.focus=(online.focus/5+1)*5;
    goto done;
  }
  if(key&B){
    if(online.page==MD_REGISTER||online.page==MD_DASHBOARD){online.action=MD_ACTION_EXIT;goto done;}
    if(online.page==MD_CLUB){change_page(MD_LEAGUES);online.focus=manager_club_category_ordinal(online.category);}
    else if(online.page==MD_NAME){pin_clear();change_page(MD_CLUB);}
    else if(online.page==MD_LOGIN||online.page==MD_LEAGUES){pin_clear();change_page(MD_REGISTER);online.focus=online.auth_register?1:0;}
    else if(online.page==MD_PACK)change_page(MD_SHOP);
    else if(online.page==MD_SHOP){online.shop_sizes=0;change_page(MD_SHOP_CLUBS);}
    else if(online.page==MD_PROMOTION){online.input_promo=0;mo_wipe(online.promo_code,sizeof(online.promo_code));change_page(shop_page());}
    else if(online.page==MD_PACK_RESULT){open_shop();}
    else if(route_page(online.page)){online.touchline=0;route_back();}
    else if(online.page==MD_PAYMENT_RECOVERY){online.shop_sizes=0;change_page(MD_SHOP_CLUBS);}
    else {change_page(MD_DASHBOARD);online.focus=online.hub_focus;}
    goto done;
  }
  if(online.page==MD_REGISTER){
    if(key&(LEFT|RIGHT))online.focus^=1;
    if(key&X){online.compat_checked=0;get(J_COMPAT,"/compatibility");}
    if(key&A){if(!online.compatible){get(J_COMPAT,"/compatibility");goto done;}
      online.auth_register=online.focus!=0;pin_clear();change_page(online.auth_register?MD_LEAGUES:MD_LOGIN);}
  }else if(online.page==MD_LEAGUES){
    const uint32_t count=manager_club_category_count(),step=key&(L|R)?5u:1u;
    if(key&(UP|L))online.focus=online.focus>=step?online.focus-step:0;
    else if((key&(DOWN|R))&&count)online.focus=online.focus+step<count?online.focus+step:count-1;
    else if((key&A)&&online.focus<manager_club_category_count()){online.category=manager_club_category_at(online.focus);online.club_choice=0;change_page(MD_CLUB);}
  }else if(online.page==MD_CLUB){
    if(!manager_club_category(online.category)){change_page(MD_LEAGUES);goto done;}
    const ExhibitionTeamCategory *c=&exhibition_team_categories[online.category];
    const uint32_t step=key&(L|R)?5u:1u;
    if(key&(UP|L))online.club_choice=online.club_choice>=step?online.club_choice-step:0;
    else if((key&(DOWN|R))&&c->team_count)online.club_choice=online.club_choice+step<c->team_count?online.club_choice+step:c->team_count-1;
    else if((key&A)&&online.club_choice<c->team_count){online.team=c->teams[online.club_choice];change_page(MD_NAME);}
  }else if(online.page==MD_NAME||online.page==MD_LOGIN){
    const uint32_t last=online.page==MD_NAME?3:2;
    if((key&UP)&&online.focus)online.focus--;else if((key&DOWN)&&online.focus<last)online.focus++;
    else if(key&A){if(online.focus==last)auth_submit();else if(online.focus==(online.page==MD_NAME?2u:1u))pin_open(online.page==MD_NAME);else online.action=MD_ACTION_NAME;}
  }else if(online.page==MD_DASHBOARD){
    if(key&(L|R|LEFT|RIGHT|UP|DOWN)){uint32_t before=online.tab;md_hub_navigate(key,&online.tab,&online.focus);online.hub_focus=online.focus;if(before!=online.tab)online.serial++;}
    else if(key&A)home_action();
    else if(key&Y){if(online.environment==MO_TEST&&online.demo_time)change_page(MD_ONLINEDEV);else refresh_bootstrap();}
  }else if(online.page==MD_ONLINEDEV){
    uint32_t count=2;
    if((key&UP)&&online.focus)online.focus--;else if((key&DOWN)&&online.focus+1<count)online.focus++;
    else if(key&Y)refresh_bootstrap();
    else if(key&A){
      if(online.clock_intent.magic){if(!online.focus)service_lookup(J_CLOCK_STATUS);else clock_submit(0);}
      else {online.clock_confirm=online.focus+1;online.clock_choice=1;}
    }
  }else if(online.page==MD_PROMOTION){
    if((key&UP)&&online.focus)online.focus--;else if((key&DOWN)&&online.focus<1)online.focus++;
    else if(key&Y){if(online.promo_intent.magic)service_lookup(J_PROMO_STATUS);}
    else if(key&A){
      if(online.promo_intent.magic){if(!online.focus)service_lookup(J_PROMO_STATUS);else promotion_submit();}
      else if(!online.focus){online.input_promo=1;online.action=MD_ACTION_NAME;}
      else promotion_submit();
    }
  }else if(online.page==MD_SHOP||online.page==MD_SHOP_CLUBS){
    unsigned list[MO_OFFERS],count=online.page==MD_SHOP_CLUBS?shop_clubs(list):shop_sizes(list),at=0;
    if(online.page==MD_SHOP_CLUBS)at=online.shop_focus<count?online.shop_focus:0;
    else {while(at<count&&list[at]!=online.offer_focus)at++;if(at==count)at=0;}
    if((key&(LEFT|L))&&at)at=key&L?(at>3?at-3:0):at-1;
    else if((key&(RIGHT|R))&&at+1<count){at+=key&R?3:1;if(at>=count)at=count-1;}
    else if((key&A)&&count){
      if(online.pay_uncertain)change_page(MD_PAYMENT_RECOVERY);
      else if(online.page==MD_SHOP_CLUBS){online.shop_team=online.offers[list[at]].team;online.offer_focus=list[at];online.shop_sizes=1;change_page(MD_SHOP);}
      else if(offer_ready(&online.offers[list[at]]))change_page(MD_PACK);
      goto done;
    }
    else if(key&X){
      if(!online.promotion_codes)message("PROMOTION CODES","Promotion-code redemption is not enabled by this server yet.");
      else {change_page(MD_PROMOTION);if(online.promo_intent.magic)service_lookup(J_PROMO_STATUS);}
    }
    else if(key&Y){purchases_open();goto done;}
    if(online.page==MD_SHOP_CLUBS)online.shop_focus=at;else if(count)online.offer_focus=list[at];
  }else if(online.page==MD_PAYMENT_RECOVERY){
    if(key&(UP|DOWN))online.focus^=1;
    else if(key&Y)payment_lookup();
    else if(key&A){if(!online.focus)payment_lookup();
      else if(online.pay_uncertain&&!online.pay_corrupt&&request(J_PAY,"POST","/shop/purchases",online.pay_body,1))online.pay_uncertain=1;
      else if(online.pay_corrupt)payment_lookup();}
  }else if(online.page==MD_PACK){
    if(key&A){if(online.offer_focus>=online.offer_count)goto done;const MoOffer *o=&online.offers[online.offer_focus];
      if(online.pay_uncertain){message("PAYMENT NEEDS VERIFICATION","Reopen Shop to recover your paid pack. A new purchase is blocked while a previous payment is unconfirmed.");goto done;}
      if(!offer_ready(o))goto done;
      if(!online.cash_known||online.cash<o->price){message("NX CASH","You do not have enough NX Cash for this pack.");goto done;}
      change_page(MD_PACK_BUY);online.focus=1;}
  }else if(online.page==MD_TEAM_INFO||online.page==MD_COLLECTION_PAGE){
    if((key&UP)&&online.focus)online.focus--;else if((key&DOWN)&&online.focus+1<online.player_count)online.focus++;
    else if((key&X)&&!online.opponent)get(J_COLLECTION,"/club/collection");
    else if((key&A)&&online.focus<online.player_count){MoPlayer *p=&online.players[online.focus];char text[256];snprintf(text,sizeof(text),"%s\n%s - OVR %u\n%s",p->row.label,p->row.detail,p->row.rating,online.page==MD_COLLECTION_PAGE?"Owned in your online collection.":online.opponent?"Registered in this club's squad.":"Registered in your online squad.");message("PLAYER PROFILE",text);}
  }else if(online.page==MD_CLUB_PROFILE){
    if((key&UP)&&online.focus)online.focus--;else if((key&DOWN)&&online.focus<5)online.focus++;
    else if(key&A){online.profile_focus=online.focus;online.profile_child=1;
      if(online.focus==0)open_squad(0);else if(online.focus==1){online.profile_child=0;open_standings();if(online.busy)online.profile_child=1;}
      else if(online.focus==2){history_open(1,1);}
      else if(online.focus==3){online.profile_child=0;monthly_open(0,1,0);if(online.busy)online.profile_child=1;}else if(online.focus==4)open_squad(1);else change_page(MD_REWARDS);}
  }else if(online.page==MD_REWARDS){
    if((key&UP)&&online.focus)online.focus--;else if((key&DOWN)&&online.focus<4)online.focus++;
  }else if(online.page==MD_OPPONENT_PROFILE){
    if((key&UP)&&online.focus)online.focus--;else if((key&DOWN)&&online.focus<2)online.focus++;
    else if(key&A){if(online.focus==0)change_page(MD_CLUB_PLAN);else if(online.focus==1)change_page(MD_TEAM_INFO);else {history_open(1,1);}}
  }else if(online.page==MD_OVERALL){
    if(key&(L|R))monthly_open(online.rank_section^1u,1,0);
    else if(key&Y)monthly_open(online.rank_section,1,0);
    else if(key&UP){if(online.focus)online.focus--;else if(online.rank_page>1)monthly_open(online.rank_section,online.rank_page-1,1);}
    else if(key&DOWN){if(online.focus+1<online.row_count)online.focus++;
      else if((uint64_t)online.rank_page*MO_RANK_PAGE_SIZE<online.rank_total)monthly_open(online.rank_section,online.rank_page+1,0);}
  }else if(online.page==MD_TABLE||online.page==MD_TEAMS_PAGE){
    if((key&UP)&&online.focus)online.focus--;else if((key&DOWN)&&online.focus+1<online.row_count)online.focus++;
    else if((key&A)&&online.focus<online.row_count){uint64_t club=online.rows[online.focus].team_id;
      if(club==strtoull(online.club_id,NULL,10)){online.opponent=0;get(J_PROFILE,"/club/profile");}
      else if(club){online.opponent_id=club;char path[160];snprintf(path,sizeof(path),"/club/opponents/%llu",(unsigned long long)club);get(J_OPPONENT,path);}
      else message("CLUB PROFILE UNAVAILABLE","Club details for this ranking entry have not been published yet.");}
    else if(key&Y){online.want_teams=online.page==MD_TEAMS_PAGE;get(J_STANDINGS,"/league/standings");}
  }else if(online.page==MD_TEAM_HISTORY){
    if((key&L)&&online.history_page>1)history_open(online.history_page-1,0);
    else if((key&R)&&online.history_page*5<online.history_total)history_open(online.history_page+1,0);
    else if((key&UP)&&online.focus)online.focus--;
    else if((key&DOWN)&&online.focus+1<online.history_count)online.focus++;
    else if((key&A)&&online.focus<online.history_count)watch_open(&online.history_matches[online.focus]);
    else if(key&Y)history_open(1,1);
  }else if(online.page==MD_SCHEDULE){
    uint32_t list[MO_MATCHES],n=group_matches(list);
    if(key&L){online.match_group=online.match_group?online.match_group-1:2;online.focus=0;}
    else if(key&R){online.match_group=(online.match_group+1)%3;online.focus=0;}
    else if((key&LEFT)&&online.focus%2)online.focus--;
    else if((key&RIGHT)&&!(online.focus%2)&&online.focus+1<n)online.focus++;
    else if((key&UP)&&online.focus>=2)online.focus-=2;else if((key&DOWN)&&online.focus+2<n)online.focus+=2;
    else if((key&A)&&online.focus<n){const MoMatch *match=&online.matches[list[online.focus]];if(!match->phase)message("SCHEDULED BROADCAST","This match has not started yet. Return at the scheduled kickoff.");else watch_open(match);}
    else if(key&Y)get(J_SCHEDULE,"/league/schedule");
  }else if(online.page==MD_WATCH){
    if(key&Y){online.watch_fail=online.watch_stalled=0;online.watermark_changed=online.mono;online.last_header=online.last_events=0;
      if(online.bundle_capable){char path[160];snprintf(path,sizeof(path),"/matches/%llu/playback",(unsigned long long)online.fixture);get(J_RECORDING,path);}else queue_watch_header();}
    else if(key&X){char path[160];snprintf(path,sizeof(path),"/matches/%llu/events",(unsigned long long)online.fixture);online.touchline=1;online.touchline_focus=0;if(!online.bundle_ready)get(J_EVENTS,path);}
    else if((key&A)&&online.replay)online.paused=!online.paused;
    else if((key&L)&&online.replay){online.play_ms=online.play_ms>30000?online.play_ms-30000:0;online.timeline_serial++;}
    else if((key&R)&&online.replay){online.play_ms=online.play_ms+30000<online.duration?online.play_ms+30000:online.duration;online.timeline_serial++;}
  }else if(online.page==MD_CLUB_PLAN){/* Opponent snapshot has no edit controls. */}
  else if(online.page==MD_NEWS||online.page==MD_PLAYER_FEED){
    uint32_t count=online.page==MD_NEWS?online.activity_count:online.player_feed_count[online.feed_section];
    if((key&UP)&&online.focus)online.focus--;else if((key&DOWN)&&online.focus+1<count)online.focus++;
    else if(key&(L|R)){
      if(online.page==MD_PLAYER_FEED){online.feed_section^=1;online.focus=0;}
      else if(key&L)online.focus=online.focus>3?online.focus-3:0;
      else online.focus=online.focus+3<count?online.focus+3:count?count-1:0;
    }else if(key&Y)get(online.page==MD_NEWS?J_NEWS:J_PLAYER_FEED,online.page==MD_NEWS?"/news":"/league/player-feed");
  }
  else {
    uint32_t count=online.page==MD_RULES?MH_RULE_COUNT:online.page==MD_WEEK_SCHEDULE?7:online.page==MD_LEAGUE_TIMELINE?6:online.row_count;
    if((key&UP)&&online.focus)online.focus--;else if((key&DOWN)&&online.focus+1<count)online.focus++;
  }
done:online.force_read=0;pthread_mutex_unlock(&ui_mutex);
}
void manager_online_pad(uint32_t key){manager_online_input(key,0,0,0,0);}
void manager_online_sample(uint32_t buttons,uint32_t key,int32_t ax,int32_t ay){manager_online_input(key,buttons,ax,ay,1);}

const char *manager_online_name(void){return online.input_promo?online.promo_code:online.page==MD_NAME&&online.focus==0?online.club_name:online.login_id;}
const char *manager_online_input_label(void){return online.input_promo?"PROMOTION CODE":online.page==MD_NAME&&online.focus==0?"TEAM NAME":"USER ID";}
int manager_online_input_promotion(void){return online.input_promo!=0;}
void manager_online_name_result(const char *text){
  pthread_mutex_lock(&ui_mutex);
  if(online.input_promo){
    if(text&&!normalize_promo(text,online.promo_code))message("PROMOTION CODE","Use the 12-32 letters and numbers printed on your code. Spaces and hyphens are optional.");
    online.input_promo=0;
  }else if(text){if(online.page==MD_NAME&&online.focus==0){size_t n=strlen(text);int valid=n>=3&&n<=31;for(size_t i=0;i<n;i++)if((unsigned char)text[i]<32)valid=0;
      if(valid)copy(online.club_name,sizeof(online.club_name),text);else message("TEAM NAME","Use a team name of 3-31 UTF-8 bytes without control characters.");
    }else {char id[32];if(md_auth_id(id,text))copy(online.login_id,sizeof(online.login_id),id);else message("USER ID","Use 3-24 letters, numbers, dots or underscores.");}}
  pthread_mutex_unlock(&ui_mutex);
}
uint32_t manager_online_take_action(void){pthread_mutex_lock(&ui_mutex);uint32_t action=online.action;online.action=0;pthread_mutex_unlock(&ui_mutex);return action;}
static void view_list(MdView *v,const MdRow *rows,uint32_t count,uint32_t visible){
  v->total=count;if(online.focus>=count)online.focus=count?count-1:0;v->focus=online.focus;v->first=online.focus/visible*visible;v->count=count-v->first;if(v->count>visible)v->count=visible;
  for(uint32_t i=0;i<v->count;i++)v->rows[i]=rows[v->first+i];
}
static uint32_t game_second(uint32_t elapsed){return elapsed<300000?elapsed*9/1000:elapsed<360000?2700:elapsed<660000?2700+(elapsed-360000)*9/1000:5400;}
static const char *phase_label(void){
  if(online.calendar_conflict){uint64_t now=server_now();return now<online.match_day_start?"PREPARATION":now<online.match_day_end?"MATCH DAY":"RESULTS & REWARDS";}
  if(!online.league_known)return "CALENDAR NOT PUBLISHED";
  if(!strcmp(online.phase,"REGISTRATION"))return "REGISTRATION & PREP";
  if(!strcmp(online.phase,"PREPARATION"))return "PREPARATION";
  if(strstr(online.phase,"MATCH")||strstr(online.phase,"COMPETITION"))return "MATCH DAY";
  if(strstr(online.phase,"RESULT")||strstr(online.phase,"CLOSED")||!strcmp(online.phase,"SETTLED"))return "RESULTS & REWARDS";
  return online.phase;
}
static void profile_view(MdView *v){
  static const char *const labels[]={"REGISTERED SQUAD","LEAGUE STANDINGS","MATCH HISTORY","LEAGUE RANKING","GAME PLAN","LEAGUE REWARDS"};
  static const char *const details[]={"Your players and positions","League position and points","Your club's scheduled games and replays","Current month and past season champions","Latest saved formation and eleven","Participation and finishing rewards"};
  copy(v->headline,sizeof(v->headline),online.club_name);copy(v->club,sizeof(v->club),exhibition_team_catalog_name(online.team));
  v->club_rank=online.club_rank;v->league_points=online.league_points;v->club_reputation=online.reputation;v->rank=online.overall_rank;
  if(!v->club_rank)for(uint32_t i=0;i<online.standing_count;i++)if(online.standings[i].selected){v->club_rank=i+1;break;}
  copy(v->season_label,sizeof(v->season_label),online.profile_season);
  char season[8];md_season_text(server_now(),season,sizeof(season),1);
  if(strcmp(season,online.profile_season)){v->club_reputation=v->rank=0;v->season_label[0]=0;}
  v->total=6;v->first=online.focus>3?1:0;v->count=5;
  for(uint32_t i=0;i<5;i++){uint32_t at=v->first+i;row(v,i,labels[at],details[at],"OPEN",0);
    if(at==0)snprintf(v->rows[i].value,sizeof(v->rows[i].value),"%u PLAYERS",online.roster_count);
    if(at==1&&v->club_rank)snprintf(v->rows[i].value,sizeof(v->rows[i].value),"POSITION %u",v->club_rank);
    if(at==3&&v->rank)snprintf(v->rows[i].value,sizeof(v->rows[i].value),"RANK %u",v->rank);
  }
  helper(v,"LS","SCROLL");helper(v,"A","OPEN");
}
static void watch_view(MdView *v){
  v->duration_ms=online.duration;v->elapsed_ms=online.play_ms;v->kickoff_ms=online.kickoff;v->watching_replay=online.replay;v->paused=online.paused;v->phase=online.ended?2:1;
  copy(v->home,sizeof(v->home),online.home);copy(v->away,sizeof(v->away),online.away);
  v->home_badge=online.home_badge;v->away_badge=online.away_badge;
  if(online.watch_fail)copy(v->empty_detail,sizeof(v->empty_detail),"BROADCAST UNAVAILABLE - Y TO RETRY, B TO RETURN");
  else if(online.watch_stalled)copy(v->empty_detail,sizeof(v->empty_detail),online.environment==MO_TEST?"TEST CLOCK IS PAUSED - WAITING FOR SERVER TIME":"WAITING FOR THE NEXT SERVER UPDATE");
  else copy(v->empty_detail,sizeof(v->empty_detail),"LOADING MATCH RECORDING");
  uint32_t second=game_second(online.play_ms);snprintf(v->clock,sizeof(v->clock),"%02u:%02u",second/60,second%60);v->minute=second/60;
  v->event_kind=UINT32_MAX;v->event_age_ms=UINT32_MAX;
  uint32_t index=online.chunk_ms?online.play_ms/online.chunk_ms:0;if(index>=online.chunk_count&&online.chunk_count)index=online.chunk_count-1;
  MoChunk *chunk=&online.chunks[index];
  const MoFrame *from=NULL,*to=NULL;
  if(chunk->valid&&chunk->index==index&&chunk->count){
    if(chunk->frames[0].at<=online.play_ms){
      uint32_t a=0;while(a+1<chunk->count&&chunk->frames[a+1].at<=online.play_ms)a++;
      from=&chunk->frames[a];to=a+1<chunk->count?&chunk->frames[a+1]:from;
      if(to==from&&index+1<online.chunk_count&&online.chunks[index+1].valid&&online.chunks[index+1].count)to=&online.chunks[index+1].frames[0];
    }else if(index&&online.chunks[index-1].valid&&online.chunks[index-1].count){
      MoChunk *previous=&online.chunks[index-1];from=&previous->frames[previous->count-1];to=&chunk->frames[0];
    }
  }
  if(from&&to&&from->at<=online.play_ms){
    float alpha=to->at>from->at?(float)(online.play_ms-from->at)/(float)(to->at-from->at):0;
    if(alpha<0)alpha=0;
    if(alpha>1)alpha=1;
    for(int i=0;i<23;i++){v->dots[i]=from->dots[i];v->dots[i].x+=(to->dots[i].x-from->dots[i].x)*alpha;v->dots[i].y+=(to->dots[i].y-from->dots[i].y)*alpha;}
    v->watch_ready=1;
  }
  v->home_goals=v->away_goals=0;v->shots[0]=v->shots[1]=v->on_target[0]=v->on_target[1]=0;
  for(uint32_t i=0;i<online.event_count;i++){
    const MoEvent *e=&online.events[i];if(e->at>online.play_ms)continue;
    if(e->kind==MD_GOAL){if(e->side)v->away_goals++;else v->home_goals++;v->shots[e->side]++;v->on_target[e->side]++;}
    if(e->kind==MD_SHOT)v->shots[e->side]++;
    if(e->kind==MD_SAVE){v->shots[1-e->side]++;v->on_target[1-e->side]++;}
    if(e->kind==MD_FOUL)v->fouls[e->side]++;
    if(e->kind==MD_YELLOW)v->cards[e->side]++;
    if(e->kind==MD_CORNER)v->corners[e->side]++;
    if(e->kind==MD_SUB)v->substitutions[e->side]++;
    if(v->event_age_ms==UINT32_MAX||online.play_ms-e->at<=v->event_age_ms){v->event_kind=e->kind;v->event_age_ms=online.play_ms-e->at;v->event_side=e->side;v->event_at_ms=e->at;v->event_serial=i+1;v->event_game_second=e->second;copy(v->event_name,sizeof(v->event_name),e->name);copy(v->event_other_name,sizeof(v->event_other_name),e->other);}
  }
  snprintf(v->score,sizeof(v->score),"%u - %u",v->home_goals,v->away_goals);
  uint32_t count=visible_events();
  for(uint32_t i=0;i<3&&i<count;i++)v->event_feed[i]=online.events[count-1-i].row;
  helper(v,"X","TOUCHLINE");helper(v,"Y","RETRY");if(online.replay){helper(v,"A",online.paused?"PLAY":"PAUSE");
    helper(v,"L","REWIND");
    helper(v,"R","FORWARD");}
  v->touchline_open=online.touchline;v->touchline_total=count;
  if(online.touchline_focus>=count)online.touchline_focus=count?count-1:0;
  v->focus=online.touchline_focus;
  v->touchline_first=online.touchline_focus;v->touchline_count=count-v->touchline_first;if(v->touchline_count>5)v->touchline_count=5;
  for(uint32_t i=0;i<v->touchline_count;i++){v->touchline[i]=online.events[count-1-v->touchline_first-i].row;v->touchline[i].selected=i==0;}
  if(online.touchline){v->helper_count=0;
    helper(v,"B","CLOSE");
    helper(v,"UP","SCROLL");
    helper(v,"L","PREV PAGE");
    helper(v,"R","NEXT PAGE");}
}
void manager_online_view(MdView *v){
  pthread_mutex_lock(&ui_mutex);memset(v,0,sizeof(*v));v->page=online.page;v->online=1;v->online_cash_available=online.cash_known;v->online_cash=online.cash;
  v->online_test=online.authenticated&&online.environment==MO_TEST;
  v->balance=online.cash>UINT32_MAX?UINT32_MAX:(uint32_t)online.cash;v->focus=online.focus;v->tab=online.tab;v->now_ms=online.mono;
  v->navigation_serial=online.serial;v->roster_size=online.roster_count;v->badge=exhibition_team_catalog_badge(online.team);v->joined=online.joined;
  if(online.opponent&&(online.page==MD_OPPONENT_PROFILE||online.page==MD_TEAM_INFO||online.page==MD_TEAM_HISTORY||online.page==MD_CLUB_PLAN))v->badge=exhibition_team_catalog_badge(online.opponent_team);
  v->week_id=(uint32_t)online.cycle;v->week.state=strstr(online.phase,"COMPETITION")||strstr(online.phase,"MATCH")?MD_MATCH_DAY:strstr(online.phase,"RESULT")||strstr(online.phase,"CLOSED")?MD_RESULT:MD_PRE_LEAGUE;
  copy(v->name,sizeof(v->name),online.club_name);copy(v->club,sizeof(v->club),online.club_name);copy(v->user_id,sizeof(v->user_id),online.login_id);
  copy(v->title,sizeof(v->title),online.authenticated&&online.environment==MO_TEST?"ONLINEDEV - TEST":"ONLINE LEAGUE");copy(v->subtitle,sizeof(v->subtitle),online.authenticated?"YOUR CLUB. YOUR LEAGUE.":"CONNECT TO YOUR ONLINE CLUB");
  copy(v->phase_label,sizeof(v->phase_label),phase_label());
  char current_date[48];format_date(server_now(),current_date,sizeof(current_date));
  snprintf(v->caption,sizeof(v->caption),"%.26s - %.7s - %.32s",phase_label(),online.league_label,current_date);
    helper(v,"B","BACK");
  if(online.page==MD_REGISTER){v->count=2;copy(v->headline,sizeof(v->headline),"YOUR CLUB. YOUR LEAGUE.");
    helper(v,"A","SELECT");
    helper(v,"X","RECONNECT");}
  else if(online.page==MD_LEAGUES){
    v->picker_category=manager_club_category_at(online.focus);
    copy(v->headline,sizeof(v->headline),"SELECT LEAGUE");v->total=manager_club_category_count();v->first=online.focus/5*5;v->count=v->total>v->first?v->total-v->first:0;if(v->count>5)v->count=5;
    for(uint32_t i=0;i<v->count;i++){const ExhibitionTeamCategory *c=&exhibition_team_categories[manager_club_category_at(v->first+i)];row(v,i,c->label,"","",c->badge_slot);}
    helper(v,"A","CONFIRM");helper(v,"L","PREV PAGE");helper(v,"R","NEXT PAGE");
  }else if(online.page==MD_CLUB){
    const uint32_t category=manager_club_category(online.category)?online.category:manager_club_category_at(0);
    v->picker_category=category;
    const ExhibitionTeamCategory *c=category<EXHIBITION_TEAM_CATEGORY_COUNT?&exhibition_team_categories[category]:NULL;copy(v->headline,sizeof(v->headline),"SELECT CLUB");v->focus=online.club_choice;v->total=c?c->team_count:0;v->first=online.club_choice/5*5;v->count=v->total>v->first?v->total-v->first:0;if(v->count>5)v->count=5;
    for(uint32_t i=0;i<v->count;i++){uint32_t team=c->teams[v->first+i];row(v,i,exhibition_team_catalog_name(team),"","",exhibition_team_catalog_badge(team));}helper(v,"A","CONFIRM");helper(v,"L","PREV PAGE");helper(v,"R","NEXT PAGE");
  }else if(online.page==MD_NAME||online.page==MD_LOGIN){
    int creating=online.page==MD_NAME;copy(v->headline,sizeof(v->headline),creating?"CREATE YOUR ONLINE CLUB":"WELCOME BACK");copy(v->caption,sizeof(v->caption),creating?"YOUR ONLINE MANAGER ACCOUNT":"LOG IN WITH YOUR USER ID AND PIN");
    v->count=creating?4:3;
    if(creating)row(v,0,"TEAM NAME","Your online club name",online.club_name[0]?online.club_name:"ENTER NAME",0);
    row(v,creating?1:0,"USER ID","3-24 letters, numbers, dot or underscore",online.login_id[0]?online.login_id:"ENTER USER ID",0);
    row(v,creating?2:1,"4-DIGIT PIN","",pin_confirmed?"****":"ENTER PIN",0);row(v,creating?3:2,creating?"CREATE CLUB":"LOGIN","","",0);
    helper(v,"A","SELECT");
  }else if(online.page==MD_DASHBOARD||online.page==MD_LOGOUT){
    md_hub_fill(v,hub_phase(),server_now(),hub_phase_end(),online.league_label);
    v->hub_live=hub_live_count();
    if(online.calendar_conflict)copy(v->rows[0].value,sizeof(v->rows[0].value),"REGISTERED - STATUS SYNCING");
    v->league_points=online.league_points;v->club_rank=online.club_rank;
    if(hub_phase()!=MH_REGISTRATION){v->table_preview_count=online.standing_count<3?online.standing_count:3;
      for(uint32_t i=0;i<v->table_preview_count;i++)v->table_preview[i]=online.standings[i];}
    if(!online.tab){v->news_preview_count=online.news_count;if(online.news_count)v->news_preview=online.news[(online.mono/7000)%online.news_count];}
    helper(v,"L","PREV TAB");helper(v,"R","NEXT TAB");helper(v,"A","OPEN");
    helper(v,"Y",online.environment==MO_TEST&&online.demo_time?"DEMO TIME":"REFRESH");
  }else if(online.page==MD_CLUB_PROFILE){profile_view(v);
  }else if(online.page==MD_OPPONENT_PROFILE){
    v->badge=exhibition_team_catalog_badge(online.opponent_team);copy(v->headline,sizeof(v->headline),online.opponent_name);copy(v->club,sizeof(v->club),exhibition_team_catalog_name(online.opponent_team));
    v->roster_size=online.player_count;v->club_rank=online.opponent_rank;v->league_points=online.opponent_points;v->club_rating=online.opponent_rating;v->count=v->total=3;
    row(v,0,"GAME PLAN","Latest published formation and starting eleven","OPEN",0);row(v,1,"REGISTERED SQUAD","Players and positions in the published squad","OPEN",0);row(v,2,"MATCH HISTORY","This club's fixtures and replays","OPEN",0);helper(v,"A","OPEN");
  }else if(online.page==MD_REWARDS){
    static const char *const labels[]={"STARTING WALLET","LEAGUE PARTICIPATION","CHAMPION","SECOND PLACE","THIRD PLACE"};
    static const char *const values[]={"5,000 NX CASH","1,500 NX CASH","5,000 NX CASH","4,000 NX CASH","3,000 NX CASH"};
    copy(v->headline,sizeof(v->headline),"LEAGUE REWARDS");v->count=v->total=5;
    for(uint32_t i=0;i<5;i++)row(v,i,labels[i],i==0?"Once when you create your manager account":i==1?"Once per league joined; no duplicate carry-over bonus":"Paid by the server on Sunday after official results",values[i],0);
    helper(v,"LS","SCROLL");
  }else if(online.page==MD_PAYMENT_RECOVERY){
    copy(v->headline,sizeof(v->headline),"RESUME YOUR PURCHASE");v->count=v->total=2;
    row(v,0,"CHECK PURCHASE","Look up the saved request and paid pack","CHECK",0);
    row(v,1,"RESUME PURCHASE","Same original purchase and request ID; no new charge","RETRY",0);
    helper(v,"A","SELECT");helper(v,"Y","CHECK STATUS");
  }else if(online.page==MD_ONLINEDEV){
    copy(v->headline,sizeof(v->headline),"ONLINEDEV - DEMO TIME");v->count=v->total=2;
    if(online.clock_intent.magic){
      row(v,0,"CHECK TEST OPERATION","Recover the saved server operation","CHECK",0);
      row(v,1,"RETRY SAME OPERATION","Uses the same request ID; no second advance","RETRY",0);
    }else{
      row(v,0,"NEXT MILESTONE","Next prep, registration close, kickoff or full time","ADVANCE",0);
      row(v,1,"FINISH THIS REAL WEEK","Process both leagues through Sunday rewards","ADVANCE",0);
    }
    helper(v,"A","SELECT");helper(v,"Y","REFRESH");
  }else if(online.page==MD_PROMOTION){
    copy(v->headline,sizeof(v->headline),"PROMOTION CODE");v->count=v->total=2;
    if(online.promo_intent.magic){
      row(v,0,"CHECK REDEMPTION","Recover the saved code transaction","CHECK",0);
      row(v,1,"RETRY SAME CODE","Uses the same request ID; no duplicate credit","RETRY",0);
    }else{
      row(v,0,"ENTER PROMOTION CODE","",online.promo_code[0]?"CODE ENTERED":"ENTER CODE",0);
      row(v,1,"REDEEM CODE","","REDEEM",0);
    }
    helper(v,"A","SELECT");if(online.promo_intent.magic)helper(v,"Y","CHECK STATUS");
  }else if(online.page==MD_PURCHASE_HISTORY){
    copy(v->headline,sizeof(v->headline),"PURCHASED PLAYERS");view_list(v,online.purchases,online.purchases_count,5);
    helper(v,"L","PREV PAGE");helper(v,"R","NEXT PAGE");
    if(!v->count)copy(v->summary,sizeof(v->summary),"NO PURCHASED PLAYERS YET");
  }else if(online.page==MD_PLAN_RESERVES){
    unsigned indices[MO_PLAYERS],count=plan_reserves(indices);MdRow rows[MO_PLAYERS]={0};
    for(unsigned i=0;i<count;i++)rows[i]=online.players[indices[i]].row;
    copy(v->headline,sizeof(v->headline),"RESERVES");view_list(v,rows,count,5);helper(v,"A","ADD TO SQUAD");
    if(!count)copy(v->summary,sizeof(v->summary),"ALL OWNED PLAYERS ARE IN YOUR SQUAD");
  }else if(online.page==MD_TEAM_INFO||online.page==MD_COLLECTION_PAGE){
    copy(v->headline,sizeof(v->headline),online.page==MD_TEAM_INFO?"REGISTERED SQUAD":"YOUR PLAYER COLLECTION");
    if(online.opponent)snprintf(v->headline,sizeof(v->headline),"%.48s - SQUAD",online.opponent_name);
    MdRow rows[MO_PLAYERS];for(uint32_t i=0;i<online.player_count;i++)rows[i]=online.players[i].row;view_list(v,rows,online.player_count,5);
    helper(v,"A","PLAYER");
    if(!online.opponent)helper(v,"X","COLLECTION");
  }else if(online.page==MD_CLUB_PLAN||online.page==MD_PLAN_SETTINGS){
    copy(v->headline,sizeof(v->headline),online.opponent?online.opponent_name:"YOUR GAME PLAN");memcpy(v->plan_players,online.plan_players,sizeof(v->plan_players));memcpy(v->plan_dots,online.plan_dots,sizeof(v->plan_dots));
    v->plan_count=online.opponent?18:online.plan_count;v->plan_field_focus=online.plan_field_focus;v->plan_bench_focus=online.plan_bench_focus;
    v->plan_condition=online.plan_condition;v->plan_editable=!online.opponent;v->plan_dirty=online.plan_dirty;v->plan_pick=online.plan_pick;v->plan_move=online.plan_move;v->plan_pending=online.plan_save_pending;v->focus=online.plan_focus;
    copy(v->plan_formation,sizeof(v->plan_formation),fnx_gameplan_shapes[online.plan.formation].label);
    copy(v->summary,sizeof(v->summary),online.opponent?"USING THE LATEST SAVED TEAM DATA":online.plan_save_pending?"DRAFT KEPT - CHECK SAVE STATUS OR RETRY":online.plan_move?"RELEASE A TO DROP THE PLAYER":online.plan_dirty?"CHANGES SAVE WHEN YOU LEAVE":"SELECT A PLAYER TO SWAP WITH A TEAMMATE");
    if(online.page==MD_PLAN_SETTINGS){
      v->plan_menu=online.plan_menu;v->plan_picker=online.plan_picker;v->focus=online.focus;
      v->total=online.plan_picker?(online.plan_menu==1?FNX_GAMEPLAN_SHAPE_COUNT+1:plan_picker_count()):online.plan_menu==3?9:4;
      unsigned visible=online.plan_picker?(online.plan_menu==1?5:7):9;
      v->first=online.focus>visible/2?online.focus-visible/2:0;if(v->total<=visible)v->first=0;else if(v->first+visible>v->total)v->first=v->total-visible;
      v->count=v->total-v->first;if(v->count>visible)v->count=visible;
      static const char *const tactics[]={"MENTALITY","TEMPO","PRESSING","DEFENSIVE LINE"};
      static const char *const forms[]={"PLAYING STYLE","TEAM SHAPE","OFFSIDE TRAP","SUBSTITUTIONS"};
      static const char *const duties[]={"CAPTAIN","RIGHT CORNER KICK","LEFT CORNER KICK","LONG FREE KICK","SHORT FREE KICK","PENALTY KICK","SET-PIECE ATTACKER 1","SET-PIECE ATTACKER 2","SET-PIECE ATTACKER 3"};
      for(unsigned i=0;i<v->count;i++){
        unsigned at=v->first+i;MdRow *r=&v->plan_rows[i];r->enabled=1;MoPlayer *p=NULL;
        if(online.plan_picker&&online.plan_menu==1){copy(r->label,sizeof(r->label),at<FNX_GAMEPLAN_SHAPE_COUNT?fnx_gameplan_shapes[at].label:"RESET DEFAULT");r->selected=at==online.plan.formation;}
        else if(online.plan_menu==1){copy(r->label,sizeof(r->label),forms[at]);copy(r->value,sizeof(r->value),at==0?mo_tactics[0][online.plan.tactics[0]]:at==1?v->plan_formation:at==2?(online.plan.offside?"ON":"OFF"):(online.plan.auto_subs?"ON":"OFF"));}
        else if(online.plan_menu==2){copy(r->label,sizeof(r->label),tactics[at]);copy(r->value,sizeof(r->value),mo_tactics[at][online.plan.tactics[at]]);}
        else if(online.plan_picker){p=find_instance(plan_picker_id(at));copy(r->label,sizeof(r->label),p?p->row.label:"NONE");r->selected=online.plan.duties[online.plan_menu_focus]==(p?p->instance:0);}
        else {p=find_instance(online.plan.duties[at]);copy(r->label,sizeof(r->label),duties[at]);snprintf(r->value,sizeof(r->value),"%.39s",p?p->row.label:"NONE");}
        if(p){r->identity=p->row.identity;r->portrait=p->row.portrait;r->role=p->row.role;r->rating=p->row.rating;}
      }
      helper(v,"A","SELECT");
    }else if(!online.opponent){
      v->helper_count=0;
      helper(v,"A",online.plan_focus<MO_PLAYERS?"SWAP":"SELECT");
      helper(v,"B",online.plan_save_pending?"RETRY SAVE":online.plan_focus<MO_PLAYERS?"BACK":"SAVE & BACK");
      if(online.plan_save_pending){helper(v,"X","RELOAD");helper(v,"Y","CHECK SAVE");}
      else {if(online.plan_focus<18)helper(v,"X","RESERVES");if(online.plan_focus<11)helper(v,"Y","CHANGE ROLE");helper(v,"R",online.plan_condition?"POSITIONS":"CONDITION");}
    }
  }else if(online.page==MD_SHOP||online.page==MD_SHOP_CLUBS){
    unsigned list[MO_OFFERS],count=online.page==MD_SHOP_CLUBS?shop_clubs(list):shop_sizes(list),at=0;
    if(online.page==MD_SHOP_CLUBS)at=online.shop_focus<count?online.shop_focus:0;
    else {while(at<count&&list[at]!=online.offer_focus)at++;if(at==count)at=0;}
    copy(v->headline,sizeof(v->headline),online.page==MD_SHOP_CLUBS?"CHOOSE CLUB PACK":"CHOOSE PACK SIZE");
    v->first=at/3*3;v->count=count-v->first;if(v->count>3)v->count=3;v->focus=at%3;v->total=count;
    for(uint32_t i=0;i<v->count;i++){
      const MoOffer *o=&online.offers[list[v->first+i]];
      row(v,i,online.page==MD_SHOP_CLUBS?"CLUB PACK":o->tier,"","",exhibition_team_catalog_badge(o->team));v->rows[i].team_id=o->team;
      if(online.page==MD_SHOP_CLUBS){
        unsigned sizes=0,ready=0;for(unsigned j=0;j<online.offer_count;j++)if(online.offers[j].team==o->team){sizes++;ready+=online.offers[j].available;}
        snprintf(v->rows[i].detail,sizeof(v->rows[i].detail),"%u PACK SIZES",sizes);
        copy(v->rows[i].value,sizeof(v->rows[i].value),ready?"SELECT CLUB":!strcmp(o->unavailable,"CATALOG_NOT_READY")?"CATALOG NOT READY":"VIEW SIZES");
      }else{
        snprintf(v->rows[i].detail,sizeof(v->rows[i].detail),"%u PLAYERS FROM A POOL OF %u",o->draw,o->pool);
        snprintf(v->rows[i].value,sizeof(v->rows[i].value),"%u NX CASH",o->price);
        if(!o->available)copy(v->rows[i].value,sizeof(v->rows[i].value),!strcmp(o->unavailable,"OFFER_ALREADY_PURCHASED")?"CLAIMED":"UNAVAILABLE");
      }
    }
    helper(v,"LEFT","SELECT");helper(v,"A",online.pay_uncertain?"PAYMENT RECOVERY":online.page==MD_SHOP_CLUBS?"PACK SIZES":"VIEW PACK");
    helper(v,"X","PROMOTION CODE");helper(v,"Y","PURCHASE HISTORY");
  }else if(online.page==MD_PACK||online.page==MD_PACK_BUY||online.page==MD_PACK_SELECT||online.page==MD_PACK_OPENING||online.page==MD_PACK_RESULT){
    const MoOffer *offer=NULL;
    if(online.page==MD_PACK||online.page==MD_PACK_BUY){if(online.offer_focus<online.offer_count)offer=&online.offers[online.offer_focus];}
    else for(uint32_t i=0;i<online.offer_count;i++)if(online.offers[i].id==online.pending_offer){offer=&online.offers[i];break;}
    v->badge=offer?exhibition_team_catalog_badge(offer->team):0;copy(v->headline,sizeof(v->headline),offer?offer->name:"YOUR PAID PACK");
    v->pack_pool=online.page==MD_PACK||online.page==MD_PACK_BUY?(offer?offer->pool:0):online.pool_count;
    v->pack_draw=online.page==MD_PACK||online.page==MD_PACK_BUY?(offer?offer->draw:0):online.draw;
    v->pack_price=online.page==MD_PACK||online.page==MD_PACK_BUY?(offer?offer->price:0):online.paid_amount;
    v->pack_selected=online.selected;v->pack_selection_count=selected_count();v->pack_opening_ms=(uint32_t)(online.mono-online.opening_at);
    if(online.page==MD_PACK_OPENING||online.page==MD_PACK_SELECT||online.page==MD_PACK_RESULT){v->helper_count=0;uint32_t n=0;for(uint32_t i=0;i<online.pool_count;i++)if(online.page!=MD_PACK_RESULT||(online.selected&(1u<<i)))v->pack_players[n++]=online.pool[i].row;v->pack_count=n;}
    helper(v,"A",online.page==MD_PACK?"BUY":online.page==MD_PACK_RESULT?"CONTINUE":online.page==MD_PACK_SELECT&&online.focus==online.pool_count?"CONFIRM":"SELECT");
    if(online.page==MD_PACK_SELECT)helper(v,"Y","PURCHASE HISTORY");
  }else if(online.page==MD_TEAM_HISTORY){
    copy(v->headline,sizeof(v->headline),"MATCH HISTORY");v->count=online.history_count;v->total=online.history_total;
    v->first=(online.history_page?online.history_page-1:0)*5;v->focus=v->first+online.focus;
    for(unsigned i=0;i<v->count;i++)v->rows[i]=online.history_matches[i].row;
    helper(v,"L","PREV PAGE");helper(v,"R","NEXT PAGE");helper(v,"A","REPLAY");
  }else if(online.page==MD_SCHEDULE){
    uint32_t list[MO_MATCHES],n=group_matches(list);if(online.focus>=n)online.focus=n?n-1:0;v->focus=online.focus;v->first=online.focus/6*6;v->count=n-v->first;if(v->count>6)v->count=6;v->total=n;v->match_group=online.match_group;
    uint64_t club=online.opponent?online.opponent_id:strtoull(online.club_id,NULL,10);
    for(uint32_t i=0;i<online.match_count;i++)if(!online.history||online.matches[i].home_club==club||online.matches[i].away_club==club)v->match_groups[online.matches[i].phase==1?0:online.matches[i].phase==0?1:2]++;
    for(uint32_t i=0;i<v->count;i++)v->rows[i]=online.matches[list[v->first+i]].row;
    helper(v,"L","PREV SECTION");
    helper(v,"R","NEXT SECTION");
    helper(v,"A","WATCH");
    helper(v,"Y","REFRESH");
  }else if(online.page==MD_LEAGUE_TIMELINE){
    copy(v->headline,sizeof(v->headline),"YOUR LEAGUE TIMELINE");v->total=6;v->first=online.focus/5*5;v->count=6-v->first;if(v->count>5)v->count=5;
    const char *const labels[]={"CURRENT WINDOW","REGISTRATION CLOSES","MATCHES START","MATCHES FINISH","REWARDS","NEXT REGISTRATION"};
    const char *const defaults[]={phase_label(),!strcmp(online.league_label,"W2")?"Thursday 23:59 WIB":"Monday 23:59 WIB",!strcmp(online.league_label,"W2")?"Saturday - time TBC":"Wednesday - time TBC","After the final match","Sunday - time TBC","Monday / Thursday"};
    uint64_t moments[]={0,online.registration_close,online.match_day_start,online.match_day_end,online.rewards_at,online.next_registration};
    for(uint32_t i=0;i<v->count;i++){unsigned at=v->first+i;char date[48];if(moments[at])format_date(moments[at],date,sizeof(date));else copy(date,sizeof(date),defaults[at]);
      row(v,i,labels[at],at==0?(online.calendar_conflict?"Your entry is syncing. Your scheduled matches are available.":online.joined?"Your club is registered for this window":"Your club is not registered for this window"):moments[at]?"Confirmed league schedule":"Weekly schedule - exact time to be confirmed",date,0);}
    helper(v,"LS","SCROLL");
  }else if(online.page==MD_WATCH)watch_view(v);
  else if(online.page==MD_RULES){
    md_hub_rules(v,online.focus);helper(v,"LS","SCROLL");
  }else if(online.page==MD_WEEK_SCHEDULE){
    md_hub_calendar(v,server_now());helper(v,"LS","SCROLL");
  }else if(online.page==MD_NEWS||online.page==MD_PLAYER_FEED){
    int players=online.page==MD_PLAYER_FEED;const MdFeedItem *items=players?online.player_feed[online.feed_section]:online.activity;
    uint32_t count=players?online.player_feed_count[online.feed_section]:online.activity_count;
    if(online.focus>=count)online.focus=count?count-1:0;
    v->focus=online.focus;v->first=online.focus/3*3;v->count=count-v->first;if(v->count>3)v->count=3;v->total=count;
    for(uint32_t i=0;i<v->count;i++)v->feed[i]=items[v->first+i];
    v->feed_section=online.feed_section;memcpy(v->feed_totals,online.player_feed_count,sizeof(v->feed_totals));
    copy(v->headline,sizeof(v->headline),players?"PLAYER FEED":"CLUB FEED");
    copy(v->summary,sizeof(v->summary),players?(online.feed_section?"Rising Stars: match OVR 69 or below, ranked by goal contributions.":"Top scorers in this league - published match events only."):"");
    copy(v->empty_detail,sizeof(v->empty_detail),players?"No qualifying performances have been published yet.":"No club activity has been published yet.");
    helper(v,"LS","SCROLL");helper(v,"L",players?"PREV LIST":"PREV PAGE");helper(v,"R",players?"NEXT LIST":"NEXT PAGE");helper(v,"Y","REFRESH");
  }else if(online.page==MD_OVERALL){
    copy(v->headline,sizeof(v->headline),"LEAGUE RANKING");view_list(v,online.rows,online.row_count,5);
    v->ranking_section=online.rank_section;v->ranking_offset=(online.rank_page?online.rank_page-1:0)*MO_RANK_PAGE_SIZE;
    v->total=online.rank_total;v->rank_reset_ms=online.rank_ends;
    copy(v->season_label,sizeof(v->season_label),online.rank_season);
    copy(v->summary,sizeof(v->summary),online.rank_section?"ONE CHAMPION PER COMPLETED MONTH":"PARTICIPATION AND PODIUM POINTS ACCUMULATE THIS MONTH");
    copy(v->empty_detail,sizeof(v->empty_detail),online.rank_section?"No completed monthly seasons yet.":"No participants in this monthly season yet.");
    if(online.rank_ends&&server_now()>=online.rank_ends){
      v->count=v->first=v->total=v->ranking_offset=0;v->rank_reset_ms=md_season_end(server_now());
      md_season_text(server_now(),v->season_label,sizeof(v->season_label),0);
      copy(v->empty_detail,sizeof(v->empty_detail),"A new season has started. Refresh to load its ranking.");
    }
    helper(v,"LS","SCROLL");helper(v,"L","PREV TAB");helper(v,"R","NEXT TAB");helper(v,"Y","REFRESH");
  }else{
    copy(v->headline,sizeof(v->headline),online.page==MD_TABLE?"LEAGUE STANDINGS":online.page==MD_TEAMS_PAGE?"LEAGUE CLUBS":online.page==MD_CHAMPIONS?"LEAGUE RANKING HISTORY":online.page==MD_PLAYER_INFO?"CLUB PROFILE":"CLUB NEWS");
    view_list(v,online.rows,online.row_count,5);
    if(!online.row_count){copy(v->summary,sizeof(v->summary),online.page==MD_TABLE?"The league table is published after registration closes.":"No published records yet.");copy(v->empty_detail,sizeof(v->empty_detail),online.page==MD_TABLE?"Registration: Mon/Thu. Preparation: Tue/Fri. Matches: Wed/Sat.":"Return after your league publishes its first results.");}
    if(online.page==MD_TABLE||online.page==MD_TEAMS_PAGE||online.page==MD_OVERALL){helper(v,"A","CLUB PROFILE");helper(v,"Y","REFRESH");}
  }
  v->pin_open=pin_active;v->pin_cursor=pin_cursor;v->pin_length=pin_length;v->pin_confirming=pin_confirming;v->pin_creating=pin_creating;
  if(pin_active){v->helper_count=0;
    helper(v,"B","CANCEL");
    helper(v,"X","DELETE");
    helper(v,"A","SELECT");}
  if(online.page==MD_PACK_BUY||online.page==MD_LOGOUT){
    if(online.page==MD_LOGOUT)v->focus=online.hub_focus;
    v->modal.open=1;v->modal.selected=online.focus;v->modal.destructive=online.page==MD_LOGOUT;
    copy(v->modal.title,sizeof(v->modal.title),online.page==MD_LOGOUT?"LOG OUT OF YOUR CLUB?":"OPEN THIS PACK?");
    if(online.page==MD_LOGOUT)copy(v->modal.body,sizeof(v->modal.body),"Your club, players and paid purchases remain on the server.");
    else snprintf(v->modal.body,sizeof(v->modal.body),"Pay %u NX Cash now, then choose %u from %u players. Your paid pack resumes if the game closes.",v->pack_price,v->pack_draw,v->pack_pool);
    copy(v->modal.accept,sizeof(v->modal.accept),online.page==MD_LOGOUT?"LOGOUT":"PAY & OPEN");v->helper_count=0;
    helper(v,"B","CANCEL");
    helper(v,"A","SELECT");
  }
  if(online.join_confirm){
    v->modal.open=1;v->modal.selected=online.join_choice;
    snprintf(v->modal.title,sizeof(v->modal.title),"REGISTER FOR LEAGUE %s?",online.league_label);
    copy(v->modal.body,sizeof(v->modal.body),"Enter this league with your club and receive 1,500 NX Cash once. Prepare your squad before Match Day.");
    copy(v->modal.accept,sizeof(v->modal.accept),"REGISTER");v->helper_count=0;helper(v,"B","CANCEL");helper(v,"A","SELECT");
  }
  if(online.clock_confirm){
    v->modal.open=1;v->modal.selected=online.clock_choice;v->modal.destructive=0;
    copy(v->modal.title,sizeof(v->modal.title),"ADVANCE TEST TIME?");
    copy(v->modal.body,sizeof(v->modal.body),online.clock_confirm==2?"Finish this TEST week through Sunday rewards. Only TEST data is processed by the server.":"Move to the next TEST calendar milestone. The server processes fixtures and rewards before confirming.");
    copy(v->modal.accept,sizeof(v->modal.accept),"ADVANCE");v->helper_count=0;helper(v,"B","CANCEL");helper(v,"A","SELECT");
  }
  if(!v->modal.open&&!v->pin_open&&v->helper_count<6)helper(v,"ZL","INFO");
  if(online.plan_discard){v->modal.open=1;v->modal.selected=online.focus;v->modal.destructive=1;copy(v->modal.title,sizeof(v->modal.title),"DISCARD YOUR DRAFT?");copy(v->modal.body,sizeof(v->modal.body),"Reload the latest saved Game Plan from the server. Your unsaved changes will be discarded only after the reload succeeds.");copy(v->modal.accept,sizeof(v->modal.accept),"RELOAD");v->helper_count=0;helper(v,"B","CANCEL");helper(v,"A","SELECT");}
  if(online.notice[0]){v->modal.open=1;v->modal.information=1;copy(v->modal.title,sizeof(v->modal.title),online.notice_title);copy(v->modal.body,sizeof(v->modal.body),online.notice);copy(v->modal.accept,sizeof(v->modal.accept),"OK");v->helper_count=0;
    helper(v,"A","OK");}
  pthread_mutex_unlock(&ui_mutex);
}
void manager_online_audio_frame(ManagerLeagueAudioFrame *out,uint64_t ms){
  if(!out)return;
  memset(out,0,sizeof(*out));pthread_mutex_lock(&ui_mutex);
  out->fixture_token=online.fixture;out->monotonic_ms=ms;out->timeline_serial=online.timeline_serial;
  out->position_ms=online.play_ms;out->replay=online.replay;out->paused=online.paused;
  uint32_t index=online.chunk_ms?online.play_ms/online.chunk_ms:0;
  if(online.chunk_count&&index>=online.chunk_count)index=online.chunk_count-1;
  out->visible_watch=online.active&&online.page==MD_WATCH&&online.chunks[index].valid&&online.chunks[index].index==index;out->event_kind=MLA_EVENT_COUNT;
  for(uint32_t i=0;i<online.event_count;i++)if(online.events[i].at<=online.play_ms){
    out->event_serial=i+1;out->event_at_ms=online.events[i].at;out->event_kind=online.events[i].kind;out->event_side=online.events[i].side;
  }
  pthread_mutex_unlock(&ui_mutex);
}
