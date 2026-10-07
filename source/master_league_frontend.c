#include "master_league_frontend.h"
#include "master_league_catalog.h"
#include "exhibition_team_catalog.h"
#include "fl26_league_catalog_generated.h"
#include "fl26_cup_catalog_generated.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ML_B (1u<<0)
#define ML_A (1u<<1)
#define ML_Y (1u<<2)
#define ML_X (1u<<3)
#define ML_L (1u<<4)
#define ML_R (1u<<7)
#define ML_UP (1u<<10)
#define ML_DOWN (1u<<11)
#define ML_LEFT (1u<<12)
#define ML_RIGHT (1u<<13)

static MasterLeague career;
static MlSettings setup;
static MlCareerOptions setup_options;
static MlPage page, return_page;
static uint32_t focus, action, league_choice, club_choice;
static uint32_t league_options[FL26_LEAGUE_CATALOG_COUNT], league_count;
static uint32_t countries[EXHIBITION_TEAM_CATALOG_COUNT], country_count, nationality;
static uint32_t row_players[ML_MAX_PLAYERS], player_rows, market_club;
static uint32_t transaction_player, destination, years=3u, confirm_kind;
static uint32_t selected_player=ML_INVALID_INDEX;
static uint32_t active_slot=ML_INVALID_INDEX, saving, overwrite_slot;
static uint32_t session_ready, match_active, result_received, match_swapped;
static uint32_t match_from_day, result_saved, return_focus;
static MlView confirm_background;
static uint32_t plan_editor;
static uint32_t shootout_winner;
static uint32_t table_scorers;
static uint32_t hub_section, feed_index, navigation_serial;
static int slide_direction;
static MlEvent pending;
static char manager[ML_NAME_SIZE], message[112];
static uint32_t toast_serial;
static char toast[64];
static uint64_t frontend_clock,advance_started;
static uint32_t advance_from,advance_to,advance_duration;
static char advance_notice[64];
static void ml_begin_advance(uint32_t from,const char *notice);
static void ml_start_advance(uint32_t from,const char *notice);
static void ml_open_confirmation(uint32_t kind);
static void ml_cancel_confirmation(void);
static void ml_renew_open(uint32_t index);
static uint8_t slot_valid[ML_SAVE_SLOTS];
static char slot_club[ML_SAVE_SLOTS][64], slot_progress[ML_SAVE_SLOTS][80];

static int ml_review_pad(uint32_t pressed);
static void ml_review_view(MlView *view);
static void ml_review_reset(void);

static void ml_message(const char *text) { snprintf(message,sizeof(message),"%s",text);toast[0]=0;toast_serial++; }
static void ml_toast(const char *text) {snprintf(toast,sizeof(toast),"%s",text);toast_serial++;message[0]=0;}
static void ml_page(MlPage next) {
  page=next; focus=next==ML_PAGE_SETTINGS && session_ready ? 2u : 0u; message[0]=0;
  if(next==ML_PAGE_SETTINGS && session_ready) setup_options=career.options;
}
static const Fl26LeagueCatalogEntry *ml_league_entry(void) {
  return league_count ? &fl26_league_catalog[league_options[league_choice]] : NULL;
}
static const char *ml_competition_name(void) {
  for (uint32_t i=0; i<FL26_LEAGUE_CATALOG_COUNT; i++)
    if (fl26_league_catalog[i].competition_id==career.settings.competition_id)
      return fl26_league_catalog[i].name;
  return "MASTER LEAGUE";
}
static const char *ml_cup_name(void) {
  for (uint32_t i=0; i<FL26_CUP_CATALOG_COUNT; i++)
    if (fl26_cup_catalog[i].competition_id==career.settings.cup_id)
      return fl26_cup_catalog[i].name;
  return "DOMESTIC CUP";
}
static void ml_money(char *out, size_t size, int64_t amount) {
  const uint32_t currency=session_ready ? career.options.currency : setup_options.currency;
  const char *unit=currency==1u ? "GBP" : currency==2u ? "USD" : "EUR";
  /* Fixed fictional economy conversion, never fetched live or used in storage. */
  amount=amount*(currency==1u ? 85 : currency==2u ? 110 : 100)/100;
  snprintf(out,size,"%s %s%lld.%02lld M",unit,amount<0 ? "-" : "",
      (long long)((amount<0 ? -amount : amount)/1000000),
      (long long)(((amount<0 ? -amount : amount)%1000000)/10000));
}
static void ml_scan_saves(void) {
  MasterLeague *snapshot=malloc(sizeof(*snapshot));
  for (uint32_t i=0; i<ML_SAVE_SLOTS; i++) {
    slot_valid[i]=snapshot && ml_save_read(i,ml_catalog_content_id(),snapshot);
    snprintf(slot_club[i],sizeof(slot_club[i]),"%s",slot_valid[i]
        ? exhibition_team_catalog_name(snapshot->settings.club) : "NO COMPATIBLE SAVE");
    if (slot_valid[i]) snprintf(slot_progress[i],sizeof(slot_progress[i]),
        "%s  /  SEASON %u  /  DAY %u",snapshot->manager_name,snapshot->season,snapshot->day+1u);
    else slot_progress[i][0]=0;
  }
  free(snapshot);
}
static int ml_autosave(void) {
  if (active_slot>=ML_SAVE_SLOTS || !ml_save_write(active_slot,&career)) {
    ml_message("SAVE FAILED - KEEP THIS SESSION OPEN AND RETRY SAVE"); return 0;
  }
  return 1;
}
static void ml_refresh_players(uint32_t club) {
  player_rows=0u;
  const MlClub *roster=ml_find_club(&career,club);
  if (roster) {
    for (uint32_t i=0;i<roster->count;i++) row_players[player_rows++]=roster->players[i];
  } else if (!club) {
    for (uint32_t i=0;i<career.player_count;i++)
      if (!career.players[i].club) row_players[player_rows++]=i;
  }
}
static uint32_t ml_count(void) {
  switch(page) {
    case ML_PAGE_LANDING: return 2u;
    case ML_PAGE_SETTINGS: return 6u;
    case ML_PAGE_MANAGER: return 3u;
    case ML_PAGE_NATIONALITY: return country_count;
    case ML_PAGE_CLUBS: return ml_league_entry() ? ml_league_entry()->pool_count : 0u;
    case ML_PAGE_HUB: return 4u;
    case ML_PAGE_SLOTS: return ML_SAVE_SLOTS;
    case ML_PAGE_OFFICE: return 5u;
    case ML_PAGE_MARKET_CLUBS: return career.club_count+1u;
    case ML_PAGE_SQUAD: case ML_PAGE_MARKET_PLAYERS: case ML_PAGE_CONTRACTS: case ML_PAGE_MY_PLAYERS:
      return player_rows;
    case ML_PAGE_TABLE: return table_scorers ? 4u : career.league.team_count;
    case ML_PAGE_NEXT: return 2u;
    case ML_PAGE_CONFIRM: return 2u;
    case ML_PAGE_NEWS: return 4u;
    case ML_PAGE_CALENDAR: return career.league.matchday_count;
    case ML_PAGE_CUP: return career.cup_enabled ? career.cup.round_count : 0u;
    default: return 1u;
  }
}
void ml_frontend_open(void) {
  session_ready=match_active=result_received=plan_editor=0u;
  ml_review_reset();
  hub_section=feed_index=0u; navigation_serial++; slide_direction=0;
  active_slot=ML_INVALID_INDEX; action=0u;
  league_count=country_count=0u;
  for (uint32_t i=0; i<FL26_LEAGUE_CATALOG_COUNT; i++) {
    const Fl26LeagueCatalogEntry *entry=&fl26_league_catalog[i];
    if (!entry->competition_id || entry->pool_count<2u || entry->pool_count>32u) continue;
    int valid=1;
    for (uint32_t t=0;t<entry->pool_count;t++)
      if (!ml_catalog_has_team(entry->team_ids[t])) { valid=0; break; }
    if (valid) league_options[league_count++]=i;
  }
  /* Nationality uses the curated native flag atlas, including Indonesia,
   * rather than reintroducing removed selector entries or foreign assets. */
  for (uint32_t c=0;c<EXHIBITION_TEAM_CATEGORY_COUNT;c++) {
    const ExhibitionTeamCategory *category=&exhibition_team_categories[c];
    if (!strstr(category->label,"NATIONAL")) continue;
    for (uint32_t t=0;t<category->team_count;t++) countries[country_count++]=category->teams[t];
  }
  /* Sort by the displayed country name, not database or confederation order. */
  for(uint32_t i=1;i<country_count;i++) {
    uint32_t country=countries[i],j=i;
    while(j && strcmp(exhibition_team_catalog_name(countries[j-1u]),
                      exhibition_team_catalog_name(country))>0) {
      countries[j]=countries[j-1u]; j--;
    }
    countries[j]=country;
  }
  ml_scan_saves(); ml_page(ML_PAGE_LANDING);
}
void ml_frontend_close(void) {
  match_active=session_ready=action=plan_editor=0u;
  ml_review_reset();
  selected_player=ML_INVALID_INDEX;
}
const MasterLeague *ml_frontend_career(void) { return session_ready ? &career : NULL; }
uint32_t ml_frontend_take_action(void) { uint32_t result=action; action=0u; return result; }
const char *ml_frontend_manager_name(void) { return manager; }
void ml_frontend_name_result(const char *text) {
  if (page!=ML_PAGE_MANAGER || !text) return;
  if (!ml_manager_name_valid(text)) { ml_message("USE 1-31 LATIN LETTERS, SPACES, APOSTROPHE, DOT OR HYPHEN"); return; }
  snprintf(manager,sizeof(manager),"%s",text); message[0]=0;
}

