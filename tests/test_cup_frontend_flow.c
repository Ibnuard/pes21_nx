#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

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

#include "competition_confirmation_checks.inc"

static void new_custom_cup(uint32_t teams, uint32_t players) {
  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_A);press(BUTTON_A);press(BUTTON_LEFT);
  press(BUTTON_DOWN);press(BUTTON_DOWN);
  for (uint32_t i = teams; i < 8u; i++) press(BUTTON_LEFT);
  for (uint32_t i = 8u; i < teams; i++) press(BUTTON_RIGHT);
  press(BUTTON_UP);
  for (uint32_t i = 1u; i < players; i++) press(BUTTON_RIGHT);
  while (competition_frontend_focus() != 5u) press(BUTTON_DOWN);
  press(BUTTON_A);
}

static void check_opening_owner_rule(void) {
  for (uint32_t teams = 2u; teams <= 32u; teams++) {
    uint32_t opening = 1u;
    while (opening * 2u < teams) opening *= 2u;
    for (uint32_t players = 1u; players <= teams && players <= 8u; players++) {
      new_custom_cup(teams, players);
      if (players > 2u * (teams - opening)) {
        assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_SETTINGS);
        assert(strstr(competition_frontend_status(), "NO PLAYER BYES"));
        continue;
      }
      assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
      const CompetitionEntryDraft *draft = competition_frontend_cup_draft();
      for (uint32_t i = 0; i < opening; i++) {
        const uint32_t h = competition_draft_fixture_slot(draft, i, 0u);
        const uint32_t a = competition_draft_fixture_slot(draft, i, 1u);
        if (a == UINT32_MAX) assert(!draft->owners[h]);
      }
    }
  }
  /* One human playing is not enough: P2 must not be left on a bye either. */
  new_custom_cup(3u, 2u);
  press(BUTTON_A);press(BUTTON_X);
  const CompetitionEntryDraft before = *competition_frontend_cup_draft();
  const CupTournament bracket = *competition_frontend_cup_tournament();
  press(BUTTON_DOWN); /* P2 */
  press(BUTTON_Y);press(BUTTON_DOWN);press(BUTTON_A); /* -> bye */
  assert(competition_frontend_cup_opening_rule_popup());
  assert(!memcmp(&before, competition_frontend_cup_draft(), sizeof(before)));
  assert(!memcmp(&bracket, competition_frontend_cup_tournament(), sizeof(bracket)));
  press(BUTTON_B);
  assert(!competition_frontend_cup_opening_rule_popup());
  assert(competition_frontend_cup_bracket_swap_source() == 1u);
  competition_frontend_close();
  competition_frontend_finish_close();
}

