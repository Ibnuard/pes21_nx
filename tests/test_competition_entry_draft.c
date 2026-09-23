#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "competition_entry_draft.h"

static void mapping(uint32_t teams) {
  CompetitionEntryDraft draft;
  assert(competition_draft_init(&draft, teams, 2u, 0x26u));
  uint32_t seen[COMPETITION_DRAFT_MAX_TEAMS] = {0};
  uint32_t opening = 2u;
  while (opening * 2u < teams) opening *= 2u;
  for (uint32_t fixture = 0; fixture < opening; fixture++) {
    for (uint32_t side = 0; side < 2u; side++) {
      const uint32_t slot = competition_draft_fixture_slot(
          &draft, fixture, side);
      if (slot == UINT32_MAX) continue;
      assert(slot < teams && !seen[slot]++);
      uint32_t actual_fixture = UINT32_MAX, actual_side = UINT32_MAX;
      assert(competition_draft_slot_fixture(&draft, slot, &actual_fixture,
                                             &actual_side));
      assert(actual_fixture == fixture && actual_side == side);
    }
  }
  for (uint32_t slot = 0; slot < teams; slot++) assert(seen[slot] == 1u);
}

static void fill_and_shuffle(void) {
  CompetitionEntryDraft draft;
  uint32_t pool[20];
  for (uint32_t i = 0; i < 20u; i++) pool[i] = 100u + i;
  assert(competition_draft_init(&draft, 8u, 3u, 0x123456u));
  assert(competition_draft_assign(&draft, 0u, 100u));
  assert(competition_draft_assign(&draft, 1u, 101u));
  assert(!competition_draft_assign(&draft, 2u, 100u));
  assert(competition_draft_assign_or_swap(&draft, 0u, 101u));
  assert(draft.teams[0] == 101u && draft.teams[1] == 100u);
  assert(draft.owners[0] == 1u && draft.owners[1] == 2u);
  assert(competition_draft_assign_or_swap(&draft, 0u, 100u));
  assert(draft.teams[0] == 100u && draft.teams[1] == 101u);
  assert(competition_draft_swap_slots(&draft, 0u, 2u));
  assert(draft.owners[0] == 3u && draft.owners[2] == 1u);
  assert(draft.teams[2] == 100u && draft.teams[0] == 0u);
  assert(competition_draft_swap_slots(&draft, 0u, 2u));
  assert(!competition_draft_ready(&draft));
  assert(!competition_draft_shuffle(&draft));
  assert(competition_draft_random_fill(&draft, pool, 20u));
  assert(competition_draft_ready(&draft));
  assert(draft.teams[0] == 100u && draft.teams[1] == 101u);
  uint32_t owned[3] = {draft.teams[0], draft.teams[1], draft.teams[2]};
  assert(competition_draft_shuffle(&draft));
  for (uint32_t owner = 1u; owner <= 3u; owner++) {
    uint32_t found = 0;
    for (uint32_t slot = 0; slot < draft.team_count; slot++)
      if (draft.owners[slot] == owner) {
        assert(draft.teams[slot] == owned[owner - 1u]);
        found++;
      }
    assert(found == 1u);
  }
}

int main(void) {
  mapping(3u);
  mapping(4u);
  mapping(8u);
  mapping(20u);
  mapping(32u);
  fill_and_shuffle();
  puts("competition entry draft tests passed");
  return 0;
}
