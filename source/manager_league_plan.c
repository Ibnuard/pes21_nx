#include "manager_league_plan.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#endif

enum { MANAGER_PLAN_MAGIC = 0x31504d46u, MANAGER_PLAN_VERSION = 1u };
/* Explicit 32-bit fields keep the on-disk envelope independent of uint64_t
 * alignment. The complete canonical membership is compared, not a short hash. */
typedef struct {
  uint32_t magic, version, bytes, sequence, checksum;
  uint32_t account_low, account_high, team_id, player_count;
  char runtime_id[16], content_hash[64];
  uint32_t players[GAMEPLAN_PRESET_MAX_PLAYERS];
  uint32_t positions[GAMEPLAN_PRESET_MAX_PLAYERS];
} ManagerPlanHeader;

static int manager_plan_hex(const char *text, uint32_t count) {
  uint32_t nonzero = 0u;
  for (uint32_t i = 0; i < count; i++) {
    if (!((text[i] >= '0' && text[i] <= '9') ||
          (text[i] >= 'a' && text[i] <= 'f'))) return 0;
    nonzero |= text[i] != '0';
  }
  return nonzero != 0u;
}

int manager_league_plan_scope_valid(const ManagerLeaguePlanScope *scope) {
  if (!scope || !scope->account || !scope->team_id ||
      scope->player_count < 18u ||
      scope->player_count > GAMEPLAN_PRESET_MAX_PLAYERS ||
      !manager_plan_hex(scope->runtime_id, sizeof(scope->runtime_id)) ||
      !manager_plan_hex(scope->content_hash, sizeof(scope->content_hash))) return 0;
  uint32_t keepers = 0u;
  for (uint32_t i = 0; i < scope->player_count; i++) {
    if (!scope->players[i] || scope->positions[i] > 12u) return 0;
    keepers += scope->positions[i] == 0u;
    for (uint32_t j = 0; j < i; j++)
      if (scope->players[j] == scope->players[i]) return 0;
  }
  return keepers != 0u;
}

int manager_league_plan_compatible(const ManagerLeaguePlanScope *scope,
                                   const GameplanPreset *plan) {
  if (!manager_league_plan_scope_valid(scope) || !gameplan_preset_valid(plan) ||
      plan->team_id != scope->team_id ||
      plan->player_count != scope->player_count) return 0;
  uint32_t starting_keepers = 0u;
  for (uint32_t i = 0; i < plan->player_count; i++) {
    uint32_t native = 0u;
    memcpy(&native, plan->players[i].player_id, sizeof(native));
    for (uint32_t b = sizeof(native); b < sizeof(plan->players[i].player_id); b++)
      if (plan->players[i].player_id[b]) return 0;
    uint32_t at = 0u;
    while (at < scope->player_count && scope->players[at] != native) at++;
    if (at == scope->player_count) return 0;
    /* Native squad order is not a role index. Exactly one natural keeper
     * must remain registered among the eleven, in any native order. */
    starting_keepers += plan->players[i].order_no < 11u && scope->positions[at] == 0u;
  }
  return starting_keepers == 1u;
}

static ManagerPlanHeader manager_plan_header(const ManagerLeaguePlanScope *scope) {
  ManagerPlanHeader header = {0};
  header.magic = MANAGER_PLAN_MAGIC;
  header.version = MANAGER_PLAN_VERSION;
  header.bytes = sizeof(GameplanPreset);
  header.account_low = (uint32_t)scope->account;
  header.account_high = (uint32_t)(scope->account >> 32u);
  header.team_id = scope->team_id;
  header.player_count = scope->player_count;
  memcpy(header.runtime_id, scope->runtime_id, sizeof(header.runtime_id));
  memcpy(header.content_hash, scope->content_hash, sizeof(header.content_hash));
  /* Membership is a set. Saving an order and reopening with that order must
   * not invalidate its own roster namespace. */
  for (uint32_t i = 0; i < scope->player_count; i++) {
    uint32_t at = i;
    while (at && header.players[at - 1u] > scope->players[i]) {
      header.players[at] = header.players[at - 1u];
      header.positions[at] = header.positions[at - 1u];
      at--;
    }
    header.players[at] = scope->players[i];
    header.positions[at] = scope->positions[i];
  }
  return header;
}

static uint32_t manager_plan_hash(uint32_t hash, const void *data, size_t bytes) {
  const unsigned char *cursor = data;
  for (size_t i = 0; i < bytes; i++) {
    hash ^= cursor[i];
    hash *= 16777619u;
  }
  return hash;
}

