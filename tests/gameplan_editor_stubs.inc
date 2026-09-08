#pragma pack(push, 1)
typedef struct {
  uint8_t native_prefix[0x1cc];
  TmpdbFormationValue formation[2];
  uint32_t saved;
  uint32_t written;
} MockSquad;
#pragma pack(pop)
static MockSquad mock_squads[2];
static uint32_t mock_bench_swaps;

static const uint8_t *mock_position(const void *f, uint32_t order, uint32_t phase) {
  assert(order < 11 && phase == 0);
  return (const uint8_t *)f + order * 2;
}
static uint32_t mock_role(const void *f, uint32_t order, uint32_t phase) {
  assert(order < 11 && phase == 0);
  return ((const uint8_t *)f)[22 + order];
}
static void mock_set_position(void *f, uint32_t order, const void *pos, uint32_t phase) {
  assert(order < 11 && phase == 0);
  const uint8_t *p = pos;
  assert(p[0] <= 48 && p[1] <= 105);
  memcpy((uint8_t *)f + order * 2, p, 2);
}
static void mock_set_role(void *f, uint32_t order, uint32_t role, uint32_t phase) {
  assert(order < 11 && role < 13 && phase == 0);
  ((uint8_t *)f)[22 + order] = (uint8_t)role;
}
static TmpdbFormationValue mock_get_formation(const void *squad, uint32_t tactics) {
  assert(tactics < 2);
  return ((const MockSquad *)squad)->formation[tactics];
}
static void mock_set_formation(void *squad, uint32_t tactics, const void *formation) {
  assert(tactics < 2);
  MockSquad *s = squad;
  // The real setter only stores roles; it never stores formation coordinates.
  memcpy((uint8_t *)&s->formation[tactics] + 22, (const uint8_t *)formation + 22, 11);
  s->written++;
}
static void *mock_copy_formation(void *destination, const void *source) {
  return memcpy(destination, source, sizeof(TmpdbFormationValue));
}
static void mock_set_player_role(void *squad, uint32_t role, uint32_t member,
                                 const uint32_t *tactics) {
  assert(member < 11 && tactics != NULL && *tactics < 2);
  mock_set_role(&((MockSquad *)squad)->formation[*tactics], member, role, 0);
}
static void prematch_gameplan_refresh_side(uint32_t side) {
  PrematchGameplanSide *s = &exhibition_gameplan_sides[side];
  const TmpdbFormationValue *f = &mock_squads[side].formation[s->tactics];
  for (uint32_t i = 0; i < s->field_count; i++) {
    PrematchGameplanPlayer *p = prematch_gameplan_nth_player(s, 1, i);
    const uint8_t *pos = mock_position(f, p->order_no, 0);
    p->role = (uint8_t)mock_role(f, p->order_no, 0);
    p->pitch_x = (uint8_t)((pos[1] * 255u + 52u) / 105u);
    p->pitch_y = (uint8_t)(255u - (pos[0] * 255u + 24u) / 48u);
  }
  prematch_gameplan_build_formation_label(s);
  prematch_gameplan_detect_preset(s);
}
static void exhibition_save_matchplan_sides(uint32_t mask) {
  for (uint32_t i = 0; i < 2; i++)
    if (mask & (1u << i)) mock_squads[i].saved++;
}
static void prematch_gameplan_swap(uint32_t side) {
  mock_bench_swaps++;
  exhibition_gameplan_sides[side].selected_area = PREMATCH_GAMEPLAN_NO_SELECTION;
  exhibition_gameplan_sides[side].selected_index = PREMATCH_GAMEPLAN_NO_SELECTION;
}
static void prematch_gameplan_toggle_formation_setting(uint32_t side, uint32_t row) {
  if (row == 0) exhibition_gameplan_sides[side].tactics ^= 1u;
  prematch_gameplan_refresh_side(side);
}
static void prematch_gameplan_process_root(uint32_t side, uint32_t action) {
  if (action == PES_PAUSE_INPUT_DECIDE)
    exhibition_gameplan_sides[side].page = PES_PREMATCH_GAMEPLAN_PAGE_SUBSTITUTE;
}
static void prematch_gameplan_process_auto(uint32_t side, uint32_t action) {
  (void)side; (void)action;
}
static void prematch_gameplan_process_positions(uint32_t side, uint32_t action) {
  (void)side; (void)action;
}
