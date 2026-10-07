/* Master League's controller-first panels. Included after the base projections
 * so match/save operations remain in one module, with no renderer mutations. */
enum { ML_DRAWER_NONE, ML_DRAWER_SETTING, ML_DRAWER_COUNTRY,
       ML_DRAWER_SQUAD, ML_DRAWER_CLUB, ML_DRAWER_TRANSACTION,
       ML_DRAWER_MARKET_LEAGUE,ML_DRAWER_MARKET_TEAM,ML_DRAWER_OFFER,
       ML_DRAWER_OFFER_ACTIONS,ML_DRAWER_NOTICE,ML_DRAWER_JOB,ML_DRAWER_MY_PLAYER };
enum { ML_SETTING_LEAGUE, ML_SETTING_CLUB, ML_SETTING_DIFFICULTY,
       ML_SETTING_TIME, ML_SETTING_TRANSFER, ML_SETTING_CURRENCY,
       ML_SETTING_SKIP_WINDOW, ML_SETTING_COUNT };
static uint32_t drawer_kind, drawer_focus, drawer_first, drawer_serial;
static uint32_t calendar_day;
static void ml_start_advance(uint32_t from,const char *notice) {
  advance_from=from;advance_to=career.day;
  const uint32_t days=advance_to>=from ? advance_to-from : 0u;
  advance_duration=1100u+(days<30u ? days : 30u)*45u;
  advance_started=frontend_clock;calendar_day=from;
  snprintf(advance_notice,sizeof(advance_notice),"%s",notice);
  toast[0]=0;toast_serial++;
  ml_page(ML_PAGE_ADVANCE);
}
static void ml_begin_advance(uint32_t from,const char *notice) {
  /* Office/simulated events save once before playback. Played results were
   * already saved by their callback and use ml_start_advance on native return. */
  hub_section=0u;ml_page(ML_PAGE_HUB);
  if(ml_autosave())ml_start_advance(from,notice);
}
void ml_frontend_tick(uint64_t milliseconds) {
  frontend_clock=milliseconds;
  if(!session_ready || page!=ML_PAGE_ADVANCE)return;
  const uint64_t elapsed=milliseconds>=advance_started ? milliseconds-advance_started : 0u;
  const uint32_t travel=advance_duration-500u;
  const uint64_t moving=elapsed>250u ? elapsed-250u : 0u;
  const uint32_t delta=advance_to>=advance_from ? advance_to-advance_from : 0u;
  calendar_day=moving>=travel ? advance_to : advance_from+(uint32_t)(moving*delta/travel);
  if(elapsed<advance_duration)return;
  ml_page(ML_PAGE_HUB);
  if(advance_notice[0])ml_toast(advance_notice);
}
static int ml_office_pad(uint32_t pressed);
static void ml_office_view(MlView *v);
static void ml_offer_open(uint32_t index,uint32_t id);
static const char *ml_setting_labels[]={"LEAGUE","CLUB","DIFFICULTY","MATCH TIME",
  "TRANSFER DIFFICULTY","CURRENCY","SKIP FIRST TRANSFER WINDOW"};
static const char *ml_difficulties[]={"BEGINNER","AMATEUR","REGULAR","PROFESSIONAL",
  "TOP PLAYER","SUPER STAR","LEGEND"};
static const char *ml_transfer_levels[]={"NORMAL","EASY","HARD"};
static const char *ml_currencies[]={"EUR","GBP","USD"};
static uint32_t ml_league_badge(uint32_t index) {
  if(index>=FL26_LEAGUE_CATALOG_COUNT)return 0u;
  const uint32_t category=fl26_league_catalog[index].category_index;
  return category<EXHIBITION_TEAM_CATEGORY_COUNT ? exhibition_team_categories[category].badge_slot : 0u;
}

