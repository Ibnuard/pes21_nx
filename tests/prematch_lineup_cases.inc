static void init(void) {
  memset(plan, 0xa5, sizeof(plan));
  memset(match_bytes, 0xa6, sizeof(match_bytes));
  memset(teams, 0, sizeof(teams));
  for (uint32_t i = 0; i < TEST_COUNT; ++i) ids[i] = 100000u + i;
  ids[7] = 530066u; // Bright: registered starter.
  ids[21] = 7511u;  // Messi: full-roster reserve, NOT one of the native 18.
  for (uint32_t side = 0; side < 2u; ++side) {
    TestSquad *s = &squads[side];
    s->count = TEST_COUNT;
    *(unsigned char *)exhibition_matchplan_common_side(side) = TEST_COUNT;
    const uint32_t flags = TEST_COUNT << 9;
    memcpy(teams[side] + 0x3a6u, &flags, 4u);
    for (uint32_t i = 0; i < TEST_COUNT; ++i) {
      s->key[i][0] = 0xfffeu - side; s->key[i][1] = ids[i] ^ CRYPT_KEY;
      s->key[i][2] = i + 800u; s->key[i][3] = 0;
      if (i < 18u) { s->member_uid[i] = ids[i]; s->order[i] = i; }
      unsigned char *p = (unsigned char *)get_player(match_bytes, &side, &i);
      const uint64_t id = ((uint64_t)ids[i] << 32) | (0xfffeu - side);
      memset(p, (int)(i + 1 + side * 40u), 0x380u);
      memcpy(p + 44, &id, 8u);
      snprintf((char *)p + 56, 40, "PLAYER-%u-SIDE-%u", ids[i], side);
      memcpy(original[side][i], p, 0x380u);
      memcpy(teams[side] + 0x110u + i * 8u, &id, 8u);
      const uint16_t shirt = (uint16_t)(i + 1);
      memcpy(teams[side] + 0x25cu + i * 2u, &shirt, 2u);
      unsigned char *info = plan + 0x500u + side * 0x340u + i * 16u;
      memset(info, (int)(i + 19u + side * 40u), 8u);
      memcpy(original_info[side][i], info, 8u);
      memcpy(info + 8u, &p, sizeof(p));
      set_member(exhibition_matchplan_common_side(side), i, i);
    }
    set_match_order(exhibition_matchplan_common_side(side));
  }
}

static void assert_consistent(uint32_t side) {
  uint64_t seen = 0;
  const unsigned char *common = exhibition_matchplan_common_side(side);
  for (uint32_t i = 0; i < TEST_COUNT; ++i) {
    const void *p = get_player(match_bytes, &side, &i), *info_player = NULL;
    const unsigned char *info = plan + 0x500u + side * 0x340u + i * 16u;
    uint64_t id = 0, team_id = 0;
    memcpy(&id, (const unsigned char *)p + 44, 8u);
    uint32_t from = 0;
    while (from < TEST_COUNT && ids[from] != (uint32_t)(id >> 32)) ++from;
    assert(from < TEST_COUNT && !(seen & (1ULL << from)));
    seen |= 1ULL << from;
    // Identity, appearance, attributes, condition, base and increased copies.
    assert(memcmp(p, original[side][from], 0x380u) == 0);
    assert(memcmp(info, original_info[side][from], 8u) == 0);
    memcpy(&info_player, info + 8, sizeof(info_player));
    assert(info_player == p);
    memcpy(&team_id, teams[side] + 0x110u + i * 8u, 8u);
    assert(id == team_id);
    uint16_t shirt = 0;
    memcpy(&shirt, teams[side] + 0x25cu + i * 2u, 2u);
    assert(shirt == from + 1u);
    if (i < 18u) assert((uint32_t)(id >> 32) == squads[side].member_uid[i]);
    assert(common[0x1b4u + i] == (i < 18u ? squads[side].order[i] : i));
    if (i < 11u) {
      uint32_t match_member = 0;
      memcpy(&match_member, common + 0x1ecu + i * 4u, 4u);
      assert(match_member == squads[side].order[i]);
    }
  }
  assert(seen == (1ULL << TEST_COUNT) - 1u);
  assert(copies == destroys);
}

