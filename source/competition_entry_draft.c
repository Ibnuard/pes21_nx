#include "competition_entry_draft.h"

#include <string.h>

static uint32_t draft_roll(CompetitionEntryDraft *draft) {
  uint32_t x = draft->seed ? draft->seed : 1u;
  x ^= x << 13;
  x ^= x >> 17;
  x ^= x << 5;
  draft->seed = x;
  return x;
}

int competition_draft_init(CompetitionEntryDraft *draft, uint32_t team_count,
                           uint32_t player_count, uint32_t seed) {
  if (!draft || team_count < 2u ||
      team_count > COMPETITION_DRAFT_MAX_TEAMS || !player_count ||
      player_count > COMPETITION_DRAFT_MAX_PLAYERS ||
      player_count > team_count)
    return 0;
  memset(draft, 0, sizeof(*draft));
  draft->team_count = team_count;
  draft->player_count = player_count;
  draft->seed = seed ? seed : 1u;
  for (uint32_t i = 0; i < player_count; i++)
    draft->owners[i] = (uint8_t)(i + 1u);
  return 1;
}

int competition_draft_assign(CompetitionEntryDraft *draft, uint32_t slot,
                             uint32_t team_id) {
  if (!draft || slot >= draft->team_count || !team_id) return 0;
  for (uint32_t i = 0; i < draft->team_count; i++)
    if (i != slot && draft->teams[i] == team_id) return 0;
  draft->teams[slot] = team_id;
  return 1;
}

int competition_draft_assign_or_swap(CompetitionEntryDraft *draft,
                                     uint32_t slot, uint32_t team_id) {
  if (!draft || slot >= draft->team_count || !team_id) return 0;
  for (uint32_t other = 0; other < draft->team_count; other++) {
    if (other == slot || draft->teams[other] != team_id) continue;
    draft->teams[other] = draft->teams[slot];
    draft->teams[slot] = team_id;
    return 1;
  }
  draft->teams[slot] = team_id;
  return 1;
}

int competition_draft_swap_slots(CompetitionEntryDraft *draft,
                                 uint32_t first, uint32_t second) {
  if (!draft || first >= draft->team_count ||
      second >= draft->team_count) return 0;
  const uint32_t team = draft->teams[first];
  const uint8_t owner = draft->owners[first];
  draft->teams[first] = draft->teams[second];
  draft->owners[first] = draft->owners[second];
  draft->teams[second] = team;
  draft->owners[second] = owner;
  return 1;
}

uint32_t competition_draft_assigned_count(const CompetitionEntryDraft *draft) {
  if (!draft) return 0u;
  uint32_t count = 0;
  for (uint32_t i = 0; i < draft->team_count; i++)
    count += draft->teams[i] != 0u;
  return count;
}

int competition_draft_ready(const CompetitionEntryDraft *draft) {
  if (!draft || !draft->team_count ||
      competition_draft_assigned_count(draft) != draft->team_count)
    return 0;
  for (uint32_t i = 0; i < draft->team_count; i++)
    for (uint32_t j = i + 1u; j < draft->team_count; j++)
      if (draft->teams[i] == draft->teams[j]) return 0;
  return 1;
}

int competition_draft_random_fill(CompetitionEntryDraft *draft,
                                   const uint32_t *pool, uint32_t pool_count) {
  if (!draft || !pool || !pool_count ||
      pool_count > COMPETITION_DRAFT_MAX_POOL)
    return 0;
  uint32_t candidates[COMPETITION_DRAFT_MAX_POOL];
  uint32_t available = 0;
  for (uint32_t i = 0; i < pool_count; i++) {
    const uint32_t team = pool[i];
    if (!team) continue;
    uint32_t duplicate = 0;
    for (uint32_t j = 0; j < draft->team_count; j++)
      if (draft->teams[j] == team) duplicate = 1;
    for (uint32_t j = 0; j < available; j++)
      if (candidates[j] == team) duplicate = 1;
    if (!duplicate) candidates[available++] = team;
  }
  const uint32_t missing = draft->team_count -
                           competition_draft_assigned_count(draft);
  if (available < missing) return 0;
  for (uint32_t i = available; i > 1u; i--) {
    const uint32_t j = draft_roll(draft) % i;
    const uint32_t tmp = candidates[i - 1u];
    candidates[i - 1u] = candidates[j];
    candidates[j] = tmp;
  }
  uint32_t next = 0;
  for (uint32_t i = 0; i < draft->team_count; i++)
    if (!draft->teams[i]) draft->teams[i] = candidates[next++];
  return 1;
}

int competition_draft_shuffle(CompetitionEntryDraft *draft) {
  if (!competition_draft_ready(draft)) return 0;
  for (uint32_t i = draft->team_count; i > 1u; i--) {
    const uint32_t j = draft_roll(draft) % i;
    const uint32_t team = draft->teams[i - 1u];
    const uint8_t owner = draft->owners[i - 1u];
    draft->teams[i - 1u] = draft->teams[j];
    draft->owners[i - 1u] = draft->owners[j];
    draft->teams[j] = team;
    draft->owners[j] = owner;
  }
  return 1;
}

uint32_t competition_draft_fixture_slot(const CompetitionEntryDraft *draft,
                                         uint32_t fixture, uint32_t side) {
  if (!draft || !draft->team_count || side > 1u) return UINT32_MAX;
  uint32_t opening = 1u;
  while (opening * 2u < draft->team_count) opening *= 2u;
  const uint32_t pairs = draft->team_count - opening;
  if (fixture >= opening || (side && fixture >= pairs)) return UINT32_MAX;
  return fixture + (fixture < pairs ? fixture : pairs) + side;
}

int competition_draft_slot_fixture(const CompetitionEntryDraft *draft,
                                    uint32_t slot, uint32_t *fixture,
                                    uint32_t *side) {
  if (!draft || slot >= draft->team_count) return 0;
  uint32_t opening = 1u;
  while (opening * 2u < draft->team_count) opening *= 2u;
  for (uint32_t i = 0; i < opening; i++) {
    for (uint32_t s = 0; s < 2u; s++) {
      if (competition_draft_fixture_slot(draft, i, s) != slot) continue;
      if (fixture) *fixture = i;
      if (side) *side = s;
      return 1;
    }
  }
  return 0;
}
