#include <assert.h>
#include <stdint.h>
#include <string.h>

#include "competition_frontend.h"

enum {
  BUTTON_B = 1u << 0,
  BUTTON_A = 1u << 1,
  BUTTON_Y = 1u << 2,
  BUTTON_X = 1u << 3,
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

int main(void) {
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_LANDING);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_SETTINGS);
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  for (uint32_t i = 0; i < 20u; i++) press(BUTTON_LEFT);
  assert(strcmp(competition_frontend_item_value(2u), "2") == 0);
  press(BUTTON_DOWN);
  assert(strcmp(competition_frontend_item_value(3u), "OFF") == 0);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_HUB);
  assert(competition_frontend_league_draft()->team_count == 2u);
  assert(strcmp(competition_frontend_item_label(0u), "TEAMS") == 0);
  assert(strcmp(competition_frontend_item_label(1u), "GENERAL SETTING") == 0);
  assert(strcmp(competition_frontend_item_label(2u), "NEXT") == 0);
  assert(strcmp(competition_frontend_item_label(3u), "SAVE") == 0);
  assert(!competition_frontend_item_enabled(2u));
  press(BUTTON_A); /* Teams editor. */
  assert(competition_frontend_league_teams_editing());
  press(BUTTON_X); /* Assign all missing teams. */
  assert(competition_draft_ready(competition_frontend_league_draft()));
  assert(competition_frontend_league_tournament()->matchday_count == 1u);
  press(BUTTON_B);
  assert(!competition_frontend_league_teams_editing());
  press(BUTTON_RIGHT);
  press(BUTTON_A); /* General settings. */
  assert(competition_frontend_cup_general_open());
  press(BUTTON_B);
  press(BUTTON_RIGHT);
  assert(competition_frontend_focus() == 2u);
  assert(competition_frontend_item_enabled(2u));
  press(BUTTON_Y);
  assert(competition_frontend_league_scorers_open());
  press(BUTTON_Y);
  assert(!competition_frontend_league_scorers_open());
  press(BUTTON_RIGHT);
  press(BUTTON_A); /* Save slot 1. */
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_SLOTS);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_HUB);
  assert(competition_frontend_league_draft()->team_count == 2u);

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
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_HUB);
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
  competition_frontend_league_match_result(2u, 0u);
  competition_frontend_league_restore_after_match();
  assert(competition_frontend_league_tournament()->phase ==
         LEAGUE_PHASE_KNOCKOUT);
  assert(!competition_frontend_item_enabled(0u));
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
  assert(competition_frontend_item_count() == 1u);
  assert(strcmp(competition_frontend_item_label(0u), "TOP TO MENU") == 0);
  press(BUTTON_B);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_HUB);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_NONE);

  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_LEAGUE_SETTINGS);
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  for (uint32_t i = 0; i < 20u; i++) press(BUTTON_LEFT);
  press(BUTTON_DOWN);
  press(BUTTON_RIGHT); /* Home & Away ON: reversed return leg. */
  assert(strcmp(competition_frontend_item_value(3u), "ON") == 0);
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
  for (uint32_t i = 0; i < 4u; i++) press(BUTTON_DOWN);
  press(BUTTON_A); /* Default 16-team season has 8 fixtures per day. */
  press(BUTTON_A);
  press(BUTTON_X);
  press(BUTTON_B);
  assert(competition_frontend_league_tournament()->
         matchday_fixture_count[0] == 8u);
  press(BUTTON_DOWN);
  assert(competition_frontend_league_schedule_page() == 1u);
  press(BUTTON_R);
  assert(competition_frontend_league_table_page() == 1u);
  assert(competition_frontend_league_schedule_page() == 1u);
  return 0;
}