static void do_swap(uint32_t side, uint32_t field, uint32_t bench) {
  assert(prematch_gameplan_replace_player(side, &squads[side],
      squads[side].key[field], squads[side].key[bench]));
  assert_consistent(side);
}

static void test_reserve(void) {
  assert(get_member(&squads[0], squads[0].key[21]) == 0xffu);
  do_swap(0, 7, 21);
  assert(get_member(&squads[0], squads[0].key[21]) == 7u);
  assert(get_order(&squads[0], squads[0].key[21]) == 7u);
  const uint32_t side = 0, member = 7;
  const unsigned char *actor = get_player(match_bytes, &side, &member);
  assert(strstr((const char *)actor + 56, "7511"));
  assert(memcmp(actor, original[0][21], 0x380u) == 0);
  assert_consistent(1);
}

static void test_bench(void) {
  do_swap(0, 7, 12);
  assert(get_member(&squads[0], squads[0].key[12]) == 12u);
  assert(get_order(&squads[0], squads[0].key[12]) == 7u);
  const uint32_t side = 0, member = 7;
  assert(memcmp(get_player(match_bytes, &side, &member), original[0][7], 0x380u) == 0);
  assert_consistent(1);
}

static void test_repeat(void) {
  do_swap(0, 7, 21);
  do_swap(0, 21, 24);
  do_swap(0, 24, 7);
  do_swap(0, 4, 12);
  do_swap(0, 12, 25); // Reuse member 12 at order 4, not member/order equality.
  unsigned char before[sizeof(match_bytes)], before_plan[sizeof(plan)];
  memcpy(before, match_bytes, sizeof(before)); memcpy(before_plan, plan, sizeof(plan));
  my_side = 1;
  for (uint32_t i = 0; i < 4u; ++i) exhibition_save_matchplan_sides(3u);
  assert(my_side == 1 && saves[0] == 4u && saves[1] == 4u && publishes == 4u);
  assert(memcmp(before, match_bytes, sizeof(before)) == 0);
  assert(memcmp(before_plan, plan, sizeof(plan)) == 0);
  assert_consistent(0); assert_consistent(1);
}

static void test_sides(void) {
  // Same team/unique IDs, distinct side-local payloads and locators.
  do_swap(1, 7, 21);
  assert(get_order(&squads[0], squads[0].key[21]) == 0xffu);
  assert_consistent(0);
  do_swap(0, 4, 22);
  assert_consistent(1);
}

static void test_reject(void) {
  unsigned char before[sizeof(match_bytes)], before_plan[sizeof(plan)];
  TestSquad before_squad = squads[0];
  memcpy(before, match_bytes, sizeof(before)); memcpy(before_plan, plan, sizeof(plan));
  fail_alloc = 1;
  assert(!prematch_gameplan_replace_player(0, &squads[0], squads[0].key[7], squads[0].key[21]));
  fail_alloc = 0;
  assert(memcmp(&before_squad, &squads[0], sizeof(before_squad)) == 0);
  assert(memcmp(before, match_bytes, sizeof(before)) == 0);
  assert(memcmp(before_plan, plan, sizeof(plan)) == 0);
  squads[0].key[21][1] ^= 0x01000000u; // Unknown identity, no fallback to HOME[0].
  before_squad = squads[0];
  assert(!prematch_gameplan_replace_player(0, &squads[0], squads[0].key[7], squads[0].key[21]));
  assert(memcmp(&before_squad, &squads[0], sizeof(before_squad)) == 0);
  assert(memcmp(before, match_bytes, sizeof(before)) == 0);
  assert(memcmp(before_plan, plan, sizeof(plan)) == 0);
  squads[0].key[21][1] ^= 0x01000000u;
  exhibition_plan_ready = 0;
  assert(!prematch_gameplan_replace_player(0, &squads[0], squads[0].key[7], squads[0].key[21]));
  exhibition_plan_ready = 1;
  teams[0][0x110 + 21 * 8 + 4] ^= 1u;
  assert(!prematch_gameplan_replace_player(0, &squads[0], squads[0].key[7], squads[0].key[21]));
  assert(memcmp(before, match_bytes, sizeof(before)) == 0);
  assert(copies == destroys);
}

