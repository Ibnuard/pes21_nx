#ifndef PESNX_MANAGER_LEAGUE_PLAN_H
#define PESNX_MANAGER_LEAGUE_PLAN_H

#include <stdint.h>
#include "gameplan_preset.h"

/* Manager presets are account data. They never share native per-team or
 * Master League career files. All IDs here are canonical native IDs, with
 * their BaseId/fingerprint provenance bound by the complete catalog hash. */
#define MANAGER_LEAGUE_CURRENT_PLAN_SLOT GAMEPLAN_PRESET_SLOTS
typedef struct {
  uint64_t account;
  uint32_t team_id, player_count;
  char runtime_id[16], content_hash[64];
  uint32_t players[GAMEPLAN_PRESET_MAX_PLAYERS];
  uint8_t positions[GAMEPLAN_PRESET_MAX_PLAYERS]; /* Native natural role; GK=0. */
} ManagerLeaguePlanScope;

int manager_league_plan_scope_valid(const ManagerLeaguePlanScope *scope);
int manager_league_plan_compatible(const ManagerLeaguePlanScope *scope,
                                   const GameplanPreset *plan);
/* Slots 0..2 are explicitly named saves; slot 3 is the account/team default.
 * Reads leave out unchanged on any failure. Membership/catalog changes refuse
 * the complete preset instead of partially importing stale identities. */
int manager_league_plan_read(const ManagerLeaguePlanScope *scope, uint32_t slot,
                              GameplanPreset *out);
int manager_league_plan_write(const ManagerLeaguePlanScope *scope, uint32_t slot,
                               const GameplanPreset *plan);

#endif