static void ml_create(void) {
  if (!league_count || !ml_manager_name_valid(manager) || !nationality) {
    ml_message("ENTER MANAGER NAME AND SELECT NATIONALITY"); return;
  }
  const Fl26LeagueCatalogEntry *entry=ml_league_entry();
  setup.competition_id=entry->competition_id;
  setup.club=entry->team_ids[club_choice]; setup.cup_id=0u;
  uint32_t cup_teams[CUP_MAX_TEAMS], cup_count=0u;
  /* Use only an existing domestic cup with a verified pool. Capacity is
   * explicit: this is the supported FootballNX field, not every real club. */
  for (uint32_t i=0;i<FL26_CUP_CUSTOM_INDEX;i++) {
    const Fl26CupCatalogEntry *cup=&fl26_cup_catalog[i];
    if (cup->competition_id!=15u && cup->competition_id!=16u && cup->competition_id!=17u) continue;
    int belongs=0;
    for (uint32_t t=0;t<cup->pool_count;t++) belongs |= cup->team_ids[t]==setup.club;
    if (!belongs) continue;
    cup_teams[cup_count++]=setup.club;
    for (uint32_t t=0;t<cup->pool_count && cup_count<cup->bracket_limit;t++)
      if (cup->team_ids[t]!=setup.club && ml_catalog_has_team(cup->team_ids[t]))
        cup_teams[cup_count++]=cup->team_ids[t];
    setup.cup_id=cup->competition_id; break;
  }
  const uint32_t seed=0x4d4c2026u ^ (setup.club*2654435761u);
  if (!ml_init(&career,ml_catalog_content_id(),&setup,manager,nationality,seed) ||
      !ml_catalog_import(&career) ||
      !ml_start_season(&career,entry->team_ids,entry->pool_count,cup_teams,cup_count) ||
      !ml_valid(&career)) {
    session_ready=0u; ml_message("CAREER DATA VALIDATION FAILED - ORIGINAL SAVES UNCHANGED"); return;
  }
  career.options=setup_options;
  session_ready=1u; saving=1u; active_slot=ML_INVALID_INDEX;
  ml_scan_saves(); ml_page(ML_PAGE_SLOTS);
}
static void ml_save_selected(uint32_t slot) {
  if (!ml_save_write(slot,&career)) { ml_message("CAREER SAVE FAILED"); return; }
  active_slot=slot; hub_section=0u; ml_page(ML_PAGE_HUB);
}
static void ml_choose_transaction(uint32_t index, int renewal) {
  transaction_player=index; years=3u; confirm_kind=renewal ? 2u : 1u;
  ml_open_confirmation(confirm_kind);
}
static void ml_open_confirmation(uint32_t kind) {
  /* Capture the actual underlying page once; rendering a modal must not
   * temporarily mutate global navigation or accidentally mark inboxes read. */
  ml_frontend_view(&confirm_background);
  return_page=page;return_focus=focus;confirm_kind=kind;
  ml_page(ML_PAGE_CONFIRM);
  if(kind==4u || kind==6u)focus=1u; /* destructive actions default to Cancel */
}
static void ml_cancel_confirmation(void) {
  ml_page(return_page);focus=return_focus;
}
static void ml_hub_open(uint32_t item) {
  /* Section cards are intentionally destinations, not a dense nested menu. */
  static const MlPage pages[4][4] = {
    {ML_PAGE_NEXT, ML_PAGE_NEWS, ML_PAGE_CALENDAR, ML_PAGE_SLOTS},
    {ML_PAGE_SQUAD, ML_PAGE_CONTRACTS, ML_PAGE_MARKET_CLUBS, ML_PAGE_NEWS},
    {ML_PAGE_MARKET_CLUBS, ML_PAGE_CONTRACTS, ML_PAGE_FINANCES, ML_PAGE_SETTINGS},
    {ML_PAGE_TABLE, ML_PAGE_TABLE, ML_PAGE_CUP, ML_PAGE_CALENDAR}
  };
  const MlPage next=pages[hub_section][item];
  if (next==ML_PAGE_CUP && !career.cup_enabled) return;
  if (next==ML_PAGE_NEXT) ml_next_event(&career,&pending);
  if (next==ML_PAGE_SQUAD || next==ML_PAGE_CONTRACTS) {
    ml_refresh_players(career.settings.club); selected_player=ML_INVALID_INDEX;
  }
  if (next==ML_PAGE_MARKET_CLUBS) destination=0u;
  if (next==ML_PAGE_SETTINGS) setup=career.settings;
  if (next==ML_PAGE_TABLE) table_scorers=item==1u;
  if (next==ML_PAGE_SLOTS) { saving=1u; ml_scan_saves(); }
  ml_page(next);
  if (next==ML_PAGE_SLOTS) focus=active_slot<3u ? active_slot : 0u;
}
static void ml_confirm(void) {
  switch(page) {
    case ML_PAGE_LANDING:
      if (!focus) {
        if (!league_count) { ml_message("PAIRED CAREER CATALOG REQUIRED"); return; }
        session_ready=0u; active_slot=ML_INVALID_INDEX;
        setup=(MlSettings){0}; setup.difficulty=3u; setup.match_minutes=10u;
        setup_options=(MlCareerOptions){0};
        setup.condition=5u; setup.injuries=1u; setup.max_substitutions=5u;
        league_choice=club_choice=nationality=0u; manager[0]=0;
        ml_page(ML_PAGE_SETTINGS);
      } else { saving=0u; ml_scan_saves(); ml_page(ML_PAGE_SLOTS); }
      break;
    case ML_PAGE_SETTINGS:
      if (focus==5u) ml_page(ML_PAGE_MANAGER);
      else if (focus==1u) { ml_page(ML_PAGE_CLUBS); focus=club_choice; }
      break;
    case ML_PAGE_MANAGER:
      if (!focus) action=ML_ACTION_NAME_INPUT;
      else if (focus==1u) ml_page(ML_PAGE_NATIONALITY);
      else ml_create();
      break;
    case ML_PAGE_NATIONALITY:
      if (focus<country_count) { nationality=countries[focus]; ml_page(ML_PAGE_MANAGER); focus=1u; }
      break;
    case ML_PAGE_CLUBS:
      club_choice=focus; ml_page(ML_PAGE_SETTINGS); focus=1u; break;
    case ML_PAGE_SLOTS:
      if (saving) {
        char path[80]; snprintf(path,sizeof(path),"SaveData/footballnx_master_league_%u_a.bin",focus+1u);
        FILE *existing=fopen(path,"rb");
        if (!existing) { snprintf(path,sizeof(path),"SaveData/footballnx_master_league_%u_b.bin",focus+1u); existing=fopen(path,"rb"); }
        if (existing) { fclose(existing); overwrite_slot=focus; ml_open_confirmation(4u); }
        else ml_save_selected(focus);
      } else if (slot_valid[focus] && ml_save_read(focus,ml_catalog_content_id(),&career)) {
        session_ready=1u; active_slot=focus; hub_section=0u; ml_page(ML_PAGE_HUB);
      } else ml_message("EMPTY, DAMAGED OR DIFFERENT ROSTER VERSION - NOT OVERWRITTEN");
      break;
    case ML_PAGE_HUB:
      ml_hub_open(focus);
      break;
    case ML_PAGE_OFFICE:
      if (!focus) { destination=0u; ml_page(ML_PAGE_MARKET_CLUBS); }
      else if (focus==1u) { ml_refresh_players(career.settings.club); ml_page(ML_PAGE_CONTRACTS); }
      else if (focus==2u) ml_page(ML_PAGE_FINANCES);
      else if (focus==3u) { table_scorers=0u; ml_page(ML_PAGE_TABLE); }
      else { setup=career.settings; ml_page(ML_PAGE_SETTINGS); }
      break;
    case ML_PAGE_MARKET_CLUBS:
      market_club=focus<career.club_count ? career.clubs[focus].team : 0u;
      if (destination) {
        destination=market_club;
        if (!destination || destination==career.settings.club) { ml_message("SELECT A BUYING CLUB"); destination=career.settings.club; break; }
        ml_open_confirmation(1u);
      } else { ml_refresh_players(market_club); ml_page(ML_PAGE_MARKET_PLAYERS); }
      break;
    case ML_PAGE_MARKET_PLAYERS:
      if (focus>=player_rows) break;
      if (career.players[row_players[focus]].club==career.settings.club) {
        transaction_player=row_players[focus]; destination=career.settings.club; years=3u;
        ml_page(ML_PAGE_MARKET_CLUBS);
      } else { destination=career.settings.club; ml_choose_transaction(row_players[focus],0); }
      break;
    case ML_PAGE_CONTRACTS:
      if (focus<player_rows) ml_choose_transaction(row_players[focus],1);
      break;
    case ML_PAGE_SQUAD:
      if (focus>=player_rows) break;
      if (selected_player==ML_INVALID_INDEX) selected_player=focus;
      else {
        if(!ml_swap(&career,career.settings.club,selected_player,focus)) {
          ml_message("KEEP A GOALKEEPER IN THE GOALKEEPER SLOT"); break;
        }
        selected_player=ML_INVALID_INDEX; ml_refresh_players(career.settings.club);
        ml_autosave();
      }
      break;
    case ML_PAGE_NEXT:
      if (pending.kind==ML_EVENT_SEASON_END) {
        if (focus) { ml_page(ML_PAGE_HUB); break; }
        if (!ml_next_season(&career)) ml_message("RENEW EXPIRING CONTRACTS: KEEP 18 PLAYERS AND A GOALKEEPER");
        else { ml_begin_advance(0u,"New season started"); }
      } else if (!focus) {
        if (!pending.home || !pending.away) { ml_message("YOUR CLUB HAS NO MATCH - CHOOSE SIMULATE"); break; }
        ml_open_confirmation(5u);
      } else ml_open_confirmation(3u);
      break;
    case ML_PAGE_CONFIRM:
      if (focus) { ml_cancel_confirmation(); break; }
      if (confirm_kind==4u) { ml_save_selected(overwrite_slot); break; }
      if (confirm_kind==5u) {
        /* A kickoff, failed handoff or quit is not a completed calendar event.
         * Date/wages move only when the result is committed, then animate on
         * return from the native result screen. */
        match_from_day=career.day;result_saved=0u;
        match_active=1u;plan_editor=0u;result_received=shootout_winner=0u;
        match_swapped=pending.away==career.settings.club;action=ML_ACTION_MATCH;
        ml_page(ML_PAGE_HUB);break;
      }
      if (confirm_kind==6u) {
        const char *error=ml_release(&career,transaction_player);
        if(*error){ml_message(error);break;}
        ml_cancel_confirmation();ml_refresh_players(career.settings.club);
        if(focus>=player_rows)focus=player_rows ? player_rows-1u : 0u;
        if(ml_autosave())ml_toast("Player released to free agency");
        break;
      }
      if (confirm_kind==3u) {
        const uint32_t from=career.day;
        if (!ml_simulate_event(&career,&pending)) { ml_message("EVENT CHANGED - RETURN TO CAREER HUB"); break; }
        ml_begin_advance(from,"Matchday completed"); break;
      }
      {
        const char *error=confirm_kind==2u ? ml_renew(&career,transaction_player,years)
            : ml_transfer(&career,transaction_player,destination,years);
        if (*error) { ml_message(error); break; }
        destination=0u;
        ml_page(ML_PAGE_OFFICE); ml_autosave();
      }
      break;
    default: break;
  }
}