static void test_live(void) {
  unsigned char before[sizeof(match_bytes)], before_plan[sizeof(plan)];
  memcpy(before, match_bytes, sizeof(before)); memcpy(before_plan, plan, sizeof(plan));
  live_gameplan_window = (void *)1;
  assert(!exhibition_sync_prematch_lineup(0, &squads[0]));
  assert(!prematch_gameplan_replace_player(0, &squads[0], squads[0].key[7], squads[0].key[12]));
  exhibition_save_matchplan_sides(1u); // Native live reservations still saved.
  assert(saves[0] == 1 && !saves[1] && publishes == 1);
  assert(memcmp(before, match_bytes, sizeof(before)) == 0);
  assert(memcmp(before_plan, plan, sizeof(plan)) == 0);
}

static void test_conditions(void) {
  exhibition_prepare_team_conditions(100, 200);
  assert(condition_calls == 2 && last_condition_mode == 5);
  exhibition_prepare_team_conditions(100, 200);
  assert(condition_calls == 2);
  exhibition_settings_player_condition = 2;
  exhibition_prepare_team_conditions(100, 200);
  assert(condition_calls == 4 && last_condition_mode == 2);
}
static void test_office(void) {
  unsigned char before[sizeof(match_bytes)],before_plan[sizeof(plan)];
  memcpy(before,match_bytes,sizeof(before));memcpy(before_plan,plan,sizeof(plan));
  office_editor=1;exhibition_plan_ready=0; /* No playable MatchPlan is required. */
  assert(prematch_gameplan_replace_player(0,&squads[0],squads[0].key[7],squads[0].key[21]));
  assert(get_order(&squads[0],squads[0].key[21])==7u);
  assert(get_order(&squads[0],squads[0].key[7])==0xffu);
  assert(prematch_gameplan_replace_player(0,&squads[0],squads[0].key[21],squads[0].key[12]));
  assert(get_order(&squads[0],squads[0].key[12])==7u);
  exhibition_save_matchplan_sides(3u);assert(!saves[0] && !saves[1] && !publishes);
  assert(!memcmp(before,match_bytes,sizeof(before)) && !memcmp(before_plan,plan,sizeof(plan)));
  TestSquad own=squads[0],other=squads[1];
  assert(!prematch_gameplan_replace_player(1,&squads[1],squads[1].key[7],squads[1].key[21]));
  assert(!memcmp(&other,&squads[1],sizeof(other)));
  squads[0].key[24][1]^=0x10000000u;own=squads[0];
  assert(!prematch_gameplan_replace_player(0,&squads[0],squads[0].key[12],squads[0].key[24]));
  assert(!memcmp(&own,&squads[0],sizeof(own))); /* unknown career identity rolls back */
  squads[0].key[24][1]^=0x10000000u;
  memcpy(squads[0].key[24],squads[0].key[23],16u);own=squads[0];
  assert(!prematch_gameplan_replace_player(0,&squads[0],squads[0].key[12],squads[0].key[23]));
  assert(!memcmp(&own,&squads[0],sizeof(own))); /* duplicate reserves also fail */
  assert(copies==destroys);
}

int main(int argc, char **argv) {
  assert(argc == 2); init();
  if (!strcmp(argv[1], "reserve")) test_reserve();
  else if (!strcmp(argv[1], "bench")) test_bench();
  else if (!strcmp(argv[1], "repeat")) test_repeat();
  else if (!strcmp(argv[1], "sides")) test_sides();
  else if (!strcmp(argv[1], "reject")) test_reject();
  else if (!strcmp(argv[1], "live")) test_live();
  else if (!strcmp(argv[1], "conditions")) test_conditions();
  else if (!strcmp(argv[1], "office")) test_office();
  else assert(0);
  return 0;
}
