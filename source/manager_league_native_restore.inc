/* Included immediately before prematch_gameplan_load_preset, after the shared
 * restore function. Manager restores keep the complete native squad on failure. */
static int manager_league_native_plan_seed(void) {
  if (!manager_dummy_plan_editor()) return 1;
  void *squad = prematch_gameplan_resolve_squad(0u);
  ManagerLeaguePlanScope scope;
  if (!squad || !manager_dummy_plan_scope(&scope) ||
      !manager_league_office_lineup_valid(0u, squad) ||
      !exhibition_common_get_crypt_key || !match_squad_data_get_formation ||
      !match_formation_set_position || !match_formation_set_role ||
      !match_squad_data_set_formation || !match_formation_copy_assign ||
      !match_squad_data_set_player_role_position || !match_squad_data_set_tactics) return 0;
  uint32_t members[11] = {0}, keeper = UINT32_MAX;
  const uint32_t crypt = exhibition_common_get_crypt_key();
  for (uint32_t i = 0u; i < scope.player_count; i++) {
    const void *key = exhibition_squad_data_get_player_by_index(squad, &i);
    const uint32_t order = match_squad_data_get_order_no(squad, key);
    if (order >= 11u) continue;
    members[order] = match_squad_data_get_member_id(squad, key);
    uint32_t native = 0u;
    memcpy(&native, (const unsigned char *)key + 4u, sizeof(native));
    native ^= crypt;
    uint32_t at = 0u;
    while (at < scope.player_count && scope.players[at] != native) at++;
    if (at == scope.player_count) return 0;
    if (scope.positions[at] == 0u) keeper = order;
  }
  if (keeper >= 11u) return 0;
  const PrematchFormationPreset *shape = &prematch_formation_presets[0];
  for (uint32_t tactic = 0u; tactic < 2u; tactic++) {
    TmpdbFormationValue formation = match_squad_data_get_formation(squad, tactic);
    uint32_t next = 1u;
    for (uint32_t order = 0u; order < 11u; order++) {
      const uint32_t slot = order == keeper ? 0u : next++;
      const uint8_t position[2] = {shape->y[slot], shape->x[slot]};
      match_formation_set_position(&formation, order, position, 0u);
      match_formation_set_role(&formation, order, shape->role[slot], 0u);
    }
    prematch_gameplan_store_formation(squad, tactic, &formation);
    next = 1u;
    for (uint32_t order = 0u; order < 11u; order++) {
      const uint32_t slot = order == keeper ? 0u : next++;
      match_squad_data_set_player_role_position(squad, shape->role[slot],
          members[order], &tactic);
    }
  }
  match_squad_data_set_tactics(squad, 0u);
  exhibition_gameplan_sides[0].default_formation_valid = 0u;
  return 1;
}

static int manager_league_native_plan_rekey_settings(uint32_t side,
    const GameplanPreset *saved, TmpdbMatchPlanSettingsValue *settings) {
  if (!manager_dummy_plan_editor()) return 1;
  if (side != 0u || !settings || !manager_league_native_plan_members_valid(saved) ||
      !match_squad_data_get_member_id) return 0;
  const PrematchGameplanSide *state = &exhibition_gameplan_sides[side];
  if (!state->squad_data || saved->player_count != state->player_count) return 0;
  uint8_t remap[18];
  uint32_t seen = 0u;
  memset(remap, 0xff, sizeof(remap));
  for (uint32_t i = 0u; i < saved->player_count; i++) {
    const uint32_t old_member = saved->players[i].reserved[0];
    if (old_member == 0xffu) continue;
    const uint32_t current = match_squad_data_get_member_id(state->squad_data,
        saved->players[i].player_id);
    if (current >= 18u || (seen & (1u << current))) return 0;
    seen |= 1u << current;
    remap[old_member] = (uint8_t)current;
  }
  if (seen != 0x3ffffu) return 0;
  /* These are the fields exposed by prematch_gameplan_position_member.
   * Byte 45 is not used by that editor API and stays native-owned. */
  static const uint8_t fields[] = {49u,40u,41u,42u,43u,44u,46u,47u,48u};
  for (uint32_t i = 0u; i < sizeof(fields); i++) {
    const uint32_t member = settings->bytes[fields[i]];
    if (member == 0xffu) continue;
    if (member >= 18u || remap[member] == 0xffu) return 0;
    settings->bytes[fields[i]] = remap[member];
  }
  return 1;
}

static int manager_league_native_plan_restore(uint32_t side,
                                              const GameplanPreset *saved) {
  if (side != 0u || !manager_dummy_plan_editor() || !saved || live_gameplan_window ||
      !exhibition_common_get_crypt_key || !match_squad_data_copy_construct ||
      !match_squad_data_copy_assign || !match_squad_data_destruct ||
      !gameplan_preset_valid(saved)) return 0;
  PrematchGameplanSide *state = &exhibition_gameplan_sides[side];
  ManagerLeaguePlanScope scope;
  if (!state->squad_data || !manager_dummy_plan_scope(&scope) ||
      !manager_league_plan_scope_valid(&scope) ||
      saved->team_id != scope.team_id || saved->player_count != state->player_count) return 0;
  const uint32_t crypt = exhibition_common_get_crypt_key();
  GameplanPreset canonical = *saved;
  const void *incoming_keeper = NULL, *outgoing_keeper = NULL;
  for (uint32_t i = 0u; i < canonical.player_count; i++) {
    uint32_t encoded = 0u;
    memcpy(&encoded, saved->players[i].player_id + 4u, sizeof(encoded));
    const uint32_t native = encoded ^ crypt;
    memset(canonical.players[i].player_id, 0, sizeof(canonical.players[i].player_id));
    memcpy(canonical.players[i].player_id, &native, sizeof(native));
    uint32_t at = 0u;
    while (at < scope.player_count && scope.players[at] != native) at++;
    if (at == scope.player_count) return 0;
    int found = 0;
    for (uint32_t j = 0u; j < state->player_count; j++) {
      const PrematchGameplanPlayer *current = &state->players[j];
      if (memcmp(saved->players[i].player_id, current->player_id, 16u)) continue;
      found = 1;
      if (scope.positions[at] == 0u) {
        if (saved->players[i].order_no < 11u) incoming_keeper = current->player_id;
        if (current->order_no < 11u) outgoing_keeper = current->player_id;
      }
      break;
    }
    if (!found) return 0;
  }
  if (!incoming_keeper || !outgoing_keeper ||
      !manager_league_native_plan_shape_valid(&canonical)) return 0;
  _Alignas(8) unsigned char before[EXHIBITION_PRE_STRATEGY_SQUAD_SNAPSHOT_BYTES] = {0};
  match_squad_data_copy_construct(before, state->squad_data);
  /* Exchange keepers first. The ordinary order loop may otherwise briefly
   * register two keepers while moving a different keeper to another slot. */
  int restored = 1;
  if (memcmp(incoming_keeper, outgoing_keeper, 16u)) {
    restored = prematch_gameplan_replace_player(side, state->squad_data,
        outgoing_keeper, incoming_keeper);
    if (restored) prematch_gameplan_refresh_side(side);
  }
  if (restored) restored = prematch_gameplan_restore(side, saved);
  if (!restored) {
    match_squad_data_copy_assign(state->squad_data, before);
    prematch_gameplan_refresh_side(side);
  }
  match_squad_data_destruct(before);
  return restored;
}