void ml_frontend_pad(uint32_t pressed) {
  if (match_active || page==ML_PAGE_ADVANCE) return;
  if (ml_review_pad(pressed)) return;
  if (pressed & ML_B) {
    if (page==ML_PAGE_LANDING) { ml_frontend_close(); action=ML_ACTION_EXIT; }
    else if (page==ML_PAGE_HUB) { if (ml_autosave()) { ml_frontend_close(); action=ML_ACTION_EXIT; } }
    else if (page==ML_PAGE_SETTINGS) ml_page(session_ready ? ML_PAGE_OFFICE : ML_PAGE_LANDING);
    else if (page==ML_PAGE_MANAGER) ml_page(ML_PAGE_SETTINGS);
    else if (page==ML_PAGE_NATIONALITY) { ml_page(ML_PAGE_MANAGER); focus=1u; }
    else if (page==ML_PAGE_CLUBS) { ml_page(ML_PAGE_SETTINGS); focus=1u; }
    else if (page==ML_PAGE_SLOTS) ml_page(session_ready && active_slot<3u ? ML_PAGE_HUB : ML_PAGE_LANDING);
    else if (page==ML_PAGE_CONFIRM) ml_cancel_confirmation();
    else if (page==ML_PAGE_MARKET_PLAYERS) { destination=0u; ml_page(ML_PAGE_MARKET_CLUBS); }
    else if (page==ML_PAGE_SQUAD && selected_player!=ML_INVALID_INDEX) selected_player=ML_INVALID_INDEX;
    else if (page==ML_PAGE_OFFICE || page==ML_PAGE_SQUAD || page==ML_PAGE_NEXT) ml_page(ML_PAGE_HUB);
    else ml_page(ML_PAGE_HUB);
    return;
  }
  const uint32_t count=ml_count();
  if (page==ML_PAGE_HUB) {
    const uint32_t old=hub_section;
    if (pressed&ML_UP) focus&=1u;
    else if (pressed&ML_DOWN) focus|=2u;
    else if (pressed&(ML_LEFT|ML_L)) {
      if ((pressed&ML_LEFT) && (focus&1u)) focus--;
      else if (hub_section) { hub_section--; focus|=1u; }
    } else if (pressed&(ML_RIGHT|ML_R)) {
      if ((pressed&ML_RIGHT) && !(focus&1u)) focus++;
      else if (hub_section<3u) { hub_section++; focus&=2u; }
    }
    else if (pressed&ML_X) { if (ml_autosave()) ml_message("CAREER SAVED"); }
    else if (pressed&ML_A) ml_confirm();
    if (old!=hub_section) { slide_direction=hub_section>old ? 1 : -1; navigation_serial++; message[0]=0; }
    return;
  }
  if (page==ML_PAGE_NEWS) {
    if (pressed&(ML_LEFT|ML_L|ML_RIGHT|ML_R)) {
      const int right=(pressed&(ML_RIGHT|ML_R))!=0;
      feed_index=(feed_index+(right ? 1u : 3u))%4u;
      slide_direction=right ? 1 : -1; navigation_serial++;
    }
    return;
  }
  if (page==ML_PAGE_TABLE && (pressed&ML_Y)) { table_scorers=!table_scorers; focus=0u; return; }
  if (pressed&(ML_UP|ML_DOWN|ML_L|ML_R)) {
    const uint32_t step=pressed&(ML_L|ML_R) ? 5u : 1u;
    if (count) focus=pressed&(ML_UP|ML_L) ? (focus>=step ? focus-step : 0u)
                                         : (focus+step<count ? focus+step : count-1u);
    return;
  }
  if (pressed&(ML_LEFT|ML_RIGHT)) {
    const int change=pressed&ML_RIGHT ? 1 : -1;
    if (page==ML_PAGE_SETTINGS) {
      if (focus==0u && !session_ready && league_count) {
        league_choice=(league_choice+league_count+change)%league_count; club_choice=0u;
      } else if (focus==1u && !session_ready && ml_league_entry()) {
        uint32_t n=ml_league_entry()->pool_count; club_choice=(club_choice+n+change)%n;
      } else if (focus==2u) setup.difficulty=(setup.difficulty+7u+change)%7u;
      else if (focus==3u) setup.match_minutes=change>0
          ? (setup.match_minutes<30u ? setup.match_minutes+5u : 5u)
          : (setup.match_minutes>5u ? setup.match_minutes-5u : 30u);
      else if (focus==4u) setup.condition=setup.condition==5u ? 2u : 5u;
    } else if (page==ML_PAGE_CONFIRM && confirm_kind<=2u)
      years=(uint32_t)((int)years+change+4)%5u+1u;
    return;
  }
  if (pressed&ML_A) {
    if (page==ML_PAGE_SETTINGS && session_ready) {
      if (focus==5u) { career.settings.difficulty=setup.difficulty; career.settings.match_minutes=setup.match_minutes;
        career.settings.condition=setup.condition; ml_page(ML_PAGE_OFFICE); ml_autosave(); }
      return;
    }
    ml_confirm();
  }
}