static uint32_t manager_plan_checksum(const ManagerPlanHeader *header,
                                      const GameplanPreset *plan) {
  ManagerPlanHeader checked = *header;
  checked.checksum = 0u;
  return manager_plan_hash(manager_plan_hash(2166136261u, &checked,
      sizeof(checked)), plan, sizeof(*plan));
}

static void manager_plan_path(const ManagerLeaguePlanScope *scope, uint32_t slot,
                               uint32_t copy, char path[112]) {
  snprintf(path, 112, "SaveData/footballnx_manager_plan_%08x%08x_%u_%u_%c.bin",
      (unsigned)(scope->account >> 32u), (unsigned)scope->account,
      (unsigned)scope->team_id, (unsigned)(slot + 1u), copy ? 'b' : 'a');
}

static int manager_plan_read_copy(const ManagerLeaguePlanScope *scope,
                                  uint32_t slot, uint32_t copy,
                                  GameplanPreset *out, uint32_t *sequence) {
  char path[112];
  manager_plan_path(scope, slot, copy, path);
  FILE *stream = fopen(path, "rb");
  if (!stream) return 0;
  ManagerPlanHeader header;
  GameplanPreset plan;
  const int read = fread(&header, 1, sizeof(header), stream) == sizeof(header) &&
      fread(&plan, 1, sizeof(plan), stream) == sizeof(plan);
  const int end = fgetc(stream) == EOF;
  const int closed = fclose(stream) == 0;
  if (!read || !end || !closed ||
      header.checksum != manager_plan_checksum(&header, &plan) ||
      !manager_league_plan_compatible(scope, &plan)) return 0;
  ManagerPlanHeader expected = manager_plan_header(scope);
  expected.sequence = header.sequence;
  expected.checksum = header.checksum;
  if (memcmp(&header, &expected, sizeof(header))) return 0;
  *out = plan;
  *sequence = header.sequence;
  return 1;
}

static int manager_plan_sequence_after(uint32_t first, uint32_t second) {
  const uint32_t delta = first - second;
  return delta && delta < 0x80000000u;
}

int manager_league_plan_read(const ManagerLeaguePlanScope *scope, uint32_t slot,
                              GameplanPreset *out) {
  if (!out || slot > MANAGER_LEAGUE_CURRENT_PLAN_SLOT ||
      !manager_league_plan_scope_valid(scope)) return 0;
  GameplanPreset plans[2];
  uint32_t sequence[2] = {0};
  const int a = manager_plan_read_copy(scope, slot, 0u, &plans[0], &sequence[0]);
  const int b = manager_plan_read_copy(scope, slot, 1u, &plans[1], &sequence[1]);
  if (!a && !b) return 0;
  *out = !a || (b && manager_plan_sequence_after(sequence[1], sequence[0]))
      ? plans[1] : plans[0];
  return 1;
}

int manager_league_plan_write(const ManagerLeaguePlanScope *scope, uint32_t slot,
                               const GameplanPreset *plan) {
  if (slot > MANAGER_LEAGUE_CURRENT_PLAN_SLOT ||
      !manager_league_plan_compatible(scope, plan)) return 0;
#ifdef _WIN32
  if (_mkdir("SaveData") != 0 && errno != EEXIST) return 0;
#else
  if (mkdir("SaveData", 0777) != 0 && errno != EEXIST) return 0;
#endif
  GameplanPreset previous[2];
  uint32_t sequence[2] = {0};
  const int a = manager_plan_read_copy(scope, slot, 0u, &previous[0], &sequence[0]);
  const int b = manager_plan_read_copy(scope, slot, 1u, &previous[1], &sequence[1]);
  const uint32_t newest = !a || (b && manager_plan_sequence_after(sequence[1], sequence[0])) ? 1u : 0u;
  const uint32_t copy = !a ? 0u : !b ? 1u : 1u - newest;
  ManagerPlanHeader header = manager_plan_header(scope);
  header.sequence = a || b ? sequence[newest] + 1u : 1u;
  header.checksum = manager_plan_checksum(&header, plan);
  char path[112];
  manager_plan_path(scope, slot, copy, path);
  FILE *stream = fopen(path, "wb");
  if (!stream) return 0;
  const int written = fwrite(&header, 1, sizeof(header), stream) == sizeof(header) &&
      fwrite(plan, 1, sizeof(*plan), stream) == sizeof(*plan);
  const int flushed = fflush(stream) == 0;
  const int closed = fclose(stream) == 0;
  GameplanPreset verify;
  uint32_t verified_sequence = 0u;
  return written && flushed && closed &&
      manager_plan_read_copy(scope, slot, copy, &verify, &verified_sequence) &&
      verified_sequence == header.sequence && !memcmp(&verify, plan, sizeof(verify));
}
