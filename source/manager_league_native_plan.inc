/* Included by ue4_hooks.c after its native function forward declarations.
 * This bridge opens the SAME native squad bootstrap and custom Game Plan
 * used by the Master League office; it owns no alternative strategy page. */
static uint32_t manager_league_plan_restore_pending;
static int manager_league_native_plan_rekey_settings(uint32_t side,
    const GameplanPreset *saved, TmpdbMatchPlanSettingsValue *settings);

static int native_office_plan_editor(void) {
  return ml_frontend_plan_editor() || manager_dummy_plan_editor();
}

enum { MANAGER_PLAN_MEMBER_MARKER = 0x4du, MANAGER_PLAN_MEMBER_VERSION = 1u };

/* The ordinary preset format leaves these bytes unused. Manager plans bind
 * every registered native MemberId to its canonical player identity, so
 * captain/taker/attacker assignments survive a reordered profile bootstrap. */
static int manager_league_native_plan_members_valid(const GameplanPreset *plan) {
  if (!plan || !gameplan_preset_valid(plan)) return 0;
  uint32_t members = 0u;
  for (uint32_t i = 0u; i < plan->player_count; i++) {
    const GameplanPresetPlayer *player = &plan->players[i];
    if (player->reserved[1] != MANAGER_PLAN_MEMBER_MARKER ||
        player->reserved[2] != MANAGER_PLAN_MEMBER_VERSION) return 0;
    const uint32_t member = player->reserved[0];
    if (player->order_no >= 18u) {
      if (member != 0xffu) return 0;
    } else {
      if (member >= 18u || (members & (1u << member))) return 0;
      members |= 1u << member;
    }
  }
  return members == 0x3ffffu;
}

static int manager_league_native_plan_shape_valid(const GameplanPreset *plan) {
  if (!manager_dummy_plan_editor()) return 1;
  ManagerLeaguePlanScope scope;
  if (!manager_dummy_plan_scope(&scope) ||
      !manager_league_native_plan_members_valid(plan) ||
      !manager_league_plan_compatible(&scope, plan) ||
      !match_formation_get_role || !match_formation_get_position) return 0;
  for (uint32_t tactic = 0u; tactic < 2u; tactic++) {
    TmpdbFormationValue formation;
    memcpy(&formation, plan->formation[tactic], sizeof(formation));
    uint32_t keepers = 0u;
    for (uint32_t order = 0u; order < 11u; order++) {
      const uint32_t role = match_formation_get_role(&formation, order, 0u);
      const uint8_t *position = match_formation_get_position(&formation, order, 0u);
      if (role > 12u || !position || position[0] > 48u || position[1] > 105u) return 0;
      uint32_t native = 0u;
      for (uint32_t i = 0u; i < plan->player_count; i++)
        if (plan->players[i].order_no == order)
          memcpy(&native, plan->players[i].player_id, sizeof(native));
      uint32_t at = 0u;
      while (at < scope.player_count && scope.players[at] != native) at++;
      if (at == scope.player_count || ((role == 0u) != (scope.positions[at] == 0u))) return 0;
      keepers += role == 0u;
    }
    if (keepers != 1u) return 0;
  }
  return 1;
}

static int manager_league_native_plan_snapshot_members(uint32_t side,
                                                       GameplanPreset *plan) {
  if (!manager_dummy_plan_editor()) return 1;
  if (side != 0u || !plan || side > 1u) return 0;
  const PrematchGameplanSide *state = &exhibition_gameplan_sides[side];
  if (plan->player_count != state->player_count ||
      plan->player_count > GAMEPLAN_PRESET_MAX_PLAYERS) return 0;
  for (uint32_t i = 0u; i < plan->player_count; i++) {
    const uint32_t member = state->players[i].member_id;
    if (member >= 18u && member != 0xffu) return 0;
    plan->players[i].reserved[0] = (uint8_t)member;
    plan->players[i].reserved[1] = MANAGER_PLAN_MEMBER_MARKER;
    plan->players[i].reserved[2] = MANAGER_PLAN_MEMBER_VERSION;
  }
  return manager_league_native_plan_members_valid(plan);
}

/* Validate the native deep-copy transaction without publishing SquadEdit to
 * tmpdb::Match. There is no playable Manager fixture behind this editor. */
static int manager_league_office_lineup_valid(uint32_t side, void *squad) {
  if (side != 0u || !manager_dummy_plan_editor() || !squad || live_gameplan_window ||
      !exhibition_common_get_crypt_key || !exhibition_squad_data_get_player_count ||
      !exhibition_squad_data_get_player_by_index || !match_squad_data_get_member_id ||
      !match_squad_data_get_order_no) return 0;
  ManagerLeaguePlanScope scope;
  if (!manager_dummy_plan_scope(&scope) || !manager_league_plan_scope_valid(&scope) ||
      exhibition_squad_data_get_player_count(squad) != scope.player_count) return 0;
  GameplanPreset plan = {0};
  plan.team_id = scope.team_id;
  plan.player_count = scope.player_count;
  const uint32_t crypt = exhibition_common_get_crypt_key();
  uint32_t orders = 0u, members = 0u, reserve = 18u;
  for (uint32_t i = 0u; i < plan.player_count; i++) {
    const void *key = exhibition_squad_data_get_player_by_index(squad, &i);
    if (!key) return 0;
    uint32_t native = 0u;
    memcpy(&native, (const unsigned char *)key + 4u, sizeof(native));
    native ^= crypt;
    memcpy(plan.players[i].player_id, &native, sizeof(native));
    const uint32_t order = match_squad_data_get_order_no(squad, key);
    const uint32_t member = match_squad_data_get_member_id(squad, key);
    if (order == 0xffu && member == 0xffu) {
      plan.players[i].order_no = (uint8_t)reserve++;
      continue;
    }
    if (order >= 18u || member >= 18u ||
        (orders & (1u << order)) || (members & (1u << member))) return 0;
    orders |= 1u << order;
    members |= 1u << member;
    plan.players[i].order_no = (uint8_t)order;
  }
  return orders == 0x3ffffu && members == 0x3ffffu &&
      manager_league_plan_compatible(&scope, &plan);
}

static void main_menu_activate_manager_plan(void) {
  uint32_t home = 0u, away = 0u;
  if (!manager_dummy_plan_teams(&home, &away) || !home || !away || home == away) {
    manager_dummy_plan_handoff_result(0);
    return;
  }
  GameplanPreset current;
  manager_league_plan_restore_pending =
      manager_dummy_preset_read(home, MANAGER_LEAGUE_CURRENT_PLAN_SLOT, &current) != 0;
  __atomic_store_n(&exhibition_home_team_id, home, __ATOMIC_RELEASE);
  __atomic_store_n(&exhibition_away_team_id, away, __ATOMIC_RELEASE);
  __atomic_store_n(&main_menu_2p_prematch_bootstrap_mode,
      MAIN_MENU_2P_PREMATCH_BOOT_HUB, __ATOMIC_RELEASE);
  const int started = main_menu_start_exhibition_match();
  if (!started) manager_league_plan_restore_pending = 0u;
  manager_dummy_plan_handoff_result(started);
  if (started) competition_frontend_finish_close();
}