int ml_frontend_match_active(void) { return match_active!=0u; }
int ml_frontend_plan_editor(void) { return match_active && plan_editor; }
void ml_frontend_plan_error(void) { ml_message("SQUAD EDITOR COULD NOT OPEN - PLEASE RETRY"); }
int ml_frontend_match_is_cup(void) { return match_active && !plan_editor && pending.kind==ML_EVENT_CUP; }
int ml_frontend_match_teams(uint32_t *home,uint32_t *away) {
  if (!match_active || !pending.home || !pending.away) return 0;
  if (home) *home=match_swapped ? pending.away : pending.home;
  if (away) *away=match_swapped ? pending.home : pending.away;
  return 1;
}
void ml_frontend_handoff_result(int opened) {
  if (!opened) {
    ml_message(plan_editor ? "SQUAD EDITOR COULD NOT OPEN - PLEASE RETRY" : "MATCH COULD NOT START - FIXTURE KEPT");
    match_active=plan_editor=0u;
  }
}
void ml_frontend_penalty_result(uint32_t home,uint32_t away) {
  if (!ml_frontend_match_is_cup() || result_received) return;
  uint32_t native_home=0u,native_away=0u;
  ml_frontend_match_teams(&native_home,&native_away);
  shootout_winner=home==away || home>99u || away>99u ? 0u : home>away ? native_home : native_away;
}
void ml_frontend_result(uint32_t home,uint32_t away,const LeagueScorer *scorers,uint32_t count) {
  if (!match_active || plan_editor || result_received) return;
  if (!ml_record_event_decided(&career,&pending,match_swapped ? away : home,
        match_swapped ? home : away,scorers,count,0,shootout_winner)) {
    ml_message("RESULT NOT AVAILABLE - FIXTURE KEPT FOR RETRY"); return;
  }
  message[0]=0;
  result_received=1u; result_saved=ml_autosave();
}
int ml_frontend_restore(void) {
  if (!match_active) return 0;
  match_active=0u;
  char saved_message[112]; snprintf(saved_message,sizeof(saved_message),"%s",message);
  if(plan_editor) {plan_editor=0u;ml_page(ML_PAGE_SQUAD);focus=1u;}
  else {
    hub_section=0u;ml_page(ML_PAGE_HUB);
    if(result_received && result_saved)ml_start_advance(match_from_day,"Matchday completed");
  }
  if (saved_message[0]) ml_message(saved_message);
  return 1;
}
int ml_frontend_roster(uint32_t team,uint32_t players[40],uint8_t shirts[40],uint32_t *count) {
  const MlClub *club=match_active ? ml_find_club(&career,team) : NULL;
  if (!club || !players || !shirts || !count) return 0;
  *count=club->count;
  for (uint32_t i=0;i<club->count;i++) {
    const MlPlayer *p=&career.players[club->players[i]];
    players[i]=p->native_id; shirts[i]=p->shirt;
  }
  return 1;
}
int ml_frontend_player_allowed(uint32_t team,uint32_t native) {
  if (!match_active) return -1;
  const MlPlayer *p=ml_find_native(&career,native);
  return p && p->club==team;
}
int ml_frontend_preset_read(uint32_t team,uint32_t slot,GameplanPreset *out) {
  if (!match_active || team!=career.settings.club || slot>ML_CURRENT_PLAN_SLOT || !out) return 0;
  const GameplanPreset *p=slot==ML_CURRENT_PLAN_SLOT ? &career.current_plan : &career.presets[slot];
  if (!ml_plan_compatible(&career,p)) return 0;
  *out=*p; return 1;
}
int ml_frontend_preset_write(uint32_t team,uint32_t slot,const GameplanPreset *plan) {
  if (!match_active || team!=career.settings.club || slot>=GAMEPLAN_PRESET_SLOTS ||
      !ml_plan_compatible(&career,plan)) return 0;
  career.presets[slot]=*plan;
  return ml_autosave();
}
int ml_frontend_store_current_plan(const GameplanPreset *plan) {
  /* Match-hub and pause changes are temporary. Only the office editor owns
   * the career default; explicit named preset saves remain independent. */
  return match_active && plan_editor && ml_store_plan(&career,plan) && ml_autosave();
}

