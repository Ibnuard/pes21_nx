#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define debugPrintf(...) ((void)0)
#define EXHIBITION_PRE_STRATEGY_SQUAD_SNAPSHOT_BYTES 2048u
#define CRYPT_KEY 0xa59c43e7u
#define TEST_COUNT 26u
typedef struct {
  uint32_t count, key[40][4], member_uid[18], order[18];
} TestSquad;
typedef struct { uint32_t order, member, key[4]; } TestSwap;
static TestSquad squads[2];
static unsigned char plan[0x1200], match_bytes[0x1248 + 2 * 0x8c00], teams[2][0x590];
static unsigned char original[2][40][0x380], original_info[2][40][8];
static uint32_t ids[40], exhibition_plan_ready = 1, my_side, saves[2], publishes;
static uint32_t copies, destroys, fail_alloc;
static void *live_gameplan_window;
static int office_editor;
typedef struct {struct {uint32_t club;} settings;} MasterLeague;
static const MasterLeague career={.settings={101u}};
static int ml_frontend_plan_editor(void){return office_editor;}
static const MasterLeague *ml_frontend_career(void){return &career;}
static int ml_frontend_roster(uint32_t team,uint32_t players[40],uint8_t shirts[40],uint32_t *count) {
  assert(team==101u);*count=TEST_COUNT;
  for(uint32_t i=0;i<TEST_COUNT;i++){players[i]=ids[i];shirts[i]=(uint8_t)(i+1u);}return 1;
}
static void *get_plan(void) { return plan; }
static void *(*exhibition_matchplan_get_instance)(void) = get_plan;
static void *exhibition_get_tmpdb_match(void) { return match_bytes; }
static unsigned char *exhibition_get_squad_edit(void) { return (unsigned char *)squads; }
static void *get_squad(void *edit, uint32_t side) { (void)edit; return &squads[side]; }
static void *(*exhibition_squad_edit_get_squad_data)(void *, uint32_t) = get_squad;
static uint32_t get_count(void *squad) { return ((TestSquad *)squad)->count; }
static uint32_t (*exhibition_squad_data_get_player_count)(void *) = get_count;
static void *get_key(void *squad, const uint32_t *i) { return ((TestSquad *)squad)->key[*i]; }
static void *(*exhibition_squad_data_get_player_by_index)(void *, const uint32_t *) = get_key;
static uint32_t get_member(void *squad, const void *key) {
  const TestSquad *s = squad;
  const uint32_t uid = ((const uint32_t *)key)[1] ^ CRYPT_KEY;
  for (uint32_t i = 0; i < 18u; ++i) if (s->member_uid[i] == uid) return i;
  return 0xffu;
}
static uint32_t (*match_squad_data_get_member_id)(void *, const void *) = get_member;
static uint32_t get_order(void *squad, const void *key) {
  const TestSquad *s = squad;
  const uint32_t member = get_member(squad, key);
  if (member == 0xffu) return 0xffu;
  for (uint32_t order = 0; order < 18u; ++order)
    if (s->order[order] == member) return order;
  return 0xffu;
}
static uint32_t (*match_squad_data_get_order_no)(void *, const void *) = get_order;
static const void *get_player(const void *match, const uint32_t *side, const uint32_t *i) {
  return (const unsigned char *)match + 0x1248u + *side * 0x8c00u + *i * 0x380u;
}
static const void *(*match_tmpdb_match_get_player)(const void *, const uint32_t *, const uint32_t *) = get_player;
static void *get_team(void *match, const uint32_t *side) { (void)match; return teams[*side]; }
static void *(*exhibition_tmpdb_match_get_team)(void *, const uint32_t *) = get_team;
static uint32_t crypt_key(void) { return CRYPT_KEY; }
static uint32_t (*exhibition_common_get_crypt_key)(void) = crypt_key;
static uint32_t get_num(const void *common) { return *(const unsigned char *)common; }
static uint32_t (*matchplan_common_get_player_num)(const void *) = get_num;
static void set_member(void *common, uint32_t order, uint32_t member) {
  ((unsigned char *)common)[0x1b4 + order] = (unsigned char)member;
}
static void (*matchplan_common_set_member_id)(void *, uint32_t, uint32_t) = set_member;
static void set_match_order(void *common) {
  for (uint32_t i = 0; i < 11u; ++i) {
    const uint32_t member = ((unsigned char *)common)[0x1b4 + i];
    memcpy((unsigned char *)common + 0x1ec + i * 4u, &member, 4u);
  }
}
static void (*matchplan_common_set_match_order)(void *) = set_match_order;
static uint32_t get_my_side(const void *edit) { (void)edit; return my_side; }
static uint32_t (*exhibition_squad_edit_get_my_side)(const void *) = get_my_side;
static void set_my_side(void *edit, const uint32_t *side) { (void)edit; my_side = *side; }
static void (*exhibition_squad_edit_set_my_side)(void *, const uint32_t *) = set_my_side;
static void save_squad(void) { assert(my_side < 2u); saves[my_side]++; }
static void (*matchplan_squad_save)(void) = save_squad;
static void publish(void *p) { assert(p == plan); publishes++; }
static void (*exhibition_matchplan_update_tmpdb)(void *) = publish;
static void construct(void *dest, const void *src) { memcpy(dest, src, sizeof(TestSquad)); copies++; }
static void (*match_squad_data_copy_construct)(void *, const void *) = construct;
static void *assign(void *dest, const void *src) { return memcpy(dest, src, sizeof(TestSquad)); }
static void *(*match_squad_data_copy_assign)(void *, const void *) = assign;
static void destruct(void *squad) { (void)squad; destroys++; }
static void (*match_squad_data_destruct)(void *) = destruct;
static void make_swap(void *value, uint32_t order, uint32_t member, const void *key) {
  TestSwap *s = value; s->order = order; s->member = member; memcpy(s->key, key, 16u);
}
static void (*match_swap_member_info_construct)(void *, uint32_t, uint32_t, const void *) = make_swap;
static void replace(void *squad, const void *first, const void *second) {
  TestSquad *s = squad;
  const TestSwap *a = first, *b = second;
  assert(a->member < 18u && a->order < 18u);
  if (b->member == 0xffu) {
    assert(b->order == 0xffu);
    s->member_uid[a->member] = b->key[1] ^ CRYPT_KEY;
  } else {
    assert(b->member < 18u && b->order < 18u);
    s->order[a->order] = b->member; s->order[b->order] = a->member;
  }
}
static void (*match_replace_squad_player)(void *, const void *, const void *) = replace;
static void *allocate(size_t size) { return fail_alloc ? NULL : malloc(size); }
#define malloc allocate

static uint32_t exhibition_settings_player_condition = 5;
static uint32_t exhibition_condition_team_ids[2], exhibition_condition_applied_mode;
static uint32_t exhibition_condition_initialized, condition_calls, last_condition_mode;
static void setup_condition(const uint32_t *team, uint32_t mode, uint32_t boosted, uint32_t force_normal) {
  assert(*team && !boosted && !force_normal); condition_calls++; last_condition_mode = mode;
}
static void (*exhibition_setup_random_condition)(const uint32_t *, uint32_t, uint32_t, uint32_t) = setup_condition;
