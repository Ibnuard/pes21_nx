#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "competition_frontend.h"
#include "exhibition_team_catalog.h"

enum {
  BUTTON_B = 1u << 0,
  BUTTON_A = 1u << 1,
  BUTTON_Y = 1u << 2,
  BUTTON_X = 1u << 3,
  BUTTON_L = 1u << 4,
  BUTTON_R = 1u << 7,
  BUTTON_UP = 1u << 10,
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
  assert(competition_frontend_cup_tournament()->history_count == 0u);
  const uint32_t other_team = competition_frontend_cup_draft()->teams[1];
  press(BUTTON_Y); /* mark source slot */
  assert(competition_frontend_cup_bracket_swap_source() == 0u);
  press(BUTTON_DOWN);
  press(BUTTON_Y); /* exchange complete team+owner entries */
  assert(competition_frontend_cup_bracket_swap_source() == UINT32_MAX);
  assert(competition_frontend_cup_draft()->teams[1] == manual_team);
  assert(competition_frontend_cup_draft()->owners[1] == 1u);
  assert(competition_frontend_cup_tournament()->history_count == 0u);
  press(BUTTON_Y);
  press(BUTTON_UP);
  press(BUTTON_Y); /* restore source for the save test */
  assert(competition_frontend_cup_draft()->teams[0] == manual_team);
  press(BUTTON_A);
  assert(competition_frontend_cup_team_picker_active());
  competition_frontend_cup_team_picker_result(other_team);
  assert(competition_frontend_cup_draft()->teams[0] == other_team);
  assert(competition_frontend_cup_draft()->teams[1] == manual_team);
  assert(competition_frontend_cup_draft()->owners[0] == 1u);
  press(BUTTON_A);
  competition_frontend_cup_team_picker_result(manual_team);
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
  const CupFixture *unplayed_final = cup_tournament_fixture(
      competition_frontend_cup_tournament(), 1u, 0u);
  assert(unplayed_final && !unplayed_final->home &&
         !unplayed_final->away && !unplayed_final->winner);
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
  const uint32_t english_field =
      exhibition_team_categories[0].team_count < 16u
          ? exhibition_team_categories[0].team_count : 16u;
  assert(competition_frontend_cup_team_count() == english_field);
  while (competition_frontend_focus() != 8u) press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_cup_draft()->team_count == english_field);
  assert(competition_frontend_cup_view_stage_count() == 3u);
  assert(competition_frontend_cup_view_page_count() == 4u);
  assert(competition_frontend_cup_view_count() == 7u);
  assert(competition_frontend_cup_view_first_fixture() == 0u);
  press(BUTTON_Y); /* button focus scrolls down within the same round */
  assert(competition_frontend_cup_view_round() == 0u);
  assert(competition_frontend_cup_view_first_fixture() == 2u);
  press(BUTTON_Y);
  assert(competition_frontend_cup_view_first_fixture() == 4u);
  press(BUTTON_Y);
  assert(competition_frontend_cup_view_first_fixture() == 6u);
  press(BUTTON_Y);
  assert(competition_frontend_cup_view_first_fixture() == 0u);
  press(BUTTON_R); /* shoulder moves horizontally to quarter-final */
  assert(competition_frontend_cup_view_round() == 1u);
  assert(competition_frontend_cup_view_first_fixture() == 0u);
  assert(competition_frontend_cup_view_page_count() == 2u);
  press(BUTTON_R); /* semi-final, final, champion share a stage */
  assert(competition_frontend_cup_view_round() == 2u);
  assert(competition_frontend_cup_view_page_count() == 1u);
  press(BUTTON_L);
  assert(competition_frontend_cup_view_round() == 1u);
  press(BUTTON_A);
  assert(competition_frontend_cup_view_round() == 0u);
  press(BUTTON_R); /* shoulders do not move the bracket while editing */
  assert(competition_frontend_cup_view_round() == 0u);
  press(BUTTON_X);
  assert(competition_draft_ready(competition_frontend_cup_draft()));
  assert(competition_frontend_cup_tournament()->history_count == 0u);
  assert(competition_frontend_cup_tournament()->bracket_size == 16u);
  for (uint32_t i = 0; i < 8u; i++) {
    const CupFixture *fixture = cup_tournament_fixture(
        competition_frontend_cup_tournament(), 0u, i);
    assert(fixture && fixture->home && fixture->away && !fixture->complete);
  }
  for (uint32_t round = 1u; round < 4u; round++) {
    const uint32_t count = cup_tournament_fixture_count(
        competition_frontend_cup_tournament(), round);
    for (uint32_t i = 0; i < count; i++) {
      const CupFixture *fixture = cup_tournament_fixture(
          competition_frontend_cup_tournament(), round, i);
      assert(fixture && !fixture->home && !fixture->away &&
             !fixture->winner && !fixture->complete);
    }
  }
  const uint32_t english_first = competition_frontend_cup_draft()->teams[0];
  const uint32_t english_second = competition_frontend_cup_draft()->teams[1];
  press(BUTTON_A);
  assert(competition_frontend_cup_team_picker_active());
  competition_frontend_cup_team_picker_result(english_second);
  assert(competition_frontend_cup_draft()->teams[0] == english_second);
  assert(competition_frontend_cup_draft()->teams[1] == english_first);
  assert(competition_frontend_cup_tournament()->history_count == 0u);
  puts("Cup frontend flow tests passed");
  return 0;
}
