#include <assert.h>
#include <stdint.h>
#include <string.h>

#include "competition_frontend.h"
#include "league_save.h"

enum {
  BUTTON_B = 1u << 0,
  BUTTON_A = 1u << 1,
  BUTTON_Y = 1u << 2,
  BUTTON_X = 1u << 3,
  BUTTON_L = 1u << 4,
  BUTTON_UP = 1u << 10,
  BUTTON_R = 1u << 7,
  BUTTON_DOWN = 1u << 11,
  BUTTON_LEFT = 1u << 12,
  BUTTON_RIGHT = 1u << 13,
};

uint32_t pes_controller_native_hid_connected_mask(void) { return 3u; }

static void press(uint32_t button) {
  competition_frontend_pad_event(0u, 0u);
  competition_frontend_pad_event(button, 0u);
  competition_frontend_pad_event(0u, 0u);
}

#include "competition_confirmation_checks.inc"

static void focus_hub(uint32_t target) {
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_HUB);
  if (competition_frontend_league_page() != LEAGUE_PAGE_HOME) press(BUTTON_B);
  const int top = target == 5u || target == 2u;
  const uint32_t current = competition_frontend_focus();
  if (top != (current == 5u || current == 2u)) press(BUTTON_UP);
  for (uint32_t i=0;i<4u && competition_frontend_focus()!=target;i++) press(BUTTON_RIGHT);
  assert(competition_frontend_focus()==target);
}

