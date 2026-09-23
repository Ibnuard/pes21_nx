#ifndef PES21_COMPETITION_ENTRY_DRAFT_H
#define PES21_COMPETITION_ENTRY_DRAFT_H

#include <stdint.h>

/* Shared by Cup now and by League's future participant-selection screen. */
#define COMPETITION_DRAFT_MAX_TEAMS 32u
#define COMPETITION_DRAFT_MAX_PLAYERS 8u
#define COMPETITION_DRAFT_MAX_POOL 512u

typedef struct {
  uint32_t team_count;
  uint32_t player_count;
  uint32_t seed;
  uint32_t teams[COMPETITION_DRAFT_MAX_TEAMS];
  uint8_t owners[COMPETITION_DRAFT_MAX_TEAMS];
} CompetitionEntryDraft;

int competition_draft_init(CompetitionEntryDraft *draft, uint32_t team_count,
                           uint32_t player_count, uint32_t seed);
int competition_draft_assign(CompetitionEntryDraft *draft, uint32_t slot,
                             uint32_t team_id);
/* Selecting a team already in another slot exchanges the two teams while
 * preserving the fixed P1/P2/COM ownership labels of those slots. */
int competition_draft_assign_or_swap(CompetitionEntryDraft *draft,
                                     uint32_t slot, uint32_t team_id);
/* Bracket-order swap moves team and owner together. */
int competition_draft_swap_slots(CompetitionEntryDraft *draft,
                                 uint32_t first, uint32_t second);
int competition_draft_ready(const CompetitionEntryDraft *draft);
uint32_t competition_draft_assigned_count(const CompetitionEntryDraft *draft);
int competition_draft_random_fill(CompetitionEntryDraft *draft,
                                   const uint32_t *pool, uint32_t pool_count);
int competition_draft_shuffle(CompetitionEntryDraft *draft);
uint32_t competition_draft_fixture_slot(const CompetitionEntryDraft *draft,
                                         uint32_t fixture, uint32_t side);
int competition_draft_slot_fixture(const CompetitionEntryDraft *draft,
                                    uint32_t slot, uint32_t *fixture,
                                    uint32_t *side);

#endif
