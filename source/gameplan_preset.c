#include "gameplan_preset.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#endif

#define GAMEPLAN_PRESET_MAGIC 0x31504e46u /* FNP1 */
#define GAMEPLAN_PRESET_VERSION 1u

typedef struct {
  uint32_t magic, version, size, sequence, checksum;
} GameplanPresetHeader;

static uint32_t gameplan_preset_checksum(const GameplanPreset *preset) {
  const uint8_t *bytes = (const uint8_t *)preset;
  uint32_t hash = 2166136261u;
  for (size_t i = 0; i < sizeof(*preset); ++i) {
    hash ^= bytes[i];
    hash *= 16777619u;
  }
  return hash;
}

int gameplan_preset_valid(const GameplanPreset *preset) {
  if (!preset || !preset->team_id ||
      preset->player_count < 11u ||
      preset->player_count > GAMEPLAN_PRESET_MAX_PLAYERS ||
      preset->tactics > 1u) return 0;
  uint32_t starting = 0;
  for (uint32_t i = 0; i < preset->player_count; ++i) {
    const GameplanPresetPlayer *entry = &preset->players[i];
    if (entry->order_no >= preset->player_count) return 0;
    if (entry->order_no < 11u) starting++;
    for (uint32_t j = 0; j < i; ++j)
      if (entry->order_no == preset->players[j].order_no ||
          memcmp(entry->player_id, preset->players[j].player_id,
                 sizeof(entry->player_id)) == 0)
        return 0;
  }
  return starting == 11u;
}

static void gameplan_preset_path(uint32_t team_id, uint32_t slot,
                                 uint32_t copy, char path[80]) {
  snprintf(path, 80, "SaveData/footballnx_plan_%u_%u_%c.bin",
           team_id, slot + 1u, copy ? 'b' : 'a');
}

static int gameplan_preset_read_copy(uint32_t team_id, uint32_t slot,
                                     uint32_t copy, GameplanPreset *out,
                                     uint32_t *sequence, const char *scope,
                                     uint32_t *canonical) {
  char path[80];
  gameplan_preset_path(team_id, slot, copy, path);
  FILE *stream = fopen(path, "rb");
  if (!stream) return 0;
  GameplanPresetHeader header;
  char stored_scope[16];
  const int header_read = fread(&header, 1, sizeof(header), stream) == sizeof(header);
  const int scoped = header_read && header.version == 2u;
  const int scope_read = !scoped || (fread(stored_scope, 1, sizeof(stored_scope), stream) == sizeof(stored_scope) &&
      scope && strlen(scope) == sizeof(stored_scope) && !memcmp(scope, stored_scope, sizeof(stored_scope)));
  const int read = header_read && scope_read &&
      fread(out, 1, sizeof(*out), stream) == sizeof(*out);
  const int end = fgetc(stream) == EOF;
  const int closed = fclose(stream) == 0;
  if (!read || !end || !closed || header.magic != GAMEPLAN_PRESET_MAGIC ||
      (header.version != GAMEPLAN_PRESET_VERSION && header.version != 2u) ||
      header.size != sizeof(*out) || out->team_id != team_id ||
      header.checksum != gameplan_preset_checksum(out) ||
      !gameplan_preset_valid(out)) return 0;
  *sequence = header.sequence;
  if (canonical) *canonical = scoped;
  return 1;
}

int gameplan_preset_read_scoped(uint32_t team_id, uint32_t slot,
                         GameplanPreset *out, const char *scope, uint32_t *canonical) {
  if (!team_id || slot >= GAMEPLAN_PRESET_SLOTS || !out) return 0;
  GameplanPreset first, second;
  uint32_t first_seq = 0, second_seq = 0;
  uint32_t first_kind = 0, second_kind = 0;
  const int a = gameplan_preset_read_copy(team_id, slot, 0u,
                                          &first, &first_seq, scope, &first_kind);
  const int b = gameplan_preset_read_copy(team_id, slot, 1u,
                                          &second, &second_seq, scope, &second_kind);
  if (!a && !b) return 0;
  *out = !a ? second : !b || first_seq >= second_seq ? first : second;
  if (canonical) *canonical = !a ? second_kind : !b || first_seq >= second_seq ? first_kind : second_kind;
  return 1;
}

int gameplan_preset_read(uint32_t team_id, uint32_t slot, GameplanPreset *out) {
  return gameplan_preset_read_scoped(team_id, slot, out, NULL, NULL);
}

int gameplan_preset_slot_present(uint32_t team_id, uint32_t slot) {
  if (!team_id || slot >= GAMEPLAN_PRESET_SLOTS) return 0;
  for (uint32_t copy = 0; copy < 2u; ++copy) {
    char path[80]; gameplan_preset_path(team_id, slot, copy, path);
    struct stat info;
    if (!stat(path, &info)) return 1;
  }
  return 0;
}

int gameplan_preset_write_scoped(uint32_t team_id, uint32_t slot,
                          const GameplanPreset *preset, const char *scope) {
  if (!team_id || slot >= GAMEPLAN_PRESET_SLOTS || !preset ||
      preset->team_id != team_id || !gameplan_preset_valid(preset) ||
      (scope && strlen(scope) != 16u)) return 0;
#ifdef _WIN32
  if (_mkdir("SaveData") != 0 && errno != EEXIST) return 0;
#else
  if (mkdir("SaveData", 0777) != 0 && errno != EEXIST) return 0;
#endif
  GameplanPreset first, second;
  uint32_t first_seq = 0, second_seq = 0;
  const int a = gameplan_preset_read_copy(team_id, slot, 0u,
                                          &first, &first_seq, scope, NULL);
  const int b = gameplan_preset_read_copy(team_id, slot, 1u,
                                          &second, &second_seq, scope, NULL);
  const uint32_t copy = !a ? 0u : !b ? 1u
      : first_seq <= second_seq ? 0u : 1u;
  const uint32_t sequence = a && (!b || first_seq >= second_seq)
      ? first_seq + 1u : b ? second_seq + 1u : 1u;
  GameplanPresetHeader header = {GAMEPLAN_PRESET_MAGIC,
      scope ? 2u : GAMEPLAN_PRESET_VERSION, sizeof(*preset), sequence,
      gameplan_preset_checksum(preset)};
  char path[80];
  gameplan_preset_path(team_id, slot, copy, path);
  FILE *stream = fopen(path, "wb");
  if (!stream) return 0;
  const int written = fwrite(&header, 1, sizeof(header), stream) ==
          sizeof(header) &&
      (!scope || fwrite(scope, 1, 16u, stream) == 16u) &&
      fwrite(preset, 1, sizeof(*preset), stream) == sizeof(*preset);
  const int flushed = fflush(stream) == 0;
  const int closed = fclose(stream) == 0;
  GameplanPreset verify;
  uint32_t verify_seq = 0;
  return written && flushed && closed &&
      gameplan_preset_read_copy(team_id, slot, copy, &verify,
                                &verify_seq, scope, NULL) && verify_seq == sequence;
}

int gameplan_preset_write(uint32_t team_id, uint32_t slot, const GameplanPreset *preset) {
  return gameplan_preset_write_scoped(team_id, slot, preset, NULL);
}