int main(void) {
  assert(competition_frontend_scoreboard(101u,107u)==9u);
  assert(competition_frontend_scoreboard(101u,108u)==0u);
  assert(competition_frontend_scoreboard(0u,107u)==0u);
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_LANDING);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_SETTINGS);
  press(BUTTON_LEFT); /* FootballNX is the custom, unrestricted preset. */
  assert(strcmp(competition_frontend_item_value(0u), "FOOTBALLNX LEAGUE") == 0);
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  for (uint32_t i = 0; i < 20u; i++) press(BUTTON_LEFT);
  assert(strcmp(competition_frontend_item_value(2u), "2") == 0);
  press(BUTTON_DOWN);
  assert(strcmp(competition_frontend_item_value(3u), "OFF") == 0);
  press(BUTTON_DOWN);
  assert(strcmp(competition_frontend_item_value(4u), "KNOCKOUT STAGES") == 0);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_HUB);
  assert(competition_frontend_league_draft()->team_count == 2u);
  assert(strcmp(competition_frontend_item_label(0u), "TEAMS") == 0);
  assert(strcmp(competition_frontend_item_label(1u), "GENERAL SETTING") == 0);
  assert(strcmp(competition_frontend_item_label(2u), "NEXT") == 0);
  assert(strcmp(competition_frontend_item_label(3u), "SAVE") == 0);
  assert(!competition_frontend_item_enabled(2u));
  press(BUTTON_RIGHT); /* Bottom cards follow their on-screen positions. */
  assert(competition_frontend_focus() == 4u);
  press(BUTTON_RIGHT);
  assert(competition_frontend_focus() == 1u);
  press(BUTTON_UP); /* Disabled Next remains focusable for its explanation. */
  assert(competition_frontend_focus() == 2u);
  press(BUTTON_A);
  assert(competition_frontend_take_action() == COMPETITION_ACTION_NONE);
  focus_hub(0u);
  press(BUTTON_A); /* Teams editor. */
  assert(competition_frontend_league_teams_editing());
  press(BUTTON_X); /* Assign all missing teams. */
  assert(strcmp(competition_frontend_status(), "") == 0);
  assert(competition_draft_ready(competition_frontend_league_draft()));
  assert(competition_frontend_league_tournament()->matchday_count == 1u);
  press(BUTTON_B);
  assert(!competition_frontend_league_teams_editing());
  focus_hub(1u);
  press(BUTTON_A); /* General settings. */
  assert(competition_frontend_cup_general_open());
  press(BUTTON_B);
  focus_hub(2u);
  assert(competition_frontend_item_enabled(2u));
  focus_hub(5u);press(BUTTON_A);
  assert(competition_frontend_league_page() == LEAGUE_PAGE_MATCHES);
  press(BUTTON_X);
  assert(competition_frontend_league_scorers_open());
  press(BUTTON_X);
  assert(!competition_frontend_league_scorers_open());
  focus_hub(3u);
  press(BUTTON_A); /* Save slot 1. */
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_SLOTS);
  assert(strcmp(competition_frontend_slot_competition(0u),
                "NO SAVE DATA") == 0);
  assert(strcmp(competition_frontend_slot_progress(0u), "") == 0);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_HUB);
  assert(competition_frontend_league_draft()->team_count == 2u);
  static LeagueSaveState retired_preset_save;
  check_save_confirmations(0);
  assert(league_save_read(0u, &retired_preset_save));
  retired_preset_save.league_competition_id = 22u;
  assert(league_save_write(0u, &retired_preset_save));

  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  press(BUTTON_DOWN);
  press(BUTTON_A); /* Continue from save slot 1. */
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_SLOTS);
  assert(competition_frontend_item_enabled(0u));
  assert(strcmp(competition_frontend_slot_competition(0u),
                "ARGENTINA LEAGUE") == 0);
  assert(strcmp(competition_frontend_slot_progress(0u),
                "MATCHDAY 1/1") == 0);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_HUB);
  assert(strcmp(competition_frontend_league_name(), "FOOTBALLNX LEAGUE") == 0);
  assert(competition_draft_ready(competition_frontend_league_draft()));
  assert(competition_frontend_league_tournament()->matchday_count == 1u);
  assert(competition_frontend_focus() == 2u);
  press(BUTTON_A);
  assert(competition_frontend_take_action() ==
         COMPETITION_ACTION_LEAGUE_FIXTURE);
  uint32_t home = 0, away = 0;
  assert(competition_frontend_league_match_teams(&home, &away));
  assert(home && away && home != away);
  assert(!competition_frontend_league_match_is_knockout());
  competition_frontend_league_handoff_result(1);
  assert(competition_frontend_scoreboard(101u,107u)==1001u);
  /* Match Hub B: no result means the exact fixture remains available. */
  const LeagueTournament before_abort = *competition_frontend_league_tournament();
  const uint32_t abort_home = home, abort_away = away;
  competition_frontend_league_restore_after_match();
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_HUB);
  assert(!competition_frontend_league_match_active());
  assert(!memcmp(&before_abort, competition_frontend_league_tournament(), sizeof(before_abort)));
  assert(competition_frontend_item_enabled(2u));
  press(BUTTON_A);
  assert(competition_frontend_take_action() == COMPETITION_ACTION_LEAGUE_FIXTURE);
  assert(competition_frontend_league_match_teams(&home, &away));
  assert(home == abort_home && away == abort_away);
  competition_frontend_league_handoff_result(1);
  competition_frontend_league_match_result(2u, 0u);
  competition_frontend_league_restore_after_match();
  assert(competition_frontend_league_tournament()->phase ==
         LEAGUE_PHASE_KNOCKOUT);
  assert(competition_frontend_item_enabled(0u));
  focus_hub(0u);press(BUTTON_A);
  assert(competition_frontend_league_page() == LEAGUE_PAGE_TEAMS);
  assert(!competition_frontend_league_teams_editing());
  const LeagueTournament locked = *competition_frontend_league_tournament();
  press(BUTTON_X);press(BUTTON_A);
  assert(!competition_frontend_cup_team_picker_active());
  assert(!memcmp(&locked,competition_frontend_league_tournament(),sizeof(locked)));
  focus_hub(2u);
  assert(competition_frontend_focus() == 2u);
  press(BUTTON_A);
  assert(competition_frontend_take_action() ==
         COMPETITION_ACTION_LEAGUE_FIXTURE);
  assert(competition_frontend_league_match_is_knockout());
  assert(competition_frontend_league_match_teams(&home, &away));
  competition_frontend_league_handoff_result(1);
  competition_frontend_league_match_result(1u, 0u);
  competition_frontend_league_restore_after_match();
  assert(competition_frontend_league_tournament()->phase ==
         LEAGUE_PHASE_COMPLETE);
  assert(competition_frontend_item_count() == 6u);
  press(BUTTON_A); /* Completed seasons retain their results pages. */
  assert(competition_frontend_league_page() == LEAGUE_PAGE_BRACKET);
  press(BUTTON_X);
  assert(competition_frontend_league_page() == LEAGUE_PAGE_TABLE);
  press(BUTTON_Y);
  assert(competition_frontend_league_page() == LEAGUE_PAGE_BRACKET);
  focus_hub(3u);press(BUTTON_A);press(BUTTON_A);
  assert(competition_frontend_confirmation_active());
  press(BUTTON_LEFT);press(BUTTON_A);
  LeagueSaveState completed;
  assert(league_save_read(0u,&completed));
  assert(completed.tournament.phase==LEAGUE_PHASE_COMPLETE);
  press(BUTTON_B);
  assert(competition_frontend_confirmation_active() && !competition_frontend_closing());
  press(BUTTON_LEFT);press(BUTTON_A);
  assert(competition_frontend_closing());

  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_SETTINGS);
  press(BUTTON_LEFT);
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  for (uint32_t i = 0; i < 20u; i++) press(BUTTON_LEFT);
  press(BUTTON_DOWN);
  press(BUTTON_RIGHT); /* Home & Away ON: reversed return leg. */
  assert(strcmp(competition_frontend_item_value(3u), "ON") == 0);
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  press(BUTTON_A);
  press(BUTTON_X);
  const LeagueTournament *league = competition_frontend_league_tournament();
  assert(league->matchday_count == 2u);
  assert(league->fixture_count == 2u);
  assert(league->fixtures[0].home == league->fixtures[1].away);
  assert(league->fixtures[0].away == league->fixtures[1].home);

  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  press(BUTTON_A);
  assert(strcmp(competition_frontend_item_value(0u), "PREMIER LEAGUE") == 0);
  assert(strcmp(competition_frontend_item_value(4u), "BY STANDING") == 0);
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  char fixed_team_count[16];
  strcpy(fixed_team_count, competition_frontend_item_value(2u));
  press(BUTTON_LEFT);
  press(BUTTON_RIGHT);
  press(BUTTON_A);
  assert(strcmp(competition_frontend_item_value(2u), fixed_team_count) == 0);
  for (uint32_t i = 0; i < 3u; i++) press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_HUB);
  press(BUTTON_A);
  assert(competition_frontend_league_teams_editing());
  press(BUTTON_A);
  assert(competition_frontend_cup_picker_focused_team() != 0u);
  press(BUTTON_B);

  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  press(BUTTON_A);
  press(BUTTON_LEFT); /* Preserve the 16-team custom-league regression. */
  for (uint32_t i = 0; i < 5u; i++) press(BUTTON_DOWN);
  press(BUTTON_A); /* Default 16-team season has 8 fixtures per day. */
  press(BUTTON_A);
  press(BUTTON_X);
  press(BUTTON_B);
  assert(competition_frontend_league_tournament()->
         matchday_fixture_count[0] == 8u);
  focus_hub(5u);press(BUTTON_A);press(BUTTON_DOWN);
  assert(competition_frontend_league_schedule_page() == 1u);
  const LeagueTournament before = *competition_frontend_league_tournament();
  press(BUTTON_R);
  assert(competition_frontend_league_view_matchday() == 1u);
  assert(competition_frontend_league_schedule_page() == 0u);
  press(BUTTON_L);
  assert(competition_frontend_league_view_matchday() == 0u);
  focus_hub(4u);press(BUTTON_A);press(BUTTON_R);
  assert(competition_frontend_league_table_page() == 1u);
  press(BUTTON_R); /* Six rows per page; 16 teams ends on page three. */
  assert(competition_frontend_league_table_page() == 2u);
  press(BUTTON_R);assert(competition_frontend_league_table_page() == 2u);
  press(BUTTON_L);assert(competition_frontend_league_table_page() == 1u);
  assert(!memcmp(&before,competition_frontend_league_tournament(),sizeof(before)));
  /* Carousel advances only on home, never while browsing a submenu. */
  uint64_t tick=1000u;competition_frontend_tick(tick);
  const uint32_t news=competition_frontend_league_news_index();
  for(uint32_t i=0;i<8u;i++)competition_frontend_tick(tick+=1000u);
  assert(competition_frontend_league_news_index()==news);
  press(BUTTON_B);
  for(uint32_t i=0;i<6u;i++)competition_frontend_tick(tick+=1000u);
  assert(competition_frontend_league_news_index()==(news+1u)%4u);
  assert(!memcmp(&before,competition_frontend_league_tournament(),sizeof(before)));
  return 0;
}