int main(void) {
  check_opening_owner_rule();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u); /* consume opening A tick */
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_LANDING);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_SETTINGS);
  press(BUTTON_LEFT); /* wrap from FA Cup to FootballNX Cup */
  for (uint32_t row = 0; row < 5u; row++) press(BUTTON_DOWN);
  assert(competition_frontend_focus() == 5u);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
  assert(competition_frontend_cup_draft());
  assert(competition_frontend_item_count() == 6u);
  assert(strcmp(competition_frontend_item_label(0u), "TEAMS") == 0);
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
  assert(strcmp(competition_frontend_status(), "") == 0);
  assert(competition_draft_ready(competition_frontend_cup_draft()));
  assert(competition_frontend_cup_draft()->teams[0] == manual_team);
  assert(competition_frontend_cup_tournament()->history_count == 0u);
  const uint32_t other_team = competition_frontend_cup_draft()->teams[1];
  press(BUTTON_Y); /* mark source slot */
  assert(competition_frontend_cup_bracket_swap_source() == 0u);
  press(BUTTON_DOWN);
  press(BUTTON_A); /* place source: exchange complete team+owner entries */
  assert(competition_frontend_cup_bracket_swap_source() == UINT32_MAX);
  assert(competition_frontend_cup_draft()->teams[1] == manual_team);
  assert(competition_frontend_cup_draft()->owners[1] == 1u);
  assert(competition_frontend_cup_tournament()->history_count == 0u);
  press(BUTTON_Y);
  press(BUTTON_UP);
  press(BUTTON_A); /* restore source for the save test */
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
  press(BUTTON_B); /* return to tournament home */
  assert(!competition_frontend_cup_bracket_editing());
  assert(competition_frontend_item_enabled(1u));

  CupTournament before_news=*competition_frontend_cup_tournament();
  for(uint64_t ms=100u;ms<=6100u;ms+=100u)competition_frontend_tick(ms);
  assert(competition_frontend_cup_news_index()==1u);
  assert(competition_frontend_cup_news_progress()==0.f);
  press(BUTTON_L);assert(competition_frontend_cup_news_index()==0u);
  press(BUTTON_L);assert(competition_frontend_cup_news_index()==3u);
  competition_frontend_tick(1000000u); /* a suspend gap does not skip the feed */
  assert(competition_frontend_cup_news_index()==3u);
  assert(!memcmp(&before_news,competition_frontend_cup_tournament(),sizeof(before_news)));
  press(BUTTON_RIGHT);press(BUTTON_A);
  assert(competition_frontend_cup_page()==CUP_PAGE_BRACKET);
  for(uint64_t ms=1000100u;ms<=1007000u;ms+=100u)competition_frontend_tick(ms);
  assert(competition_frontend_cup_news_index()==3u); /* pauses off Home */
  press(BUTTON_R);press(BUTTON_Y);press(BUTTON_B);
  assert(competition_frontend_cup_page()==CUP_PAGE_HOME);
  assert(competition_frontend_focus()==4u);
  assert(!memcmp(&before_news,competition_frontend_cup_tournament(),sizeof(before_news)));
  press(BUTTON_LEFT);
  press(BUTTON_UP); /* Teams -> news -> next match -> Settings */
  press(BUTTON_RIGHT);
  assert(competition_frontend_focus() == 1u);
  press(BUTTON_DOWN);
  assert(competition_frontend_focus() == 2u);
  press(BUTTON_A); /* General Setting reuses the hub settings viewport. */
  assert(competition_frontend_cup_general_open());
  assert(competition_frontend_cup_general_count() == 8u);
  for (uint32_t row = 0; row < competition_frontend_cup_general_count(); row++)
    assert(strcmp(competition_frontend_cup_general_label(row), "PENALTIES") != 0);
  press(BUTTON_DOWN);
  assert(competition_frontend_cup_general_focus() == 1u);
  press(BUTTON_B);
  assert(!competition_frontend_cup_general_open());
  press(BUTTON_RIGHT);
  assert(competition_frontend_focus() == 3u);
  press(BUTTON_A); /* Save */
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_SLOTS);
  assert(strcmp(competition_frontend_slot_competition(0u),
                "NO SAVE DATA") == 0);
  assert(strcmp(competition_frontend_slot_progress(0u), "") == 0);
  press(BUTTON_A); /* Slot 1 */
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
  assert(competition_frontend_cup_draft()->teams[0] == manual_team);

  check_save_confirmations(1);
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

  /* A three-team Cup shows semis -> final and locks editing after kickoff.
   * Completed tournaments retain read-only results and bracket navigation. */
  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_A);
  press(BUTTON_A);
  press(BUTTON_LEFT); /* FootballNX custom Cup */
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  for (uint32_t i = 0; i < 5u; i++) press(BUTTON_LEFT);
  assert(competition_frontend_cup_team_count() == 3u);
  while (competition_frontend_focus() != 5u) press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_cup_view_count() == 2u);
  press(BUTTON_A);
  press(BUTTON_X);
  const CupFixture *unplayed_final = cup_tournament_fixture(
      competition_frontend_cup_tournament(), 1u, 0u);
  assert(unplayed_final && !unplayed_final->home &&
         !unplayed_final->away && !unplayed_final->winner);
  press(BUTTON_Y); /* P1 cannot be moved to the sole opening bye. */
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_cup_opening_rule_popup());
  assert(competition_frontend_cup_draft()->owners[0] == 1u);
  assert(competition_frontend_cup_draft()->owners[2] == 0u);
  assert(competition_frontend_cup_tournament()->history_count == 0u);
  press(BUTTON_A); /* dismiss modal, without opening the team picker */
  assert(!competition_frontend_cup_opening_rule_popup());
  assert(!competition_frontend_cup_team_picker_active());
  press(BUTTON_UP);
  press(BUTTON_UP);
  press(BUTTON_B); /* cancel the pending swap */
  assert(competition_frontend_cup_bracket_editing());
  assert(competition_frontend_cup_bracket_swap_source() == UINT32_MAX);
  press(BUTTON_B); /* leave Teams */
  press(BUTTON_UP);press(BUTTON_RIGHT);
  for (uint32_t match = 0; match < 2u; match++) {
    press(BUTTON_A);
    assert(competition_frontend_take_action() ==
           COMPETITION_ACTION_CUP_FIXTURE);
    uint32_t home = 0, away = 0;
    assert(competition_frontend_cup_match_teams(&home, &away));
    assert(home && away);
    competition_frontend_cup_handoff_result(1);
    competition_frontend_cup_match_result(1u, 0u);
    assert(!competition_frontend_cup_take_champion_presentation());
    competition_frontend_cup_restore_after_match();
    if (!competition_frontend_cup_tournament()->champion)
      assert(!competition_frontend_item_enabled(0u));
    if (competition_frontend_cup_tournament()->champion) {
      assert(competition_frontend_cup_take_champion_presentation());
      assert(!competition_frontend_cup_take_champion_presentation());
      break;
    }
    assert(!competition_frontend_cup_take_champion_presentation());
  }
  assert(competition_frontend_cup_tournament()->champion);
  assert(competition_frontend_cup_view_round() == 1u);
  assert(competition_frontend_focus() == 1u);
  assert(competition_frontend_item_count() == 6u);
  assert(!competition_frontend_item_enabled(0u));
  assert(competition_frontend_item_enabled(1u));
  assert(strcmp(competition_frontend_item_label(1u), "TOP MENU") == 0);
  /* Completed cups still expose results and bracket before returning home. */
  press(BUTTON_LEFT);press(BUTTON_A);
  assert(competition_frontend_cup_page()==CUP_PAGE_MATCHES);
  press(BUTTON_B);press(BUTTON_RIGHT);press(BUTTON_A);
  assert(competition_frontend_confirmation_active() && competition_frontend_confirmation_focus()==1u);
  press(BUTTON_LEFT);press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_NONE);

  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_A);
  press(BUTTON_A);
  /* FA Cup is the first predefined choice and uses its eligible pool. */
  const uint32_t english_field =
      exhibition_team_categories[0].team_count < 16u
          ? exhibition_team_categories[0].team_count : 16u;
  assert(competition_frontend_cup_team_count() == english_field);
  while (competition_frontend_focus() != 5u) press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_cup_draft()->team_count == english_field);
  assert(competition_frontend_cup_view_stage_count() == 4u);
  assert(competition_frontend_cup_view_page_count() == 4u);
  assert(competition_frontend_cup_view_count() == 8u);
  assert(competition_frontend_cup_view_first_fixture() == 0u);
  press(BUTTON_RIGHT);press(BUTTON_A); /* dedicated bracket page */
  assert(competition_frontend_cup_page()==CUP_PAGE_BRACKET);
  press(BUTTON_Y); /* browse the next two fixtures */
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
  press(BUTTON_R); /* semi-final and final share a match stage */
  assert(competition_frontend_cup_view_round() == 2u);
  assert(competition_frontend_cup_view_page_count() == 1u);
  press(BUTTON_R); /* Final and third place have their own page. */
  assert(competition_frontend_cup_view_round() == 3u);
  assert(competition_frontend_cup_view_page_count() == 1u);
  press(BUTTON_L);
  assert(competition_frontend_cup_view_round() == 2u);
  press(BUTTON_L);
  assert(competition_frontend_cup_view_round() == 1u);
  press(BUTTON_B);press(BUTTON_LEFT);press(BUTTON_A);
  assert(competition_frontend_cup_bracket_editing());
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

  /* A fully player-owned Cup hides COM Level in the reused General Setting. */
  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_A);
  press(BUTTON_A);
  press(BUTTON_LEFT); /* FootballNX custom Cup */
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  for (uint32_t i = 0; i < 4u; i++) press(BUTTON_LEFT); /* 8 -> 4 teams */
  press(BUTTON_UP);
  press(BUTTON_RIGHT);
  press(BUTTON_RIGHT);
  press(BUTTON_RIGHT); /* 4 logical player owners */
  assert(competition_frontend_cup_player_count() == 4u);
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  assert(competition_frontend_focus() == 3u);
  press(BUTTON_A);
  assert(competition_frontend_cup_home_away());
  press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_cup_third_place());
  press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
  assert(competition_frontend_cup_tournament()->home_away);
  assert(competition_frontend_cup_tournament()->third_place_enabled);
  press(BUTTON_RIGHT);press(BUTTON_RIGHT);
  assert(competition_frontend_focus() == 2u); /* dedicated Settings card */
  press(BUTTON_A);
  assert(competition_frontend_cup_general_count() == 7u);
  assert(competition_frontend_cup_general_open());
  assert(competition_frontend_cup_general_label(0u)[0] == 'M');
  for (uint32_t row = 0; row < competition_frontend_cup_general_count(); row++)
    assert(strcmp(competition_frontend_cup_general_label(row), "PENALTIES") != 0);
  press(BUTTON_B);
  press(BUTTON_LEFT);press(BUTTON_LEFT); /* return to Teams. */
  assert(competition_frontend_focus() == 0u);
  press(BUTTON_A);
  press(BUTTON_X);
  assert(competition_draft_ready(competition_frontend_cup_draft()));
  press(BUTTON_B);
  press(BUTTON_RIGHT);
  press(BUTTON_RIGHT);
  press(BUTTON_RIGHT);
  assert(competition_frontend_focus() == 3u);
  press(BUTTON_A); /* persist new Cup and General rules in version 3 */
  press(BUTTON_A);
  assert(competition_frontend_confirmation_active());
  press(BUTTON_LEFT);press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_A);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
  assert(competition_frontend_cup_home_away());
  assert(competition_frontend_cup_third_place());
  assert(competition_frontend_cup_tournament()->third_place_enabled);

  /* Two-team custom Cup has one Final page; save/continue accepts one round. */
  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_A);
  press(BUTTON_A);
  press(BUTTON_LEFT); /* FootballNX custom Cup */
  press(BUTTON_DOWN);
  press(BUTTON_DOWN);
  for (uint32_t i = 0; i < 6u; i++) press(BUTTON_LEFT);
  assert(competition_frontend_cup_team_count() == 2u);
  press(BUTTON_LEFT);
  assert(competition_frontend_cup_team_count() == 2u);
  while (competition_frontend_focus() != 5u) press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_cup_view_stage_count() == 1u);
  assert(competition_frontend_cup_view_count() == 1u);
  assert(competition_frontend_cup_view_round() == 0u);
  assert(competition_frontend_cup_tournament()->round_count == 1u);
  assert(competition_frontend_cup_tournament()->bracket_size == 2u);
  press(BUTTON_A); /* edit Final entrants */
  press(BUTTON_X);
  assert(competition_draft_ready(competition_frontend_cup_draft()));
  const CupFixture *quick_final = cup_tournament_fixture(
      competition_frontend_cup_tournament(), 0u, 0u);
  assert(quick_final && quick_final->home && quick_final->away);
  assert(!quick_final->complete && !quick_final->winner);
  press(BUTTON_B);
  press(BUTTON_RIGHT);
  press(BUTTON_RIGHT);
  press(BUTTON_RIGHT); /* save two-team bracket */
  assert(competition_frontend_focus() == 3u);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_SLOTS);
  assert(strcmp(competition_frontend_slot_competition(1u),
                "NO SAVE DATA") == 0);
  assert(strcmp(competition_frontend_slot_progress(1u), "") == 0);
  press(BUTTON_A);
  assert(competition_frontend_confirmation_active());
  press(BUTTON_LEFT);press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
  competition_frontend_close();
  competition_frontend_finish_close();
  competition_frontend_open_modes();
  competition_frontend_pad_event(0u, 0u);
  press(BUTTON_A);
  press(BUTTON_DOWN);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_SLOTS);
  assert(strcmp(competition_frontend_slot_competition(0u),
                "FOOTBALLNX CUP") == 0);
  assert(strcmp(competition_frontend_slot_progress(0u), "FINAL") == 0);
  press(BUTTON_A);
  assert(competition_frontend_state() == COMPETITION_FRONTEND_CUP_BRACKET);
  assert(competition_frontend_cup_tournament()->round_count == 1u);
  assert(competition_frontend_cup_team_count() == 2u);
  press(BUTTON_UP);press(BUTTON_RIGHT);
  assert(competition_frontend_focus() == 1u);
  press(BUTTON_A);
  assert(competition_frontend_take_action() ==
         COMPETITION_ACTION_CUP_FIXTURE);
  competition_frontend_cup_handoff_result(1);
  competition_frontend_cup_match_result(2u, 0u);
  /* Custom Cup wins even when both clubs belong to the Premier League. */
  assert(competition_frontend_scoreboard(101u,107u)==1000u);
  competition_frontend_cup_restore_after_match();
  assert(competition_frontend_cup_tournament()->champion);
  assert(competition_frontend_cup_view_round() == 0u);
  assert(competition_frontend_focus() == 1u);
  assert(competition_frontend_cup_take_champion_presentation());
  puts("Cup frontend flow tests passed");
  return 0;
}