static void ml_review_reset(void) {
  drawer_kind=drawer_focus=drawer_first=0u; drawer_serial++; calendar_day=0u;
  toast[0]=0;toast_serial++;
}
static void ml_drawer_close(void) { drawer_kind=0u; drawer_serial++; }
static void ml_drawer_open(uint32_t kind,uint32_t selected) {
  drawer_kind=kind; drawer_focus=selected; drawer_first=selected/5u*5u;
  drawer_serial++; message[0]=0;
}
static uint32_t ml_setting_value(uint32_t setting) {
  switch(setting) {
    case ML_SETTING_LEAGUE:return league_choice;
    case ML_SETTING_CLUB:return club_choice;
    case ML_SETTING_DIFFICULTY:return setup.difficulty;
    case ML_SETTING_TIME:return setup.match_minutes/5u-1u;
    case ML_SETTING_TRANSFER:return setup_options.transfer_difficulty==1u ? 0u : setup_options.transfer_difficulty==0u ? 1u : 2u;
    case ML_SETTING_CURRENCY:return setup_options.currency;
    case ML_SETTING_SKIP_WINDOW:return setup_options.skip_first_window;
    default:return 0u;
  }
}
static uint32_t ml_drawer_count(void) {
  if(drawer_kind==ML_DRAWER_COUNTRY) return country_count;
  if(drawer_kind==ML_DRAWER_SQUAD) return player_rows;
  if(drawer_kind==ML_DRAWER_CLUB) return career.club_count;
  if(drawer_kind==ML_DRAWER_TRANSACTION) return 2u; /* editable duration + payment */
  if(drawer_kind!=ML_DRAWER_SETTING) return 0u;
  switch(focus) {
    case ML_SETTING_LEAGUE:return league_count;
    case ML_SETTING_CLUB:return ml_league_entry() ? ml_league_entry()->pool_count : 0u;
    case ML_SETTING_DIFFICULTY:return 7u;
    case ML_SETTING_TIME:return 6u;
    case ML_SETTING_TRANSFER:case ML_SETTING_CURRENCY:return 3u;
    default:return 2u;
  }
}
static void ml_select_setting(void) {
  switch(focus) {
    case ML_SETTING_LEAGUE:league_choice=drawer_focus;club_choice=0u;break;
    case ML_SETTING_CLUB:club_choice=drawer_focus;break;
    case ML_SETTING_DIFFICULTY:setup.difficulty=drawer_focus;break;
    case ML_SETTING_TIME:setup.match_minutes=(drawer_focus+1u)*5u;break;
    case ML_SETTING_TRANSFER:setup_options.transfer_difficulty=drawer_focus<2u ? 1u-drawer_focus : 2u;break;
    case ML_SETTING_CURRENCY:setup_options.currency=drawer_focus;break;
    case ML_SETTING_SKIP_WINDOW:setup_options.skip_first_window=drawer_focus;break;
    default:break;
  }
  ml_drawer_close();
}
static void ml_open_plan_editor(void) {
  if(career.office.dismissed){ml_message("MANAGER DISMISSED");return;}
  /* Reuse the native squad bootstrap only. No event/date/wage/fixture advance.
   * The other club supplies the existing split editor's read-only COM pane. */
  uint32_t other=0u;
  for(uint32_t i=0;i<career.league.team_count;i++)
    if(career.league.standings[i].team!=career.settings.club) {other=career.league.standings[i].team;break;}
  if(!other) {ml_message("SQUAD EDITOR UNAVAILABLE");return;}
  pending=(MlEvent){0};pending.home=career.settings.club;pending.away=other;
  match_active=plan_editor=1u;match_swapped=result_received=shootout_winner=0u;
  action=ML_ACTION_MATCH;
}
static void ml_renew_open(uint32_t index) {
  if(index>=career.player_count || career.players[index].club!=career.settings.club)return;
  transaction_player=index;confirm_kind=2u;destination=career.settings.club;
  const uint32_t end=career.players[index].contract_end;
  years=end>=career.season+3u ? end-career.season+1u : 3u;
  if(years>5u)years=5u;
  ml_drawer_open(ML_DRAWER_TRANSACTION,0u);
}
static void ml_open_home_rank(void) {table_scorers=0u;ml_page(ML_PAGE_TABLE);}
static int ml_calendar_leap(uint32_t year) {return year%4u==0u && (year%100u!=0u || year%400u==0u);}
static uint32_t ml_calendar_month_days(uint32_t month,uint32_t year) {
  static const uint32_t days[]={31u,28u,31u,30u,31u,30u,31u,31u,30u,31u,30u,31u};
  return days[month-1u]+(month==2u && ml_calendar_leap(year));
}
static void ml_calendar_date(uint32_t day,uint32_t *year,uint32_t *month,uint32_t *date) {
  *year=2025u+career.season;*month=7u;
  while(day>=ml_calendar_month_days(*month,*year)) {
    day-=ml_calendar_month_days(*month,*year);
    if(++*month==13u){*month=1u;(*year)++;}
  }
  *date=day+1u;
}
static uint32_t ml_calendar_weekday(uint32_t year,uint32_t month) {
  static const uint32_t offsets[]={0u,3u,2u,5u,0u,3u,5u,1u,4u,6u,2u,4u};
  if(month<3u) year--;
  return (year+year/4u-year/100u+year/400u+offsets[month-1u]+7u)%7u; /* Monday = 0 */
}
static void ml_calendar_move(int change,int month_step) {
  uint32_t y,m,d;ml_calendar_date(calendar_day,&y,&m,&d);
  int next=(int)calendar_day+change;
  if(month_step) {
    const int first=(int)calendar_day-(int)d+1;
    if(month_step>0) next=first+(int)ml_calendar_month_days(m,y);
    else {
      if(m==1u){m=12u;y--;}else m--;
      next=first-(int)ml_calendar_month_days(m,y);
    }
  }
  const int last=364+ml_calendar_leap(2026u+career.season);
  calendar_day=next<0 ? 0u : next>last ? (uint32_t)last : (uint32_t)next;
}
static int ml_review_pad(uint32_t pressed) {
  if(page==ML_PAGE_CONFIRM && (pressed&(ML_LEFT|ML_RIGHT))) {
    focus=(pressed&ML_RIGHT) ? 1u : 0u;return 1;
  }
  if(ml_office_pad(pressed))return 1;
  if(drawer_kind) {
    if(pressed&ML_B) {ml_drawer_close();return 1;}
    if(drawer_kind==ML_DRAWER_TRANSACTION && !drawer_focus && (pressed&(ML_LEFT|ML_RIGHT))) {
      if((pressed&ML_LEFT) && years>1u)years--;
      if((pressed&ML_RIGHT) && years<5u)years++;
      return 1;
    }
    const uint32_t count=ml_drawer_count();
    if(pressed&(ML_UP|ML_DOWN|ML_L|ML_R)) {
      const uint32_t step=pressed&(ML_L|ML_R) ? 5u : 1u;
      if(count) drawer_focus=pressed&(ML_UP|ML_L) ? (drawer_focus>=step ? drawer_focus-step : 0u)
          : (drawer_focus+step<count ? drawer_focus+step : count-1u);
      if(drawer_focus<drawer_first) drawer_first=drawer_focus;
      if(drawer_focus>=drawer_first+5u) drawer_first=drawer_focus-4u;
      return 1;
    }
    if(!(pressed&ML_A) || !count) return 1;
    if(drawer_kind==ML_DRAWER_SETTING) ml_select_setting();
    else if(drawer_kind==ML_DRAWER_COUNTRY) {nationality=countries[drawer_focus];ml_drawer_close();}
    else if(drawer_kind==ML_DRAWER_CLUB) {
      market_club=career.clubs[drawer_focus].team;
      if(destination) {destination=market_club;confirm_kind=1u;years=3u;ml_drawer_open(ML_DRAWER_TRANSACTION,2u);}
      else {ml_drawer_close();ml_refresh_players(market_club);ml_page(ML_PAGE_MARKET_PLAYERS);}
    } else if(drawer_kind==ML_DRAWER_TRANSACTION) {
      if(!drawer_focus)drawer_focus=1u;
      else {
        const char *error=confirm_kind==2u ? ml_renew(&career,transaction_player,years)
            : ml_transfer(&career,transaction_player,destination,years);
        if(*error) ml_message(error);
        else {ml_drawer_close();ml_refresh_players(page==ML_PAGE_MARKET_PLAYERS ? market_club : career.settings.club);
          if(focus>=player_rows) focus=player_rows ? player_rows-1u : 0u;
          if(ml_autosave()) ml_toast(confirm_kind==2u ? "Contract renewed - signing fee paid" : "Transfer completed");}
      }
    }
    return 1;
  }
  if(page==ML_PAGE_SETTINGS) {
    const uint32_t first=session_ready ? 2u : 0u;
    if(focus<first)focus=first;
    if(pressed&ML_B) {ml_page(session_ready ? ML_PAGE_HUB : ML_PAGE_LANDING);return 1;}
    if(pressed&ML_UP) {if(focus>first)focus--;return 1;}
    if(pressed&ML_DOWN) {if(focus<ML_SETTING_COUNT)focus++;return 1;}
    if((pressed&(ML_LEFT|ML_RIGHT)) && focus>=2u && focus<ML_SETTING_COUNT) {
      const uint32_t count=focus==2u ? 7u : focus==3u ? 6u : focus==6u ? 2u : 3u;
      drawer_focus=(ml_setting_value(focus)+count+((pressed&ML_RIGHT) ? 1u : count-1u))%count;
      ml_select_setting();return 1;
    }
    if(pressed&ML_A) {
      if(focus<2u) ml_drawer_open(ML_DRAWER_SETTING,ml_setting_value(focus));
      else if(focus<ML_SETTING_COUNT)return 1;
      else if(session_ready) {
        setup.condition=5u;career.settings=setup;career.options=setup_options;ml_page(ML_PAGE_HUB);ml_autosave();
      } else ml_page(ML_PAGE_MANAGER);
    }
    return 1;
  }
  if(page==ML_PAGE_MANAGER && (pressed&ML_A) && focus==1u) {
    uint32_t selected=0u;
    for(uint32_t i=0;i<country_count;i++)if(countries[i]==nationality)selected=i;
    ml_drawer_open(ML_DRAWER_COUNTRY,selected);return 1;
  }
  if(page==ML_PAGE_HUB) {
    if(pressed&ML_B)return 0;
    const uint32_t old=hub_section;
    const int bottom=focus>=2u;
    if(pressed&ML_UP)focus=focus==4u ? 1u : focus==3u ? 1u : 0u;
    else if(pressed&ML_DOWN)focus=focus==1u ? 4u : focus<2u ? 2u : focus;
    else if(pressed&(ML_L|ML_R)) {
      if((pressed&ML_L) && hub_section)hub_section--;
      if((pressed&ML_R) && hub_section<3u)hub_section++;
      focus=bottom ? 2u : 0u;
    } else if(pressed&ML_LEFT) {
      if(focus==1u || focus>2u)focus--;
      else if(hub_section){hub_section--;focus=bottom ? 4u : 1u;}
    } else if(pressed&ML_RIGHT) {
      if(focus==0u || (focus>=2u && focus<4u))focus++;
      else if(hub_section<3u){hub_section++;focus=bottom ? 2u : 0u;}
    } else if(pressed&ML_X) {if(ml_autosave())ml_toast("Career saved");}
    else if(pressed&ML_A) {
      if(focus==3u) {
        if(hub_section==1u){ml_page(ML_PAGE_SQUAD);ml_refresh_players(career.settings.club);}
        else if(hub_section==2u)ml_page(ML_PAGE_MANAGER_OFFICE);
        else ml_open_home_rank();
      } else ml_hub_open(focus==4u ? 3u : focus);
      if(page==ML_PAGE_CALENDAR) calendar_day=career.day;
    }
    if(old!=hub_section){slide_direction=hub_section>old ? 1 : -1;navigation_serial++;message[0]=0;}
    return 1;
  }
  if(page==ML_PAGE_CALENDAR) {
    if(pressed&ML_B){ml_page(ML_PAGE_HUB);return 1;}
    if(pressed&ML_L)ml_calendar_move(0,-1);
    else if(pressed&ML_R)ml_calendar_move(0,1);
    else if(pressed&ML_LEFT)ml_calendar_move(-1,0);
    else if(pressed&ML_RIGHT)ml_calendar_move(1,0);
    else if(pressed&ML_UP)ml_calendar_move(-7,0);
    else if(pressed&ML_DOWN)ml_calendar_move(7,0);
    return 1;
  }
  if(page==ML_PAGE_SQUAD || page==ML_PAGE_MARKET_CLUBS) {
    if(pressed&ML_B){destination=0u;ml_page(ML_PAGE_HUB);return 1;}
    if(pressed&(ML_UP|ML_LEFT))focus=0u;
    else if(pressed&(ML_DOWN|ML_RIGHT))focus=1u;
    else if(pressed&ML_A) {
      if(page==ML_PAGE_SQUAD) {
        if(focus)ml_open_plan_editor();
        else {ml_refresh_players(career.settings.club);ml_drawer_open(ML_DRAWER_SQUAD,0u);}
      } else if(focus) {market_club=0u;ml_refresh_players(0u);ml_page(ML_PAGE_MARKET_PLAYERS);}
      else {destination=0u;ml_drawer_open(ML_DRAWER_CLUB,0u);}
    }
    return 1;
  }
  if((page==ML_PAGE_CONTRACTS || page==ML_PAGE_MARKET_PLAYERS) && (pressed&ML_A)) {
    if(focus>=player_rows) return 1;
    transaction_player=row_players[focus];years=3u;
    confirm_kind=page==ML_PAGE_CONTRACTS ? 2u : 1u;
    if(confirm_kind==1u)ml_offer_open(transaction_player,0u);
    else ml_renew_open(transaction_player);
    return 1;
  }
  /* Confirmation dialogs use the same left/right action navigation as buttons. */
  if(page==ML_PAGE_CONFIRM && (pressed&(ML_LEFT|ML_RIGHT))) {
    focus=pressed&ML_RIGHT ? 1u : 0u;return 1;
  }
  return 0;
}

