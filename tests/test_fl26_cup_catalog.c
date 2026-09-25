#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "competition_frontend.h"
#include "fl26_cup_catalog_generated.h"

enum {
  BUTTON_A = 1u << 1,
  BUTTON_X = 1u << 3,
  BUTTON_DOWN = 1u << 11,
  BUTTON_RIGHT = 1u << 13,
};

uint32_t pes_controller_native_hid_connected_mask(void) { return 3u; }

static void press(uint32_t button) {
  competition_frontend_pad_event(0u, 0u);
  competition_frontend_pad_event(button, 0u);
  competition_frontend_pad_event(0u, 0u);
}

static int pool_contains(const Fl26CupCatalogEntry *cup, uint32_t team) {
  for (uint32_t i = 0; i < cup->pool_count; i++)
    if (cup->team_ids[i] == team) return 1;
  return 0;
}

static void open_settings(void) {
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_A); /* Cup landing */
  press(BUTTON_A); /* New Cup settings */
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_SETTINGS);
}

int main(void) {
  assert(FL26_CUP_CATALOG_COUNT == 7u);
  assert(FL26_CUP_CUSTOM_INDEX == 6u);
  for (uint32_t selected = 0; selected < FL26_CUP_CUSTOM_INDEX; selected++) {
    open_settings();
    for (uint32_t step = 0; step < selected; step++) press(BUTTON_RIGHT);
    const Fl26CupCatalogEntry *cup = &fl26_cup_catalog[selected];
    assert(competition_frontend_cup_catalog_index() == selected);
    assert(strcmp(competition_frontend_cup_name(), cup->name) == 0);
    assert(strcmp(competition_frontend_cup_logo_file(), cup->logo_file) == 0);
    assert(competition_frontend_cup_team_count() ==
           (selected == 5u ? 32u : 16u));
    press(BUTTON_DOWN); press(BUTTON_DOWN); /* Number of Teams */
    press(BUTTON_RIGHT);
    if (selected < 3u) {
      assert(competition_frontend_cup_team_count() == cup->bracket_limit);
      press(BUTTON_RIGHT);
      assert(competition_frontend_cup_team_count() == 8u);
      press(BUTTON_RIGHT);
      assert(competition_frontend_cup_team_count() == 16u);
      press(BUTTON_RIGHT);
      assert(competition_frontend_cup_team_count() == cup->bracket_limit);
    } else {
      assert(competition_frontend_cup_team_count() ==
             (selected == 5u ? 32u : 16u));
    }
    for (uint32_t i = 0; i < cup->pool_count; i++)
      assert(competition_frontend_cup_team_allowed(cup->team_ids[i]));
    while (competition_frontend_focus() != 5u) press(BUTTON_DOWN);
    press(BUTTON_A); /* Hub */
    assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
    press(BUTTON_A); /* Bracket editor */
    press(BUTTON_X); /* Only first-round slots receive teams */
    const CompetitionEntryDraft *draft = competition_frontend_cup_draft();
    const CupTournament *bracket = competition_frontend_cup_tournament();
    assert(draft && bracket && competition_draft_ready(draft));
    assert(draft->team_count == competition_frontend_cup_team_count());
    assert(bracket->history_count == 0u && bracket->champion == 0u);
    for (uint32_t slot = 0; slot < draft->team_count; slot++)
      assert(pool_contains(cup, draft->teams[slot]));
    press(BUTTON_A); /* League-scoped team selector */
    assert(competition_frontend_cup_team_picker_active());
    assert(competition_frontend_cup_picker_phase() == 2u);
    assert(competition_frontend_cup_picker_focused_team() == cup->team_ids[0]);
    assert(competition_frontend_cup_picker_visible_count() ==
        (cup->pool_count < 5u ? cup->pool_count : 5u));
    competition_frontend_cup_team_picker_result(cup->team_ids[0]);
    assert(!competition_frontend_cup_team_picker_active());
    competition_frontend_close();
    competition_frontend_finish_close();
  }
  open_settings();
  press(BUTTON_RIGHT); press(BUTTON_RIGHT); press(BUTTON_RIGHT);
  press(BUTTON_RIGHT); press(BUTTON_RIGHT); press(BUTTON_RIGHT);
  assert(competition_frontend_cup_catalog_index() == FL26_CUP_CUSTOM_INDEX);
  assert(strcmp(competition_frontend_cup_name(), "FOOTBALLNX CUP") == 0);
  assert(competition_frontend_cup_logo_file() == NULL);
  assert(competition_frontend_cup_team_count() == 8u);
  press(BUTTON_RIGHT);
  assert(competition_frontend_cup_catalog_index() == 0u);
  puts("FL26 Cup catalog frontend tests passed");
  return 0;
}