static const char *ml_role(uint32_t role) {
  static const char *labels[]={"GK","CB","LB","RB","DMF","CMF","LMF","RMF","AMF","LWF","RWF","SS","CF"};
  return role<13u ? labels[role] : "--";
}
static void ml_dashboard_view(MlView *v) {
  const uint32_t team=career.settings.club;
  const MlClub *club=ml_find_club(&career,team);
  snprintf(v->club_name,sizeof(v->club_name),"%s",exhibition_team_catalog_name(team));
  snprintf(v->competition,sizeof(v->competition),"%s",ml_competition_name());
  v->rank=ml_rank(&career);v->board_target=career.target_rank;
  v->squad_size=club ? club->count : 0u;
  ml_money(v->balance,sizeof(v->balance),club ? club->cash : 0);
  snprintf(v->season_summary,sizeof(v->season_summary),"SEASON %u  /  DAY %u",career.season,career.day+1u);
  MlEvent next={0};ml_next_event(&career,&next);
  snprintf(v->next.competition,sizeof(v->next.competition),"%s",next.kind==ML_EVENT_CUP ? ml_cup_name() : ml_competition_name());
  snprintf(v->next.day,sizeof(v->next.day),"DAY %u",next.day+1u);
  if(next.home && next.away) {
    snprintf(v->next.home,sizeof(v->next.home),"%s",exhibition_team_catalog_name(next.home));
    snprintf(v->next.away,sizeof(v->next.away),"%s",exhibition_team_catalog_name(next.away));
    v->next.home_badge=exhibition_team_catalog_badge(next.home);
    v->next.away_badge=exhibition_team_catalog_badge(next.away);
  }
  /* Keep the last completed match in view, then the next two matchdays. */
  uint32_t start=career.league.active_matchday;
  if(start) start--;
  for(uint32_t day=start;day<career.league.matchday_count && v->fixture_count<3u;day++) {
    for(uint32_t f=0;f<career.league.matchday_fixture_count[day];f++) {
      const LeagueFixture *fixture=league_tournament_matchday_fixture(&career.league,day,f);
      if(!fixture || (fixture->home!=team && fixture->away!=team)) continue;
      const uint32_t opponent=fixture->home==team ? fixture->away : fixture->home;
      MlViewRow *row=&v->fixtures[v->fixture_count++];
      snprintf(row->label,sizeof(row->label),"%s",exhibition_team_catalog_name(opponent));
      snprintf(row->detail,sizeof(row->detail),"MATCHDAY %u  /  %s",day+1u,fixture->home==team ? "HOME" : "AWAY");
      if(fixture->complete) snprintf(row->value,sizeof(row->value),"%u - %u",fixture->home_goals,fixture->away_goals);
      else snprintf(row->value,sizeof(row->value),"VS");
      row->badge=exhibition_team_catalog_badge(opponent);break;
    }
  }
  uint8_t order[LEAGUE_MAX_TEAMS]={0};
  league_tournament_ranked_slots(&career.league,order);
  for(uint32_t i=0;i<3u && i<career.league.team_count;i++) {
    const LeagueStanding *standing=&career.league.standings[order[i]];
    MlViewRow *row=&v->ranking[v->ranking_count++];
    snprintf(row->label,sizeof(row->label),"%s",exhibition_team_catalog_name(standing->team));
    snprintf(row->detail,sizeof(row->detail),"%u",i+1u);
    snprintf(row->value,sizeof(row->value),"%u",standing->points);
    row->badge=exhibition_team_catalog_badge(standing->team);
  }
  for(uint32_t i=0;club && i<3u && i<club->count;i++) {
    const MlPlayer *p=&career.players[club->players[i]];
    MlViewRow *row=&v->squad[v->squad_count++];
    snprintf(row->label,sizeof(row->label),"%s",p->name);
    snprintf(row->detail,sizeof(row->detail),"%s  /  #%u",ml_role(p->position),p->shirt);
    snprintf(row->value,sizeof(row->value),"%u",p->overall);
  }
}
static void ml_base_view(MlView *v) {
  memset(v,0,sizeof(*v)); v->page=page; v->selected=focus;
  v->total=ml_count(); v->first=focus/5u*5u;
  snprintf(v->title,sizeof(v->title),"MASTER LEAGUE");
  v->section=hub_section; v->section_count=4u;
  v->feed_index=feed_index; v->feed_count=4u;
  v->navigation_serial=navigation_serial; v->slide_direction=slide_direction;
  snprintf(v->status,sizeof(v->status),"%s",message);
  v->helper_count=4u;
  v->helper_key[0]="A"; v->helper_label[0]="SELECT";
  v->helper_key[1]="B"; v->helper_label[1]=page==ML_PAGE_HUB ? "SAVE & EXIT" : "BACK";
  v->helper_key[2]="SL"; v->helper_label[2]="PREV PAGE";
  v->helper_key[3]="SR"; v->helper_label[3]="NEXT PAGE";
  snprintf(v->left_title,sizeof(v->left_title),"CAREER");
  snprintf(v->right_title,sizeof(v->right_title),"CLUB OFFICE");
  if (session_ready) {
    snprintf(v->caption,sizeof(v->caption),"%s  /  SEASON %u  /  DAY %u",career.manager_name,career.season,career.day+1u);
    snprintf(v->info[0],96,"%s",exhibition_team_catalog_name(career.settings.club));
    snprintf(v->info[1],96,"%s",ml_competition_name());
    snprintf(v->info[2],96,"LEAGUE POSITION  %u / %u",ml_rank(&career),career.league.team_count);
    snprintf(v->info[3],96,"BOARD TARGET  TOP %u",career.target_rank);
    const MlClub *club=ml_find_club(&career,career.settings.club);
    char cash[32]; ml_money(cash,sizeof(cash),club ? club->cash : 0);
    snprintf(v->info[4],96,"TRANSFER BALANCE  %s",cash);
    snprintf(v->info[5],96,"TRANSFER WINDOW  %s",ml_window_open(&career) ? "OPEN" : "CLOSED");
    v->badge=exhibition_team_catalog_badge(career.settings.club);
  }
  static const char *difficulty[]={"BEGINNER","AMATEUR","REGULAR","PROFESSIONAL","TOP PLAYER","SUPER STAR","LEGEND"};
  if (page==ML_PAGE_HUB) {
    ml_dashboard_view(v);
    static const char *sections[]={"HOME","SQUAD","CLUB OFFICE","COMPETITIONS"};
    static const char *labels[4][4]={
      {"NEXT MATCH","CLUB FEED","SEASON CALENDAR","SAVE CAREER"},
      {"SQUAD","CONTRACTS","TRANSFER MARKET","CLUB FEED"},
      {"TRANSFER MARKET","CONTRACTS","FINANCES","CAREER SETTINGS"},
      {"LEAGUE TABLE","TOP SCORER","DOMESTIC CUP","SEASON CALENDAR"}
    };
    static const char *details[4][4]={
      {"PLAY OR SIMULATE THE NEXT EVENT","RESULTS, CLUB NEWS AND SEASON STORIES","LEAGUE MATCHDAYS AND RESULTS","THREE INDEPENDENT CAREER SLOTS"},
      {"STARTING XI AND RESERVES","RENEW YOUR PLAYERS' CONTRACTS","BUY, SELL AND SIGN FREE AGENTS","YOUR MANAGER AND CLUB PROGRESS"},
      {"SCOUT THE PLAYABLE CLUB POOL","MANAGE EXPIRING CONTRACTS","BALANCE, WAGES AND MATCH INCOME","DIFFICULTY, MATCH LENGTH, CONDITION"},
      {"STANDINGS AND SEASON PROGRESS","THE LEAGUE'S LEADING GOALSCORERS","FOLLOW THE KNOCKOUT ROUNDS","BROWSE YOUR FIXTURES"}
    };
    snprintf(v->left_title,64,"%s",sections[hub_section]);
    snprintf(v->right_title,64,"NEXT EVENT");
    v->count=4u; v->total=4u; v->first=0u; v->selected=focus;
    v->action_count=0u; v->action_selected=0;
    for (uint32_t i=0;i<4u;i++) {
      snprintf(v->rows[i].label,64,"%s",labels[hub_section][i]);
      snprintf(v->rows[i].detail,96,"%s",details[hub_section][i]);
      v->rows[i].enabled=!(hub_section==3u && i==2u && !career.cup_enabled);
      if (!v->rows[i].enabled) snprintf(v->rows[i].detail,96,"NO SUPPORTED DOMESTIC CUP IN THIS LEAGUE");
    }
    MlEvent next={0}; ml_next_event(&career,&next);
    memset(v->info,0,sizeof(v->info));
    snprintf(v->info[0],96,"%s",next.kind==ML_EVENT_SEASON_END ? "SEASON REVIEW" :
             next.kind==ML_EVENT_CUP ? ml_cup_name() : ml_competition_name());
    snprintf(v->info[1],96,"SEASON DAY %u",next.day+1u);
    snprintf(v->info[2],96,"%s",next.home ? exhibition_team_catalog_name(next.home) : "NO CLUB FIXTURE");
    snprintf(v->info[3],96,"%s",next.away ? "VS" : "ADVANCE THE CALENDAR");
    snprintf(v->info[4],96,"%s",next.away ? exhibition_team_catalog_name(next.away) : "");
    snprintf(v->info[6],96,"MANAGER NATIONALITY: %s",exhibition_team_catalog_name(career.manager_nationality));
    if (!hub_section) {
      if (next.home && next.away)
        snprintf(v->rows[0].detail,96,"%.38s VS %.38s",exhibition_team_catalog_name(next.home),exhibition_team_catalog_name(next.away));
      else {
        snprintf(v->rows[0].label,64,"%s",next.kind==ML_EVENT_SEASON_END ? "SEASON REVIEW" : "NEXT EVENT");
        snprintf(v->rows[0].detail,96,"%s",next.kind==ML_EVENT_SEASON_END ? "REVIEW YOUR SEASON AND CONTINUE" : "REST DAY / ADVANCE THE MATCHDAY");
      }
      snprintf(v->rows[0].value,48,"DAY %u",next.day+1u);
      v->rows[0].badge=v->badge;
      snprintf(v->rows[1].value,48,"4 STORIES");
    }
    v->helper_count=3u; v->helper_key[2]="X"; v->helper_label[2]="QUICK SAVE";
    v->helper_label[1]="SAVE & EXIT";
    return;
  }
  if (page==ML_PAGE_NEWS) {
    v->count=0u; v->action_count=0u;
    snprintf(v->title,64,"CLUB FEED");
    memset(v->info,0,sizeof(v->info));
    if (feed_index==0u) {
      snprintf(v->info[0],96,"FROM THE MANAGER'S OFFICE");
      snprintf(v->info[1],96,"%s",career.manager_name);
      snprintf(v->info[2],96,"%s",exhibition_team_catalog_name(career.settings.club));
      snprintf(v->info[3],96,"NATIONALITY  %s",exhibition_team_catalog_name(career.manager_nationality));
      snprintf(v->info[5],96,"SEASON %u: A NEW CHAPTER",career.season);
    } else if (feed_index==1u) {
      const LeagueFixture *last=NULL;
      for (uint32_t i=0;i<career.league.fixture_count;i++) {
        const LeagueFixture *f=&career.league.fixtures[i];
        if (f->complete && (f->home==career.settings.club || f->away==career.settings.club)) last=f;
      }
      snprintf(v->info[0],96,"LATEST LEAGUE RESULT");
      if (last) {
        snprintf(v->info[1],96,"%s",exhibition_team_catalog_name(last->home));
        snprintf(v->info[2],96,"%u - %u",last->home_goals,last->away_goals);
        snprintf(v->info[3],96,"%s",exhibition_team_catalog_name(last->away));
      } else snprintf(v->info[1],96,"NO MATCHES PLAYED YET");
    } else if (feed_index==2u) {
      snprintf(v->info[0],96,"SEASON WATCH");
      snprintf(v->info[1],96,"LEAGUE POSITION  %u / %u",ml_rank(&career),career.league.team_count);
      snprintf(v->info[2],96,"BOARD TARGET  TOP %u",career.target_rank);
      snprintf(v->info[4],96,"%u SEASONS COMPLETED",career.seasons_completed);
    } else {
      snprintf(v->info[0],96,"TRANSFER DESK");
      snprintf(v->info[1],96,"WINDOW  %s",ml_window_open(&career) ? "OPEN" : "CLOSED");
      snprintf(v->info[2],96,"%u COMPLETED CLUB TRANSACTIONS",career.transaction_sequence);
      snprintf(v->info[4],96,"SQUAD SIZE  %u / %u",ml_find_club(&career,career.settings.club)->count,ML_SQUAD_SIZE);
    }
    MlStoryView *story=&v->story;
    story->club_badge=exhibition_team_catalog_badge(career.settings.club);
    story->nation_badge=exhibition_team_catalog_badge(career.manager_nationality);
    snprintf(story->headline,64,"%s",feed_index==0u ? career.manager_name : feed_index==1u ? "MATCH CENTRE" :
        feed_index==2u ? "THE SEASON SO FAR" : "TRANSFER DESK");
    snprintf(story->summary,112,"%s",feed_index==0u ? exhibition_team_catalog_name(career.manager_nationality) :
        feed_index==1u ? "Latest league results" : feed_index==2u ? ml_competition_name() : "Your club's transfer activity");
    for(uint32_t i=career.league.fixture_count;i>0u && story->history_count<3u;i--) {
      const LeagueFixture *f=&career.league.fixtures[i-1u];
      if(feed_index!=1u || !f->complete || (f->home!=career.settings.club && f->away!=career.settings.club))continue;
      if(!story->has_result) {
        story->has_result=1u;story->home_badge=exhibition_team_catalog_badge(f->home);story->away_badge=exhibition_team_catalog_badge(f->away);
        snprintf(story->home,64,"%s",exhibition_team_catalog_name(f->home));snprintf(story->away,64,"%s",exhibition_team_catalog_name(f->away));
        story->home_goals=f->home_goals;story->away_goals=f->away_goals;
      }
      MlViewRow *r=&story->history[story->history_count++];
      const int home=f->home==career.settings.club;const uint32_t opponent=home ? f->away : f->home;
      r->enabled=1;r->badge=exhibition_team_catalog_badge(opponent);
      snprintf(r->label,64,"%s",exhibition_team_catalog_name(opponent));
      snprintf(r->detail,96,"%s / LEAGUE",home ? "HOME" : "AWAY");
      snprintf(r->value,48,"%u - %u",f->home_goals,f->away_goals);
    }
    const MlClub *own=ml_find_club(&career,career.settings.club);
    const char *labels[3]={feed_index==2u ? "LEAGUE POSITION" : feed_index==3u ? "WINDOW" : "SEASON",
      feed_index==2u ? "BOARD TARGET" : feed_index==3u ? "COMPLETED DEALS" : "SQUAD",
      feed_index==2u ? "SEASONS COMPLETED" : feed_index==3u ? "SQUAD" : "BOARD TARGET"};
    for(uint32_t i=0;i<3u;i++)snprintf(story->stat_label[i],32,"%s",labels[i]);
    snprintf(story->stat_value[0],48,"%u",feed_index==2u ? ml_rank(&career) : career.season);
    snprintf(story->stat_value[1],48,feed_index==2u ? "TOP %u" : "%u PLAYERS",feed_index==2u ? career.target_rank : own->count);
    snprintf(story->stat_value[2],48,feed_index==2u ? "%u" : "TOP %u",feed_index==2u ? career.seasons_completed : career.target_rank);
    if(feed_index==3u) {
      uint32_t deals=0u;
      for(uint32_t i=career.office.offer_count;i>0u;i--) {
        const MlOffer *o=&career.office.offers[i-1u];deals+=o->status==ML_OFFER_COMPLETED;
        if(story->history_count>=3u)continue;
        MlViewRow *r=&story->history[story->history_count++];r->enabled=1;
        const uint32_t other=o->incoming ? o->to : o->from;
        r->badge=exhibition_team_catalog_badge(other);
        snprintf(r->label,64,"%s",career.players[o->player].name);
        static const char *status[]={"","WAITING","APPROVED","COUNTEROFFER","REJECTED","COMPLETED","CANCELLED","OFFER EXPIRED"};
        snprintf(r->detail,96,"%s / %.48s",status[o->status],other ? exhibition_team_catalog_name(other) : "FREE AGENT");
        ml_money(r->value,48,o->fee);
      }
      snprintf(story->stat_value[0],48,"%s",ml_window_open(&career) ? "OPEN" : "CLOSED");
      snprintf(story->stat_value[1],48,"%u",deals);snprintf(story->stat_value[2],48,"%u / 40",own->count);
    }
    v->helper_count=3u; v->helper_key[0]="L"; v->helper_label[0]="PREVIOUS STORY";
    v->helper_key[2]="R"; v->helper_label[2]="NEXT STORY";
    return;
  }
  if (page==ML_PAGE_SETTINGS || page==ML_PAGE_MANAGER) {
    v->first=0u; v->count=page==ML_PAGE_MANAGER ? 2u : 5u;
    v->total=v->count; /* The bottom action is not a paginated settings row. */
    v->action_count=1u; v->action_focus=0u; v->action_selected=focus==v->count;
    v->action_enabled[0]=page!=ML_PAGE_MANAGER || (ml_manager_name_valid(manager) && nationality);
    snprintf(v->action[0],32,"%s",page==ML_PAGE_MANAGER ? "START CAREER" : session_ready ? "APPLY" : "NEXT");
    snprintf(v->title,64,"%s",page==ML_PAGE_MANAGER ? "MANAGER PROFILE" : "CAREER SETTINGS");
    const char *labels[]={"LEAGUE","CLUB","COM LEVEL","MATCH LENGTH","PLAYER CONDITION"};
    for (uint32_t i=0;i<v->count;i++) {
      snprintf(v->rows[i].label,64,"%s",page==ML_PAGE_MANAGER ? (i ? "MANAGER NATIONALITY" : "MANAGER NAME") : labels[i]);
      v->rows[i].enabled=page==ML_PAGE_MANAGER || !session_ready || i>1u;
    }
    if (page==ML_PAGE_MANAGER) {
      snprintf(v->rows[0].detail,96,"%s",manager[0] ? manager : "PRESS A TO ENTER NAME");
      snprintf(v->rows[1].detail,96,"%s",nationality ? exhibition_team_catalog_name(nationality) : "SELECT NATIONALITY");
      v->rows[1].badge=nationality ? exhibition_team_catalog_badge(nationality) : 0u;
      snprintf(v->info[0],96,"YOUR MANAGER");
      snprintf(v->info[1],96,"NAME AND NATIONALITY ARE SAVED");
      snprintf(v->info[2],96,"WITH THIS CAREER ONLY.");
      snprintf(v->info[4],96,"NAME: 1-31 LATIN CHARACTERS");
      snprintf(v->info[5],96,"NATIONALITY DOES NOT CHANGE");
      snprintf(v->info[6],96,"YOUR CLUB OR ITS PLAYER ROSTER.");
    } else {
      const Fl26LeagueCatalogEntry *entry=ml_league_entry();
      snprintf(v->rows[0].detail,96,"%s",session_ready ? ml_competition_name() : entry ? entry->name : "NO AVAILABLE LEAGUE");
      const uint32_t club=session_ready ? career.settings.club : entry ? entry->team_ids[club_choice] : 0u;
      snprintf(v->rows[1].detail,96,"%s",exhibition_team_catalog_name(club));
      v->rows[1].badge=exhibition_team_catalog_badge(club);
      snprintf(v->rows[2].value,48,"%s",difficulty[setup.difficulty]);
      snprintf(v->rows[3].value,48,"%u MIN",setup.match_minutes);
      snprintf(v->rows[4].value,48,"%s",setup.condition==5u ? "RANDOM" : "NORMAL");
      snprintf(v->info[0],96,"EXISTING CLUB CAREER");
      snprintf(v->info[1],96,"FIXED LEAGUE PARTICIPANTS");
      snprintf(v->info[2],96,"HOME & AWAY / BY STANDINGS");
      snprintf(v->info[4],96,"LEFT / RIGHT TO CHANGE");
      snprintf(v->info[5],96,"A ON CLUB TO BROWSE TEAMS");
      snprintf(v->info[6],96,"SUPPORTED PLAYABLE POOL");
      snprintf(v->info[7],96,"NO PROMOTION / RELEGATION YET");
    }
    v->helper_count=2u; return;
  }
  if (page==ML_PAGE_CONFIRM) {
    snprintf(v->title,64,"CONFIRM"); v->count=0u; v->action_count=2u;
    v->action_selected=1; v->action_focus=focus;
    snprintf(v->action[0],32,"CONFIRM"); snprintf(v->action[1],32,"CANCEL");
    v->action_enabled[0]=v->action_enabled[1]=1;
    memset(v->info,0,sizeof(v->info));
    if (confirm_kind==3u) { snprintf(v->left_title,64,"SIMULATE THIS EVENT?"); snprintf(v->info[0],96,"RESULTS WILL BE SAVED."); }
    else if (confirm_kind==4u) { snprintf(v->left_title,64,"OVERWRITE SAVE SLOT %u?",overwrite_slot+1u); snprintf(v->info[0],96,"THIS REPLACES THE SELECTED CAREER."); }
    else {
      const MlPlayer *p=&career.players[transaction_player]; char fee[32];
      ml_money(fee,sizeof(fee),confirm_kind==2u ? 0 : ml_transfer_value(p));
      snprintf(v->left_title,64,"%s",p->name);
      snprintf(v->info[0],96,"%s",confirm_kind==2u ? "CONTRACT RENEWAL" : "PERMANENT TRANSFER");
      snprintf(v->info[1],96,"DESTINATION: %s",exhibition_team_catalog_name(confirm_kind==2u ? p->club : destination));
      snprintf(v->info[2],96,"TRANSFER FEE: %s",fee);
      snprintf(v->info[3],96,"CONTRACT: %u YEARS",years);
      snprintf(v->info[4],96,"WEEKLY WAGE: %u",p->wage ? p->wage : 1000u+(p->overall>40u ? p->overall-40u : 1u)*(p->overall>40u ? p->overall-40u : 1u)*15u);
      snprintf(v->info[6],96,"LEFT / RIGHT: CONTRACT DURATION");
      snprintf(v->info[7],96,"GAME ECONOMY, NOT REAL SALARIES");
    }
    v->helper_count=2u; return;
  }
  if (page==ML_PAGE_FINANCES) {
    v->count=5u; v->first=0u; v->total=5u;
    const MlClub *club=ml_find_club(&career,career.settings.club);
    const char *labels[]={"CASH BALANCE","WEEKLY WAGES / BUDGET","WAGES PAID THIS SEASON","MATCH REVENUE","PRIZE MONEY"};
    for (uint32_t i=0;i<5u;i++) { snprintf(v->rows[i].label,64,"%s",labels[i]); v->rows[i].enabled=1; }
    ml_money(v->rows[0].value,48,club->cash);
    snprintf(v->rows[1].detail,96,"%u / %u",ml_weekly_wage(&career,club->team),club->wage_budget);
    ml_money(v->rows[2].value,48,career.wages_paid);
    ml_money(v->rows[3].value,48,career.match_income);
    ml_money(v->rows[4].value,48,career.prize_income);
    snprintf(v->title,64,"FINANCES"); v->helper_count=2u; return;
  }
  uint8_t standings[LEAGUE_MAX_TEAMS]={0}; uint16_t scorers[4]={0}; uint32_t scorer_count=0u;
  if (page==ML_PAGE_TABLE) {
    league_tournament_ranked_slots(&career.league,standings);
    scorer_count=league_tournament_top_scorers(&career.league,scorers);
    if (table_scorers) v->total=scorer_count;
    v->helper_count=3u; v->helper_key[2]="Y";
    v->helper_label[2]=table_scorers ? "LEAGUE TABLE" : "TOP SCORER";
    snprintf(v->title,64,"%s",table_scorers ? "TOP SCORER" : "LEAGUE TABLE");
    if (!v->total) snprintf(v->left_title,64,"NO MATCHES PLAYED YET");
  }
  for (uint32_t r=0;r<5u && v->first+r<v->total;r++) {
    const uint32_t index=v->first+r;
    MlViewRow *row=&v->rows[v->count++]; row->enabled=1;
    switch(page) {
      case ML_PAGE_LANDING:
        snprintf(row->label,64,"%s",index ? "CONTINUE" : "NEW");
        snprintf(row->detail,96,"%s",index ? "LOAD ONE OF THREE CAREER SAVES" : "BUILD YOUR CLUB ACROSS SEASONS");
        row->enabled=index || league_count; v->helper_count=2u;
        snprintf(v->info[0],96,"EXISTING CLUB CAREER");
        snprintf(v->info[2],96,"SQUAD / TRANSFERS / CONTRACTS");
        snprintf(v->info[3],96,"LEAGUE / DOMESTIC CUP");
        snprintf(v->info[4],96,"PLAY OR SIMULATE");
        snprintf(v->info[6],96,"THREE INDEPENDENT SAVE SLOTS");
        break;
      case ML_PAGE_SLOTS:
        snprintf(v->title,64,"%s",saving ? "SAVE CAREER" : "LOAD CAREER");
        snprintf(row->label,64,"SLOT %u - %.48s",index+1u,slot_club[index]);
        snprintf(row->detail,96,"%s",slot_progress[index]); row->enabled=saving || slot_valid[index];
        v->helper_count=2u; break;
      case ML_PAGE_NATIONALITY: case ML_PAGE_CLUBS: case ML_PAGE_MARKET_CLUBS: {
        uint32_t team=page==ML_PAGE_NATIONALITY ? countries[index] :
            page==ML_PAGE_CLUBS ? ml_league_entry()->team_ids[index] :
            index<career.club_count ? career.clubs[index].team : 0u;
        snprintf(v->title,64,"%s",page==ML_PAGE_NATIONALITY ? "MANAGER NATIONALITY" :
            page==ML_PAGE_CLUBS ? "SELECT CLUB" : destination ? "SELECT BUYING CLUB" : "TRANSFER MARKET");
        snprintf(row->label,64,"%s",team ? exhibition_team_catalog_name(team) : "FREE AGENTS");
        row->badge=team ? exhibition_team_catalog_badge(team) : 0u;
        break;
      }
      case ML_PAGE_SQUAD: case ML_PAGE_MARKET_PLAYERS: case ML_PAGE_CONTRACTS: {
        const MlPlayer *p=&career.players[row_players[index]];
        snprintf(v->title,64,"%s",page==ML_PAGE_SQUAD ? "SQUAD" : page==ML_PAGE_CONTRACTS ? "CONTRACTS" : "TRANSFER MARKET");
        snprintf(row->label,64,"%s",p->name);
        snprintf(row->detail,96,"%s  /  STR %u  /  #%u  /  CONTRACT S%u",ml_role(p->position),p->overall,p->shirt,p->contract_end);
        if (page==ML_PAGE_SQUAD) snprintf(row->value,48,"%s",index==selected_player ? "SELECTED" : index<11u ? "STARTER" : "RESERVE");
        else ml_money(row->value,48,ml_transfer_value(p));
        row->portrait=p->portrait_id;
        if (page==ML_PAGE_SQUAD) {
          v->helper_label[0]=selected_player==ML_INVALID_INDEX ? "CHOOSE PLAYER" : "SWAP";
          snprintf(v->info[6],96,"FORMATION / PRESETS: GAME PLAN");
          snprintf(v->info[7],96,"AVAILABLE BEFORE EACH KICKOFF");
        }
        break;
      }
      case ML_PAGE_OFFICE: {
        const char *labels[]={"TRANSFERS","CONTRACTS","FINANCES","COMPETITIONS","GENERAL SETTINGS"};
        snprintf(row->label,64,"%s",labels[index]); snprintf(v->title,64,"CLUB OFFICE"); break;
      }
      case ML_PAGE_CALENDAR: {
        snprintf(v->title,64,"SEASON CALENDAR");
        snprintf(row->label,64,"MATCHDAY %u / %u",index+1u,career.league.matchday_count);
        const uint32_t n=career.league.matchday_fixture_count[index];
        const LeagueFixture *own=NULL;
        for(uint32_t i=0;i<n;i++) {
          const LeagueFixture *f=league_tournament_matchday_fixture(&career.league,index,i);
          if(f && (f->home==career.settings.club || f->away==career.settings.club)) own=f;
        }
        if(own) {
          const uint32_t opponent=own->home==career.settings.club ? own->away : own->home;
          snprintf(row->detail,96,"%s  /  %s",own->home==career.settings.club ? "HOME" : "AWAY",exhibition_team_catalog_name(opponent));
          row->badge=exhibition_team_catalog_badge(opponent);
          if(own->complete) snprintf(row->value,48,"%u - %u",own->home_goals,own->away_goals);
          else snprintf(row->value,48,"PENDING");
        } else snprintf(row->detail,96,"REST DAY");
        v->helper_count=2u; break;
      }
      case ML_PAGE_CUP: {
        snprintf(v->title,64,"%s",ml_cup_name());
        snprintf(row->label,64,"%s",index+1u==career.cup.round_count ? "FINAL" : index+2u==career.cup.round_count ? "SEMI FINAL" : index+3u==career.cup.round_count ? "QUARTER FINAL" : "OPENING ROUND");
        const uint32_t n=cup_tournament_fixture_count(&career.cup,index);
        const CupFixture *own=NULL;
        for(uint32_t i=0;i<n;i++) {
          const CupFixture *f=cup_tournament_fixture(&career.cup,index,i);
          if(f && (f->home==career.settings.club || f->away==career.settings.club)) own=f;
        }
        if(own) {
          const uint32_t opponent=own->home==career.settings.club ? own->away : own->home;
          snprintf(row->detail,96,"%s",opponent ? exhibition_team_catalog_name(opponent) : "BYE");
          row->badge=opponent ? exhibition_team_catalog_badge(opponent) : 0u;
          if(own->complete) snprintf(row->value,48,"%u - %u",own->home_goals,own->away_goals);
          else snprintf(row->value,48,"PENDING");
        } else snprintf(row->detail,96,"%s",index>career.cup.active_round ? "TO BE DECIDED" : "YOUR CLUB DID NOT REACH THIS ROUND");
        snprintf(v->info[6],96,"%s",career.cup.champion ? "CUP CHAMPION" : "SINGLE-LEG KNOCKOUT");
        if(career.cup.champion) snprintf(v->info[7],96,"%s",exhibition_team_catalog_name(career.cup.champion));
        v->helper_count=2u; break;
      }
      case ML_PAGE_NEXT:
        if (pending.kind==ML_EVENT_SEASON_END) snprintf(row->label,64,"%s",index ? "BACK" : "START NEXT SEASON");
        else { snprintf(row->label,64,"%s",index ? "SIMULATE" : "PLAY MATCH"); row->enabled=index || (pending.home && pending.away); }
        snprintf(v->left_title,64,"%s",pending.kind==ML_EVENT_SEASON_END ? "SEASON COMPLETE" : pending.kind==ML_EVENT_CUP ? ml_cup_name() : ml_competition_name());
        snprintf(row->detail,96,"%s",index ? "ADVANCE THE WHOLE MATCH EVENT" : "YOUR GAME PLAN IS AVAILABLE BEFORE KICKOFF");
        v->helper_count=2u; break;
      case ML_PAGE_TABLE:
        if (table_scorers) {
          const LeagueScorer *s=&career.league.scorers[scorers[index]];
          snprintf(row->label,64,"%u  %s",index+1u,s->name); snprintf(row->detail,96,"%s",exhibition_team_catalog_name(s->team));
          snprintf(row->value,48,"%u GOALS",s->goals); row->portrait=s->portrait_id;
          row->badge=exhibition_team_catalog_badge(s->team);
        } else {
          const LeagueStanding *s=&career.league.standings[standings[index]];
          snprintf(row->label,64,"%u  %.55s",index+1u,exhibition_team_catalog_name(s->team));
          snprintf(row->detail,96,"P %u   W %u   D %u   L %u   GD %+d",s->played,s->wins,s->draws,s->losses,(int)s->goals_for-s->goals_against);
          snprintf(row->value,48,"%u PTS",s->points); row->badge=exhibition_team_catalog_badge(s->team);
        }
        break;
      default: break;
    }
  }
}