static void ml_setting_row(MlViewRow *r,uint32_t index) {
  memset(r,0,sizeof(*r));r->enabled=!session_ready || index>1u;
  snprintf(r->label,sizeof(r->label),"%s",ml_setting_labels[index]);
  const Fl26LeagueCatalogEntry *entry=ml_league_entry();
  if(index==0u) {
    snprintf(r->detail,sizeof(r->detail),"%s",session_ready ? ml_competition_name() : entry ? entry->name : "UNAVAILABLE");
    for(uint32_t i=0;i<FL26_LEAGUE_CATALOG_COUNT;i++)
      if(fl26_league_catalog[i].competition_id==(session_ready ? career.settings.competition_id : entry ? entry->competition_id : 0u)) {
        r->league_logo=i+1u;r->badge=ml_league_badge(i);
      }
  } else if(index==1u) {
    const uint32_t club=session_ready ? career.settings.club : entry ? entry->team_ids[club_choice] : 0u;
    r->badge=exhibition_team_catalog_badge(club);
    snprintf(r->detail,sizeof(r->detail),"%s",exhibition_team_catalog_name(club));
  } else if(index==2u)snprintf(r->value,sizeof(r->value),"%s",ml_difficulties[setup.difficulty]);
  else if(index==3u)snprintf(r->value,sizeof(r->value),"%u MIN",setup.match_minutes);
  else if(index==4u)snprintf(r->value,sizeof(r->value),"%s",ml_transfer_levels[setup_options.transfer_difficulty]);
  else if(index==5u)snprintf(r->value,sizeof(r->value),"%s",ml_currencies[setup_options.currency]);
  else if(index==6u)snprintf(r->value,sizeof(r->value),"%s",setup_options.skip_first_window ? "ON" : "OFF");
  else snprintf(r->value,sizeof(r->value),"%s",setup.condition==5u ? "RANDOM" : "NORMAL");
  if(index<2u && session_ready)snprintf(r->value,sizeof(r->value),"LOCKED");
  r->adjustable=index>=2u;
}
static void ml_drawer_view(MlView *v) {
  MlDrawerView *d=&v->drawer;d->open=drawer_kind!=0u;d->serial=drawer_serial;
  if(!d->open)return;
  d->total=ml_drawer_count();d->selected=drawer_focus;d->first=drawer_first;
  if(drawer_kind==ML_DRAWER_TRANSACTION){d->first=0u;d->confirm=1;d->confirm_selected=drawer_focus==1u;d->modal=1;d->selected=drawer_focus ? UINT32_MAX : 0u;}
  const char *title=drawer_kind==ML_DRAWER_COUNTRY ? "SELECT NATIONALITY" : drawer_kind==ML_DRAWER_SQUAD ? "MY SQUAD LIST" :
      drawer_kind==ML_DRAWER_CLUB ? (destination ? "SELECT BUYING CLUB" : "SELECT CLUB") : "SELECT OPTION";
  snprintf(d->title,sizeof(d->title),"%s",title);
  if(drawer_kind==ML_DRAWER_SETTING)snprintf(d->title,sizeof(d->title),"SELECT %s",ml_setting_labels[focus]);
  if(drawer_kind==ML_DRAWER_TRANSACTION) {
    const MlPlayer *p=&career.players[transaction_player];char fee[32];ml_money(fee,sizeof(fee),ml_transfer_fee(&career,p));
    snprintf(d->title,sizeof(d->title),"%s",confirm_kind==2u ? "RENEW CONTRACT" : "CONFIRM TRANSFER");
    snprintf(d->subtitle,sizeof(d->subtitle),"%s",p->name);
    snprintf(d->detail,sizeof(d->detail),"%s",exhibition_team_catalog_name(confirm_kind==2u ? p->club : destination));
    if(confirm_kind==2u) {
      const uint32_t rating=p->overall>40u ? p->overall-40u : 1u;
      const uint32_t wage=(1000u+rating*rating*15u)*(career.options.currency==1u ? 85u : career.options.currency==2u ? 110u : 100u)/100u;
      ml_money(fee,sizeof(fee),ml_renew_fee(&career,transaction_player,years));
      snprintf(d->detail,sizeof(d->detail),"SIGNING FEE  %s",fee);
      snprintf(d->value,sizeof(d->value),"WEEKLY WAGE  %s %u.%u K",ml_currencies[career.options.currency],wage/1000u,(wage%1000u)/100u);
      snprintf(d->confirm_label,sizeof(d->confirm_label),"PAY & RENEW");
    } else snprintf(d->value,sizeof(d->value),"TRANSFER FEE  %s",fee);
    d->count=3u;
    for(uint32_t i=0;i<3u;i++)d->rows[i].enabled=1;
    snprintf(d->rows[0].label,64,"CONTRACT");d->rows[0].adjustable=2u;
    snprintf(d->rows[0].value,48,"%u YEARS / UNTIL S%u",years,career.season+years);
    snprintf(d->rows[1].label,64,"SIGNING FEE");snprintf(d->rows[1].value,48,"%s",fee);
    snprintf(d->rows[2].label,64,"WEEKLY WAGE");
    snprintf(d->rows[2].value,48,"%.47s",d->value+13u);
    v->helper_count=2u;v->helper_key[0]="A";v->helper_key[1]="B";
    v->helper_label[0]=drawer_focus ? "PAY & RENEW" : "CONTINUE";v->helper_label[1]="CANCEL";
    return;
  }
  for(uint32_t i=0;i<5u && d->first+i<d->total;i++) {
    const uint32_t index=d->first+i;MlViewRow *r=&d->rows[d->count++];r->enabled=1;
    uint32_t team=0u;
    if(drawer_kind==ML_DRAWER_COUNTRY)team=countries[index];
    else if(drawer_kind==ML_DRAWER_CLUB)team=career.clubs[index].team;
    else if(drawer_kind==ML_DRAWER_SETTING) {
      switch(focus) {
        case ML_SETTING_LEAGUE: {
          const uint32_t cat=league_options[index];
          snprintf(r->label,sizeof(r->label),"%s",fl26_league_catalog[cat].name);
          r->league_logo=cat+1u;r->badge=ml_league_badge(cat);break;
        }
        case ML_SETTING_CLUB:team=ml_league_entry()->team_ids[index];break;
        case ML_SETTING_DIFFICULTY:snprintf(r->label,sizeof(r->label),"%s",ml_difficulties[index]);break;
        case ML_SETTING_TIME:snprintf(r->label,sizeof(r->label),"%u MIN",(index+1u)*5u);break;
        case ML_SETTING_TRANSFER:snprintf(r->label,sizeof(r->label),"%s",index==0u ? "EASY" : index==1u ? "NORMAL" : "HARD");break;
        case ML_SETTING_CURRENCY:snprintf(r->label,sizeof(r->label),"%s",ml_currencies[index]);break;
        case ML_SETTING_SKIP_WINDOW:snprintf(r->label,sizeof(r->label),"%s",index ? "ON" : "OFF");break;
        default:snprintf(r->label,sizeof(r->label),"%s",index ? "NORMAL" : "RANDOM");break;
      }
    } else if(drawer_kind==ML_DRAWER_SQUAD) {
      const MlPlayer *p=&career.players[row_players[index]];
      snprintf(r->label,sizeof(r->label),"%s",p->name);r->portrait=p->portrait_id;
      r->rating=p->overall;r->role=p->position;
      snprintf(r->detail,sizeof(r->detail),"%s",ml_role(p->position));
    } else if(drawer_kind==ML_DRAWER_TRANSACTION) {
      snprintf(r->label,sizeof(r->label),"%u %s",index+1u,index ? "YEARS" : "YEAR");
      if(index+1u==years)snprintf(r->value,sizeof(r->value),"SELECTED");
    }
    if(team) {snprintf(r->label,sizeof(r->label),"%s",exhibition_team_catalog_name(team));r->badge=exhibition_team_catalog_badge(team);}
  }
  v->helper_count=drawer_kind==ML_DRAWER_TRANSACTION ? 2u : 4u;
  v->helper_label[0]=drawer_kind==ML_DRAWER_SQUAD ? "VIEW" : "CONFIRM";
  v->helper_label[1]="CLOSE";
  if(drawer_kind==ML_DRAWER_SQUAD) {
    v->helper_count=3u;v->helper_key[0]="L";v->helper_label[0]="PREV PAGE";
    v->helper_key[2]="R";v->helper_label[2]="NEXT PAGE";
  }
}
static void ml_calendar_view(MlView *v) {
  static const char *months[]={"JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE","JULY","AUGUST","SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"};
  uint32_t year,month,date;ml_calendar_date(calendar_day,&year,&month,&date);
  const uint32_t first=calendar_day-date+1u,weekday=ml_calendar_weekday(year,month);
  snprintf(v->calendar_month,sizeof(v->calendar_month),"%s %u",months[month-1u],year);
  snprintf(v->title,sizeof(v->title),"SEASON CALENDAR");v->count=0u;
  v->calendar_count=42u;
  snprintf(v->calendar_detail,sizeof(v->calendar_detail),"%u %s / REST & TRAINING",date,months[month-1u]);
  for(uint32_t d=0;d<ml_calendar_month_days(month,year);d++) {
    MlCalendarCell *cell=&v->calendar[weekday+d];cell->day=d+1u;
    const uint32_t day=first+d,team=career.settings.club;
    cell->transfer=ml_calendar_transfer(&career,day);
    cell->current=day==(page==ML_PAGE_ADVANCE ? calendar_day : career.day);cell->selected=day==calendar_day;
    uint32_t opponent=0u,home=0u,done=0u,hg=0u,ag=0u;
    for(uint32_t i=0;i<career.league.matchday_count;i++)if(ml_league_day(&career,i)==day) {
      for(uint32_t j=0;j<career.league.matchday_fixture_count[i];j++) {
        const LeagueFixture *f=league_tournament_matchday_fixture(&career.league,i,j);
        if(f && (f->home==team || f->away==team)) {
          home=f->home==team;opponent=home ? f->away : f->home;done=f->complete;hg=f->home_goals;ag=f->away_goals;cell->kind=1u;
        }
      }
    }
    for(uint32_t i=0;career.cup_enabled && i<career.cup.round_count;i++)if(ml_cup_day(&career,i)==day) {
      for(uint32_t j=0;j<cup_tournament_fixture_count(&career.cup,i);j++) {
        const CupFixture *f=cup_tournament_fixture(&career.cup,i,j);
        if(f && (f->home==team || f->away==team)) {
          home=f->home==team;opponent=home ? f->away : f->home;done=f->complete;hg=f->home_goals;ag=f->away_goals;cell->kind=2u;
        }
      }
    }
    if(opponent) {
      cell->badge=exhibition_team_catalog_badge(opponent);
      snprintf(cell->label,sizeof(cell->label),"%.15s",exhibition_team_catalog_name(opponent));
      if(done)snprintf(cell->detail,sizeof(cell->detail),"%s %u-%u",home ? "H" : "A",home ? hg : ag,home ? ag : hg);
      else snprintf(cell->detail,sizeof(cell->detail),"%s / %s",home ? "HOME" : "AWAY",cell->kind==2u ? "CUP" : "LEAGUE");
      if(cell->selected)snprintf(v->calendar_detail,sizeof(v->calendar_detail),"%u %s / %s / %.50s / %s",date,months[month-1u],cell->kind==2u ? "CUP" : "LEAGUE",exhibition_team_catalog_name(opponent),cell->detail);
    } else if(cell->transfer) {
      const char *label=cell->transfer==1u ? "WINDOW OPENS" : cell->transfer==2u ? "MID-WINDOW" : cell->transfer==3u ? "DEADLINE" : "RESPONSE";
      snprintf(cell->detail,sizeof(cell->detail),"%s",label);
      if(cell->selected)snprintf(v->calendar_detail,sizeof(v->calendar_detail),"%u %s / TRANSFER %s",date,months[month-1u],label);
    }
  }
  v->helper_count=3u;v->helper_key[0]="L";v->helper_label[0]="PREV MONTH";
  v->helper_key[2]="R";v->helper_label[2]="NEXT MONTH";
}
static void ml_review_view(MlView *v) {
  /* Each page owns one primary panel; secondary content is opt-in. */
  if(v->helper_key[2] && !strcmp(v->helper_key[2],"SL"))v->helper_key[2]="L";
  if(v->helper_key[3] && !strcmp(v->helper_key[3],"SR"))v->helper_key[3]="R";
  if(session_ready) {
    const MlClub *club=ml_find_club(&career,career.settings.club);
    ml_money(v->annual_budget,sizeof(v->annual_budget),club ? (int64_t)club->wage_budget*52 : 0);
    ml_money(v->transfer_budget,sizeof(v->transfer_budget),club ? club->cash : 0);
  }
  if(page==ML_PAGE_SETTINGS) {
    v->first=0u;v->count=v->total=ML_SETTING_COUNT;v->selected=focus;
    v->action_count=1u;v->action_selected=focus==ML_SETTING_COUNT;v->action_focus=0u;v->action_enabled[0]=1;
    snprintf(v->action[0],32,"%s",session_ready ? "APPLY" : "NEXT");
    for(uint32_t i=0;i<ML_SETTING_COUNT;i++)ml_setting_row(&v->rows[i],i);
  } else if(page==ML_PAGE_HUB) {
    v->rows[4]=v->rows[3];memset(&v->rows[3],0,sizeof(v->rows[3]));v->rows[3].enabled=1;
    snprintf(v->rows[3].label,64,"%s",hub_section==1u ? "MY SQUAD" : hub_section==2u ? "MANAGER" : "LEAGUE RANKING");
    v->count=v->total=5u;v->selected=focus;
  } else if(page==ML_PAGE_SQUAD || page==ML_PAGE_MARKET_CLUBS) {
    memset(v->rows,0,sizeof(v->rows));v->count=v->total=2u;v->first=0u;v->selected=focus;v->helper_count=2u;
    snprintf(v->title,64,"%s",page==ML_PAGE_SQUAD ? "SQUAD" : "TRANSFER MARKET");
    snprintf(v->rows[0].label,64,"%s",page==ML_PAGE_SQUAD ? "MY SQUAD LIST" : "BROWSE CLUBS");
    snprintf(v->rows[1].label,64,"%s",page==ML_PAGE_SQUAD ? "GAME PLAN" : "FREE AGENTS");
    snprintf(v->rows[0].detail,96,"%s",page==ML_PAGE_SQUAD ? "Players, roles and squad registration" : "Choose a club to buy or sell players");
    snprintf(v->rows[1].detail,96,"%s",page==ML_PAGE_SQUAD ? "Set your permanent career formation and lineup" : "Find players without a club");
    v->rows[0].enabled=v->rows[1].enabled=1;
  } else if(page==ML_PAGE_CALENDAR || page==ML_PAGE_ADVANCE) {
    ml_calendar_view(v);
    if(page==ML_PAGE_ADVANCE) {
      const uint64_t elapsed=frontend_clock>=advance_started ? frontend_clock-advance_started : 0u;
      const uint32_t travel=advance_duration-500u;
      const uint64_t moving=elapsed>250u ? elapsed-250u : 0u;
      const uint32_t delta=advance_to>=advance_from ? advance_to-advance_from : 0u;
      v->advance_progress=(float)(elapsed<advance_duration ? elapsed : advance_duration)/advance_duration;
      v->advance_fraction=moving<travel ? (float)((moving*delta)%travel)/travel : 0.f;
      snprintf(v->title,64,"ADVANCING CALENDAR");
      snprintf(v->caption,96,"%s  /  SEASON %u  /  DAY %u",career.manager_name,career.season,calendar_day+1u);
      v->helper_count=0u;
    }
  }
  if(page==ML_PAGE_LANDING) {
    snprintf(v->rows[0].detail,96,"Build your club across seasons");
    snprintf(v->rows[1].detail,96,"Load one of three career saves");
  }
  if(page==ML_PAGE_CONTRACTS || page==ML_PAGE_MARKET_PLAYERS) {
    if(!player_rows) {snprintf(v->left_title,64,"NO PLAYERS AVAILABLE");v->count=v->total=0u;}
    v->helper_label[0]=page==ML_PAGE_CONTRACTS ? "RENEW CONTRACT" : "PLAYER DETAILS";
    for(uint32_t i=0;i<v->count;i++)ml_money(v->rows[i].value,48,ml_transfer_fee(&career,&career.players[row_players[v->first+i]]));
  }
  ml_drawer_view(v);
  ml_office_view(v);
}

#include "master_league_office_frontend.inc"
