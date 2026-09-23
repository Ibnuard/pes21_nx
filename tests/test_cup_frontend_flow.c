#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "competition_frontend.h"
#include "exhibition_team_catalog.h"

enum {
  BUTTON_B = 1u << 0,
  BUTTON_A = 1u << 1,
  BUTTON_X = 1u << 3,
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
  competition_frontend_pad_event(0u, 0u); /* consume opening A tick */
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_LANDING);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_SETTINGS);
  for (uint32_t row = 0; row < 8u; row++) press(BUTTON_DOWN);
  assert(competition_frontend_focus() == 8u);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
  assert(competition_frontend_cup_draft());
  assert(!competition_frontend_item_enabled(1u));
  assert(competition_frontend_item_enabled(0u));

  press(BUTTON_A); /* Bracket edit */
  assert(competition_frontend_cup_bracket_editing());
  press(BUTTON_A); /* one-sided team selector */
  assert(competition_frontend_cup_team_picker_active());
  const uint32_t manual_team = exhibition_team_catalog_first_id();
  assert(manual_team);
  competition_frontend_cup_team_picker_result(manual_team);
  assert(!competition_frontend_cup_team_picker_active());
  assert(competition_frontend_cup_draft()->teams[0] == manual_team);
  press(BUTTON_X); /* fill only remaining slots */
  assert(competition_draft_ready(competition_frontend_cup_draft()));
  assert(competition_frontend_cup_draft()->teams[0] == manual_team);
  press(BUTTON_B); /* return to four actions */
  assert(!competition_frontend_cup_bracket_editing());
  assert(competition_frontend_item_enabled(1u));

  press(BUTTON_RIGHT);
  assert(competition_frontend_focus() == 1u);
  press(BUTTON_RIGHT);
  assert(competition_frontend_focus() == 2u);
  press(BUTTON_A); /* Save */
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_SLOTS);
  press(BUTTON_A); /* Slot 1 */
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
  assert(competition_frontend_cup_draft()->teams[0] == manual_team);

  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_A);
  press(BUTTON_DOWN);
  press(BUTTON_A); /* Continue */
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_SLOTS);
  assert(competition_frontend_item_enabled(0u));
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
  assert(competition_frontend_cup_draft()->teams[0] == manual_team);
  assert(competition_frontend_item_enabled(1u));

  /* A three-team Cup keeps semi-final, final, and champion on one view,
   * freezes the bracket after the first match, and hides Next at Game Over. */
  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_A);
  press(BUTTON_A);
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  for (uint32_t i = 0; i < 5u; i++) press(BUTTON_LEFT);
  assert(competition_frontend_cup_team_count() == 3u);
  while (competition_frontend_focus() != 8u) press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_cup_view_count() == 1u);
  press(BUTTON_A);
  press(BUTTON_X);
  press(BUTTON_B);
  press(BUTTON_RIGHT);
  for (uint32_t match = 0; match < 2u; match++) {
    press(BUTTON_A);
    assert(competition_frontend_take_action() ==
           COMPETITION_ACTION_CUP_FIXTURE);
    uint32_t home = 0, away = 0;
    assert(competition_frontend_cup_match_teams(&home, &away));
    assert(home && away);
    competition_frontend_cup_handoff_result(1);
    competition_frontend_cup_match_result(1u, 0u);
    competition_frontend_cup_restore_after_match();
    assert(!competition_frontend_item_enabled(0u));
    if (competition_frontend_cup_tournament()->champion) break;
  }
  assert(competition_frontend_cup_tournament()->champion);
  assert(competition_frontend_focus() == 3u);
  assert(!competition_frontend_item_enabled(1u));
  assert(!competition_frontend_item_label(1u)[0]);

  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_A);
  press(BUTTON_A);
  press(BUTTON_RIGHT); /* English Cup uses its eligible league pool. */
  assert(competition_frontend_cup_team_count() ==
         exhibition_team_categories[0].team_count);
  while (competition_frontend_focus() != 8u) press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_cup_draft()->team_count ==
         exhibition_team_categories[0].team_count);
  press(BUTTON_A);
  press(BUTTON_X);
  assert(competition_draft_ready(competition_frontend_cup_draft()));
  puts("Cup frontend flow tests passed");
  return 0;
}