#include "master_league_navigation.inc"

void ml_frontend_view(MlView *v) {
  if(page==ML_PAGE_CONFIRM) {
    *v=confirm_background;memset(&v->drawer,0,sizeof(v->drawer));
    v->modal.open=1u;v->modal.selected=focus;v->modal.destructive=confirm_kind==4u || confirm_kind==6u;
    snprintf(v->modal.accept,32,"%s",confirm_kind==3u ? "SIMULATE" : confirm_kind==5u ? "PLAY MATCH" : "CONFIRM");
    snprintf(v->modal.title,64,"%s",confirm_kind==3u ? "SIMULATE MATCH?" : confirm_kind==5u ? "PLAY MATCH?" : "CONFIRM");
    snprintf(v->modal.body,256,"%s",confirm_kind==3u ? "Simulate this event and save the result? This cannot be undone." :
      "Open the pre-match Game Plan and play this fixture? The calendar advances after the match is completed.");
    if(confirm_kind==4u) {
      snprintf(v->modal.title,64,"OVERWRITE SLOT %u?",overwrite_slot+1u);
      snprintf(v->modal.body,256,"Replace %s in this slot with the current career? Other slots remain unchanged.",slot_club[overwrite_slot]);
      snprintf(v->modal.accept,32,"OVERWRITE");
    }else if(confirm_kind==6u) {
      char fee[32];ml_money(fee,sizeof(fee),ml_release_value(&career,transaction_player));
      snprintf(v->modal.title,64,"RELEASE PLAYER?");
      snprintf(v->modal.body,256,"Release %s as a free agent? Compensation: %s. Weekly wages stop. This cannot be undone.",career.players[transaction_player].name,fee);
      snprintf(v->modal.accept,32,"RELEASE");
    }
    snprintf(v->modal.error,112,"%s",message);v->status[0]=v->toast[0]=0;
    v->helper_count=2u;v->helper_key[0]="A";v->helper_label[0]="SELECT";v->helper_key[1]="B";v->helper_label[1]="CANCEL";
    return;
  }
  ml_base_view(v);
  ml_review_view(v);
}
